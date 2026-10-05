// MAPZI archive proxy — reads history.json from the PRIVATE mapzi-archive repo via GitHub API.
export const config = { runtime: 'edge' };

const REPO = process.env.ARCHIVE_REPO || 'GAROGARO22/mapzi-archive';
const TOKEN = process.env.MAPZI_PAT || '';   // Vercel env var (fine-grained, contents:read on archive repo)
const GH = `https://api.github.com/repos/${REPO}/contents/`;

async function readJson(name) {
  if (!TOKEN) return null;
  try {
    const r = await fetch(GH + name + '?ref=main', { headers: { Authorization: 'Bearer ' + TOKEN, Accept: 'application/vnd.github+json' }, cache: 'no-store' });
    if (!r.ok) return null;
    const j = await r.json();
    return JSON.parse(decodeURIComponent(escape(atob(j.content.replace(/\n/g, '')))));
  } catch { return null; }
}

export default async function handler(req) {
  const cors = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' };
  if (req.method === 'OPTIONS') return new Response(null, { headers: { ...cors, 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' } });
  if (req.method === 'GET') {
    const hist = (await readJson('history.json')) || {};
    return new Response(JSON.stringify(hist), { headers: { ...cors, 'Access-Control-Allow-Origin': '*' } });
  }
  if (req.method === 'POST') {
    // suggestions are queued client-side until admin backend is wired
    return new Response(JSON.stringify({ ok: true, queued: true }), { status: 202, headers: { ...cors, 'Access-Control-Allow-Origin': '*' } });
  }
  return new Response(JSON.stringify({ error: 'method' }), { status: 405, headers: cors });
}
