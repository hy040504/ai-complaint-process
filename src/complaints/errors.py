"""HTTP와 저장소 계층이 공유하는 명시적인 업무 오류입니다."""


class AppError(Exception):
    """호출자가 처리할 HTTP 상태·오류 코드·한국어 안내를 보관합니다.

    Args:
        status: HTTP 상태 코드입니다.
        code: 프로그램이 구분할 업무 오류 코드입니다.
        message: 사용자에게 제공할 한국어 안내입니다.
    """

    def __init__(self, status: int, code: str, message: str) -> None:
        """업무 오류 정보를 초기화합니다.

        Args:
            status: 응답할 HTTP 상태 코드입니다.
            code: 프로그램에서 구분할 오류 코드입니다.
            message: 사용자에게 표시할 한국어 안내입니다.
        """
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
