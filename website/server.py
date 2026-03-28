"""Simple dev server for the DictateMe website with download routes."""
import http.server
import os
import sys

PORT = 8080
SITE_DIR = os.path.dirname(os.path.abspath(__file__))
# Point to Tauri build output
RELEASE_DIR = os.path.join(SITE_DIR, "..", "app", "src-tauri", "target", "release", "bundle")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/download/"):
            self.handle_download()
        else:
            super().do_GET()

    def handle_download(self):
        platform = self.path.split("/download/")[-1].strip("/").lower()

        # Map platform to installer files
        files = {
            "windows": self._find_file(["nsis", "msi"], [".exe", ".msi"]),
            "macos": self._find_file(["dmg", "macos"], [".dmg"]),
            "linux": self._find_file(["deb", "appimage"], [".deb", ".AppImage"]),
        }

        installer = files.get(platform)
        if installer and os.path.isfile(installer):
            self.send_response(200)
            filename = os.path.basename(installer)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(os.path.getsize(installer)))
            self.end_headers()
            with open(installer, "rb") as f:
                self.wfile.write(f.read())
        else:
            # No build yet - show a friendly page
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Download DictateMe for {platform.title()}</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #0E0E12; color: #F2F0ED;
       display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
.card {{ background: #1C1C23; border: 1px solid #25252D; border-radius: 16px;
         padding: 48px; max-width: 480px; text-align: center; }}
h2 {{ color: #FFBA08; margin-bottom: 16px; }}
p {{ color: #9A9AA6; line-height: 1.6; margin-bottom: 24px; }}
code {{ background: #252530; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }}
a {{ color: #FFBA08; }}
</style></head><body>
<div class="card">
<h2>DictateMe for {platform.title()}</h2>
<p>The installer hasn't been built yet for this platform. To build it locally:</p>
<p><code>cd app/src-tauri && cargo tauri build</code></p>
<p>Or grab the source from <a href="https://github.com/kristerus/dictateme">GitHub</a>.</p>
<p><a href="/">&larr; Back to homepage</a></p>
</div></body></html>"""
            self.wfile.write(html.encode())

    def _find_file(self, subdirs, extensions):
        """Search release bundle directories for an installer file."""
        for subdir in subdirs:
            dirpath = os.path.join(RELEASE_DIR, subdir)
            if os.path.isdir(dirpath):
                for f in os.listdir(dirpath):
                    for ext in extensions:
                        if f.endswith(ext):
                            return os.path.join(dirpath, f)
        return None


if __name__ == "__main__":
    print(f"Serving DictateMe website at http://localhost:{PORT}")
    print(f"Download routes: /download/windows, /download/macos, /download/linux")
    server = http.server.HTTPServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
