// Local stand-in for Vercel: serves docs/, routes /api/live to the real handler and applies vercel.json headers.
//   node scripts/dev-server.mjs [port]      (set LIVE_BASE_URL to override the buffer source)
import http from 'node:http';
import { createRequire } from 'node:module';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';

const require = createRequire(import.meta.url);
const root = new URL('..', import.meta.url).pathname;
const cfg = JSON.parse(readFileSync(join(root, 'vercel.json'), 'utf8'));
const handlers = { '/api/live': require('../api/live.js'), '/api/xcheck': require('../api/xcheck.js') };
const port = Number(process.argv[2] || process.env.PORT || 3000);
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.css': 'text/css', '.md': 'text/plain' };

const rules = cfg.headers.map((h) => ({ re: new RegExp('^' + h.source.replace(/\(\.\*\)/g, '.*') + '$'), headers: h.headers }));
const withHeaders = (res, pathname) => rules.forEach((r) => r.re.test(pathname) && r.headers.forEach((h) => res.setHeader(h.key, h.value)));

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  withHeaders(res, url.pathname);
  if (handlers[url.pathname]) return handlers[url.pathname](req, res);
  let p = normalize(join(root, 'docs', url.pathname === '/' ? 'index.html' : url.pathname));
  if (!p.startsWith(join(root, 'docs'))) { res.statusCode = 403; return res.end(); }
  if (existsSync(p) && statSync(p).isDirectory()) p = join(p, 'index.html');
  if (!existsSync(p) && existsSync(p + '.html')) p += '.html';           // cleanUrls
  if (!existsSync(p)) { res.statusCode = 404; return res.end('Not found'); }
  res.setHeader('content-type', MIME[extname(p)] || 'application/octet-stream');
  res.end(readFileSync(p));
}).listen(port, () => console.log(`hazeshaman dev server on http://localhost:${port}`));
