"""خادم تطوير محلي لملفات web/ مع gzip وCORS ونوع MIME الصحيح للـ GeoJSON.

الاستخدام:  python serve.py [المنفذ]   ثم افتح  http://localhost:8000
"""
import gzip
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class MapziHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".geojson": "application/geo+json",
        ".json": "application/json",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        # كاش قصير الأمد بدل تعطيل الكاش كلياً بـ ?t=Timestamp
        self.send_header("Cache-Control", "public, max-age=60")
        super().end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        gz_path = path + ".gz"
        # خدمة نسخة gzip جاهزة إن كانت أحدث من الأصل
        if (
            "gzip" in self.headers.get("Accept-Encoding", "")
            and os.path.isfile(gz_path)
            and os.path.getmtime(gz_path) >= os.path.getmtime(path)
        ):
            with open(gz_path, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return None
        return super().send_head()


def build_gzip():
    for name in os.listdir(WEB_DIR):
        src = os.path.join(WEB_DIR, name)
        if os.path.isfile(src) and name.endswith((".geojson", ".js", ".css", ".html")):
            dst = src + ".gz"
            if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
                with open(src, "rb") as fin, gzip.open(dst, "wb", compresslevel=9) as fout:
                    fout.write(fin.read())
                saved = 1 - os.path.getsize(dst) / os.path.getsize(src)
                print(f"🗜️  {name}: ضغط بنسبة {saved:.0%}")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    build_gzip()
    httpd = ThreadingHTTPServer(("localhost", port), MapziHandler)
    print(f"🗺️  MAPZI يعمل على  http://localhost:{port}  (Ctrl+C للإيقاف)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:

