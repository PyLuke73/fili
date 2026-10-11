"""Tests for scripts/package_wdi_bundle.py. They use a dummy file called wdi-simple.exe in a
temporary directory: no real binary, no network, nothing is installed."""

import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("package_wdi_bundle", os.path.join(ROOT, "scripts", "package_wdi_bundle.py"))
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)

DRIVERS = "WinUSB co-installer (WDK 10.0.x): Microsoft redistribution terms, checked on 2026-01-01\n"


def make(tmp):
    exe = os.path.join(tmp, "wdi-simple.exe")
    open(exe, "wb").write(b"MZ dummy")
    drv = os.path.join(tmp, "drivers.txt")
    open(drv, "w").write(DRIVERS)
    src = os.path.join(tmp, "src.tar.gz")
    open(src, "wb").write(b"fake source archive")
    return exe, drv, src


class TestBundle(unittest.TestCase):
    def test_complete_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe, drv, src = make(tmp)
            out = os.path.join(tmp, "bundle")
            self.assertEqual(pb.main(["--exe", exe, "--out", out, "--drivers-file", drv, "--source-archive", src]), 0)
            for rel in ["wdi-simple.exe", "LICENSE", "NOTICE", "LICENSES/LGPL-3.0.txt", "LICENSES/GPL-3.0.txt",
                        "docs/building-wdi-simple.md", "THIRD_PARTY/libwdi-SOURCE.txt",
                        "THIRD_PARTY/embedded-drivers.txt", "THIRD_PARTY/libwdi-1.5.1.tar.gz", "SHA256SUMS"]:
                self.assertTrue(os.path.isfile(os.path.join(out, rel)), rel)
            offer = open(os.path.join(out, "THIRD_PARTY", "libwdi-SOURCE.txt"), encoding="utf-8").read()
            self.assertIn("v1.5.1", offer)
            self.assertIn(pb.DEFAULT_COMMIT, offer)
            self.assertIn("Written offer", offer)
            self.assertIn("GNU Lesser General Public License", offer)

    def test_sha256sums_match_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe, drv, src = make(tmp)
            out = os.path.join(tmp, "bundle")
            pb.main(["--exe", exe, "--out", out, "--drivers-file", drv, "--source-archive", src])
            lines = open(os.path.join(out, "SHA256SUMS"), encoding="utf-8").read().strip().splitlines()
            self.assertGreaterEqual(len(lines), 9)
            for line in lines:
                digest, rel = line.split("  ", 1)
                data = open(os.path.join(out, rel), "rb").read()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest, rel)

    def test_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe, drv, src = make(tmp)
            out = os.path.join(tmp, "b")
            # no drivers list
            self.assertEqual(pb.main(["--exe", exe, "--out", out, "--source-archive", src]), 2)
            # empty drivers list
            empty = os.path.join(tmp, "e.txt"); open(empty, "w").write("x")
            self.assertEqual(pb.main(["--exe", exe, "--out", out, "--drivers-file", empty, "--source-archive", src]), 2)
            # no source and no download: the LGPL source is mandatory
            self.assertEqual(pb.main(["--exe", exe, "--out", out, "--drivers-file", drv, "--no-download"]), 2)
            # wrong executable name
            other = os.path.join(tmp, "other.exe"); open(other, "wb").write(b"x")
            self.assertEqual(pb.main(["--exe", other, "--out", out, "--drivers-file", drv, "--source-archive", src]), 2)
            # missing exe
            self.assertEqual(pb.main(["--exe", os.path.join(tmp, "nope.exe"), "--out", out,
                                      "--drivers-file", drv, "--source-archive", src]), 2)
            # another tag without its commit
            self.assertEqual(pb.main(["--exe", exe, "--out", out, "--drivers-file", drv, "--source-archive", src,
                                      "--libwdi-tag", "v1.6.0"]), 2)
            self.assertFalse(os.path.exists(os.path.join(out, "wdi-simple.exe")))

    def test_non_empty_output_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe, drv, src = make(tmp)
            out = os.path.join(tmp, "b"); os.makedirs(out)
            open(os.path.join(out, "x"), "w").write("keep")
            self.assertEqual(pb.main(["--exe", exe, "--out", out, "--drivers-file", drv, "--source-archive", src]), 2)
            self.assertTrue(os.path.isfile(os.path.join(out, "x")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
