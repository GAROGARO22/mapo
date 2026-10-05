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
    return JSON.parse(b64dec(j.content));
  } catch { return null; }
}

// base64 helpers that work in edge runtime (no Buffer)
function b64enc(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}
function b64dec(b64) {
  const bin = atob(b64.replace(/\n/g, ''));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

// commit a JSON file to the archive repo (create or update with sha)
async function writeJson(name, obj, msg) {
  if (!TOKEN) return false;
  try {
    let sha = null;
    const g = await fetch(GH + name + '?ref=main', { headers: { Authorization: 'Bearer ' + TOKEN, Accept: 'application/vnd.github+json' }, cache: 'no-store' });
    if (g.ok) sha = (await g.json()).sha || null;
    const payload = { message: msg || ('mapzi: update ' + name), content: b64enc(JSON.stringify(obj)) };
    if (sha) payload.sha = sha;
    const r = await fetch(GH + name, { method: 'PUT', headers: { Authorization: 'Bearer ' + TOKEN, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' }, body: JSON.stringify(payload), cache: 'no-store' });
    return r.ok;
  } catch { return false; }
}

// merge incoming history with stored history (per-day, dedupe by sig+t)
function mergeHistory(stored, incoming) {
  const out = Object.assign({}, stored);
  for (const [day, val] of Object.entries(incoming || {})) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) continue;
    const cur = out[day] || { updates: [], latest: null };
    const seen = new Set((cur.updates || []).map(u => u.t + '|' + u.sig));
    for (const u of (val.updates || [])) {
      const key = u.t + '|' + u.sig;
      if (!seen.has(key)) { cur.updates.push(u); seen.add(key); }
    }
    cur.updates.sort((a, b) => a.t < b.t ? -1 : 1);
    if (cur.updates.length > 1000) cur.updates.splice(0, cur.updates.length - 1000);
    const lastSig = cur.updates[cur.updates.length - 1];
    cur.latest = lastSig ? lastSig.sig : cur.latest;
    out[day] = cur;
  }
  return out;
}

export default async function handler(req) {
  const cors = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' };
  if (req.method === 'OPTIONS') return new Response(null, { headers: { ...cors } });
  if (req.method === 'GET') {
    const hist = (await readJson('history.json')) || {};
    return new Response(JSON.stringify(hist), { headers: { ...cors } });
  }
  if (req.method === 'POST') {
    const corsPost = { ...cors };
    let j = null;
    try { j = await req.json(); } catch {}
    if (j && j.action === 'save' && j.history) {
      const stored = (await readJson('history.json')) || {};
      const merged = mergeHistory(stored, j.history);
      const ok = await writeJson('history.json', merged, 'mapzi: daily history rollup');
      return new Response(JSON.stringify({ ok, merged }), { status: ok ? 200 : 502, headers: corsPost });
    }
    if (j && j.action === 'suggest' && j.payload) {
      // queue visitor suggestions server-side (never exposes tables to visitors)
      const q = (await readJson('suggestions.json')) || [];
      q.push(Object.assign({}, j.payload, { at: new Date().toISOString() }));
      const ok = await writeJson('suggestions.json', q.slice(-500), 'mapzi: new place suggestion');
      return new Response(JSON.stringify({ ok: true, queued: !!ok }), { status: 202, headers: corsPost });
    }
    return new Response(JSON.stringify({ ok: true, queued: true }), { status: 202, headers: corsPost });
  }
  return new Response(JSON.stringify({ error: 'method' }), { status: 405, headers: cors });
}
