'use strict';
/**
 * GET /api/live  ->  live.json-shaped document, fresh to the latest DOE hourly report.
 *
 * The DOE API only allows browser calls from its own portal (CORS) and only serves the last 24 h, so this
 * function fetches it server-side and overlays it on the rolling 120 h buffer that the hourly GitHub job
 * keeps in docs/live.json (read from raw.githubusercontent.com, falling back to the bundled copy).
 * If DOE is down the buffer is returned unchanged (the dashboard then shows its own "lagging/stale" banner).
 */
const fs = require('fs');
const path = require('path');
const { mergeLive, nowMyt } = require('./_lib/merge');

const DOE_URL = 'https://eqms.doe.gov.my/api3/publicportalapims/apitablehourly';

async function getJson(url, ms) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetch(url, { signal: ctl.signal, headers: { 'user-agent': 'Mozilla/5.0 hazeshaman', accept: 'application/json' } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } finally { clearTimeout(timer); }
}

function baseUrl() {
  if (process.env.LIVE_BASE_URL) return process.env.LIVE_BASE_URL;
  const o = process.env.VERCEL_GIT_REPO_OWNER, s = process.env.VERCEL_GIT_REPO_SLUG;
  const b = process.env.LIVE_BASE_BRANCH || 'HEAD';
  return o && s ? `https://raw.githubusercontent.com/${o}/${s}/${b}/docs/live.json` : null;
}

async function loadBase() {
  const url = baseUrl();
  if (url) {
    try { const j = await getJson(url, 3000); if (j && j.areas) return { doc: j, from: 'github' }; } catch (e) { /* fall through */ }
  }
  for (const p of [path.join(process.cwd(), 'docs', 'live.json'), path.join(__dirname, '..', 'docs', 'live.json')]) {
    try { return { doc: JSON.parse(fs.readFileSync(p, 'utf8')), from: 'bundled' }; } catch (e) { /* next */ }
  }
  return { doc: null, from: 'none' };
}

module.exports = async function handler(req, res) {
  if (req.method && req.method !== 'GET' && req.method !== 'HEAD') {
    res.statusCode = 405; res.setHeader('Allow', 'GET, HEAD'); return res.end();
  }
  const asOf = nowMyt();
  const [base, doe] = await Promise.all([
    loadBase(),
    getJson(DOE_URL, 6000).then((payload) => ({ payload }), (error) => ({ error })),
  ]);
  let doc = null, source;
  if (doe.payload) { doc = mergeLive(base.doc, doe.payload, asOf); source = `doe+${base.from}`; }
  if (!doc && base.doc) { doc = base.doc; source = `${base.from}-only`; }
  if (!doc) {
    res.statusCode = 502; res.setHeader('content-type', 'application/json');
    return res.end(JSON.stringify({ error: 'no data', detail: String(doe.error || 'empty') }));
  }
  doc.source = source;
  res.statusCode = 200;
  res.setHeader('content-type', 'application/json; charset=utf-8');
  res.setHeader('x-live-source', source);
  // edge-cache 5 min, serve stale up to 10 min while revalidating: one DOE call per 5 min regardless of traffic
  res.setHeader('cache-control', 'public, max-age=0, s-maxage=300, stale-while-revalidate=600');
  res.end(JSON.stringify(doc));
};
module.exports.DOE_URL = DOE_URL;
