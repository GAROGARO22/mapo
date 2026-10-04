/* MAPZI — إعدادات مصدر البيانات */
window.MAPZI_CONFIG = {
  // الملف الساكن (fallback مضمون — موجود دائماً على Vercel)
  staticDataUrl: 'data.geojson',

  // الـ API الحيّ المنشور على نفس دومين الموقع (نسبي = يعمل تلقائياً على الإنتاج والمحلي)
  liveApiUrl: '/api/features',

  // true = جرّب الـ API أولاً، وإن فشل ارجع تلقائياً للملف الساكن
  preferLive: true
};