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


if __name__ == "__main__":
    unittest.main()
