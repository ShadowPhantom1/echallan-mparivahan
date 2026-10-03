#!/usr/bin/env python3
"""Minimal test server using http.server directly."""

from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, unquote
import signal
import sys
import traceback

DIST = Path('/home/aakash/parivahan-app/dist').resolve()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            print(f'Request: {self.path}', flush=True)
            try:
                raw_path = unquote(urlsplit(self.path).path)
            except Exception:
                self.send_error(400)
                return
            
            if raw_path == '/healthz':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
                return
            
            if raw_path == '/app.apk':
                apk = DIST / 'app.apk'
                if apk.is_file():
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/vnd.android.package-archive')
                    self.send_header('Content-Length', str(apk.stat().st_size))
                    self.end_headers()
                    with open(apk, 'rb') as f:
                        self.wfile.write(f.read())
                    return
                self.send_error(404)
                return
            
            # Default: index.html
            index = DIST / 'index.html'
            if index.is_file():
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(index.stat().st_size))
                self.end_headers()
                self.wfile.write(index.read_bytes())
                return
            
            self.send_error(404)
            
        except Exception as e:
            print(f"Error handling request {self.path}: {e}", flush=True)
            traceback.print_exc()
            self.send_error(500)

    def log_message(self, format, *args):
        print(f'{self.address_string()} - {format % args}', flush=True)

def signal_handler(sig, frame):
    print('Shutting down...', flush=True)
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f'DIST: {DIST}', flush=True)
    print(f'index.html: {(DIST/"index.html").exists()}', flush=True)
    print(f'app.apk: {(DIST/"app.apk").exists()}', flush=True)
    print(f'app.apk size: {(DIST/"app.apk").stat().st_size if (DIST/"app.apk").exists() else "N/A"}', flush=True)
    server = HTTPServer(('0.0.0.0', 8080), Handler)
    print('Server starting on 8080...', flush=True)
    try:
        server.serve_forever()
    except Exception as e:
        print(f"Server error: {e}", flush=True)
        traceback.print_exc()