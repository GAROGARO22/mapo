-- =====================================================
-- 05_supabase.sql — تهيئة قاعدة Supabase كاملة للمشروع
-- =====================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- 1) جدول الأنماط (الألوان والأيقونات القادمة من KML)
CREATE TABLE IF NOT EXISTS styles (
    id SERIAL PRIMARY KEY,
    style_key VARCHAR(150) UNIQUE NOT NULL,
    icon_url TEXT,
    icon_scale NUMERIC(4,2) DEFAULT 1.0,
    icon_color VARCHAR(20),
    line_color VARCHAR(20),
    line_width NUMERIC(5,2) DEFAULT 1.0,
    poly_color VARCHAR(20),
    balloon_text TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2) جدول الطبقات بهيكل شجري (مطابق لـ Google My Maps)
CREATE TABLE IF NOT EXISTS folders (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_folders_name_parent UNIQUE (name, parent_id)
);

-- 3) جدول المعالم المكاني الرئيسي (نقاط + خطوط + مضلعات)
CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    style_id INTEGER REFERENCES styles(id) ON DELETE SET NULL,
    name VARCHAR(255),
    description TEXT,
    geom GEOMETRY(Geometry, 4326) NOT NULL,
    properties JSONB DEFAULT '{}'::jsonb,
    country_code CHAR(2),
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE features ADD COLUMN IF NOT EXISTS country_code CHAR(2);

-- 4) الفهارس (مكانية + نصية + ربط)
CREATE INDEX IF NOT EXISTS idx_features_geom        ON features USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_features_folder_id   ON features (folder_id);
CREATE INDEX IF NOT EXISTS idx_features_style_id    ON features (style_id);
CREATE INDEX IF NOT EXISTS idx_features_properties  ON features USING GIN (properties);
CREATE INDEX IF NOT EXISTS idx_features_country     ON features (country_code);

-- فهرس بحث نصي (trigram)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_features_name_trgm
                 ON features USING GIN (coalesce(name,'''') gin_trgm_ops)';
    END IF;
END $$;

-- 5) دالة تصنيف المعالم حسب الدولة (صناديق حدود تقريبية)
CREATE OR REPLACE FUNCTION fn_assign_countries() RETURNS integer AS $$
DECLARE updated integer;
BEGIN
    UPDATE features f SET country_code = c.code
    FROM (VALUES
        ('SY', ST_MakeEnvelope(35.6, 32.3, 42.4, 37.4, 4326)),
        ('YE', ST_MakeEnvelope(42.5, 12.5, 54.5, 19.0, 4326)),
        ('UA', ST_MakeEnvelope(22.0, 44.0, 40.5, 52.5, 4326)),
        ('AF', ST_MakeEnvelope(60.4, 29.3, 75.1, 38.6, 4326)),
        ('LY', ST_MakeEnvelope(9.3, 19.5, 25.3, 33.2, 4326)),
        ('IQ', ST_MakeEnvelope(38.7, 29.0, 48.8, 37.4, 4326)),
        ('PS', ST_MakeEnvelope(34.1, 29.3, 35.9, 33.4, 4326)),
        ('SA', ST_MakeEnvelope(34.4, 16.3, 55.8, 32.2, 4326)),
        ('LB', ST_MakeEnvelope(35.0, 33.0, 36.7, 34.8, 4326)),
        ('JO', ST_MakeEnvelope(34.9, 29.1, 39.4, 33.5, 4326))
    ) AS c(code, env)
    WHERE ST_Centroid(f.geom) && c.env
      AND ST_Contains(c.env, ST_Centroid(f.geom))
      AND (f.country_code IS DISTINCT FROM c.code);
    GET DIAGNOSTICS updated = ROW_COUNT;
    RETURN updated;
END; $$ LANGUAGE plpgsql;

-- 6) العروض الجاهزة
CREATE OR REPLACE VIEW v_features_full AS
SELECT f.id, f.name, f.description, f.folder_id, fo.name AS folder_name,
       f.country_code, GeometryType(f.geom) AS geom_type,
       ST_AsGeoJSON(f.geom)::jsonb AS geojson,
       s.icon_url, s.icon_color, s.line_color, s.line_width, s.poly_color,
       f.properties->>'layer_path' AS layer_path
FROM features f
LEFT JOIN folders fo ON f.folder_id = fo.id
LEFT JOIN styles  s  ON f.style_id  = s.id;

CREATE OR REPLACE VIEW v_layer_stats AS
SELECT fo.id AS folder_id, fo.name AS layer_name, COUNT(f.id) AS feature_count,
       COUNT(*) FILTER (WHERE GeometryType(f.geom) = 'POINT') AS points,
       COUNT(*) FILTER (WHERE GeometryType(f.geom) = 'LINESTRING') AS lines,
       COUNT(*) FILTER (WHERE GeometryType(f.geom) IN ('POLYGON','MULTIPOLYGON')) AS polygons
FROM folders fo LEFT JOIN features f ON f.folder_id = fo.id
GROUP BY fo.id, fo.name ORDER BY feature_count DESC;

-- 7) حماية الصفوف: قراءة عامة فقط
ALTER TABLE features ENABLE ROW LEVEL SECURITY;
ALTER TABLE folders  ENABLE ROW LEVEL SECURITY;
ALTER TABLE styles   ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "public_read" ON features;
CREATE POLICY "public_read" ON features FOR SELECT USING (true);
DROP POLICY IF EXISTS "public_read" ON folders;
CREATE POLICY "public_read" ON folders FOR SELECT USING (true);
DROP POLICY IF EXISTS "public_read" ON styles;
CREATE POLICY "public_read" ON styles FOR SELECT USING (true);