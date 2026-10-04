/* MAPZI — وضع "Google My Maps": عرض خريطة جوجل المضمّنة للقراءة فقط.
 * الحماية: sandbox يمنع أي تفاعل كتابي/تعديل + منع القائمة اليمنى + شفافية معقّمة.
 */
(function () {
  const GMAPS_URL = 'https://www.google.com/maps/d/embed?mid=1NZygQ5FhCvHG3ZH6Ddk3lbzAwnJum8M&ehbc=2E312F';

  function buildView() {
    // حاوية iframe تغطي منطقة الخريطة (تحت اللوحة الجانبية)
    const wrap = document.createElement('div');
    wrap.id = 'gmaps-wrap';
    wrap.hidden = true;

    const frame = document.createElement('iframe');
    frame.id = 'gmaps-frame';
    frame.title = 'خريطة MAPZI على Google My Maps';
    frame.src = GMAPS_URL;
    frame.allowFullscreen = false;
    // Sandbox: بدون forms/scripts-top/downloads → الزائر مشاهد فقط ولا يستطيع التعديل أو النسخ
    frame.setAttribute('sandbox', 'allow-same-origin allow-scripts');
    frame.setAttribute('referrerpolicy', 'no-referrer-when-downgrade');
    frame.loading = 'lazy';

    const shield = document.createElement('div');
    shield.id = 'gmaps-shield';
    shield.title = 'وضع المشاهدة فقط';

    const note = document.createElement('div');
    note.id = 'gmaps-note';
    note.textContent = '👁️ وضع المشاهدة فقط — النقر والسحب داخل الخريطة يعملان، والنسخ/التعديل ممنوع.';

    wrap.append(frame, shield, note);
    document.body.appendChild(wrap);
  }

  function setMode(mode) {
    const leafletEl = document.getElementById('map');
    const wrap = document.getElementById('gmaps-wrap');
    if (!wrap) return;
    const gmaps = mode === 'gmaps';
    wrap.hidden = !gmaps;
    leafletEl.style.visibility = gmaps ? 'hidden' : 'visible';
    // إيقاف أحداث Leaflet أثناء وضع جوجل
    if (window.MAPZI_MAP) {
      try { gmaps ? window.MAPZI_MAP.pm && window.MAPZI_MAP.pm.disableDraw() : null; } catch (e) {}
    }
    btnG.className = gmaps ? 'mode-btn active' : 'mode-btn';
    btnL.className = gmaps ? 'mode-btn' : 'mode-btn active';
    panel.disabled = gmaps;
  }

  let btnG, btnL, panel;

  function init() {
    buildView();
    panel = document.getElementById('panel');

    // شريط تبديل الوضع أعلى اللوحة
    const bar = document.createElement('div');
    bar.className = 'mode-bar';
    btnL = document.createElement('button');
    btnL.type = 'button';
    btnL.className = 'mode-btn active';
    btnL.textContent = '🗺️ خريطة MAPZI';
    btnG = document.createElement('button');
    btnG.type = 'button';
    btnG.className = 'mode-btn';
    btnG.textContent = '🟦 خريطة جوجل';
    bar.append(btnL, btnG);
    panel.prepend(bar);

    btnL.addEventListener('click', () => setMode('leaflet'));
    btnG.addEventListener('click', () => setMode('gmaps'));

    // حماية إضافية: منع قائمة الفأرة اليمنى فوق الـ iframe ومنع تحديد النص حوله
    ['contextmenu'].forEach(ev =>
      document.getElementById('gmaps-wrap').addEventListener(ev, e => e.preventDefault()));

    window.MAPZI_SET_MODE = setMode; // للاستخدام من أزرار أخرى لاحقاً
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();