"""민원 첨부파일의 매직바이트 검증, 이미지 EXIF/메타데이터 제거, 안전한 저장소를 제공합니다.

외부 이미지 라이브러리 없이 표준 라이브러리만으로 JPEG·PNG·WebP·PDF의 실제
파일 시그니처를 검사하고, 사진의 GPS·촬영기기 등 개인정보 메타데이터 청크
(JPEG APP1/COM, PNG eXIf/tEXt/iTXt/zTXt, WebP EXIF/XMP)를 제거합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
from threading import Lock
from typing import Literal, Protocol
from uuid import uuid4
import zlib

from src.complaints.errors import AppError

AllowedMime = Literal[
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
]

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 단일 첨부파일 최대 5 MiB
MAX_ATTACHMENTS_PER_COMPLAINT = 5  # 민원당 최대 5개
MAX_UPLOAD_REQUEST_BYTES = 6 * 1024 * 1024  # 멀티파트 헤더 포함 요청 상한 6 MiB

_MIME_TO_EXT: dict[AllowedMime, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}

_SAFE_NAME_RE = re.compile(r"[^0-9A-Za-z가-힣._ -]+")
_STORAGE_KEY_RE = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|webp|pdf)$")
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_META_CHUNKS = frozenset({b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME"})
# APP1~APP15(EXIF·XMP·ICC·IPTC·제조사 노트 등)와 COM을 제거합니다.
# 색 변환에 필요한 Adobe APP14(`Adobe` 시그니처)만 예외로 보존합니다.
_JPEG_STRIP_MARKERS = frozenset({*range(0xE1, 0xF0), 0xFE})


@dataclass(frozen=True)
class SanitizedFile:
    """검증과 메타데이터 제거를 마친 안전한 첨부파일 바이트와 속성입니다.

    Attributes:
        filename: 경로 문자와 제어문자를 제거하고 확장자를 맞춘 표시용 파일명입니다.
        content_type: 매직바이트로 확정한 허용 MIME 타입입니다.
        extension: 저장 키와 확장자 정합에 사용하는 소문자 확장자입니다.
        data: 메타데이터 제거 후 최종 저장할 바이트열입니다.
        size_bytes: 최종 바이트 크기입니다.
        sha256: 최종 바이트의 SHA-256 16진 해시입니다.
        is_image: 브라우저 썸네일 미리보기가 가능한 이미지 여부입니다.
        exif_stripped: 이미지에서 EXIF·XMP·텍스트 메타데이터 청크를 제거했으면 True입니다.
    """

    filename: str
    content_type: AllowedMime
    extension: str
    data: bytes
    size_bytes: int
    sha256: str
    is_image: bool
    exif_stripped: bool


def sanitize_filename(raw_name: str, expected_ext: str) -> str:
    """업로드된 원본 파일명에서 경로 탈출·제어문자를 제거하고 확장자를 정합합니다.

    Args:
        raw_name: 클라이언트가 전송한 원본 파일명입니다.
        expected_ext: 매직바이트로 판별된 실제 확장자(예: `.jpg`)입니다.

    Returns:
        안전하게 정리된 최대 120자 파일명입니다.
    """
    base = raw_name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    stem, _old_ext = os.path.splitext(base)
    cleaned_stem = _SAFE_NAME_RE.sub("_", stem).strip(" ._")
    cleaned_stem = re.sub(r"[_ ]{2,}", " ", cleaned_stem)
    if not cleaned_stem:
        cleaned_stem = "첨부파일"
    max_stem = max(1, 120 - len(expected_ext))
    return f"{cleaned_stem[:max_stem]}{expected_ext}"


def _strip_jpeg_metadata(data: bytes) -> tuple[bytes, bool]:
    """JPEG 바이트열의 구조를 검증하고 EXIF·XMP·코멘트 세그먼트를 제거합니다.

    Args:
        data: 원본 JPEG 파일 바이트입니다.

    Returns:
        `(정제된 JPEG 바이트, 메타데이터 청크를 하나 이상 제거했는지 여부)` 튜플입니다.

    Raises:
        AppError: JPEG 마커 구조가 손상되었거나 이미지 본문이 없으면 422를 발생합니다.
    """
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise AppError(422, "invalid_attachment", "올바른 JPEG 이미지가 아닙니다.")
    out = bytearray(b"\xff\xd8")
    pos = 2
    n = len(data)
    stripped = False
    saw_sos = False
    saw_eoi = False
    while pos < n:
        if data[pos] != 0xFF:
            raise AppError(
                422, "invalid_attachment", "손상된 JPEG 파일은 첨부할 수 없습니다."
            )
        while pos < n and data[pos] == 0xFF:
            pos += 1
        if pos >= n:
            break
        marker = data[pos]
        pos += 1
        if marker == 0xD9:  # EOI: 이후 바이트(트레일러)는 모두 버립니다.
            out.extend(b"\xff\xd9")
            saw_eoi = True
            if pos < n:
                stripped = True
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            out.extend((0xFF, marker))
            continue
        if pos + 2 > n:
            raise AppError(
                422, "invalid_attachment", "손상된 JPEG 세그먼트는 첨부할 수 없습니다."
            )
        seg_len = int.from_bytes(data[pos : pos + 2], "big")
        if seg_len < 2 or pos + seg_len > n:
            raise AppError(
                422, "invalid_attachment", "손상된 JPEG 세그먼트는 첨부할 수 없습니다."
            )
        segment = data[pos : pos + seg_len]
        if marker in _JPEG_STRIP_MARKERS and not (
            marker == 0xEE and segment[2:7] == b"Adobe"
        ):
            stripped = True
        else:
            out.extend((0xFF, marker))
            out.extend(segment)
        pos += seg_len
        if marker == 0xDA:
            # SOS 헤더 뒤의 엔트로피 데이터는 `FF 00`·RSTn·`FF FF` 외의 마커가 나오기 전까지
            # 그대로 복사하고, 다음 마커(다음 스캔·DHT·EOI)는 바깥 루프가 계속 처리합니다.
            saw_sos = True
            scan_start = pos
            while pos + 1 < n:
                if (
                    data[pos] == 0xFF
                    and data[pos + 1] not in (0x00, 0xFF)
                    and not (0xD0 <= data[pos + 1] <= 0xD7)
                ):
                    break
                pos += 1
            else:
                pos = n
            out.extend(data[scan_start:pos])
    if not saw_sos or len(out) < 4:
        raise AppError(422, "invalid_attachment", "이미지 본문이 없는 JPEG 파일입니다.")
    if not saw_eoi:
        out.extend(b"\xff\xd9")  # 종료 마커가 잘린 파일은 정상 종료 마커로 마감합니다.
    return bytes(out), stripped


def _strip_png_metadata(data: bytes) -> tuple[bytes, bool]:
    """PNG 바이트열의 청크 구조를 검증하고 `eXIf`/`tEXt`/`iTXt`/`zTXt`/`tIME`을 제거합니다.

    Args:
        data: 원본 PNG 파일 바이트입니다.

    Returns:
        `(정제된 PNG 바이트, 메타데이터 청크 제거 여부)` 튜플입니다.

    Raises:
        AppError: PNG 청크 구조가 손상되었거나 `IHDR`/`IEND`가 없으면 422를 발생합니다.
    """
    if len(data) < 24 or not data.startswith(_PNG_SIG):
        raise AppError(422, "invalid_attachment", "올바른 PNG 이미지가 아닙니다.")
    out = bytearray(_PNG_SIG)
    pos = 8
    n = len(data)
    stripped = False
    saw_ihdr = False
    saw_iend = False
    while pos < n:
        if pos + 12 > n:
            raise AppError(
                422, "invalid_attachment", "손상된 PNG 파일은 첨부할 수 없습니다."
            )
        length = int.from_bytes(data[pos : pos + 4], "big")
        ctype = data[pos + 4 : pos + 8]
        chunk_end = pos + 12 + length
        if chunk_end > n:
            raise AppError(
                422, "invalid_attachment", "손상된 PNG 청크는 첨부할 수 없습니다."
            )
        stored_crc = int.from_bytes(data[chunk_end - 4 : chunk_end], "big")
        if zlib.crc32(data[pos + 4 : chunk_end - 4]) & 0xFFFFFFFF != stored_crc:
            raise AppError(
                422, "invalid_attachment", "손상된 PNG 청크(CRC 불일치)입니다."
            )
        if ctype == b"IHDR":
            saw_ihdr = True
        if ctype in _PNG_META_CHUNKS:
            stripped = True
        else:
            out.extend(data[pos:chunk_end])
        pos = chunk_end
        if ctype == b"IEND":
            saw_iend = True
            if pos < n:
                stripped = True  # IEND 뒤 트레일러는 버립니다.
            break
    if not (saw_ihdr and saw_iend):
        raise AppError(422, "invalid_attachment", "완전하지 않은 PNG 이미지입니다.")
    return bytes(out), stripped


def _strip_webp_metadata(data: bytes) -> tuple[bytes, bool]:
    """WebP(RIFF) 컨테이너에서 `EXIF`·`XMP ` 청크를 제거하고 헤더 크기를 재계산합니다.

    Args:
        data: 원본 WebP 파일 바이트입니다.

    Returns:
        `(정제된 WebP 바이트, 메타데이터 청크 제거 여부)` 튜플입니다.

    Raises:
        AppError: WebP 컨테이너 구조가 손상되었으면 422를 발생합니다.
    """
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise AppError(422, "invalid_attachment", "올바른 WebP 이미지가 아닙니다.")
    body = bytearray()
    pos = 12
    n = len(data)
    stripped = False
    saw_image_chunk = False
    while pos < n:
        if pos + 8 > n:
            raise AppError(
                422, "invalid_attachment", "손상된 WebP 파일은 첨부할 수 없습니다."
            )
        fourcc = data[pos : pos + 4]
        chunk_size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        padded = chunk_size + (chunk_size & 1)
        chunk_end = pos + 8 + padded
        if chunk_end > n:
            raise AppError(
                422, "invalid_attachment", "손상된 WebP 청크는 첨부할 수 없습니다."
            )
        if fourcc in (b"EXIF", b"XMP "):
            stripped = True
        else:
            if fourcc in (b"VP8 ", b"VP8L", b"VP8X"):
                saw_image_chunk = True
            if fourcc == b"VP8X" and chunk_size >= 1:
                chunk_bytes = bytearray(data[pos:chunk_end])
                # VP8X 플래그의 EXIF(0x08)·XMP(0x04) 비트를 클리어합니다.
                chunk_bytes[8] &= ~0x0C
                body.extend(chunk_bytes)
            else:
                body.extend(data[pos:chunk_end])
        pos = chunk_end
    if not saw_image_chunk:
        raise AppError(422, "invalid_attachment", "이미지 본문이 없는 WebP 파일입니다.")
    riff_size = len(body) + 4
    return b"RIFF" + riff_size.to_bytes(4, "little") + b"WEBP" + bytes(body), stripped


def _validate_pdf(data: bytes) -> bytes:
    """PDF 매직 헤더와 종료 마커 존재 여부를 검증합니다.

    Args:
        data: 원본 PDF 파일 바이트입니다.

    Returns:
        검증을 통과한 PDF 바이트입니다.

    Raises:
        AppError: PDF 헤더 또는 종료 마커가 없으면 422를 발생합니다.
    """
    if len(data) < 16 or not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
        raise AppError(422, "invalid_attachment", "올바른 PDF 문서가 아닙니다.")
    return data


def detect_mime_from_bytes(data: bytes) -> AllowedMime:
    """파일 확장자나 브라우저 MIME 대신 실제 매직바이트로 허용 형식을 판별합니다.

    Args:
        data: 업로드된 파일 원시 바이트입니다.

    Returns:
        허용된 4종 MIME 타입 중 하나입니다.

    Raises:
        AppError: 허용하지 않는 형식이거나 위조 파일이면 422를 발생합니다.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(_PNG_SIG):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    raise AppError(
        422,
        "unsupported_attachment_type",
        "JPG·PNG·WebP 이미지 또는 PDF 파일만 첨부할 수 있습니다.",
    )


def validate_and_sanitize_upload(raw_bytes: bytes, raw_filename: str) -> SanitizedFile:
    """업로드 파일의 크기·형식을 검사하고 이미지 메타데이터를 제거해 반환합니다.

    Args:
        raw_bytes: 업로드된 원시 파일 바이트입니다.
        raw_filename: 클라이언트가 보낸 원본 파일명입니다.

    Returns:
        저장 가능한 `SanitizedFile` 레코드입니다.

    Raises:
        AppError: 빈 파일·용량 초과(413)·비허용 형식·손상 파일(422) 시 발생합니다.
    """
    if not raw_bytes:
        raise AppError(422, "empty_attachment", "비어 있는 파일은 첨부할 수 없습니다.")
    if len(raw_bytes) > MAX_ATTACHMENT_BYTES:
        raise AppError(
            413,
            "attachment_too_large",
            "첨부파일 한 개의 크기는 5MB를 넘을 수 없습니다.",
        )
    mime = detect_mime_from_bytes(raw_bytes)
    ext = _MIME_TO_EXT[mime]
    exif_stripped = False
    if mime == "image/jpeg":
        clean_bytes, exif_stripped = _strip_jpeg_metadata(raw_bytes)
    elif mime == "image/png":
        clean_bytes, exif_stripped = _strip_png_metadata(raw_bytes)
    elif mime == "image/webp":
        clean_bytes, exif_stripped = _strip_webp_metadata(raw_bytes)
    else:
        clean_bytes = _validate_pdf(raw_bytes)

    if len(clean_bytes) > MAX_ATTACHMENT_BYTES:
        raise AppError(
            413,
            "attachment_too_large",
            "첨부파일 한 개의 크기는 5MB를 넘을 수 없습니다.",
        )
    return SanitizedFile(
        filename=sanitize_filename(raw_filename, ext),
        content_type=mime,
        extension=ext,
        data=clean_bytes,
        size_bytes=len(clean_bytes),
        sha256=sha256(clean_bytes).hexdigest(),
        is_image=mime.startswith("image/"),
        exif_stripped=exif_stripped,
    )


def new_storage_key(extension: str) -> str:
    """추측 불가능한 평면 저장소 키(`{uuid4 hex}{ext}`)를 생성합니다.

    Args:
        extension: 점(`.`)으로 시작하는 허용 확장자입니다.

    Returns:
        저장소 키 문자열입니다.
    """
    return f"{uuid4().hex}{extension}"


class AttachmentStorage(Protocol):
    """검증된 첨부파일 바이트를 저장·조회·삭제하는 저장소 인터페이스입니다."""

    def save(self, key: str, data: bytes) -> None:
        """지정한 키에 파일 바이트를 안전하게 저장합니다.

        Args:
            key: `new_storage_key()`로 발급한 평면 저장소 키입니다.
            data: 저장할 정제된 바이트열입니다.
        """
        ...

    def load(self, key: str) -> bytes:
        """지정한 키의 파일 바이트를 읽어 반환합니다.

        Args:
            key: 저장된 파일의 저장소 키입니다.

        Raises:
            AppError: 파일이 존재하지 않으면 404를 발생합니다.
        """
        ...

    def delete(self, key: str) -> None:
        """지정한 키의 파일을 삭제하며 이미 없는 파일은 조용히 무시합니다.

        Args:
            key: 삭제할 저장소 키입니다.
        """
        ...


class MemoryAttachmentStorage:
    """단위 테스트용 프로세스 메모리 첨부파일 저장소입니다."""

    def __init__(self) -> None:
        """빈 바이트 맵과 잠금을 초기화합니다."""
        self._blobs: dict[str, bytes] = {}
        self._lock = Lock()

    def save(self, key: str, data: bytes) -> None:
        """키 형식을 검사한 뒤 메모리에 바이트 사본을 저장합니다.

        Args:
            key: 평면 저장소 키입니다.
            data: 저장할 바이트열입니다.
        """
        if not _STORAGE_KEY_RE.fullmatch(key):
            raise AppError(400, "invalid_storage_key", "잘못된 첨부 저장 키입니다.")
        with self._lock:
            self._blobs[key] = bytes(data)

    def load(self, key: str) -> bytes:
        """메모리에서 첨부 바이트를 반환합니다.

        Args:
            key: 조회할 저장소 키입니다.

        Returns:
            저장된 바이트열입니다.

        Raises:
            AppError: 키가 없으면 404를 발생합니다.
        """
        with self._lock:
            blob = self._blobs.get(key)
        if blob is None:
            raise AppError(404, "not_found", "첨부파일을 찾을 수 없습니다.")
        return blob

    def delete(self, key: str) -> None:
        """메모리에서 첨부 바이트를 제거합니다.

        Args:
            key: 삭제할 저장소 키입니다.
        """
        with self._lock:
            self._blobs.pop(key, None)


class DiskAttachmentStorage:
    """로컬 `.web-data/uploads/`에 경로 탈출을 차단하며 첨부파일을 저장합니다.

    Args:
        base_dir: 첨부파일을 보관할 루트 디렉터리입니다(Git 제외 경로 권장).
    """

    def __init__(self, base_dir: Path) -> None:
        """저장 디렉터리를 생성하고 절대 경로를 고정합니다.

        Args:
            base_dir: 첨부파일 보관 디렉터리 경로입니다.
        """
        self._base_dir = base_dir.resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        """평면 키 형식과 디렉터리 경계를 검증해 안전한 파일 경로를 반환합니다.

        Args:
            key: 저장소 키 문자열입니다.

        Returns:
            `base_dir` 내부로 검증된 `Path` 객체입니다.

        Raises:
            AppError: 키 형식이 잘못되었거나 경로 탈출 시도면 400을 발생합니다.
        """
        if not _STORAGE_KEY_RE.fullmatch(key):
            raise AppError(400, "invalid_storage_key", "잘못된 첨부 저장 키입니다.")
        candidate = (self._base_dir / key).resolve()
        if not candidate.is_relative_to(self._base_dir):
            raise AppError(400, "invalid_storage_key", "허용되지 않은 파일 경로입니다.")
        return candidate

    def save(self, key: str, data: bytes) -> None:
        """임시 파일 기록 후 원자적 교체(`os.replace`)로 디스크에 저장합니다.

        Args:
            key: 평면 저장소 키입니다.
            data: 저장할 바이트열입니다.
        """
        target = self._safe_path(key)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.{uuid4().hex[:8]}.tmp")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

    def load(self, key: str) -> bytes:
        """디스크에서 첨부파일 바이트를 읽어 반환합니다.

        Args:
            key: 저장소 키입니다.

        Returns:
            파일 바이트열입니다.

        Raises:
            AppError: 파일이 없으면 404를 발생합니다.
        """
        target = self._safe_path(key)
        if not target.is_file():
            raise AppError(404, "not_found", "첨부파일을 찾을 수 없습니다.")
        return target.read_bytes()

    def delete(self, key: str) -> None:
        """디스크에서 첨부파일을 삭제하며 이미 없으면 무시합니다.

        Args:
            key: 삭제할 저장소 키입니다.
        """
        if not _STORAGE_KEY_RE.fullmatch(key):
            return
        target = self._safe_path(key)
        target.unlink(missing_ok=True)
