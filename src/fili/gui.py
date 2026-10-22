"""fili-gui: una piccola finestra sulle stesse operazioni della riga di comando (tkinter, nessuna dipendenza in più).

La finestra mostra sempre il piano della prova (dry-run) e chiede conferma prima dell'esecuzione vera; l'esecuzione
vera è la CLI con --yes, quindi ogni regola di sicurezza della CLI vale senza modifiche.
"""

import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Optional

from . import __version__, guicore

DRIVERS = ("winusb", "libusbk", "libusb-win32", "usbser")
COLUMNS = (("vidpid", "VID:PID", 90), ("mi", "Iface", 55), ("cls", "Class", 90), ("service", "Driver", 90),
           ("status", "Status", 70), ("name", "Name", 330))
WARNING = ("This replaces the driver of the selected device and adds a self-signed certificate to this PC's "
           "trusted stores (remove it later with 'fili cert-remove'). Use only on devices you own.")


def scrolled(parent, widget, horizontal: bool = True) -> ttk.Frame:
    """Mette un Text/Treeview in un frame con barre di scorrimento verticale e orizzontale; il frame va posizionato da chi chiama."""
    frame = ttk.Frame(parent)
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    widget.grid(in_=frame, row=0, column=0, sticky="nsew")
    widget.lift(frame)   # un widget gestito "in_" un frame creato dopo di lui resta sotto il frame, quindi invisibile
    vs = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
    widget.configure(yscrollcommand=vs.set)
    vs.grid(row=0, column=1, sticky="ns")
    if horizontal:
        hs = ttk.Scrollbar(frame, orient="horizontal", command=widget.xview)
        widget.configure(xscrollcommand=hs.set)
        hs.grid(row=1, column=0, sticky="ew")
    return frame


def copy_to_clipboard(widget, text: str) -> None:
    widget.clipboard_clear()
    widget.clipboard_append(text)


def make_text(parent, height: int = 12, wrap: str = "none") -> tk.Text:
    """Un Text in sola lettura con menu contestuale (Copia la selezione / Seleziona tutto)."""
    text = tk.Text(parent, height=height, wrap=wrap, state="disabled", font=("Consolas", 10))
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


TEAL, INK = "#0B6F7A", "#1B2A41"
TERM_SECTIONS = ("OPTIONS", "BUTTONS")     # sezioni di guida fatte di "termine   descrizione" su due colonne


def parse_document(content: str, term_sections=TERM_SECTIONS) -> List[tuple]:
    """Trasforma il testo semplice di guida/informazioni in blocchi (tipo, termine, testo): title, head, item, bullet, para.

    La prima riga e' il titolo; una riga senza rientro e' un titolo di sezione se e' tutta maiuscola o se la
    segue una riga rientrata; nelle sezioni 'a termini' la colonna 2-16 e' il termine; le righe di continuazione
    (rientro maggiore, o a capo dentro lo stesso paragrafo) si uniscono al blocco precedente."""
    lines = content.split(chr(10))
    blocks: List[list] = []
    section, blank_before, first = "", True, True
    for n, raw in enumerate(lines):
        if not raw.strip():
            blank_before = True
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        body = raw.strip()
        if first:
            blocks.append(["title", "", body])
            first, blank_before = False, False
            continue
        nxt = next((l for l in lines[n + 1:] if l.strip()), "")
        if indent == 0:
            if body.isupper() or nxt.startswith("  "):
                section = body
                blocks.append(["head", "", body])
            else:
                blocks.append(["para", "", body])
            blank_before = False
            continue
        starter = None
        if body.startswith(("* ", "- ")):
            starter = ["bullet", "", body[2:]]
        elif indent == 2 and section in term_sections and len(raw) > 16 and raw[15] == " " and raw[16] != " " and raw[2:16].strip():
            starter = ["item", raw[2:16].strip(), raw[16:].strip()]
        last = blocks[-1] if blocks else None
        joins = (last is not None and last[0] in ("item", "bullet", "para") and not blank_before
                 and (indent > 2 or last[0] == "para"))
        if starter and not (joins and indent > 2):
            blocks.append(starter)
        elif joins:
            last[2] += " " + body
        else:
            blocks.append(["para", "", body])
        blank_before = False
    return [tuple(b) for b in blocks]


def render_document(text: tk.Text, content: str) -> None:
    """Disegna il testo di guida con titoli, colonne a rientro sospeso e elenchi, nei caratteri di sistema."""
    base = tkfont.nametofont("TkDefaultFont").copy()
    base.configure(size=10)
    bold, head, title = base.copy(), base.copy(), base.copy()
    bold.configure(weight="bold")
    head.configure(weight="bold", size=11)
    title.configure(weight="bold", size=17)
    text._fonts = (base, bold, head, title)        # i Font vanno tenuti vivi finche' esiste il widget
    text.configure(font=base, background="#FFFFFF", foreground=INK, padx=20, pady=16, spacing1=2, spacing3=3,
                   wrap="word", selectbackground="#BFE9ED", selectforeground=INK, relief="flat")
    text.tag_configure("title", font=title, spacing3=10)
    text.tag_configure("head", font=head, foreground=TEAL, spacing1=18, spacing3=5)
    text.tag_configure("para", lmargin1=2, lmargin2=2, spacing1=4)
    text.tag_configure("item", lmargin1=2, lmargin2=150, tabs=("150",), spacing1=4)
    text.tag_configure("term", font=bold)
    text.tag_configure("bullet", lmargin1=2, lmargin2=20, tabs=("20",), spacing1=4)
    text.configure(state="normal")
    text.delete("1.0", "end")
    for kind, term, body in parse_document(content):
        if kind == "item":
            text.insert("end", term, ("item", "term"))
            text.insert("end", chr(9) + body + chr(10), ("item",))
        elif kind == "bullet":
            text.insert("end", chr(0x2022) + chr(9) + body + chr(10), ("bullet",))
        else:
            text.insert("end", body + chr(10), (kind,))
    text.configure(state="disabled")


def show_text_window(parent, title: str, content: str, width: int = 100, height: int = 30) -> None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("800x640")
    text = make_text(win, height, wrap="word")
    render_document(text, content)
    ttk.Button(win, text="Close", command=win.destroy).pack(side="bottom", pady=8)
    scrolled(win, text, horizontal=False).pack(fill="both", expand=True, padx=8, pady=(8, 0))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("fili %s" % __version__)
        self.geometry("920x560")
        self.devices: List[dict] = []
        self.busy = False

        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        self.hubs = tk.BooleanVar(value=False)
        ttk.Button(top, text="☕ Ko-fi", width=9, command=self.donate).pack(side="right", padx=(8, 0))
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
        self.all_matching = tk.BooleanVar()
        for text, var in (("WCID", self.wcid), ("Filter driver", self.filt), ("All matching", self.all_matching),
                          ("Force (protected class)", self.force)):
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

        # avanzamento di un'installazione/ripristino: passo corrente e tempo trascorso (la percentuale dentro un passo
        # non esiste: wdi-simple non la comunica)
        self.prog_frame = ttk.Frame(self, padding=(6, 0))
        self.prog_text = tk.StringVar()
        ttk.Label(self.prog_frame, textvariable=self.prog_text).pack(fill="x")
        self.prog_bar = ttk.Progressbar(self.prog_frame, mode="determinate")
        self.prog_bar.pack(fill="x", pady=(2, 0))
        self.prog = None

        self.log = make_text(self)
        self.log_frame = scrolled(self, self.log)
        self.log_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.build_menu()
        self.refresh()

    # -- menu, aiuto, informazioni, salva, copia -----------------------------------------------
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
        help_menu.add_command(label="Buy me a coffee (Ko-fi)", command=self.donate)
        bar.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=bar)
        self.bind("<F1>", lambda e: self.help())
        self.bind("<Control-s>", lambda e: self.save_output())

    def help(self) -> None:
        show_text_window(self, "fili - Help", guicore.HELP_TEXT, height=36)

    def donate(self) -> None:
        webbrowser.open(guicore.KOFI_URL)

    def about(self) -> None:
        show_text_window(self, "About fili", guicore.about_text(), height=22)

    def save_output(self) -> None:
        content = self.log.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showinfo("fili", "Nothing to save yet.")
            return
        path = filedialog.asksaveasfilename(parent=self, title="Save output", defaultextension=".txt",
                                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content + "\n")
        except OSError as e:
            messagebox.showerror("fili", "Cannot save: %s" % e)

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

    # -- funzioni di supporto ----------------------------------------------------------------
    def write(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", text)
        self.log.configure(state="disabled")

    def selected(self) -> Optional[dict]:
        sel = self.tree.selection()
        return self.devices[int(sel[0])] if sel else None

    def background(self, work: Callable, done: Callable) -> None:
        """Esegue work() fuori dal thread dell'interfaccia, poi done(result) su di esso. Ignorato mentre un altro lavoro è in corso."""
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
            except Exception as e:  # mostrato nella finestra, mai perso nel thread
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

    # -- avanzamento -------------------------------------------------------------------------
    def progress_start(self) -> None:
        self.prog = {"done": 0, "total": 1, "text": "starting...", "t0": time.monotonic(), "tick": None}
        self.prog_bar.configure(maximum=1, value=0)
        self.prog_frame.pack(fill="x", before=self.log_frame)
        self.progress_draw()

    def on_progress(self, done: int, total: int, text: str) -> None:
        """Chiamata dal thread di lavoro: passa al thread dell'interfaccia."""
        self.after(0, lambda: self.progress_update(done, total, text))

    def progress_update(self, done: int, total: int, text: str) -> None:
        if self.prog is None:
            return
        self.prog.update(done=done, total=total, text=text, t0=time.monotonic())
        self.prog_bar.configure(maximum=total, value=done - 1)  # il passo in corso non conta come completato
        self.progress_draw()

    def progress_draw(self) -> None:
        p = self.prog
        if p is None:
            return
        self.prog_text.set(guicore.progress_label(p["done"], p["total"], p["text"], time.monotonic() - p["t0"]))
        p["tick"] = self.after(1000, self.progress_draw)

    def progress_stop(self, ok: bool) -> None:
        p, self.prog = self.prog, None
        if p is None:
            return
        if p["tick"]:
            self.after_cancel(p["tick"])
        if ok:
            self.prog_bar.configure(value=self.prog_bar.cget("maximum"))
        self.prog_text.set("Done." if ok else "Stopped: see the output below.")

    # -- azioni ------------------------------------------------------------------------------
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
            messagebox.showinfo("fili", "Select a device first.")
            return
        argv = guicore.install_args(action, dev, self.driver.get(), force=self.force.get(), name=self.name.get(),
                                    wcid=self.wcid.get(), filter_driver=self.filt.get(),
                                    all_matching=self.all_matching.get())

        def applied(res):
            self.progress_stop(not isinstance(res, Exception) and res.ok)
            self.write(self.text_of(res))
            self.refresh()

        def previewed(res):
            self.write(self.text_of(res))
            if isinstance(res, Exception) or not res.ok:
                return
            if not guicore.is_admin():
                messagebox.showwarning("fili", "Administrator rights are needed to apply this change. "
                                       "Use 'Restart as Administrator'.")
                return
            question = "%s\n\n%s %s (%s)?" % (WARNING, action.capitalize(), dev["vidpid"], dev["name"] or "no name")
            if messagebox.askyesno("Confirm", question, icon="warning"):
                self.progress_start()
                self.background(lambda: guicore.apply(argv, progress=self.on_progress), applied)
        self.background(lambda: guicore.preview(argv), previewed)

    def diagnose(self) -> None:
        dev = self.selected()
        argv = ["diagnose"] + (guicore.target_args(dev) if dev else [])
        self.background(lambda: guicore.call(argv), lambda r: self.write(self.text_of(r)))

    def certs(self) -> None:
        self.background(lambda: guicore.call(["cert-remove"]), lambda r: self.write(
            self.text_of(r) + "\n\nTo remove one: fili cert-remove --thumbprint <hash> --yes"))

    def licenses(self) -> None:
        self.write(guicore.licenses_text())

    def elevate(self) -> None:
        if guicore.relaunch_elevated():
            self.destroy()
        else:
            messagebox.showerror("fili", "The elevation request was refused or failed.")


def main() -> int:
    if sys.platform != "win32":
        print("fili-gui works on Windows only.", file=sys.stderr)
        return 1
    App().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
