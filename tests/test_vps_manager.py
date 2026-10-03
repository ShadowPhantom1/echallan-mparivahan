"""Run with: python3 -m unittest discover -s tests -p 'test_vps_manager.py'."""

import functools
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import vps_manager as manager


class SettingsTests(unittest.TestCase):
    def test_ports(self):
        self.assertEqual(manager.parse_port("8080"), 8080)
        self.assertEqual(manager.parse_port("65535"), 65535)
        for value in ["80", "65536", "zero", "8080.5", True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                manager.parse_port(value)

    def test_addresses(self):
        self.assertEqual(manager.parse_ip(""), "")
        self.assertEqual(manager.parse_ip("203.0.113.10"), "203.0.113.10")
        for value in ["http://203.0.113.10", "localhost", "127.0.0.1", "0.0.0.0", "224.0.0.1"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                manager.parse_ip(value)

    def test_missing_build(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                manager.validate_site(manager.Settings(webroot=directory))

    def test_source_project_is_not_a_webroot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("website", encoding="utf-8")
            (root / "package.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                manager.validate_site(manager.Settings(webroot=directory))

    def test_index_cannot_point_outside_webroot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "dist"
            root.mkdir()
            (root.parent / "private.html").write_text("private", encoding="utf-8")
            try:
                (root / "index.html").symlink_to(root.parent / "private.html")
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable on this platform")
            with self.assertRaises(ValueError):
                manager.validate_site(manager.Settings(webroot=str(root)))

    def test_systemd_paths_are_quoted(self):
        self.assertEqual(manager.systemd_quote('/srv/site 100%'), '"/srv/site 100%%"')
        with self.assertRaises(ValueError):
            manager.systemd_quote("/srv/site\nExecStart=other")


class HostingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "dist"
        self.root.mkdir()
        (self.root / "index.html").write_text("<h1>Independent preview</h1>", encoding="utf-8")
        (self.root / "styles.css").write_text("body { color: white; }", encoding="utf-8")
        (self.root / ".env").write_text("private", encoding="utf-8")
        (self.root / "app.apk").write_bytes(b"not a release")
        (self.root / "folder").mkdir()
        (self.root.parent / "secret.txt").write_text("private", encoding="utf-8")
        handler = functools.partial(manager.PreviewHandler, directory=str(self.root))
        self.server = manager.PreviewServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temporary.cleanup()

    def request(self, path, method="GET"):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_index_and_headers(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Independent preview", body)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_health(self):
        status, _, body = self.request("/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["mode"], "independent-preview")

    def test_head_does_not_send_body(self):
        status, headers, body = self.request("/", method="HEAD")
        self.assertEqual(status, 200)
        self.assertTrue(int(headers["Content-Length"]) > 0)
        self.assertEqual(body, b"")

    def test_static_file(self):
        status, headers, body = self.request("/styles.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers["Content-Type"])
        self.assertIn(b"white", body)

    def test_spa_route(self):
        status, _, body = self.request("/app/details")
        self.assertEqual(status, 200)
        self.assertIn(b"Independent preview", body)

    def test_apk_publishing_disabled(self):
        status, _, body = self.request("/app.apk")
        self.assertEqual(status, 403)
        self.assertIn(b"APK publishing is disabled", body)

    def test_no_directory_listing(self):
        self.assertEqual(self.request("/folder/")[0], 404)

    def test_private_paths_blocked(self):
        for path in ["/.env", "/%2e%2e/secret.txt", "/folder/%2e%2e/secret.txt", "/a%00b"]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 403)

    def test_symlink_cannot_escape_root(self):
        link = self.root / "outside.txt"
        try:
            link.symlink_to(self.root.parent / "secret.txt")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable on this platform")
        self.assertEqual(self.request("/outside.txt")[0], 403)

    def test_index_symlink_is_rejected_on_every_route(self):
        (self.root / "index.html").unlink()
        outside = self.root.parent / "private.html"
        outside.write_text("private", encoding="utf-8")
        try:
            (self.root / "index.html").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable on this platform")
        self.assertEqual(self.request("/")[0], 403)
        self.assertEqual(self.request("/app/details")[0], 403)

    def test_missing_asset_is_not_html(self):
        status, headers, _ = self.request("/missing.js")
        self.assertEqual(status, 404)
        self.assertIn("application/json", headers["Content-Type"])


if __name__ == "__main__":
    unittest.main()