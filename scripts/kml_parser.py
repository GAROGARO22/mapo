"""قارئ KML مستقل (Google My Maps) — بدون أي اتصال بقاعدة بيانات.

نسخة نظيفة من منطق sync_kml.py تُستخدم لتوليد SQL مباشرة في Supabase SQL Editor.
الاستخدام المباشر للفحص:  py scripts/kml_parser.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json

from lxml import etree
from shapely.geometry import Point, LineString, Polygon, shape
from shapely.wkt import dumps
from shapely.validation import make_valid

KML_FILE = os.environ.get("KML_FILE", "data/kml/map.kml")
NS = {"kml": "http://www.opengis.net/kml/2.2"}


def _coords_to_tuples(coords_text):
    """تحويل نص <coordinates> إلى قائمة نقاط (lon, lat)."""
    pts = []
    for chunk in coords_text.strip().split():
        parts = chunk.split(",")
        if len(parts) >= 2:
            try:
                pts.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return pts


def parse_polygon(poly_elem):
    """قراءة Polygon مع outer/inner boundaries وإرجاع Shapely Polygon أو None."""
    outer_elem = poly_elem.find("kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", NS)
    if outer_elem is None or not (outer_elem.text or "").strip():
        return None
    shell = _coords_to_tuples(outer_elem.text)
    if len(shell) < 4:
        return None
    holes = []
    for hole_elem in poly_elem.findall("kml:innerBoundaryIs/kml:LinearRing/kml:coordinates", NS):
        if hole_elem.text and hole_elem.text.strip():
            ring = _coords_to_tuples(hole_elem.text)
            if len(ring) >= 4:
                holes.append(ring)
    try:
        return Polygon(shell, holes)
    except Exception:
        return None


def geometry_from_placemark(pm):
    """استخراج هندسة Shapely من Placemark (يدعم MultiGeometry)."""
    multi = pm.find("kml:MultiGeometry", NS)
    container = multi if multi is not None else pm
    geoms = []

    point_elem = container.find("kml:Point/kml:coordinates", NS)
    if point_elem is not None and (point_elem.text or "").strip():
        pts = _coords_to_tuples(point_elem.text)
        if pts:
            geoms.append(Point(pts[0]))

    line_elem = container.find("kml:LineString/kml:coordinates", NS)
    if line_elem is not None and (line_elem.text or "").strip():
        pts = _coords_to_tuples(line_elem.text)
        if len(pts) >= 2:
            geoms.append(LineString(pts))

    polys = [p for p in (parse_polygon(el) for el in container.findall("kml:Polygon", NS)) if p is not None]
    if polys:
        if len(polys) == 1 and not geoms:
            return dumps(polys[0])
        geoms.extend(polys)

    if not geoms:
        return None
    if len(geoms) == 1:
        geom = geoms[0]
    else:
        gc = {
            "type": "GeometryCollection",
            "geometries": [g.__geo_interface__ for g in geoms],
        }
        geom = shape(gc)
    if not geom.is_valid:
        geom = make_valid(geom)
    return dumps(geom)


def load_styles(root):
    """استخراج Styles/StyleMap نقياً — إرجاع (style_rows, style_index)."""
    style_rows, style_index = [], {}
    for style in root.findall(".//kml:Style", NS):
        key = style.get("id")
        if not key or key in style_index:
            continue
        icon_url = icon_color = line_color = poly_color = None
        icon_scale, line_width = 1.0, 1.0
        icon_style = style.find("kml:IconStyle", NS)
        if icon_style is not None:
            href = icon_style.find(".//kml:href", NS)
            icon_url = href.text if href is not None else None
            c = icon_style.find("kml:color", NS)
            if c is not None:
                icon_color = c.text
            s = icon_style.find("kml:scale", NS)
            if s is not None:
                try:
                    icon_scale = float(s.text)
                except (TypeError, ValueError):
                    pass
        ls = style.find("kml:LineStyle", NS)
        if ls is not None:
            lc = ls.find("kml:color", NS)
            if lc is not None:
                line_color = lc.text
            lw = ls.find("kml:width", NS)
            if lw is not None:
                try:
                    line_width = float(lw.text)
                except (TypeError, ValueError):
                    pass
        ps = style.find("kml:PolyStyle", NS)
        if ps is not None:
            pc = ps.find("kml:color", NS)
            if pc is not None:
                poly_color = pc.text
        style_index[key] = len(style_rows) + 1  # id متوقع = ترتيب الإدراج (SERIAL يبدأ من 1)
        style_rows.append(dict(key=key, icon_url=icon_url, icon_color=icon_color,
                               icon_scale=icon_scale, line_color=line_color,
                               line_width=line_width, poly_color=poly_color))
    for sm in root.findall(".//kml:StyleMap", NS):
        map_key = sm.get("id")
        if not map_key or map_key in style_index:
            continue
        for pair in sm.findall("kml:Pair", NS):
            if pair.findtext("kml:key", namespaces=NS) == "normal":
                normal_url = pair.findtext("kml:styleUrl", namespaces=NS)
                if normal_url and normal_url.replace("#", "") in style_index:
                    style_index[map_key] = style_index[normal_url.replace("#", "")]
                break
    return style_rows, style_index


def upsert_folder(name, parent_id, cache):
    """توليد معرّف متسلسل للمجلدات بدون قاعدة بيانات."""
    key = (name, parent_id)
    if key not in cache:
        cache[key] = len(cache) + 1
    return cache[key]


def process_folder(folder_elem, parent_id, path, style_index, folder_cache, stats):
    folder_name = folder_elem.findtext("kml:name", default="بدون اسم", namespaces=NS)
    folder_id = upsert_folder(folder_name, parent_id, folder_cache)
    folder_path = f"{path}/{folder_name}" if path else folder_name
    stats["folder_rows"].append((folder_id, folder_name, parent_id))

    for pm in folder_elem.findall("kml:Placemark", NS):
        name = pm.findtext("kml:name", default="", namespaces=NS)
        desc = pm.findtext("kml:description", default="", namespaces=NS) or ""
        style_url = (pm.findtext("kml:styleUrl", default="", namespaces=NS) or "").replace("#", "")
        style_id = style_index.get(style_url)

        geom_wkt = geometry_from_placemark(pm)
        if not geom_wkt:
            stats["skipped"] += 1
            continue

        props = {"folder_name": folder_name, "layer_path": folder_path}
        stats["feature_rows"].append((folder_id, style_id, name, desc, geom_wkt,
                                      json.dumps(props, ensure_ascii=False)))
        stats["inserted"] += 1

    for sub in folder_elem.findall("kml:Folder", NS):
        process_folder(sub, folder_id, folder_path, style_index, folder_cache, stats)


def parse_all(kml_file=None):
    """قراءة KML وإرجاع كل البيانات جاهزة للكتابة (SQL أو DB)."""
    kml_file = kml_file or KML_FILE
    if not os.path.exists(kml_file):
        raise FileNotFoundError(f"ملف KML غير موجود: {kml_file}")
    root = etree.parse(kml_file).getroot()
    style_rows, style_index = load_styles(root)
    folder_cache, stats = {}, {"inserted": 0, "skipped": 0, "folder_rows": [], "feature_rows": []}
    document = root.find("kml:Document", NS)
    if document is None:
        document = root
    for folder in document.findall("kml:Folder", NS):
        process_folder(folder, None, "", style_index, folder_cache, stats)
    for pm in document.findall("kml:Placemark", NS):
        name = pm.findtext("kml:name", default="", namespaces=NS)
        desc = pm.findtext("kml:description", default="", namespaces=NS) or ""
        style_url = (pm.findtext("kml:styleUrl", default="", namespaces=NS) or "").replace("#", "")
        geom_wkt = geometry_from_placemark(pm)
        if geom_wkt:
            stats["feature_rows"].append((None, style_index.get(style_url), name, desc, geom_wkt, "{}"))
            stats["inserted"] += 1
        else:
            stats["skipped"] += 1
    return dict(styles=style_rows, folders=stats["folder_rows"], features=stats["feature_rows"],
                skipped=stats["skipped"])


if __name__ == "__main__":
    d = parse_all()
    print(f"✅ قراءة ناجحة: {len(d['styles'])} نمطاً، {len(d['folders'])} مجلداً، "
          f"{len(d['features'])} معلماً، تخطي {d['skipped']}")