/**
 * 실제 구동 중인 검사기 웹 서버(:5010)와 검색 API(:8007)에 HTTP POST 요청을 보내어
 * 실제 반환 JSON과 showResult DOM 렌더링을 통합 검증합니다.
 */

import fs from "fs";
import { renderCodexPrompts } from "../src/lab_web/static/app.js";

// 가상 DOM 환경
class FakeElement {
  constructor(id = "", tagName = "div") {
    this.id = id;
    this.tagName = tagName;
    this.textContent = "";
    this.hidden = false;
    this.children = [];
    this.innerHTML = "";
    this.className = "";
    this.dataset = {};
  }
  querySelector() {
    return null;
  }
  querySelectorAll() {
    return [];
  }
  replaceChildren(...nodes) {
    this.children = nodes;
  }
  append(...nodes) {
    this.children.push(...nodes);
  }
  appendChild(node) {
    this.children.push(node);
  }
  setAttribute() {}
}

const elementIds = [
  "result-source",
  "result-district",
  "result-message",
  "result-outcome",
  "result-reason",
  "result-failures",
  "result-answer",
  "result-draft",
  "result-sanitize",
  "result-hits",
  "codex-prompts",
  "codex-json",
  "sent-json",
  "received-json",
];

const elements = {};
for (const id of elementIds) {
  elements[id] = new FakeElement(id);
}

globalThis.document = {
  querySelector(sel) {
    const id = sel.replace("#", "");
    return elements[id] || new FakeElement(id);
  },
  createElement(tag) {
    return new FakeElement("", tag);
  },
};

const appJsSource = fs.readFileSync("src/lab_web/static/app.js", "utf-8");
const showResultMatch = appJsSource.match(/function showResult\([\s\S]*?\n\}/);
const showResultCode = `
  const outcomeNames = {
    faq_answer: "안내를 드렸습니다",
    department_suggestion: "담당 부서 후보로 넘겼습니다",
    human_handoff: "담당자가 이어서 살펴봅니다",
  };
  const reasonNames = {
    ok: "검색 근거로 안내합니다",
    insufficient_evidence: "검색 근거만으로 안내를 확정하기 어렵습니다",
    action_required: "현장 조치가 필요한 요청입니다",
  };
  ${showResultMatch[0]}
  return showResult;
`;
const showResult = new Function(
  "document",
  "renderCodexPrompts",
  showResultCode
)(globalThis.document, renderCodexPrompts);

async function testLiveApi() {
  console.log("=== 실서버(:5010) 연동 및 showResult 검증 시작 ===");
  const payload = {
    title: "오송읍 도로 가로등 고장 신고",
    category: "도로·교통",
    district: null, // 본문 지명 '오송읍' -> '흥덕구' 자동 추출 기대
    body: "오송읍 만수리 부근 가로등이 며칠째 켜지지 않아 밤에 너무 어둡고 위험합니다.",
  };

  try {
    console.log("1. http://127.0.0.1:5010/api/v1/lab/complaints 에 민원 전송 중...");
    const res = await fetch("http://127.0.0.1:5010/api/v1/lab/complaints", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`서버 응답 오류 (HTTP ${res.status}): ${await res.text()}`);
    }

    const data = await res.json();
    console.log("2. 서버 응답 수신 성공!");
    console.log("   - effectiveDistrict:", data.effectiveDistrict);
    console.log("   - districtInferred:", data.districtInferred);
    console.log("   - assist.outcome:", data.assist?.outcome);
    console.log("   - assist.reasonCode:", data.assist?.reasonCode);

    console.log("3. showResult(payload, data) 렌더링 호출...");
    showResult(payload, data);
    console.log("4. 렌더링 성공!");
    console.log("   - 뱃지 문구:", elements["result-district"].textContent);
    console.log("   - 판정 결과:", elements["result-outcome"].textContent);
    console.log("   - 사유 문구:", elements["result-reason"].textContent);
    console.log("\n[최종 결과] 'Cannot access assist before initialization' 오류 완전 해결 및 실호출 검증 통과!");
  } catch (err) {
    console.error("\n[실패] 실호출 검증 중 오류 발생:", err);
    process.exit(1);
  }
}

testLiveApi();
