-- =====================================================
-- 03_update_style.sql — أمثلة على تعديل ألوان الطبقات من داخل pgAdmin
-- (تنفيذ آمن: UPDATE + SELECT للتحقق، ثم ROLLBACK أو COMMIT)
-- =====================================================

-- 🔍 أولاً: تأكد من اسم الطبقة كما هو مخزّن في جدول folders
SELECT id, name FROM folders WHERE name ILIKE '%marib%' OR name ILIKE '%مأرب%' OR name ILIKE '%ma%rib%';

-- 🎨 ثانياً: اجعل كل معالم طبقة "Marib" خضراء (نقاط + خطوط + مضلعات)
BEGIN;

UPDATE styles
SET icon_color = '#00FF00FF',      -- KML: AABBGGRR → أخضر غير شفاف
    line_color = '#00FF00FF',
    poly_color = '#6600FF00'       -- 40% شفافية للأخضر في التعبئة
WHERE style_key IN (
    SELECT s.style_key
    FROM features f
    JOIN folders fo ON f.folder_id = fo.id
    JOIN styles  s  ON f.style_id  = s.id
    WHERE fo.name ILIKE '%marib%'   -- عدّل الاسم حسب نتيجة الاستعلام الأول
);

-- ✅ تحقق قبل الحفظ
SELECT fo.name AS layer, s.style_key, s.icon_color, s.line_color, s.poly_color, COUNT(f.id) AS cnt
FROM features f
JOIN folders fo ON f.folder_id = fo.id
JOIN styles  s  ON f.style_id  = s.id
WHERE fo.name ILIKE '%marib%'
GROUP BY 1,2,3,4,5;

COMMIT;     -- احفظ التغييرات (أو اكتب ROLLBACK; للتراجع عنها)

-- 💡 ملاحظة: بعد أي تعديل ألوان هنا يجب إعادة التصدير ليظهر التغيير في الخريطة:
--    py scripts/export_geojson.py

-- =====================================================
-- أمثلة تعديل ألوان الطبقات (من 03_update_style.sql السابق)
-- تنفيذ آمن: UPDATE + SELECT للتحقق، ثم COMMIT أو ROLLBACK
-- =====================================================

-- 🔍 تأكد من اسم الطبقة كما هو مخزّن:
-- SELECT id, name FROM folders WHERE name ILIKE '%marib%' OR name ILIKE '%مأرب%';

-- 🎨 اجعل كل معالم طبقة "Marib" خضراء (KML صيغة AABBGGRR):
-- BEGIN;
-- UPDATE styles SET icon_color='#00FF00FF', line_color='#00FF00FF', poly_color='#6600FF00'
-- WHERE style_key IN (
--   SELECT s.style_key FROM features f
--   JOIN folders fo ON f.folder_id = fo.id
--   JOIN styles  s  ON f.style_id  = s.id
--   WHERE fo.name ILIKE '%marib%');
-- COMMIT;   -- أو ROLLBACK; للتراجع
-- ⚠️ بعد أي تعديل ألوان أعد التصدير: py scripts/export_geojson.py
