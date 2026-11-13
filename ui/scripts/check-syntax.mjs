/** 새로 추가된 모듈도 빠뜨리지 않고 JavaScript 문법을 검사합니다. */
import { readdir } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const project = new URL("../", import.meta.url);
const files = [
  new URL("server.mjs", project),
  new URL("../src/lab_web/static/app.js", project),
];
for (const directory of ["src/", "adapters/", "scripts/", "tests/"]) {
  for (const item of await readdir(new URL(directory, project), {
    withFileTypes: true,
  })) {
    if (item.isFile() && /\.(?:js|mjs)$/.test(item.name))
      files.push(new URL(directory + item.name, project));
  }
}
for (const file of files) {
  const result = spawnSync(process.execPath, ["--check", fileURLToPath(file)], {
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
console.log(`JavaScript 문법 검사 ${files.length}개 통과`);
