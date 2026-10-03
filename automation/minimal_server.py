#!/usr/bin/env python3
"""Minimal test server."""

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

class TestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        if directory is None:
            directory = os.getcwd()
        self.directory = Path(directory).resolve()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        print(f'[DEBUG] Request: {self.path}', flush=True)
        try:
            raw_path = unquote(urlsplit(self.path).path, errors='strict')
        except (ValueError, UnicodeError):
            self.send_error(400)
            return
        
        if raw_path == '/healthz':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            body = b'{"status": "ok"}'
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        
        if raw_path == '/app.apk':
            apk_path = self.directory / 'app.apk'
            if apk_path.is_file():
                self.send_response(200)
                self.send_header('Content-Type', 'application/vnd.android.package-archive')
                self.send_header('Content-Length', str(apk_path.stat().st_size))
                self.end_headers()
                with open(apk_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404)
            return
        
        # Serve index.html for everything else
        candidate = self.directory / 'index.html'
        if candidate.is_file():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(candidate.stat().st_size))
            self.end_headers()
            with open(candidate, 'rb') as f:
                self.wfile.write(f.read())
            return
        
        self.send_error(404)

webroot = Path('/home/aakash/parivahan-app/dist').resolve()
print(f'Webroot: {webroot}', flush=True)
print(f'index.html: {(webroot / "index.html").exists()}', flush=True)
print(f'app.apk: {(webroot / "app.apk").exists()}', flush=True)

handler = lambda *args, **kwargs: TestHandler(*args, directory=str(webroot), **kwargs)
server = ThreadingHTTPServer(('0.0.0.0', 8080), handler)
print('Server starting on 8080...', flush=True)
server.serve_forever()