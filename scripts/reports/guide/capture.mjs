// 사용 가이드용 주석 캡처 도구: 화면을 열고 기능 영역에 번호 배지와 테두리를 직접 그려 PNG로 저장합니다.
// 사용법: node capture.mjs <크롬 디버깅 포트> <screens.json> <출력 폴더> [dump]
// 로그인 비밀번호는 설정 파일에 쓰지 않고 "$ENV:이름" 형태로 적으면 같은 이름의 환경변수에서 읽습니다.
// 화면 요소 목록만 보고 싶으면 마지막 인자에 dump를 줍니다.
// spec: { "base": "http://127.0.0.1:5001", "shots": [ { name, steps:[...], width, height|"full", theme, notes:[{sel,n,pad}] } ] }
// steps: {go:url} {wait:ms} {eval:js} {click:sel} {type:{sel,value}} {login:{site,id,pw,role}} {logout:true}
// sel: "css:..." 또는 "text:글자" (보이는 요소 중 글자를 포함하는 가장 작은 요소)
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const [port, specPath, outDir, mode] = process.argv.slice(2);
const spec = JSON.parse(readFileSync(specPath, "utf8").replace(/^\uFEFF/, ""));
mkdirSync(outDir, { recursive: true });
const cdp = `http://127.0.0.1:${port}`;
for (let i = 0; i < 50; i++) { try { await fetch(`${cdp}/json/version`); break; } catch { await new Promise((r) => setTimeout(r, 200)); } }
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method: "PUT" })).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const errors = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg.result ?? msg.error); pending.delete(msg.id); }
  else if (msg.method === "Runtime.exceptionThrown") errors.push("EXC " + (msg.params.exceptionDetails?.exception?.description || "").slice(0, 160));
};
const send = (method, params = {}) => new Promise((resolve) => { const i = ++id; pending.set(i, resolve); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expression) => { const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }); if (r?.exceptionDetails) throw new Error("eval: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text)); return r?.result?.value; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await send("Page.enable"); await send("Runtime.enable");
await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });

// 화면 안에서 쓰는 도우미(요소 찾기)
const HELPERS = `(() => {
  window.__find = (sel) => {
    if (sel.startsWith('panel:')) { const el = window.__find(sel.slice(6)); return el ? (el.closest('.panel, section, aside') || el) : null; }
    if (sel.startsWith('css:')) { const el = document.querySelector(sel.slice(4)); return el; }
    const text = sel.startsWith('text:') ? sel.slice(5) : sel;
    const cands = [...document.querySelectorAll('button,a,label,h1,h2,h3,h4,summary,[role=button],input,select,textarea,th,li,span,b,strong,p,div')]
      .filter((e) => { const r = e.getBoundingClientRect(); if (r.width < 4 || r.height < 4) return false; const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') return false;
        const t = (e.textContent || '').replace(/\\s+/g, ' ').trim(); const ph = e.getAttribute('placeholder') || ''; return t.includes(text) || ph.includes(text); });
    cands.sort((a, b) => (a.textContent || '').length - (b.textContent || '').length);
    return cands[0] || null;
  };
  window.__rectOf = (sel) => { if (sel.startsWith('xy:')) { const [x,y,w,h] = sel.slice(3).split(',').map(Number); return { x, y, w, h }; } const el = window.__find(sel); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height }; };
  return true; })()`;

async function setSize(width, height, theme) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 600 });
}
let currentTheme = null;
async function go(url, theme) {
  if (theme !== currentTheme) {
    await send("Page.addScriptToEvaluateOnNewDocument", { source: `try{localStorage.setItem('minwon-ui-theme', ${JSON.stringify(theme || "light")})}catch(e){}` });
    currentTheme = theme;
  }
  await send("Page.navigate", { url });
  await sleep(2600);
  await ev(HELPERS);
}
async function runStep(step, base) {
  if (step.go) { await go(step.go.startsWith("http") ? step.go : base + step.go, "light"); }
  else if (step.wait) await sleep(step.wait);
  else if (step.eval) await ev(step.eval);
  else if (step.click) {
    const ok = await ev(`(() => { const el = window.__find(${JSON.stringify(step.click)}); if (!el) return false; el.click(); return true; })()`);
    if (!ok) console.log("   ! 클릭 대상 없음:", step.click);
    await sleep(step.after ?? 700);
  } else if (step.type) {
    const ok = await ev(`(() => { const el = window.__find(${JSON.stringify(step.type.sel)}); if (!el) return false; el.focus(); const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : (el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype); Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(step.type.value)}); el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); return true; })()`);
    if (!ok) console.log("   ! 입력 대상 없음:", step.type.sel);
  } else if (step.login) {
    const envStr = (v) => String(v).replace(/\$ENV:([A-Za-z0-9_]+)/g, (_, k) => process.env[k] ?? "");
    const site = step.login.site, lid = envStr(step.login.id), pw = envStr(step.login.pw), role = step.login.role;
    if ((await ev("location.origin")) !== new URL(base).origin) await go(base + "/", "light");
    const res = await ev(`fetch('/api/v1/auth/login', {method:'POST', headers:{'Content-Type':'application/json','X-Cheongju-Site':${JSON.stringify(site)}}, body: JSON.stringify({loginId:${JSON.stringify(lid)}, password:${JSON.stringify(pw)}, expectedRole:${JSON.stringify(role)}})}).then(r => r.status)`);
    if (res !== 200) console.log("   ! 로그인 실패", res);
  } else if (step.logout) {
    if ((await ev("location.origin")) !== new URL(base).origin) await go(base + "/", "light");
    await ev(`fetch('/api/v1/auth/logout', {method:'POST', headers:{'X-Cheongju-Site': ${JSON.stringify(step.logout)} }}).then(r => r.status)`);
  } else if (step.guest) {
    await ev(`fetch('/api/v1/auth/guest', {method:'POST', headers:{'X-Cheongju-Site':'citizen'}}).then(r => r.status)`);
  }
}

const OVERLAY = (items) => `(() => {
  document.getElementById('__guide_overlay')?.remove();
  const wrap = document.createElement('div'); wrap.id = '__guide_overlay';
  wrap.style.cssText = 'position:absolute;left:0;top:0;width:0;height:0;z-index:2147483647;pointer-events:none;font-family:"Noto Sans KR","Malgun Gothic",sans-serif';
  const items = ${JSON.stringify(items)};
  const miss = [];
  const W = document.documentElement.scrollWidth;
  for (const it of items) {
    const r = window.__rectOf(it.sel);
    if (!r) { miss.push(it.sel); continue; }
    const pad = it.pad ?? 4;
    const box = document.createElement('div');
    box.style.cssText = 'position:absolute;box-sizing:border-box;border:3px solid #d92d20;border-radius:8px;background:rgba(217,45,32,0.07);' +
      'left:' + (r.x - pad) + 'px;top:' + (r.y - pad) + 'px;width:' + (r.w + pad * 2) + 'px;height:' + (r.h + pad * 2) + 'px';
    wrap.appendChild(box);
    const size = 28;
    let bx = r.x - pad - size / 2, by = r.y - pad - size / 2;
    if (it.badge === 'right') { bx = r.x + r.w + pad - size / 2; }
    if (it.badge === 'inside') { bx = r.x + 6; by = r.y + 6; }
    bx = Math.max(2, Math.min(bx, W - size - 2)); by = Math.max(2, by);
    const b = document.createElement('div');
    b.textContent = String(it.n);
    b.style.cssText = 'position:absolute;width:' + size + 'px;height:' + size + 'px;border-radius:50%;background:#d92d20;color:#fff;font-weight:800;font-size:15px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 3px #fff, 0 2px 6px rgba(0,0,0,.35);left:' + bx + 'px;top:' + by + 'px';
    wrap.appendChild(b);
  }
  // 열린 모달(<dialog>)은 브라우저의 최상위 층에 그려져 body 위의 표시를 덮는다.
  // 모달이 열려 있으면 그 안에 viewport 기준(fixed)으로 넣어 번호가 보이게 한다.
  const modal = document.querySelector('dialog[open]');
  if (modal) { wrap.style.position = 'fixed'; modal.appendChild(wrap); }
  else document.body.appendChild(wrap);
  return JSON.stringify(miss);
})()`;

const DUMP = `(() => {
  const out = [];
  for (const e of document.querySelectorAll('button,a,input,select,textarea,summary,h1,h2,h3,[data-action]')) {
    const r = e.getBoundingClientRect(); if (r.width < 4 || r.height < 4 || r.top > 3000) continue;
    const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const t = (e.textContent || e.getAttribute('placeholder') || '').replace(/\\s+/g, ' ').trim().slice(0, 28);
    out.push([e.tagName.toLowerCase(), (e.getAttribute('data-action') || e.id || e.name || ''), t, Math.round(r.left), Math.round(r.top + scrollY), Math.round(r.width), Math.round(r.height)].join(' | '));
  }
  return out.join('\\n');
})()`;

for (const shot of spec.shots) {
  if (spec.only && !spec.only.includes(shot.name)) continue;
  const width = shot.width || 1280;
  await setSize(width, shot.height && shot.height !== "full" ? shot.height : 900);
  console.log("▶", shot.name);
  for (const step of shot.steps || []) await runStep(step, spec.base);
  await ev(HELPERS);
  if (mode === "dump") { console.log(await ev(DUMP)); continue; }
  if (shot.height === "full") {
    const h = Math.min(await ev("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)"), 2600);
    await setSize(width, h);
    await sleep(500);
  }
  const miss = JSON.parse(await ev(OVERLAY(shot.notes || [])));
  if (miss.length) console.log("   ! 못 찾은 요소:", miss.join(" / "));
  await sleep(250);
  const png = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  writeFileSync(`${outDir}/${shot.name}.png`, Buffer.from(png.data, "base64"));
  console.log("   저장:", shot.name + ".png");
}
if (errors.length) console.log("스크립트 오류:", errors.join(" | "));
ws.close();
