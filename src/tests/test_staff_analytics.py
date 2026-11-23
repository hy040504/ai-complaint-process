"""담당자 통계의 시계열·교차·시간대·처리기간 분석 집계를 검증합니다."""

from datetime import datetime, timedelta, timezone

from src.complaints.models import Answer, Complaint
from src.complaints.staff_reports import build_staff_analytics

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 23, 12, 0, tzinfo=KST)  # 월요일


def _row(
    cid: str,
    created: datetime,
    *,
    category: str = "도로·교통",
    district: str = "상당구",
    answered_at: datetime | None = None,
) -> Complaint:
    """분석 집계 시험용 민원을 만듭니다."""
    published = (
        Answer(text="답변", origin="staff", reason="시험", date=answered_at)
        if answered_at
        else None
    )
    return Complaint(
        id=cid,
        owner="citizen-01",
        title="제목",
        body="본문",
        district=district,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        visibility="public",
        date=created,
        published=published,
    )


def test_trends_bucket_received_and_resolved_by_kst_day() -> None:
    """일 단위 시계열은 오늘이 마지막 칸이며 접수와 답변 게시를 따로 센다."""
    rows = [
        _row("A", NOW - timedelta(hours=1)),
        _row("B", NOW - timedelta(days=1), answered_at=NOW - timedelta(hours=2)),
        _row("C", NOW - timedelta(days=20)),
    ]
    result = build_staff_analytics(rows, now=NOW)
    day = next(t for t in result.trends if t.unit == "day")
    assert len(day.labels) == len(day.received) == len(day.resolved) == 14
    assert day.received[-1] == 1 and day.received[-2] == 1
    assert sum(day.received) == 2
    assert day.resolved[-1] == 1 and sum(day.resolved) == 1
    assert day.labels[-1] == "11/23"
    assert day.category_received["도로·교통"] == day.received
    assert sum(sum(v) for v in day.category_received.values()) == sum(day.received)
    month = next(t for t in result.trends if t.unit == "month")
    assert month.labels[-1] == "26.11" and month.received[-1] == 3


def test_cross_hours_and_resolution_summary() -> None:
    """지역×분야 교차·요일×시각 행렬·처리기간 구간이 일관되게 계산된다."""
    created = datetime(2026, 11, 18, 9, 30, tzinfo=KST)  # 수요일 9시
    rows = [
        _row("A", created, answered_at=created + timedelta(hours=12)),
        _row(
            "B",
            created,
            category="환경·청소",
            district="서원구",
            answered_at=created + timedelta(days=5),
        ),
        _row("C", created),
    ]
    result = build_staff_analytics(rows, now=NOW)
    assert result.hour_weekday[2][9] == 3
    cross = {row.district: row for row in result.district_category}
    assert cross["상당구"].total == 2
    assert cross["서원구"].counts[result.categories.index("환경·청소")] == 1
    buckets = {b.key: b.count for b in result.resolution_buckets}
    assert buckets == {"within1": 1, "within3": 0, "within7": 1, "over7": 0}
    resolution = {r.category: r for r in result.resolution_by_category}
    assert resolution["도로·교통"].avg_days == 0.5
    assert resolution["기타"].avg_days is None
    assert result.resolve_rate == 66.7
    assert result.ai_first_response_rate == 0.0
    assert result.category_trends[0].category == "도로·교통"
    assert result.category_trends[0].total == 2


def test_empty_rows_produce_zero_filled_analytics() -> None:
    """민원이 없어도 모든 시계열은 고정 길이 0으로 채워진다."""
    result = build_staff_analytics([], now=NOW)
    assert [len(t.received) for t in result.trends] == [14, 8, 12]
    assert len(result.hour_weekday) == 7 and len(result.hour_weekday[0]) == 24
    assert result.resolve_rate == 0.0


def test_category_change_compares_completed_months_only() -> None:
    """분야 증감률은 진행 중인 이번 달을 빼고 지난달을 지지난달과 비교한다."""
    rows = [
        _row("A", datetime(2026, 9, 10, 10, tzinfo=KST)),
        _row("B", datetime(2026, 9, 11, 10, tzinfo=KST)),
        _row("C", datetime(2026, 10, 10, 10, tzinfo=KST)),
        _row("D", datetime(2026, 11, 3, 10, tzinfo=KST)),
        _row("E", datetime(2026, 11, 4, 10, tzinfo=KST)),
        _row("F", datetime(2026, 11, 5, 10, tzinfo=KST)),
    ]
    result = build_staff_analytics(rows, now=NOW)
    trend = next(t for t in result.category_trends if t.category == "도로·교통")
    assert trend.counts[-3:] == [2, 1, 3]
    assert trend.change_pct == -50.0


def test_unknown_category_does_not_break_trends() -> None:
    """분야 목록에 없는 값이 있어도 접수 건수만 세고 분야별 집계는 건너뛴다."""
    row = _row("A", NOW - timedelta(hours=1))
    object.__setattr__(row, "category", "목록밖분야")
    result = build_staff_analytics([row], now=NOW)
    day = next(t for t in result.trends if t.unit == "day")
    assert day.received[-1] == 1
    assert "목록밖분야" not in day.category_received
