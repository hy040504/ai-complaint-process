"""청주시 현행 부서 디렉터리를 조회·검증하는 시연 포털용 helper입니다."""

from __future__ import annotations

from functools import lru_cache
import json
from threading import Lock
import time

from src.complaints.config import ROOT
from src.complaints.models import DepartmentEntry
from src.rag import departments_via_api

_DISTRICTS: tuple[str, ...] = ("상당구", "서원구", "흥덕구", "청원구")
_CASES_PATH = ROOT / "rag" / "origin" / "공개_민원_사례.json"
_REMOTE_CACHE_TTL = 60.0
_remote_lock = Lock()
_remote_cache: tuple[float, tuple[DepartmentEntry, ...]] | None = None


def _infer_district(name: str) -> str | None:
    """부서 이름에 포함된 자치구 이름을 추출합니다.

    Args:
        name: 정규화된 청주시 부서명입니다.

    Returns:
        포함된 4대 자치구 이름 또는 본청·직속기관인 경우 None입니다.
    """
    for district in _DISTRICTS:
        if district in name:
            return district
    return None


@lru_cache(maxsize=1)
def _fallback_departments() -> tuple[DepartmentEntry, ...]:
    """검색 API 미연결 시 공개 민원 사례 JSON에서 현행 부서 목록을 읽습니다.

    최초 1회만 원본 JSON을 파싱하고 이후 호출에서는 메모리 캐시를 재사용합니다.

    Returns:
        정규화 상태가 `review_required`가 아닌 정렬된 부서 목록입니다.
    """
    if not _CASES_PATH.is_file():
        return ()
    raw = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw.get("cases", raw.get("records", []))
    names = sorted(
        {
            str(item["department_current"]).strip()
            for item in items
            if isinstance(item, dict)
            and item.get("department_current")
            and item.get("department_status") != "review_required"
        }
    )
    return tuple(
        DepartmentEntry(
            canonical_name=name,
            district=_infer_district(name),
            duty_status="unverified",
            jurisdiction_status="inferred_from_name",
            automatic_transfer=False,
        )
        for name in names
    )


def _fetch_remote_departments() -> tuple[DepartmentEntry, ...]:
    """검색 API 부서 디렉터리 응답을 짧은 TTL 캐시로 조회합니다.

    매 화면 이동·배정 요청마다 `:8007/departments`로 HTTP 요청을 반복하지 않도록
    성공한 응답만 메모리 캐시에 보관하고, 실패 시 빈 튜플을 돌려 fallback으로 넘깁니다.

    Returns:
        검색 API에서 읽어 정규화한 부서 튜플입니다. 실패 시 빈 튜플입니다.
    """
    global _remote_cache
    now = time.monotonic()
    with _remote_lock:
        if _remote_cache and now - _remote_cache[0] < _REMOTE_CACHE_TTL:
            return _remote_cache[1]
    try:
        remote_rows = departments_via_api()
    except (ValueError, OSError, TimeoutError):
        return ()
    entries = tuple(
        sorted(
            (
                DepartmentEntry(
                    canonical_name=str(item["canonical_name"]).strip(),
                    district=(
                        str(item["district"]).strip()
                        if item.get("district")
                        else _infer_district(str(item["canonical_name"]))
                    ),
                    duty_status=str(item.get("duty_status") or "unverified"),
                    jurisdiction_status=str(
                        item.get("jurisdiction_status") or "inferred_from_name"
                    ),
                    automatic_transfer=False,
                )
                for item in remote_rows
                if item.get("canonical_name")
            ),
            key=lambda entry: entry.canonical_name,
        )
    )
    if entries:
        with _remote_lock:
            _remote_cache = (time.monotonic(), entries)
    return entries


def load_department_directory(*, prefer_remote: bool = True) -> list[DepartmentEntry]:
    """청주시 현행 부서 디렉터리 목록을 정렬해 반환합니다.

    검색 API 연결이 활성화된 경우 `:8007/departments` 캐시를 먼저 사용하고,
    미연결 또는 테스트 환경에서는 저장소 원본 JSON fallback을 사용합니다.

    Args:
        prefer_remote: 검색 API 조회를 먼저 시도할지 여부입니다.

    Returns:
        검증된 이름·관할 추론 정보가 포함된 부서 목록입니다.
    """
    if prefer_remote:
        remote_entries = _fetch_remote_departments()
        if remote_entries:
            return list(remote_entries)
    return list(_fallback_departments())


def valid_department_names(*, prefer_remote: bool = False) -> frozenset[str]:
    """배정 입력 검증에 사용할 허용 부서 이름 집합을 반환합니다.

    Args:
        prefer_remote: 검증 시 원격 검색 API 목록도 우선 조회할지 여부입니다.

    Returns:
        정규화 부서명 집합입니다.
    """
    return frozenset(
        entry.canonical_name
        for entry in load_department_directory(prefer_remote=prefer_remote)
    )
