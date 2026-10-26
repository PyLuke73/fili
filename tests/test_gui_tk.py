"""Test della finestra vera (tkinter): crea l'App, seleziona righe, preme pulsanti e caselle.
Nulla tocca il sistema: i comandi passano da un esecutore finto, le finestre di conferma sono risposte da codice,
il browser e il salvataggio non si aprono. Serve un desktop con tkinter (altrimenti i test sono saltati).

Come gira: l'App è creata nel thread principale e questo esegue il vero mainloop(), come nell'app; il corpo di ogni
test gira in un altro thread e tocca i widget da lì (tkinter inoltra le chiamate al thread di Tk). Così i thread di
lavoro dell'App si comportano come nell'uso reale (leggono variabili Tk e chiamano after()).

Esecuzione:  python -I tests/test_gui_tk.py        (dalla radice del repository)
"""

import gc
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_fili import DEVICES, FakeRun, fake_wdi  # noqa: E402  (disattiva anche l'esecutore vero)

from fili import cli, guicore, updates  # noqa: E402

try:
    import tkinter as tk
    from tkinter import ttk
    from fili import gui
    _r = tk.Tk()
    _r.destroy()
    HAVE_TK = True
except Exception:  # niente tkinter o nessun desktop
    HAVE_TK = False

TWIN_X1 = "USB\\VID_AAAA&PID_0002\\X1"


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


@unittest.skipUnless(HAVE_TK, "tkinter o desktop non disponibili")
class GuiCase(unittest.TestCase):
    admin = True

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_ = FakeRun()
        self.dialogs = []          # (tipo, titolo, testo)
        self.answer = True         # risposta di askyesno
        self.opened = []           # url aperti
        self.save_path = os.path.join(self.tmp.name, "out.txt")
        self.releases = []         # le Release che 'GitHub' restituisce (nessuna richiesta di rete nei test)
        self.settings_env = {"APPDATA": os.path.join(self.tmp.name, "appdata")}
        self.env = {"FILI_WDI": fake_wdi(self.tmp.name)}
        real_call = guicore.call

        def fake_call(argv, main=cli.main, **kw):
            base = dict(run=self.run_, is_admin=lambda: self.admin, env=self.env)
            base.update(kw)
            return real_call(argv, main, **base)

        def record(kind):
            def fn(title=None, message=None, **kw):
                self.dialogs.append((kind, title, message))
                return True
            return fn

        patches = [
            mock.patch.object(guicore, "call", fake_call),
            mock.patch.object(guicore, "is_admin", lambda: self.admin),
            mock.patch.object(gui.messagebox, "showinfo", record("info")),
            mock.patch.object(gui.messagebox, "showwarning", record("warning")),
            mock.patch.object(gui.messagebox, "showerror", record("error")),
            mock.patch.object(gui.messagebox, "askyesno",
                              lambda *a, **k: (self.dialogs.append(("askyesno", a, k)), self.answer)[1]),
            mock.patch.object(gui.filedialog, "asksaveasfilename", lambda **k: self.save_path),
            mock.patch.object(updates, "fetch_releases", lambda *a, **k: self.releases),
            mock.patch.object(gui.App, "env", self.settings_env),
            mock.patch.object(gui.webbrowser, "open", lambda url, *a, **k: self.opened.append(url)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        # la prima lettura dell'elenco parte dal test (start), non dal costruttore: prima del mainloop il thread di
        # lavoro non potrebbe leggere le variabili Tk
        with mock.patch.object(gui.App, "background", lambda app, work, done: None):
            self.app = gui.App()
        self.app.withdraw()
        self.addCleanup(self.close)
        self.finished = False

    def _callTestMethod(self, method):
        errors = []

        def body():
            try:
                method()
            except BaseException as e:  # riportata nel thread principale
                errors.append(e)
            finally:
                self.finished = True

        worker = threading.Thread(target=body, daemon=True)

        def poll():
            if self.finished:
                self.app.quit()
            else:
                self.app.after(20, poll)
        self.app.after(20, poll)
        worker.start()
        self.app.mainloop()
        worker.join(5)
        if errors:
            raise errors[0]

    def start(self, run=None):
        """Imposta l'esecutore finto e legge l'elenco, come fa la finestra all'avvio."""
        if run is not None:
            self.run_ = run
        self.app.refresh()
        self.assertTrue(self.pump(lambda: self.app.devices), "l'elenco dei dispositivi non si è riempito: " + self.text())
        return self.app

    def close(self):
        """Chiude la finestra nel thread principale. Le variabili Tk dell'App vengono staccate dall'interprete prima:
        se le liberasse il garbage collector dopo destroy() (o da un altro thread) tkinter stamperebbe errori."""
        for value in list(vars(self.app).values()):
            if isinstance(value, tk.Variable):
                value._tk = None
        try:
            self.app.destroy()
        except tk.TclError:
            pass
        gc.collect()

    # -- aiuti ------------------------------------------------------------------------------
    def pump(self, cond, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.02)
        return False

    def idle(self):
        self.assertTrue(self.pump(lambda: not self.app.busy), "la finestra è rimasta occupata")

    def widget(self, cls, text):
        for w in walk(self.app):
            if isinstance(w, cls):
                try:
                    if w.cget("text") == text:
                        return w
                except tk.TclError:
                    pass
        self.fail("nessun %s con testo '%s'" % (cls.__name__, text))

    def button(self, text):
        return self.widget(ttk.Button, text)

    def press(self, text):
        self.button(text).invoke()

    def select(self, vid, pid, mi=None, instance=None):
        for i, d in enumerate(self.app.devices):
            if instance and d["instance_id"].lower() == instance.lower():
                break
            if not instance and d["vid"] == vid and d["pid"] == pid and d["mi"] == mi:
                break
        else:
            self.fail("dispositivo non trovato")
        self.app.tree.selection_set(str(i))

    def text(self):
        return self.app.log.get("1.0", "end-1c")

    def mutating(self):
        return self.run_.mutating()


class TestStartup(GuiCase):
    def test_title_rows_and_no_admin_banner(self):
        app = self.start()
        self.assertTrue(app.title().startswith("fili "))
        ids = [d["instance_id"] for d in app.devices]
        self.assertIn("USB\\VID_0483&PID_374B&MI_00\\6&AA&0&0000", ids)
        self.assertNotIn("USB\\ROOT_HUB30\\4&1&0&0", ids)           # senza VID/PID: saltato
        self.assertEqual(len(app.tree.get_children()), len(app.devices))
        self.assertFalse([w for w in walk(app) if isinstance(w, ttk.Button) and w.cget("text") == "Restart as Administrator"])

    def test_list_and_log_are_not_hidden_under_their_scroll_frame(self):
        # Un widget gestito "in_" un frame creato dopo di lui resta sotto il frame: elenco e testi risultano vuoti.
        app = self.start()
        for w in (app.tree, app.log):
            frame = w.grid_info()["in"]
            order = list(w.master.winfo_children())
            self.assertGreater(order.index(w), order.index(frame), w)

    def test_buttons_carry_the_icons_of_the_set(self):
        app = self.start()
        for text in ("Install", "Reinstall", "Restore", "Restart", "Diagnose", "Certificates", "Licenses", "Save output...", "Help",
                     "About", "Refresh", "Ko-fi"):
            b = self.widget(ttk.Button, text)
            self.assertTrue(str(b.cget("image")), text)
        self.assertEqual(len(app.images), 18)

    def test_show_hubs_refreshes_with_the_flag(self):
        app = self.start()
        before = len(app.devices)
        self.widget(ttk.Checkbutton, "Show hubs").invoke()
        self.idle()
        self.assertGreater(len(app.devices), before)
        self.assertTrue(app.hubs.get())

    def test_refresh_button_rereads_the_list(self):
        self.start()
        n = self.run_.enumerations
        self.press("Refresh")
        self.idle()
        self.assertGreater(self.run_.enumerations, n)


class TestSelectionAndGuards(GuiCase):
    def test_actions_without_a_selection_say_so_and_run_nothing(self):
        self.start()
        for name in ("Install", "Reinstall", "Restore", "Restart"):
            self.press(name)
        self.assertEqual([d[0] for d in self.dialogs], ["info"] * 4)
        self.assertTrue(all("Select a device first" in d[2] for d in self.dialogs))
        self.assertEqual(self.mutating(), [])

    def test_buttons_are_disabled_while_busy_and_enabled_after(self):
        app = self.start()
        gate = threading.Event()
        done = []
        app.background(gate.wait, lambda r: done.append(r))
        self.pump(lambda: "disabled" in self.button("Install").state())
        self.assertIn("disabled", self.button("Install").state())
        self.assertIn("disabled", self.button("Diagnose").state())
        gate.set()
        self.assertTrue(self.pump(lambda: done))
        self.assertNotIn("disabled", self.button("Install").state())

    def test_second_background_job_is_ignored_while_busy(self):
        app = self.start()
        gate, ran = threading.Event(), []
        app.background(gate.wait, lambda r: None)
        app.background(lambda: ran.append(1), lambda r: None)
        gate.set()
        self.idle()
        self.assertEqual(ran, [])


class TestInstallFlow(GuiCase):
    def pick_probe(self):
        self.select(0x483, 0x374B, 0)

    def test_preview_asks_and_cancel_runs_nothing(self):
        self.start()
        self.pick_probe()
        self.answer = False
        self.press("Install")
        self.idle()
        self.assertIn("dry-run", self.text())
        self.assertEqual(self.mutating(), [])
        asks = [d for d in self.dialogs if d[0] == "askyesno"]
        self.assertEqual(len(asks), 1)
        self.assertIn("0483:374B", asks[0][1][1])
        self.assertIn("self-signed certificate", asks[0][1][1])

    def test_confirm_runs_the_command_and_the_progress_bar_finishes(self):
        app = self.start()
        self.pick_probe()
        self.app.driver.set("winusb")
        self.answer = True
        self.press("Install")
        self.assertTrue(self.pump(lambda: self.mutating()), "nessun comando eseguito dopo la conferma")
        self.idle()
        self.assertTrue(self.pump(lambda: app.prog_text.get() == "Done."), app.prog_text.get())
        self.assertEqual(float(app.prog_bar.cget("value")), float(app.prog_bar.cget("maximum")))
        self.assertIn("exit code 0", self.text())
        self.assertEqual(self.mutating()[0][0], self.env["FILI_WDI"])

    def test_options_reach_the_command_line(self):
        app = self.start()
        self.pick_probe()
        app.driver.set("libusbk")
        app.name.set("  Mia scheda ")
        app.wcid.set(True)
        self.answer = False
        self.press("Install")
        self.idle()
        text = self.text()
        self.assertIn("-t 2", text)                    # libusbK
        self.assertIn("Mia scheda", text)
        self.assertNotIn("-t 2 --", text)

    def test_protected_class_is_refused_with_no_confirmation(self):
        self.start()
        self.select(0x093A, 0x2510)
        self.press("Install")
        self.idle()
        self.assertFalse([d for d in self.dialogs if d[0] == "askyesno"])
        self.assertIn("exit code 2", self.text())
        self.assertEqual(self.mutating(), [])

    def test_force_checkbox_lifts_the_protection_in_the_preview(self):
        app = self.start()
        self.select(0x093A, 0x2510)
        app.force.set(True)
        self.answer = False
        self.press("Install")
        self.idle()
        self.assertIn("exit code 0", self.text())
        self.assertTrue([d for d in self.dialogs if d[0] == "askyesno"])
        self.assertEqual(self.mutating(), [])


class TestNotElevated(GuiCase):
    admin = False

    def test_banner_and_elevate_button(self):
        app = self.start()
        self.button("Restart as Administrator")
        labels = [w.cget("text") for w in walk(app) if isinstance(w, ttk.Label)]
        self.assertTrue(any("Not elevated" in t for t in labels))

    def test_install_warns_and_never_asks_to_confirm(self):
        self.start()
        self.select(0x483, 0x374B, 0)
        self.press("Install")
        self.idle()
        self.assertEqual([d[0] for d in self.dialogs], ["warning"])
        self.assertIn("Administrator", self.dialogs[0][2])
        self.assertEqual(self.mutating(), [])


class TestRestoreAllMatching(GuiCase):
    def twin_run(self):
        """Finto che, come il sistema vero, ripristina i gemelli quando vede 'pnputil /delete-driver'."""
        back = [dict(d, InfPath="usb.inf", Service="vendor_drv", Provider="Vendor")
                if d["InstanceId"].startswith("USB\VID_AAAA&PID_0002") else d for d in DEVICES]

        class Run(FakeRun):
            def __call__(self, cmd):
                if cmd[:2] == ["pnputil", "/delete-driver"]:
                    self.devices_json = back
                return super().__call__(cmd)
        return Run()

    def test_restore_refuses_a_shared_package_without_the_box(self):
        self.start()
        self.select(None, None, instance=TWIN_X1)
        self.press("Restore")
        self.idle()
        self.assertIn("exit code 2", self.text())
        self.assertIn("restore --all-matching", self.text())
        self.assertFalse([d for d in self.dialogs if d[0] == "askyesno"])
        self.assertEqual(self.mutating(), [])

    def test_restore_with_all_matching_removes_the_shared_package(self):
        app = self.start(run=self.twin_run())
        self.select(None, None, instance=TWIN_X1)
        app.all_matching.set(True)
        self.answer = True
        self.press("Restore")
        self.assertTrue(self.pump(lambda: self.mutating()), self.text())
        self.idle()
        self.assertEqual([c[1] for c in self.mutating()], ["/delete-driver", "/scan-devices"])
        self.assertIn("exit code 0", self.text())


class TestReadOnlyButtons(GuiCase):
    def test_certificates_licenses_and_diagnose_fill_the_box(self):
        self.start()
        self.press("Certificates")
        self.idle()
        self.assertIn("A" * 40, self.text())
        self.assertIn("fili cert-remove --thumbprint", self.text())
        self.press("Licenses")
        self.idle()
        self.assertIn("libwdi", self.text())
        self.select(0x416, 0x9391)
        self.press("Diagnose")
        self.idle()
        self.assertIn("0416", self.text())
        self.assertEqual(self.mutating(), [])

    def test_save_output_writes_the_box_and_warns_when_empty(self):
        app = self.start()
        app.write("")
        app.save_output()
        self.assertEqual(self.dialogs[-1][0], "info")
        self.assertIn("Nothing to save", self.dialogs[-1][2])
        self.press("Licenses")
        self.idle()
        app.save_output()
        with open(self.save_path, encoding="utf-8") as f:
            self.assertEqual(f.read().rstrip("\n"), self.text())

    def test_copy_row_puts_the_row_and_instance_on_the_clipboard(self):
        app = self.start()
        self.select(0x483, 0x374B, 0)
        app.copy_row()
        clip = app.clipboard_get()
        self.assertIn("0483:374B", clip)
        self.assertIn("USB\\VID_0483&PID_374B&MI_00", clip)

    def test_help_about_and_kofi(self):
        app = self.start()
        self.press("Help")
        self.press("About")
        wins = [w for w in walk(app) if isinstance(w, tk.Toplevel)]
        self.assertEqual(len(wins), 2)
        texts = [w.winfo_children() and "".join(t.get("1.0", "end") for t in walk(w) if isinstance(t, tk.Text)) for w in wins]
        self.assertTrue(any("DEVICE LIST" in t for t in texts))
        self.assertTrue(any("GPL" in t for t in texts))
        self.press("Ko-fi")
        self.assertEqual(self.opened, [guicore.KOFI_URL])

    def test_menu_has_save_exit_help(self):
        app = self.start()
        menu = app.nametowidget(app.cget("menu"))
        labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1) if menu.type(i) == "cascade"]
        self.assertEqual(labels, ["File", "Help"])


REL = [{"tag_name": "v9.0.0", "html_url": "https://github.com/PyLuke73/fili/releases/tag/v9.0.0", "prerelease": False,
        "draft": False, "published_at": "2030-01-01T00:00:00Z"}]


class TestUpdates(GuiCase):
    def invoke(self, label):
        menu = self.app.nametowidget(self.app.cget("menu"))
        help_menu = menu.nametowidget(menu.entrycget(menu.index("end"), "menu"))
        for i in range(help_menu.index("end") + 1):
            if help_menu.type(i) != "separator" and help_menu.entrycget(i, "label") == label:
                help_menu.invoke(i)
                return
        self.fail(label)

    def test_nothing_contacts_the_network_by_default(self):
        calls = []
        with mock.patch.object(updates, "fetch_releases", lambda *a, **k: calls.append(1) or []):
            app = self.start()
            time.sleep(0.3)
        self.assertEqual(calls, [])
        self.assertFalse(app.auto_update.get())
        self.assertFalse(app.update_btn.winfo_manager())

    def test_manual_check_with_a_newer_version_offers_the_download_page(self):
        self.releases = REL
        app = self.start()
        self.invoke("Check for updates...")
        self.assertTrue(self.pump(lambda: any(d[0] == "askyesno" for d in self.dialogs)))
        self.assertIn("9.0.0", str(self.dialogs[-1][1]))
        self.assertEqual(self.opened, [REL[0]["html_url"]])
        self.assertIn("9.0.0", app.update_btn.cget("text"))

    def test_manual_check_when_up_to_date(self):
        self.releases = [dict(REL[0], tag_name="v0.0.1", html_url="https://github.com/PyLuke73/fili/releases/tag/v0.0.1")]
        self.start()
        self.invoke("Check for updates...")
        self.assertTrue(self.pump(lambda: any(d[0] == "info" for d in self.dialogs)))
        self.assertIn("latest version", self.dialogs[-1][2])
        self.assertEqual(self.opened, [])

    def test_manual_check_reports_a_network_error(self):
        def boom(*a, **k):
            raise updates.UpdateError("cannot reach GitHub: offline")
        self.start()
        with mock.patch.object(updates, "fetch_releases", boom):
            self.invoke("Check for updates...")
            self.assertTrue(self.pump(lambda: any(d[0] == "error" for d in self.dialogs)))
        self.assertIn("offline", self.dialogs[-1][2])

    def test_startup_box_is_saved(self):
        app = self.start()
        self.invoke("Check for updates at startup")
        self.assertTrue(app.auto_update.get())
        self.assertIs(updates.load_settings(self.settings_env).get("check_updates"), True)

    def test_automatic_check_is_silent_and_shows_a_button(self):
        self.releases = REL
        updates.save_settings(self.settings_env, check_updates=True)
        app = self.start()
        app.check_updates(manual=False)
        self.assertTrue(self.pump(lambda: app.update_btn.winfo_manager()))
        self.assertEqual([d for d in self.dialogs if d[0] in ("info", "askyesno", "error")], [])
        self.assertIsInstance(updates.load_settings(self.settings_env).get("last_check"), float)
        app.update_btn.invoke()
        self.assertEqual(self.opened, [REL[0]["html_url"]])

    def test_automatic_check_ignores_network_errors(self):
        def boom(*a, **k):
            raise updates.UpdateError("offline")
        app = self.start()
        with mock.patch.object(updates, "fetch_releases", boom):
            app.check_updates(manual=False)
            time.sleep(0.5)
        self.assertEqual(self.dialogs, [])


if __name__ == "__main__":
    unittest.main()
