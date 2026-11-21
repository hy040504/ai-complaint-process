/** 민원 첨부파일 클라이언트 검증·작성 폼·상세 갤러리 렌더러를 검증합니다. */
import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_ATTACHMENT_BYTES,
  attachmentUrl,
  formatFileSize,
  renderDetailAttachmentsPanel,
  renderWriteAttachmentField,
  validateClientAttachmentFiles,
} from "../src/attachments.js";

test("formatFileSize와 attachmentUrl은 용량 표기와 안전 경로 인코딩을 처리한다", () => {
  assert.equal(formatFileSize(512), "512 B");
  assert.equal(formatFileSize(2048), "2.0 KB");
  assert.equal(formatFileSize(2 * 1024 * 1024), "2.00 MB");
  assert.equal(
    attachmentUrl("DEMO-2026-1", "ATT-1"),
    "/api/v1/complaints/DEMO-2026-1/attachments/ATT-1",
  );
  assert.equal(
    attachmentUrl("DEMO-2026-1", "ATT-1", { download: true }),
    "/api/v1/complaints/DEMO-2026-1/attachments/ATT-1?download=1",
  );
});

test("validateClientAttachmentFiles는 허용 형식·5MB 용량·최대 5개 한도를 사전 검사한다", () => {
  const okJpg = { name: "현장.jpg", type: "image/jpeg", size: 1024 };
  const okPdf = { name: "증빙.pdf", type: "application/pdf", size: 4096 };
  const badExe = { name: "악성.exe", type: "application/octet-stream", size: 100 };
  const tooBig = { name: "초대형.png", type: "image/png", size: MAX_ATTACHMENT_BYTES + 1 };

  const res = validateClientAttachmentFiles([okJpg, badExe, tooBig, okPdf], 4);
  assert.equal(res.accepted.length, 1);
  assert.equal(res.accepted[0].name, "현장.jpg");
  assert.ok(res.errors.some((e) => e.includes("최대 5개")));
});

test("renderWriteAttachmentField와 renderDetailAttachmentsPanel은 EXIF 배지·삭제 권한 경계를 반영한다", () => {
  const writeHtml = renderWriteAttachmentField({
    pendingFiles: [{ name: "road.jpg", size: 2048, type: "image/jpeg" }],
    existingAttachments: [
      { id: "ATT-1", filename: "기존.pdf", sizeBytes: 4096, isImage: false, exifStripped: false },
    ],
    complaintId: "DEMO-2026-1",
  });
  assert.match(writeHtml, /2\/5/);
  assert.match(writeHtml, /EXIF 위치 자동 제거/);
  assert.match(writeHtml, /road\.jpg/);
  assert.match(writeHtml, /기존\.pdf/);

  const complaint = {
    id: "DEMO-2026-1",
    status: "submitted",
    published: null,
    attachments: [
      {
        id: "ATT-IMG",
        filename: "가로등.jpg",
        sizeBytes: 3000,
        isImage: true,
        exifStripped: true,
      },
      {
        id: "ATT-PDF",
        filename: "문서.pdf",
        sizeBytes: 5000,
        isImage: false,
        exifStripped: false,
      },
    ],
  };

  // 작성자 본인(미게시): 추가 + 삭제 버튼 모두 노출
  const ownerHtml = renderDetailAttachmentsPanel(complaint, {
    isOwner: true,
    isStaff: false,
  });
  assert.match(ownerHtml, /EXIF 제거/);
  assert.match(ownerHtml, /data-action="preview-attachment"/);
  assert.match(ownerHtml, /data-action="delete-attachment"/);
  assert.match(ownerHtml, /파일 추가/);

  // 담당자 화면: 미리보기·내려받기는 허용하되 추가·삭제 버튼은 미노출
  const staffHtml = renderDetailAttachmentsPanel(complaint, {
    isOwner: false,
    isStaff: true,
  });
  assert.match(staffHtml, /내려받기/);
  assert.doesNotMatch(staffHtml, /data-action="delete-attachment"/);
  assert.doesNotMatch(staffHtml, /파일 추가/);
});
