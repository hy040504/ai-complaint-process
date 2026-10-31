/** npm 명령에서도 루트 src의 Flask 서버를 실행하는 편의 실행기입니다. */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const nativePython = resolve(
  root,
  ".venv-web",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const executable =
  process.env.COMPLAINT_PYTHON ||
  (existsSync(nativePython) ? nativePython : "python");
const server = spawn(executable, ["-m", "src"], {
  cwd: root,
  stdio: "inherit",
  windowsHide: true,
});
server.on("error", () => {
  console.error(
    "Flask 실행 환경을 확인하세요. src/README.md의 설치 절차를 따르세요.",
  );
  process.exitCode = 1;
});
server.on("exit", (code) => {
  process.exitCode = code ?? 1;
});
process.on("SIGINT", () => server.kill("SIGINT"));
process.on("SIGTERM", () => server.kill("SIGTERM"));
