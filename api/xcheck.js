'use strict';
/**
 * GET /api/xcheck -> docs/xcheck.json: the hourly Open-Meteo cross-check (DOE API vs an independent source,
 * expected range per station, flags). Read from the default branch on GitHub so data-only commits need no redeploy;
 * falls back to the copy bundled in the deployment.
 */
const fs = require('fs');
const path = require('path');

async function getJson(url, ms) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetch(url, { signal: ctl.signal, headers: { 'user-agent': 'hazeshaman', accept: 'application/json' } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } finally { clearTimeout(timer); }
}
function baseUrl() {
  if (process.env.XCHECK_BASE_URL) return process.env.XCHECK_BASE_URL;
  const o = process.env.VERCEL_GIT_REPO_OWNER, s = process.env.VERCEL_GIT_REPO_SLUG, b = process.env.LIVE_BASE_BRANCH || 'HEAD';
  return o && s ? `https://raw.githubusercontent.com/${o}/${s}/${b}/docs/xcheck.json` : null;
}
module.exports = async function handler(req, res) {
  if (req.method && req.method !== 'GET' && req.method !== 'HEAD') { res.statusCode = 405; res.setHeader('Allow', 'GET, HEAD'); return res.end(); }
  let doc = null, from = 'none';
  const url = baseUrl();
  if (url) { try { const j = await getJson(url, 4000); if (j && j.stations) { doc = j; from = 'github'; } } catch (e) { /* fall back */ } }
  if (!doc) {
    for (const p of [path.join(process.cwd(), 'docs', 'xcheck.json'), path.join(__dirname, '..', 'docs', 'xcheck.json')]) {
      try { doc = JSON.parse(fs.readFileSync(p, 'utf8')); from = 'bundled'; break; } catch (e) { /* next */ }
    }
  }
  if (!doc) { res.statusCode = 404; res.setHeader('content-type', 'application/json'); return res.end(JSON.stringify({ error: 'no cross-check data yet' })); }
  doc.source_via = from;
  res.statusCode = 200;
  res.setHeader('content-type', 'application/json; charset=utf-8');
  res.setHeader('x-xcheck-source', from);
  res.setHeader('cache-control', 'public, max-age=0, s-maxage=300, stale-while-revalidate=600');
  res.end(JSON.stringify(doc));
};
