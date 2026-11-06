"""저장소 루트에서 `python -m src.lab_web`으로 검사기 웹을 실행합니다."""

import os

from src.lab_web.app import create_app
from src.lab_web.constants import DEFAULT_PORT


def main() -> None:
    """localhost에서 검사기 웹만 켭니다.

    포트는 `LAB_WEB_PORT`이며 기본값은 5010입니다. 기존 민원 CRUD
    Flask(:5000)는 종료하지 않습니다.
    """
    app = create_app()
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("LAB_WEB_PORT", str(DEFAULT_PORT))),
        debug=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
