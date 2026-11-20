"""담당자 실시간 SSE 작업 모니터용 커서 기반 이벤트 브로커입니다.

이벤트 페이로드에는 민원 원문, 미게시 초안 본문, 비밀 키, 내부 추론 과정을
포함하지 않고 작업 식별자·단계·시각 메타데이터만 전달합니다.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from queue import Empty, Full, Queue
from threading import Lock
import time
from typing import Any, Literal

StaffEventType = Literal[
    "ai_job.stage_changed",
    "ai_job.completed",
    "ai_job.failed",
    "ai_job.cancelled",
    "complaint.created",
    "complaint.updated",
    "complaint.deleted",
]

_RESYNC_SENTINEL = object()


def _iso_utc_now() -> str:
    """현재 UTC 시각을 Z 표기 ISO-8601 문자열로 반환합니다."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def format_sse_message(
    event_name: str,
    payload: dict[str, Any],
    *,
    event_id: int | None = None,
) -> str:
    """SSE 규격에 맞춘 단일 이벤트 프레임 문자열을 만듭니다.

    Args:
        event_name: SSE `event:` 필드 이름입니다.
        payload: JSON으로 직렬화할 이벤트 본문 사전입니다.
        event_id: 선택적인 `id:` 커서 번호입니다.

    Returns:
        빈 줄로 끝나는 SSE 이벤트 프레임 문자열입니다.
    """
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")
    lines.append("data: " + json.dumps(payload, ensure_ascii=False))
    return "\n".join(lines) + "\n\n"


@dataclass(frozen=True)
class StaffEvent:
    """담당자 SSE 구독자에게 전달하는 단일 커밋 이벤트입니다.

    Attributes:
        event_id: 저장·갱신 커밋 순서대로 증가하는 이벤트 커서 번호입니다.
        event_type: 작업 또는 민원 상태 변화 유형입니다.
        complaint_id: 대상 민원 식별자입니다.
        context_version: 이벤트 시점의 민원 내용 버전입니다.
        attempt: 현재 AI 작업 시도 번호입니다.
        job_status: 현재 AI 작업 상태입니다.
        stage: 화면에 표시할 짧은 작업 단계 안내 문구입니다.
        occurred_at: 이벤트 발생 UTC 시각(ISO-8601)입니다.
    """

    event_id: int
    event_type: StaffEventType
    complaint_id: str
    context_version: int
    attempt: int
    job_status: str
    stage: str
    occurred_at: str

    def to_payload(self) -> dict[str, Any]:
        """민감 본문 없이 camelCase 메타데이터 사전으로 직렬화합니다.

        Returns:
            브라우저 `EventSource`에 전달할 안전한 이벤트 사전입니다.
        """
        return {
            "eventId": self.event_id,
            "type": self.event_type,
            "complaintId": self.complaint_id,
            "contextVersion": self.context_version,
            "attempt": self.attempt,
            "jobStatus": self.job_status,
            "stage": self.stage,
            "occurredAt": self.occurred_at,
        }

    def to_sse(self) -> str:
        """커서 `id`와 이벤트 유형이 포함된 SSE 프레임으로 변환합니다.

        Returns:
            표준 `text/event-stream` 프레임 문자열입니다.
        """
        return format_sse_message(
            self.event_type, self.to_payload(), event_id=self.event_id
        )


class StaffEventBroker:
    """스레드 안전한 담당자 SSE 발행·구독·커서 재전송 브로커입니다.

    Args:
        max_history: 재연결(`Last-Event-ID`) 재전송용으로 보관할 최근 이벤트 수입니다.
        max_queue_size: 구독자별 대기열 최대 길이입니다. 초과 시 재동기화를 요청합니다.
    """

    def __init__(self, *, max_history: int = 256, max_queue_size: int = 64) -> None:
        """브로커 내부 링 버퍼와 구독자 목록을 초기화합니다.

        Args:
            max_history: 재전송 이력 최대 보관 개수입니다.
            max_queue_size: 느린 구독자 보호용 대기열 상한입니다.
        """
        self._lock = Lock()
        self._cursor = 0
        self._history: deque[StaffEvent] = deque(maxlen=max(1, max_history))
        self._subscribers: set[Queue[StaffEvent | object]] = set()
        self._max_queue_size = max(1, max_queue_size)

    @property
    def cursor(self) -> int:
        """가장 최근 커밋된 이벤트 커서 번호를 반환합니다."""
        with self._lock:
            return self._cursor

    @property
    def subscriber_count(self) -> int:
        """현재 연결된 SSE 구독자 수를 반환합니다."""
        with self._lock:
            return len(self._subscribers)

    def publish(
        self,
        event_type: StaffEventType,
        complaint_id: str,
        *,
        context_version: int = 1,
        attempt: int = 0,
        job_status: str = "queued",
        stage: str = "",
    ) -> StaffEvent:
        """커밋이 완료된 변경을 새 커서 번호로 기록하고 모든 구독자에게 전달합니다.

        Args:
            event_type: 발행할 이벤트 유형입니다.
            complaint_id: 대상 민원 ID입니다.
            context_version: 민원 내용 버전입니다.
            attempt: 작업 시도 번호입니다.
            job_status: 현재 AI 작업 상태입니다.
            stage: 짧은 단계 안내 문구입니다.

        Returns:
            새로 발행된 `StaffEvent` 인스턴스입니다.
        """
        with self._lock:
            self._cursor += 1
            event = StaffEvent(
                event_id=self._cursor,
                event_type=event_type,
                complaint_id=complaint_id,
                context_version=context_version,
                attempt=attempt,
                job_status=job_status,
                stage=stage[:140],
                occurred_at=_iso_utc_now(),
            )
            self._history.append(event)
            for queue in list(self._subscribers):
                try:
                    queue.put_nowait(event)
                except Full:
                    # 느린 구독자의 대기열이 가득 차면 오래된 항목을 비우고 스냅샷 재조회 신호를 남깁니다.
                    try:
                        while True:
                            queue.get_nowait()
                    except Empty:
                        pass
                    try:
                        queue.put_nowait(_RESYNC_SENTINEL)
                    except Full:
                        pass
            return event

    def _replay_since_locked(self, last_event_id: int) -> tuple[list[StaffEvent], bool]:
        """락을 보유한 상태에서 `last_event_id` 이후 누락 이벤트와 재동기화 여부를 계산합니다.

        Args:
            last_event_id: 클라이언트가 마지막으로 수신한 이벤트 커서 번호입니다.

        Returns:
            `(재전송 이벤트 목록, 스냅샷 재동기화 필요 여부)` 튜플입니다.
        """
        if last_event_id < 0:
            return [], True
        if last_event_id == self._cursor:
            return [], False
        if last_event_id > self._cursor:
            # 서버 재기동 등으로 커서가 초기화된 경우 전체 스냅샷 재조회를 안내합니다.
            return [], True
        if not self._history:
            return [], True
        oldest_id = self._history[0].event_id
        if last_event_id < oldest_id - 1:
            return [], True
        return [ev for ev in self._history if ev.event_id > last_event_id], False

    def replay_since(self, last_event_id: int) -> tuple[list[StaffEvent], bool]:
        """지정한 `last_event_id` 이후 누락 이벤트를 조회하거나 재동기화 필요 여부를 판정합니다.

        Args:
            last_event_id: 클라이언트가 마지막으로 수신한 이벤트 커서 번호입니다.

        Returns:
            `(재전송 이벤트 목록, 스냅샷 재동기화 필요 여부)` 튜플입니다.
        """
        with self._lock:
            return self._replay_since_locked(last_event_id)

    def subscribe(
        self,
        last_event_id: int | None = None,
        *,
        ai_connected: bool = False,
        heartbeat_seconds: float = 15.0,
        max_events: int | None = None,
        max_seconds: float | None = None,
    ) -> Iterator[str]:
        """담당자용 SSE 이벤트 프레임을 생성하는 이터레이터를 반환합니다.

        Args:
            last_event_id: 재연결 시 `Last-Event-ID`로 전달된 마지막 커서입니다.
            ai_connected: 실제 RAG+LLM 백그라운드 워커 연결 여부입니다.
            heartbeat_seconds: 이벤트가 없을 때 연결 유지 하트비트를 보내는 간격(초)입니다.
            max_events: 테스트용 최대 전달 데이터 이벤트 수 상한입니다. None이면 무제한입니다.
            max_seconds: 테스트용 최대 유지 시간(초)입니다. None이면 무제한입니다.

        Yields:
            브라우저 `EventSource`가 소비할 SSE 텍스트 청크입니다.
        """
        queue: Queue[StaffEvent | object] = Queue(maxsize=self._max_queue_size)
        with self._lock:
            self._subscribers.add(queue)
            current_cursor = self._cursor
            if last_event_id is None:
                missed: list[StaffEvent] = []
                resync = False
            else:
                missed, resync = self._replay_since_locked(last_event_id)

        sent_count = 0
        started = time.monotonic()
        last_sent_id = current_cursor if last_event_id is None else last_event_id

        try:
            yield "retry: 3000\n\n"
            yield format_sse_message(
                "connected",
                {
                    "cursor": current_cursor,
                    "aiConnected": ai_connected,
                    "occurredAt": _iso_utc_now(),
                },
            )
            if resync:
                yield format_sse_message(
                    "resync_required",
                    {
                        "reason": "cursor_expired",
                        "cursor": current_cursor,
                        "occurredAt": _iso_utc_now(),
                    },
                )
                last_sent_id = current_cursor
                sent_count += 1
                if max_events is not None and sent_count >= max_events:
                    return
            else:
                for ev in missed:
                    yield ev.to_sse()
                    last_sent_id = ev.event_id
                    sent_count += 1
                    if max_events is not None and sent_count >= max_events:
                        return

            while True:
                if max_seconds is not None:
                    remaining = max_seconds - (time.monotonic() - started)
                    if remaining <= 0:
                        return
                    wait = min(max(0.05, heartbeat_seconds), remaining)
                else:
                    wait = max(0.05, heartbeat_seconds)

                try:
                    item = queue.get(timeout=wait)
                except Empty:
                    if (
                        max_seconds is not None
                        and (time.monotonic() - started) >= max_seconds
                    ):
                        return
                    yield f": heartbeat {_iso_utc_now()}\n\n"
                    continue

                if item is _RESYNC_SENTINEL:
                    cur = self.cursor
                    yield format_sse_message(
                        "resync_required",
                        {
                            "reason": "buffer_overflow",
                            "cursor": cur,
                            "occurredAt": _iso_utc_now(),
                        },
                    )
                    last_sent_id = cur
                    sent_count += 1
                elif isinstance(item, StaffEvent):
                    if item.event_id <= last_sent_id:
                        continue
                    yield item.to_sse()
                    last_sent_id = item.event_id
                    sent_count += 1

                if max_events is not None and sent_count >= max_events:
                    return
        finally:
            with self._lock:
                self._subscribers.discard(queue)
