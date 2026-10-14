// Policy-maker social kit: live snapshots of the dashboard + three share cards whose numbers are read from the data files.
//   BASE=https://hazeshaman.vercel.app PW_ROOT=/node-tools/node_modules CHROMIUM_PATH=/opt/pw-browsers/chromium node scripts/make_policy_cards.mjs
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
const require = createRequire(process.env.PW_ROOT ? process.env.PW_ROOT.replace(/\/?$/, '/') : import.meta.url);
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'https://hazeshaman.vercel.app';
const root = fileURLToPath(new URL('..', import.meta.url));
const SNAP = join(root, 'social/snapshots'); mkdirSync(SNAP, { recursive: true });
const read = (f) => JSON.parse(readFileSync(join(root, f), 'utf8'));
const model = JSON.parse(readFileSync(join(root, 'docs/model.js'), 'utf8').split('=').slice(1).join('=').trim().replace(/;$/, ''));
const dec = read('docs/decisions.json'), xc = read('docs/xcheck.json');

/* ---------- numbers (all from the files the dashboard runs on) ---------- */
const R = dec.replay.rows, hit = (col) => R.filter((r) => r[col] && r.trigger_met_next_day).length, days = R.filter((r) => r.trigger_met_next_day).length;
const med = (a) => { const s = a.slice().sort((x, y) => x - y); return s[s.length >> 1]; };
const corr = (pre) => med(Object.entries(xc.stations).filter(([k]) => k.startsWith(pre)).map(([, v]) => v.stats.corr));
const peninsula = med(Object.entries(xc.stations).filter(([k]) => !/^(Sarawak|Sabah|WP Labuan)\|/.test(k)).map(([, v]) => v.stats.corr));
const grades = { A: 0, B: 0, C: 0 }; for (const v of Object.values(xc.stations)) grades[v.grade]++;
const bss = model.announce_hours.map((h) => model.backtest[h].metrics.close.bss), sm = dec.summary;
const F = {
  modelHit: hit('model_says_close'), closHit: hit('authorities_closed'), days, evenings: R.length,
  sar: corr('Sarawak|'), sab: corr('Sabah|'), pen: peninsula, grades, flagged: xc.summary.flagged, critical: xc.summary.critical, stations: Object.keys(xc.stations).length,
  skillLo: Math.round(Math.min(...bss) * 100), skillHi: Math.round(Math.max(...bss) * 100), justified: sm.justified, evaluated: sm.evaluated,
  late: sm.lag.filter((l) => l.school_days_late >= 1).length,
  schools: Object.values(model.schools_by_state).reduce((n, c) => n + c.schools, 0), students: Object.values(model.schools_by_state).reduce((n, c) => n + c.students, 0),
};
writeFileSync(join(SNAP, 'facts.json'), JSON.stringify(F, null, 1));

/* ---------- live snapshots ---------- */
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] });
const ctx = await browser.newContext({ viewport: { width: 1300, height: 1000 }, deviceScaleFactor: 2, colorScheme: 'dark' });
const page = await ctx.newPage();
await page.goto(BASE + '/'); await page.waitForSelector('#bandName:not(:empty)'); await page.waitForTimeout(3500);
await page.addStyleTag({ content: 'body{background-attachment:scroll!important}.fab,#fab{display:none!important}' });
const live = await page.evaluate(() => ({ when: document.getElementById('skyTime').textContent, band: document.getElementById('bandName').textContent,
  risk: document.querySelector('#hero .kpi b')?.textContent, schools: [...document.querySelectorAll('#hero .kpi b')].map((b) => b.textContent) }));
const shot = async (name, sels) => {
  const box = await page.evaluate((ss) => { const r = ss.map((s) => document.querySelector(s).getBoundingClientRect()); const x0 = Math.min(...r.map((b) => b.left)), y0 = Math.min(...r.map((b) => b.top)) + scrollY, x1 = Math.max(...r.map((b) => b.right)), y1 = Math.max(...r.map((b) => b.bottom)) + scrollY; return { x: Math.max(0, x0 - 10), y: Math.max(0, y0 - 10), width: x1 - x0 + 20, height: y1 - y0 + 20 }; }, sels);
  const buf = await page.screenshot({ clip: box, fullPage: true }); writeFileSync(join(SNAP, name), buf); console.log('wrote snapshots/' + name); return buf;
};
await page.evaluate(() => scrollTo(0, 0));
await page.evaluate(() => document.querySelector('header').style.visibility = 'hidden');
const sOver = await shot('overview.png', ['#sky']);
await page.evaluate(() => document.querySelector('#tab-overview').click()); await page.waitForTimeout(300);
const sTable = await shot('national-outlook.png', ['#overview']);
await page.evaluate(() => { selectState('Johor'); setTab('forecast'); }); await page.waitForTimeout(900);
const sFore = await shot('forecast-johor.png', ['#verdict', '#kpis']);
const sScen = await shot('scenarios.png', ['#verdict', '#kpis', '#scen']);
await page.evaluate(() => { selectState(''); setTab('check'); }); await page.waitForTimeout(900);
const sCheck = await shot('data-check.png', ['#xcHero', '#xcList']);
await page.evaluate(() => setTab('analysis')); await page.waitForTimeout(500);
const sAn = await shot('analysis.png', ['#anPanel']);
await page.evaluate(() => setTab('schools')); await page.waitForTimeout(500);
const sSchools = await shot('schools-closures.png', ['#schPanel']);
await browser.close();

/* ---------- cards ---------- */
const b64 = (b) => `data:image/png;base64,${b.toString('base64')}`;
const css = (w, h) => `*{box-sizing:border-box}body{margin:0;width:${w}px;height:${h}px;overflow:hidden;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#f6ede6;position:relative;
 background:radial-gradient(70% 60% at 85% 0%,#ffa94d55,transparent 70%),radial-gradient(60% 50% at 0% 100%,#7dd3fc22,transparent 70%),linear-gradient(170deg,#3a2314,#171117 80%)}
 .in{position:relative;height:100%;display:flex;flex-direction:column;padding:56px 60px;gap:24px}
 .br{font-weight:850;font-size:28px;letter-spacing:.02em}.br span{color:#ffa94d}.tag{font-size:17px;letter-spacing:.16em;text-transform:uppercase;color:#ffcf99;font-weight:750}
 h1{margin:0;font-size:60px;line-height:1.04;letter-spacing:-.03em;font-weight:850}h1 em{font-style:normal;color:#ffa94d}
 p.lead{margin:0;font-size:25px;line-height:1.35;color:#e6d6c8}
 .st{display:grid;gap:16px}.s{background:#1a131899;border:1px solid #ffffff2e;border-radius:22px;padding:20px 26px;display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center}
 .s b{font-size:62px;line-height:1;font-variant-numeric:tabular-nums;letter-spacing:-.03em;color:#ffb866}.s span{font-size:21px;line-height:1.32;color:#eadbcd}.s small{display:block;font-size:15px;color:#bfae9f;margin-top:4px}
 img.sh{width:100%;border-radius:22px;border:1px solid #ffffff33;box-shadow:0 18px 50px #000a}
 .ft{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;gap:20px;color:#cdbaa9;font-size:17px;line-height:1.35}.ft b{color:#fff;font-size:24px}`;
const cards = [
  // A - the decision-support card for policy makers (portrait: LinkedIn / Instagram / Facebook)
  ['policy-card-portrait.png', 1080, 1350, `<style>${css(1080, 1350)}</style><div class="in">
    <div style="display:flex;justify-content:space-between;align-items:center"><div class="br">Haze<span>shaman</span></div><div class="tag">Decision support · Malaysia</div></div>
    <h1>An early, evidence-backed signal for <em>next-morning</em> school decisions.</h1>
    <p class="lead">Next-morning closure risk for every state, from hourly DOE data since 2017, cross-checked against an independent source and tested on days the model never saw.</p>
    <div class="st">
     <div class="s"><b>${F.modelHit} of ${F.days}</b><span>days the KPM trigger was met next day were flagged by the 6 PM model run the evening before (6–13 Oct replay)<small>Recorded closures covered ${F.closHit} of ${F.days}. Not like-for-like: authorities also weigh health, logistics and district scope.</small></span></div>
     <div class="s"><b>${F.grades.A} · ${F.grades.B} · ${F.grades.C}</b><span>stations graded A · B · C against Open-Meteo, with ${F.flagged} doubtful reports flagged<small>Sarawak and Sabah data agree about as well as the peninsula.</small></span></div>
     <div class="s"><b>${F.skillLo}–${F.skillHi}%</b><span>lower error than always guessing the base rate (Brier skill, 3–9 PM decisions, out-of-sample)<small>Cost-optimal announcement time moves with your own trade-off.</small></span></div>
    </div>
    <img class="sh" src="${b64(sFore)}">
    <div class="ft"><div><b>hazeshaman.vercel.app</b><br>Live snapshot ${live.when.replace(/ · \d+ STATIONS/i, '')} · model estimates, not an official decision</div><div style="text-align:right">Data: DOE API · OpenDOSM / MOE · Open-Meteo (CAMS)</div></div></div>`],
  // B - data trust (landscape: X / LinkedIn / link preview)
  ['trust-card-landscape.png', 1200, 630, `<style>${css(1200, 630)}.in{padding:40px 52px;gap:16px}h1{font-size:46px}.s b{font-size:50px}.s{padding:14px 22px}.s span{font-size:19px}</style><div class="in">
    <div style="display:flex;justify-content:space-between;align-items:center"><div class="br">Haze<span>shaman</span></div><div class="tag">Is the number on the screen right?</div></div>
    <h1>Every reading is <em>cross-checked</em>, and doubtful ones are flagged.</h1>
    <div style="display:grid;grid-template-columns:1fr 1.15fr;gap:22px;align-items:center">
     <div class="st"><div class="s"><b>${F.sar.toFixed(2)}</b><span>Sarawak agreement with an independent model<small>Sabah ${F.sab.toFixed(2)} · Peninsula ${F.pen.toFixed(2)}</small></span></div>
      <div class="s"><b>${F.flagged}</b><span>reports flagged in 5 days<small>${F.critical} at closure level, ${F.grades.C} stations graded “verify”</small></span></div></div>
     <img class="sh" src="${b64(sCheck)}"></div>
    <div class="ft"><div><b>hazeshaman.vercel.app</b> · live data check tab</div><div>Model estimates; confirm with official APIMS and KPM.</div></div></div>`],
  // C - public-facing live card (square)
  ['live-card-square.png', 1080, 1080, `<style>${css(1080, 1080)}h1{font-size:54px}.in{justify-content:space-between}</style><div class="in">
    <div style="display:flex;justify-content:space-between;align-items:center"><div class="br">Haze<span>shaman</span></div><div class="tag">${live.when.replace(/ · \d+ STATIONS/i, '')}</div></div>
    <h1>${live.band.charAt(0) + live.band.slice(1).toLowerCase()} air across Malaysia. <em>${live.risk.replace(' / ', ' of ')} stations</em> at closure risk tomorrow.</h1>
    <img class="sh" src="${b64(sOver)}">
    <p class="lead" style="font-size:22px">Live from the DOE hourly API, by state and station, with the schools, students and teachers behind each state.</p>
    <div class="ft"><div><b>hazeshaman.vercel.app</b></div><div style="text-align:right">Model estimate, not an official decision.</div></div></div>`],
];
const b2 = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] });
for (const [file, w, h, html] of cards) {
  const p = await b2.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 }); await p.setContent(html); await p.waitForTimeout(300);
  await p.screenshot({ path: join(root, 'social', file) }); await p.close(); console.log('wrote social/' + file);
}
await b2.close();
console.log(JSON.stringify({ live, F }, null, 1));
