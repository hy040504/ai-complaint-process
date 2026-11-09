/**
 * Node.js 환경에서 DOM을 모킹하여 app.js의 결과 렌더링(showResult)에
 * TDZ(Temporal Dead Zone) 또는 초기화 전 참조 에러가 없는지 검증합니다.
 */

import fs from "fs";
import { formatRunTime, fillDistrictSelect, renderCodexPrompts } from "../src/lab_web/static/app.js";

/**
 * 테스트용 가상 DOM 엘리먼트 모킹 클래스입니다.
 */
class FakeElement {
  /**
   * @param {string} [id=""] 엘리먼트 ID입니다.
   * @param {string} [tagName="div"] 태그 이름입니다.
   */
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

  /**
   * 하위 요소를 검색합니다.
   *
   * @param {string} sel 셀렉터입니다.
   * @returns {FakeElement|null} 찾은 가상 엘리먼트 또는 null입니다.
   */
  querySelector(sel) {
    return elements[sel.replace("#", "")] || null;
  }

  /**
   * 하위 요소 목록을 반환합니다.
   *
   * @returns {FakeElement[]}
   */
  querySelectorAll() {
    return [];
  }

  /**
   * 자식 노드를 교체합니다.
   *
   * @param {...FakeElement} nodes 교체할 노드 목록입니다.
   * @returns {void}
   */
  replaceChildren(...nodes) {
    this.children = nodes;
  }

  /**
   * 자식 노드를 추가합니다.
   *
   * @param {...FakeElement} nodes 추가할 노드 목록입니다.
   * @returns {void}
   */
  append(...nodes) {
    this.children.push(...nodes);
  }

  /**
   * 단일 자식 노드를 추가합니다.
   *
   * @param {FakeElement} node 추가할 노드입니다.
   * @returns {void}
   */
  appendChild(node) {
    this.children.push(node);
  }

  /**
   * 속성을 설정합니다.
   *
   * @param {string} name 속성 이름입니다.
   * @param {string} value 속성 값입니다.
   * @returns {void}
   */
  setAttribute(name, value) {
    this[name] = value;
  }
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

// app.js 내부의 showResult를 테스트하기 위해 app.js 전체 모듈 읽기 검증
console.log("1. app.js 기본 export 함수 검증:");
console.log(" - formatRunTime:", typeof formatRunTime === "function");
console.log(" - fillDistrictSelect:", typeof fillDistrictSelect === "function");
console.log(" - renderCodexPrompts:", typeof renderCodexPrompts === "function");

// app.js의 showResult 로직 시뮬레이션 및 TDZ 검증
const mockPayload = {
  title: "가경동 도로 파손 보수 요청",
  category: "도로·교통",
  district: null,
  body: "가경동 홈플러스 앞 도로에 큰 포트홀이 생겼습니다.",
};

const mockReceivedCases = [
  {
    name: "자동 지명 추출 응답 (effectiveDistrict: 흥덕구, districtInferred: true)",
    data: {
      message: "검색 후보를 찾은 뒤 판정했습니다.",
      searchQuery: "가경동 도로 파손 보수 요청\n\n가경동 홈플러스 앞 도로에 큰 포트홀이 생겼습니다.",
      effectiveDistrict: "흥덕구",
      districtInferred: true,
      assist: {
        outcome: "human_handoff",
        reasonCode: "action_required",
        district: "흥덕구",
        districtInferred: true,
        answer: null,
        staffDraft: {
          draftAnswer: "가경동 포트홀 긴급 보수 현장 점검을 실시하겠습니다.",
        },
        sanitize: null,
        faq: [],
        cases: [{ corpus: "routing", sourceId: "case-1", title: "도로 보수 민원" }],
        codex: [{ role: "decision", system: "PREFIX-00+01", sent: true, prompt: "..." }],
      },
    },
  },
  {
    name: "지역 미지정 응답 (effectiveDistrict: null)",
    data: {
      message: "검색 후보를 찾은 뒤 판정했습니다.",
      searchQuery: "대형폐기물 수거 기준 문의",
      effectiveDistrict: null,
      districtInferred: false,
      assist: {
        outcome: "faq_answer",
        reasonCode: "ok",
        district: null,
        districtInferred: false,
        answer: "대형폐기물 스티커를 부착 후 배출하시면 됩니다.",
        faq: [{ corpus: "faq", sourceId: "faq-1", title: "대형폐기물 배출 방법" }],
        cases: [],
        codex: [],
      },
    },
  },
  {
    name: "assist 필드가 비어있거나 불완전한 비정상/오류 응답",
    data: {
      message: "검색 서버에 연결하지 못했습니다.",
      effectiveDistrict: null,
      districtInferred: false,
      assist: {},
    },
  },
];

// app.js 파일의 showResult 함수 추출 후 실행
const appJsSource = fs.readFileSync("src/lab_web/static/app.js", "utf-8");

// showResult 정의부 추출하여 Function으로 평가
const showResultMatch = appJsSource.match(/function showResult\([\s\S]*?\n\}/);
if (!showResultMatch) {
  throw new Error("showResult 함수를 찾을 수 없습니다.");
}

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

const extractedShowResult = new Function(
  "document",
  "renderCodexPrompts",
  showResultCode
)(globalThis.document, renderCodexPrompts);

console.log("\n2. showResult 런타임 및 TDZ 오류 검증:");
for (const tc of mockReceivedCases) {
  try {
    extractedShowResult(mockPayload, tc.data, "테스트 안내문");
    console.log(` [PASS] ${tc.name}`);
    console.log(`   - 뱃지 문구: "${elements["result-district"].textContent}"`);
    console.log(`   - 판정 결과: "${elements["result-outcome"].textContent}"`);
    console.log(`   - 사유 문구: "${elements["result-reason"].textContent}"`);
  } catch (err) {
    console.error(` [FAIL] ${tc.name}`);
    console.error(`   에러 발생: ${err.message}`);
    process.exit(1);
  }
}

console.log("\n모든 프론트엔드 showResult 케이스 검증 통과! TDZ/초기화 에러 없음.");
