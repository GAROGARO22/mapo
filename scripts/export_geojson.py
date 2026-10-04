"""تصدير المعالم من PostGIS إلى GeoJSON لاستخدام الواجهة الويب."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_config import get_connection  # noqa: E402

OUTPUT = os.path.join("web", "data.geojson")


def export_to_geojson():
    print("🔄 جاري استخراج البيانات من PostGIS إلى صيغة GeoJSON...")
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT jsonb_build_object(
        'type',     'FeatureCollection',
        'features', COALESCE(jsonb_agg(features.feature), '[]'::jsonb)
    )
    FROM (
      SELECT jsonb_build_object(
        'type',       'Feature',
        'id',         f.id,
        'geometry',   ST_AsGeoJSON(f.geom)::jsonb,
        'properties', jsonb_build_object(
            'name',        f.name,
            'description', f.description,
            'folder_id',   f.folder_id,
            'folder_name', fo.name,
            'layer_path',  f.properties ->> 'layer_path',
            'icon_url',    s.icon_url,
            'icon_color',  s.icon_color,
            'line_color',  s.line_color,
            'poly_color',  s.poly_color,
            'line_width',  s.line_width,
            'country_code', f.country_code
        )
      ) AS feature
      FROM features f
      LEFT JOIN folders fo ON f.folder_id = fo.id
      LEFT JOIN styles  s  ON f.style_id  = s.id
      ORDER BY f.id
    ) features;
    """
    cursor.execute(query)
    geojson_data = cursor.fetchone()[0]

    if not os.path.exists("web"):
        os.makedirs("web")
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(geojson_data, fh, ensure_ascii=False, separators=(",", ":"))

    n = len(geojson_data.get("features", []))
    size_mb = os.path.getsize(OUTPUT) / 1e6
    print(f"✅ تم إنشاء الملف: {OUTPUT} ({n} معلماً، {size_mb:.1f} MB)")
    cursor.close()
    conn.close()


if __name__ == "__main__":
    export_to_geojson()
