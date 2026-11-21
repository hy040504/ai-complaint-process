# 사례 118: 시연 민원 웹 무료 외부 공개 (Cloudflare Quick Tunnel)

- **사례 번호:** CASE-118
- **기록일:** 2026-11-21 KST
- **유형:** 운영·보안·배포·검증
- **작업 상태:** 완료(서버 `navy2025`의 민원 웹 `:5000`을 Quick Tunnel로 공개, `origin/main` 푸시 포함). 고정 주소·도메인·속도 제한은 미구현
- **관련 문서:** [원격 서버 배포](../harness/원격_서버_배포.md) · [CASE-117](사례-117-시민·담당자-사이트-분리와-원격-서버-배포-2026-11-21.md) · [서버·API 안내](../../src/README.md) · [변경 이력](../../CHANGELOG.md)

---

## 1. 요구와 선택

"시연 민원 웹을 무료로 외부 배포하고 터널링까지 진행"하라는 요청이었다.

| 후보 | 판단 |
| --- | --- |
| **Cloudflare Quick Tunnel(`cloudflared`)** | **채택.** 계정·도메인·카드 불필요, 서버가 GitHub·`trycloudflare` API에 접근 가능, 기존 인프라를 건드리지 않음 |
| Tailscale Funnel | 서버의 Tailscale은 사용자 접속 인프라(`tailcat`)와 얽혀 있고 funnel은 관리자 ACL 변경이 필요해 제외 |
| 고정 주소 터널(Cloudflare 이름 터널·도메인) | 도메인이 필요해 보류. 필요하면 후속 |

## 2. 조치 내용

| 영역 | 변경 |
| --- | --- |
| 터널 | `scripts/ops/remote/setup-tunnel.sh`: `cloudflared`를 GitHub 릴리스에서 받아 **SHA-256 다이제스트 대조 후** `~/.local/bin`에 설치, 사용자 서비스 `cheongju-tunnel`(`--url http://127.0.0.1:5000`)로 등록. `public-url.sh`로 현재 주소 확인 |
| 노출 범위 | 민원 웹 `:5000`만 공개. 응대 검사기 `:5010`(로그인 없음)과 검색 API `:8007`은 공개하지 않음 |
| 백엔드 보강 | HTTPS 요청(`X-Forwarded-Proto`)에만 `Secure` 쿠키와 HSTS, 모든 응답에 `X-Frame-Options: SAMEORIGIN`·`Referrer-Policy: same-origin`. 프록시가 붙이는 `CF-Ray` 헤더가 있는 요청은 `/docs`·`/swagger`·`/openapi*`·`/design/*`를 `404`로 숨김(로컬·SSH 터널은 그대로) |
| 브랜치 | `main`을 `origin/main`에 push(`1b96e00..b6d333b`, fast-forward). 이후 커밋도 같은 흐름으로 push |

## 3. 검증 (`2026-11-21 KST`)

| 항목 | 결과 |
| --- | --- |
| `RUN_PG_TESTS=1 pytest src/tests` / mypy | **201 passed** / 0오류 (공개 대비 테스트 2건 추가) |
| 외부(내 PC)에서 공개 주소 접속 | `/`·`/staff/`·`/api/v1/health` 200, `/docs`·`/swagger`·`/openapi.json`·`/design/ui04` **404**, 검사기 포트 접근 불가, HSTS·`X-Frame-Options`·`Referrer-Policy` 확인, 담당자 페이지 `noindex` |
| 공개 주소 경유 로그인(서버에서 호출) | 담당자 로그인 200, 쿠키 `Secure`·`HttpOnly`·`SameSite=Strict`, 다른 Origin **403**, 시민 사이트에서 담당자 계정 **403**, 비로그인 민원 목록 **401**, 존재하지 않는 계정 6회 시도에서 **429 잠금** |

## 4. 한계와 위험

- **주소가 바뀐다.** Quick Tunnel 주소는 `cheongju-tunnel`을 재시작하거나 서버가 재부팅할 때마다 새로 발급된다. 현재 주소는 서버에서 `bash scripts/ops/remote/public-url.sh`로 확인한다. 서비스 수준 보장(SLA)이 없고 시연·테스트용이다.
- **담당자 사이트도 공개된다.** `/staff/`는 계정 로그인과 잠금(같은 아이디 5회 실패 시 60초)으로만 보호된다. IP 단위 속도 제한은 없어 계정 잠금을 노린 반복 시도(서비스 방해)가 가능하다.
- **시민 가입이 열려 있다.** 누구나 계정을 만들고 첨부(파일당 5MB·민원당 5개)를 올릴 수 있어 저장 공간 남용 가능성이 있다. 가입 제한·용량 한도는 미구현이다.
- LLM 키가 없어 AI 응답은 담당자 검토로 넘어간다(`assistLlm=false`).
- TLS는 Cloudflare가 종단한다. 고정 도메인·WAF·접근 정책은 구성하지 않았다.
