/* MAPZI — الخريطة التفاعلية (المرحلة 2: طبقات + بحث) */

const map = L.map('map', { preferCanvas: true }).setView([15.5527, 48.5164], 6);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors | MAPZI'
}).addTo(map);

// تحليل ألوان KML (صيغة Google: aabbggrr)
function parseKmlStyle(kmlColor, defaultHex = '#3388ff') {
    if (!kmlColor) return { hex: defaultHex, opacity: 0.5 };
    let clean = String(kmlColor).replace('#', '').trim();
    if (clean.length === 8) {
        const a = (parseInt(clean.substring(0, 2), 16) / 255).toFixed(2);
        const b = clean.substring(2, 4), g = clean.substring(4, 6), r = clean.substring(6, 8);
        return { hex: `#${r}${g}${b}`, opacity: parseFloat(a) };
    }
    return { hex: defaultHex, opacity: 0.5 };
}


function safeHex(hex, fallback) {
    return /^#[0-9a-fA-F]{6}$/.test(hex) ? hex : fallback;
}

                }
            },
            clearSelection() { selLayer.clearLayers(); },
            fitAll() {
                const b = L.latLngBounds([]);
                data.features.forEach(f => flattenGeom(f).forEach(g => {
                    if (g.type === 'Point') b.extend([g.coordinates[1], g.coordinates[0]]);
                    else if (g.type === 'LineString') g.coordinates.forEach(c => b.extend([c[1], c[0]]));
                    else g.coordinates.forEach(r => r.forEach(c => b.extend([c[1], c[0]])));
                }));
                if (b.isValid()) map.fitBounds(b);
            }
        };

        if (window.MAPZI_ON_DATA) window.MAPZI_ON_DATA(api);
    })
    .catch(err => console.error('حدث خطأ في تحميل البيانات:', err));