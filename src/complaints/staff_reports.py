"""담당자 업무 목록의 검색·정렬, 통계 집계, 안전 CSV 생성을 담당하는 순수 로직입니다.

서비스(`ComplaintService`)가 저장소 조회와 권한 검사를 마친 민원 목록을 받아,
조회 경계와 무관한 계산만 수행합니다. 네트워크·저장소·스레드에 의존하지 않아
단독으로 검증하기 쉽습니다.
"""

import csv
import io
from datetime import date, datetime, timedelta, timezone

from src.complaints.models import (
    CATEGORIES,
    Actor,
    Complaint,
    NormalizedDbSummary,
    PublicComplaint,
    StaffAnalytics,
    StaffCategoryTrend,
    StaffCrossRow,
    StaffExportQuery,
    StaffOperationalMetrics,
    StaffResolutionRow,
    StaffStatsBucket,
    StaffStatsResponse,
    StaffTrendSeries,
    utcnow,
)

STATUS_LABELS: dict[str, str] = {
    "submitted": "접수 대기",
    "under_review": "검토 중",
    "answered": "답변 완료",
    "closed": "처리 종료",
    "withdrawn": "철회",
}

AI_OUTCOME_LABELS: dict[str, str] = {
    "faq_answer": "공식 FAQ 안내",
    "department_suggestion": "담당 부서 후보",
    "human_handoff": "담당자 검토 필요",
    "none": "AI 분석 전/미완료",
}

JOB_STATUS_LABELS: dict[str, str] = {
    "queued": "분석 대기",
    "running": "AI 분석 중",
    "succeeded": "분석 완료",
    "failed": "분석 실패",
    "cancelled": "작업 취소",
    "superseded": "맥락 변경",
}

STATS_DISTRICTS: tuple[str, ...] = ("상당구", "서원구", "흥덕구", "청원구", "모름")


def csv_safe_cell(value: object) -> str:
    """엑셀 수식 주입(CSV Formula Injection)을 차단하도록 셀 문자열을 정제합니다.

    Args:
        value: CSV 셀에 기록할 원시 값입니다.

    Returns:
        수식 선두 문자(`=`, `+`, `-`, `@`, 탭, CR)를 중화한 안전한 문자열입니다.
    """
    text = "" if value is None else str(value)
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def matches_search(
    row: PublicComplaint | Complaint, query_text: str, *, include_staff_fields: bool
) -> bool:
    """민원 제목·본문·식별자(및 담당자 화면의 배정 부서)를 통합 검색합니다.

    Args:
        row: 검사할 민원 모델입니다.
        query_text: 사용자가 입력한 검색어입니다.
        include_staff_fields: 담당자 전용 배정 부서명까지 함께 검색할지 여부입니다.

    Returns:
        검색어가 비었거나 대상 필드 중 하나에 부분 일치하면 True입니다.
    """
    needle = (query_text or "").strip().casefold()
    if not needle:
        return True
    if (
        needle in row.title.casefold()
        or needle in row.body.casefold()
        or needle in row.id.casefold()
    ):
        return True
    if include_staff_fields and isinstance(row, Complaint) and row.department:
        return needle in row.department.casefold()
    return False


def in_staff_scope(actor: Actor, row: Complaint) -> bool:
    """담당자의 부서 RBAC 소관 범위에 속하는 민원인지 판정합니다.

    총괄 담당자(`actor.department is None`)는 모든 민원을 집계·내보내기하며,
    부서 담당자는 미배정 민원과 본인 소속 부서에 배정된 민원만 포함합니다.

    Args:
        actor: 통계를 조회하거나 CSV를 내보내는 담당자입니다.
        row: 검사할 민원 레코드입니다.

    Returns:
        담당자 소관 범위이면 True입니다.
    """
    if not actor.department:
        return True
    return not row.department or row.department == actor.department


def filter_and_sort_staff_rows(
    rows: list[Complaint], query: StaffExportQuery
) -> list[Complaint]:
    """담당자 업무 목록의 통합 검색·AI 판정·시연 제외·정렬 조건을 일관되게 적용합니다.

    Args:
        rows: RBAC 소관 범위 필터를 통과한 활성 민원 목록입니다.
        query: 검증된 필터·정렬 쿼리 모델입니다.

    Returns:
        조건과 정렬이 적용된 민원 목록입니다.
    """
    filtered: list[Complaint] = []
    for row in rows:
        if not query.include_synthetic and row.is_synthetic:
            continue
        if not matches_search(row, query.q, include_staff_fields=True):
            continue
        if query.status and row.status != query.status:
            continue
        if query.district and row.district != query.district:
            continue
        if query.category and row.category != query.category:
            continue
        if query.assign:
            has_assignee = row.assigned or bool(row.department)
            if has_assignee != (query.assign == "mine"):
                continue
        if query.view:
            if query.view == "followup" and not row.messages:
                continue
            if query.view == "drafts" and not (row.draft and not row.published):
                continue
            if query.view == "failed" and row.job.status != "failed":
                continue
            if query.view == "published" and row.published is None:
                continue
        if query.ai_outcome:
            if query.ai_outcome == "none":
                if row.ai_assist is not None:
                    continue
            elif row.ai_assist is None or row.ai_assist.outcome != query.ai_outcome:
                continue
        filtered.append(row)

    if query.sort == "oldest_open":
        filtered.sort(
            key=lambda r: (
                0 if r.status in ("submitted", "under_review") else 1,
                r.date,
                r.id,
            )
        )
    elif query.sort == "most_followups":
        filtered.sort(key=lambda r: (-len(r.messages), -r.date.timestamp(), r.id))
    elif query.sort == "unpublished_first":
        filtered.sort(
            key=lambda r: (
                0 if (r.draft and not r.published) else 1,
                -r.date.timestamp(),
                r.id,
            )
        )
    else:
        filtered.sort(key=lambda r: (r.date, r.id), reverse=True)
    return filtered


KST = timezone(timedelta(hours=9))
TREND_SPANS: tuple[tuple[str, int], ...] = (("day", 14), ("week", 8), ("month", 12))
CATEGORY_TREND_MONTHS = 6
RESOLUTION_BUCKETS: tuple[tuple[str, str, float], ...] = (
    ("within1", "1일 이내", 1.0),
    ("within3", "1~3일", 3.0),
    ("within7", "3~7일", 7.0),
    ("over7", "7일 초과", float("inf")),
)


def _to_kst(value: datetime) -> datetime:
    """시각을 한국 표준시로 바꿉니다. 시간대 정보가 없으면 UTC로 간주합니다.

    Args:
        value: 변환할 시각입니다.

    Returns:
        KST로 변환한 시각입니다.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(KST)


def _month_index(value: datetime) -> int:
    """KST 기준 연·월을 단조 증가하는 정수(연*12+월-1)로 바꿉니다.

    Args:
        value: KST로 맞춘 시각입니다.

    Returns:
        월 단위 비교용 정수입니다.
    """
    return value.year * 12 + value.month - 1


def _period_index(unit: str, value: datetime, today: date) -> int:
    """KST 시각이 오늘 기준 몇 번째 이전 구간인지 구합니다. 0이 현재 구간입니다.

    Args:
        unit: 집계 단위(`day`·`week`·`month`)입니다.
        value: KST로 맞춘 대상 시각입니다.
        today: KST 기준 오늘 날짜입니다.

    Returns:
        현재 구간이면 0, 이전 구간일수록 큰 정수입니다.
    """
    if unit == "day":
        return (today - value.date()).days
    if unit == "week":
        monday = today - timedelta(days=today.weekday())
        value_monday = value.date() - timedelta(days=value.weekday())
        return (monday - value_monday).days // 7
    return _month_index(datetime(today.year, today.month, 1)) - _month_index(value)


def _period_label(unit: str, back: int, today: date) -> str:
    """오늘 기준 `back` 구간 이전의 표시 문구를 만듭니다.

    Args:
        unit: 집계 단위(`day`·`week`·`month`)입니다.
        back: 현재 구간에서 거슬러 올라갈 구간 수입니다.
        today: KST 기준 오늘 날짜입니다.

    Returns:
        일(`11/23`)·주(`11/23주`)·월(`26.11`) 형식의 표시 문구입니다.
    """
    if unit == "day":
        target = today - timedelta(days=back)
        return f"{target.month}/{target.day}"
    if unit == "week":
        monday = today - timedelta(days=today.weekday()) - timedelta(weeks=back)
        return f"{monday.month}/{monday.day}주"
    month = today.year * 12 + today.month - 1 - back
    return f"{month // 12 % 100:02d}.{month % 12 + 1:02d}"


def build_staff_analytics(rows: list[Complaint], *, now: datetime) -> StaffAnalytics:
    """소관 범위 민원으로 시계열·교차·시간대·처리기간 분석 집계를 만듭니다.

    Args:
        rows: 시연 포함 여부 필터를 마친 소관 범위 민원 목록입니다.
        now: 구간 기준이 되는 현재 시각입니다.

    Returns:
        통계 분석·민원 분류 탭용 `StaffAnalytics`입니다. 날짜는 KST 기준입니다.
    """
    today = _to_kst(now).date()
    trends: list[StaffTrendSeries] = []
    for unit, span in TREND_SPANS:
        received = [0] * span
        resolved = [0] * span
        by_category = {str(cat): [0] * span for cat in CATEGORIES}
        for row in rows:
            back = _period_index(unit, _to_kst(row.date), today)
            if 0 <= back < span:
                received[span - 1 - back] += 1
                if row.category in by_category:
                    by_category[row.category][span - 1 - back] += 1
            if row.published is not None:
                back = _period_index(unit, _to_kst(row.published.date), today)
                if 0 <= back < span:
                    resolved[span - 1 - back] += 1
        trends.append(
            StaffTrendSeries(
                unit=unit,  # type: ignore[arg-type]
                labels=[_period_label(unit, span - 1 - i, today) for i in range(span)],
                received=received,
                resolved=resolved,
                category_received=by_category,
            )
        )

    months = CATEGORY_TREND_MONTHS
    categories: list[str] = [str(cat) for cat in CATEGORIES]
    cat_series = {cat: [0] * months for cat in categories}
    district_names = list(STATS_DISTRICTS)
    cross = {d: [0] * len(categories) for d in district_names}
    hours = [[0] * 24 for _ in range(7)]
    durations: dict[str, list[float]] = {cat: [] for cat in categories}
    bucket_counts = {key: 0 for key, _, _ in RESOLUTION_BUCKETS}

    for row in rows:
        created = _to_kst(row.date)
        back = _period_index("month", created, today)
        if row.category in cat_series and 0 <= back < months:
            cat_series[row.category][months - 1 - back] += 1
        if row.district in cross and row.category in categories:
            cross[row.district][categories.index(row.category)] += 1
        hours[created.weekday()][created.hour] += 1
        if row.published is not None:
            elapsed = _to_kst(row.published.date) - created
            days = max(0.0, elapsed.total_seconds() / 86400.0)
            if row.category in durations:
                durations[row.category].append(days)
            for key, _, limit in RESOLUTION_BUCKETS:
                if days <= limit:
                    bucket_counts[key] += 1
                    break

    category_trends = []
    for cat in categories:
        counts = cat_series[cat]
        # 이번 달은 진행 중이라 비교에서 빼고, 끝난 직전 두 달(지난달·지지난달)만 비교한다.
        prev, last = counts[-3], counts[-2]
        category_trends.append(
            StaffCategoryTrend(
                category=cat,
                counts=counts,
                total=sum(counts),
                change_pct=round((last - prev) / prev * 100.0, 1) if prev else None,
            )
        )
    category_trends.sort(key=lambda item: (-item.total, item.category))

    with_ai = [row for row in rows if row.ai_assist is not None]
    faq_done = sum(
        1 for row in with_ai if row.ai_assist and row.ai_assist.outcome == "faq_answer"
    )
    published = sum(1 for row in rows if row.published is not None)
    return StaffAnalytics(
        trends=trends,
        month_labels=[
            _period_label("month", months - 1 - i, today) for i in range(months)
        ],
        category_trends=category_trends,
        categories=categories,
        district_category=[
            StaffCrossRow(district=d, counts=cross[d], total=sum(cross[d]))
            for d in district_names
        ],
        hour_weekday=hours,
        resolution_by_category=[
            StaffResolutionRow(
                category=cat,
                resolved=len(durations[cat]),
                avg_days=(
                    round(sum(durations[cat]) / len(durations[cat]), 1)
                    if durations[cat]
                    else None
                ),
            )
            for cat in categories
        ],
        resolution_buckets=[
            StaffStatsBucket(key=key, label=label, count=bucket_counts[key])
            for key, label, _ in RESOLUTION_BUCKETS
        ],
        ai_first_response_rate=(
            round(faq_done / len(with_ai) * 100.0, 1) if with_ai else 0.0
        ),
        resolve_rate=round(published / len(rows) * 100.0, 1) if rows else 0.0,
    )


def build_staff_stats(
    actor: Actor,
    scoped_all: list[Complaint],
    *,
    include_synthetic: bool,
    db_summary: NormalizedDbSummary,
) -> StaffStatsResponse:
    """담당자 소관 범위 민원으로 운영 KPI·드릴다운 차트·DB 요약 응답을 만듭니다.

    Args:
        actor: 통계를 조회한 담당자입니다. 소속 부서로 범위 표시 문구를 정합니다.
        scoped_all: RBAC 소관 범위를 통과한 활성 민원 전체(시연 데이터 포함)입니다.
        include_synthetic: 공개 시연 데이터(`DEMO-*`)를 집계에 포함할지 여부입니다.
        db_summary: 정규화 7테이블 행 수·AI 집계 요약입니다.

    Returns:
        권한 범위가 적용된 `StaffStatsResponse` 모델입니다.
    """
    real_count = sum(1 for row in scoped_all if not row.is_synthetic)
    synthetic_count = sum(1 for row in scoped_all if row.is_synthetic)
    rows = (
        scoped_all
        if include_synthetic
        else [row for row in scoped_all if not row.is_synthetic]
    )

    now = utcnow()
    open_rows = [row for row in rows if row.status in ("submitted", "under_review")]
    avg_open_days = (
        round(
            sum(
                max(0.0, (now - row.date).total_seconds() / 86400.0)
                for row in open_rows
            )
            / len(open_rows),
            1,
        )
        if open_rows
        else 0.0
    )
    operational = StaffOperationalMetrics(
        open_count=len(open_rows),
        submitted_count=sum(1 for r in rows if r.status == "submitted"),
        under_review_count=sum(1 for r in rows if r.status == "under_review"),
        answered_count=sum(1 for r in rows if r.status == "answered"),
        unassigned_count=sum(1 for r in rows if not r.assigned and not r.department),
        unpublished_drafts=sum(1 for r in rows if bool(r.draft and not r.published)),
        with_followups=sum(1 for r in rows if bool(r.messages)),
        ai_failed=sum(1 for r in rows if r.job.status == "failed"),
        ai_running=sum(1 for r in rows if r.job.status == "running"),
        published_count=sum(1 for r in rows if r.published is not None),
        avg_open_days=avg_open_days,
    )

    by_status = [
        StaffStatsBucket(
            key=key,
            label=STATUS_LABELS[key],
            count=sum(1 for r in rows if r.status == key),
            filter_key="status",
            filter_value=key,
        )
        for key in ("submitted", "under_review", "answered", "closed")
    ]
    by_district = [
        StaffStatsBucket(
            key=dist,
            label=dist,
            count=sum(1 for r in rows if r.district == dist),
            filter_key="district",
            filter_value=dist,
        )
        for dist in STATS_DISTRICTS
    ]
    by_category = [
        StaffStatsBucket(
            key=cat,
            label=cat,
            count=sum(1 for r in rows if r.category == cat),
            filter_key="category",
            filter_value=cat,
        )
        for cat in CATEGORIES
    ]
    by_ai_outcome = [
        StaffStatsBucket(
            key=key,
            label=AI_OUTCOME_LABELS[key],
            count=sum(
                1
                for r in rows
                if (
                    r.ai_assist is None
                    if key == "none"
                    else (r.ai_assist is not None and r.ai_assist.outcome == key)
                )
            ),
            filter_key="aiOutcome",
            filter_value=key,
        )
        for key in ("faq_answer", "department_suggestion", "human_handoff", "none")
    ]

    dept_counts: dict[str, int] = {}
    unassigned_dept_count = 0
    for row in rows:
        if row.department:
            dept_counts[row.department] = dept_counts.get(row.department, 0) + 1
        else:
            unassigned_dept_count += 1
    by_department = [
        StaffStatsBucket(
            key=dept,
            label=dept,
            count=cnt,
            filter_key="q",
            filter_value=dept,
        )
        for dept, cnt in sorted(
            dept_counts.items(), key=lambda pair: (-pair[1], pair[0])
        )[:10]
    ]
    if unassigned_dept_count > 0 or not by_department:
        by_department.append(
            StaffStatsBucket(
                key="unassigned",
                label="부서 미배정",
                count=unassigned_dept_count,
                filter_key="assign",
                filter_value="none",
            )
        )

    scope_label = (
        f"{actor.department} 소관 + 미배정"
        if actor.department
        else "청주시 전체 민원 (총괄)"
    )
    return StaffStatsResponse(
        scope_label=scope_label,
        is_admin_scope=actor.department is None,
        include_synthetic=include_synthetic,
        total_complaints=len(rows),
        real_complaints=real_count,
        synthetic_complaints=synthetic_count,
        operational=operational,
        by_status=by_status,
        by_district=by_district,
        by_category=by_category,
        by_ai_outcome=by_ai_outcome,
        by_department=by_department,
        analytics=build_staff_analytics(rows, now=now),
        db_summary=db_summary,
    )


def build_complaints_csv(rows: list[Complaint]) -> str:
    """담당자 업무 메타데이터를 엑셀 수식 주입을 중화한 UTF-8 BOM CSV 문자열로 만듭니다.

    미게시 AI 초안·원문·순화 본문은 열에 포함하지 않습니다.

    Args:
        rows: 필터·정렬을 마친 민원 목록입니다.

    Returns:
        BOM(`\\ufeff`)으로 시작하는 CSV 문자열입니다.
    """
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(
        [
            "민원ID",
            "등록일",
            "상태",
            "관할구",
            "분야",
            "제목",
            "공개구분",
            "시연데이터",
            "배정부서",
            "담당자",
            "AI판정",
            "AI사유",
            "작업상태",
            "답변게시여부",
            "추가문의수",
        ]
    )
    for row in rows:
        ai_outcome_label = (
            AI_OUTCOME_LABELS.get(row.ai_assist.outcome, row.ai_assist.outcome)
            if row.ai_assist is not None
            else AI_OUTCOME_LABELS["none"]
        )
        ai_reason = row.ai_assist.reason_code if row.ai_assist is not None else ""
        writer.writerow(
            [
                csv_safe_cell(row.id),
                csv_safe_cell(row.date.strftime("%Y-%m-%d %H:%M")),
                csv_safe_cell(STATUS_LABELS.get(row.status, row.status)),
                csv_safe_cell(row.district),
                csv_safe_cell(row.category),
                csv_safe_cell(row.title),
                csv_safe_cell("공개" if row.visibility == "public" else "비공개"),
                csv_safe_cell("시연" if row.is_synthetic else "실제"),
                csv_safe_cell(row.department or "미배정"),
                csv_safe_cell(
                    row.assignee_name or ("담당 지정" if row.assigned else "미지정")
                ),
                csv_safe_cell(ai_outcome_label),
                csv_safe_cell(ai_reason),
                csv_safe_cell(JOB_STATUS_LABELS.get(row.job.status, row.job.status)),
                csv_safe_cell("게시됨" if row.published is not None else "미게시"),
                str(len(row.messages)),
            ]
        )
    return buf.getvalue()
