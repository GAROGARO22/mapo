

خريطة ويب تفاعلية مبنية على **Leaflet** مع خط بيانات **KML → PostGIS → GeoJSON**.
تُستورد طبقات Google My Maps (نقاط/خطوط/مضلعات بألوانها وأيقوناتها الأصلية) إلى
قاعدة بيانات PostGIS ثم تُصدَّر كـ GeoJSON تستهلكه الواجهة.

## هيكل المشروع

sql/             01_init_db.sql (الجداول) · 02_views.sql (عناوين v_features_full و v_layer_stats)
scripts/         db_config.py (اتصال موحّد) · sync_kml.py (KML→DB) · export_geojson.py (DB→GeoJSON)
web/             index.html · css/ · js/ (app.js + sanitize.js التعقيم) · data.geojson (ملف مُولَّد)
serve.py         خادم تطوير محلي (gzip + CORS + MIME صحيح)


## التشغيل من الصفر (Windows)
```powershell
# 1) التبعيات
pip install -r requirements.txt

# 2) إعداد قاعدة البيانات (بعد تثبيت PostgreSQL + PostGIS وتشغيل الخدمة)

& $PSQL -U postgres -d postgres -c "CREATE DATABASE gis_map;"   # مرة واحدة فقط
& $PSQL -U postgres -d gis_map -c "CREATE EXTENSION postgis;"   # مرة واحدة فقط
& $PSQL -U postgres -d gis_map -f sql/01_init_db.sql            # الجداول
& $PSQL -U postgres -d gis_map -f sql/02_views.sql              # العروض (views)

# 3) انسخ .env.example إلى .env واملأ كلمة مرور PostgreSQL الخاصة بك
copy .env.example .env

# 4) مزامنة KML إلى قاعدة البيانات ثم التصدير إلى GeoJSON
python scripts/sync_kml.py
python scripts/export_geojson.py

# 5) تشغيل الخريطة
python serve.py            # ثم افتح http://localhost:8000
