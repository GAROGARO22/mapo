// MAPZI archive proxy — reads/writes history.json in the mapzi-archive repo.
export const config = { runtime: 'edge' };

const ARCHIVE_RAW = 'https://raw.githubusercontent.com/GAROGARO22/mapzi-archive/main/';
const WRITE_API = process.env.MAPZI_PAT ? `https://api.github.com/repos/${process.env.ARCHIVE_REPO || 'GAROGARO22/mapzi-archive'}/contents/` : '';
const TOKEN = process.env.MAPZI_PAT || '';

async function readJson(name) {
  try {
    const r = await fetch(ARCHIVE_RAW + name + '?_=' + Date.now(), { cache: 'no-store' });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}
async function writeJson(name, data, msg) {
  if (!TOKEN) return false;
  let sha = null;
  const cur = await fetch(WRITE_API + name + '?ref=main', { headers: { Authorization: `Bearer ${TOKEN}`, Accept: 'application/vnd.github+json' } });
  if (cur.ok) { try { sha = (await cur.json()).sha; } catch {} }
  const body = { message: msg, branch: 'main', content: btoa(unescape(encodeURIComponent(JSON.stringify(data)))) };
  if (sha) body.sha = sha;
  const r = await fetch(WRITE_API + name, { method: 'PUT', headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json', Accept: 'application/vnd.github+json' }, body: JSON.stringify(body) });
  return r.ok;
}

export default async function handler(req) {
  const cors = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' };
  if (req.method === 'OPTIONS') return new Response(null, { headers: { ...cors, 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' } });
  try {
    if (req.method === 'GET') {
      const hist = (await readJson('history.json')) || {};
      return new Response(JSON.stringify(hist), { headers: { ...cors, 'Access-Control-Allow-Origin': '*' } });
    }
    if (req.method === 'POST') {
      const b = await req.json();
      if (b.action === 'suggest') {
        // suggestions queue stored client-side until admin wires a backend; keep API ready
        const ok = await writeJson('suggestions.json', ((await readJson('suggestions.json')) || []).concat(b.payload).slice(-5000), 'new suggestion');
        return new Response(JSON.stringify({ ok }), { status: ok ? 200 : 202, headers: { ...cors, 'Access-Control-Allow-Origin': '*' } });
      }
      return new Response(JSON.stringify({ error: 'bad request' }), { status: 400, headers: cors });
    }
    return new Response(JSON.stringify({ error: 'method' }), { status: 405, headers: cors });
  } catch (e) { return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: cors }); }
}
