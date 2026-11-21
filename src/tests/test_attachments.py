"""민원 파일 첨부 업로드·EXIF 제거·권한 격리·연쇄 삭제 테스트입니다."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any
from uuid import uuid4
import zlib

import psycopg
from psycopg import sql
import pytest

from src.app import create_app
from src.complaints.attachments import (
    MAX_ATTACHMENT_BYTES,
    DiskAttachmentStorage,
    MemoryAttachmentStorage,
    validate_and_sanitize_upload,
)
from src.complaints.config import Settings
from src.complaints.errors import AppError
from src.complaints.repository import PostgresRepository


def _make_jpeg_with_exif(
    secret_exif: bytes = b"Exif\x00\x00GPS_SECRET_36.6424",
) -> bytes:
    """APP1 EXIF 세그먼트와 최소 이미지 본문(SOS+EOI)을 포함한 합성 JPEG 바이트를 만듭니다.

    Args:
        secret_exif: 제거 여부를 확인할 APP1 EXIF 페이로드입니다.

    Returns:
        유효 마커 구조를 가진 테스트용 JPEG 바이트입니다.
    """
    app0_body = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    app0 = b"\xff\xe0" + (len(app0_body) + 2).to_bytes(2, "big") + app0_body
    app1 = b"\xff\xe1" + (len(secret_exif) + 2).to_bytes(2, "big") + secret_exif
    com_body = b"CAMERA_SERIAL_999"
    com = b"\xff\xfe" + (len(com_body) + 2).to_bytes(2, "big") + com_body
    sos = b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x00\xff\xd9"
    return b"\xff\xd8" + app0 + app1 + com + sos


def _png_chunk(ctype: bytes, payload: bytes) -> bytes:
    """CRC를 계산한 단일 PNG 청크 바이트를 조립합니다.

    Args:
        ctype: 4바이트 청크 이름입니다.
        payload: 청크 데이터 바이트입니다.

    Returns:
        길이·유형·본문·CRC가 결합된 청크 바이트입니다.
    """
    crc = zlib.crc32(ctype + payload) & 0xFFFFFFFF
    return len(payload).to_bytes(4, "big") + ctype + payload + crc.to_bytes(4, "big")


def _make_png_with_metadata(
    secret_text: bytes = b"Comment\x00SECRET_META_TEXT",
) -> bytes:
    """`tEXt`와 `eXIf` 메타데이터 청크가 포함된 최소 1x1 PNG 바이트를 만듭니다.

    Args:
        secret_text: `tEXt` 청크에 심을 테스트 문자열입니다.

    Returns:
        유효한 1x1 PNG 바이트입니다.
    """
    ihdr = _png_chunk(b"IHDR", b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00")
    exif = _png_chunk(b"eXIf", b"MM\x00\x2aPNG_GPS_SECRET")
    text = _png_chunk(b"tEXt", secret_text)
    idat = _png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
    iend = _png_chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + exif + text + idat + iend


def _make_webp_with_exif(secret_exif: bytes = b"WEBP_GPS_SECRET_001") -> bytes:
    """`VP8X` EXIF 플래그와 `EXIF` 청크를 포함한 합성 WebP 바이트를 만듭니다.

    Args:
        secret_exif: 제거 여부를 확인할 EXIF 바이트입니다.

    Returns:
        RIFF/WEBP 구조의 테스트 바이트입니다.
    """
    # VP8X: 10바이트 페이로드(첫 바이트 0x08=EXIF 플래그, 0x04=XMP 플래그)
    vp8x_payload = bytes([0x0C]) + b"\x00" * 9
    vp8x = b"VP8X" + len(vp8x_payload).to_bytes(4, "little") + vp8x_payload
    exif_pad = secret_exif + (b"\x00" if len(secret_exif) % 2 else b"")
    exif = b"EXIF" + len(secret_exif).to_bytes(4, "little") + exif_pad
    vp8_payload = b"\x00\x00\x00\x00"
    vp8 = b"VP8 " + len(vp8_payload).to_bytes(4, "little") + vp8_payload
    body = vp8x + exif + vp8
    return b"RIFF" + (len(body) + 4).to_bytes(4, "little") + b"WEBP" + body


def _make_minimal_pdf() -> bytes:
    """최소 유효 PDF 헤더·종료 마커를 가진 테스트 바이트를 만듭니다."""
    return b"%PDF-1.4\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF\n"


def test_attachment_sanitizer_strips_exif_and_blocks_spoofed_files(
    tmp_path: Path,
) -> None:
    """JPEG·PNG·WebP의 EXIF/메타데이터를 제거하고 위조 확장자·크기 초과·경로 탈출을 차단합니다."""
    # 1. JPEG EXIF/COM 제거 + 경로 탈출 파일명 정제
    jpg = validate_and_sanitize_upload(_make_jpeg_with_exif(), "../../현장/사진<1>.exe")
    assert jpg.content_type == "image/jpeg"
    assert jpg.filename == "사진_1.jpg"
    assert jpg.is_image is True
    assert jpg.exif_stripped is True
    assert b"GPS_SECRET" not in jpg.data
    assert b"CAMERA_SERIAL" not in jpg.data
    assert jpg.data.startswith(b"\xff\xd8")

    # 2. PNG eXIf/tEXt 제거
    png = validate_and_sanitize_upload(_make_png_with_metadata(), "pothole.png")
    assert png.content_type == "image/png"
    assert png.exif_stripped is True
    assert b"SECRET_META_TEXT" not in png.data
    assert b"PNG_GPS_SECRET" not in png.data
    assert png.data.startswith(b"\x89PNG\r\n\x1a\n")

    # 3. WebP EXIF 제거 및 VP8X 플래그 클리어
    webp = validate_and_sanitize_upload(_make_webp_with_exif(), "street.webp")
    assert webp.content_type == "image/webp"
    assert webp.exif_stripped is True
    assert b"WEBP_GPS_SECRET" not in webp.data
    # VP8X 플래그 바이트(오프셋 12+8=20)의 EXIF(0x08)·XMP(0x04) 비트가 0이어야 합니다.
    assert (webp.data[20] & 0x0C) == 0

    # 4. PDF 허용
    pdf = validate_and_sanitize_upload(_make_minimal_pdf(), "증빙자료.pdf")
    assert pdf.content_type == "application/pdf"
    assert pdf.is_image is False

    # 5. 확장자 위조(HTML/SVG를 .jpg로 위장) 차단
    with pytest.raises(AppError) as err_spoof:
        validate_and_sanitize_upload(
            b"<html><script>alert(1)</script></html>", "fake.jpg"
        )
    assert err_spoof.value.status == 422

    # 6. 빈 파일 및 5 MiB 초과 차단
    with pytest.raises(AppError) as err_empty:
        validate_and_sanitize_upload(b"", "empty.jpg")
    assert err_empty.value.status == 422

    with pytest.raises(AppError) as err_big:
        validate_and_sanitize_upload(
            b"\xff\xd8\xff" + b"0" * MAX_ATTACHMENT_BYTES, "huge.jpg"
        )
    assert err_big.value.status == 413

    # 7. DiskAttachmentStorage 경로 탈출 차단 및 저장·조회·삭제
    disk = DiskAttachmentStorage(tmp_path / "uploads")
    with pytest.raises(AppError):
        disk.save("../escape.jpg", jpg.data)
    key = "a" * 32 + ".jpg"
    disk.save(key, jpg.data)
    assert disk.load(key) == jpg.data
    disk.delete(key)
    with pytest.raises(AppError) as err_gone:
        disk.load(key)
    assert err_gone.value.status == 404


def _run_attachment_api_suite(app: Any) -> None:
    """Memory/PostgreSQL 공통으로 첨부 업로드·열람 격리·개수 제한·삭제·연쇄 정리를 검증합니다."""
    owner = app.test_client()
    other = app.test_client()
    staff = app.test_client()
    storage: MemoryAttachmentStorage = app.extensions[
        "complaint_service"
    ].attachment_storage

    citizen_pw = os.environ.get(
        "COMPLAINT_CITIZEN_INIT_PASSWORD", "cheongju-citizen-2026!"
    )
    staff_pw = os.environ.get("COMPLAINT_STAFF_INIT_PASSWORD", "cheongju-staff-2026!")

    assert (
        owner.post(
            "/api/v1/auth/login", json={"loginId": "citizen_01", "password": citizen_pw}
        ).status_code
        == 200
    )
    assert (
        other.post(
            "/api/v1/auth/register",
            json={
                "loginId": f"att_other_{uuid4().hex[:6]}",
                "password": "other-password-2026!",
                "displayName": "타시민",
            },
        ).status_code
        == 201
    )
    assert (
        staff.post(
            "/api/v1/auth/login", json={"loginId": "staff_admin", "password": staff_pw}
        ).status_code
        == 200
    )

    # 일반 JSON 경로는 여전히 64 KiB 한도를 초과하면 413으로 거부되어야 합니다.
    oversize_json = owner.post(
        "/api/v1/complaints",
        data=b'{"title":"a","body":"' + b"x" * (65 * 1024) + b'"}',
        content_type="application/json",
    )
    assert oversize_json.status_code == 413

    # 비공개 민원 생성
    created = owner.post(
        "/api/v1/complaints",
        json={
            "title": "사창동 도로 파손 현장 사진 첨부",
            "body": "사창동 사거리 인근 포트홀 현장 사진과 증빙 문서를 함께 첨부합니다.",
            "district": "서원구",
            "category": "도로·교통",
            "visibility": "private",
        },
    )
    assert created.status_code == 201
    cid = created.get_json()["id"]

    # 1. 이미지(EXIF 포함) + PDF 첨부 업로드
    up_img = owner.post(
        f"/api/v1/complaints/{cid}/attachments",
        data={"file": (io.BytesIO(_make_jpeg_with_exif()), "현장사진.jpg")},
        content_type="multipart/form-data",
    )
    assert up_img.status_code == 201
    img_meta = up_img.get_json()
    assert img_meta["isImage"] is True
    assert img_meta["exifStripped"] is True
    assert "storageKey" not in img_meta
    img_id = img_meta["id"]

    up_pdf = owner.post(
        f"/api/v1/complaints/{cid}/attachments",
        data={"file": (io.BytesIO(_make_minimal_pdf()), "증빙서류.pdf")},
        content_type="multipart/form-data",
    )
    assert up_pdf.status_code == 201
    pdf_id = up_pdf.get_json()["id"]

    # 2. 열람 권한 및 보안 헤더 검증 (작성자 OK, 담당자 OK, 타 시민 404 차단!)
    dl_owner = owner.get(f"/api/v1/complaints/{cid}/attachments/{img_id}")
    assert dl_owner.status_code == 200
    assert dl_owner.mimetype == "image/jpeg"
    assert dl_owner.headers["Content-Disposition"].startswith("inline;")
    assert "sandbox" in dl_owner.headers["Content-Security-Policy"]
    assert dl_owner.headers["X-Content-Type-Options"] == "nosniff"
    assert b"GPS_SECRET" not in dl_owner.get_data()

    dl_pdf_staff = staff.get(f"/api/v1/complaints/{cid}/attachments/{pdf_id}")
    assert dl_pdf_staff.status_code == 200
    assert dl_pdf_staff.headers["Content-Disposition"].startswith("attachment;")

    # 비공개 민원 첨부파일 타 시민 접근 차단(404) + 업로드/삭제 차단
    assert (
        other.get(f"/api/v1/complaints/{cid}/attachments/{img_id}").status_code == 404
    )
    assert (
        other.delete(f"/api/v1/complaints/{cid}/attachments/{img_id}").status_code
        == 404
    )
    assert (
        staff.post(
            f"/api/v1/complaints/{cid}/attachments",
            data={"file": (io.BytesIO(_make_minimal_pdf()), "staff.pdf")},
            content_type="multipart/form-data",
        ).status_code
        == 403
    )
    assert (
        staff.delete(f"/api/v1/complaints/{cid}/attachments/{img_id}").status_code
        == 403
    )

    # 3. 개수 한도(최대 5개) 검증: 현재 2개 -> 3개 더 올려 5개 채운 뒤 6번째 409
    for idx in range(3):
        r = owner.post(
            f"/api/v1/complaints/{cid}/attachments",
            data={"file": (io.BytesIO(_make_png_with_metadata()), f"extra_{idx}.png")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 201
    sixth = owner.post(
        f"/api/v1/complaints/{cid}/attachments",
        data={"file": (io.BytesIO(_make_minimal_pdf()), "overflow.pdf")},
        content_type="multipart/form-data",
    )
    assert sixth.status_code == 409
    assert sixth.get_json()["code"] == "attachment_limit_exceeded"

    # 4. 답변 게시 전 첨부 삭제 성공 (5 -> 4)
    assert (
        owner.delete(f"/api/v1/complaints/{cid}/attachments/{pdf_id}").status_code
        == 204
    )
    assert (
        owner.get(f"/api/v1/complaints/{cid}/attachments/{pdf_id}").status_code == 404
    )

    # 5. 답변 게시 후에는 증빙 첨부 삭제 불가(409 already_published)
    latest_staff = staff.get(f"/api/v1/complaints/{cid}").get_json()
    pub = staff.post(
        f"/api/v1/complaints/{cid}/publish",
        json={
            "version": latest_staff["version"],
            "text": "현장 사진을 확인하여 보수 조치를 완료했습니다.",
            "reason": "현장 확인 완료",
        },
    )
    assert pub.status_code == 200
    blocked_del = owner.delete(f"/api/v1/complaints/{cid}/attachments/{img_id}")
    assert blocked_del.status_code == 409
    assert blocked_del.get_json()["code"] == "already_published"

    # 6. 민원 영구 삭제 시 첨부 바이트 스토리지까지 연쇄 정리 확인
    latest_owner = owner.get(f"/api/v1/complaints/{cid}").get_json()
    assert len(latest_owner["attachments"]) == 4
    del_c = owner.post(
        f"/api/v1/complaints/{cid}/delete",
        json={"version": latest_owner["version"]},
    )
    assert del_c.status_code == 204
    if isinstance(storage, MemoryAttachmentStorage):
        assert len(storage._blobs) == 0


def test_attachments_api_memory() -> None:
    """메모리 저장소에서 첨부 업로드·격리·한도·삭제·연쇄 정리를 검증합니다."""
    app = create_app(
        Settings(secret_key="test-att-mem", backend="memory", testing=True),
        auto_start_ai=False,
    )
    _run_attachment_api_suite(app)


@pytest.mark.skipif(
    os.environ.get("RUN_PG_TESTS") != "1",
    reason="RUN_PG_TESTS=1 환경에서만 격리 PostgreSQL 스키마를 검증합니다.",
)
def test_attachments_api_postgres() -> None:
    """PostgreSQL 격리 스키마에서 `attachments` 테이블 저장과 ON DELETE CASCADE를 검증합니다."""
    schema = f"complaint_app_att_{uuid4().hex[:8]}"
    repo = PostgresRepository(schema=schema)
    try:
        app = create_app(
            Settings(
                secret_key="test-att-pg",
                backend="postgresql",
                schema=schema,
                testing=True,
            ),
            repository=repo,
            auto_start_ai=False,
        )
        _run_attachment_api_suite(app)
        with repo.connection() as conn:
            row = conn.execute(
                sql.SQL("SELECT count(*) FROM {}.attachments").format(
                    sql.Identifier(schema)
                )
            ).fetchone()
            assert row is not None and row[0] == 0
    finally:
        with psycopg.connect(connect_timeout=10) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
            conn.commit()
