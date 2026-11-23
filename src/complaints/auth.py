"""민원인·담당자 아이디·비밀번호 로그인(`scrypt`)과 세션·부서 권한을 관리합니다.

외부 이동통신사 PASS·행정 SSO 연동은 별도 인프라 범위이며,
이 모듈은 간결한 아이디·비밀번호 기반 민원인/담당자 로그인,
간단 민원인 계정 가입, 연속 실패 잠금, 세션 사용자 대조를 제공합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from functools import lru_cache
import os
import secrets
from threading import Lock
import time
from typing import TYPE_CHECKING
from uuid import uuid4

from werkzeug.security import check_password_hash, generate_password_hash

from src.complaints.errors import AppError
from src.complaints.models import (
    Actor,
    AuthMode,
    LoginInput,
    RegisterInput,
    Role,
    utcnow,
)

if TYPE_CHECKING:
    from src.complaints.repository import ComplaintRepository

# 로컬 개발·검증용 초기 비밀번호입니다. 배포 시 환경변수로 교체합니다.
DEFAULT_CITIZEN_INIT_PASSWORD = os.environ.get(
    "COMPLAINT_CITIZEN_INIT_PASSWORD", "cheongju-citizen-2026!"
)
DEFAULT_STAFF_INIT_PASSWORD = os.environ.get(
    "COMPLAINT_STAFF_INIT_PASSWORD", "cheongju-staff-2026!"
)
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SECONDS = 60.0


@dataclass(frozen=True)
class StoredUser:
    """`complaint_app.users` 테이블에 저장되는 내부 사용자 레코드입니다.

    비밀번호 해시(`password_hash`)는 API 응답 모델(`Actor`)에 노출하지 않습니다.

    Attributes:
        id: 사용자 고유 식별자(`users.id`)입니다.
        login_id: 로그인 아이디(유니크)입니다.
        display_name: 화면·이력에 표시할 이름입니다.
        role: `citizen` 또는 `staff`입니다.
        password_hash: `werkzeug.security` `scrypt` 해시 문자열입니다.
        department: 담당자 소속 부서명입니다. 총괄 담당자·민원인은 None입니다.
        is_demo: 시연 원클릭 계정 여부입니다.
        active: 계정 활성 상태입니다. 비활성 계정은 로그인·세션을 거부합니다.
        created_at: 계정 생성 UTC 시각입니다.
        last_login_at: 마지막 로그인 UTC 시각입니다.
    """

    id: str
    login_id: str
    display_name: str
    role: Role
    password_hash: str
    department: str | None = None
    is_demo: bool = False
    active: bool = True
    created_at: datetime = field(default_factory=utcnow)
    last_login_at: datetime | None = None

    def to_actor(self, *, auth_mode: AuthMode | None = None) -> Actor:
        """비밀번호 해시를 제거한 응답용 `Actor` 모델로 변환합니다.

        Args:
            auth_mode: 세션에 기록된 인증 방식입니다. 생략하면 계정 유형으로 추정합니다.

        Returns:
            API·세션에서 사용하는 `Actor` 모델입니다.
        """
        resolved_mode: AuthMode = auth_mode or ("demo" if self.is_demo else "password")
        return Actor(
            id=self.id,
            login_id=self.login_id,
            display_name=self.display_name,
            role=self.role,
            department=self.department,
            auth_mode=resolved_mode,
            demo=self.is_demo or resolved_mode == "demo",
        )


def hash_password(raw_password: str) -> str:
    """비밀번호 원문을 `scrypt` 솔트 해시로 변환합니다.

    Args:
        raw_password: 평문 비밀번호 문자열입니다.

    Returns:
        DB에 저장할 해시 문자열입니다.
    """
    return generate_password_hash(raw_password, method="scrypt")


def verify_password(password_hash: str, raw_password: str) -> bool:
    """저장된 비밀번호 해시와 입력 비밀번호를 상수 시간 비교합니다.

    Args:
        password_hash: DB에 저장된 해시 문자열입니다.
        raw_password: 사용자가 제출한 비밀번호입니다.

    Returns:
        일치하면 True, 아니면 False입니다.
    """
    if not password_hash or not raw_password:
        return False
    return check_password_hash(password_hash, raw_password)


@lru_cache(maxsize=4)
def _cached_seed_hashes(
    citizen_password: str, staff_password: str
) -> tuple[str, str, str]:
    """초기 시드 계정의 `scrypt` 해시를 프로세스당 한 번만 계산해 캐시합니다.

    Args:
        citizen_password: 기본 민원인 계정 초기 비밀번호입니다.
        staff_password: 기본 담당자 계정 초기 비밀번호입니다.

    Returns:
        `(시연용 비활성 해시, 기본 민원인 해시, 기본 담당자 해시)` 튜플입니다.
    """
    demo_unusable = hash_password(secrets.token_urlsafe(32))
    citizen_hash = hash_password(citizen_password)
    staff_hash = hash_password(staff_password)
    return demo_unusable, citizen_hash, staff_hash


def default_seed_users() -> list[StoredUser]:
    """`complaint_app.users` 최초 초기화 시 적재할 기본 계정을 반환합니다.

    Returns:
        시연 호환 2계정, 기본 민원인 1계정, 담당자 3계정(총 6개) 목록입니다.
    """
    citizen_pw = os.environ.get(
        "COMPLAINT_CITIZEN_INIT_PASSWORD", DEFAULT_CITIZEN_INIT_PASSWORD
    )
    staff_pw = os.environ.get(
        "COMPLAINT_STAFF_INIT_PASSWORD", DEFAULT_STAFF_INIT_PASSWORD
    )
    demo_hash, citizen_hash, staff_hash = _cached_seed_hashes(citizen_pw, staff_pw)
    return [
        StoredUser(
            id="citizen-demo",
            login_id="citizen-demo",
            display_name="시연 시민",
            role="citizen",
            password_hash=demo_hash,
            department=None,
            is_demo=True,
        ),
        StoredUser(
            id="staff-demo",
            login_id="staff-demo",
            display_name="김담당",
            role="staff",
            password_hash=demo_hash,
            department=None,
            is_demo=True,
        ),
        StoredUser(
            id="citizen-01",
            login_id="citizen_01",
            display_name="청주시민",
            role="citizen",
            password_hash=citizen_hash,
            department=None,
            is_demo=False,
        ),
        StoredUser(
            id="staff-admin",
            login_id="staff_admin",
            display_name="청주시 민원과 총괄",
            role="staff",
            password_hash=staff_hash,
            department=None,
            is_demo=False,
        ),
        StoredUser(
            id="staff-seowon",
            login_id="staff_seowon",
            display_name="서원구 건설과 담당자",
            role="staff",
            password_hash=staff_hash,
            department="서원구 건설과",
            is_demo=False,
        ),
        StoredUser(
            id="staff-heungdeok",
            login_id="staff_heungdeok",
            display_name="흥덕구 환경위생과 담당자",
            role="staff",
            password_hash=staff_hash,
            department="흥덕구 환경위생과",
            is_demo=False,
        ),
    ]


class LoginRateLimiter:
    """비밀번호 연속 실패 시 계정을 일시 잠금해 무차별 대입을 방지합니다."""

    def __init__(
        self,
        *,
        max_failures: int = LOGIN_MAX_FAILURES,
        lock_seconds: float = LOGIN_LOCK_SECONDS,
    ) -> None:
        """실패 한도와 잠금 시간(초)을 초기화합니다.

        Args:
            max_failures: 잠금이 발동되는 연속 실패 횟수입니다.
            lock_seconds: 잠금 유지 시간(초)입니다.
        """
        self._max_failures = max(1, max_failures)
        self._lock_seconds = max(1.0, lock_seconds)
        self._lock = Lock()
        self._failures: dict[str, tuple[int, float]] = {}

    def check_allowed(self, login_id: str) -> None:
        """해당 로그인 아이디가 잠금 상태인지 검사합니다.

        Args:
            login_id: 로그인 시도 아이디입니다.

        Raises:
            AppError: 잠금 기간 중이면 429 오류를 발생합니다.
        """
        key = login_id.casefold()
        now = time.monotonic()
        with self._lock:
            entry = self._failures.get(key)
            if entry is None:
                return
            count, unlock_at = entry
            if unlock_at > now:
                remain = max(1, int(unlock_at - now))
                raise AppError(
                    429,
                    "auth_locked",
                    f"로그인 시도가 여러 번 실패했습니다. {remain}초 뒤 다시 시도해 주세요.",
                )
            if count >= self._max_failures:
                self._failures.pop(key, None)

    def record_failure(self, login_id: str) -> None:
        """비밀번호 불일치 실패 횟수를 누적하고 한도 도달 시 잠금을 설정합니다.

        장기 실행 시 존재하지 않는 아이디 시도로 메모리가 무한 증가하지 않도록
        잠금이 만료된 항목을 주기적으로 정리합니다.

        Args:
            login_id: 실패한 로그인 아이디입니다.
        """
        key = login_id.casefold()
        now = time.monotonic()
        with self._lock:
            if len(self._failures) >= 512:
                expired = [
                    k
                    for k, (cnt, unlock_at) in self._failures.items()
                    if cnt >= self._max_failures and unlock_at <= now
                ]
                for k in expired:
                    self._failures.pop(k, None)
            count, _ = self._failures.get(key, (0, 0.0))
            count += 1
            unlock_at = now + self._lock_seconds if count >= self._max_failures else 0.0
            self._failures[key] = (count, unlock_at)

    def reset(self, login_id: str) -> None:
        """로그인 성공 시 실패 누적 카운터를 초기화합니다.

        Args:
            login_id: 로그인에 성공한 아이디입니다.
        """
        with self._lock:
            self._failures.pop(login_id.casefold(), None)


GUEST_ID_RE = re.compile(r"^guest-[0-9a-f]{32}$")
GUEST_COMPLAINT_LIMIT = 5


class SlidingWindowLimiter:
    """키(보통 클라이언트 IP)별 최근 시간 창의 이벤트 횟수를 제한하는 메모리 제한기입니다.

    Args:
        max_events: 시간 창 안에서 허용하는 최대 횟수입니다.
        window_seconds: 시간 창 길이(초)입니다.
    """

    def __init__(self, max_events: int, window_seconds: float) -> None:
        """제한 한도와 빈 이벤트 기록을 초기화합니다.

        Args:
            max_events: 시간 창 안에서 허용하는 최대 횟수입니다.
            window_seconds: 시간 창 길이(초)입니다.
        """
        self._max = max_events
        self._window = window_seconds
        self._events: dict[str, list[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, message: str) -> None:
        """이벤트 1회를 기록하고 한도를 넘으면 429를 발생합니다.

        Args:
            key: 제한 단위(클라이언트 IP 등)입니다.
            message: 한도 초과 시 사용자에게 보일 안내 문구입니다.

        Raises:
            AppError: 시간 창 안의 횟수가 한도에 도달해 있으면 429를 발생합니다.
        """
        now = time.monotonic()
        with self._lock:
            if len(self._events) >= 2048:
                for k in [
                    k
                    for k, stamps in self._events.items()
                    if not stamps or stamps[-1] <= now - self._window
                ]:
                    self._events.pop(k, None)
            stamps = [s for s in self._events.get(key, []) if s > now - self._window]
            if len(stamps) >= self._max:
                self._events[key] = stamps
                raise AppError(429, "rate_limited", message)
            stamps.append(now)
            self._events[key] = stamps


class AuthService:
    """민원인·담당자 아이디·비밀번호 로그인, 간단 가입, 게스트·세션 검증을 관리합니다.

    Args:
        repository: `users` 영속 저장을 제공하는 업무 저장소입니다.
    """

    def __init__(self, repository: ComplaintRepository) -> None:
        """인증 서비스와 로그인 실패 제한기를 초기화합니다.

        Args:
            repository: 사용자 조회·저장을 제공하는 저장소입니다.
        """
        self.repository = repository
        self.rate_limiter = LoginRateLimiter()
        # 로그인 없는 게스트 세션 발급·접수의 IP 단위 남용 방지(시간당 10회)입니다.
        self.guest_session_limiter = SlidingWindowLimiter(10, 3600.0)
        self.guest_complaint_limiter = SlidingWindowLimiter(10, 3600.0)
        # 응대 검사기(외부 LLM 호출)의 담당자 계정별 실행 횟수 제한(10분당 20회)입니다.
        self.assist_limiter = SlidingWindowLimiter(20, 600.0)

    def create_guest(self) -> Actor:
        """로그인 없이 민원을 접수하는 게스트 `Actor`를 만듭니다. DB 계정은 만들지 않습니다.

        Returns:
            무작위 128비트 ID를 가진 민원인 역할의 게스트 `Actor`입니다.
        """
        return Actor(
            id="guest-" + uuid4().hex,
            login_id=None,
            display_name="게스트",
            role="citizen",
            department=None,
            auth_mode="guest",
            demo=False,
            guest=True,
        )

    def register_citizen(self, body: RegisterInput) -> Actor:
        """아이디·비밀번호·이름으로 새 민원인 계정을 `users` 테이블에 생성합니다.

        Args:
            body: 로그인 아이디·비밀번호·표시 이름입니다.

        Returns:
            생성된 민원인 `Actor` 모델입니다.

        Raises:
            AppError: 아이디가 이미 존재하면 409 오류를 발생합니다.
        """
        if self.repository.get_user_by_login(body.login_id) is not None:
            raise AppError(
                409,
                "login_id_taken",
                "이미 사용 중인 아이디입니다. 다른 아이디를 입력해 주세요.",
            )
        now = utcnow()
        user = StoredUser(
            id="USR-CIT-" + uuid4().hex[:10].upper(),
            login_id=body.login_id,
            display_name=body.display_name,
            role="citizen",
            password_hash=hash_password(body.password),
            department=None,
            is_demo=False,
            active=True,
            created_at=now,
            last_login_at=now,
        )
        saved = self.repository.create_user(user)
        return saved.to_actor(auth_mode="password")

    def login(self, body: LoginInput) -> Actor:
        """민원인 또는 담당자 계정의 아이디·비밀번호를 검증하고 로그인합니다.

        Args:
            body: 로그인 아이디·비밀번호·선택 기대 역할입니다.

        Returns:
            인증된 사용자 `Actor` 모델입니다.

        Raises:
            AppError: 잠금·계정 없음·비활성·비밀번호 불일치·역할 불일치 시 발생합니다.
        """
        self.rate_limiter.check_allowed(body.login_id)
        # 같은 아이디를 두 사이트에서 쓰는 시연 계정은 `<아이디>@<역할>` 내부 아이디로 먼저 찾는다.
        # 가입·담당자 생성은 `@`를 막으므로 일반 사용자가 이 이름을 선점할 수 없다.
        candidates = [body.login_id]
        if body.expected_role:
            candidates.insert(0, f"{body.login_id}@{body.expected_role}")
        user = None
        for candidate in candidates:
            user = self.repository.get_user_by_login(candidate)
            if user is not None:
                break
        if (
            user is None
            or not user.active
            or user.is_demo
            or not verify_password(user.password_hash, body.password)
        ):
            self.rate_limiter.record_failure(body.login_id)
            raise AppError(
                401,
                "invalid_credentials",
                "아이디 또는 비밀번호가 올바르지 않습니다.",
            )
        if body.expected_role and user.role != body.expected_role:
            role_label = "담당자" if body.expected_role == "staff" else "민원인"
            raise AppError(
                403,
                "role_mismatch",
                f"{role_label} 전용 로그인 화면입니다. 계정 유형을 확인해 주세요.",
            )
        self.rate_limiter.reset(body.login_id)
        self.repository.touch_user_login(user.id)
        return user.to_actor(auth_mode="password")

    def demo_actor(self, role: Role) -> Actor:
        """로컬 시연 전환용 기본 민원인·담당자 계정을 반환합니다.

        Args:
            role: 선택할 시연 역할(`citizen` 또는 `staff`)입니다.

        Returns:
            `users` 테이블에 연결된 시연 `Actor` 모델입니다.
        """
        user_id = "staff-demo" if role == "staff" else "citizen-demo"
        found = self.repository.get_user_by_id(user_id)
        if found is not None and found.active:
            return found.to_actor(auth_mode="demo")
        return Actor(
            id=user_id,
            login_id=user_id,
            display_name="김담당" if role == "staff" else "시연 시민",
            role=role,
            department=None,
            auth_mode="demo",
            demo=True,
        )

    def resolve_session_actor(
        self,
        *,
        user_id: str | None,
        role: str | None,
        auth_mode: str | None,
    ) -> Actor:
        """Flask 세션 쿠키의 사용자 ID와 역할을 DB `users`와 대조해 복원합니다.

        Args:
            user_id: 세션에 저장된 `users.id`입니다.
            role: 세션에 저장된 역할 문자열입니다.
            auth_mode: 세션에 저장된 인증 방식 문자열입니다.

        Returns:
            검증된 최신 `Actor` 모델입니다.

        Raises:
            AppError: 세션이 없거나 계정이 비활성화되었으면 401을 발생합니다.
        """
        if auth_mode == "guest":
            if role != "citizen" or not user_id or not GUEST_ID_RE.fullmatch(user_id):
                raise AppError(
                    401, "session_invalid", "게스트 세션이 올바르지 않습니다."
                )
            return Actor(
                id=user_id,
                login_id=None,
                display_name="게스트",
                role="citizen",
                department=None,
                auth_mode="guest",
                demo=False,
                guest=True,
            )
        if user_id:
            found = self.repository.get_user_by_id(user_id)
            if found is None or not found.active:
                raise AppError(
                    401,
                    "session_invalid",
                    "계정 세션이 만료되었거나 비활성화되었습니다. 다시 로그인해 주세요.",
                )
            resolved_mode: AuthMode = (
                "password"
                if auth_mode == "password"
                else ("demo" if found.is_demo else "password")
            )
            return found.to_actor(auth_mode=resolved_mode)
        if role in ("citizen", "staff"):
            return self.demo_actor("staff" if role == "staff" else "citizen")
        raise AppError(
            401,
            "authentication_required",
            "먼저 로그인하거나 시연 계정을 선택해 주세요.",
        )
