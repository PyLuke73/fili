"""Test di 'restart' (riattiva un dispositivo disattivato o lo riavvia). Nulla tocca il sistema: ogni comando passa da un
esecutore finto.

Esecuzione:  python -I tests/test_restart.py        (dalla radice del repository)
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_fili import DEVICES, FakeRun, call  # noqa: E402  (disattiva anche l'esecutore vero)

from fili import devices, ops  # noqa: E402

NIC = r"USB\VID_0BDA&PID_8153\SERIAL1"
ARGV = ["restart", "--vid", "0BDA", "--pid", "8153"]


def nic(problem):
    return {"InstanceId": NIC, "Class": "Net", "Status": "Error" if problem else "OK", "FriendlyName": "USB GbE Family Controller",
            "ProblemCode": problem, "Service": "rtu53cx22x64", "InfPath": "oem44.inf", "Provider": "Realtek"}


def pnputil(run):
    return [c[1:] for c in run.mutating() if c[0] == "pnputil"]


class TestRestart(unittest.TestCase):
    def run_with(self, problem, after=None):
        return FakeRun(devices_json=DEVICES + [nic(problem)], after=None if after is None else DEVICES + [nic(after)])

    def test_plan_enables_a_disabled_device(self):
        dev = devices.select_target(devices.parse_device_list(__import__("json").dumps([nic(22)])), 0x0BDA, 0x8153, None)
        self.assertEqual(ops.restart_plan(dev), [["pnputil", "/enable-device", NIC]])

    def test_plan_restarts_a_running_device(self):
        dev = devices.select_target(devices.parse_device_list(__import__("json").dumps([nic(0)])), 0x0BDA, 0x8153, None)
        self.assertEqual(ops.restart_plan(dev), [["pnputil", "/restart-device", NIC]])

    def test_dry_run_changes_nothing(self):
        code, out, err, run = call(ARGV + ["--dry-run"], run=self.run_with(22))
        self.assertEqual(code, 0, err)
        self.assertEqual(run.mutating(), [])
        self.assertIn("/enable-device", out)
        self.assertIn("disabled", out)

    def test_needs_yes_and_administrator(self):
        code, out, err, run = call(ARGV, run=self.run_with(22), admin=True)
        self.assertEqual(code, 7)
        self.assertEqual(run.mutating(), [])
        code, out, err, run = call(ARGV + ["--yes"], run=self.run_with(22), admin=False)
        self.assertEqual(code, 3)
        self.assertEqual(run.mutating(), [])

    def test_enables_a_disabled_device_and_reports_the_result(self):
        code, out, err, run = call(ARGV + ["--yes"], run=self.run_with(22, after=0), admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(pnputil(run), [["/enable-device", NIC]])
        self.assertIn("after:", out)

    def test_restarts_a_running_device(self):
        code, out, err, run = call(ARGV + ["--yes"], run=self.run_with(0), admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(pnputil(run), [["/restart-device", NIC]])

    def test_still_disabled_after_the_command_is_an_error(self):
        code, out, err, run = call(ARGV + ["--yes"], run=self.run_with(22, after=22), admin=True)
        self.assertEqual(code, 6)
        self.assertIn("22", err + out)

    def test_command_failure_is_reported(self):
        run = FakeRun(devices_json=DEVICES + [nic(22)], fail={"/enable-device": (5, "", "access denied")})
        code, out, err, run = call(ARGV + ["--yes"], run=run, admin=True)
        self.assertEqual(code, 6)

    def test_a_disabled_mouse_can_be_enabled_without_force(self):
        mouse = dict(DEVICES[7], ProblemCode=22, Status="Error")
        code, out, err, run = call(["restart", "--vid", "093A", "--pid", "2510", "--yes"],
                                   run=FakeRun(devices_json=[mouse], after=[dict(mouse, ProblemCode=0, Status="OK")]), admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(pnputil(run)[0][0], "/enable-device")


class TestReinstallOriginalDriver(unittest.TestCase):
    """reinstall di un dispositivo con il driver del produttore: si toglie il dispositivo e Windows lo rileva di nuovo."""
    ARGV = ["reinstall", "--vid", "0BDA", "--pid", "8153"]

    def run_with(self, problem=0):
        return FakeRun(devices_json=DEVICES + [nic(problem)])

    def test_dry_run_shows_remove_and_scan_and_changes_nothing(self):
        code, out, err, run = call(self.ARGV + ["--dry-run"], run=self.run_with(22))
        self.assertEqual(code, 0, err)
        self.assertEqual(run.mutating(), [])
        self.assertIn("/remove-device " + NIC, out)
        self.assertIn("/scan-devices", out)
        self.assertIn("not a driver installed by fili", out)

    def test_needs_yes_and_administrator(self):
        self.assertEqual(call(self.ARGV, run=self.run_with(), admin=True)[0], 7)
        code, out, err, run = call(self.ARGV + ["--yes"], run=self.run_with(), admin=False)
        self.assertEqual(code, 3)
        self.assertEqual(run.mutating(), [])

    def test_runs_remove_then_scan_and_checks_the_device(self):
        run = FakeRun(devices_json=DEVICES + [nic(22)], after=DEVICES + [nic(0)])
        code, out, err, run = call(self.ARGV + ["--yes"], run=run, admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(pnputil(run), [["/remove-device", NIC], ["/scan-devices"]])
        self.assertIn("after:", out)

    def test_no_wdi_and_no_certificate_are_involved(self):
        code, out, err, run = call(self.ARGV + ["--yes"], run=self.run_with(), admin=True)
        self.assertNotIn("wdi-simple", " ".join(" ".join(c) for c in run.mutating()))

    def test_protected_class_needs_force(self):
        argv = ["reinstall", "--vid", "093A", "--pid", "2510", "--yes"]
        code, out, err, run = call(argv, run=FakeRun(), admin=True)
        self.assertEqual(code, 2)
        self.assertEqual(run.mutating(), [])

    def test_device_that_does_not_come_back_is_an_error(self):
        from fili import cli
        from unittest import mock
        run = FakeRun(devices_json=DEVICES + [nic(0)], after=DEVICES)
        with mock.patch.object(cli, "RESET_WAIT", (2, 0)):
            code, out, err, run = call(self.ARGV + ["--yes"], run=run, admin=True)
        self.assertEqual(code, 6)
        self.assertIn("not listed", err + out)

    def test_a_fili_driver_still_takes_the_old_path(self):
        code, out, err, run = call(["reinstall", "--vid", "0483", "--pid", "374B", "--iface", "2", "--dry-run"])
        self.assertEqual(code, 0, err)
        self.assertNotIn("/remove-device", out)


if __name__ == "__main__":
    unittest.main()
