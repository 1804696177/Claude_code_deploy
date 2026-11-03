#!/usr/bin/env python3
"""Offline checks only: no downloads, host changes or deployment script execution."""

import ast
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


def deny_network(event, args):
    if event.startswith("socket."):
        raise RuntimeError("Network access is forbidden during local validation")


sys.addaudithook(deny_network)


class LocalChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="claude-network-check-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.output = self.work / "generated"
        # Format-only fixtures; not a real X25519 pair and never used for a handshake.
        self.private = base64.urlsafe_b64encode(bytes(range(32))).decode().rstrip("=")
        self.public = base64.urlsafe_b64encode(bytes(range(32, 64))).decode().rstrip("=")
        self.key = self.work / "keys.txt"
        self.key.write_text(f"PrivateKey: {self.private}\nPassword (PublicKey): {self.public}\n")
        self.key.chmod(0o600)

    def generate(self, **overrides):
        # Public address is a syntactic fixture only: nothing connects to it.
        options = {
            "vps-ip": "1.1.1.1", "sni": "example.com",
            "key-file": str(self.key), "wan-dev": "eth1.2",
            "out": str(self.output),
        }
        options.update(overrides)
        argv = [str(ROOT / "scripts/generate-configs.py")]
        for name, value in options.items():
            argv.extend([f"--{name}", value])
        old_argv, old_umask = sys.argv, os.umask(0o077)
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            sys.argv = argv
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    runpy.run_path(argv[0], run_name="__main__")
                except SystemExit as exc:
                    return exc.code, stdout.getvalue(), stderr.getvalue()
            return 0, stdout.getvalue(), stderr.getvalue()
        finally:
            sys.argv = old_argv
            os.umask(old_umask)

    def test_generation_and_credentials(self):
        code, stdout, stderr = self.generate()
        self.assertEqual(code, 0, stderr)
        server = json.loads((self.output / "server/config.json").read_text())
        router = json.loads((self.output / "router/config.json").read_text())
        inbound = server["inbounds"][0]
        outbound = router["outbounds"][0]
        client = inbound["settings"]["clients"][0]
        user = outbound["settings"]["vnext"][0]["users"][0]
        self.assertEqual(client["id"], user["id"])
        reality = inbound["streamSettings"]["realitySettings"]
        peer = outbound["streamSettings"]["realitySettings"]
        self.assertEqual(reality["privateKey"], self.private)
        self.assertEqual(peer["password"], self.public)
        self.assertIn(peer["shortId"], reality["shortIds"])
        self.assertEqual(client["flow"], "xtls-rprx-vision")
        self.assertEqual(user["flow"], "xtls-rprx-vision-udp443")
        self.assertEqual(outbound["streamSettings"]["sockopt"]["interface"], "eth1.2")
        for path in (self.output / "router").iterdir():
            self.assertNotIn(self.private, path.read_text(), path.name)
        self.assertNotIn(self.private, stdout + stderr)
        self.assertNotIn(client["id"], stdout + stderr)
        env = dict(token.split("=", 1) for token in shlex.split(
            (self.output / "router/site.env").read_text()))
        self.assertEqual(env["WAN_DEV"], "eth1.2")
        for name in ("apply-router.sh", "rollback-router.sh"):
            self.assertEqual((self.output / "router" / name).read_bytes(),
                             (ROOT / "scripts" / name).read_bytes())
        self.assertFalse((self.output / "router/preflight-ok").exists())

    def test_preflight_has_no_tun(self):
        self.assertEqual(self.generate()[0], 0)
        config = json.loads((self.output / "router/preflight.json").read_text())
        self.assertEqual(len(config["inbounds"]), 1)
        inbound = config["inbounds"][0]
        self.assertEqual((inbound["protocol"], inbound["listen"], inbound["port"]),
                         ("socks", "127.0.0.1", 2081))

    def test_permissions_and_complete_render(self):
        self.assertEqual(self.generate()[0], 0)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        for path in self.output.rglob("*"):
            expected = 0o700 if path.is_dir() else 0o600
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected, str(path))
            if path.is_file():
                self.assertIsNone(re.search(r"__[A-Z0-9_]+__", path.read_text()), str(path))

    def test_refuses_overwrite_without_changing_files(self):
        self.assertEqual(self.generate()[0], 0)
        before = {str(p): p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        self.assertNotEqual(self.generate()[0], 0)
        after = {str(p): p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_rejects_invalid_parameters_before_writing(self):
        for options in (
            {"vps-ip": "203.0.113.10"}, {"vps-ip": "192.168.1.1"},
            {"tun-cidr": "172.31.255.0/30"}, {"tun-cidr": "172.31.255.1/24"},
            {"wan-dev": "br-lan"}, {"lan-zone": "wan"},
            {"wan-dev": "eth1;touch injected"}, {"sni": "https://example.com"},
        ):
            with self.subTest(options=options):
                self.assertNotEqual(self.generate(**options)[0], 0)
                self.assertFalse(self.output.exists())
        self.key.write_text("PrivateKey: invalid\nHash32: not-a-public-key\n")
        self.assertNotEqual(self.generate()[0], 0)
        self.assertFalse(self.output.exists())

    def test_python_shell_and_json_syntax(self):
        for path in (ROOT / "scripts").glob("*.py"):
            ast.parse(path.read_text(), filename=str(path))
        paths = list((ROOT / "scripts").glob("*.sh"))
        paths.append(ROOT / "assets/templates/us-vpn.init")
        for path in paths:
            # -n parses only. Never invoke apply-router/rollback-router themselves.
            result = subprocess.run(["sh", "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        for path in (ROOT / "assets/templates").glob("*.json"):
            json.loads(path.read_text())

    def test_local_document_links(self):
        for path in [ROOT / "SKILL.md", *sorted((ROOT / "references").glob("*.md"))]:
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" not in target and not target.startswith("#"):
                    self.assertTrue((path.parent / target.split("#")[0]).exists(),
                                    f"Broken link in {path.name}: {target}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
