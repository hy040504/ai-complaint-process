/**
 * 검사기 테스트 기록 저장 한도와 읽기를 확인합니다.
 */
import {
  MAX_RUNS,
  RUN_STORAGE_KEY,
  addRun,
  loadRuns,
  makeRun,
  saveRuns,
} from "../lab_web/static/app.js";

const storage = {
  data: {},
  getItem(key) {
    return Object.hasOwn(this.data, key) ? this.data[key] : null;
  },
  setItem(key, value) {
    this.data[key] = String(value);
  },
};

let runs = [];
for (let index = 0; index < 25; index += 1) {
  runs = addRun(runs, { id: String(index), title: `문항 ${index}` });
}
if (runs.length !== MAX_RUNS) {
  throw new Error(`한도 실패: ${runs.length}`);
}
if (runs[0].id !== "24" || runs[runs.length - 1].id !== "5") {
  throw new Error("새 기록이 앞에 와야 합니다.");
}

const run = makeRun(
  {
    title: "대형폐기물 배출",
    category: "환경·청소",
    district: null,
    body: "배출 방법이 궁금합니다.",
  },
  { assist: { outcome: "faq_answer", reasonCode: "ok" } },
);
if (run.outcome !== "faq_answer" || run.title !== "대형폐기물 배출") {
  throw new Error("기록 항목 칸이 비었습니다.");
}

saveRuns([run], storage);
const loaded = loadRuns(storage);
if (loaded.length !== 1 || loaded[0].reasonCode !== "ok") {
  throw new Error("저장 읽기가 실패했습니다.");
}
if (!storage.data[RUN_STORAGE_KEY]) {
  throw new Error("저장 키가 없습니다.");
}

console.log("ok");
