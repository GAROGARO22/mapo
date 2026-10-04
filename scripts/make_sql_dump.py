"""توليد sql/06_seed.sql من ملف KML مباشرة — بدون أي قاعدة بيانات أو اتصال.

الاستخدام:  py scripts/make_sql_dump.py
ثم انسخ محتوى sql/06_seed.sql إلى Supabase SQL Editor واضغط Run.

يعتمد على scripts/kml_parser.py (نسخة مستقلة عن sync_kml.py لا تحتاج postgres).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kml_parser as kp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "sql", "06_seed.sql")
BATCH_SIZE = 150


def q(value):
    """تهريب قيمة نصية داخل SQL."""
    if value is None:
        return "NULL"
    s = str(value)
    if "\\" in s:  # تسلسلات مثل \n و \uXXXX داخل نص KML (CDATA) — تُفكّ بأمان دون المساس بالعربية
        s = s.encode("ascii", "backslashreplace").decode("unicode-escape")
    return "'" + s.replace("'", "''") + "'"


def main():
    print("🔄 قراءة KML...")
    d = kp.parse_all()
    print(f"   {len(d['styles'])} نمطاً | {len(d['folders'])} مجلداً | {len(d['features'])} معلماً | تخطي {d['skipped']}")

    lines = [
        "-- 06_seed.sql — مُولَّد آلياً بـ make_sql_dump.py — لا تُحرّره يدوياً",
        "-- انسخه كاملاً إلى Supabase SQL Editor ثم Run",
        "BEGIN;",
        "TRUNCATE features, folders, styles RESTART IDENTITY CASCADE;",
    ]

    for st in d["styles"]:
        lines.append(
            "INSERT INTO styles(style_key,icon_url,icon_scale,icon_color,line_color,line_width,poly_color) VALUES ("
            f"{q(st['key'])},{q(st['icon_url'])},{st['icon_scale']},{q(st['icon_color'])},"
            f"{q(st['line_color'])},{st['line_width']},{q(st['poly_color'])});"
        )

    for folder_id, name, parent_id in d["folders"]:
        pid = parent_id if parent_id else "NULL"
        lines.append(f"INSERT INTO folders(id,name,parent_id) VALUES ({folder_id},{q(name)},{pid});")
    lines.append("SELECT setval(pg_get_serial_sequence('folders','id'), (SELECT MAX(id) FROM folders));")

    batch = []
    for folder_id, style_id, name, desc, wkt, props in d["features"]:
        fid = folder_id if folder_id else "NULL"
        sid = style_id if style_id else "NULL"
        batch.append(f"({fid},{sid},{q(name)},{q(desc)},ST_GeomFromText({q(wkt)},4326),{q(props)}::jsonb)")
        if len(batch) >= BATCH_SIZE:
            lines.append("INSERT INTO features(folder_id,style_id,name,description,geom,properties) VALUES\n"
                         + ",\n".join(batch) + ";")
            batch = []
    if batch:
        lines.append("INSERT INTO features(folder_id,style_id,name,description,geom,properties) VALUES\n"
                     + ",\n".join(batch) + ";")

    lines.append("SELECT fn_assign_countries();")
    lines.append("COMMIT;")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    size_mb = os.path.getsize(OUT_PATH) / 1e6
    print(f"✅ تم توليد {OUT_PATH} ({size_mb:.2f} MB، {len(d['features'])} معلماً)")
    print("👉 الخطوة التالية: افتح الملف → Ctrl+A → Ctrl+C → الصق في Supabase SQL Editor → Run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())