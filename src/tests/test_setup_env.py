"""설치 스크립트의 인자·캐시 경로·가상환경 Python 경로를 확인합니다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def setup_env() -> ModuleType:
    """scripts/setup_env.py를 한 번만 불러옵니다."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "setup_env.py"
    spec = importlib.util.spec_from_file_location("setup_env", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_args_check(setup_env: ModuleType) -> None:
    """--check 는 설치를 건너뛰는 확인 모드입니다."""
    args = setup_env.parse_args(["--check", "--skip-db", "--skip-model"])
    assert args.check is True
    assert args.skip_db is True
    assert args.skip_model is True
    assert args.upgrade is False


def test_hub_snapshot_dir(setup_env: ModuleType, tmp_path: Path) -> None:
    """모델 스냅샷 경로는 Hugging Face hub 규칙을 따릅니다."""
    path = setup_env.hub_snapshot_dir(
        tmp_path,
        "dragonkue/multilingual-e5-small-ko",
        "bba4cb8e3299d445c04f62bf62e2b26461d03715",
    )
    assert path == (
        tmp_path
        / "hub"
        / "models--dragonkue--multilingual-e5-small-ko"
        / "snapshots"
        / "bba4cb8e3299d445c04f62bf62e2b26461d03715"
    )


def test_model_cached_false_without_config(setup_env: ModuleType, tmp_path: Path) -> None:
    """config.json이 없으면 모델 캐시가 없는 것으로 봅니다."""
    assert setup_env.model_cached(tmp_path) is False


def test_venv_python_matches_platform(setup_env: ModuleType, tmp_path: Path) -> None:
    """가상환경 Python 파일 이름은 OS에 맞춥니다."""
    python = setup_env.venv_python(tmp_path / ".venv")
    if setup_env.os.name == "nt":
        assert python.name == "python.exe"
        assert python.parent.name == "Scripts"
    else:
        assert python.name == "python"
        assert python.parent.name == "bin"
