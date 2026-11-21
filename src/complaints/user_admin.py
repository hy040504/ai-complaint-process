"""담당자 계정 생성·비밀번호 재설정·비활성화 같은 운영자용 계정 관리 로직입니다.

Flask CLI(`create-staff`·`reset-password`·`deactivate-user`·`activate-user`·`list-users`)가
호출합니다. 비밀번호 원문은 명령줄 인자로 받지 않고 환경변수 또는 숨김 프롬프트로만
받으며, 이 모듈은 해시만 저장소에 넘깁니다.
"""

import re
from uuid import uuid4

from src.complaints.auth import StoredUser, hash_password
from src.complaints.departments import valid_department_names
from src.complaints.errors import AppError
from src.complaints.repository import ComplaintRepository

LOGIN_ID_RE = re.compile(r"[A-Za-z0-9_.-]{3,32}")
MIN_STAFF_PASSWORD_LENGTH = 8


def _check_password(password: str) -> None:
    """운영 계정 비밀번호 최소 규칙을 검사합니다.

    Args:
        password: 비밀번호 원문입니다.

    Raises:
        AppError: 길이가 부족하거나 공백뿐이면 422를 발생합니다.
    """
    if len(password) < MIN_STAFF_PASSWORD_LENGTH or not password.strip():
        raise AppError(
            422,
            "weak_password",
            f"비밀번호는 {MIN_STAFF_PASSWORD_LENGTH}자 이상이어야 합니다.",
        )


def _require_user(repository: ComplaintRepository, login_id: str) -> StoredUser:
    """아이디로 시연 계정이 아닌 사용자를 조회합니다.

    Args:
        repository: 업무 저장소입니다.
        login_id: 로그인 아이디입니다.

    Returns:
        조회된 사용자입니다.

    Raises:
        AppError: 계정이 없거나 시연 계정이면 404·403을 발생합니다.
    """
    user = repository.get_user_by_login(login_id)
    if user is None:
        raise AppError(404, "user_not_found", f"계정을 찾을 수 없습니다: {login_id}")
    if user.is_demo:
        raise AppError(403, "demo_user_protected", "시연 계정은 변경할 수 없습니다.")
    return user


def create_staff(
    repository: ComplaintRepository,
    *,
    login_id: str,
    display_name: str,
    department: str | None,
    password: str,
) -> StoredUser:
    """담당자 계정을 만듭니다.

    Args:
        repository: 업무 저장소입니다.
        login_id: 로그인 아이디(영문·숫자·`_.-` 3~32자)입니다.
        display_name: 이력·화면에 표시할 이름(2~30자)입니다.
        department: 소속 부서입니다. 비우면 전 부서를 다루는 총괄 담당자입니다.
        password: 비밀번호 원문(8자 이상)입니다.

    Returns:
        저장된 담당자 계정입니다.

    Raises:
        AppError: 입력이 규칙에 맞지 않거나 부서가 현행 디렉터리에 없거나 아이디가 중복이면 발생합니다.
    """
    if not LOGIN_ID_RE.fullmatch(login_id):
        raise AppError(
            422, "invalid_login_id", "아이디는 영문·숫자·_.- 3~32자여야 합니다."
        )
    name = display_name.strip()
    if not 2 <= len(name) <= 30:
        raise AppError(422, "invalid_display_name", "이름은 2~30자여야 합니다.")
    _check_password(password)
    dept = (department or "").strip() or None
    if dept is not None and dept not in valid_department_names():
        raise AppError(
            422,
            "unknown_department",
            f"현행 부서 디렉터리에 없는 부서입니다: {dept}",
        )
    user = StoredUser(
        id=f"staff-{uuid4().hex[:12]}",
        login_id=login_id,
        display_name=name,
        role="staff",
        password_hash=hash_password(password),
        department=dept,
    )
    return repository.create_user(user)


def reset_password(
    repository: ComplaintRepository, *, login_id: str, password: str
) -> StoredUser:
    """계정의 비밀번호를 새 값으로 바꿉니다.

    Args:
        repository: 업무 저장소입니다.
        login_id: 대상 로그인 아이디입니다.
        password: 새 비밀번호 원문입니다.

    Returns:
        대상 계정(변경 전 조회 시점의 레코드)입니다.

    Raises:
        AppError: 계정이 없거나 시연 계정이거나 비밀번호가 약하면 발생합니다.
    """
    user = _require_user(repository, login_id)
    _check_password(password)
    repository.update_user_password(user.id, hash_password(password))
    return user


def set_active(
    repository: ComplaintRepository, *, login_id: str, active: bool
) -> StoredUser:
    """계정을 활성화하거나 비활성화합니다. 비활성 계정은 로그인·세션을 거부합니다.

    Args:
        repository: 업무 저장소입니다.
        login_id: 대상 로그인 아이디입니다.
        active: 활성화하려면 True입니다.

    Returns:
        대상 계정(변경 전 조회 시점의 레코드)입니다.

    Raises:
        AppError: 계정이 없거나 시연 계정이면 발생합니다.
    """
    user = _require_user(repository, login_id)
    repository.set_user_active(user.id, active)
    return user
