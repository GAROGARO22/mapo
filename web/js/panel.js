/* MAPZI — لوحة الطبقات والبحث (المرحلة 2) */
(function () {
  const panel = document.getElementById('panel');
  const searchBox = document.getElementById('search');
  const layerList = document.getElementById('layers');
  const status = document.getElementById('status');

  function esc(s) { return String(s == null ? '' : s); }

  window.MAPZI_ON_DATA = function (state) {
    const { layers, selectLayer, clearSelection, fitAll } = state;

    // حالة الأزرار السريعة
    document.getElementById('btn-fit').onclick = fitAll;
    document.getElementById('btn-all').onclick = () => {
      layers.forEach(l => l.show());
      render();
    };
    document.getElementById('btn-none').onclick = () => {
      layers.forEach(l => l.hide());
      render();
    };

    // البحث النصي
    let t = null;
    searchBox.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => {
        const q = searchBox.value.trim().toLowerCase();
        if (q.length < 2) { clearSelection(); status.textContent = ''; return; }
        const hits = featuresMatching(q);
        selectLayer(hits);
        status.textContent = `نتائج البحث: ${hits.length}`;
      }, 250);
    });

    function featuresMatching(q) {
      const out = [];
      window.MAPZI_DATA.features.forEach(f => {
        const p = f.properties || {};
        if ((p.name && p.name.toLowerCase().includes(q)) ||
            (p.folder_name && p.folder_name.toLowerCase().includes(q))) out.push(f);
      });
      return out.slice(0, 800); // حدّ أعلى للأداء
    }

    // قائمة الطبقات
    function render() {
      layerList.innerHTML = '';
      layers.forEach(l => {
        const row = document.createElement('label');
        row.className = 'layer-row' + (l.visible ? ' on' : '');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = l.visible;
        cb.addEventListener('change', () => { cb.checked ? l.show() : l.hide(); render(); });
        const dot = document.createElement('span');
        dot.className = 'dot';
        dot.style.background = l.color || '#3388ff';
        const nm = document.createElement('span');
        nm.className = 'lname';
        nm.textContent = l.name;
        const ct = document.createElement('span');
        ct.className = 'lcount';
        ct.textContent = l.count;
        row.append(cb, dot, nm, ct);
        layerList.appendChild(row);
      });
    }
    render();
    status.textContent = `${window.MAPZI_DATA.features.length} معلماً في ${layers.length} طبقة`;
  };
})();