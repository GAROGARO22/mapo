// MAPZI — map data proxy (standalone backend)
// Pulls the ORIGINAL Google My Maps KML export server-side, parses it into a
// compact JSON snapshot {layers, points} and commits it to the private archive
// repo as mapdata.json. The frontend NEVER talks to google.com directly.
export const config = { runtime: 'edge' };

const REPO = globalThis.process?.env?.ARCHIVE_REPO || 'GAROGARO22/mapzi-archive';
const TOKEN = globalThis.process?.env?.MAPZI_PAT || '';
const MID = '1NZygQ5FhCvHG3ZH6Ddk3lbzAwnJum8M';
const GH = `https://api.github.com/repos/${REPO}/contents/`;
const RAW = `https://raw.githubusercontent.com/${REPO}/main/`;

const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }
});

function b64enc(str) {
  const bytes = new TextEncoder().encode(str); let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}
function b64dec(b64) {
  const bin = atob(b64.replace(/\n/g, '')); const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

async function ghRead(name) { // returns {content, sha} or null
  try {
    const r = await fetch(GH + name + '?ref=main', { headers: { Authorization: 'Bearer ' + TOKEN, Accept: 'application/vnd.github+json' }, cache: 'no-store' });
    if (!r.ok) return null;
    const j = await r.json();
    return { content: b64dec(j.content), sha: j.sha };
  } catch { return null; }
}
async function ghWrite(name, str, msg) {
  try {
    const cur = await ghRead(name);
    const payload = { message: msg, content: b64enc(str) };
    if (cur && cur.sha) payload.sha = cur.sha;
    const r = await fetch(GH + name, { method: 'PUT', headers: { Authorization: 'Bearer ' + TOKEN, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    return r.ok;
  } catch { return false; }
}

// ---------- minimal KML parser (regex based, edge-safe) ----------
function hexFromAABBGGRR(c) { return '#' + c.slice(6, 8) + c.slice(4, 6) + c.slice(2, 4); }

function parseKml(xml) {
  // style id -> color
  const styleColor = {};
  const stRe = /<Style\s+id="([^"]+)">([\s\S]*?)<\/Style>/g; let m;
  while ((m = stRe.exec(xml))) {
    const c = /<color>([0-9a-fA-F]{8})<\/color>/.exec(m[2]);
    if (c) styleColor[m[1]] = hexFromAABBGGRR(c[1].toLowerCase());
  }
  const smRe = /<StyleMap\s+id="([^"]+)">[\s\S]*?<key>normal<\/key>\s*<styleUrl>#([^<]+)<\/styleUrl>[\s\S]*?<\/StyleMap>/g;
  while ((m = smRe.exec(xml))) {
    if (styleColor[m[2]]) styleColor[m[1]] = styleColor[m[2]];
  }
  // folders & placemarks in document order
  const layers = []; const points = [];
  const folderRe = /<Folder>\s*<name>([^<]*)<\/name>([\s\S]*?)<\/Folder>/g;
  while ((m = folderRe.exec(xml))) {
    const lname = (m[1] || '').replace(/&amp;/g, '&').replace(/&#39;/g, "'").trim() || 'بدون اسم';
    if (!layers.includes(lname)) layers.push(lname);
    const body = m[2];
    const pmRe = /<Placemark>([\s\S]*?)<\/Placemark>/g; let p;
    while ((p = pmRe.exec(body))) {
      const blk = p[1];
      const co = /<Point>\s*<coordinates>([^<]+)<\/coordinates>/.exec(blk);
      if (!co) continue;
      const parts = co[1].trim().split(',');
      const lon = parseFloat(parts[0]), lat = parseFloat(parts[1]);
      if (!isFinite(lat) || !isFinite(lon)) continue;
      const nm = /<name>([^<]*)<\/name>/.exec(blk);
      const su = /<styleUrl>#([^<]+)<\/styleUrl>/.exec(blk);
      const de = /<description>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/description>/.exec(blk);
      let desc = de ? de[1] : '';
      desc = desc.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim().slice(0, 250);
      let color = '#cfd8dc';
      if (su) {
        if (styleColor[su[1]]) color = styleColor[su[1]];
        else { const mm = /-([0-9a-fA-F]{8})-/.exec(su[1]); if (mm) color = hexFromAABBGGRR(mm[1].toLowerCase()); }
      }
      const name = nm ? nm[1].replace(/&amp;/g, '&').replace(/&#39;/g, "'").trim() : '';
      points.push({ id: points.length, n: name.slice(0, 120), la: Math.round(lat * 1e5) / 1e5, lo: Math.round(lon * 1e5) / 1e5, l: lname, c: color, d: desc });
    }
  }
  // placemarks outside any <Folder> (document level) — keep them too, dedupe by coords
  const seen = new Set(points.map(p => Math.round(p.la * 1e5) + ',' + Math.round(p.lo * 1e5)));
  for (const blk of xml.split('<Placemark>').slice(1)) {
    const body = blk.split('</Placemark>')[0];
    const co = /<Point>\s*<coordinates>([^<]+)<\/coordinates>/.exec(body);
    if (!co) continue;
    const parts = co[1].trim().split(',');
    const lon = parseFloat(parts[0]), lat = parseFloat(parts[1]);
    if (!isFinite(lat) || !isFinite(lon)) continue;
    const key = Math.round(lat * 1e5) + ',' + Math.round(lon * 1e5);
    if (seen.has(key)) continue;
    seen.add(key);
    const nm = /<name>([^<]*)<\/name>/.exec(body);
    const su = /<styleUrl>#([^<]+)<\/styleUrl>/.exec(body);
    const de = /<description>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/description>/.exec(body);
    let desc = de ? de[1] : '';
    desc = desc.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim().slice(0, 250);
    let color = '#cfd8dc';
    if (su) {
      if (styleColor[su[1]]) color = styleColor[su[1]];
      else { const mm = /-([0-9a-fA-F]{8})-/.exec(su[1]); if (mm) color = hexFromAABBGGRR(mm[1].toLowerCase()); }
    }
    const name = nm ? nm[1].replace(/&amp;/g, '&').replace(/&#39;/g, "'").trim() : '';
    const lname = 'بدون طبقة';
    if (!layers.includes(lname)) layers.push(lname);
    points.push({ id: points.length, n: name.slice(0, 120), la: Math.round(lat * 1e5) / 1e5, lo: Math.round(lon * 1e5) / 1e5, l: lname, c: color, d: desc });
  }
  return { layers, points };
}

function sigOf(points) { // cheap hash over sorted coords+names
  let h1 = 0x811c9dc5 >>> 0;
  const s = points.map(p => p.la + ',' + p.lo + '|' + p.n).sort().join(';');
  for (let i = 0; i < s.length; i++) { h1 ^= s.charCodeAt(i); h1 = Math.imul(h1, 0x01000193) >>> 0; }
  return ('00000000' + h1.toString(16)).slice(-8) + '-' + points.length;
}

async function pullFresh() {
  const ctrl = new AbortController(); const timer = setTimeout(() => ctrl.abort(), 15000);
  let xml = '';
  try {
    const r = await fetch('https://www.google.com/maps/d/kml?mid=' + MID + '&forcekml=1', { signal: ctrl.signal, headers: { 'User-Agent': 'Mozilla/5.0 (compatible; MapziBot/1.0)' } });
    if (!r.ok) throw new Error('kml http ' + r.status);
    xml = await r.text();
  } finally { clearTimeout(timer); }
  if (!xml || xml.indexOf('<kml') === -1) throw new Error('bad kml payload');
  const parsed = parseKml(xml);
  if (!parsed.points.length) throw new Error('no points parsed');
  return parsed;
}

export default async function (req) {
  const url = new URL(req.url);
  const action = url.searchParams.get('action') || 'get';

  // GET latest snapshot from archive repo (or raw fallback if no token)
  if (action === 'get') {
    let data = null;
    if (TOKEN) { const cur = await ghRead('mapdata.json'); if (cur) { try { data = JSON.parse(cur.content); } catch {} } }
    if (!data) { try { const r = await fetch(RAW + 'mapdata.json?cb=' + Date.now(), { cache: 'no-store' }); if (r.ok) data = await r.json(); } catch {} }
    if (!data) return json({ error: 'no data yet' }, 503);
    return json(data);
  }

  // REFRESH: pull KML, compare signature, commit on change
  if (action === 'refresh') {
    if (!TOKEN) return json({ error: 'no token configured' }, 500);
    try {
      const fresh = await pullFresh();
      const sig = sigOf(fresh.points);
      const out = { v: 1, mapName: 'Yemen War 🇾🇪', sig, pulledAt: new Date().toISOString(), layers: fresh.layers, points: fresh.points };
      let changed = true;
      const cur = await ghRead('mapdata.json');
      if (cur) { try { const old = JSON.parse(cur.content); if (old.sig === sig) changed = false; } catch {} }
      if (changed) {
        const ok = await ghWrite('mapdata.json', JSON.stringify(out), 'mapzi: refresh ' + sig + ' @ ' + out.pulledAt);
        return json({ ok, changed: true, count: fresh.points.length, sig, committed: ok });
      }
      return json({ ok: true, changed: false, count: fresh.points.length, sig });
    } catch (e) { return json({ error: String(e.message || e) }, 502); }
  }

  return json({ error: 'unknown action' }, 400);
}
