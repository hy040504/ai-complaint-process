"""운영용 로컬 계정·비밀번호 해시(`scrypt`)·시민 본인확인 OTP·로그인 잠금 인증 모듈입니다.

실제 외부 이동통신사 PASS/공동인증서/행정 SSO 연동은 별도 인프라 범위이며,
이 모듈은 서버 측 `scrypt` 비밀번호 검증, 2단계 시민 본인확인 코드 검증,
부서별 담당자 권한(`department`), 브루트포스 잠금, 세션 사용자 검증을 제공합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
import hashlib
import hmac
import os
import re
import secrets
from threading import Lock
import time
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from werkzeug.security import check_password_hash, generate_password_hash

from src.complaints.errors import AppError
from src.complaints.models import (
    Actor,
    AuthMode,
    CitizenRegisterInput,
    CitizenVerifyRequest,
    CitizenVerifyResponse,
    LoginInput,
    Role,
    utcnow,
)

if TYPE_CHECKING:
    from src.complaints.repository import ComplaintRepository

# 로컬 개발·검증용 초기 담당자 비밀번호입니다. 운영 시 반드시 COMPLAINT_STAFF_INIT_PASSWORD로 교체합니다.
DEFAULT_STAFF_INIT_PASSWORD = os.environ.get(
    "COMPLAINT_STAFF_INIT_PASSWORD", "cheongju-staff-2026!"
)
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SECONDS = 60.0


@dataclass(frozen=True)
class StoredUser:
    """`complaint_app.users` 테이블에 저장되는 내부 사용자 레코드입니다.

    비밀번호 해시(`password_hash`)는 API 응답 모델(`Actor`)에 절대 노출하지 않습니다.

    Attributes:
        id: 사용자 고유 식별자(`users.id`)입니다.
        login_id: 로그인 아이디(유니크)입니다.
        display_name: 화면·이력에 표시할 이름입니다.
        role: `citizen` 또는 `staff`입니다.
        password_hash: `werkzeug.security` `scrypt` 해시 문자열입니다.
        department: 담당자 소속 부서명입니다. 총괄 담당자·시민은 None입니다.
        verified: 시민 본인확인 또는 담당자 계정 인증 여부입니다.
        phone_last4: 마스킹 확인용 휴대전화 끝 4자리입니다(원문 번호 미저장).
        is_demo: 시연 원클릭 계정 여부입니다.
        active: 계정 활성 상태입니다. 비활성 계정은 세션·로그인을 거부합니다.
        created_at: 계정 생성 UTC 시각입니다.
        last_login_at: 마지막 비밀번호 로그인 UTC 시각입니다.
    """

    id: str
    login_id: str
    display_name: str
    role: Role
    password_hash: str
    department: str | None = None
    verified: bool = False
    phone_last4: str | None = None
    is_demo: bool = False
    active: bool = True
    created_at: datetime = field(default_factory=utcnow)
    last_login_at: datetime | None = None

    def to_actor(self, *, auth_mode: AuthMode | None = None) -> Actor:
        """비밀번호 해시를 제거한 안전한 응답용 `Actor` 모델로 변환합니다.

        Args:
            auth_mode: 세션에 기록된 인증 방식입니다. 생략하면 계정 유형으로 추정합니다.

        Returns:
            API·세션에서 사용하는 `Actor` 모델입니다.
        """
        resolved_mode: AuthMode = auth_mode or (
            "demo"
            if self.is_demo
            else ("verified_account" if self.role == "citizen" else "password")
        )
        return Actor(
            id=self.id,
            login_id=self.login_id,
            display_name=self.display_name,
            role=self.role,
            department=self.department,
            verified=self.verified,
            auth_mode=resolved_mode,
            demo=self.is_demo or resolved_mode == "demo",
        )


def hash_password(raw_password: str) -> str:
    """비밀번호 원문을 `scrypt` 솔트 해시로 변환합니다.

    Args:
        raw_password: 평문 비밀번호 문자열입니다.

    Returns:
        DB에 안전하게 저장할 해시 문자열입니다.
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


def validate_password_strength(raw_password: str) -> None:
    """회원가입 비밀번호가 최소 보안 기준(8자 이상, 영문+숫자 조합)을 지키는지 검사합니다.

    Args:
        raw_password: 사용자가 설정하려는 비밀번호입니다.

    Raises:
        AppError: 영문·숫자 조합이 없거나 길이가 부족하면 422 오류를 발생합니다.
    """
    if (
        len(raw_password) < 8
        or not re.search(r"[A-Za-z]", raw_password)
        or not re.search(r"\d", raw_password)
    ):
        raise AppError(
            422,
            "weak_password",
            "비밀번호는 8자 이상이며 영문과 숫자를 모두 포함해야 합니다.",
        )


@lru_cache(maxsize=4)
def _cached_seed_hashes(staff_password: str) -> tuple[str, str]:
    """초기 시드 계정의 `scrypt` 해시를 프로세스당 한 번만 계산해 캐시합니다.

    Args:
        staff_password: 담당자 초기 비밀번호 문자열입니다.

    Returns:
        `(시연 전용 비활성 랜덤 해시, 담당자 초기 비밀번호 해시)` 튜플입니다.
    """
    # 시연 원클릭 계정은 비밀번호 로그인을 막기 위해 임의 난수 해시를 부여합니다.
    demo_unusable = hash_password(secrets.token_urlsafe(32))
    staff_hash = hash_password(staff_password)
    return demo_unusable, staff_hash


def default_seed_users() -> list[StoredUser]:
    """`complaint_app.users` 최초 초기화 시 적재할 기본 시연·담당자 계정을 반환합니다.

    Returns:
        시연 2계정과 부서별 담당자 3계정(총 5개) 목록입니다.
    """
    staff_pw = os.environ.get(
        "COMPLAINT_STAFF_INIT_PASSWORD", DEFAULT_STAFF_INIT_PASSWORD
    )
    demo_hash, staff_hash = _cached_seed_hashes(staff_pw)
    return [
        StoredUser(
            id="citizen-demo",
            login_id="citizen-demo",
            display_name="시연 시민",
            role="citizen",
            password_hash=demo_hash,
            department=None,
            verified=True,
            phone_last4="0000",
            is_demo=True,
        ),
        StoredUser(
            id="staff-demo",
            login_id="staff-demo",
            display_name="김담당",
            role="staff",
            password_hash=demo_hash,
            department=None,
            verified=True,
            is_demo=True,
        ),
        StoredUser(
            id="staff-admin",
            login_id="staff_admin",
            display_name="청주시 민원과 총괄",
            role="staff",
            password_hash=staff_hash,
            department=None,
            verified=True,
            is_demo=False,
        ),
        StoredUser(
            id="staff-seowon",
            login_id="staff_seowon",
            display_name="서원구 건설과 담당자",
            role="staff",
            password_hash=staff_hash,
            department="서원구 건설과",
            verified=True,
            is_demo=False,
        ),
        StoredUser(
            id="staff-heungdeok",
            login_id="staff_heungdeok",
            display_name="흥덕구 환경위생과 담당자",
            role="staff",
            password_hash=staff_hash,
            department="흥덕구 환경위생과",
            verified=True,
            is_demo=False,
        ),
    ]


@dataclass
class _VerificationChallenge:
    """시민 2단계 본인확인용 6자리 인증코드 챌린지 상태입니다."""

    challenge_id: str
    name: str
    phone_hash: str
    phone_last4: str
    code: str
    expires_at: float
    attempts: int = 0
    consumed: bool = False


class CitizenVerificationManager:
    """시민 회원가입용 6자리 본인확인 OTP 발급·검증을 스레드 안전하게 관리합니다."""

    def __init__(self, *, ttl_seconds: int = OTP_TTL_SECONDS) -> None:
        """만료 시간과 내부 챌린지 저장소를 초기화합니다.

        Args:
            ttl_seconds: 인증코드 유효 시간(초)입니다.
        """
        self._ttl_seconds = max(30, ttl_seconds)
        self._lock = Lock()
        self._challenges: dict[str, _VerificationChallenge] = {}

    def issue(
        self, name: str, phone: str, *, expose_demo_code: bool = True
    ) -> CitizenVerifyResponse:
        """6자리 난수 인증코드를 발급하고 마스킹된 전화번호와 챌린지 ID를 반환합니다.

        Args:
            name: 본인확인 신청자 이름입니다.
            phone: 휴대전화 번호 원문입니다(해시·끝 4자리만 보관).
            expose_demo_code: 로컬 검증용 `demoCode`를 응답에 포함할지 여부입니다.

        Returns:
            본인확인 1단계 응답 모델입니다.
        """
        digits = re.sub(r"\D", "", phone)
        last4 = digits[-4:]
        masked = f"{digits[:3]}-****-{last4}"
        phone_hash = hashlib.sha256(digits.encode("utf-8")).hexdigest()
        challenge_id = "VER-" + uuid4().hex[:16].upper()
        code = f"{secrets.randbelow(1_000_000):06d}"
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            self._challenges[challenge_id] = _VerificationChallenge(
                challenge_id=challenge_id,
                name=name.strip(),
                phone_hash=phone_hash,
                phone_last4=last4,
                code=code,
                expires_at=now + self._ttl_seconds,
            )
        mode: Literal["local_otp", "external_sms"] = (
            "local_otp" if expose_demo_code else "external_sms"
        )
        return CitizenVerifyResponse(
            challenge_id=challenge_id,
            expires_in_seconds=self._ttl_seconds,
            masked_phone=masked,
            verification_mode=mode,
            demo_code=code if expose_demo_code else None,
        )

    def verify_and_consume(self, challenge_id: str, code: str) -> str:
        """제출된 6자리 인증코드를 상수 시간 검증하고 1회 소비합니다.

        Args:
            challenge_id: 1단계에서 발급한 챌린지 ID입니다.
            code: 사용자가 입력한 6자리 인증코드입니다.

        Returns:
            검증이 완료된 휴대전화 끝 4자리 문자열입니다.

        Raises:
            AppError: 만료·존재하지 않음·횟수 초과·코드 불일치 시 발생합니다.
        """
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            item = self._challenges.get(challenge_id)
            if item is None or item.consumed or now > item.expires_at:
                raise AppError(
                    400,
                    "verification_expired",
                    "본인확인 인증코드가 만료되었거나 유효하지 않습니다. 다시 요청해 주세요.",
                )
            if item.attempts >= OTP_MAX_ATTEMPTS:
                self._challenges.pop(challenge_id, None)
                raise AppError(
                    429,
                    "verification_locked",
                    "인증코드 입력 횟수를 초과했습니다. 새 인증코드를 발급받아 주세요.",
                )
            if not hmac.compare_digest(item.code, code.strip()):
                item.attempts += 1
                raise AppError(
                    400,
                    "verification_failed",
                    f"본인확인 인증코드가 일치하지 않습니다 ({item.attempts}/{OTP_MAX_ATTEMPTS}).",
                )
            item.consumed = True
            self._challenges.pop(challenge_id, None)
            return item.phone_last4

    def _purge_expired(self, now: float) -> None:
        """만료된 본인확인 챌린지를 메모리에서 정리합니다.

        Args:
            now: `time.monotonic()` 기준 현재 시각입니다.
        """
        stale = [
            cid
            for cid, item in self._challenges.items()
            if item.consumed or now > item.expires_at
        ]
        for cid in stale:
            self._challenges.pop(cid, None)


class LoginRateLimiter:
    """로그인 비밀번호 연속 실패 시 계정을 일시 잠금해 무차별 대입을 방지합니다."""

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

        Args:
            login_id: 실패한 로그인 아이디입니다.
        """
        key = login_id.casefold()
        now = time.monotonic()
        with self._lock:
            count, _ = self._failures.get(key, (0, 0.0))
            count += 1
            unlock_at = now + self._lock_seconds if count >= self._max_failures else 0.0
            self._failures[key] = (count, unlock_at)

    def reset(self, login_id: str) -> None:
        """로그인 성공 시 실패 누적 카운터를 초기화합니다.

        Args:
            login_id: 인증에 성공한 로그인 아이디입니다.
        """
        with self._lock:
            self._failures.pop(login_id.casefold(), None)


class AuthService:
    """시민 본인확인 가입·실계정 비밀번호 로그인·세션 사용자 조회를 총괄합니다.

    Args:
        repository: `users` 영속 저장을 제공하는 업무 저장소입니다.
        expose_demo_otp: 로컬 OTP 챌린지 응답에 `demoCode`를 노출할지 여부입니다.
    """

    def __init__(
        self,
        repository: ComplaintRepository,
        *,
        expose_demo_otp: bool = True,
    ) -> None:
        """인증 서비스와 본인확인·잠금 관리자를 초기화합니다.

        Args:
            repository: 사용자 조회·저장을 제공하는 저장소입니다.
            expose_demo_otp: 외부 SMS 미연동 로컬 환경에서 확인용 코드를 내려줄지 여부입니다.
        """
        self.repository = repository
        self.expose_demo_otp = expose_demo_otp
        self.verifications = CitizenVerificationManager()
        self.rate_limiter = LoginRateLimiter()

    def request_citizen_verification(
        self, body: CitizenVerifyRequest
    ) -> CitizenVerifyResponse:
        """시민 회원가입 전 본인확인 6자리 코드를 발급합니다.

        Args:
            body: 신청자 이름과 휴대전화 번호입니다.

        Returns:
            챌린지 ID와 마스킹된 연락처 응답입니다.
        """
        return self.verifications.issue(
            body.name, body.phone, expose_demo_code=self.expose_demo_otp
        )

    def register_citizen(self, body: CitizenRegisterInput) -> Actor:
        """본인확인 코드를 검증하고 새 시민 계정을 `users` 테이블에 생성합니다.

        Args:
            body: 아이디·비밀번호·이름·본인확인 챌린지·6자리 코드입니다.

        Returns:
            본인확인이 완료된 새 시민 `Actor` 모델입니다.

        Raises:
            AppError: 약한 비밀번호·인증코드 실패·아이디 중복 시 발생합니다.
        """
        validate_password_strength(body.password)
        if self.repository.get_user_by_login(body.login_id) is not None:
            raise AppError(
                409,
                "login_id_taken",
                "이미 사용 중인 아이디입니다. 다른 아이디를 입력해 주세요.",
            )
        phone_last4 = self.verifications.verify_and_consume(
            body.challenge_id, body.code
        )
        now = utcnow()
        user = StoredUser(
            id="USR-CIT-" + uuid4().hex[:10].upper(),
            login_id=body.login_id,
            display_name=body.display_name,
            role="citizen",
            password_hash=hash_password(body.password),
            department=None,
            verified=True,
            phone_last4=phone_last4,
            is_demo=False,
            active=True,
            created_at=now,
            last_login_at=now,
        )
        saved = self.repository.create_user(user)
        return saved.to_actor(auth_mode="verified_account")

    def login(self, body: LoginInput) -> Actor:
        """시민 또는 담당자 실계정의 아이디·비밀번호를 검증하고 로그인합니다.

        Args:
            body: 로그인 아이디·비밀번호·선택 기대 역할입니다.

        Returns:
            인증된 사용자 `Actor` 모델입니다.

        Raises:
            AppError: 잠금·계정 없음·비활성·비밀번호 불일치·역할 불일치 시 발생합니다.
        """
        self.rate_limiter.check_allowed(body.login_id)
        user = self.repository.get_user_by_login(body.login_id)
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
            role_label = "담당자" if body.expected_role == "staff" else "시민"
            raise AppError(
                403,
                "role_mismatch",
                f"{role_label} 전용 로그인 화면입니다. 계정 유형을 확인해 주세요.",
            )
        self.rate_limiter.reset(body.login_id)
        self.repository.touch_user_login(user.id)
        mode: AuthMode = "verified_account" if user.role == "citizen" else "password"
        return user.to_actor(auth_mode=mode)

    def demo_actor(self, role: Role) -> Actor:
        """로컬 시연 전환용 기본 시민·담당자 계정을 반환합니다.

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
            verified=True,
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
                else (
                    "verified_account"
                    if auth_mode == "verified_account"
                    else ("demo" if found.is_demo else "password")
                )
            )
            return found.to_actor(auth_mode=resolved_mode)
        if role in ("citizen", "staff"):
            return self.demo_actor("staff" if role == "staff" else "citizen")
        raise AppError(
            401,
            "authentication_required",
            "먼저 로그인하거나 시연 계정을 선택해 주세요.",
        )
