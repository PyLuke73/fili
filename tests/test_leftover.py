"""Regressione: 'restore' deve rimuovere OGNI pacchetto residuo, anche quelli il cui provider non è 'libwdi'
(i pacchetti libusbK e libusb-win32 sono pubblicati con il proprio nome). Nulla tocca il sistema.

Esecuzione:  python -I tests/test_leftover.py        (dalla radice del repository)
"""

import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_fili import FakeRun, call  # noqa: E402  (disattiva anche l'esecutore vero)

from fili import devices, ops  # noqa: E402

ID = "USB\\VID_0E8D&PID_201C\\SER1"


class NoFilterRun(FakeRun):
    def __call__(self, cmd):
        if cmd[0] == "powershell" and "DEVPKEY_Device_UpperFilters" in cmd[-1]:
            return types.SimpleNamespace(returncode=0, stdout="[]", stderr="")
        return super().__call__(cmd)


def row(inf, provider, service):
    return {"InstanceId": ID, "Class": "USBDevice", "Status": "OK", "FriendlyName": "Phone", "ProblemCode": 0,
            "Service": service, "InfPath": inf, "Provider": provider}


class TestLeftoverPackages(unittest.TestCase):
    def test_provider_is_not_the_only_signal(self):
        for provider, service in (("libwdi", "WinUSB"), ("libusbK", "libusbK"), ("libusb-win32", "libusb0")):
            dev = devices.parse_device_list(__import__("json").dumps([row("oem5.inf", provider, service)]))[0]
            self.assertTrue(ops.is_libwdi_package(dev), provider)

    def test_inbox_and_foreign_packages_are_not_ours(self):
        for inf, provider, service in (("winusb.inf", "Microsoft", "WINUSB"), ("oem9.inf", "Acme", "acmedrv")):
            dev = devices.parse_device_list(__import__("json").dumps([row(inf, provider, service)]))[0]
            self.assertFalse(ops.is_libwdi_package(dev), inf)

    def test_restore_goes_through_two_libusbk_packages(self):
        seq = [[row("oem181.inf", "libusbK", "libusbK")], [row("winusb.inf", "Microsoft", "WINUSB")]]
        run = NoFilterRun(devices_json=[row("oem191.inf", "libusbK", "libusbK")], after_seq=seq)
        code, out, err, run = call(["restore", "--vid", "0E8D", "--pid", "201C", "--yes"], run=run, admin=True)
        self.assertEqual(code, 0, err)
        deleted = [c[2] for c in run.mutating() if c[:2] == ["pnputil", "/delete-driver"]]
        self.assertEqual(deleted, ["oem191.inf", "oem181.inf"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
