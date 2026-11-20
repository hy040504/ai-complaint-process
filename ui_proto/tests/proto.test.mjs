/** 구상 메모 기능의 비교 로직과 브라우저 보관 상태를 검증합니다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { diffTokens } from '../src/proto-diff.js';

test('같은 문장이면 바뀐 구간이 없다', () => {
  const diff = diffTokens('불편을 드려 죄송합니다.', '불편을 드려 죄송합니다.');
  assert.ok(diff.left.every(([type]) => type === 'eq'));
  assert.ok(diff.right.every(([type]) => type === 'eq'));
});

test('편집으로 빠진 단어는 원문 쪽, 새로 들어간 단어는 편집본 쪽에 표시된다', () => {
  const diff = diffTokens('도로 보수를 검토하겠습니다.', '도로 보수 일정을 확인하겠습니다.');
  const removed = diff.left.filter(([type]) => type === 'del').map(([, text]) => text.trim()).filter(Boolean);
  const added = diff.right.filter(([type]) => type === 'ins').map(([, text]) => text.trim()).filter(Boolean);
  // 공백 단위 토큰이라 '보수를'과 '보수'는 다른 단어로 봅니다.
  assert.deepEqual(removed, ['보수를', '검토하겠습니다.']);
  assert.deepEqual(added, ['보수', '일정을', '확인하겠습니다.']);
});

test('원문과 편집본을 합치면 각각 원래 문장이 복원된다', () => {
  const before = '현장 확인 후 보수 일정을 안내드리겠습니다.';
  const after = '현장 확인 후 보수 계획을 안내드리겠습니다. 감사합니다.';
  const diff = diffTokens(before, after);
  assert.equal(diff.left.map(([, t]) => t).join(''), before);
  assert.equal(diff.right.map(([, t]) => t).join(''), after);
});

test('너무 긴 입력은 비교를 건너뛰고 null을 돌려준다', () => {
  const long = Array.from({ length: 3000 }, (_, i) => `단어${i}`).join(' ');
  assert.equal(diffTokens(long, long + ' 추가'), null);
});
