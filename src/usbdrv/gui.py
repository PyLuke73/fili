"""usbdrv-gui: a small window over the same operations as the command line (tkinter, no extra dependency).

The window always shows the dry-run plan and asks for confirmation before the real run; the real run is the
CLI with --yes, so every safety rule of the CLI applies unchanged.
"""

import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Optional

from . import __version__, guicore

DRIVERS = ("winusb", "libusbk", "libusb-win32", "usbser")
COLUMNS = (("vidpid", "VID:PID", 90), ("mi", "Iface", 55), ("cls", "Class", 90), ("service", "Driver", 90),
           ("status", "Status", 70), ("name", "Name", 330))
WARNING = ("This replaces the driver of the selected device and adds a self-signed certificate to this PC's "
           "trusted stores (remove it later with 'usbdrv cert-remove'). Use only on devices you own.")


def scrolled(parent, widget) -> ttk.Frame:
    """Put a Text/Treeview in a frame with vertical and horizontal scroll bars; the caller packs the frame."""
    frame = ttk.Frame(parent)
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    widget.grid(in_=frame, row=0, column=0, sticky="nsew")
    vs = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
    hs = ttk.Scrollbar(frame, orient="horizontal", command=widget.xview)
    widget.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
    vs.grid(row=0, column=1, sticky="ns")
    hs.grid(row=1, column=0, sticky="ew")
    return frame


def copy_to_clipboard(widget, text: str) -> None:
    widget.clipboard_clear()
    widget.clipboard_append(text)


def make_text(parent, height: int = 12, wrap: str = "none") -> tk.Text:
    """A read-only Text with a right-click menu (Copy the selection / Select all)."""
    text = tk.Text(parent, height=height, wrap=wrap, state="disabled")
    menu = tk.Menu(text, tearoff=False)

    def selection() -> str:
        return text.get("sel.first", "sel.last") if text.tag_ranges("sel") else ""

    def select_all(event=None):
        text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def copy(event=None):
        copy_to_clipboard(text, selection())
        return "break"

    menu.add_command(label="Copy", command=copy)
    menu.add_command(label="Select all", command=select_all)

    def popup(event):
        text.focus_set()
        menu.entryconfigure("Copy", state="normal" if text.tag_ranges("sel") else "disabled")
        menu.tk_popup(event.x_root, event.y_root)

    text.bind("<Button-3>", popup)
    text.bind("<Control-a>", select_all)
    text.bind("<Control-c>", copy)
    text.bind("<Button-1>", lambda e: text.focus_set())
    return text


def show_text_window(parent, title: str, content: str, width: int = 100, height: int = 30) -> None:
    win = tk.Toplevel(parent)
    win.title(title)
    text = make_text(win, height, wrap="word")
    text.configure(width=width, state="normal")
    text.insert("end", content)
    text.configure(state="disabled")
    ttk.Button(win, text="Close", command=win.destroy).pack(side="bottom", pady=6)
    scrolled(win, text).pack(fill="both", expand=True, padx=6, pady=6)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("usbdrv %s" % __version__)
        self.geometry("920x560")
        self.devices: List[dict] = []
        self.busy = False

        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        self.hubs = tk.BooleanVar(value=False)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="right")
        ttk.Checkbutton(top, text="Show hubs", variable=self.hubs, command=self.refresh).pack(side="right", padx=8)
        if not guicore.is_admin():
            ttk.Label(top, text="Not elevated: you can look, but changes need Administrator.",
                      foreground="#a00").pack(side="left")
            ttk.Button(top, text="Restart as Administrator", command=self.elevate).pack(side="left", padx=8)

        self.tree = ttk.Treeview(self, columns=[c[0] for c in COLUMNS], show="headings", selectmode="browse", height=10)
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        scrolled(self, self.tree).pack(fill="both", expand=True, padx=6)
        self.tree_menu = tk.Menu(self.tree, tearoff=False)
        self.tree_menu.add_command(label="Copy row", command=self.copy_row)
        self.tree.bind("<Button-3>", self.tree_popup)

        opt = ttk.Frame(self, padding=6)
        opt.pack(fill="x")
        ttk.Label(opt, text="Driver").pack(side="left")
        self.driver = tk.StringVar(value=DRIVERS[0])
        ttk.Combobox(opt, textvariable=self.driver, values=DRIVERS, state="readonly", width=13).pack(side="left", padx=4)
        ttk.Label(opt, text="Name").pack(side="left", padx=(8, 0))
        self.name = tk.StringVar()
        ttk.Entry(opt, textvariable=self.name, width=24).pack(side="left", padx=4)
        self.wcid, self.filt, self.force = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        for text, var in (("WCID", self.wcid), ("Filter driver", self.filt), ("Force (protected class)", self.force)):
            ttk.Checkbutton(opt, text=text, variable=var).pack(side="left", padx=4)

        btn = ttk.Frame(self, padding=6)
        btn.pack(fill="x")
        self.buttons = []
        for text, action in (("Install", "install"), ("Reinstall", "reinstall"), ("Restore", "restore")):
            b = ttk.Button(btn, text=text, command=lambda a=action: self.act(a))
            b.pack(side="left", padx=2)
            self.buttons.append(b)
        for text, fn in (("Diagnose", self.diagnose), ("Certificates", self.certs), ("Licenses", self.licenses)):
            b = ttk.Button(btn, text=text, command=fn)
            b.pack(side="left", padx=(12 if text == "Diagnose" else 2, 2))
            self.buttons.append(b)
        for text, fn in (("Save output...", self.save_output), ("Help", self.help), ("About", self.about)):
            ttk.Button(btn, text=text, command=fn).pack(side="right" if text != "Save output..." else "left",
                                                        padx=(12, 2) if text == "Save output..." else 2)

        self.log = make_text(self)
        scrolled(self, self.log).pack(fill="both", expand=True, padx=6, pady=6)
        self.build_menu()
        self.refresh()

    # -- menu, help, about, save, copy ---------------------------------------------------------
    def build_menu(self) -> None:
        bar = tk.Menu(self)
        file_menu = tk.Menu(bar, tearoff=False)
        file_menu.add_command(label="Save output...", command=self.save_output, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        bar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(bar, tearoff=False)
        help_menu.add_command(label="Help", command=self.help, accelerator="F1")
        help_menu.add_command(label="About / Licenses", command=self.about)
        bar.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=bar)
        self.bind("<F1>", lambda e: self.help())
        self.bind("<Control-s>", lambda e: self.save_output())

    def help(self) -> None:
        show_text_window(self, "usbdrv - Help", guicore.HELP_TEXT, height=36)

    def about(self) -> None:
        show_text_window(self, "About usbdrv", guicore.about_text(), height=22)

    def save_output(self) -> None:
        content = self.log.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showinfo("usbdrv", "Nothing to save yet.")
            return
        path = filedialog.asksaveasfilename(parent=self, title="Save output", defaultextension=".txt",
                                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content + "\n")
        except OSError as e:
            messagebox.showerror("usbdrv", "Cannot save: %s" % e)

    def tree_popup(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.tree_menu.tk_popup(event.x_root, event.y_root)

    def copy_row(self) -> None:
        sel = self.tree.selection()
        if sel:
            values = [str(v) for v in self.tree.item(sel[0], "values")]
            copy_to_clipboard(self, "\t".join(values + [self.devices[int(sel[0])]["instance_id"]]))

    # -- helpers -----------------------------------------------------------------------------
    def write(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", text)
        self.log.configure(state="disabled")

    def selected(self) -> Optional[dict]:
        sel = self.tree.selection()
        return self.devices[int(sel[0])] if sel else None

    def background(self, work: Callable, done: Callable) -> None:
        """Run work() off the UI thread, then done(result) on it. Ignored while another job runs."""
        if self.busy:
            return
        self.busy = True
        for b in self.buttons:
            b.state(["disabled"])

        def finish(res):
            self.busy = False
            for b in self.buttons:
                b.state(["!disabled"])
            done(res)

        def run():
            try:
                res = work()
            except Exception as e:  # shown in the window, never lost in the thread
                res = e
            self.after(0, lambda: finish(res))

        threading.Thread(target=run, daemon=True).start()

    @staticmethod
    def text_of(res) -> str:
        if isinstance(res, Exception):
            return "error: %s" % res
        lines = list(res.messages)
        if res.error:
            lines += ["", "error: %s" % res.error]
        lines += ["", "exit code %d: %s" % (res.code, res.meaning)]
        return "\n".join(lines)

    # -- actions -----------------------------------------------------------------------------
    def refresh(self) -> None:
        def done(res):
            if isinstance(res, Exception) or not res.ok:
                self.write(self.text_of(res))
                return
            self.devices = res.data or []
            self.tree.delete(*self.tree.get_children())
            for i, d in enumerate(self.devices):
                mi = "MI_%02X" % d["mi"] if d["mi"] is not None else "-"
                self.tree.insert("", "end", iid=str(i), values=(d["vidpid"], mi, d["cls"] or "-", d["service"] or "-",
                                                                d["status"] or "-", d["name"] or "-"))
        self.background(lambda: guicore.list_devices(hubs=self.hubs.get()), done)

    def act(self, action: str) -> None:
        dev = self.selected()
        if not dev:
            messagebox.showinfo("usbdrv", "Select a device first.")
            return
        argv = guicore.install_args(action, dev, self.driver.get(), force=self.force.get(), name=self.name.get(),
                                    wcid=self.wcid.get(), filter_driver=self.filt.get())

        def applied(res):
            self.write(self.text_of(res))
            self.refresh()

        def previewed(res):
            self.write(self.text_of(res))
            if isinstance(res, Exception) or not res.ok:
                return
            if not guicore.is_admin():
                messagebox.showwarning("usbdrv", "Administrator rights are needed to apply this change. "
                                       "Use 'Restart as Administrator'.")
                return
            question = "%s\n\n%s %s (%s)?" % (WARNING, action.capitalize(), dev["vidpid"], dev["name"] or "no name")
            if messagebox.askyesno("Confirm", question, icon="warning"):
                self.background(lambda: guicore.apply(argv), applied)
        self.background(lambda: guicore.preview(argv), previewed)

    def diagnose(self) -> None:
        dev = self.selected()
        argv = ["diagnose"] + (guicore.target_args(dev) if dev else [])
        self.background(lambda: guicore.call(argv), lambda r: self.write(self.text_of(r)))

    def certs(self) -> None:
        self.background(lambda: guicore.call(["cert-remove"]), lambda r: self.write(
            self.text_of(r) + "\n\nTo remove one: usbdrv cert-remove --thumbprint <hash> --yes"))

    def licenses(self) -> None:
        self.background(lambda: guicore.call(["licenses"]), lambda r: self.write(self.text_of(r)))

    def elevate(self) -> None:
        if guicore.relaunch_elevated():
            self.destroy()
        else:
            messagebox.showerror("usbdrv", "The elevation request was refused or failed.")


def main() -> int:
    if sys.platform != "win32":
        print("usbdrv-gui works on Windows only.", file=sys.stderr)
        return 1
    App().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
