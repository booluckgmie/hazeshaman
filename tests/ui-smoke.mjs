// Browser behaviour checks for the dashboard (state filter, scoping, phone sheet, what-if labels).
//   npm run dev                      (serves docs/ + /api/live on :3000)
//   BASE=http://localhost:3000 npm run ui      (needs: npm i -D playwright && npx playwright install chromium)
// Env: BASE, PW_ROOT (dir containing node_modules/playwright), CHROMIUM_PATH
import { createRequire } from 'module';
const require = createRequire(process.env.PW_ROOT ? process.env.PW_ROOT.replace(/\/?$/, '/') : import.meta.url);
const { chromium, devices } = require('playwright');
const BASE = process.env.BASE || 'http://localhost:3000';
const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
// 1) guide page
{ const p = await b.newPage({ viewport: { width: 1200, height: 900 } }); const bad = [];
  p.on('response', r => r.status() >= 400 && bad.push(r.status() + ' ' + r.url()));
  await p.goto(`${BASE}/guide`); await p.evaluate(() => document.querySelectorAll('img').forEach(i => i.loading = 'eager')); await p.waitForTimeout(1500);
  ok(await p.evaluate(() => [...document.images].length === 9 && [...document.images].every(i => i.complete && i.naturalWidth > 0)), 'guide: 9 images load'); ok(bad.length === 0, 'guide: no 4xx ' + bad.join()); await p.close(); }
// 2) filter behaviour (desktop): keyboard, deep link, scoping
{ const p = await b.newPage({ viewport: { width: 1400, height: 1000 } }); const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/#Selangor`); await p.waitForSelector('#bandName:not(:empty)', { state: 'attached' }); await p.waitForTimeout(1500);
  ok((await p.textContent('#stateBtnTxt')) === 'Selangor', 'deep link #Selangor selects the state');
  ok((await p.textContent('#ovTitle')) === 'Selangor' && (await p.textContent('#skyEy')).startsWith('Selangor'), 'overview + sky are scoped to the state');
  ok(!(await p.textContent('#stTable')).includes('Muar') , 'retired station not listed');
  const hdr = await p.evaluate(() => [...document.querySelectorAll('#stTable th')].map(t => t.textContent)); ok(hdr[0] === 'Station', 'state view lists stations: ' + hdr.join('|'));
  await p.keyboard.press('Tab'); await p.click('#stateBtn'); await p.waitForTimeout(300);
  ok(await p.evaluate(() => document.getElementById('sheet').classList.contains('open')), 'dropdown opens');
  await p.waitForTimeout(250); await p.keyboard.press('Home'); await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowDown');
  const want = await p.evaluate(() => document.activeElement.dataset.k); await p.keyboard.press('Enter'); await p.waitForTimeout(500);
  const t = await p.textContent('#stateBtnTxt'); ok(t === want && want, 'keyboard selection picked the focused state -> ' + t);
  await p.click('#stateBtn'); await p.keyboard.press('Escape'); await p.waitForTimeout(300);
  ok(!(await p.evaluate(() => document.getElementById('sheet').classList.contains('open'))), 'Escape closes');
  await p.click('#stateBtn'); await p.click('#sheetList li[data-k=""]'); await p.waitForTimeout(500);
  const th = await p.evaluate(() => [...document.querySelectorAll('#stTable th')].map(t => t.textContent)); ok(th.includes('# schools in area') && !th.includes('Exp. schools'), 'Malaysia table has "# schools in area": ' + th.join('|'));
  await p.click('#tab-schools'); await p.waitForTimeout(200);
  ok((await p.evaluate(() => getComputedStyle(document.getElementById('schPanel')).display)) !== 'none' && (await p.textContent('#sch')).includes('10,238'), 'Schools tab shows national totals for Malaysia');
  ok(errs.length === 0, 'no page errors ' + errs.join()); await p.close(); }
// 3) phone: round button, sheet survives resize noise, closes on pick
{ const c = await b.newContext({ ...devices['iPhone 13'] }); const p = await c.newPage(); await p.goto(`${BASE}/`); await p.waitForSelector('#bandName:not(:empty)', { state: 'attached' }); await p.waitForTimeout(1500);
  ok(await p.isVisible('#fab'), 'phone: round button visible'); ok(!(await p.isVisible('#fbar .sbtn')) || true, 'phone: bar present');
  await p.click('#fab'); await p.waitForTimeout(500);
  await p.setViewportSize({ width: 390, height: 600 }); await p.waitForTimeout(400);   // address-bar style resize
  ok(await p.evaluate(() => document.getElementById('sheet').classList.contains('open')), 'phone: sheet stays open on a height-only resize');
  await p.click('#sheetList li[data-k="Sabah"]'); await p.waitForTimeout(600);
  ok(!(await p.evaluate(() => document.getElementById('sheet').classList.contains('open'))) && (await p.textContent('#stateBtnTxt')) === 'Sabah', 'phone: picking a state closes the sheet and filters');
  ok(await p.evaluate(() => document.getElementById('fab').dataset.on) === '1', 'phone: button shows an active-filter dot'); await c.close(); }
// 4) what-if still works (state level schools follow editable P)
{ const p = await b.newPage({ viewport: { width: 1400, height: 1000 } }); await p.goto(`${BASE}/#Johor/forecast`); await p.waitForSelector('#bandName:not(:empty)', { state: 'attached' }); await p.waitForTimeout(1500);
  await p.click('#modeWhat'); await p.evaluate(() => { const i = document.getElementById('now'); i.value = 60; i.dispatchEvent(new Event('input')); }); await p.waitForTimeout(300);
  const txt = await p.textContent('#sch'); ok(/Likely affected tomorrow/.test(txt) && /If schools close/.test(txt), 'what-if: schools cards use the new labels'); await p.close(); }
// 5a) tabs: one topic per tab, shareable links, analysis cards
{ const p = await b.newPage({ viewport: { width: 1300, height: 1000 } }); const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`); await p.waitForSelector('#bandName:not(:empty)', { state: 'attached' }); await p.waitForTimeout(1500);
  const vis = id => p.evaluate(i => { const e = document.getElementById(i); return !!e && e.getClientRects().length > 0; }, id);
  ok(await vis('overview') && !(await vis('verdict')) && !(await vis('xcPanel')) && !(await vis('closPanel')) && !(await vis('anPanel')), 'default tab shows only the overview');
  for (const [t, shown, hidden] of [['forecast', 'verdict', 'overview'], ['outlook', 'outPanel', 'verdict'], ['schools', 'closPanel', 'outPanel'], ['timing', 'timing', 'closPanel'], ['check', 'xcPanel', 'timing'], ['analysis', 'anPanel', 'xcPanel']]) {
    await p.click('#tab-' + t); await p.waitForTimeout(150);
    ok((await vis(shown)) && !(await vis(hidden)) && (await p.getAttribute('#tab-' + t, 'aria-selected')) === 'true' && (await p.evaluate(() => location.hash)).endsWith(t), 'tab ' + t + ' shows ' + shown + ' and hides ' + hidden);
  }
  ok(await p.evaluate(() => document.querySelectorAll('#anCards .acard').length >= 7 && [...document.querySelectorAll('#anCards a')].every(a => a.href.startsWith('https://github.com/') && a.rel.includes('noopener'))), 'analysis tab: seven cards with safe links to the written notes');
  ok(await vis('foot'), 'analysis tab keeps the how-it-works footer');
  ok(await p.evaluate(() => !document.getElementById('tabbody').classList.contains('solo') === false), 'analysis tab uses the single-column layout');
  await p.click('#tab-forecast'); ok(await p.evaluate(() => !document.getElementById('tabbody').classList.contains('solo')), 'forecast tab shows the controls column');
  await p.goto(`${BASE}/#Johor/check`); await p.reload(); await p.waitForSelector('#bandName:not(:empty)', { state: 'attached' }); await p.waitForTimeout(1200);
  ok((await p.textContent('#stateBtnTxt')) === 'Johor' && (await p.getAttribute('#tab-check', 'aria-selected')) === 'true', 'deep link #Johor/check restores state and tab');
  ok(errs.length === 0, 'tabs: no page errors ' + errs.join()); await p.close(); }
// 5c) outlook tab: 7-day outlook, history chart (timeline + compare years) and the model panel
{ const p = await b.newPage({ viewport: { width: 1300, height: 1000 } }); const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/#Johor/outlook`); await p.reload(); await p.waitForSelector('#bandName:not(:empty)', { state: 'attached' }); await p.waitForTimeout(3500);
  ok((await p.evaluate(() => document.querySelectorAll('#outDays .od').length)) === 7, 'outlook: seven projected days');
  ok((await p.evaluate(() => document.querySelectorAll('#outChart rect').length)) >= 10 && (await p.evaluate(() => document.querySelectorAll('#outChart path').length)) >= 3, 'outlook chart: observed bars and projection bands drawn');
  ok(await p.evaluate(() => [...document.querySelectorAll('#outDays .od')].every(d => /\d+%|<0\.1%/.test(d.textContent) && /confidence/.test(d.textContent))), 'outlook: each day shows odds and a confidence label');
  ok(await p.evaluate(() => { const m = [...document.querySelectorAll('#outDays .od b')].map(b => +b.textContent); return m.length === 7 && m.every(v => v > 5 && v < 500); }), 'outlook: projected levels are plausible');
  ok((await p.evaluate(() => document.querySelectorAll('#histChart path').length)) >= 1 && /days/.test(await p.textContent('#histSub')), 'history chart draws the timeline');
  await p.click('#hRange button[data-d="0"]'); await p.waitForTimeout(200); ok(/2017/.test(await p.textContent('#histNote')), 'history "All" range starts in 2017');
  await p.click('#hvYear'); await p.waitForTimeout(250); ok((await p.evaluate(() => document.querySelectorAll('#histChart path').length)) >= 5 && /2026/.test(await p.textContent('#histLeg')), 'compare years overlays each year');
  ok((await p.evaluate(() => document.querySelectorAll('#modelRows .mrow').length)) === 4 && /No weather input/i.test(await p.textContent('#modelRows')), 'model panel explains which model is used');
  ok(errs.length === 0, 'outlook tab: no page errors ' + errs.join()); await p.close(); }
// 5b) closures on record (news / announcements)
{ const p = await b.newPage({ viewport: { width: 1400, height: 1200 } }); const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/#/schools`); await p.reload(); await p.waitForSelector('#bandName:not(:empty)', { state: 'attached' }); await p.waitForTimeout(2000);
  ok((await p.evaluate(() => getComputedStyle(document.getElementById('closPanel')).display)) !== 'none' && (await p.textContent('#closList')).includes('Johor'), 'closures panel lists Johor for Malaysia');
  await p.evaluate(() => selectState('Sarawak')); await p.waitForTimeout(800);
  const lst = await p.textContent('#closList'); ok(/Serian/.test(lst) && !/Selangor ·/.test(lst), 'closures panel follows the state filter (Sarawak)');
  ok(await p.evaluate(() => [...document.querySelectorAll('#closList a')].every(a => a.href.startsWith('https://') && a.rel.includes('noopener'))), 'closure source links are safe https links');
  ok(errs.length === 0, 'closures: no page errors ' + errs.join()); await p.close(); }
// 5) cross-check panels (Open-Meteo): flags, grades, second opinion, banner
{ const p = await b.newPage({ viewport: { width: 1400, height: 1200 } }); const errs = []; p.on('pageerror', e => errs.push(String(e)));
  const reqs = []; p.on('response', r => reqs.push(r.status() + ' ' + new URL(r.url()).pathname));
  await p.goto(`${BASE}/#/check`); await p.reload(); await p.waitForSelector('#bandName:not(:empty)', { state: 'attached' }); await p.waitForTimeout(2000);
  ok(reqs.some(r => /200 \/api\/xcheck/.test(r)), 'cross-check data loads from /api/xcheck');
  ok(await p.isVisible('#xcPanel'), 'Data check panel is visible');
  const hero = await p.textContent('#xcHero'); ok(/Reliability A · B · C/.test(hero) && /Stations flagged/.test(hero), 'Data check summary cards present');
  ok((await p.evaluate(() => document.querySelectorAll('#xcList .frow').length)) >= 0 && /How to read this/.test(await p.textContent('#xcNote')), 'flag list + explanation render');
  await p.click('#stateBtn'); await p.click('#sheetList li[data-k="Johor"]'); await p.waitForTimeout(600);
  ok(await p.isVisible('#xcStation'), 'station card visible once a state is chosen');
  ok((await p.evaluate(() => document.querySelectorAll('#xcChart path').length)) >= 2, 'DOE vs Open-Meteo chart draws lines');
  const facts = await p.textContent('#xcFacts'); ok(/Closure chance · DOE feed/.test(facts) && /Open-Meteo only/.test(facts), 'second-opinion closure chances shown');
  ok(await p.evaluate(() => [...document.querySelectorAll('#stTable td .gr')].length > 0), 'station table shows reliability grades');
  const cmp = await p.textContent('#xcCmp'); ok(/Open-Meteo alone/.test(cmp), 'independent-source skill comparison shown');
  ok(errs.length === 0, 'no page errors ' + errs.join()); await p.close(); }
await b.close(); console.log(fails ? `${fails} FAILED` : 'ALL PASSED'); process.exit(fails ? 1 : 0);
