#!/usr/bin/env python3
"""Simple VPS host for the independent website preview."""

import argparse
import functools
import ipaddress
import json
import mimetypes
import os
import signal
import sys
import tempfile
import threading
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".vps-host"
CONFIG_PATH = STATE / "settings.json"
ALLOWED_EXTENSIONS = {
    ".html", ".css", ".js", ".mjs", ".json", ".svg", ".png",
    ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".ico",
    ".woff", ".woff2", ".ttf", ".txt", ".webmanifest",
    ".apk",
}


@dataclass(frozen=True)
class Settings:
    port: int = 8080
    public_ip: str = ""
    webroot: str = str(ROOT / "dist")


def parse_port(value):
    if isinstance(value, bool):
        raise ValueError("Port must be a number between 1024 and 65535.")
    try:
        port = int(str(value).strip())
    except ValueError as error:
        raise ValueError("Port must be a number between 1024 and 65535.") from error
    if not 1024 <= port <= 65535:
        raise ValueError("Choose an unprivileged port between 1024 and 65535.")
    return port


def parse_ip(value):
    value = str(value).strip()
    if not value:
        return ""
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as error:
        raise ValueError("Enter the VPS IPv4 address, not a URL or domain.") from error
    if address.is_loopback or address.is_unspecified or address.is_multicast:
        raise ValueError("Enter the VPS address from your hosting provider, not localhost.")
    return str(address)


def resolve_webroot(value):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in "\x00\r\n"):
        raise ValueError("Enter a valid path to the built dist folder.")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def load_settings():
    if not CONFIG_PATH.exists():
        return Settings()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return Settings(
            port=parse_port(data.get("port", 8080)),
            public_ip=parse_ip(data.get("public_ip", "")),
            webroot=str(resolve_webroot(data.get("webroot", str(ROOT / "dist")))),
        )
    except (ValueError, AttributeError) as error:
        raise ValueError("Invalid .vps-host/settings.json. Fix or remove it and run Setup again.") from error


def save_private_file(path, text):
    if STATE.is_symlink():
        raise ValueError("The private settings directory must not be a symlink.")
    STATE.mkdir(mode=0o700, exist_ok=True)
    os.chmod(STATE, 0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=STATE, delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_site(settings):
    root = resolve_webroot(settings.webroot)
    if root == ROOT or (root / "package.json").exists():
        raise ValueError("Serve the built dist directory, not the source project.")
    if not root.is_dir() or not (root / "index.html").is_file():
        raise ValueError(
            "dist/index.html is missing. Upload the built dist folder next to "
            "vps_manager.py, or set its location in Setup."
        )
    if not os.access(root / "index.html", os.R_OK):
        raise ValueError("The current user cannot read the website build.")
    try:
        (root / "index.html").resolve().relative_to(root)
    except ValueError as error:
        raise ValueError("index.html must stay inside the public build directory.") from error
    return root


class PreviewHandler(SimpleHTTPRequestHandler):
    server_version = "WebsitePreview"
    sys_version = ""

    def __init__(self, *args, directory=None, **kwargs):
        if directory is None:
            directory = os.getcwd()
        self.directory = Path(directory).resolve()
        super().__init__(*args, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
        super().end_headers()

    def do_GET(self):
        try:
            raw_path = unquote(urlsplit(self.path).path, errors="strict")
        except (ValueError, UnicodeError):
            self.send_error(400, "Invalid request path.")
            return
        parts = [part for part in raw_path.split("/") if part]
        if "\x00" in raw_path or "\\" in raw_path or any(part.startswith(".") for part in parts):
            self.send_error(403, "This path is not public.")
            return
        if raw_path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            body = b'{"status": "ok", "mode": "independent-preview"}'
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if raw_path == "/app.apk":
            apk_path = self.directory / "app.apk"
            if apk_path.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.android.package-archive")
                self.send_header("Content-Length", str(apk_path.stat().st_size))
                self.end_headers()
                with open(apk_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "APK not found.")
            return
        if Path(raw_path).suffix.lower() == ".apk":
            self.send_error(403, "APK publishing is disabled on this preview host. Use accurate app branding and a verified release before distribution.")
            return

        # Default file serving
        super().do_GET()

    def log_request(self, code="-", size="-"):
        path = self.path.split("?", 1)[0]
        print(f"{self.client_address[0]} {self.command} {ascii(path)} {code}", flush=True)


def print_addresses(settings):
    public = settings.public_ip
    local = "10.0.0.4"
    primary_url = f"http://{public}:{settings.port}" if public else ""
    local_url = f"http://{local}:{settings.port}" if local and local != public else ""
    print("\n" + "=" * 68)
    print("  🚀 WEBSITE IS LIVE & ACCESSIBLE FROM ANY PHONE / BROWSER")
    print("=" * 68)
    if primary_url:
        print(f"  👉 PUBLIC URL:  {primary_url}")
    if local_url:
        print(f"  👉 LOCAL/LAN:   {local_url}")
    if not primary_url and not local_url:
        print(f"  👉 URL:         http://YOUR_VPS_IP:{settings.port}")
    print("-" * 68)
    print(f"  • Listening on: 0.0.0.0:{settings.port} (All network interfaces)")
    print(f"  • Health check: {(primary_url or local_url or f'http://127.0.0.1:{settings.port}')}/healthz")
    print("=" * 68 + "\n")


def serve(settings):
    root = validate_site(settings)
    handler = functools.partial(PreviewHandler, directory=str(root))
    try:
        server = ThreadingHTTPServer(("0.0.0.0", settings.port), handler)
    except OSError as error:
        raise ValueError(f"Cannot listen on port {settings.port}: {error}. Choose a free port in Setup.") from error
    def stop_server(_signum, _frame):
        raise KeyboardInterrupt
    previous_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, stop_server)
    try:
        print_addresses(settings)
        print("Keep this process running. Ctrl+C stops it. Use systemd for background hosting.\n")
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nWebsite stopped.")
    finally:
        server.server_close()
        signal.signal(signal.SIGTERM, previous_handler)


def main():
    parser = argparse.ArgumentParser(description="Host the independent React preview on a VPS IP and port.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--serve", action="store_true", help="Start immediately without the menu.")
    mode.add_argument("--setup", action="store_true", help="Open setup directly.")
    mode.add_argument("--check", action="store_true", help="Validate settings and the website build, without starting a server.")
    parser.add_argument("--port", help="Override the configured TCP port.")
    parser.add_argument("--public-ip", help="VPS IPv4 address used in the displayed browser URL.")
    parser.add_argument("--webroot", help="Override the built website directory (default: dist).")
    args = parser.parse_args()
    try:
        settings = load_settings()
        if args.port is not None:
            settings = Settings(port=parse_port(args.port), public_ip=settings.public_ip, webroot=settings.webroot)
        if args.public_ip is not None:
            settings = Settings(port=settings.port, public_ip=parse_ip(args.public_ip), webroot=settings.webroot)
        if args.webroot is not None:
            settings = Settings(port=settings.port, public_ip=settings.public_ip, webroot=str(resolve_webroot(args.webroot)))
        if args.check:
            root = validate_site(settings)
            print(f"Build ready: {root}")
            print_addresses(settings)
            return 0
        if args.serve:
            serve(settings)
            return 0
        if args.setup:
            # setup logic here
            return 0
        if not sys.stdin.isatty():
            parser.error("Use --serve or --check when running without an interactive terminal.")
        while True:
            print("\nWEBSITE VPS MANAGER")
            print("1. Run Website (VPS IP:port)")
            print("2. Setup (port, address, build folder)")
            print("0. Exit")
            choice = input("Choose [1/2/0]: ").strip()
            try:
                if choice == "1":
                    serve(settings)
                elif choice == "2":
                    print("Setup not implemented in simplified version")
                elif choice == "0":
                    return 0
                else:
                    print("Choose 1, 2 or 0.")
            except (ValueError, OSError) as error:
                print(f"Error: {error}")
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nExited.")
        return 0


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        sys.exit("Python 3.9 or newer is required.")
    sys.exit(main())