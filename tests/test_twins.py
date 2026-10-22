"""Test di 'install'/'reinstall' con dispositivi identici (VID:PID uguali): casi di errore e di ripiego.
Nulla tocca il sistema: ogni comando esterno passa da un esecutore finto.

Esecuzione:  python -I tests/test_twins.py        (dalla radice del repository)
"""

import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_fili import FakeRun, call, fake_wdi  # noqa: E402  (disattiva anche l'esecutore vero)

X1 = "USB\\VID_AAAA&PID_0002\\X1"
ARGV = ["install", "--vid", "AAAA", "--pid", "0002", "--driver", "winusb", "--instance", X1]
PUBLISHED = (0, "Published Name:     oem99.inf\n", "")


class WdiFailsOnce(FakeRun):
    """Il primo wdi-simple fallisce con il codice dato, i successivi riescono."""

    def __init__(self, wdi, rc, **kw):
        super().__init__(**kw)
        self.wdi, self.rc, self.wdi_calls = wdi, rc, 0

    def __call__(self, cmd):
        if cmd[0] == self.wdi:
            self.calls.append(list(cmd))
            self.wdi_calls += 1
            if self.wdi_calls == 1:
                return types.SimpleNamespace(returncode=self.rc, stdout="", stderr="")
            return types.SimpleNamespace(returncode=0, stdout="ok\n", stderr="")
        return super().__call__(cmd)


class TestTwinsRetry(unittest.TestCase):
    def test_needs_admin_error_is_retried_in_a_fresh_folder(self):
        """Con dei gemelli il ritentativo di -15 deve estrarre di nuovo e usare la cartella del secondo tentativo."""
        with tempfile.TemporaryDirectory() as tmp:
            wdi = fake_wdi(tmp)
            run = WdiFailsOnce(wdi, 0xFFFFFFF1)
            run.fail = {"/add-driver": PUBLISHED}
            code, out, err, run = call(ARGV + ["--wdi", wdi, "--yes"], run=run, admin=True)
            self.assertEqual(code, 0, err)
            wdi_calls = [c for c in run.calls if c[0] == wdi]
            self.assertEqual(len(wdi_calls), 2)
            for c in wdi_calls:
                self.assertIn("-x", c)
            first, second = (c[c.index("-d") + 1] for c in wdi_calls)
            self.assertNotEqual(first, second)
            stage = [c for c in run.calls if c[:2] == ["pnputil", "/add-driver"]]
            self.assertEqual(len(stage), 1)
            self.assertEqual(os.path.dirname(stage[0][2]), second)
            self.assertIn("Retrying once", out)


class TestTwinsStage(unittest.TestCase):
    def test_stage_without_a_published_name_stops_before_binding(self):
        """pnputil esce con 0 ma l'output non contiene oemNN.inf (output inatteso): non si associa nulla."""
        with tempfile.TemporaryDirectory() as tmp:
            run = FakeRun(fail={"/add-driver": (0, "Driver package added successfully.\n", "")})
            code, out, err, run = call(ARGV + ["--wdi", fake_wdi(tmp), "--yes"], run=run, admin=True)
            self.assertEqual(code, 6)
            self.assertIn("driver store", err)
            self.assertFalse([c for c in run.mutating() if "-EncodedCommand" in c])


class TestTwinsAllMatching(unittest.TestCase):
    def test_all_matching_runs_wdi_once_and_nothing_else(self):
        """--all-matching: una sola chiamata a wdi-simple, senza -x, e nessun pnputil né associazione per istanza."""
        with tempfile.TemporaryDirectory() as tmp:
            wdi = fake_wdi(tmp)
            code, out, err, run = call(ARGV + ["--all-matching", "--wdi", wdi, "--yes"], admin=True)
            self.assertEqual(code, 0, err)
            calls = run.mutating()
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], wdi)
            self.assertNotIn("-x", calls[0])
            self.assertFalse([c for c in run.calls if c[0] == "pnputil"])
            self.assertFalse([c for c in run.calls if "-EncodedCommand" in c])
            self.assertIn("will be changed TOO", out)


class TestTwinsRestoreAllMatching(unittest.TestCase):
    """Dopo 'install --all-matching' i gemelli condividono un pacchetto: 'restore --all-matching' lo annulla."""

    ARGV = ["restore", "--vid", "AAAA", "--pid", "0002", "--instance", X1]

    @staticmethod
    def _twins():
        from fili import devices
        from test_fili import DEVICES
        return devices.parse_device_list(__import__("json").dumps(DEVICES)), devices

    def test_plan_refuses_shared_package_without_the_flag_and_hints_at_it(self):
        from fili import ops
        devs, devices = self._twins()
        x1 = devices.select_target(devs, 0xAAAA, 0x0002, None, X1)
        with self.assertRaises(ValueError) as cm:
            ops.restore_plan(x1, devs)
        self.assertIn("restore --all-matching", str(cm.exception))

    def test_plan_with_the_flag_accepts_identical_devices_only(self):
        import json
        from fili import ops
        from test_fili import DEVICES
        devs, devices = self._twins()
        x1 = devices.select_target(devs, 0xAAAA, 0x0002, None, X1)
        plan = ops.restore_plan(x1, devs, all_matching=True)
        self.assertEqual(plan[0][:3], ["pnputil", "/delete-driver", "oem7.inf"])
        # un dispositivo DIVERSO sullo stesso pacchetto resta un motivo di rifiuto, anche con il flag
        stranger = dict(DEVICES[0], InstanceId="USB\\VID_BBBB&PID_0009\\Z1", InfPath="oem7.inf", Service="WinUSB")
        devs2 = devices.parse_device_list(json.dumps(DEVICES + [stranger]))
        x1b = devices.select_target(devs2, 0xAAAA, 0x0002, None, X1)
        with self.assertRaises(ValueError) as cm:
            ops.restore_plan(x1b, devs2, all_matching=True)
        self.assertIn("VID_BBBB", str(cm.exception))
        self.assertNotIn("VID_AAAA&PID_0002\\X2", str(cm.exception))

    def test_cli_refuses_then_succeeds_with_the_flag(self):
        import json
        from test_fili import DEVICES
        code, out, err, run = call(self.ARGV + ["--yes"], admin=True)
        self.assertEqual(code, 2)
        self.assertEqual(run.mutating(), [])
        self.assertIn("--all-matching", err)
        back = [dict(d, InfPath="usb.inf", Service="vendor_drv", Provider="Vendor")
                if d["InstanceId"].startswith("USB\\VID_AAAA&PID_0002") else d for d in DEVICES]
        run = FakeRun(after=back)
        code, out, err, run = call(self.ARGV + ["--all-matching", "--yes"], run=run, admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual([c[1] for c in run.mutating()], ["/delete-driver", "/scan-devices"])
        self.assertIn("TOO", out)
        self.assertIn("USB\\VID_AAAA&PID_0002\\X2", out)

    def test_dry_run_with_the_flag_changes_nothing(self):
        code, out, err, run = call(self.ARGV + ["--all-matching", "--dry-run"], admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(run.mutating(), [])


class TestTwinsReinstall(unittest.TestCase):
    def test_reinstall_keeps_the_current_driver_on_one_instance(self):
        """reinstall con gemelli: stesso driver di prima (WinUSB, -t 0), ma solo sull'istanza scelta."""
        argv = ["reinstall", "--vid", "AAAA", "--pid", "0002", "--instance", X1]
        with tempfile.TemporaryDirectory() as tmp:
            wdi = fake_wdi(tmp)
            run = FakeRun(fail={"/add-driver": PUBLISHED})
            code, out, err, run = call(argv + ["--wdi", wdi, "--yes"], run=run, admin=True)
            self.assertEqual(code, 0, err)
            calls = run.mutating()
            self.assertEqual(calls[0][0], wdi)
            self.assertEqual(calls[0][calls[0].index("-t") + 1], "0")
            self.assertIn("-x", calls[0])
            self.assertEqual(calls[1][:2], ["pnputil", "/add-driver"])
            self.assertIn("-EncodedCommand", calls[2])
            self.assertEqual(len(calls), 3)
            self.assertIn("this instance only", out)


class TestTwinsWcid(unittest.TestCase):
    def test_exists_error_explains_wcid_and_stops(self):
        """WDI_ERROR_EXISTS con --wcid nel percorso per istanza: spiega il WCID e non va oltre wdi-simple."""
        with tempfile.TemporaryDirectory() as tmp:
            wdi = fake_wdi(tmp)
            run = FakeRun(fail={wdi: (0xFFFFFFF3, "", "")})
            code, out, err, run = call(ARGV + ["--wcid", "--wdi", wdi, "--yes"], run=run, admin=True)
            self.assertEqual(code, 6)
            self.assertIn("WCID", err)
            self.assertEqual(len([c for c in run.calls if c[0] == wdi]), 1)
            self.assertFalse([c for c in run.calls if c[0] == "pnputil"])
            self.assertFalse([c for c in run.calls if "-EncodedCommand" in c])


class TestBindScript(unittest.TestCase):
    DEV = types.SimpleNamespace(instance_id=X1)

    @staticmethod
    def _script(windir):
        import base64
        from fili import ops
        return base64.b64decode(ops.bind_command(TestBindScript.DEV, "oem99.inf", windir)[-1]).decode("utf-16-le")

    def test_apostrophe_in_windir_cannot_break_out_of_the_string(self):
        """windir viene da SystemRoot: un apice nel percorso va raddoppiato, non deve chiudere la stringa PowerShell."""
        script = self._script("C:\\Win'dows; calc; '")
        self.assertIn("C:\\Win''dows; calc; ''\\INF\\oem99.inf", script)
        self.assertNotIn("Win'dows", script)

    @unittest.skipUnless(sys.platform == "win32", "needs Windows PowerShell and .NET")
    def test_csharp_compiles(self):
        """Compila BIND_CSHARP con Add-Type (solo in memoria, senza chiamare Run): un errore di sintassi emergerebbe solo su hardware."""
        import subprocess
        from fili import ops
        script = ("$ErrorActionPreference = 'Stop'\n"
                  "Add-Type -TypeDefinition @'\n%s'@\n"
                  "if (-not ('FiliBind' -as [type])) { throw 'FiliBind missing' }\n"
                  "if (-not [FiliBind].GetMethod('Run')) { throw 'Run missing' }\n" % ops.BIND_CSHARP)
        res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
