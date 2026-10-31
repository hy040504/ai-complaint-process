/** API 오류와 역할 전환 시 민감한 캐시 제거를 검증합니다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { api, setRole, refresh, read } from '../src/store.js';

test('API 응답을 캐시하고 역할을 변경하면 기존 초안을 먼저 제거한다', async () => {
  globalThis.fetch = async url => ({ ok: true, status: 200, json: async () => url.endsWith('/workspace') ? { revision: 1, complaints: [{ id: 'staff-only', draft: '비공개' }] } : { role: 'staff' } });
  await setRole('staff'); await refresh(); assert.equal(read().complaints[0].draft, '비공개');
  await setRole('citizen'); assert.equal(read().complaints.length, 0);
});
test('409 응답을 성공으로 취급하지 않고 서버 코드와 안내를 보존한다', async () => {
  globalThis.fetch = async () => ({ ok: false, status: 409, json: async () => ({ code: 'version_conflict', message: '최신 버전을 확인해 주세요.' }) });
  await assert.rejects(api('/complaints/demo', { method: 'PUT', body: { version: 1 } }), error => error.status === 409 && error.code === 'version_conflict');
});
test('네트워크 실패를 로컬 저장 성공으로 대체하지 않는다', async () => {
  globalThis.fetch = async () => { throw new Error('연결 끊김'); };
  await assert.rejects(api('/complaints'), /Flask 서버/);
});
