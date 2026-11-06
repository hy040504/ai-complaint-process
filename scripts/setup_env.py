"""프로젝트 실행에 필요한 가상환경·PostgreSQL·임베딩 모델을 준비합니다.

Docker는 쓰지 않습니다. 이미 있는 가상환경·DB·모델 캐시는 지우지 않고
부족한 항목만 받습니다. 검색 원본 5,109건 적재(`python -m rag ingest`)는
이 스크립트의 기본 범위가 아닙니다.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF_HOME_DEFAULT = ROOT / ".rag-cache" / "huggingface"
PG_DATA = ROOT / ".rag-data" / "postgres"
PG_PREFIX = ROOT / ".rag-data" / "pgsql"
DOWNLOAD_DIR = ROOT / ".rag-data" / "downloads"

TORCH_CPU_VERSION = "2.9.1"
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
PG_ZIP_NAME = "postgresql-18.6-1-windows-x64-binaries.zip"
PG_ZIP_URL = f"https://get.enterprisedb.com/postgresql/{PG_ZIP_NAME}"
PGVECTOR_ZIP_NAME = "vector.v0.8.7-pg18.zip"
PGVECTOR_ZIP_URL = (
    "https://github.com/andreiramani/pgvector_pgsql_windows/"
    f"releases/download/0.8.7/{PGVECTOR_ZIP_NAME}"
)
EMBEDDING_REPO = "dragonkue/multilingual-e5-small-ko"
EMBEDDING_REVISION = "bba4cb8e3299d445c04f62bf62e2b26461d03715"
DATABASE_NAME = "complaints_native"
APP_SQL = ROOT / "src" / "complaints" / "schema" / "complaint_app.sql"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """설치 인자를 해석합니다.

    Args:
        argv: 인자 목록입니다. None이면 `sys.argv`를 씁니다.

    Returns:
        해석한 이름공간입니다.
    """
    parser = argparse.ArgumentParser(
        description=(
            "가상환경, PostgreSQL/pgvector, 임베딩 모델을 준비합니다. "
            "이미 있는 항목은 다시 받지 않습니다."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="설치하지 않고 가상환경·DB 바이너리·모델 캐시만 확인합니다.",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="이미 있는 pip 패키지도 요구 파일 기준으로 다시 설치합니다.",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="PostgreSQL 다운로드·계정·확장 준비를 건너뜁니다.",
    )
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="Hugging Face 임베딩 모델 다운로드를 건너뜁니다.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help=".venv-web에 src/requirements-dev.txt 를 설치합니다.",
    )
    return parser.parse_args(argv)


def hf_home() -> Path:
    """모델 캐시 루트를 반환합니다.

    Returns:
        `HF_HOME` 또는 저장소 `.rag-cache/huggingface`입니다.
    """
    raw = os.environ.get("HF_HOME", "").strip()
    return Path(raw) if raw else HF_HOME_DEFAULT


def hub_snapshot_dir(cache_root: Path, repo_id: str, revision: str) -> Path:
    """Hugging Face hub 스냅샷 디렉터리를 계산합니다.

    Args:
        cache_root: `HF_HOME`입니다.
        repo_id: `org/name` 형식의 저장소입니다.
        revision: 커밋 해시 또는 태그입니다.

    Returns:
        `config.json`이 있어야 하는 스냅샷 경로입니다.
    """
    folder = "models--" + repo_id.replace("/", "--")
    return cache_root / "hub" / folder / "snapshots" / revision


def model_cached(cache_root: Path | None = None) -> bool:
    """기본 임베딩 스냅샷이 있으면 True입니다.

    Args:
        cache_root: 캐시 루트입니다. None이면 `hf_home()`입니다.

    Returns:
        `config.json`이 있으면 True입니다.
    """
    marker = hub_snapshot_dir(
        cache_root or hf_home(), EMBEDDING_REPO, EMBEDDING_REVISION
    ) / "config.json"
    return marker.is_file()


def venv_python(venv_dir: Path) -> Path:
    """가상환경 Python 경로를 반환합니다.

    Args:
        venv_dir: `.venv` 또는 `.venv-web`입니다.

    Returns:
        Windows는 `Scripts/python.exe`, 그 외는 `bin/python`입니다.
    """
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """TCP 포트에 연결되면 True입니다.

    Args:
        host: 호스트입니다.
        port: 포트입니다.
        timeout: 초 단위 대기입니다.

    Returns:
        연결되면 True입니다.
    """
    target = "127.0.0.1" if host.lower() in {"localhost", "0.0.0.0"} else host
    try:
        with socket.create_connection((target, port), timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, seconds: float) -> bool:
    """포트가 열릴 때까지 기다립니다.

    Args:
        host: 호스트입니다.
        port: 포트입니다.
        seconds: 최대 대기 시간입니다.

    Returns:
        열리면 True입니다.
    """
    deadline = time.time() + max(seconds, 0.0)
    while time.time() <= deadline:
        if port_open(host, port):
            return True
        time.sleep(0.4)
    return port_open(host, port)


def python_major_minor(executable: str) -> tuple[int, int] | None:
    """인터프리터의 major.minor를 읽습니다.

    Args:
        executable: Python 실행 파일입니다.

    Returns:
        (3, 12) 같은 튜플입니다. 실패하면 None입니다.
    """
    try:
        probe = subprocess.run(
            [
                executable,
                "-c",
                "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if probe.returncode != 0:
        return None
    text = probe.stdout.strip()
    parts = text.split(".")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def find_python312() -> str:
    """호스트의 Python 3.12를 찾습니다.

    Returns:
        실행 파일 경로입니다.

    Raises:
        FileNotFoundError: 3.12를 찾지 못한 경우 발생합니다.
    """
    current = python_major_minor(sys.executable)
    if current == (3, 12):
        return sys.executable
    candidates: list[str] = []
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidates.append(
                str(Path(local) / "Programs" / "Python" / "Python312" / "python.exe")
            )
            candidates.append(
                str(Path(local) / "Programs" / "Python" / "Launcher" / "py.exe")
            )
        candidates.extend(["py", "python3.12", "python"])
    else:
        candidates.extend(["python3.12", "python3", "python"])
    for name in candidates:
        path = name
        if path in {"py", "python3.12", "python3", "python"}:
            found = shutil.which(name)
            if found is None:
                continue
            path = found
        elif not Path(path).is_file():
            continue
        if Path(path).name.lower() == "py.exe" or name == "py":
            try:
                probe = subprocess.run(
                    [path, "-3.12", "-c", "import sys; print(sys.executable)"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if probe.returncode == 0 and probe.stdout.strip():
                return probe.stdout.strip()
            continue
        if python_major_minor(path) == (3, 12):
            return path
    raise FileNotFoundError(
        "Python 3.12가 필요합니다. python3.12 또는 Windows Python 3.12를 설치하세요."
    )


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """명령을 실행하고 실패하면 예외를 냅니다.

    Args:
        command: 실행 파일과 인자입니다.
        cwd: 작업 디렉터리입니다.
        env: 자식 환경입니다.

    Raises:
        subprocess.CalledProcessError: 종료 코드가 0이 아니면 발생합니다.
    """
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=str(cwd or ROOT), env=env, check=True)


def module_importable(python: Path, statement: str) -> bool:
    """가상환경에서 import 문이 성공하면 True입니다.

    Args:
        python: 가상환경 Python입니다.
        statement: `import flask` 같은 문장입니다.

    Returns:
        종료 코드 0이면 True입니다.
    """
    try:
        probe = subprocess.run(
            [str(python), "-c", statement],
            cwd=str(ROOT),
            capture_output=True,
            timeout=40,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def ensure_venv(python312: str, venv_dir: Path) -> Path:
    """가상환경이 없으면 만듭니다.

    Args:
        python312: 호스트 Python 3.12입니다.
        venv_dir: 만들 디렉터리입니다.

    Returns:
        가상환경 Python 경로입니다.
    """
    python = venv_python(venv_dir)
    if python.is_file():
        print(f"가상환경 유지: {venv_dir}")
        return python
    print(f"가상환경 생성: {venv_dir}")
    run([python312, "-m", "venv", str(venv_dir)])
    if not python.is_file():
        raise FileNotFoundError(f"가상환경 Python을 만들지 못했습니다: {python}")
    return python


def pip_install(python: Path, args: list[str]) -> None:
    """가상환경 pip로 패키지를 설치합니다.

    Args:
        python: 가상환경 Python입니다.
        args: `pip install` 뒤에 붙는 인자입니다.
    """
    run([str(python), "-m", "pip", "install", "--upgrade", "pip", "wheel"])
    run([str(python), "-m", "pip", "install", *args])


def ensure_rag_venv(python312: str, upgrade: bool) -> Path:
    """검색용 `.venv`와 CPU torch·rag 의존성을 준비합니다.

    Args:
        python312: 호스트 Python 3.12입니다.
        upgrade: True이면 이미 있는 패키지도 다시 설치합니다.

    Returns:
        `.venv` Python 경로입니다.
    """
    python = ensure_venv(python312, ROOT / ".venv")
    need_torch = upgrade or not module_importable(python, "import torch")
    need_rag = upgrade or not module_importable(
        python, "import sentence_transformers, psycopg, fastapi, kiwipiepy"
    )
    if need_torch:
        pip_install(
            python,
            [
                f"torch=={TORCH_CPU_VERSION}",
                "--index-url",
                TORCH_CPU_INDEX,
            ],
        )
    else:
        print("RAG .venv: torch 유지")
    if need_rag:
        if not need_torch:
            run([str(python), "-m", "pip", "install", "--upgrade", "pip", "wheel"])
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "-r",
                str(ROOT / "rag" / "requirements.txt"),
            ]
        )
    else:
        print("RAG .venv: rag/requirements.txt 유지")
    return python


def ensure_web_venv(python312: str, upgrade: bool, dev: bool) -> Path:
    """시연 웹용 `.venv-web`을 준비합니다.

    Args:
        python312: 호스트 Python 3.12입니다.
        upgrade: True이면 요구 파일을 다시 설치합니다.
        dev: True이면 `requirements-dev.txt`를 씁니다.

    Returns:
        `.venv-web` Python 경로입니다.
    """
    python = ensure_venv(python312, ROOT / ".venv-web")
    req = (
        ROOT / "src" / "requirements-dev.txt"
        if dev
        else ROOT / "src" / "requirements.txt"
    )
    probe = "import flask, psycopg, pydantic"
    if dev:
        probe += ", pytest"
    if upgrade or not module_importable(python, probe):
        pip_install(python, ["-r", str(req)])
    else:
        print("웹 .venv-web: src 의존성 유지")
    return python


def download_file(url: str, dest: Path) -> Path:
    """URL을 파일로 받습니다. 이미 있으면 다시 받지 않습니다.

    Args:
        url: 받을 주소입니다.
        dest: 저장 경로입니다.

    Returns:
        받은 파일 경로입니다.

    Raises:
        urllib.error.URLError: 받기에 실패한 경우 발생합니다.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"다운로드 유지: {dest.name}")
        return dest
    print(f"다운로드: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "ai-complaint-process-setup"})
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=dest.name + ".", dir=str(dest.parent))
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        with urllib.request.urlopen(request, timeout=120) as response, tmp_path.open(
            "wb"
        ) as handle:
            shutil.copyfileobj(response, handle)
        tmp_path.replace(dest)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return dest


def extract_postgres_zip(archive: Path) -> None:
    """EDB 바이너리 zip에서 `pgsql/`만 `.rag-data/`로 풉니다.

    Args:
        archive: 받은 zip 경로입니다.
    """
    print(f"압축 해제: {archive.name} -> {PG_PREFIX}")
    PG_PREFIX.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name.startswith("pgsql/"):
                continue
            if "/pgAdmin" in name or name.startswith("pgsql/pgAdmin"):
                continue
            zf.extract(info, PG_PREFIX.parent)


def install_pgvector_zip(archive: Path) -> None:
    """Windows pgvector zip을 휴대 PostgreSQL 트리에 복사합니다.

    Args:
        archive: `vector.v0.8.7-pg18.zip` 경로입니다.
    """
    print(f"pgvector 설치: {archive.name}")
    lib_dir = PG_PREFIX / "lib"
    ext_dir = PG_PREFIX / "share" / "extension"
    lib_dir.mkdir(parents=True, exist_ok=True)
    ext_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename.replace("\\", "/")).name
            lower = name.lower()
            data = zf.read(info)
            if lower == "vector.dll":
                (lib_dir / name).write_bytes(data)
            elif lower.startswith("vector") and (
                lower.endswith(".control") or lower.endswith(".sql")
            ):
                (ext_dir / name).write_bytes(data)


def windows_pg_bin(name: str) -> Path:
    """휴대 PostgreSQL 실행 파일 경로를 반환합니다.

    Args:
        name: `postgres.exe`처럼 확장자를 포함한 이름입니다.

    Returns:
        `.rag-data/pgsql/bin` 아래 경로입니다.
    """
    return PG_PREFIX / "bin" / name


def windows_pg_role() -> str:
    """Windows 클러스터 역할 이름을 반환합니다.

    Returns:
        `USERNAME` 또는 `user`입니다.
    """
    return os.environ.get("USERNAME") or os.environ.get("USER") or "user"


def init_windows_cluster() -> None:
    """데이터 디렉터리가 없으면 localhost trust 클러스터를 만듭니다."""
    if (PG_DATA / "PG_VERSION").is_file():
        print(f"PostgreSQL 데이터 유지: {PG_DATA}")
        return
    initdb = windows_pg_bin("initdb.exe")
    if not initdb.is_file():
        raise FileNotFoundError(f"initdb가 없습니다: {initdb}")
    PG_DATA.parent.mkdir(parents=True, exist_ok=True)
    role = windows_pg_role()
    run(
        [
            str(initdb),
            "-D",
            str(PG_DATA),
            "-U",
            role,
            "--encoding=UTF8",
            "--locale=C",
            "--auth=trust",
        ]
    )


def start_windows_postgres() -> None:
    """5432가 닫혀 있으면 휴대 `postgres.exe`를 분리 실행합니다."""
    if port_open("127.0.0.1", 5432):
        print("PostgreSQL이 이미 127.0.0.1:5432 에서 실행 중입니다.")
        return
    postgres = windows_pg_bin("postgres.exe")
    if not postgres.is_file():
        raise FileNotFoundError(f"postgres.exe가 없습니다: {postgres}")
    print("PostgreSQL을 사용자 프로세스로 시작합니다. 이미 있는 서버는 종료하지 않습니다.")
    flags = 0
    flags |= int(getattr(subprocess, "DETACHED_PROCESS", 0))
    flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    env = os.environ.copy()
    env["PATH"] = str(PG_PREFIX / "bin") + os.pathsep + env.get("PATH", "")
    subprocess.Popen(
        [str(postgres), "-D", str(PG_DATA)],
        cwd=str(ROOT),
        env=env,
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not wait_for_port("127.0.0.1", 5432, 25):
        raise RuntimeError("PostgreSQL 5432 준비를 확인하지 못했습니다.")


def psql_env() -> dict[str, str]:
    """psql에 넘길 Windows libpq 기본 환경을 만듭니다.

    Returns:
        복사한 환경 딕셔너리입니다.
    """
    env = os.environ.copy()
    env.setdefault("PGHOST", "127.0.0.1")
    env.setdefault("PGPORT", "5432")
    env.setdefault("PGUSER", windows_pg_role())
    env.setdefault("PGDATABASE", DATABASE_NAME)
    env["PATH"] = str(PG_PREFIX / "bin") + os.pathsep + env.get("PATH", "")
    return env


def run_psql(
    sql: str, *, database: str, tuples_only: bool = True
) -> subprocess.CompletedProcess[str]:
    """휴대 psql로 SQL을 실행합니다.

    긴 DDL은 명령줄 길이 제한을 피하려고 표준 입력으로 넘깁니다.

    Args:
        sql: 한 덩어리 SQL입니다.
        database: 접속 DB 이름입니다.
        tuples_only: True이면 `-tA`로 값만 받습니다.

    Returns:
        완료된 프로세스입니다.
    """
    psql = windows_pg_bin("psql.exe")
    env = psql_env()
    command = [
        str(psql),
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-d",
        database,
    ]
    if tuples_only:
        command.extend(["-tA"])
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".sql", delete=False
    )
    try:
        handle.write(sql)
        handle.close()
        command.extend(["-f", handle.name])
        return subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        Path(handle.name).unlink(missing_ok=True)


def ensure_windows_database() -> None:
    """`complaints_native`와 pgvector·스키마를 준비합니다. 기존 행은 지우지 않습니다."""
    if not port_open("127.0.0.1", 5432):
        raise RuntimeError("PostgreSQL 5432에 연결할 수 없습니다.")
    exists = run_psql(
        "SELECT 1 FROM pg_database WHERE datname = 'complaints_native'",
        database="postgres",
    ).stdout.strip()
    if exists != "1":
        print(f"데이터베이스 생성: {DATABASE_NAME}")
        run_psql(f'CREATE DATABASE {DATABASE_NAME}', database="postgres")
    else:
        print(f"데이터베이스 유지: {DATABASE_NAME}")
    run_psql("CREATE EXTENSION IF NOT EXISTS vector", database=DATABASE_NAME)
    rag_exists = run_psql(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'complaint_rag'",
        database=DATABASE_NAME,
    ).stdout.strip()
    if rag_exists != "1":
        dump = ROOT / "rag" / "origin" / "dumps" / "complaint_rag.dump"
        if dump.is_file():
            print(f"검색 dump 복원: {dump}")
            env = psql_env()
            run(
                [
                    str(windows_pg_bin("pg_restore.exe")),
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                    "-d",
                    DATABASE_NAME,
                    str(dump),
                ],
                env=env,
            )
        else:
            print("검색 스키마 SQL 적용. 행 데이터는 넣지 않습니다.")
            sys.path.insert(0, str(ROOT))
            from rag.config import schema_sql

            run_psql(schema_sql(), database=DATABASE_NAME)
    else:
        print("검색 스키마 유지: complaint_rag")
    app_exists = run_psql(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'complaint_app'",
        database=DATABASE_NAME,
    ).stdout.strip()
    if app_exists != "1":
        if not APP_SQL.is_file():
            raise FileNotFoundError(f"업무 스키마가 없습니다: {APP_SQL}")
        print("업무 스키마 SQL 적용")
        sql = APP_SQL.read_text(encoding="utf-8")
        run_psql(sql, database=DATABASE_NAME)
    else:
        print("업무 스키마 유지: complaint_app")


def ensure_windows_postgres() -> None:
    """휴대 PostgreSQL 18.6과 pgvector 0.8.7을 준비합니다."""
    postgres = windows_pg_bin("postgres.exe")
    vector_dll = PG_PREFIX / "lib" / "vector.dll"
    if not postgres.is_file():
        archive = download_file(PG_ZIP_URL, DOWNLOAD_DIR / PG_ZIP_NAME)
        extract_postgres_zip(archive)
    else:
        print(f"PostgreSQL 바이너리 유지: {PG_PREFIX}")
    if not vector_dll.is_file():
        archive = download_file(PGVECTOR_ZIP_URL, DOWNLOAD_DIR / PGVECTOR_ZIP_NAME)
        install_pgvector_zip(archive)
    else:
        print("pgvector 바이너리 유지")
    if not postgres.is_file():
        raise FileNotFoundError("PostgreSQL 바이너리 설치 후 postgres.exe가 없습니다.")
    init_windows_cluster()
    start_windows_postgres()
    ensure_windows_database()


def linux_psql_env() -> dict[str, str]:
    """우분투 소켓 peer 인증 기본 환경을 만듭니다.

    Returns:
        복사한 환경 딕셔너리입니다.
    """
    env = os.environ.copy()
    env.setdefault("PGHOST", "/var/run/postgresql")
    env.setdefault("PGPORT", "5432")
    env.setdefault("PGDATABASE", DATABASE_NAME)
    env.setdefault("PGUSER", env.get("USER") or env.get("LOGNAME") or "postgres")
    return env


def linux_schema_exists(schema: str) -> bool:
    """현재 DB에 스키마가 있으면 True입니다.

    Args:
        schema: `complaint_rag` 또는 `complaint_app`입니다.

    Returns:
        스키마가 있으면 True입니다.
    """
    probe = subprocess.run(
        [
            "psql",
            "-X",
            "-d",
            DATABASE_NAME,
            "-tAc",
            "SELECT 1 FROM information_schema.schemata "
            f"WHERE schema_name = '{schema}'",
        ],
        cwd=str(ROOT),
        env=linux_psql_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0 and probe.stdout.strip() == "1"


def ensure_linux_database() -> None:
    """우분투에서 계정·확장·빈 스키마를 준비합니다. 기존 행은 지우지 않습니다."""
    prepare = ROOT / "scripts" / "검색DB_준비.sh"
    restore = ROOT / "scripts" / "검색덤프_복원.sh"
    if not prepare.is_file():
        raise FileNotFoundError(prepare)
    run(["bash", str(prepare)])
    if not linux_schema_exists("complaint_rag"):
        run(["bash", str(restore)])
    else:
        print("검색 스키마 유지: complaint_rag")
    if not linux_schema_exists("complaint_app"):
        if not APP_SQL.is_file():
            raise FileNotFoundError(APP_SQL)
        run(
            ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-d", DATABASE_NAME, "-f", str(APP_SQL)],
            env=linux_psql_env(),
        )
    else:
        print("업무 스키마 유지: complaint_app")


def download_embedding_model(rag_python: Path) -> None:
    """기본 임베딩 스냅샷을 `.rag-cache/huggingface`에 받습니다.

    Args:
        rag_python: huggingface_hub가 있는 `.venv` Python입니다.
    """
    os.environ.setdefault("HF_HOME", str(hf_home()))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    cache = hf_home()
    cache.mkdir(parents=True, exist_ok=True)
    if model_cached(cache):
        print(f"임베딩 모델 유지: {EMBEDDING_REPO}@{EMBEDDING_REVISION}")
        return
    print(f"임베딩 모델 다운로드: {EMBEDDING_REPO}@{EMBEDDING_REVISION}")
    script = (
        "import os\n"
        "from huggingface_hub import snapshot_download\n"
        f"snapshot_download({EMBEDDING_REPO!r}, revision={EMBEDDING_REVISION!r}, "
        "cache_dir=os.environ['HF_HOME'])\n"
    )
    env = os.environ.copy()
    env["HF_HOME"] = str(cache)
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["HF_HUB_DISABLE_XET"] = "1"
    run([str(rag_python), "-c", script], env=env)
    if not model_cached(cache):
        raise RuntimeError("임베딩 모델 스냅샷을 확인하지 못했습니다.")


def check_report() -> list[str]:
    """설치 상태를 확인하고 실패 항목을 반환합니다.

    Returns:
        실패한 검사 메시지 목록입니다. 비어 있으면 통과입니다.
    """
    problems: list[str] = []
    try:
        find_python312()
        print("확인: Python 3.12")
    except FileNotFoundError as exc:
        problems.append(str(exc))
        print(f"실패: {exc}")

    rag_py = venv_python(ROOT / ".venv")
    if rag_py.is_file() and module_importable(
        rag_py, "import torch, sentence_transformers, psycopg, fastapi"
    ):
        print("확인: RAG .venv")
    else:
        problems.append("RAG .venv 또는 rag 의존성이 없습니다.")
        print("실패: RAG .venv")

    web_py = venv_python(ROOT / ".venv-web")
    if web_py.is_file() and module_importable(web_py, "import flask, psycopg"):
        print("확인: 웹 .venv-web")
    else:
        problems.append("웹 .venv-web 또는 Flask 의존성이 없습니다.")
        print("실패: 웹 .venv-web")

    if os.name == "nt":
        postgres = windows_pg_bin("postgres.exe")
        vector_dll = PG_PREFIX / "lib" / "vector.dll"
        if postgres.is_file() and vector_dll.is_file():
            print("확인: 휴대 PostgreSQL·pgvector")
        else:
            problems.append("Windows 휴대 PostgreSQL 또는 pgvector가 없습니다.")
            print("실패: 휴대 PostgreSQL·pgvector")
        if (PG_DATA / "PG_VERSION").is_file():
            print("확인: PostgreSQL 데이터 디렉터리")
        else:
            problems.append(".rag-data/postgres 데이터 디렉터리가 없습니다.")
            print("실패: PostgreSQL 데이터 디렉터리")
        if port_open("127.0.0.1", 5432):
            print("확인: 127.0.0.1:5432")
        else:
            print("안내: 127.0.0.1:5432 가 닫혀 있습니다. 검색-시작.cmd 또는 start-search.sh")
    else:
        if shutil.which("psql"):
            print("확인: psql")
        else:
            problems.append("psql이 PATH에 없습니다. postgresql-18 패키지를 설치하세요.")
            print("실패: psql")

    if model_cached():
        print(f"확인: {EMBEDDING_REPO}")
    else:
        problems.append(
            f"임베딩 모델 캐시가 없습니다: {EMBEDDING_REPO}@{EMBEDDING_REVISION}"
        )
        print("실패: 임베딩 모델 캐시")
    return problems


def print_next_steps() -> None:
    """설치 후 실행 명령을 안내합니다."""
    if os.name == "nt":
        print("다음: setup.cmd --check")
        print("검색: 검색-시작.cmd")
        print("웹: 웹-시작.cmd")
        print("문장: 문장-임베딩.cmd")
        print("응대: 민원-응대.cmd")
    else:
        print("다음: ./setup.sh --check")
        print("검색: ./start-search.sh")
        print("웹: ./start-web.sh")
        print("문장: ./embed-sentence.sh '나무가 쓰러짐'")
        print("응대: ./ask-assist.sh --example faq")
    print(
        "빈 검색 DB이면 dump 복원 또는 `.venv`에서 python -m rag ingest 가 필요합니다. "
        "setup은 5,109건을 자동 적재하지 않습니다."
    )


def main(argv: list[str] | None = None) -> int:
    """설치 또는 확인을 실행하고 종료 코드를 반환합니다.

    Args:
        argv: 명령줄 인자입니다.

    Returns:
        성공 0, 실패 1입니다.
    """
    args = parse_args(argv)
    os.chdir(ROOT)
    os.environ.setdefault("HF_HOME", str(hf_home()))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("RAG_DEVICE", "cpu")

    if args.check:
        problems = check_report()
        if problems:
            print("확인 실패:")
            for item in problems:
                print(f"- {item}")
            return 1
        print("확인 통과: 실행 준비가 되어 있습니다.")
        return 0

    try:
        python312 = find_python312()
        print(f"Python 3.12: {python312}")
        rag_python = ensure_rag_venv(python312, args.upgrade)
        ensure_web_venv(python312, args.upgrade, args.dev)
        if not args.skip_db:
            if os.name == "nt":
                ensure_windows_postgres()
            else:
                ensure_linux_database()
        if not args.skip_model:
            download_embedding_model(rag_python)
    except (
        FileNotFoundError,
        RuntimeError,
        subprocess.CalledProcessError,
        urllib.error.URLError,
        OSError,
    ) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1

    problems = check_report()
    print_next_steps()
    if problems:
        print("설치 후 확인에서 남은 항목:")
        for item in problems:
            print(f"- {item}")
        return 1
    print("설치 확인 통과.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
