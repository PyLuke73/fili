"""Test di 'usb-reset' e del timeout dei comandi esterni. Nulla tocca il sistema: ogni comando passa da un esecutore finto
(l'unico processo vero è un 'python' che dorme, per provare il timeout).

Esecuzione:  python -I tests/test_usbreset.py        (dalla radice del repository)
"""

import json
import os
import sys
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_fili import DEVICES, FakeRun, call  # noqa: E402  (disattiva anche l'esecutore vero)

from fili import cli, ops  # noqa: E402

DEV = "USB\\VID_0483&PID_374B&MI_00\\6&AA&0&0000"  # interfaccia WinUSB senza problemi, classe non protetta
MOUSE = "USB\\VID_093A&PID_2510\\M"                # classe protetta (HID)
HUB = "USB\\VID_0BDA&PID_0411\\7&25D82005&0&4"     # hub esterno
ROOT = "USB\\ROOT_HUB30\\4&1&0&0"                  # hub radice del controller
ARGV = ["usb-reset", "--vid", "0483", "--pid", "374B", "--iface", "0"]


def ns(rc=0, out="", err=""):
    return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)


class ResetRun(FakeRun):
    """FakeRun che risponde anche alle tre interrogazioni di sola lettura di usb-reset."""

    def __init__(self, stuck=None, parents=None, kids=None, fail=None, **kw):
        super().__init__(fail=fail, **kw)
        self.stuck = stuck or []
        self.parents = parents if parents is not None else [
            {"InstanceId": HUB, "Class": "USB", "Name": "Generic hub", "Service": "USBHUB3"},
            {"InstanceId": ROOT, "Class": "USB", "Name": "Root hub", "Service": "USBHUB3"}]
        self.kids = kids if kids is not None else [{"InstanceId": DEV, "Class": "", "Name": "Unknown device"}]

    def __call__(self, cmd):
        if cmd[0] == "powershell":
            script = cmd[-1]
            for marker, data in (("# fili:stuck", self.stuck), ("# fili:parents", self.parents),
                                 ("# fili:descendants", self.kids)):
                if marker in script:
                    self.calls.append(list(cmd))
                    return ns(0, json.dumps(data))
        return super().__call__(cmd)

    def mutating(self):
        return [c for c in super().mutating() if not (c[0] == "powershell" and "# fili:" in c[-1])]


def pnputil(run):
    return [c[1:] for c in run.mutating() if c[0] == "pnputil"]


class TestPlan(unittest.TestCase):
    def dev(self):
        from fili import devices
        return devices.select_target(devices.parse_device_list(json.dumps(DEVICES)), 0x483, 0x374B, 0)

    def test_device_cycle_without_stuck_commands(self):
        plan = ops.usb_reset_plan(self.dev(), [])
        self.assertEqual(plan, [["pnputil", "/disable-device", DEV], ["pnputil", "/enable-device", DEV]])

    def test_only_old_enough_processes_are_stopped(self):
        stuck = [{"Pid": 111, "Command": "pnputil /restart-device", "Seconds": 900},
                 {"Pid": 222, "Command": "pnputil /scan-devices", "Seconds": 3}]
        plan = ops.usb_reset_plan(self.dev(), stuck)
        self.assertEqual(plan[0], ["taskkill", "/PID", "111", "/F"])
        self.assertNotIn(["taskkill", "/PID", "222", "/F"], plan)
        self.assertEqual(len(plan), 3)

    def test_hub_is_the_target_with_a_hub(self):
        plan = ops.usb_reset_plan(self.dev(), [], {"InstanceId": HUB})
        self.assertEqual([c[2] for c in plan], [HUB, HUB])

    def test_root_hub_and_controller_are_never_chosen(self):
        chain = [{"InstanceId": ROOT, "Class": "USB", "Service": "USBHUB3"},
                 {"InstanceId": "PCI\\VEN_8086&DEV_1\\3", "Class": "USB", "Service": "USBXHCI"}]
        self.assertIsNone(ops.parent_hub(chain))
        self.assertEqual(ops.parent_hub([{"InstanceId": HUB, "Service": "USBHUB3"}] + chain)["InstanceId"], HUB)
        # un hub che sta SOPRA l'hub radice non esiste, ma se la catena lo elencasse dopo la radice non va scelto
        self.assertIsNone(ops.parent_hub([chain[0], {"InstanceId": HUB, "Service": "USBHUB3"}]))

    def test_instance_id_is_validated(self):
        from fili import devices
        bad = devices.UsbDevice(**dict(self.dev().__dict__, instance_id="USB\\X'; calc; '"))
        for fn in (ops.stuck_command, ):
            with self.assertRaises(ValueError):
                fn(bad)
        with self.assertRaises(ValueError):
            ops.usb_reset_plan(bad, [])

    def test_protected_below_uses_the_protected_classes(self):
        kids = [{"InstanceId": "a", "Class": "HIDClass"}, {"InstanceId": "b", "Class": "Net"},
                {"InstanceId": "c", "Class": "DiskDrive"}]
        self.assertEqual([k["InstanceId"] for k in ops.protected_below(kids)], ["a", "c"])


class TestCommand(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(cli, "RESET_WAIT", (2, 0))
        patch.start()
        self.addCleanup(patch.stop)

    def test_dry_run_changes_nothing_and_shows_the_plan(self):
        code, out, err, run = call(ARGV + ["--dry-run"], run=ResetRun(), admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(run.mutating(), [])
        self.assertIn("/disable-device", out)
        self.assertIn("No pnputil command is working", out)

    def test_needs_yes_and_administrator(self):
        code, out, err, run = call(ARGV, run=ResetRun(), admin=True)
        self.assertEqual(code, 7)
        self.assertEqual(run.mutating(), [])
        code, out, err, run = call(ARGV + ["--yes"], run=ResetRun(), admin=False)
        self.assertEqual(code, 3)
        self.assertEqual(run.mutating(), [])

    def test_runs_disable_then_enable(self):
        code, out, err, run = call(ARGV + ["--yes"], run=ResetRun(), admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(pnputil(run), [["/disable-device", DEV], ["/enable-device", DEV]])
        self.assertIn("after:", out)

    def test_stuck_command_is_stopped_first_and_failure_to_stop_is_not_fatal(self):
        stuck = [{"Pid": 4242, "Command": "pnputil /restart-device " + DEV, "Seconds": 600}]
        run = ResetRun(stuck=stuck, fail={"taskkill": (128, "", "not found")})
        code, out, err, run = call(ARGV + ["--yes"], run=run, admin=True)
        self.assertEqual(code, 0, err)
        order = [c[0] for c in run.mutating()]
        self.assertEqual(order, ["taskkill", "pnputil", "pnputil"])
        self.assertIn("stuck, it will be stopped", out)
        self.assertIn("could not stop it", out)

    def test_young_process_is_left_alone(self):
        stuck = [{"Pid": 7, "Command": "pnputil /scan-devices " + DEV, "Seconds": 2}]
        code, out, err, run = call(ARGV + ["--yes"], run=ResetRun(stuck=stuck), admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual([c[0] for c in run.mutating()], ["pnputil", "pnputil"])
        self.assertIn("left alone", out)

    def test_protected_class_is_refused_unless_forced(self):
        argv = ["usb-reset", "--vid", "093A", "--pid", "2510"]
        code, out, err, run = call(argv + ["--yes"], run=ResetRun(), admin=True)
        self.assertEqual(code, 2)
        self.assertEqual(run.mutating(), [])
        code, out, err, run = call(argv + ["--yes", "--force"], run=ResetRun(), admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(pnputil(run)), 2)

    def test_hub_option_restarts_the_hub_and_lists_what_is_behind_it(self):
        code, out, err, run = call(ARGV + ["--hub", "--yes"], run=ResetRun(), admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(pnputil(run), [["/disable-device", HUB], ["/enable-device", HUB]])
        self.assertIn("will be disconnected for a moment", out)

    def test_hub_with_a_keyboard_behind_it_is_refused_unless_forced(self):
        kids = [{"InstanceId": DEV, "Class": "", "Name": "Unknown device"},
                {"InstanceId": "USB\\VID_046D&PID_C534\\K", "Class": "HIDClass", "Name": "Keyboard"}]
        code, out, err, run = call(ARGV + ["--hub", "--yes"], run=ResetRun(kids=kids), admin=True)
        self.assertEqual(code, 2)
        self.assertIn("Keyboard", err)
        self.assertEqual(run.mutating(), [])
        code, out, err, run = call(ARGV + ["--hub", "--yes", "--force"], run=ResetRun(kids=kids), admin=True)
        self.assertEqual(code, 0, err)

    def test_hub_option_on_a_root_port_is_refused(self):
        root_only = [{"InstanceId": ROOT, "Class": "USB", "Name": "Root hub", "Service": "USBHUB3"}]
        code, out, err, run = call(ARGV + ["--hub", "--yes"], run=ResetRun(parents=root_only), admin=True)
        self.assertEqual(code, 2)
        self.assertIn("never restarts the USB controller", err)
        self.assertEqual(run.mutating(), [])

    def test_failing_disable_is_a_driver_error(self):
        run = ResetRun(fail={"/disable-device": (1, "", "access denied")})
        code, out, err, run = call(ARGV + ["--yes"], run=run, admin=True)
        self.assertEqual(code, 6)
        self.assertEqual(len(pnputil(run)), 1)           # l'enable non parte dopo un disable fallito

    def test_timeout_of_a_command_points_to_usb_reset(self):
        run = ResetRun(fail={"/enable-device": (cli.RC_TIMEOUT, "", "timed out after 180 s and was stopped")})
        code, out, err, run = call(ARGV + ["--yes"], run=run, admin=True)
        self.assertEqual(code, 6)
        self.assertIn("timed out", err)
        self.assertIn("fili usb-reset", out)

    def test_device_that_does_not_come_back_is_reported(self):
        gone = [d for d in DEVICES if d["InstanceId"] != DEV]
        code, out, err, run = call(ARGV + ["--yes"], run=ResetRun(after=gone), admin=True)
        self.assertEqual(code, 6)
        self.assertIn("not listed after the reset", err)

    def test_json_output_carries_the_stuck_list(self):
        stuck = [{"Pid": 5, "Command": "pnputil", "Seconds": 100}]
        code, out, err, run = call(["--json"] + ARGV + ["--dry-run"], run=ResetRun(stuck=stuck), admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["data"]["stuck"][0]["Pid"], 5)


class TestTimeouts(unittest.TestCase):
    def test_a_command_that_never_ends_is_stopped_with_the_timeout_code(self):
        with mock.patch.object(cli, "COMMAND_TIMEOUTS", {"python": 1}):
            res = cli.run_command([sys.executable, "-c", "import time; time.sleep(30)"])
        self.assertEqual(res.returncode, cli.RC_TIMEOUT)
        self.assertIn("timed out after 1 s", res.stderr)

    def test_a_command_without_a_limit_is_not_touched(self):
        with mock.patch.object(cli, "COMMAND_TIMEOUTS", {}):
            res = cli.run_command([sys.executable, "-c", "print('ok')"])
        self.assertEqual((res.returncode, res.stdout.strip()), (0, "ok"))

    def test_pnputil_and_wdi_simple_have_a_limit(self):
        self.assertIn("pnputil", cli.COMMAND_TIMEOUTS)
        self.assertIn("wdi-simple", cli.COMMAND_TIMEOUTS)

    def test_restore_that_times_out_suggests_usb_reset(self):
        run = FakeRun(fail={"/scan-devices": (cli.RC_TIMEOUT, "", "timed out after 180 s and was stopped")})
        code, out, err, run = call(["restore", "--vid", "0483", "--pid", "374B", "--iface", "0", "--yes"],
                                   run=run, admin=True)
        self.assertEqual(code, 6)
        self.assertIn("fili usb-reset", out)


if __name__ == "__main__":
    unittest.main()
