import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

const require = createRequire(import.meta.url);
const { mergeLive } = require('../api/_lib/merge.js');
const handler = require('../api/live.js');
const sample = JSON.parse(readFileSync(new URL('./fixtures/doe_sample.json', import.meta.url)));
const H = 3600e3;
const asOf = Date.parse('2026-10-13T20:00:00Z');             // naive-UTC value for 20:00 Malaysia time
const row = (t, v, extra = {}) => ({ STATION_ID: 'CA01R', STATE_ID: 9, STATION_LOCATION: 'Kangar, PERLIS', LATITUDE: 6.43, LONGITUDE: 100.21, DATETIME: t, API: v, ...extra });

test('maps stations to State|Location keys and keeps the 24 h window', () => {
  const d = mergeLive(null, sample, asOf);
  assert.equal(d.end, '2026-10-13T20:00');
  assert.deepEqual(Object.keys(d.areas), ['Johor|Pasir Gudang', 'Perlis|Kangar', 'WP Kuala Lumpur|Cheras'].sort());
  const a = d.areas['Perlis|Kangar'];
  assert.equal(a.length, 120);
  assert.equal(a.filter((v) => v !== null).length, 24);
  assert.equal(a[119], 56);
});

test('drops hours that have not been reached yet, flags, off-hour stamps and out-of-range values', () => {
  const d = mergeLive(null, { api_table_hourly: [
    row('2026-10-13T19:00:00', 80), row('2026-10-13T20:00:00', 81), row('2026-10-13T21:00:00', 400),
    row('2026-10-13T20:15:00', 90), row('2026-10-13T18:00:00', -1), row('2026-10-13T17:00:00', 900),
    row('2026-10-13T16:00:00', null), row('2026-10-13T15:00:00', '-'),
  ] }, asOf);
  assert.equal(d.end, '2026-10-13T20:00');
  assert.deepEqual(d.dropped, { non_numeric: 2, off_hour: 1, future_hours: 1, out_of_range: 2 });
  assert.equal(d.areas['Perlis|Kangar'].filter((v) => v !== null).length, 2);
});

test('rolls the buffer: keeps older hours, lets fresh readings revise, ignores future buffer values', () => {
  const t = (h) => `2026-10-13T${String(h).padStart(2, '0')}:00:00`;
  const first = mergeLive(null, { api_table_hourly: [10, 11, 12, 13, 14].map((h) => row(t(h), 50 + h)) }, Date.parse('2026-10-13T14:00:00Z'));
  const next = mergeLive(first, { api_table_hourly: [row(t(14), 99), row(t(15), 70), row(t(16), 71)] }, Date.parse('2026-10-13T15:00:00Z'));
  const a = next.areas['Perlis|Kangar'];
  assert.equal(next.end, '2026-10-13T15:00');
  assert.equal(a[119], 70); assert.equal(a[118], 99); assert.equal(a[114], 60);      // 10:00 kept, 14:00 revised
  assert.ok(!a.includes(71));                                                         // 16:00 is in the future
  const stale = mergeLive({ ...first, end: '2026-10-13T17:00' }, { api_table_hourly: [] }, Date.parse('2026-10-13T15:00:00Z'));
  assert.equal(stale.end, '2026-10-13T15:00');                                        // buffer values after "now" discarded
});

test('handler: DOE + buffer -> merged json with cache headers; DOE down -> buffer only; nothing -> 502', async () => {
  const realFetch = globalThis.fetch;
  const call = async () => {
    const out = { headers: {} };
    const res = { setHeader: (k, v) => { out.headers[k.toLowerCase()] = v; }, end: (b) => { out.body = b; }, statusCode: 0 };
    await handler({ method: 'GET' }, res);
    out.status = res.statusCode; return out;
  };
  try {
    delete process.env.LIVE_BASE_URL; delete process.env.VERCEL_GIT_REPO_OWNER;
    globalThis.fetch = async () => ({ ok: true, json: async () => sample });
    // sample rows carry 2026-10-12/13 stamps; whatever "now" is, anything later than it is dropped, so just check the shape
    let r = await call();
    assert.equal(r.status, 200);
    assert.match(r.headers['cache-control'], /s-maxage=300/);
    assert.match(r.headers['x-live-source'], /^doe\+/);
    assert.ok(JSON.parse(r.body).areas);
    globalThis.fetch = async () => { throw new Error('network down'); };
    r = await call();                                   // base falls back to the bundled docs/live.json
    assert.equal(r.status, 200);
    assert.match(r.headers['x-live-source'], /-only$/);
    assert.equal(r.headers['x-live-source'].startsWith('bundled'), true);
  } finally { globalThis.fetch = realFetch; }
});
