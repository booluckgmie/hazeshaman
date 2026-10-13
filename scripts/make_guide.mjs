// Generates the how-to-use images in docs/howto/ (annotated screenshots + social cards).
//   npm run dev            (in one terminal: serves docs/ + /api/live on :3000)
//   npm i -D playwright && npx playwright install chromium
//   npm run guide          (BASE=http://localhost:3000)
// Env: BASE, PW_ROOT (dir whose node_modules holds playwright), CHROMIUM_PATH, NOW (ISO, default = fixed demo time)
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const require = createRequire(process.env.PW_ROOT ? process.env.PW_ROOT.replace(/\/?$/, '/') : import.meta.url);
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://localhost:3000';
// fixed demo time = 35 min after the newest hour served by /api/live, so the badge, the stamp and the data agree
const NOW = process.env.NOW || await (async () => {
  const end = (await (await fetch(BASE + '/api/live')).json()).end;              // e.g. 2026-10-13T21:00 (Malaysia time)
  const t = new Date(end + ':00+08:00').getTime() + 35 * 60e3;                    // 35 min after the newest hour
  return new Date(t + 8 * 3600e3).toISOString().slice(0, 19) + '+08:00';          // as Malaysia wall-clock text
})();
const root = fileURLToPath(new URL('..', import.meta.url));
const OUT = join(root, 'docs', 'howto');
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const ctx = await browser.newContext({ viewport: { width: 1400, height: 2200 }, colorScheme: 'dark', deviceScaleFactor: 1 });
const page = await ctx.newPage();
await page.clock.setFixedTime(new Date(NOW));
await page.addStyleTag({ content: '' }).catch(() => {});
await page.goto(BASE + '/');
await page.addStyleTag({ content: 'body{background-attachment:scroll!important}' });
await page.waitForSelector('#bandName:not(:empty)');
await page.waitForTimeout(1600);

/* ---------- helpers ---------- */
const injectAnn = (items, pg = page) => pg.evaluate((items) => {
  document.getElementById('__ann')?.remove();
  const layer = document.createElement('div'); layer.id = '__ann';
  layer.style.cssText = `position:absolute;left:0;top:0;width:${document.documentElement.scrollWidth}px;height:${document.documentElement.scrollHeight}px;pointer-events:none;z-index:99999`;
  for (const it of items) {
    const el = typeof it.sel === 'string' ? document.querySelector(it.sel) : null; if (!el) { console.error('missing', it.sel); continue; }
    const r = el.getBoundingClientRect(), x = r.left + scrollX, y = r.top + scrollY;
    const box = document.createElement('div');
    box.style.cssText = `position:absolute;left:${x - 4}px;top:${y - 4}px;width:${r.width + 8}px;height:${r.height + 8}px;border:2.5px solid #ffd27a;border-radius:16px;box-shadow:0 0 0 2px rgba(20,12,8,.55),0 0 18px rgba(255,190,100,.55)`;
    const b = document.createElement('div'); b.textContent = it.n;
    const off = it.pos === 'br' ? [r.width - 6, r.height - 6] : it.pos === 'tr' ? [r.width - 6, -22] : it.pos === 'bl' ? [-22, r.height - 6] : [-22, -22];
    b.style.cssText = `position:absolute;left:${x + off[0]}px;top:${y + off[1]}px;width:30px;height:30px;border-radius:50%;background:#ffa94d;color:#1a1318;font:800 16px/30px system-ui,sans-serif;text-align:center;box-shadow:0 0 0 3px #1a1318,0 4px 14px rgba(0,0,0,.5)`;
    layer.append(box, b);
  }
  document.body.append(layer);
}, items);
const clearAnn = (pg = page) => pg.evaluate(() => document.getElementById('__ann')?.remove());
const bbox = (sels) => page.evaluate((sels) => {
  const rs = sels.map((s) => document.querySelector(s).getBoundingClientRect());
  const x = Math.min(...rs.map((r) => r.left)) + scrollX, y = Math.min(...rs.map((r) => r.top)) + scrollY;
  return { x, y, width: Math.max(...rs.map((r) => r.right)) + scrollX - x, height: Math.max(...rs.map((r) => r.bottom)) + scrollY - y };
}, sels);
const pad = (b, p = 30) => ({ x: Math.max(0, b.x - p), y: Math.max(0, b.y - p), width: Math.min(1400, b.width + 2 * p), height: b.height + 2 * p });

const legendCss = `body{margin:0;background:#17110f;color:#f4ece6;font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.t{display:flex;align-items:center;gap:14px;padding:18px 26px;background:linear-gradient(90deg,#3a2415,#17110f);border-bottom:1px solid #ffffff22}
.t b{font-size:22px;letter-spacing:-.01em}.t i{font-style:normal;color:#ffb066;font-weight:700;letter-spacing:.12em;font-size:12px;text-transform:uppercase}
img{display:block;width:100%}.lg{display:grid;grid-template-columns:1fr 1fr;gap:10px 28px;padding:20px 26px 24px;background:#1f1714;border-top:1px solid #ffffff22}
.lg div{display:flex;gap:12px;align-items:flex-start}.lg span{flex:none;width:26px;height:26px;border-radius:50%;background:#ffa94d;color:#1a1318;font-weight:800;text-align:center;line-height:26px}
.ft{padding:10px 26px;background:#120d0b;color:#a89a90;font-size:12px;display:flex;justify-content:space-between}`;
async function compose(file, step, title, shot, legend, foot) {
  const p = await ctx.newPage();
  await p.setViewportSize({ width: 1400, height: 400 });
  const b64 = shot.toString('base64');
  await p.setContent(`<style>${legendCss}</style><div class="t"><i>${step}</i><b>${title}</b></div><img src="data:image/png;base64,${b64}">
    ${legend.length ? `<div class="lg">${legend.map((l, i) => `<div><span>${i + 1}</span><p style="margin:0">${l}</p></div>`).join('')}</div>` : ''}
    <div class="ft"><span>Hazeshaman · haze early-warning for Malaysian schools</span><span>${foot}</span></div>`);
  await p.waitForTimeout(150);
  await p.screenshot({ path: join(OUT, file), fullPage: true });
  await p.close();
  console.log('wrote', file);
}
const stamp = `Snapshot: DOE API ${NOW.slice(0, 10)} ${NOW.slice(11, 16)} MYT`;

/* ---------- 1. tour ---------- */
await page.evaluate(() => scrollTo(0, 0));
await injectAnn([
  { sel: '#liveBadge', n: 1, pos: 'tl' }, { sel: '#sky', n: 2, pos: 'tl' }, { sel: '#chips', n: 3, pos: 'tl' },
  { sel: '.seg', n: 4, pos: 'tl' }, { sel: '#fbar', n: 5, pos: 'tl' }, { sel: '#overview', n: 6, pos: 'tl' }]);
let shot = await page.screenshot({ clip: { x: 0, y: 0, width: 1400, height: 960 } });
await compose('01-tour.png', 'Step 1 · Orientation', 'The dashboard in one screen', shot, [
  '<b>Live badge</b> – green = the newest hourly DOE report is under 2 h old; amber/red = the feed is lagging or stale.',
  '<b>Haze right now</b> – the sky, skyline and band name show how bad the air is across Malaysia at this hour.',
  '<b>State tiles</b> – highest API per state, coloured by band. Click one to open that state.',
  '<b>Live data / What-if</b> – Live follows the newest report; What-if lets you type your own readings.',
  '<b>State filter</b> – the whole page follows it: “Malaysia” (all states) or one state. On a phone, use the round button at the bottom-right.',
  '<b>National outlook</b> – tomorrow morning: stations at closure risk and the schools, students and teachers behind them.'], stamp);
await clearAnn();
await page.evaluate(() => { document.querySelector('header').style.visibility = 'hidden'; });   // keep later crops clean

/* ---------- 2. state filter (desktop dropdown + phone bottom sheet) ---------- */
const mobCtx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: 'dark' });
const mob = await mobCtx.newPage();
await mob.clock.setFixedTime(new Date(NOW));
await mob.goto(BASE + '/'); await mob.addStyleTag({ content: 'body{background-attachment:scroll!important}' }); await mob.waitForSelector('#bandName:not(:empty)'); await mob.waitForTimeout(1500);
await page.evaluate(() => scrollTo(0, 0));
await page.click('#stateBtn'); await page.waitForTimeout(500);
await injectAnn([{ sel: '#stateBtn', n: 1, pos: 'tl' }, { sel: '#sheet', n: 2, pos: 'tr' }]);
const deskA = await page.screenshot({ clip: pad(await bbox(['#fbar', '#sheet']), 28), fullPage: true });
await clearAnn();
await page.click('#sheetList li[data-k="Johor"]'); await page.waitForTimeout(700);
await injectAnn([{ sel: '#area', n: 3, pos: 'tl' }]);
const deskB = await page.screenshot({ clip: pad(await bbox(['#fbar']), 28), fullPage: true });
await clearAnn();
await page.evaluate(() => selectState('')); await page.waitForTimeout(500);
await mob.evaluate(() => scrollTo(0, 900)); await mob.waitForTimeout(300);
await injectAnn([{ sel: '#fab', n: 4, pos: 'tl' }], mob);
const phoneA = await mob.screenshot(); await clearAnn(mob);
await mob.click('#fab'); await mob.waitForTimeout(800);
await injectAnn([{ sel: '#sheetList li[data-k="Johor"]', n: 5, pos: 'tl' }], mob);
const phoneB = await mob.screenshot(); await clearAnn(mob);
{
  const p = await ctx.newPage(); await p.setViewportSize({ width: 1400, height: 400 });
  const img = (b) => `data:image/png;base64,${b.toString('base64')}`;
  await p.setContent(`<style>${legendCss}.mid{padding:14px 26px;background:#2a1c14;color:#ffd9ad;font-weight:650;border-top:1px solid #ffffff22;border-bottom:1px solid #ffffff22}
   .ph{display:flex;gap:34px;justify-content:center;align-items:flex-start;padding:26px;background:#1f1714}.ph div{width:300px}.ph img{border-radius:22px;border:1px solid #ffffff33;box-shadow:0 12px 40px #0008}.ph p{text-align:center;color:#d8c9bf;margin:10px 0 0}</style>
   <div class="t"><i>Step 2 · Filter by state</i><b>Malaysia or one state – on desktop and on your phone</b></div>
   <img src="${img(deskA)}"><div class="mid">Choose a state: the sky, the outlook, the schools and the station list all follow your choice. The station picker then unlocks:</div><img src="${img(deskB)}">
   <div class="mid">On a phone the same list opens from the round button (bottom-right) as a bottom sheet:</div>
   <div class="ph"><div><img src="${img(phoneA)}"><p>Round button stays in reach while you scroll</p></div><div><img src="${img(phoneB)}"><p>Tap a state; the page filters at once</p></div></div>
   <div class="lg">${[
     '<b>State button</b> – shows what the page is filtered to. Click it to open the list.',
     '<b>State list</b> – “Malaysia” first, then every state. Each row shows its highest live API (coloured by band) and Open / Watch / Close status.',
     '<b>Station picker</b> – after choosing a state, pick one of its stations or leave it on “Highest risk (auto)”.',
     '<b>Round button</b> (phones) – always bottom-right; opens the list.',
     '<b>Bottom sheet</b> – tap a state. The link is shareable: add <code>#Johor</code> to the address.'].map((l, i) => `<div><span>${i + 1}</span><p style="margin:0">${l}</p></div>`).join('')}</div>
   <div class="ft"><span>Hazeshaman · haze early-warning for Malaysian schools</span><span>${stamp}</span></div>`);
  await p.waitForTimeout(250); await p.screenshot({ path: join(OUT, '02-state-filter.png'), fullPage: true }); await p.close(); console.log('wrote 02-state-filter.png');
}
await mob.keyboard.press('Escape');

/* ---------- 3. haze at a glance ---------- */
await injectAnn([
  { sel: '#bandName', n: 1, pos: 'tl' }, { sel: '#skyStats', n: 2, pos: 'tl' }, { sel: '#scale', n: 3, pos: 'tl' }, { sel: '#chips .chip', n: 4, pos: 'tr' }]);
shot = await page.screenshot({ clip: pad(await bbox(['#sky'])), fullPage: true });
await compose('03-haze-at-a-glance.png', 'Step 3 · Read the air', 'Haze right now', shot, [
  '<b>Band</b> – Malaysian API bands: Good 0–50 · Moderate 51–100 · Unhealthy 101–200 · Very unhealthy 201–300 · Hazardous 300+. The colour follows the <i>worst</i> station.',
  '<b>Four numbers</b> – highest API, national mean, stations above 100 / 150, and tomorrow’s closure-risk count.',
  '<b>Band scale</b> – the white marker is the national mean; the coloured marker is the worst station.',
  '<b>State tile</b> – the state’s highest reading. The more haze, the thicker the particles and the blurrier the skyline.'], stamp);
await clearAnn();

/* ---------- 4. national outlook ---------- */
await injectAnn([
  { sel: '#hero .kpi:nth-child(1)', n: 1, pos: 'tl' }, { sel: '#hero .kpi:nth-child(3)', n: 2, pos: 'tl' }, { sel: '#stTable tr.row:nth-child(1) .tag', n: 3, pos: 'tl' }, { sel: '#stTable tr.row:nth-child(1)', n: 4, pos: 'bl' }, { sel: '#stTable tr.row:nth-child(1) td:last-child', n: 5, pos: 'tr' }]);
shot = await page.screenshot({ clip: pad(await bbox(['#overview'])), fullPage: true });
await compose('04-national-outlook.png', 'Step 4 · Tomorrow morning', 'National outlook and schools impacted', shot, [
  '<b>Stations at closure risk</b> – stations whose closure probability is above the cost-optimal trigger.',
  '<b>Schools likely affected</b> – closure chance × the number of schools in each state, added up (students and teachers shown underneath).',
  '<b>Status</b> – Close / PdPR, Watch or Open per state, worst first. A state’s chance is its highest-risk station.',
  '<b>Click a row</b> to filter the page to that state and see its stations.',
  '<b># schools in area</b> – government primary + secondary schools in the state (state totals, MOE via OpenDOSM).'], stamp);
await clearAnn();

/* ---------- 5. station detail (Larkin, Johor) ---------- */
await page.click('#stTable tr.row[data-k="Johor"]');
await page.selectOption('#area', 'Johor|Larkin');
await page.waitForTimeout(500);
await injectAnn([
  { sel: '#verdict', n: 1, pos: 'tl' }, { sel: '#kpis', n: 2, pos: 'tl' }, { sel: '#sch', n: 3, pos: 'tl' }, { sel: '#scen', n: 4, pos: 'tl' }]);
shot = await page.screenshot({ clip: pad(await bbox(['#verdict', '#scen'])), fullPage: true });
await compose('05-station-detail.png', 'Step 5 · One station', 'Recommendation, probabilities, schools and scenarios', shot, [
  '<b>Recommendation</b> – open / open with restrictions / close-PdPR, with the closure ring and why.',
  '<b>Probabilities</b> – 7 AM API above 100 and 150, API above 180 in school hours, and the 3-day streak rule (KPM’s two closure triggers).',
  '<b>Schools impacted (state level)</b> – schools, students and teachers in the state. “If schools close” = everyone affected by a state-wide closure; “Likely affected tomorrow” = closure chance × schools.',
  '<b>Three scenarios</b> – best (improving), base (unstable), worst (closure). The framed one is the most likely.'], stamp);
await clearAnn();

/* ---------- 6. announcement time: default view, then change the preference ---------- */
await page.evaluate(() => document.querySelector('#timing').scrollIntoView({ block: 'center' }));
await injectAnn([{ sel: '#trend', n: 1, pos: 'tl' }, { sel: '#timing', n: 2, pos: 'tl' }]);
const rowShot = await page.screenshot({ clip: pad(await bbox(['#trend', '#timing', '#timingNote'])), fullPage: true });
await clearAnn();
await page.evaluate(() => { const l = document.getElementById('lam'); l.value = 0; l.dispatchEvent(new Event('input')); });
await page.waitForTimeout(300);
await page.evaluate(() => document.querySelector('#lam').scrollIntoView({ block: 'center' }));
await injectAnn([{ sel: '#lam', n: 3, pos: 'tl' }]);
const prefShot = await page.screenshot({ clip: pad(await bbox(['#cfnV', '#cfn', '#lam', '#lamV']), 44), fullPage: true });
await clearAnn();
await page.evaluate(() => document.querySelector('#timing').scrollIntoView({ block: 'center' }));
await injectAnn([{ sel: '#timing', n: 4, pos: 'tl' }]);
const afterShot = await page.screenshot({ clip: pad(await bbox(['#timing', '#timingNote'])), fullPage: true });
await clearAnn();
{
  const p = await ctx.newPage(); await p.setViewportSize({ width: 1400, height: 400 });
  const img = (b) => `data:image/png;base64,${b.toString('base64')}`;
  await p.setContent(`<style>${legendCss}.row2{display:grid;grid-template-columns:1fr 1.15fr;gap:0;background:#1f1714;align-items:center}.row2 img{width:100%}.mid{padding:16px 26px;background:#2a1c14;color:#ffd9ad;font-weight:650;border-top:1px solid #ffffff22;border-bottom:1px solid #ffffff22}</style>
   <div class="t"><i>Step 6 · When to announce</i><b>The best announcement time reacts to your preferences</b></div>
   <img src="${img(rowShot)}">
   <div class="mid">Now drag “Cost of each hour later” from 5% to 0% (delay is free) – the ★ moves from the earliest hour to the latest:</div>
   <div class="row2"><img src="${img(prefShot)}"><img src="${img(afterShot)}"></div>
   <div class="lg">${[
     '<b>Trend + fan</b> – today’s hourly API and the model’s 10–90% range for tomorrow 7 AM.',
     '<b>Cost bars</b> – wrong-call cost (missed closure vs needless closure) plus lateness cost for each candidate hour; ★ = cheapest. Click a bar to explore that hour.',
     '<b>Decision preferences</b> (left panel) – how bad a missed closure is, and what each hour of lateness costs.',
     '<b>Result</b> – with free delay the ★ moves to 9 PM because later hours forecast better; with costly delay the earliest hour wins.'].map((l, i) => `<div><span>${i + 1}</span><p style="margin:0">${l}</p></div>`).join('')}</div>
   <div class="ft"><span>Hazeshaman · haze early-warning for Malaysian schools</span><span>${stamp}</span></div>`);
  await p.waitForTimeout(200); await p.screenshot({ path: join(OUT, '06-announcement-time.png'), fullPage: true }); await p.close(); console.log('wrote 06-announcement-time.png');
}
await page.evaluate(() => { const l = document.getElementById('lam'); l.value = 5; l.dispatchEvent(new Event('input')); });

/* ---------- 7. what-if ---------- */
await page.evaluate(() => scrollTo(0, 0));
await page.click('#modeWhat');
await page.evaluate(() => { for (const [k, v] of [['am', 105], ['noon', 120], ['a3', 135], ['now', 150]]) { const i = document.getElementById(k); i.value = v; i.dispatchEvent(new Event('input')); } });
await page.click('#streak button[data-n="1"]');
await page.evaluate(() => { for (const id of ['sky', 'overview']) document.getElementById(id).style.display = 'none'; });   // keep the crop focused on inputs + result
await page.waitForTimeout(500);
await injectAnn([{ sel: '.seg', n: 1, pos: 'tl' }, { sel: '#hours', n: 2, pos: 'tl' }, { sel: '#am', n: 3, pos: 'tl' }, { sel: '#streak', n: 4, pos: 'tl' }, { sel: '#verdict', n: 5, pos: 'tl' }]);
shot = await page.screenshot({ clip: pad(await bbox(['aside', '#verdict', '#kpis']), 26), fullPage: true });
await compose('07-what-if.png', 'Step 7 · Try your own numbers', 'What-if mode', shot, [
  '<b>What-if</b> – switch here; sliders unlock. Switch back to Live data at any time.',
  '<b>Model hour</b> – pick the hour you would decide at (outlined = candidate announcement times).',
  '<b>Readings</b> – set API at 8 AM, noon, three hours earlier and now, plus yesterday’s mean.',
  '<b>Streak</b> – how many prior days had a mean above 150 (KPM’s three-day rule).',
  '<b>Result</b> – the recommendation and every probability recompute instantly.'], 'Illustrative inputs, not an official reading');
await clearAnn();
await page.evaluate(() => { for (const id of ['sky', 'overview']) document.getElementById(id).style.display = ''; });
await page.click('#modeLive');

/* ---------- 8. mobile ---------- */
await mob.goto(BASE + '/'); await mob.addStyleTag({ content: 'body{background-attachment:scroll!important}' }); await mob.waitForSelector('#bandName:not(:empty)'); await mob.waitForTimeout(1500);
const shots = [];
for (const sel of ['#sky', '#overview', '#verdict']) {
  const h = await mob.evaluate((s) => { const e = document.querySelector(s); e.scrollIntoView({ block: 'start' }); const r = e.getBoundingClientRect(); return { x: 0, y: r.top + scrollY - 8, h: Math.min(r.height + 16, 1100) }; }, sel);
  shots.push(await mob.screenshot({ clip: { x: 0, y: h.y, width: 390, height: h.h }, fullPage: true }));
}
{
  const p = await ctx.newPage(); await p.setViewportSize({ width: 1400, height: 400 });
  await p.setContent(`<style>${legendCss}.ph{display:flex;gap:30px;justify-content:center;align-items:flex-start;padding:28px;background:#1f1714}.ph div{width:300px}.ph img{border-radius:22px;border:1px solid #ffffff33;box-shadow:0 12px 40px #0008}.ph p{text-align:center;color:#d8c9bf;margin:10px 0 0}</style>
   <div class="t"><i>Step 8 · On your phone</i><b>Same dashboard, stacked for small screens</b></div>
   <div class="ph">${['Haze right now', 'National outlook', 'Station recommendation'].map((t, i) => `<div><img src="data:image/png;base64,${shots[i].toString('base64')}"><p>${t}</p></div>`).join('')}</div>
   <div class="ft"><span>Hazeshaman · haze early-warning for Malaysian schools</span><span>${stamp}</span></div>`);
  await p.waitForTimeout(200); await p.screenshot({ path: join(OUT, '08-mobile.png'), fullPage: true }); await p.close(); console.log('wrote 08-mobile.png');
}

/* ---------- 8. social cards (numbers read from the live dashboard) ---------- */
await page.evaluate(() => selectState(''));      // social cards always show the national picture
await page.waitForTimeout(600);
await page.evaluate(() => scrollTo(0, 0));
const facts = await page.evaluate(() => {
  const t = (s) => document.querySelector(s)?.textContent.trim();
  const kp = [...document.querySelectorAll('#hero .kpi')].map((k) => ({ l: k.querySelector('span').textContent, v: k.querySelector('b').textContent, e: k.querySelector('em').textContent }));
  const st = [...document.querySelectorAll('#skyStats .kpi')].map((k) => ({ l: k.querySelector('span').textContent, v: k.querySelector('b').textContent, e: k.querySelector('em').textContent }));
  const chips = [...document.querySelectorAll('#chips .chip')].slice(0, 4).map((c) => ({ s: c.querySelector('span').textContent, v: c.querySelector('b').textContent, c: getComputedStyle(c).getPropertyValue('--c') }));
  return { band: t('#bandName'), sub: t('#bandSub'), when: t('#skyTime'), kp, st, chips, skyline: document.querySelector('.skyline').outerHTML, color: getComputedStyle(document.getElementById('sky')).getPropertyValue('--bc') };
});
writeFileSync(join(OUT, 'snapshot.json'), JSON.stringify({ at: NOW, band: facts.band, sub: facts.sub, national: facts.kp, haze: facts.st }, null, 1));
const bandColor = { GOOD: '#34d399', MODERATE: '#facc15', UNHEALTHY: '#fb923c', 'VERY UNHEALTHY': '#ef4444', HAZARDOUS: '#be185d' }[facts.band] || '#fb923c';
const card = (w, h, square) => `<style>*{box-sizing:border-box}body{margin:0;width:${w}px;height:${h}px;overflow:hidden;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#f6ede6;
 background:radial-gradient(60% 70% at 80% 10%,#ffa94d66,transparent 70%),linear-gradient(170deg,#3d2414,#1a1318 75%);position:relative}
 svg.skyline{position:absolute;left:0;right:0;bottom:0;width:100%;height:${square ? 34 : 46}%;fill:#0c080c;opacity:.55;filter:blur(2.5px)}
 .in{position:relative;padding:${square ? '64px' : '44px 56px'};height:100%;display:flex;flex-direction:column;gap:${square ? 26 : 16}px}
 .br{font-weight:800;letter-spacing:.02em;font-size:${square ? 30 : 24}px}.br span{color:#ffa94d}.ey{font-size:${square ? 20 : 16}px;letter-spacing:.16em;text-transform:uppercase;color:#d8c4b4;font-weight:700}
 .band{font-size:${square ? 120 : 92}px;font-weight:850;letter-spacing:-.035em;line-height:.95;color:${bandColor};text-shadow:0 4px 40px ${bandColor}77}
 .grid{display:grid;grid-template-columns:repeat(${square ? 2 : 4},1fr);gap:${square ? 18 : 14}px}.k{background:#1a131899;border:1px solid #ffffff2e;border-radius:20px;padding:${square ? '20px 24px' : '14px 18px'};backdrop-filter:blur(8px)}
 .k small{display:block;color:#d8c4b4;font-size:${square ? 20 : 15}px}.k b{display:block;font-size:${square ? 58 : 40}px;line-height:1.1;font-variant-numeric:tabular-nums}.k em{font-style:normal;color:#bfae9f;font-size:${square ? 17 : 13}px}
 .ft{margin-top:auto;display:flex;justify-content:space-between;color:#cdbaa9;font-size:${square ? 20 : 15}px}.note{color:#bfae9f;font-size:${square ? 17 : 13}px;max-width:70%}</style>
 ${facts.skyline}
 <div class="in"><div style="display:flex;justify-content:space-between;align-items:center"><div class="br">Haze<span>shaman</span></div><div class="ey">${facts.when.replace(/ · \d+ STATIONS/i, '')}</div></div>
 <div><div class="ey">Malaysia · haze right now</div><div class="band">${facts.band}</div></div>
 <div class="grid">${(square ? [facts.st[0], facts.st[2], facts.kp[0], facts.kp[2]] : [facts.st[0], facts.st[2], facts.kp[0], facts.kp[2]]).map((k) => `<div class="k"><small>${k.l}</small><b>${k.v}</b><em>${k.e}</em></div>`).join('')}</div>
 <div class="ft"><span class="note">Model estimate from hourly DOE API – confirm with official APIMS and KPM announcements.</span><span>Tomorrow morning outlook</span></div></div>`;
for (const [file, w, h, sq] of [['social-card.png', 1200, 630, false], ['social-square.png', 1080, 1080, true]]) {
  const p = await ctx.newPage(); await p.setViewportSize({ width: w, height: h });
  await p.setContent(card(w, h, sq)); await p.waitForTimeout(200);
  await p.screenshot({ path: join(OUT, file) }); await p.close(); console.log('wrote', file);
}
await browser.close();
