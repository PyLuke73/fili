"""Test di 'restore' su un dispositivo che ha solo il filtro libusb-win32 (install --filter). Nulla tocca il sistema.

Esecuzione:  python -I tests/test_filter.py        (dalla radice del repository)
"""

import json
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_fili import FakeRun, call, fake_wdi  # noqa: E402  (disattiva anche l'esecutore vero)

from fili import ops  # noqa: E402

STICK = {"InstanceId": "USB\\VID_0951&PID_1666\\SER1", "Class": "USB", "Status": "Error", "FriendlyName": "Stick",
         "ProblemCode": 39, "Service": "USBSTOR", "InfPath": "usbstor.inf", "Provider": "Microsoft"}
ARGV = ["restore", "--vid", "0951", "--pid", "1666"]


class FilterRun(FakeRun):
    def __init__(self, filters):
        super().__init__(devices_json=[STICK], after=[dict(STICK, Status="OK", ProblemCode=0)])
        self.filters = filters

    def __call__(self, cmd):
        if cmd[0] == "powershell" and "DEVPKEY_Device_UpperFilters" in cmd[-1]:
            self.calls.append(list(cmd))
            return types.SimpleNamespace(returncode=0, stdout=json.dumps(self.filters), stderr="")
        return super().__call__(cmd)


def mutating(run):
    return [c for c in run.mutating() if "DEVPKEY_Device_UpperFilters" not in c[-1]]


class TestFilterRestore(unittest.TestCase):
    def test_filter_only_device_is_restored(self):
        run = FilterRun(["libusb0"])
        code, out, err, run = call(ARGV + ["--yes"], run=run, admin=True)
        self.assertEqual(code, 0, err)
        cmds = mutating(run)
        self.assertIn("Remove-ItemProperty", cmds[0][-1])
        self.assertIn("Enum\\USB\\VID_0951&PID_1666\\SER1", cmds[0][-1])
        self.assertEqual(cmds[1][:2], ["pnputil", "/restart-device"])
        self.assertFalse(any("/delete-driver" in c for c in cmds))

    def test_other_filters_are_kept(self):
        run = FilterRun(["libusb0", "OtherFilter"])
        code, out, err, run = call(ARGV + ["--dry-run"], run=run)
        self.assertEqual(code, 0, err)
        self.assertIn("Set-ItemProperty", out)
        self.assertIn("'OtherFilter'", out)
        self.assertNotIn("'libusb0'", out)

    def test_dry_run_changes_nothing(self):
        code, out, err, run = call(ARGV + ["--dry-run"], run=FilterRun(["libusb0"]))
        self.assertEqual(mutating(run), [])

    def test_without_a_filter_it_still_refuses(self):
        code, out, err, run = call(ARGV + ["--yes"], run=FilterRun([]), admin=True)
        self.assertEqual(code, 2)
        self.assertIn("not an OEM package", err)
        self.assertEqual(mutating(run), [])

    def test_unsafe_instance_id_is_rejected(self):
        with self.assertRaises(ValueError):
            ops.filter_removal_commands(types.SimpleNamespace(instance_id="USB\\X'; calc; '"), ["libusb0"])


class TestFilterInstall(unittest.TestCase):
    def test_driver_stays_the_original_one(self):
        """Con --filter libusb0 è un filtro superiore: il servizio del dispositivo resta USBSTOR e non è un errore."""
        healthy = dict(STICK, Status="OK", ProblemCode=0)
        with tempfile.TemporaryDirectory() as tmp:
            run = FakeRun(devices_json=[healthy], after=[healthy])
            argv = ["install", "--vid", "0951", "--pid", "1666", "--driver", "libusb-win32", "--filter", "--force",
                    "--wdi", fake_wdi(tmp), "--yes"]
            code, out, err, run = call(argv, run=run, admin=True)
        self.assertEqual(code, 0, err)
        self.assertIn("--filter", run.mutating()[0])
        self.assertIn("driver 'USBSTOR'", out)

    def test_without_filter_the_service_is_still_checked(self):
        healthy = dict(STICK, Status="OK", ProblemCode=0)
        with tempfile.TemporaryDirectory() as tmp:
            run = FakeRun(devices_json=[healthy], after=[healthy])
            argv = ["install", "--vid", "0951", "--pid", "1666", "--driver", "libusb-win32", "--force",
                    "--wdi", fake_wdi(tmp), "--yes"]
            code, out, err, run = call(argv, run=run, admin=True)
        self.assertEqual(code, 6)
        self.assertIn("expected 'libusb0'", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
