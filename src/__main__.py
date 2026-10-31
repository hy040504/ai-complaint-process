"""저장소 루트에서 python -m src로 로컬 Flask 서버를 실행합니다."""

import os

from src.app import create_app


def main() -> None:
    """디버거를 노출하지 않고 localhost에서 업무 서버를 실행합니다."""
    app = create_app()
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("COMPLAINT_PORT", "5000")),
        debug=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
