"""검사기 테스트 기록을 JSON 파일로 남깁니다.

민원 CRUD 테이블과 RAG 원본에는 쓰지 않습니다. Git에도 올리지 않습니다.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = ROOT / ".rag-cache" / "lab-runs"
RUN_ID_RE = re.compile(r"^[0-9A-Za-z-]{10,64}$")


def default_runs_dir() -> Path:
    """기록 폴더를 고릅니다.

    Returns:
        `LAB_RUNS_DIR`이 있으면 그 경로, 없으면 `.rag-cache/lab-runs`입니다.
    """
    raw = os.environ.get("LAB_RUNS_DIR", "").strip()
    return Path(raw) if raw else DEFAULT_RUNS_DIR


def new_run_id() -> str:
    """파일 이름에 쓸 기록 ID를 만듭니다."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def run_path(directory: Path, run_id: str) -> Path:
    """기록 파일 경로를 돌려줍니다.

    Args:
        directory: 기록 폴더입니다.
        run_id: 허용된 ID입니다.

    Returns:
        `{id}.json` 경로입니다.

    Raises:
        ValueError: ID가 파일 이름 규칙을 벗어나면 발생합니다.
    """
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("기록 ID가 올바르지 않습니다.")
    return directory / f"{run_id}.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """임시 파일에 쓴 뒤 교체합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def save_run(
    directory: Path,
    *,
    payload: dict[str, Any],
    received: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    """검사 결과 한 건을 JSON 파일로 저장합니다.

    Args:
        directory: 기록 폴더입니다.
        payload: 검사기에 보낸 민원입니다.
        received: 검색·판정 응답입니다.
        run_id: 있으면 이 ID를 쓰고, 없으면 새로 만듭니다.

    Returns:
        저장한 기록 딕셔너리입니다.
    """
    ident = run_id or new_run_id()
    assist = received.get("assist") or {}
    record = {
        "id": ident,
        "at": datetime.now(timezone.utc).isoformat(),
        "title": str(payload.get("title") or ""),
        "outcome": str(assist.get("outcome") or ""),
        "reasonCode": str(assist.get("reasonCode") or ""),
        "payload": payload,
        "received": received,
    }
    _write_json(run_path(directory, ident), record)
    return record


def list_runs(directory: Path) -> list[dict[str, Any]]:
    """기록 요약 목록을 최신순으로 돌려줍니다.

    Args:
        directory: 기록 폴더입니다.

    Returns:
        `id`·`at`·`title`·`outcome`·`reasonCode` 목록입니다.
    """
    if not directory.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        items.append(
            {
                "id": str(raw.get("id") or path.stem),
                "at": str(raw.get("at") or ""),
                "title": str(raw.get("title") or ""),
                "outcome": str(raw.get("outcome") or ""),
                "reasonCode": str(raw.get("reasonCode") or ""),
            }
        )
    items.sort(
        key=lambda item: (str(item.get("at") or ""), str(item.get("id") or "")),
        reverse=True,
    )
    return items


def load_run(directory: Path, run_id: str) -> dict[str, Any] | None:
    """기록 한 건을 읽습니다.

    Args:
        directory: 기록 폴더입니다.
        run_id: 기록 ID입니다.

    Returns:
        기록 딕셔너리입니다. 없거나 ID가 잘못되면 None입니다.
    """
    try:
        path = run_path(directory, run_id)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def clear_runs(directory: Path) -> int:
    """기록 JSON을 모두 지웁니다.

    Args:
        directory: 기록 폴더입니다.

    Returns:
        삭제한 파일 수입니다.
    """
    if not directory.is_dir():
        return 0
    removed = 0
    for path in directory.glob("*.json"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed
