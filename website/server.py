"""Dev server for the DictateMe website with direct download routes.

Serves installers from two locations (first match wins):
  1. website/downloads/  — manually placed or downloaded from CI
  2. app/src-tauri/target/release/bundle/  — local Tauri build output
"""
import http.server
import os

PORT = 8080
SITE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(SITE_DIR, "downloads")
RELEASE_DIR = os.path.join(SITE_DIR, "..", "app", "src-tauri", "target", "release", "bundle")

# Platform -> (search dirs, file extensions)
PLATFORM_MAP = {
    "windows": {
        "dirs": [
            os.path.join(DOWNLOADS_DIR, "nsis"),
            os.path.join(DOWNLOADS_DIR, "msi"),
            DOWNLOADS_DIR,
            os.path.join(RELEASE_DIR, "nsis"),
            os.path.join(RELEASE_DIR, "msi"),
        ],
        "exts": [".exe", ".msi"],
    },
    "macos": {
        "dirs": [
            os.path.join(DOWNLOADS_DIR, "dmg"),
            DOWNLOADS_DIR,
            os.path.join(RELEASE_DIR, "dmg"),
        ],
        "exts": [".dmg"],
    },
    "linux": {
        "dirs": [
            os.path.join(DOWNLOADS_DIR, "deb"),
            os.path.join(DOWNLOADS_DIR, "appimage"),
            DOWNLOADS_DIR,
            os.path.join(RELEASE_DIR, "deb"),
            os.path.join(RELEASE_DIR, "appimage"),
        ],
        "exts": [".deb", ".AppImage"],
    },
}


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
        mapping = PLATFORM_MAP.get(platform)

        if not mapping:
            self.send_error(404, "Unknown platform")
            return

        # Search for installer file
        installer = None
        for dirpath in mapping["dirs"]:
            if not os.path.isdir(dirpath):
                continue
            for f in sorted(os.listdir(dirpath), reverse=True):  # newest first
                for ext in mapping["exts"]:
                    if f.lower().endswith(ext.lower()):
                        installer = os.path.join(dirpath, f)
                        break
                if installer:
                    break
            if installer:
                break

        if installer and os.path.isfile(installer):
            self.send_response(200)
            filename = os.path.basename(installer)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(os.path.getsize(installer)))
            self.end_headers()
            with open(installer, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            names = {"windows": "Windows", "macos": "macOS", "linux": "Linux"}
            name = names.get(platform, platform)
            html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Download DictateMe for {name}</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #0E0E12; color: #F2F0ED;
       display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
.card {{ background: #1C1C23; border: 1px solid #25252D; border-radius: 16px;
         padding: 48px; max-width: 480px; text-align: center; }}
h2 {{ color: #FFBA08; margin-bottom: 16px; }}
p {{ color: #9A9AA6; line-height: 1.6; margin-bottom: 24px; }}
a {{ color: #FFBA08; }}
</style></head><body>
<div class="card">
<h2>DictateMe for {name}</h2>
<p>The {name} installer is being built. Check back shortly or build from source.</p>
<p><a href="/">&larr; Back to homepage</a></p>
</div></body></html>"""
            self.wfile.write(html.encode())


if __name__ == "__main__":
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    print(f"Serving DictateMe website at http://localhost:{PORT}")
    print(f"Download routes: /download/windows, /download/macos, /download/linux")
    print(f"Place installers in: {DOWNLOADS_DIR}")
    server = http.server.HTTPServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
