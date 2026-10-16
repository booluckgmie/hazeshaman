import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const handler = require('../api/analytics.js');
const { readRows } = handler;
const call = async (env, deps, method = 'GET') => {
  const old = { ...process.env }; Object.assign(process.env, env);
  for (const k of Object.keys(process.env)) if (k.startsWith('VERCEL_ANALYTICS') || k === 'VERCEL_PROJECT_ID') if (!(k in env)) delete process.env[k];
  const res = { headers: {}, setHeader(k, v) { this.headers[k.toLowerCase()] = v; }, end(b) { this.body = b; } };
  try { await handler({ method }, res, deps); } finally { process.env = old; }
  return { code: res.statusCode, headers: res.headers, json: res.body ? JSON.parse(res.body) : null };
};

test('no token -> connected:false, no outbound call', async () => {
  let called = 0; const r = await call({}, { query: async () => { called++; return {}; } });
  assert.equal(r.code, 200); assert.equal(r.json.connected, false); assert.equal(r.json.reason, 'no_token'); assert.equal(called, 0);
});
test('rows are normalised and totals summed', async () => {
  const q = async by => ({ data: by[0] === 'day' ? [{ key: '2026-10-14', total: 10, devices: 4 }, { key: '2026-10-15', total: 5, devices: 3 }] : [{ key: '/', total: 9, devices: 6 }] });
  const r = await call({ VERCEL_ANALYTICS_TOKEN: 't', VERCEL_PROJECT_ID: 'prj_x' }, { query: q, now: Date.parse('2026-10-16T00:00:00Z') });
  assert.equal(r.json.connected, true); assert.deepEqual(r.json.totals, { views: 15, visitors: 7 });
  assert.equal(r.json.pages[0].key, '/'); assert.equal(r.json.pages[0].views, 9); assert.equal(r.json.since, '2026-09-16');
});
test('API failure degrades to connected:false and never leaks the token', async () => {
  const r = await call({ VERCEL_ANALYTICS_TOKEN: 'secret-token', VERCEL_PROJECT_ID: 'prj_x' }, { query: async () => { throw new Error('Vercel API 403'); } });
  assert.equal(r.json.connected, false); assert.equal(r.json.reason, 'api_error'); assert.ok(!JSON.stringify(r.json).includes('secret-token'));
});
test('only GET/HEAD', async () => { const r = await call({}, {}, 'POST'); assert.equal(r.code, 405); });
test('readRows tolerates alternative field names and drops empty keys', () => {
  assert.deepEqual(readRows([{ country: 'MY', count: 3, visitors: 2 }, { total: 4 }], 'country'), [{ key: 'MY', views: 3, visitors: 2 }]);
  assert.deepEqual(readRows({ data: [] }, 'x'), []);
});
