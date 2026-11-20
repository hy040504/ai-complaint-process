/** 화면과 같은 원본에서 재사용 가능한 서비스별 SVG 파일을 내보냅니다. */
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { citizenServices } from "../src/citizen.js";
import { serviceIcon } from "../src/service-icons.js";

const destination = new URL("../assets/service-icons/", import.meta.url);
await mkdir(destination, { recursive: true });
for (const [name, label] of citizenServices) {
  const svg = serviceIcon(name)
    .replace('aria-hidden="true"', `role="img" aria-label="${label}"`)
    .replace('width="40" height="40"', 'width="64" height="64"');
  await writeFile(new URL(name + ".svg", destination), svg + "\n", "utf8");
}
console.log(
  `서비스 SVG ${citizenServices.length}개 저장: ${fileURLToPath(destination)}`,
);
