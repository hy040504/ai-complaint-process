"""공식 조직도와 조직개편 기록으로 확인한 부서 표기를 정리합니다.

민원 내용으로 담당 부서를 추측하지 않습니다. 폐지되었거나 대응 관계를
확인하지 못한 부서는 department_current를 null로 남깁니다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CHECKED_ON = "2026-10-24"
ORGANIZATION_URL = "https://www.cheongju.go.kr/www/contents.do?key=7431"
REORGANIZATION_URL = (
    "https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/"
    "SvcMntsViewer.php?schSn=3980"
)

# 정확히 일치하는 이름만 치환합니다. 구청명이나 팀명을 임의로 제거하지 않습니다.
DEPARTMENT_ALIASES = {
    "대중교통과": "건설교통국 대중교통과",
    "청주시 대중교통과": "건설교통국 대중교통과",
    "교통정책과": "건설교통국 교통정책과",
    "균형건설과": "건설교통국 균형건설과",
    "도로시설과": "건설교통국 도로시설과",
    "공원관리과": "공원산림본부 공원관리과",
    "공원조성과": "공원산림본부 공원조성과",
    "산림관리과": "공원산림본부 산림관리과",
    "도시개발과": "도시국 도시개발과",
    "도시재생과": "도시국 도시재생과",
    "공동주택과": "주택국 공동주택과",
    "건축디자인과": "주택국 건축디자인과",
    "문화유산과": "문화체육관광국 문화유산과",
    "하천방재과": "재난안전실 하천방재과",
    "경제일자리과": "재정경제국 경제일자리과",
    "경제투자국 경제일자리과": "재정경제국 경제일자리과",
    "경제투자국 기업지원과": "재정경제국 기업지원과",
    "경제투자국 세정과": "재정경제국 세정과",
    "예산과": "재정경제국 예산과",
    "환경관리본부 기후대기과": "환경관리본부 기후에너지과",
    # 과거 부서의 두 표기를 묶되, 현재 부서로 취급하지 않습니다.
    "미래산업과": "경제투자국 미래산업과",
}
RENAMED_DEPARTMENTS = {
    "경제일자리과", "경제투자국 경제일자리과", "경제투자국 기업지원과",
    "경제투자국 세정과", "환경관리본부 기후대기과",
}
RETIRED_DEPARTMENTS = {"미래산업과", "경제투자국 미래산업과"}

# 조직도에서 확인한 현존 부서. 존재 확인은 개별 민원의 이관 확정을 뜻하지 않습니다.
CURRENT_GROUPS = {
    "기획행정실": "정책기획과 자치행정과 민원과 회계과 정보통신과",
    "재난안전실": "안전정책과 재난대응과 하천방재과",
    "재정경제국": "경제일자리과 예산과 기업지원과 세정과",
    "복지국": "복지정책과 통합돌봄과 노인복지과 장애인복지과 여성가족과 아동복지과 위생정책과",
    "문화체육관광국": "문화예술과 문화유산과 체육교육과 관광과 체육시설과 문예운영과",
    "농업정책국": "농업정책과 친환경농산과 농식품유통과 축산과 도매시장관리과",
    "도시국": "도시계획과 도시개발과 도시재생과 지적정보과",
    "건설교통국": "균형건설과 도로시설과 교통정책과 대중교통과",
    "주택국": "건축디자인과 공동주택과 공공시설과",
    "상당보건소": "보건정책과 건강증진과 감염병대응과",
    "농업기술센터": "지원기획과 기술보급과 연구개발과 도시농업관",
    "환경관리본부": "환경정책과 기후에너지과 자원정책과 자원관리과 하수정책과 하수처리과",
    "상수도사업본부": "업무과 시설과 정수과",
    "공원산림본부": "공원관리과 공원조성과 산림관리과",
    "도서관평생학습본부": "시립도서관 오창호수도서관 오송도서관 평생학습관 청주시립도서관 청주오창호수도서관 청주오송도서관",
    "고인쇄박물관": "운영사업과 학예연구실",
    "청주고인쇄박물관": "운영사업과 학예연구실",
}
DISTRICT_OFFICES = "행정지원과 민원지적과 주민복지과 산업교통과 세무과 환경위생과 건설과 건축과"
DISTRICT_NEIGHBORHOODS = {
    "상당구": "낭성면 미원면 가덕면 남일면 문의면 중앙동 성안동 탑대성동 영운동 금천동 용담명암산성동 용암1동 용암2동",
    "서원구": "남이면 현도면 사직1동 사직2동 사창동 모충동 산남동 분평동 수곡1동 수곡2동 성화개신죽림동",
    "흥덕구": "오송읍 강내면 옥산면 운천신봉동 복대1동 복대2동 가경동 봉명1동 봉명2송정동 강서1동 강서2동",
    "청원구": "오창읍 내수읍 북이면 우암동 내덕1동 내덕2동 율량사천동 오근장동",
}
CURRENT_DEPARTMENTS = {
    f"{parent} {child}"
    for parent, children in CURRENT_GROUPS.items()
    for child in children.split()
} | {
    f"{district} {child}"
    for district, neighborhoods in DISTRICT_NEIGHBORHOODS.items()
    for child in (DISTRICT_OFFICES + " " + neighborhoods).split()
} | {
    "대변인", "투자유치단", "상생소통담당관", "청년정책담당관", "감사관", "인사담당관",
    "서원보건소", "흥덕보건소", "청원보건소", "청주시립미술관", "청주랜드관리사업소",
    "차량등록사업소", "청주기록원",
}

# 접수처 전체 문자열을 대조하여 온라인/방문 경로와 규모 조건을 보존합니다.
FAQ_RECEIVED_BY_ALIASES = {
    "대중교통과": "건설교통국 대중교통과",
    "청주시 대중교통과": "건설교통국 대중교통과",
    "균형건설과": "건설교통국 균형건설과",
    "공동주택과": "주택국 공동주택과",
    "공동주택과 주택관리팀": "주택국 공동주택과 주택관리팀",
    "공원관리과": "공원산림본부 공원관리과",
    "기업지원과": "재정경제국 기업지원과",
    "기업지원과, 읍면동 팩스민원신청": "재정경제국 기업지원과, 읍면동 팩스민원신청",
    "구청 건축과 건축팀(6층 이하, 연면적 100㎡이상~2,000㎡이하), 건축디자인과 일반건축물팀(7층 이상, 연면적 2,000㎡이상)":
        "구청 건축과 건축팀(6층 이하, 연면적 100㎡이상~2,000㎡이하), 주택국 건축디자인과 일반건축물팀(7층 이상, 연면적 2,000㎡이상)",
    "시청 민원실 또는 지적정보과(임시청사 별관 1층) / 인터넷 정부24":
        "시청 민원실 또는 도시국 지적정보과(임시청사 별관 1층) / 인터넷 정부24",
    "홈페이지, 전화(043-201-1793), 방문(관광과)":
        "홈페이지, 전화(043-201-1793), 방문(문화체육관광국 관광과)",
    "시청(임시청사 및 제2임시청사) 민원과, 구청 민원지적과, 읍면동 행정복지센터(무인민원발급기 불가, 창구 발급) / 전국 어디서나":
        "시청(임시청사 및 제2임시청사) 기획행정실 민원과, 구청 민원지적과, 읍면동 행정복지센터(무인민원발급기 불가, 창구 발급) / 전국 어디서나",
}


def normalize_public_record(record: dict[str, object]) -> None:
    """원래 표기를 보존하고 확인된 현재 부서와 판정 상태를 갱신합니다.

    Args:
        record: 부서 표기를 갱신할 민원사례입니다. 전달한 객체를 직접 수정합니다.

    Raises:
        ValueError: 보존할 원래 부서명이 문자열이 아닌 경우 발생합니다.
    """
    original = record.setdefault("department_original", record["department"])
    if not isinstance(original, str):
        raise ValueError("department_original은 문자열이어야 합니다.")
    normalized = DEPARTMENT_ALIASES.get(original, original)
    record["department"] = normalized
    if original in RETIRED_DEPARTMENTS or normalized not in CURRENT_DEPARTMENTS:
        record["department_current"] = None
        record["department_status"] = "review_required"
    else:
        record["department_current"] = normalized
        record["department_status"] = (
            "renamed" if original in RENAMED_DEPARTMENTS
            else "normalized" if original != normalized
            else "current"
        )
    record["department_checked_on"] = CHECKED_ON


def normalize_faq_detail(detail: dict[str, str]) -> None:
    """접수 조건을 유지하며 확인된 부서명만 정리합니다.

    Args:
        detail: 접수처를 포함한 FAQ 상세 항목입니다. 전달한 객체를 직접 수정합니다.

    Raises:
        ValueError: 보존할 원래 접수처가 문자열이 아닌 경우 발생합니다.
    """
    original = detail.setdefault("received_by_original", detail["received_by"])
    if not isinstance(original, str):
        raise ValueError("received_by_original은 문자열이어야 합니다.")
    detail["received_by"] = FAQ_RECEIVED_BY_ALIASES.get(original, original)


def write_json(path: Path, data: object) -> None:
    """완성된 JSON을 임시 파일을 거쳐 교체합니다.

    Args:
        path: 완성된 결과를 저장할 경로입니다.
        data: JSON으로 직렬화할 데이터입니다.

    Raises:
        OSError: 파일 기록·권한 보존·교체에 실패한 경우 발생합니다.
    """
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if path.exists():
        temporary.chmod(path.stat().st_mode & 0o777)
    temporary.replace(path)


def main() -> None:
    """명령줄에서 지정한 두 JSON에 확인된 부서 정규화 규칙을 적용합니다."""
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="기존 두 JSON에 확인된 부서 정규화 규칙을 적용합니다.")
    parser.add_argument("--public", type=Path, default=root / "db/공개_민원_사례.json")
    parser.add_argument("--faq", type=Path, default=root / "db/자주_묻는_민원.json")
    args = parser.parse_args()
    cases = json.loads(args.public.read_text(encoding="utf-8"))
    faq = json.loads(args.faq.read_text(encoding="utf-8"))
    case_changes = faq_changes = 0
    for record in cases:
        before = record["department"]
        normalize_public_record(record)
        case_changes += before != record["department"]
    for records in faq.values():
        for record in records:
            detail = record["detail"]
            before = detail["received_by"]
            normalize_faq_detail(detail)
            faq_changes += before != detail["received_by"]
    # 두 파일 모두 변환에 성공한 후 저장합니다.
    write_json(args.public, cases)
    write_json(args.faq, faq)
    reviews = sum(r["department_current"] is None for r in cases)
    print(f"공개 민원 부서명 {case_changes}건, FAQ 접수처 {faq_changes}건 변경; 현재 부서 확인 필요 {reviews}건")


if __name__ == "__main__":
    main()
