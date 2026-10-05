// MAPZI archive proxy — reads/writes history.json in the PRIVATE mapzi-archive repo.
export const config = { runtime: 'edge' };

const REPO = process.env.ARCHIVE_REPO || 'GAROGARO22/mapzi-archive';
const TOKEN = process.env.MAPZI_PAT || '';   // set as Vercel env var (same PAT)
const FILE = 'history.json', SUGG = 'suggestions.json';
const GH = `https://api.github.com/repos/${REPO}/contents/`;

async function gh(path, init = {}) {
  return fetch(GH + path, {
    ...init,
    headers: { Authorization: `Bearer ${TOKEN}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json', ...(init.headers || {}) },
  });
}
async function readJson(name) {
  const r = await gh(`${name}?ref=main`);
  if (!r.ok) return null;
  try {
    const j = await r.json();
    return JSON.parse(decodeURIComponent(escape(atob(j.content.replace(/\n/g, '')))));
  } catch { return null; }
}
async function writeJson(name, data, msg) {
  const cur = await gh(`${name}?ref=main`);
  let sha = null;
  if (cur.ok) { try { sha = (await cur.json()).sha; } catch {} }
  const body = { message: msg, branch: 'main', content: btoa(unescape(encodeURIComponent(JSON.stringify(data)))) };
  if (sha) body.sha = sha;
  const r = await gh(name, { method: 'PUT', body: JSON.stringify(body) });
  return r.ok;
}

export default async function handler(req) {
  const cors = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' };
  if (req.method === 'OPTIONS') return new Response(null, { headers: { ...cors, 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' } });
  if (!TOKEN) return new Response(JSON.stringify({ error: 'MAPZI_PAT not configured on Vercel' }), { status: 500, headers: cors });
  const url = new URL(req.url);
  try {
    if (req.method === 'GET') return new Response(JSON.stringify((await readJson(FILE)) || {}), { headers: cors });
    if (req.method === 'POST') {
      const b = await req.json();
      if (b.action === 'suggest') {
        const arr = (await readJson(SUGG)) || [];
        arr.push(b.payload); if (arr.length > 5000) arr.splice(0, arr.length - 5000);
        const ok = await writeJson(SUGG, arr, 'new suggestion');
        return new Response(JSON.stringify({ ok }), { status: ok ? 200 : 502, headers: cors });
      }
    }
    return new Response(JSON.stringify({ error: 'bad request' }), { status: 400, headers: cors });
  } catch (e) { return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: cors }); }
}
