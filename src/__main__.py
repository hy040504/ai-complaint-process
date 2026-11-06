"""저장소 루트에서 `python -m src`로 로컬 Flask 서버를 실행합니다.

민원 웹·검사기 API를 같은 출처에서 제공합니다. Windows에서
`PGDATABASE`가 비어 있으면 `complaints_native`로 접속합니다.
"""

import os
import sys
from pathlib import Path

from src.app import create_app

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from 콘솔_기동 import apply_windows_libpq  # noqa: E402


def main() -> None:
    """디버거를 노출하지 않고 localhost에서 업무 서버를 실행합니다.

    포트는 `COMPLAINT_PORT`이며 기본값은 5000입니다. Windows에서
    `PGDATABASE`가 비어 있으면 `complaints_native`로 접속합니다.
    """
    apply_windows_libpq(os.environ)
    app = create_app()
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("COMPLAINT_PORT", "5000")),
        debug=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
