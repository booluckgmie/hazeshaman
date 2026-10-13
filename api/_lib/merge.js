'use strict';
/**
 * Pure merge logic for /api/live - a line-for-line port of hazeshaman/apims.py (parse_live/clean)
 * and hazeshaman/live.py (update): same guard, same 120 h per-station buffer, same output shape.
 * Timestamps are "Malaysia wall clock" values treated as UTC-naive milliseconds.
 */
const STATE_ID = {
  1: 'Johor', 2: 'Kedah', 3: 'Kelantan', 4: 'Melaka', 5: 'Negeri Sembilan', 6: 'Pahang', 7: 'Pulau Pinang',
  8: 'Perak', 9: 'Perlis', 10: 'Selangor', 11: 'Terengganu', 12: 'Sabah', 13: 'Sarawak',
  14: 'WP Kuala Lumpur', 15: 'WP Labuan', 16: 'WP Putrajaya',
};
const KEEP_H = 120;
const HOUR = 3600e3;

/** Current Malaysia hour (UTC+8) as a naive-UTC ms value, floored to the hour. */
const nowMyt = (d = new Date()) => Math.floor((d.getTime() + 8 * HOUR) / HOUR) * HOUR;
const parseTs = (s) => Date.parse(/Z$|[+-]\d\d:?\d\d$/.test(s) ? s : s + 'Z');
const fmt = (ms) => new Date(ms).toISOString().slice(0, 16);

/**
 * @param {object|null} base    previous live.json (rolling buffer) or null
 * @param {object} payload      DOE response {api_table_hourly: [...]}
 * @param {number} asOfMs       current Malaysia hour (naive-UTC ms); later readings are "not reached yet"
 */
function mergeLive(base, payload, asOfMs) {
  const dropped = { non_numeric: 0, off_hour: 0, future_hours: 0, out_of_range: 0 };
  const areas = new Map(); // area -> Map(ts -> value)
  const put = (a, t, v) => { if (!areas.has(a)) areas.set(a, new Map()); areas.get(a).set(t, v); };

  if (base && base.areas && base.end) {
    const endMs = parseTs(base.end);
    for (const [a, vals] of Object.entries(base.areas)) {
      vals.forEach((v, i) => {
        const t = endMs - (base.hours - 1 - i) * HOUR;
        if (v != null && t <= asOfMs) put(a, t, v);
      });
    }
  }
  const stations = {};
  for (const r of (payload && payload.api_table_hourly) || []) {
    const api = r.API === null || r.API === '' || r.API === undefined ? NaN : Number(r.API);
    const t = parseTs(String(r.DATETIME));
    const state = STATE_ID[r.STATE_ID];
    if (!Number.isFinite(api) || !Number.isFinite(t) || !state) { dropped.non_numeric++; continue; }
    if (t % HOUR !== 0) { dropped.off_hour++; continue; }
    if (t > asOfMs) { dropped.future_hours++; continue; }       // hour not reached yet
    if (api < 1 || api > 500) { dropped.out_of_range++; continue; }
    const loc = String(r.STATION_LOCATION).split(',')[0].trim();
    const key = `${state}|${loc}`;
    put(key, t, api);                                            // fresh reading overrides the buffer
    stations[key] = { lat: round5(r.LATITUDE), lon: round5(r.LONGITUDE), label: loc, station_id: r.STATION_ID };
  }
  let end = -Infinity;
  for (const m of areas.values()) for (const t of m.keys()) if (t > end) end = t;
  if (!Number.isFinite(end)) return null;
  const out = {};
  for (const a of [...areas.keys()].sort()) {
    const m = areas.get(a);
    out[a] = Array.from({ length: KEEP_H }, (_, i) => {
      const v = m.get(end - (KEEP_H - 1 - i) * HOUR);
      return v == null ? null : Math.round(v);
    });
  }
  return { end: fmt(end), hours: KEEP_H, as_of: fmt(asOfMs), dropped, stations, areas: out };
}
const round5 = (x) => Math.round(Number(x) * 1e5) / 1e5;

module.exports = { mergeLive, nowMyt, STATE_ID, KEEP_H };
