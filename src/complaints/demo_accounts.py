"""시연용 공통 로그인 계정(아이디 `abcd`)을 만드는 운영자용 로직입니다.

`users.login_id`는 UNIQUE라 같은 아이디로 민원인·담당자 계정을 둘 수 없습니다. 그래서 민원인은
`abcd`, 담당자는 내부 아이디 `abcd@staff`로 저장하고, 로그인 때 사이트가 보낸
`expected_role`로 `<아이디>@<역할>`을 먼저 찾습니다. 사용자는 두 사이트 모두 같은 아이디와
시연 비밀번호를 입력합니다. 일반 가입·담당자 생성은 `@`를 허용하지 않으므로 이 내부 아이디를 선점할 수 없습니다.

비밀번호는 **저장소에 두지 않고** 환경변수 `COMPLAINT_DEMO_ACCOUNT_PASSWORD`로만 받습니다(공개 저장소에 노출되지
않게 하기 위함). 값이 약하므로 자동으로 만들지 않고 CLI(`seed-demo-accounts`)를 실행했을 때만 만듭니다.
끄려면 `deactivate-user --login-id abcd`와 `--login-id abcd@staff`를 실행합니다.
"""

import os

from src.complaints.auth import StoredUser, hash_password
from src.complaints.errors import AppError
from src.complaints.repository import ComplaintRepository

DEMO_LOGIN_ID = "abcd"
DEMO_PASSWORD_ENV = "COMPLAINT_DEMO_ACCOUNT_PASSWORD"


def demo_password() -> str:
    """환경변수에서 시연 비밀번호를 읽습니다.

    Returns:
        `COMPLAINT_DEMO_ACCOUNT_PASSWORD` 값입니다.

    Raises:
        AppError: 값이 없거나 공백뿐이면 422를 발생합니다(코드에 기본값을 두지 않습니다).
    """
    value = os.environ.get(DEMO_PASSWORD_ENV, "")
    if not value.strip():
        raise AppError(
            422,
            "demo_password_missing",
            f"환경변수 {DEMO_PASSWORD_ENV}에 시연 비밀번호를 지정해 주세요.",
        )
    return value


def role_alias(login_id: str, role: str) -> str:
    """역할별 내부 로그인 아이디를 만듭니다.

    Args:
        login_id: 사용자가 입력한 아이디입니다.
        role: 로그인 화면이 요구하는 역할(`citizen` 또는 `staff`)입니다.

    Returns:
        `<아이디>@<역할>` 형태의 내부 아이디입니다.
    """
    return f"{login_id}@{role}"


def ensure_demo_accounts(repository: ComplaintRepository) -> list[tuple[str, str]]:
    """공통 시연 계정을 만들거나 비밀번호·활성 상태를 되돌립니다(여러 번 실행해도 같은 결과).

    Args:
        repository: 업무 저장소입니다.

    Returns:
        `(내부 로그인 아이디, 처리)` 목록입니다. 처리는 `created` 또는 `updated`입니다.

    Raises:
        AppError: 시연 비밀번호 환경변수가 없으면 발생합니다.
    """
    password = demo_password()
    specs = [
        (DEMO_LOGIN_ID, "citizen", "USR-CIT-DEMOABCD", "시연 민원인", None),
        (
            role_alias(DEMO_LOGIN_ID, "staff"),
            "staff",
            "staff-demoabcd",
            "시연 담당자",
            None,
        ),
    ]
    results: list[tuple[str, str]] = []
    for login_id, role, user_id, name, department in specs:
        found = repository.get_user_by_login(login_id)
        if found is None:
            repository.create_user(
                StoredUser(
                    id=user_id,
                    login_id=login_id,
                    display_name=name,
                    role=role,  # type: ignore[arg-type]
                    password_hash=hash_password(password),
                    department=department,
                )
            )
            results.append((login_id, "created"))
            continue
        repository.update_user_password(found.id, hash_password(password))
        repository.set_user_active(found.id, True)
        results.append((login_id, "updated"))
    return results
