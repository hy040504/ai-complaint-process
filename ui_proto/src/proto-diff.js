/**
 * 구상 메모 기능의 순수 비교 로직입니다. DOM에 의존하지 않아 테스트에서 직접 호출할 수 있습니다.
 */

/**
 * 단어 단위 최장 공통부분수열로 원문과 편집본의 차이를 구합니다.
 *
 * @param {string} before 원문입니다.
 * @param {string} after 편집본입니다.
 * @returns {{left:Array<[string,string]>,right:Array<[string,string]>}|null}
 *   각 쪽의 구간 목록입니다. 너무 길면 null을 돌려줍니다.
 */
export function diffTokens(before, after) {
  const x = String(before).match(/\s+|[^\s]+/g) || [];
  const y = String(after).match(/\s+|[^\s]+/g) || [];
  const n = x.length, m = y.length;
  if (n * m > 4_000_000) return null;
  const w = m + 1;
  const dp = new Uint32Array((n + 1) * w);
  for (let i = n - 1; i >= 0; i -= 1)
    for (let j = m - 1; j >= 0; j -= 1)
      dp[i * w + j] =
        x[i] === y[j]
          ? dp[(i + 1) * w + j + 1] + 1
          : Math.max(dp[(i + 1) * w + j], dp[i * w + j + 1]);
  const left = [], right = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (x[i] === y[j]) {
      left.push(["eq", x[i]]);
      right.push(["eq", y[j]]);
      i += 1;
      j += 1;
    } else if (dp[(i + 1) * w + j] >= dp[i * w + j + 1]) {
      left.push(["del", x[i]]);
      i += 1;
    } else {
      right.push(["ins", y[j]]);
      j += 1;
    }
  }
  while (i < n) left.push(["del", x[i++]]);
  while (j < m) right.push(["ins", y[j++]]);
  return { left, right };
}

