// MAPZI history archive proxy.
// Stores history.json + suggestions in a PRIVATE GitHub repo (server-side token only).
export const config = { runtime: 'edge' };

const REPO = process.env.ARCHIVE_REPO || 'GAROGARO22/mapzi-archive';
const TOKEN = process.env.GITHUB_TOKEN || ''; // Vercel-provided or user PAT secret
const FILE = 'history.json';
const SUGG = 'suggestions.jsonl';
const GH = 'https://api.github.com/repos/' + REPO + '/contents/';

async function gh(path, init) {
  const res = await fetch(GH + path, {
    ...init,
    headers: {
      Authorization: 'Bearer ' + TOKEN,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });
  return res;
}

async function readJson(name) {
  const r = await gh(name + '?ref=main', { method: 'GET' });
  if (!r.ok) return null;
  const j = await r.json();
  try { return JSON.parse(atob(j.content.replace(/\n/g, ''))); } catch { return null; }
}

async function writeJson(name, data, msg) {
  const cur = await gh(name + '?ref=main', { method: 'GET' });
  let sha = null;
  if (cur.ok) sha = (await cur.json()).sha;
  const body = {
    message: msg,
    content: btoa(unescape(encodeURIComponent(JSON.stringify(data)))),
    branch: 'main',
  };
  if (sha) body.sha = sha;
  const r = await gh(name, { method: sha ? 'PUT' : 'PUT', body: JSON.stringify(body) });
  return r.ok;
}

async function appendLine(name, line) {
  // store jsonl inside a json array file for simplicity
  const arr = (await readJson(name)) || [];
  arr.push(line);
  if (arr.length > 5000) arr.splice(0, arr.length - 5000);
  return writeJson(name, arr, 'append suggestion');
}

export default async function handler(req) {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };
  if (req.method === 'OPTIONS') return new Response(null, { headers: cors });
  if (!TOKEN) return new Response(JSON.stringify({ error: 'GITHUB_TOKEN not configured' }), { status: 500, headers: cors });

  const url = new URL(req.url);
  const action = url.searchParams.get('action') || 'get';

  try {
    if (req.method === 'GET' && action === 'get') {
      const hist = (await readJson(FILE)) || {};
      return new Response(JSON.stringify(hist), { headers: cors });
    }
    if (req.method === 'POST') {
      const body = await req.json();
      if (body.action === 'save') {
        const ok = await writeJson(FILE, body.history || {}, 'sync history ' + new Date().toISOString());
        return new Response(JSON.stringify({ ok }), { status: ok ? 200 : 502, headers: cors });
      }
      if (body.action === 'suggest') {
        const ok = await appendLine(SUGG, JSON.stringify(body.payload));
        return new Response(JSON.stringify({ ok }), { status: ok ? 200 : 502, headers: cors });
      }
    }
    return new Response(JSON.stringify({ error: 'bad request' }), { status: 400, headers: cors });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: cors });
  }
}
