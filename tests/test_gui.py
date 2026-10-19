"""Test della logica della GUI (guicore). Non serve tkinter e nulla tocca il sistema.

Esecuzione:  python -I tests/test_gui.py        (dalla radice del repository)
"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_usbdrv import DEVICES, FakeRun, fake_wdi  # noqa: E402  (disattiva anche l'esecutore vero)

from usbdrv import guicore  # noqa: E402


def kw(run, admin):
    return dict(run=run, is_admin=lambda: admin, env={})


def find(rows, vid, pid, mi=None):
    return next(d for d in rows if d["vid"] == vid and d["pid"] == pid and d["mi"] == mi)


class TestGuiCore(unittest.TestCase):
    def devices(self):
        res = guicore.list_devices(**kw(FakeRun(), False))
        self.assertTrue(res.ok)
        return res.data

    def test_list_returns_dicts(self):
        rows = self.devices()
        self.assertEqual(find(rows, 0x483, 0x374B, 0)["service"], "WinUSB")

    def test_target_uses_the_instance_id(self):
        dev = find(self.devices(), 0x483, 0x374B, 0)
        self.assertEqual(guicore.target_args(dev)[-2:], ["--instance", dev["instance_id"]])

    def test_install_args(self):
        dev = find(self.devices(), 0x483, 0x374B, 0)
        argv = guicore.install_args("install", dev, "libusbk", name=" My dev ", wcid=True, filter_driver=True, force=True)
        self.assertEqual(argv[0], "install")
        for part in ("--driver", "libusbk", "--name", "My dev", "--wcid", "--filter", "--force"):
            self.assertIn(part, argv)
        self.assertNotIn("--driver", guicore.install_args("restore", dev, "libusbk"))
        with self.assertRaises(ValueError):
            guicore.install_args("rm -rf", dev)

    def test_preview_changes_nothing(self):
        run = FakeRun()
        dev = find(self.devices(), 0x483, 0x374B, 0)
        with tempfile.TemporaryDirectory() as tmp:
            argv = guicore.install_args("restore", dev)
            res = guicore.preview(argv, **kw(run, False))
        self.assertTrue(res.ok)
        self.assertEqual(run.mutating(), [])
        self.assertTrue(res.data["dry_run"])

    def test_apply_needs_admin(self):
        restored = [dict(d, Service="usbvideo", InfPath="usbvideo.inf", Provider="Microsoft")
                    if "VID_0483&PID_374B&MI_00" in d["InstanceId"] else d for d in DEVICES]
        run = FakeRun(after=restored)
        dev = find(self.devices(), 0x483, 0x374B, 0)
        res = guicore.apply(guicore.install_args("restore", dev), **kw(run, False))
        self.assertFalse(res.ok)
        self.assertEqual(res.code, 3)
        self.assertIn("Administrator", res.error)
        self.assertEqual(run.mutating(), [])

    def test_apply_runs_the_plan_when_admin(self):
        restored = [dict(d, Service="usbvideo", InfPath="usbvideo.inf", Provider="Microsoft")
                    if "VID_0483&PID_374B&MI_00" in d["InstanceId"] else d for d in DEVICES]
        run = FakeRun(after=restored)
        dev = find(self.devices(), 0x483, 0x374B, 0)
        res = guicore.apply(guicore.install_args("restore", dev), **kw(run, True))
        self.assertTrue(res.ok, res.error)
        self.assertTrue(any(c[0] == "pnputil" for c in run.mutating()))

    def test_protected_class_is_refused_without_force(self):
        dev = find(self.devices(), 0x093A, 0x2510)
        with tempfile.TemporaryDirectory() as tmp:
            run = FakeRun()
            argv = guicore.install_args("install", dev) + ["--wdi", fake_wdi(tmp)]
            res = guicore.preview(argv, **kw(run, True))
            self.assertEqual(res.code, 2)
            self.assertIn("--force", res.error)
            self.assertTrue(guicore.preview(argv + ["--force"], **kw(run, True)).ok)

    def test_help_explains_every_button(self):
        for word in ("Install", "Reinstall", "Restore", "Diagnose", "Certificates", "Licenses", "Save output",
                     "Driver", "Name", "WCID", "Filter driver", "Force"):
            self.assertIn(word, guicore.HELP_TEXT)

    def test_about_has_version_license_and_credits(self):
        from usbdrv import __version__
        text = guicore.about_text()
        for part in (__version__, "MIT", "Zadig", "libwdi", "libusbK", "libusb-win32", "Not legal advice"):
            self.assertIn(part, text)

    def test_non_json_output_is_reported(self):
        res = guicore.call(["list"], main=lambda argv, out, err, **k: (out.write("not json"), 1)[1])
        self.assertFalse(res.ok)
        self.assertEqual(res.code, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
