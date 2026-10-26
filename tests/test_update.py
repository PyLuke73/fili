"""Test del controllo degli aggiornamenti ('fili update' e fili.updates). Nessuna richiesta di rete: le Release sono dati finti.

Esecuzione:  python -I tests/test_update.py        (dalla radice del repository)
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_fili import call  # noqa: E402  (disattiva anche l'esecutore vero)

from fili import __version__, cli, skill, updates  # noqa: E402

BASE = "https://github.com/PyLuke73/fili/releases"


def rel(tag, pre=False, draft=False, url=None):
    return {"tag_name": tag, "html_url": url or "%s/tag/%s" % (BASE, tag), "prerelease": pre, "draft": draft,
            "published_at": "2030-01-01T00:00:00Z"}


class TestVersionKey(unittest.TestCase):
    def test_ordering(self):
        k = updates.version_key
        self.assertLess(k("0.1.0"), k("v0.1.1"))
        self.assertLess(k("0.9.0"), k("0.10.0"))
        self.assertLess(k("1.0.0-rc1"), k("1.0.0"))
        self.assertLess(k("1.0.0-rc1"), k("1.0.0-rc2"))
        self.assertEqual(k("1.0"), k("v1.0.0"))
        self.assertIsNone(k("nightly"))
        self.assertIsNone(k(""))


class TestCheck(unittest.TestCase):
    def test_newer_release_is_reported(self):
        d = updates.check("0.1.0", lambda: [rel("v0.1.0", True), rel("v0.2.0")])
        self.assertTrue(d["update_available"])
        self.assertEqual((d["latest"], d["url"]), ("0.2.0", BASE + "/tag/v0.2.0"))

    def test_same_or_older_means_up_to_date(self):
        self.assertFalse(updates.check("0.2.0", lambda: [rel("v0.2.0"), rel("v0.1.0")])["update_available"])
        self.assertFalse(updates.check("0.3.0", lambda: [rel("v0.2.0")])["update_available"])

    def test_drafts_and_odd_tags_are_ignored(self):
        d = updates.check("0.1.0", lambda: [rel("v5.0.0", draft=True), rel("nightly"), rel("v0.1.0")])
        self.assertFalse(d["update_available"])
        self.assertEqual(d["latest"], "0.1.0")

    def test_prerelease_is_flagged(self):
        d = updates.check("0.1.0", lambda: [rel("v0.2.0-rc1", pre=True)])
        self.assertTrue(d["update_available"])
        self.assertTrue(d["prerelease"])
        self.assertIn("(pre-release)", "\n".join(updates.describe(d)))

    def test_a_url_outside_the_project_is_replaced_by_the_releases_page(self):
        d = updates.check("0.1.0", lambda: [rel("v0.2.0", url="https://evil.example/download.exe")])
        self.assertEqual(d["url"], updates.RELEASES_URL)

    def test_no_releases(self):
        d = updates.check("0.1.0", lambda: [])
        self.assertIsNone(d["latest"])
        self.assertFalse(d["update_available"])
        self.assertIn("No release is published yet.", updates.describe(d))

    def test_fetch_errors_become_update_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            with self.assertRaises(updates.UpdateError):
                updates.fetch_releases()

    def test_the_request_is_a_plain_https_get_to_the_projects_release_list(self):
        seen = {}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"[]"

        def fake_open(req, timeout=None):
            seen.update(url=req.full_url, headers=dict(req.header_items()), data=req.data, method=req.get_method(),
                        timeout=timeout)
            return Resp()
        with mock.patch("urllib.request.urlopen", fake_open):
            self.assertEqual(updates.fetch_releases(), [])
        self.assertTrue(seen["url"].startswith("https://api.github.com/repos/PyLuke73/fili/"))
        self.assertIsNone(seen["data"])
        self.assertEqual(seen["method"], "GET")
        self.assertEqual(sorted(seen["headers"]), ["Accept", "User-agent"])     # nessun dato dell'utente nelle intestazioni
        self.assertIsNotNone(seen["timeout"])


class TestCli(unittest.TestCase):
    def test_update_available_json(self):
        code, out, err, run = call(["--json", "update"], fetch=lambda: [rel("v99.0.0")])
        self.assertEqual(code, 0, err)
        doc = json.loads(out)
        self.assertTrue(doc["data"]["update_available"])
        self.assertEqual(doc["data"]["latest"], "99.0.0")
        self.assertEqual(run.mutating(), [])

    def test_up_to_date_text(self):
        code, out, err, run = call(["update", "--check"], fetch=lambda: [rel("v" + __version__)])
        self.assertEqual(code, 0, err)
        self.assertIn("You have the latest version.", out)

    def test_network_failure_is_exit_1_with_a_message(self):
        def boom():
            raise updates.UpdateError("cannot reach GitHub: offline")
        code, out, err, run = call(["update"], fetch=boom)
        self.assertEqual(code, 1)
        self.assertIn("offline", err)

    def test_no_other_command_uses_the_network(self):
        with mock.patch.object(updates, "fetch_releases", side_effect=AssertionError("network")):
            for argv in (["list"], ["licenses"], ["sample-config"], ["--skill"]):
                self.assertEqual(call(argv)[0], 0, argv)

    def test_skill_lists_update_as_the_networked_command(self):
        text = skill.build(__version__, cli.EXIT_CODES)
        self.assertIn("`update`", text)
        self.assertIn("contacts GitHub", text)


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {"APPDATA": self.tmp.name}

    def test_defaults_are_off(self):
        self.assertEqual(updates.load_settings(self.env), {})
        self.assertFalse(updates.auto_check_due({}))
        self.assertFalse(updates.auto_check_due({"check_updates": False}))
        self.assertFalse(updates.auto_check_due({"check_updates": "yes"}))

    def test_round_trip_and_merge(self):
        self.assertTrue(updates.save_settings(self.env, check_updates=True))
        self.assertTrue(updates.save_settings(self.env, last_check=100.0))
        self.assertEqual(updates.load_settings(self.env), {"check_updates": True, "last_check": 100.0})

    def test_due_only_once_a_day(self):
        on = {"check_updates": True, "last_check": 1000.0}
        self.assertFalse(updates.auto_check_due(on, now=1000.0 + 3600))
        self.assertTrue(updates.auto_check_due(on, now=1000.0 + 25 * 3600))
        self.assertTrue(updates.auto_check_due({"check_updates": True}, now=5.0))
        self.assertTrue(updates.auto_check_due({"check_updates": True, "last_check": 9999.0}, now=10.0))   # orologio spostato

    def test_broken_file_or_missing_appdata_never_raises(self):
        os.makedirs(os.path.join(self.tmp.name, "fili"))
        with open(os.path.join(self.tmp.name, "fili", "settings.json"), "w") as f:
            f.write("{not json")
        self.assertEqual(updates.load_settings(self.env), {})
        self.assertEqual(updates.load_settings({}), {})
        self.assertFalse(updates.save_settings({}, check_updates=True))


if __name__ == "__main__":
    unittest.main()
