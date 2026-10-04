/**
 * تعقيم HTML لأوصاف المعالم القادمة من KML (حماية XSS).
 * يسمح بوسوم تنسيق آمنة فقط، ويزيل المعالجات/event handlers وأي وسوم خطر.
 */
const ALLOWED_TAGS = new Set([
  "A", "B", "STRONG", "I", "EM", "U", "BR", "P", "DIV", "SPAN",
  "UL", "OL", "LI", "H1", "H2", "H3", "H4", "IMG", "TABLE", "TR", "TD", "TH", "TBODY",
]);

const ALLOWED_ATTRS = {
  A: ["href", "title", "target", "rel"],
  IMG: ["src", "alt", "title", "width", "height"],
};

function isSafeUrl(url, tag) {
  if (!url) return false;
  const u = url.trim().toLowerCase();
  if (u.startsWith("data:image/")) return tag === "IMG"; // صور مضمّنة فقط للـ img
  return u.startsWith("http://") || u.startsWith("https://") || u.startsWith("mailto:") || u.startsWith("/");
}

/** تعقيم سلسلة HTML وإرجاع سلسلة آمنة للحقن في DOM. */
function sanitizeHtml(dirty) {
  if (!dirty) return "";
  const doc = new DOMParser().parseFromString(String(dirty), "text/html");

  doc.querySelectorAll("script, style, iframe, object, embed, form, link, meta, svg, math").forEach((el) => el.remove());

  const walk = (node) => {
    [...node.children].forEach((el) => {
      if (!ALLOWED_TAGS.has(el.tagName)) {
        // استبدال الوسم غير المسموح بمحتواه النصي
        el.replaceWith(...el.childNodes);
        return;
      }
      [...el.attributes].forEach((attr) => {
        const name = attr.name.toLowerCase();
        const allowedList = ALLOWED_ATTRS[el.tagName] || [];
        if (name.startsWith("on") || !allowedList.includes(name) || !isSafeUrl(attr.value, el.tagName)) {
          el.removeAttribute(attr.name);
        }
      });
      if (el.tagName === "A") {
        el.setAttribute("rel", "noopener noreferrer");
        el.setAttribute("target", "_blank");
      }
      walk(el);
    });
  };

  walk(doc.body);
  return doc.body.innerHTML;
}

/** تعقيم رابط أيقونة للاستخدام داخل CSS mask-image — يقبل https فقط. */
function safeIconUrl(url) {
  if (!url) return null;
  const u = String(url).trim();
  return u.startsWith("https://") ? u : null;
