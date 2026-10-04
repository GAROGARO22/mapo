"""مزامنة ملف KML (Google My Maps) إلى قاعدة بيانات PostGIS.

الإصلاحات في هذه النسخة:
- دعم MultiGeometry والحلقات الداخلية للمضلعات (innerBoundaryIs).
- حفظ اسم الطبقة/المسار الهرمي لكل معلم (folder_name + layer_path).
- معاملة واحدة: عند أي خطأ لا تُفقد البيانات القديمة (بدل TRUNCATE التدميري).
- الاتصال الموحّد عبر db_config.get_connection().
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json

from lxml import etree
from shapely.geometry import Point, LineString, Polygon, shape
from shapely.wkt import dumps
from shapely.validation import make_valid

from db_config import get_connection

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
        # خلط أنواع الهندسات داخل MultiGeometry واحد -> GeometryCollection
        gc = {
            "type": "GeometryCollection",
            "geometries": [g.__geo_interface__ for g in geoms],
        }
        geom = shape(gc)
    if not geom.is_valid:
        geom = make_valid(geom)
    return dumps(geom)


def load_styles(root, cursor):
    """استخراج Styles/StyleMap وإرجاع قاموس style_key -> id."""
    style_map = {}
    print("🎨 جاري استخراج الألوان والأيقونات الأساسية...")
    for style in root.findall(".//kml:Style", NS):
        style_key = style.get("id")
        if not style_key:
            continue
        icon_url = icon_color = line_color = poly_color = None
        icon_scale, line_width = 1.0, 1.0

        icon_style = style.find("kml:IconStyle", NS)
        if icon_style is not None:
            href = icon_style.find(".//kml:href", NS)
            icon_url = href.text if href is not None else None
            color_elem = icon_style.find("kml:color", NS)
            if color_elem is not None:
                icon_color = color_elem.text
            scale_elem = icon_style.find("kml:scale", NS)
            if scale_elem is not None:
                try:
                    icon_scale = float(scale_elem.text)
                except (TypeError, ValueError):
                    pass

        line_style = style.find("kml:LineStyle", NS)
        if line_style is not None:
            lc = line_style.find("kml:color", NS)
            if lc is not None:
                line_color = lc.text
            lw = line_style.find("kml:width", NS)
            if lw is not None:
                try:
                    line_width = float(lw.text)
                except (TypeError, ValueError):
                    pass

        poly_style = style.find("kml:PolyStyle", NS)
        if poly_style is not None:
            pc = poly_style.find("kml:color", NS)
            if pc is not None:
                poly_color = pc.text

        cursor.execute(
            """
            INSERT INTO styles (style_key, icon_url, icon_color, icon_scale, line_color, line_width, poly_color)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (style_key) DO UPDATE SET
                icon_url = EXCLUDED.icon_url, icon_color = EXCLUDED.icon_color,
                line_color = EXCLUDED.line_color, poly_color = EXCLUDED.poly_color,
                line_width = EXCLUDED.line_width, icon_scale = EXCLUDED.icon_scale
            RETURNING id;
            """,
            (style_key, icon_url, icon_color, icon_scale, line_color, line_width, poly_color),
        )
        style_map[style_key] = cursor.fetchone()[0]

    print("🔗 جاري معالجة روابط أنماط Google My Maps (StyleMap)...")
    for style_map_elem in root.findall(".//kml:StyleMap", NS):
        map_key = style_map_elem.get("id")
        if not map_key:
            continue
        for pair in style_map_elem.findall("kml:Pair", NS):
            if pair.findtext("kml:key", namespaces=NS) == "normal":
                normal_url = pair.findtext("kml:styleUrl", namespaces=NS)
                if normal_url:
                    normal_key = normal_url.replace("#", "")
                    if normal_key in style_map:
                        style_map[map_key] = style_map[normal_key]
                break
    return style_map


def upsert_folder(name, parent_id, cursor, cache):
    """إنشاء/تحديث مجلد مع تجنّب التكرار داخل نفس التشغيل."""
    key = (name, parent_id)
    if key in cache:
        return cache[key]
    cursor.execute(
        """
        INSERT INTO folders (name, parent_id) VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id;
        """,
        (name, parent_id),
    )
    row = cursor.fetchone()
    if row:
        folder_id = row[0]
    else:
        cursor.execute(
            "SELECT id FROM folders WHERE name = %s AND parent_id IS NOT DISTINCT FROM %s LIMIT 1;",
            (name, parent_id),
        )
        folder_id = cursor.fetchone()[0]
    cache[key] = folder_id
    return folder_id


def process_folder(folder_elem, parent_id, path, cursor, style_map, folder_cache, stats):
    folder_name = folder_elem.findtext("kml:name", default="بدون اسم", namespaces=NS)
    folder_id = upsert_folder(folder_name, parent_id, cursor, folder_cache)
    folder_path = f"{path}/{folder_name}" if path else folder_name

    for pm in folder_elem.findall("kml:Placemark", NS):
        name = pm.findtext("kml:name", default="", namespaces=NS)
        desc = pm.findtext("kml:description", default="", namespaces=NS) or ""
        style_url = (pm.findtext("kml:styleUrl", default="", namespaces=NS) or "").replace("#", "")
        style_id = style_map.get(style_url)

        geom_wkt = geometry_from_placemark(pm)
        if not geom_wkt:
            stats["skipped"] += 1
            continue

        props = {"folder_name": folder_name, "layer_path": folder_path}
        cursor.execute(
            """
            INSERT INTO features (folder_id, style_id, name, description, geom, properties)
            VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s::jsonb);
            """,
            (folder_id, style_id, name, desc, geom_wkt, json.dumps(props, ensure_ascii=False)),
        )
        stats["inserted"] += 1

    for sub in folder_elem.findall("kml:Folder", NS):
        process_folder(sub, folder_id, folder_path, cursor, style_map, folder_cache, stats)


def sync_kml_to_db():
    if not os.path.exists(KML_FILE):
        print(f"❌ ملف KML غير موجود: {KML_FILE}")
        return 1

    print("🔄 جاري قراءة ملف KML...")
    root = etree.parse(KML_FILE).getroot()

    conn = get_connection()
    try:
        with conn:  # معاملة واحدة: أي استثناء → rollback تلقائي والبيانات القديمة آمنة
            cursor = conn.cursor()
            style_map = load_styles(root, cursor)

            print("📂 جاري معالجة المعالم المكانية وربطها بالطبقات والأنماط...")
            # حذف القديم داخل المعاملة نفسها (يُسترد تلقائياً عند الخطأ)
            cursor.execute("DELETE FROM features;")
            cursor.execute("DELETE FROM folders;")

            folder_cache = {}
            stats = {"inserted": 0, "skipped": 0}

            document = root.find("kml:Document", NS) or root.find("kml:kml", NS) or root
            # مجلدات مباشرة تحت Document
            for folder in document.findall("kml:Folder", NS):
                process_folder(folder, None, "", cursor, style_map, folder_cache, stats)
            # Placemarks خارج مجلدات (مباشرة تحت Document)
            for pm in document.findall("kml:Placemark", NS):
                name = pm.findtext("kml:name", default="", namespaces=NS)
                desc = pm.findtext("kml:description", default="", namespaces=NS) or ""
                style_url = (pm.findtext("kml:styleUrl", default="", namespaces=NS) or "").replace("#", "")
                geom_wkt = geometry_from_placemark(pm)
                if geom_wkt:
                    cursor.execute(
                        """
                        INSERT INTO features (folder_id, style_id, name, description, geom, properties)
                        VALUES (NULL, %s, %s, %s, ST_GeomFromText(%s, 4326), '{"folder_name": null}'::jsonb);
                        """,
                        (style_map.get(style_url), name, desc, geom_wkt),
                    )
                    stats["inserted"] += 1
                else:
                    stats["skipped"] += 1

            print(f"✅ اكتملت المزامنة: {stats['inserted']} معلماً، تم تخطي {stats['skipped']} (بلا هندسة صالحة)")

            # تنظيم البيانات حسب الدولة (يتطلب sql/04_organization.sql منفَّذاً)
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'fn_assign_countries');")
            if cursor.fetchone()[0]:
                cursor.execute("SELECT fn_assign_countries();")
                print(f"🌍 تصنيف المعالم حسب الدولة: {cursor.fetchone()[0]} سطراً محدَّثاً")
            else:
                print("⚠️  دالة fn_assign_countries غير موجودة — نفّذ sql/04_organization.sql لتنظيم البيانات حسب الدولة")
    except Exception as exc:
        print(f"❌ فشل أثناء المزامنة — تم التراجع (rollback) والبيانات السابقة لم تتأثر: {exc}")
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(sync_kml_to_db())
