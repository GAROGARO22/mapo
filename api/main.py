"""MAPZI API — FastAPI app for Vercel Serverless.

Endpoints:
  GET /api/health   -> {"ok": true, "service": "mapzi-api"}
  GET /api/layers   -> list of layers with counts (from Supabase view v_layer_stats)
  GET /api/features -> GeoJSON FeatureCollection with filters (bbox/layer/country/q/limit)

Env vars (Vercel Project Settings -> Environment Variables):
  SUPABASE_URL      = https://<project-ref>.supabase.co
  SUPABASE_ANON_KEY = anon public key ONLY (never service_role in this layer)

If Supabase is not configured or unreachable, endpoints fall back to serving the
static file web/data.geojson so the site never breaks.
"""
import json
import os
import urllib.parse
import urllib.request

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MAPZI API", version="0.3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

_HERE = os.path.dirname(os.path.abspath(__file__))
_STATIC_GEOJSON = os.path.join(_HERE, "..", "web", "data.geojson")


def _pg(path: str, params: dict) -> list:
    """Simple GET query against Supabase PostgREST."""
    url = f"{SUPABASE_URL}/rest/v1/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def _fallback_geojson() -> dict:
    try:
        with open(_STATIC_GEOJSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"type": "FeatureCollection", "features": []}


@app.get("/api/health")
def health():
    return {"ok": True, "service": "mapzi-api", "supabase": bool(SUPABASE_URL and ANON_KEY)}


@app.get("/api/layers")
def layers():
    if SUPABASE_URL and ANON_KEY:
        try:
            return {"layers": _pg("v_layer_stats", {"select": "*"}), "source": "supabase"}
        except Exception as e:
            print("[api] layers supabase failed:", e)
    # fallback: compute from static geojson
    data = _fallback_geojson()
    counts = {}
    for ft in data.get("features", []):
        name = (ft.get("properties") or {}).get("folder_name") or "Uncategorized"
        counts[name] = counts.get(name, 0) + 1
    rows = [{"layer_name": k, "feature_count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    return {"layers": rows, "source": "static"}


@app.get("/api/features")
def features(
    bbox: str = Query(None, description="lon_min,lat_min,lon_max,lat_max"),
    layer: str = Query(None, description="folder_name"),
    country: str = Query(None, description="ISO code, e.g. YE"),
    q: str = Query(None, description="text search on name"),
    limit: int = Query(2000, le=10000),
):
    if SUPABASE_URL and ANON_KEY:
        try:
            params = {"select": "*", "limit": limit}
            if country:
                params["country_code"] = f"eq.{country.upper()}"
            if layer:
                params["folder_name"] = f"eq.{layer}"
            if q:
                params["name"] = f"ilike.*{q}*"
            if bbox:
                try:
                    x1, y1, x2, y2 = [float(v) for v in bbox.split(",")]
                    params["geom"] = (f"srid=4326,and(gt.POLYGON(({x1} {y1},{x2} {y1},"
                                      f"{x2} {y2},{x1} {y2},{x1} {y1})))")
                except ValueError:
                    pass
            rows = _pg("v_features_full", params)
            feats = []
            for r in rows:
                gj = r.get("geojson") or {}
                if isinstance(gj, str):
                    gj = json.loads(gj)
                feats.append({
                    "type": "Feature",
                    "geometry": gj,
                    "properties": {
                        "id": r.get("id"), "name": r.get("name"), "description": r.get("description"),
                        "folder_name": r.get("folder_name"), "layer_path": r.get("layer_path"),
                        "country_code": r.get("country_code"), "geom_type": r.get("geom_type"),
                        "icon_url": r.get("icon_url"), "icon_color": r.get("icon_color"),
                        "line_color": r.get("line_color"), "line_width": r.get("line_width"),
                        "poly_color": r.get("poly_color"),
                    },
                })
            return {"type": "FeatureCollection", "features": feats, "source": "supabase"}
        except Exception as e:
            print("[api] features supabase failed:", e)
    # fallback: filter static geojson in memory
    data = _fallback_geojson()
    out = []
    minx = miny = maxx = maxy = None
    if bbox:
        try:
            minx, miny, maxx, maxy = [float(v) for v in bbox.split(",")]
        except ValueError:
            minx = None
    ql = (q or "").lower()
    for ft in data.get("features", []):
        p = ft.get("properties") or {}
        if country and (p.get("country_code") or "").upper() != country.upper():
            continue
        if layer and p.get("folder_name") != layer:
            continue
        if ql and ql not in (p.get("name") or "").lower():
            continue
        if minx is not None:
            g = ft.get("geometry") or {}
            coords = []
            def collect(c):
                if isinstance(c, (list, tuple)):
                    if c and isinstance(c[0], (int, float)) and len(c) >= 2:
                        coords.append((c[0], c[1]))
                    else:
                        for x in c:
                            collect(x)
            collect(g.get("coordinates", []))
            if not any(minx <= x <= maxx and miny <= y <= maxy for x, y in coords):
                continue
        out.append(ft)
        if len(out) >= limit:
            break
    return {"type": "FeatureCollection", "features": out, "source": "static"}