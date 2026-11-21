/**
 * 민원 첨부파일 업로드·삭제 클라이언트, 클라이언트 사전 검증,
 * 작성 폼·상세 화면 첨부 갤러리 렌더러입니다.
 *
 * 허용 형식은 JPG·PNG·WebP·PDF(파일당 최대 5MB, 민원당 최대 5개)이며,
 * 최종 형식 판별과 이미지 EXIF 메타데이터 제거는 서버가 강제합니다.
 */

import { escapeHTML as esc } from "./citizen.js";
import { icon } from "./icons.js";
import { siteHeaders } from "./site.js";

/** 민원당 최대 첨부파일 개수입니다. */
export const MAX_ATTACHMENTS = 5;
/** 단일 첨부파일 최대 바이트 크기(5 MiB)입니다. */
export const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;
/** 파일 선택 대화상자용 허용 형식 문자열입니다. */
export const ALLOWED_ATTACHMENT_ACCEPT =
  "image/jpeg,image/png,image/webp,application/pdf,.jpg,.jpeg,.png,.webp,.pdf";

const ALLOWED_MIMES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
]);
const ALLOWED_EXT_RE = /\.(?:jpe?g|png|webp|pdf)$/i;

/**
 * 바이트 수를 사람이 읽기 쉬운 단위(B·KB·MB) 문자열로 변환합니다.
 *
 * @param {number} bytes 파일 바이트 크기입니다.
 * @returns {string} 읽기 쉬운 용량 문자열입니다.
 */
export function formatFileSize(bytes) {
  const value = Math.max(0, Number(bytes) || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * 권한 검증을 거치는 민원 첨부파일 조회·다운로드 상대 URL을 생성합니다.
 *
 * @param {string} complaintId 민원 식별자입니다.
 * @param {string} attachmentId 첨부파일 식별자입니다.
 * @param {object} [options] 다운로드 강제 옵션입니다.
 * @param {boolean} [options.download=false] True이면 `download=1` 쿼리를 붙입니다.
 * @returns {string} 서버 첨부파일 API 상대 주소입니다.
 */
export function attachmentUrl(complaintId, attachmentId, { download = false } = {}) {
  return (
    `/api/v1/complaints/${encodeURIComponent(complaintId)}` +
    `/attachments/${encodeURIComponent(attachmentId)}` +
    (download ? "?download=1" : "")
  );
}

/**
 * 사용자가 선택한 파일 목록의 형식·용량·개수 한도를 서버 전송 전에 미리 검사합니다.
 *
 * @param {Iterable<File>|ArrayLike<File>} fileList 새로 선택한 파일 목록입니다.
 * @param {number} [existingCount=0] 이미 선택되었거나 서버에 저장된 첨부 개수입니다.
 * @returns {{accepted:Array<File>,errors:string[]}} 통과한 파일과 안내 오류 목록입니다.
 */
export function validateClientAttachmentFiles(fileList, existingCount = 0) {
  const accepted = [];
  const errors = [];
  let remaining = Math.max(0, MAX_ATTACHMENTS - Math.max(0, Number(existingCount) || 0));
  for (const file of Array.from(fileList || [])) {
    if (!file) continue;
    const name = String(file.name || "첨부파일");
    if (remaining <= 0) {
      errors.push(`첨부파일은 최대 ${MAX_ATTACHMENTS}개까지 등록할 수 있습니다.`);
      break;
    }
    const typeOk =
      (file.type && ALLOWED_MIMES.has(file.type.toLowerCase())) ||
      ALLOWED_EXT_RE.test(name);
    if (!typeOk) {
      errors.push(`"${name}": JPG·PNG·WebP 이미지 또는 PDF만 첨부할 수 있습니다.`);
      continue;
    }
    if (!file.size || file.size <= 0) {
      errors.push(`"${name}": 비어 있는 파일은 첨부할 수 없습니다.`);
      continue;
    }
    if (file.size > MAX_ATTACHMENT_BYTES) {
      errors.push(`"${name}": 파일 크기는 5MB 이하여야 합니다.`);
      continue;
    }
    accepted.push(file);
    remaining -= 1;
  }
  return { accepted, errors };
}

/**
 * 민원 한 건에 파일 한 개를 `multipart/form-data`로 업로드합니다.
 *
 * @param {string} complaintId 대상 민원 식별자입니다.
 * @param {File|Blob} file 업로드할 파일 객체입니다.
 * @param {object} [options] 테스트 주입용 `fetchFn` 설정입니다.
 * @param {typeof fetch=} options.fetchFn HTTP 요청 함수입니다.
 * @returns {Promise<object>} 서버가 저장한 `AttachmentItem` 메타데이터입니다.
 */
export async function uploadComplaintAttachment(
  complaintId,
  file,
  { fetchFn = fetch } = {},
) {
  const formData = new FormData();
  formData.append("file", file, file.name || "attachment");
  const res = await fetchFn(
    `/api/v1/complaints/${encodeURIComponent(complaintId)}/attachments`,
    {
      method: "POST",
      credentials: "same-origin",
      headers: siteHeaders(),
      body: formData,
    },
  );
  const body = await res.json().catch(() => null);
  if (!res.ok || !body) {
    throw new Error(body?.message || "첨부파일 업로드에 실패했습니다.");
  }
  return body;
}

/**
 * 답변 게시 전 작성자 본인의 첨부파일을 서버에서 삭제합니다.
 *
 * @param {string} complaintId 대상 민원 식별자입니다.
 * @param {string} attachmentId 삭제할 첨부 식별자입니다.
 * @param {object} [options] 테스트 주입용 `fetchFn` 설정입니다.
 * @param {typeof fetch=} options.fetchFn HTTP 요청 함수입니다.
 * @returns {Promise<void>} 삭제 완료 프로미스입니다.
 */
export async function deleteComplaintAttachment(
  complaintId,
  attachmentId,
  { fetchFn = fetch } = {},
) {
  const res = await fetchFn(
    `/api/v1/complaints/${encodeURIComponent(complaintId)}/attachments/${encodeURIComponent(attachmentId)}`,
    {
      method: "DELETE",
      credentials: "same-origin",
      headers: siteHeaders(),
    },
  );
  if (!res.ok && res.status !== 204) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.message || "첨부파일을 삭제하지 못했습니다.");
  }
}

/**
 * 민원 작성·수정 화면(`#/citizen/write`)에 표시할 첨부파일 선택·대기 목록 HTML을 생성합니다.
 *
 * @param {object} [options] 대기·기존 첨부 상태입니다.
 * @param {Array<{name:string,size:number,type:string,previewUrl?:string}>} [options.pendingFiles=[]] 등록 대기 중인 로컬 파일 목록입니다.
 * @param {Array<object>} [options.existingAttachments=[]] 수정 모드에서 서버에 이미 저장된 첨부 목록입니다.
 * @param {string} [options.complaintId=""] 수정 대상 민원 식별자입니다.
 * @returns {string} 작성 폼 첨부 영역 HTML입니다.
 */
export function renderWriteAttachmentField({
  pendingFiles = [],
  existingAttachments = [],
  complaintId = "",
} = {}) {
  const existing = Array.isArray(existingAttachments) ? existingAttachments : [];
  const pending = Array.isArray(pendingFiles) ? pendingFiles : [];
  const totalCount = existing.length + pending.length;
  const full = totalCount >= MAX_ATTACHMENTS;

  const existingHtml = existing
    .map(
      (att) =>
        `<li class="attachment-pending-item saved">${att.isImage && complaintId ? `<img class="attachment-mini-thumb" src="${esc(attachmentUrl(complaintId, att.id))}" alt="${esc(att.filename)}">` : `<span class="attachment-mini-icon">${icon("file", 18)}</span>`}<div class="attachment-item-meta"><b>${esc(att.filename)}</b><small>${esc(formatFileSize(att.sizeBytes))} · 서버 저장됨${att.exifStripped ? " · EXIF 제거" : ""}</small></div><button type="button" class="attachment-remove-btn" data-action="delete-attachment" data-id="${esc(complaintId)}" data-att-id="${esc(att.id)}" data-filename="${esc(att.filename)}" aria-label="${esc(att.filename)} 삭제">삭제</button></li>`,
    )
    .join("");

  const pendingHtml = pending
    .map(
      (item, idx) =>
        `<li class="attachment-pending-item">${item.previewUrl ? `<img class="attachment-mini-thumb" src="${esc(item.previewUrl)}" alt="${esc(item.name)}">` : `<span class="attachment-mini-icon">${icon("file", 18)}</span>`}<div class="attachment-item-meta"><b>${esc(item.name)}</b><small>${esc(formatFileSize(item.size))} · 등록 시 업로드</small></div><button type="button" class="attachment-remove-btn" data-action="remove-pending-file" data-index="${idx}" aria-label="${esc(item.name)} 제거">제거</button></li>`,
    )
    .join("");

  return `<div class="attachment-field"><div class="attachment-field-head"><label for="attachments-input">${icon("paperclip", 15)} 현장 사진 · 증빙 첨부 <small>(선택 · ${totalCount}/${MAX_ATTACHMENTS})</small></label><span class="attachment-policy-chip">EXIF 위치 자동 제거</span></div><label class="attachment-dropzone ${full ? "disabled" : ""}" id="attachment-dropzone" for="attachments-input">${icon("paperclip", 20)}<span><b>${full ? `최대 ${MAX_ATTACHMENTS}개를 모두 선택했습니다` : "클릭하거나 파일을 끌어다 놓아 첨부하세요"}</b><small>JPG · PNG · WebP 이미지 또는 PDF · 파일당 최대 5MB</small></span><input id="attachments-input" type="file" accept="${esc(ALLOWED_ATTACHMENT_ACCEPT)}" multiple ${full ? "disabled" : ""}></label>${existingHtml || pendingHtml ? `<ul class="attachment-pending-list">${existingHtml}${pendingHtml}</ul>` : ""}</div>`;
}

/**
 * 민원 상세 화면(`#/citizen/detail`·`#/staff/detail`)의 첨부파일 갤러리·관리 패널을 렌더링합니다.
 *
 * @param {object} complaint 민원 모델 객체입니다.
 * @param {object} [options] 표시 권한 옵션입니다.
 * @param {boolean} [options.isOwner=false] 현재 사용자가 작성자 본인인지 여부입니다.
 * @param {boolean} [options.isStaff=false] 담당자 화면인지 여부입니다.
 * @param {boolean} [options.uploading=false] 상세 화면에서 추가 업로드 중인지 여부입니다.
 * @returns {string} 첨부파일 패널 HTML입니다(첨부가 없고 추가 권한도 없으면 빈 문자열).
 */
export function renderDetailAttachmentsPanel(
  complaint,
  { isOwner = false, isStaff = false, uploading = false } = {},
) {
  const list = Array.isArray(complaint?.attachments) ? complaint.attachments : [];
  const canAdd = Boolean(
    isOwner &&
      !isStaff &&
      complaint?.status !== "closed" &&
      complaint?.status !== "withdrawn" &&
      list.length < MAX_ATTACHMENTS,
  );
  const canDelete = Boolean(isOwner && !isStaff && !complaint?.published);
  if (!list.length && !canAdd) return "";

  const cards = list
    .map((att) => {
      const previewHref = attachmentUrl(complaint.id, att.id);
      const downloadHref = attachmentUrl(complaint.id, att.id, { download: true });
      const thumb = att.isImage
        ? `<button type="button" class="attachment-thumb-btn" data-action="preview-attachment" data-url="${esc(previewHref)}" data-download="${esc(downloadHref)}" data-filename="${esc(att.filename)}" aria-label="${esc(att.filename)} 크게 보기"><img src="${esc(previewHref)}" alt="${esc(att.filename)}" loading="lazy"></button>`
        : `<a class="attachment-doc-box" href="${esc(downloadHref)}" download>${icon("file", 28)}<span>PDF</span></a>`;
      return `<article class="attachment-card">${thumb}<div class="attachment-card-body"><b title="${esc(att.filename)}">${esc(att.filename)}</b><small>${esc(formatFileSize(att.sizeBytes))}${att.exifStripped ? " · EXIF 제거" : ""}</small><div class="attachment-card-actions"><a class="btn subtle" href="${esc(downloadHref)}" download>${icon("download", 13)} 내려받기</a>${canDelete ? `<button type="button" class="btn danger subtle" data-action="delete-attachment" data-id="${esc(complaint.id)}" data-att-id="${esc(att.id)}" data-filename="${esc(att.filename)}">삭제</button>` : ""}</div></div></article>`;
    })
    .join("");

  const addControl = canAdd
    ? `<label class="btn subtle attachment-add-btn ${uploading ? "disabled" : ""}">${icon("paperclip", 14)} ${uploading ? "업로드 중…" : "파일 추가"}<input id="detail-attachment-input" type="file" data-id="${esc(complaint.id)}" accept="${esc(ALLOWED_ATTACHMENT_ACCEPT)}" multiple ${uploading ? "disabled" : ""}></label>`
    : "";

  return `<section class="panel attachment-panel"><div class="section-title"><h2>${icon("paperclip", 18)} 첨부파일 <small>${list.length}/${MAX_ATTACHMENTS}</small></h2>${addControl}</div>${list.length ? `<div class="attachment-grid">${cards}</div>` : '<p class="muted">아직 첨부된 현장 사진이나 증빙 문서가 없습니다. 필요하면 위 버튼으로 JPG·PNG·WebP·PDF를 추가할 수 있어요.</p>'}</section>`;
}
