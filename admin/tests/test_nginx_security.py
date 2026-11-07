"""Domains 보안 시험. 실제 DB · nginx · sudo 를 쓰지 않는다 (admin 폴더에서 python -m unittest tests.test_nginx_security)."""

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import DictLoader, Environment, select_autoescape


def _stub(name, **attributes):
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    sys.modules[name] = module
    return module


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_stub("app.db", user_logs_col=None, homepage_users_col=None, admin_settings_col=None)
_stub(
    "app.libs.jwt", decode_token=lambda token: {"sub": "u"} if token == "ok" else None
)
_stub("app.services.settings_service", get_nav_items_ordered=lambda: [])
_stub("system")
_stub("system.logging")
_stub("system.logging.user_log", insert_log=lambda *a, **k: None)
_stub("system.auth")
_stub(
    "system.auth.session",
    revalidate_session=lambda payload, col: (
        {"sub": "u", "role": "admin"} if payload else None
    ),
)
_stub(
    "app.routes.dependencies",
    get_current_user=lambda: {"sub": "u", "role": "admin"},
)

from app.routes import nginx_routes  # noqa: E402
from app.services import nginx_helper  # noqa: E402
from app.services.nginx_service import NginxService  # noqa: E402


class ValidationTest(unittest.TestCase):
    def test_trailing_newline_and_option_values_are_rejected(self):
        self.assertFalse(NginxService.is_valid_domain("a.example.com\n"))
        self.assertFalse(NginxService.is_valid_email("a@b.com\n"))
        self.assertFalse(NginxService.is_valid_email("-x@b.com"))
        self.assertFalse(NginxService.is_valid_port("٣"))
        self.assertFalse(NginxService.is_valid_port("80\n"))

    def test_console_rejects_bad_values(self):
        for action, data in (
            ("add", {"domain": "a.com\nb", "email": "a@b.com", "port": "1"}),
            ("add", {"domain": "a.com", "email": "-a@b.com", "port": "1"}),
            ("add", {"domain": "a.com", "email": "a@b.com", "port": "1", "path": "/;"}),
            ("delete", {"domain": ["a.com"]}),
            ("rename", {"old_domain": "a.com", "new_domain": "x", "email": "a@b.com"}),
        ):
            self.assertIsNotNone(nginx_routes._invalid_console_input(action, data))

    def test_new_block_overwrites_forwarded_headers(self):
        block = nginx_helper.location_block("/", "1")
        self.assertIn("X-Forwarded-For $remote_addr", block)
        self.assertNotIn("sudo", Path(nginx_routes.__file__).read_text())
        self.assertFalse((ROOT / "app" / "scripts").exists())


class ConsoleTest(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(nginx_routes.router)
        self.client = TestClient(app, base_url="http://testserver")
        self.client.cookies.set("session", "ok")
        self.calls = []

    def run_console(self, payload, command):
        def fake_command(*args):
            self.calls.append(args)
            return command

        with (
            patch.object(NginxService, "helper_installed", staticmethod(lambda: True)),
            patch.object(NginxService, "helper_command", staticmethod(fake_command)),
            patch.object(nginx_routes.domain_folder_service, "assign_domain"),
            self.client.websocket_connect(
                "/nginx/ws/console", headers={"origin": "http://testserver"}
            ) as socket,
        ):
            socket.send_json(payload)
            lines = []
            try:
                while True:
                    lines.append(socket.receive_text())
            except Exception:  # noqa: BLE001 — 서버가 닫으면 끝
                return lines

    def test_only_helper_is_called_with_validated_arguments(self):
        lines = self.run_console(
            {"action": "delete", "domain": "A.Example.com"}, ["echo", "ok"]
        )
        self.assertEqual(self.calls, [("delete", "a.example.com")])
        self.assertEqual(lines[-1], "작업이 완료되었습니다.")

    def test_failed_helper_reports_failure(self):
        lines = self.run_console(
            {"action": "delete", "domain": "a.example.com"}, ["false"]
        )
        self.assertEqual(lines[-1], "작업이 실패했습니다.")

    def test_bad_input_never_reaches_helper(self):
        lines = self.run_console({"action": "delete", "domain": "x\n.com"}, ["echo"])
        self.assertEqual(self.calls, [])
        self.assertIn("유효하지 않은", lines[0])
        self.run_console({"action": "rm", "domain": "a.com"}, ["echo"])
        self.run_console(["delete"], ["echo"])
        self.assertEqual(self.calls, [])

    def test_cross_origin_socket_is_rejected(self):
        with self.client.websocket_connect(
            "/nginx/ws/console", headers={"origin": "https://evil.example"}
        ) as socket:
            self.assertIn("허용되지", socket.receive_text())


class FolderNameTest(unittest.TestCase):
    def test_folder_name_never_lands_inside_inline_javascript(self):
        source = (ROOT / "app" / "templates" / "nginx.html").read_text()
        env = Environment(
            loader=DictLoader(
                {"nginx.html": source, "base.html": "{% block content %}{% endblock %}"}
            ),
            autoescape=select_autoescape(default=True, default_for_string=True),
        )
        attack = "');alert(1);//"
        group = {"id": "f1", "name": attack, "domains": [], "ports": []}
        html = env.get_template("nginx.html").render(
            groups=[group], folders=[group], domains=[]
        )
        self.assertNotIn("openRenameFolderModal('f1'", html)
        self.assertNotIn("deleteFolder('f1'", html)
        self.assertIn("this.dataset.folderName", html)
        self.assertNotIn(attack, html)


class HelperTest(unittest.TestCase):
    def test_helper_runs_without_passphrase_here(self):
        self.assertFalse(nginx_helper.REQUIRE_PASSPHRASE)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "av").mkdir()
            (root / "en").mkdir()
            tool = root / "tool"
            tool.write_text("#!/bin/sh\nexit 0\n")
            tool.chmod(0o755)
            with patch.multiple(
                nginx_helper,
                SITES_AVAILABLE=str(root / "av"),
                SITES_ENABLED=str(root / "en"),
                NGINX=str(tool),
                CERTBOT=str(tool),
                SYSTEMCTL=str(tool),
            ):
                code = nginx_helper.run(["add", "b.example.com", "m@x.com", "1", "/"])
            self.assertEqual(code, 0)
            config = (root / "av" / "b.example.com").read_text()
            self.assertIn("X-Forwarded-For $remote_addr", config)


if __name__ == "__main__":
    unittest.main()
