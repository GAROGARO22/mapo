-- مسح الجداول إذا كانت موجودة مسبقاً (مفيد عند إعادة التهيئة)
DROP TABLE IF EXISTS features CASCADE;
DROP TABLE IF EXISTS folders CASCADE;
DROP TABLE IF EXISTS styles CASCADE;

-- 1. جدول الأنماط والتنسيقات (Styles)
-- مخصص لتخزين الألوان، الرموز، وأحجام الخطوط من ملف KML
CREATE TABLE styles (
    id SERIAL PRIMARY KEY,
    style_key VARCHAR(150) UNIQUE NOT NULL,
    icon_url TEXT,
    icon_scale NUMERIC(4,2) DEFAULT 1.0,
    icon_color VARCHAR(20),
    line_color VARCHAR(20),
    line_width NUMERIC(5,2) DEFAULT 1.0,
    poly_color VARCHAR(20),
    balloon_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. جدول المجلدات والطبقات (Folders / Layers)
-- يحاكي الهيكلية الشجرية للطبقات الموجودة في KML
CREATE TABLE folders (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    -- قيد فريد لمنع تكرار الطبقة نفسها تحت نفس الأب (تعديل واحد فقط)
    CONSTRAINT uq_folders_name_parent UNIQUE (name, parent_id),
    parent_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. جدول المعالم المكانية الرئيسي (Placemarks)
-- يحتوي على العمود الهندسي المرن الذي يقبل (نقاط، خطوط، مضلعات)
CREATE TABLE features (
    id SERIAL PRIMARY KEY,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    style_id INTEGER REFERENCES styles(id) ON DELETE SET NULL,
    name VARCHAR(255),
    description TEXT,
    CONSTRAINT uq_folders_name_parent UNIQUE (name, parent_id),
    geom GEOMETRY(Geometry, 4326) NOT NULL,
    properties JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. إنشاء الفهارس (Indexes)
-- الفهرس المكاني (GiST) ضروري جداً لتسريع عرض الخريطة واستعلامات التقاطع
CREATE INDEX idx_features_geom ON features USING GIST (geom);
CREATE INDEX idx_features_folder_id ON features (folder_id);
CREATE INDEX idx_features_style_id ON features (style_id);
CREATE INDEX idx_features_properties ON features USING GIN (properties);