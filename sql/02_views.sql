-- =====================================================
-- 02_views.sql — عناوين جاهزة للتصدير والاستعلام
-- (تُنفَّذ بعد 01_init_db.sql، آمنة للتكرار)
-- =====================================================

-- عرض الأنماط الكاملة لكل معلم (هندسة + نمط + طبقة)
CREATE OR REPLACE VIEW v_features_full AS
SELECT
    f.id,
    f.name,
    f.description,
    f.folder_id,
    fo.name            AS folder_name,
    s.style_key,
    s.icon_url,
    s.icon_color,
    s.line_color,
    s.line_width,
    s.poly_color,
    ST_AsText(f.geom)  AS geom_wkt,
    GeometryType(f.geom) AS geom_type
FROM features f
LEFT JOIN folders fo ON f.folder_id = fo.id
LEFT JOIN styles  s  ON f.style_id  = s.id;

-- إحصاءات سريعة لكل طبقة (عدد المعالم وأنواعها)
CREATE OR REPLACE VIEW v_layer_stats AS
SELECT
    fo.id              AS folder_id,
    fo.name            AS layer_name,
    COUNT(f.id)        AS feature_count,

FROM folders fo
LEFT JOIN features f ON f.folder_id = fo.id
GROUP BY fo.id, fo.name
ORDER BY feature_count DESC;

