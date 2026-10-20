"""Test del contatore di avanzamento di install/reinstall/restore (CLI e funzione 'progress' usata dalla GUI).
Nulla tocca il sistema: ogni comando esterno passa da un esecutore finto.

Esecuzione:  python -I tests/test_progress.py        (dalla radice del repository)
"""

import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_fili import DEVICES, FakeRun, call, fake_wdi  # noqa: E402  (disattiva anche l'esecutore vero)
from fili import guicore  # noqa: E402

SINGLE = ["install", "--vid", "0483", "--pid", "374B", "--iface", "0", "--driver", "winusb"]
X1 = r"USB\VID_AAAA&PID_0002\X1"
TWINS = ["install", "--vid", "AAAA", "--pid", "0002", "--driver", "winusb", "--instance", X1]
RESTORE = ["restore", "--vid", "0483", "--pid", "374B", "--iface", "0", "--yes"]
RESTORED = [dict(d, Service="usbvideo", InfPath="usbvideo.inf", Provider="Microsoft")
            if "VID_0483&PID_374B&MI_00" in d["InstanceId"] else d for d in DEVICES]
PUBLISHED = (0, "Published Name:     oem99.inf\n", "")
STEP = re.compile(r"^\[(\d+)/(\d+)\] (.+)$", re.M)


def steps(err):
    return [(int(a), int(b), t) for a, b, t in STEP.findall(err)]


class TestCliProgress(unittest.TestCase):
    def test_single_device_has_two_steps_on_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err, run = call(SINGLE + ["--wdi", fake_wdi(tmp), "--yes"], admin=True)
        self.assertEqual(code, 0, err)
        self.assertEqual([(a, b) for a, b, _ in steps(err)], [(1, 2), (2, 2)])
        self.assertNotRegex(out, STEP)  # stdout resta quello di sempre

    def test_twins_have_four_steps_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = FakeRun(fail={"/add-driver": PUBLISHED})
            code, out, err, run = call(TWINS + ["--wdi", fake_wdi(tmp), "--yes"], run=run, admin=True)
        self.assertEqual(code, 0, err)
        got = steps(err)
        self.assertEqual([(a, b) for a, b, _ in got], [(1, 4), (2, 4), (3, 4), (4, 4)])
        self.assertIn("wdi-simple", got[0][2])
        self.assertIn("driver store", got[1][2])
        self.assertIn("this device only", got[2][2])
        self.assertIn("checking", got[3][2])

    def test_restore_counts_one_step_per_command_plus_the_check(self):
        code, out, err, run = call(RESTORE, run=FakeRun(after=RESTORED), admin=True)
        self.assertEqual(code, 0, err)
        got = steps(err)
        self.assertGreaterEqual(len(got), 2)
        total = got[0][1]
        self.assertEqual([a for a, _, _ in got], list(range(1, total + 1)))
        self.assertEqual(got[-1][2], "checking the result")

    def test_nothing_printed_with_json_silent_or_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            wdi = fake_wdi(tmp)
            for extra in (["--json"], ["--silent"], ["--dry-run"]):
                code, out, err, run = call(SINGLE + ["--wdi", wdi, "--yes"] + extra, admin=True)
                self.assertEqual(code, 0, (extra, err))
                self.assertEqual(steps(err), [], extra)
            code, out, err, run = call(["--json"] + SINGLE + ["--wdi", wdi, "--yes"], admin=True)
            self.assertTrue(json.loads(out)["ok"])  # il JSON resta un unico documento valido

    def test_failure_stops_the_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = FakeRun(fail={"/add-driver": (1, "", "boom")})
            code, out, err, run = call(TWINS + ["--wdi", fake_wdi(tmp), "--yes"], run=run, admin=True)
        self.assertEqual(code, 6)
        self.assertEqual([(a, b) for a, b, _ in steps(err)], [(1, 4), (2, 4)])


class TestProgressCallback(unittest.TestCase):
    def test_callback_replaces_stderr_output(self):
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err, run = call(TWINS + ["--wdi", fake_wdi(tmp), "--yes"],
                                       run=FakeRun(fail={"/add-driver": PUBLISHED}), admin=True,
                                       progress=lambda d, t, text: seen.append((d, t, text)))
        self.assertEqual(code, 0, err)
        self.assertEqual([(d, t) for d, t, _ in seen], [(1, 4), (2, 4), (3, 4), (4, 4)])
        self.assertEqual(steps(err), [])

    def test_guicore_forwards_progress_to_apply(self):
        seen = []

        def fake_main(argv, **kw):
            seen.append((argv, kw))
            kw["out"].write(json.dumps({"ok": True, "exit_code": 0, "data": None, "messages": []}))
            return 0
        cb = lambda d, t, text: None  # noqa: E731
        guicore.apply(["restore"], main=fake_main, progress=cb)
        self.assertIs(seen[0][1]["progress"], cb)
        self.assertIn("--yes", seen[0][0])

    def test_label(self):
        self.assertEqual(guicore.progress_label(2, 4, "adding", 12.7), "Step 2 of 4: adding (12 s)")


if __name__ == "__main__":
    unittest.main()
