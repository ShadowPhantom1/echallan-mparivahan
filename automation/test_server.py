#!/usr/bin/env python3
"""Simple VPS host for the independent website preview."""

import os
import sys
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent

@dataclass(frozen=True)
class Settings:
    port: int = 8080
    public_ip: str = ''
    webroot: str = str(ROOT / 'dist')

ALLOWED_EXTENSIONS = {
    '.html', '.css', '.js', '.mjs', '.json', '.svg', '.png',
    '.jpg', '.jpeg', '.webp', '.gif', '.avif', '.ico',
    '.woff', '.woff2', '.ttf', '.txt', '.webmanifest',
    '.apk',
}

class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        if directory is None:
            directory = os.getcwd()
        self.directory = Path(directory).resolve()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        print(f'[DEBUG] Request: {self.path}')
        try:
            raw_path = unquote(urlsplit(self.path).path, errors='strict')
        except (ValueError, UnicodeError):
            self.send_error(400, 'Invalid request path.')
            return
        parts = [part for part in raw_path.split('/') if part]
        if '\x00' in raw_path or '\\' in raw_path or any(part.startswith('.') for part in parts):
            self.send_error(403, 'This path is not public.')
            return
        if raw_path == '/healthz':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            body = b'{"status": "ok", "mode": "independent-preview"}'
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            print('[DEBUG] healthz OK')
            return
        if raw_path == '/app.apk':
            apk_path = self.directory / 'app.apk'
            print(f'[DEBUG] APK request: {apk_path}, exists={apk_path.is_file()}, cwd={os.getcwd()}, dir={self.directory}')
            if apk_path.is_file():
                print(f'[DEBUG] APK size: {apk_path.stat().st_size}')
                try:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/vnd.android.package-archive')
                    self.send_header('Content-Length', str(apk_path.stat().st_size))
                    self.end_headers()
                    with open(apk_path, 'rb') as f:
                        self.wfile.write(f.read())
                    print('[DEBUG] APK sent successfully')
                    return
                except Exception as e:
                    print(f'[DEBUG] Error sending APK: {e}')
            self.send_error(404, 'APK not found.')
            return
        if Path(raw_path).suffix.lower() == '.apk':
            self.send_error(403, 'APK publishing is disabled...')
            return

        # For SPA: serve index.html for non-file routes
        candidate = self.directory.joinpath(*parts) if parts else self.directory / 'index.html'
        if not candidate.exists() or not candidate.is_file():
            candidate = self.directory / 'index.html'
        try:
            candidate.relative_to(self.directory)
        except ValueError:
            self.send_error(403, 'This path is not public.')
            return
        
        self.send_response(200)
        content_type = mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
        if candidate.suffix.lower() in {'.html', '.css', '.js', '.mjs', '.txt'}:
            content_type += '; charset=utf-8'
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(candidate.stat().st_size))
        self.end_headers()
        with open(candidate, 'rb') as f:
            self.wfile.write(f.read())
        print(f'[DEBUG] Served: {candidate.name}')

    def log_request(self, code='-', size='-'):
        path = self.path.split('?', 1)[0]
        print(f'{self.client_address[0]} {self.command} {ascii(path)} {code}', flush=True)

def serve():
    webroot = Path('/home/aakash/parivahan-app/dist').resolve()
    print(f'[MAIN] Webroot: {webroot}', flush=True)
    print(f'[MAIN] index.html exists: {(webroot / "index.html").exists()}', flush=True)
    print(f'[MAIN] app.apk exists: {(webroot / "app.apk").exists()}', flush=True)
    print(f'[MAIN] app.apk size: {(webroot / "app.apk").stat().st_size if (webroot / "app.apk").exists() else "N/A"}', flush=True)
    handler = lambda *args, **kwargs: PreviewHandler(*args, directory=str(webroot), **kwargs)
    server = ThreadingHTTPServer(('0.0.0.0', 8080), handler)
    print('Server starting on 8080...', flush=True)
    server.serve_forever(poll_interval=0.5)

if __name__ == '__main__':
    serve()