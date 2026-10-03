#!/usr/bin/env python3
"""Two-menu VPS host for the independent website preview. Python 3.9+."""

import argparse
import functools
import ipaddress
import json
import mimetypes
import os
import re
import signal
import socket
import sys
import tempfile
import threading
import urllib.request
from dataclasses import asdict, dataclass, replace
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".vps-host"
CONFIG_PATH = STATE / "settings.json"
SERVICE_PATH = STATE / "website-preview.service"
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

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
        super().end_headers()

    def json_response(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        return None

    def send_head(self):
        try:
            raw_path = unquote(urlsplit(self.path).path, errors="strict")
        except (ValueError, UnicodeError):
            return self.json_response(400, {"error": "Invalid request path."})
        parts = [part for part in raw_path.split("/") if part]
        if "\x00" in raw_path or "\\" in raw_path or any(part.startswith(".") for part in parts):
            return self.json_response(403, {"error": "This path is not public."})
        if raw_path == "/healthz":
            return self.json_response(200, {"status": "ok", "mode": "independent-preview"})
        # Allow APK serving for /app.apk if file exists in webroot (for rotation automation)
        if raw_path == "/app.apk":
            apk_path = root / "app.apk"
            print(f"[DEBUG] APK request: path={apk_path}, exists={apk_path.is_file()}, ext_ok={apk_path.suffix.lower() in ALLOWED_EXTENSIONS}", flush=True)
            if apk_path.is_file() and apk_path.suffix.lower() in ALLOWED_EXTENSIONS:
                try:
                    handle = apk_path.open("rb")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.android.package-archive")
                    self.send_header("Content-Length", str(os.fstat(handle.fileno()).st_size))
                    self.end_headers()
                    print(f"[DEBUG] APK headers sent, returning handle", flush=True)
                    return handle
                except OSError as e:
                    print(f"[DEBUG] OSError opening APK: {e}", flush=True)
                    pass
            return self.json_response(404, {"error": "APK not found."})
        if Path(raw_path).suffix.lower() == ".apk":
            return self.json_response(403, {
                "error": "APK publishing is disabled on this preview host. "
                "Use accurate app branding and a verified release before distribution."
            })

        root = Path(self.directory).resolve()
        candidate = root.joinpath(*parts)
        if not parts or (not candidate.exists() and not candidate.suffix):
            candidate = root / "index.html"
        candidate = candidate.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return self.json_response(403, {"error": "This path is not public."})
        if candidate.suffix.lower() not in ALLOWED_EXTENSIONS or not candidate.is_file():
            return self.json_response(404, {"error": "File not found."})
        try:
            handle = candidate.open("rb")
        except OSError:
            return self.json_response(404, {"error": "File not found."})
        try:
            self.send_response(200)
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            if candidate.suffix.lower() in {".html", ".css", ".js", ".mjs", ".txt"}:
                content_type += "; charset=utf-8"
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(os.fstat(handle.fileno()).st_size))
            self.end_headers()
            return handle
        except BaseException:
            handle.close()
            raise

    def list_directory(self, path):
        return self.json_response(403, {"error": "Directory listing is disabled."})

    def log_request(self, code="-", size="-"):
        # Do not log query strings, cookies, or any account credentials.
        path = self.path.split("?", 1)[0]
        print(f"{self.client_address[0]} {self.command} {ascii(path)} {code}", flush=True)


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 32

    def __init__(self, address, handler):
        self.slots = threading.BoundedSemaphore(24)
        super().__init__(address, handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(20)
        return connection, address

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def handle_error(self, request, address):
        print(f"Request from {address[0]} ended before completion.", file=sys.stderr, flush=True)


def detect_public_ip():
    """Attempt to detect the VPS public IPv4 address with a short timeout."""
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    for url in services:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=1.5) as response:
                ip_str = response.read().decode("utf-8").strip()
                addr = ipaddress.IPv4Address(ip_str)
                if not (addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast):
                    return str(addr)
        except Exception:
            continue
    return ""


def detect_local_ip():
    """Detect primary local outbound IPv4 address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return ""


def print_addresses(settings):
    public = settings.public_ip or detect_public_ip()
    local = detect_local_ip()

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
    print("  • Phone se kholne ke liye:")
    print(f"    1. Apne phone browser mein upar diya gaya URL ({primary_url or f'http://YOUR_VPS_IP:{settings.port}'}) dalein.")
    print(f"    2. Agar load na ho toh VPS firewall mein port allow karein:")
    print(f"       sudo ufw allow {settings.port}/tcp")
    print("=" * 68 + "\n")


def serve(settings):
    root = validate_site(settings)
    handler = functools.partial(PreviewHandler, directory=str(root))
    try:
        server = PreviewServer(("0.0.0.0", settings.port), handler)
    except OSError as error:
        raise ValueError(f"Cannot listen on port {settings.port}: {error}. Choose a free port in Setup.") from error
    def stop_server(_signum, _frame):
        raise KeyboardInterrupt

    previous_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, stop_server)
    try:
        print_addresses(settings)
        print("Keep this process running. Ctrl+C stops it. Use systemd for background hosting.\n")
        with server:
            server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nWebsite stopped.")
    finally:
        server.server_close()
        signal.signal(signal.SIGTERM, previous_handler)


def systemd_quote(value):
    value = str(value)
    if any(character in value for character in "\x00\r\n$"):
        raise ValueError("Systemd paths cannot contain control characters or dollar signs.")
    return '"' + value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"') + '"'


def create_service(settings):
    if sys.platform != "linux":
        print("Optional systemd setup is available on Linux only.")
        return
    import pwd
    user = pwd.getpwuid(os.getuid()).pw_name
    if os.getuid() == 0:
        print("Run Setup as a non-root user to generate a least-privilege service.")
        return
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", user):
        raise ValueError("Cannot safely generate a service for this username.")
    executable = systemd_quote(sys.executable)
    script = systemd_quote(ROOT / "vps_manager.py")
    webroot = systemd_quote(settings.webroot)
    public_argument = " --public-ip " + settings.public_ip if settings.public_ip else ""
    unit = f"""[Unit]
Description=Independent Website Preview
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
WorkingDirectory={systemd_quote(ROOT)}
ExecStart={executable} {script} --serve --port {settings.port} --webroot {webroot}{public_argument}
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
UMask=0077

[Install]
WantedBy=multi-user.target
"""
    save_private_file(SERVICE_PATH, unit)
    print(f"\nOptional background service saved at {SERVICE_PATH}")
    print("See VPS_SETUP.md for installation. No sudo command was run automatically.")


def prompt_value(label, default, parser):
    while True:
        answer = input(f"{label} [{default or 'not set'}]: ").strip()
        try:
            return parser(answer if answer else default)
        except ValueError as error:
            print(error)


def setup(settings):
    print("\nSETUP: website preview hosting")
    print("No passwords, Telegram OTPs, API hashes or session files are requested.")
    port = prompt_value("Port", settings.port, parse_port)
    address = prompt_value("VPS IPv4 address (display URL only; blank keeps current)", settings.public_ip, parse_ip)
    webroot = prompt_value("Built website directory", settings.webroot, resolve_webroot)
    updated = Settings(port=port, public_ip=address, webroot=str(webroot))
    save_private_file(CONFIG_PATH, json.dumps(asdict(updated), indent=2) + "\n")
    print("\nSettings saved. They take effect next time the server starts.")
    try:
        validate_site(updated)
        print("Website build found.")
    except ValueError as error:
        print(f"Build not ready: {error}")
    if input("Generate optional systemd background-service file? [y/N]: ").strip().lower() == "y":
        create_service(updated)
    print_addresses(updated)
    return updated


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
            settings = replace(settings, port=parse_port(args.port))
        if args.public_ip is not None:
            settings = replace(settings, public_ip=parse_ip(args.public_ip))
        if args.webroot is not None:
            settings = replace(settings, webroot=str(resolve_webroot(args.webroot)))
        if args.check:
            root = validate_site(settings)
            print(f"Build ready: {root}")
            print_addresses(settings)
            return 0
        if args.serve:
            serve(settings)
            return 0
        if args.setup:
            setup(settings)
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
                    settings = setup(settings)
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