"""검사기 테스트 기록 JSON 저장을 확인합니다."""

from pathlib import Path

from src.lab_web.runs import (
    RUN_ID_RE,
    clear_runs,
    list_runs,
    load_run,
    new_run_id,
    save_run,
)


def test_save_list_load_and_clear(tmp_path: Path) -> None:
    """기록 파일을 쓰고 최신순으로 읽은 뒤 지웁니다."""
    directory = tmp_path / "runs"
    first = save_run(
        directory,
        payload={
            "title": "첫번째",
            "category": "기타",
            "district": None,
            "body": "내용입니다.",
        },
        received={"assist": {"outcome": "faq_answer", "reasonCode": "ok"}},
        run_id="20261106T010000Z-aaa11111",
    )
    second = save_run(
        directory,
        payload={
            "title": "두번째",
            "category": "기타",
            "district": None,
            "body": "내용입니다.",
        },
        received={
            "assist": {"outcome": "human_handoff", "reasonCode": "condition_unclear"}
        },
        run_id="20261106T020000Z-bbb22222",
    )
    assert RUN_ID_RE.fullmatch(first["id"])
    names = [item["title"] for item in list_runs(directory)]
    assert names == ["두번째", "첫번째"]
    loaded = load_run(directory, second["id"])
    assert loaded is not None
    assert loaded["received"]["assist"]["outcome"] == "human_handoff"
    assert load_run(directory, "../escape") is None
    assert clear_runs(directory) == 2
    assert list_runs(directory) == []


def test_new_run_id_is_filename_safe() -> None:
    """새 ID는 JSON 파일 이름으로 쓸 수 있습니다."""
    ident = new_run_id()
    assert RUN_ID_RE.fullmatch(ident)
    assert "/" not in ident
    assert "\\" not in ident
