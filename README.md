# fili

**Replace the driver of a USB device or interface from the command line — a scriptable, Zadig-like tool for Windows.**

> ## ⚠️ SECURITY WARNING — READ FIRST
>
> * Installing a WinUSB / libusbK / libusb-win32 driver through libwdi **creates a self-signed certificate and adds it to the
>   machine's *Root* and *TrustedPublisher* stores**. Anything signed with that certificate is then trusted by this PC.
>   `fili cert-remove` lists and removes those certificates.
> * It **requires Administrator rights** and **replaces the driver of the device/interface you select**. A wrong target can
>   disable your keyboard, mouse, disk or Bluetooth (`fili` refuses those classes unless you pass `--force`).
> * Use it **only on devices you own** and understand. Test on a disposable device first (see
>   [`docs/piano-prove-installazione.md`](docs/piano-prove-installazione.md)).
> * **Status: pre-release.** The commands that change the system (`install` with WinUSB, libusbK and libusb-win32,
>   `reinstall`, `restore`, `cert-remove`) have been run for real **once, on a virtual USB device in a Windows Server 2022
>   VM** (details and two bugs found and fixed: [`docs/risultati-prove-installazione.md`](docs/risultati-prove-installazione.md)).
>   Then on a **physical device** (the built-in webcam, a composite device, Windows 11 Pro): WinUSB, libusbK,
>   libusb-win32, `usbser`, `--name`, `reinstall`, `restore`, `cert-remove`
>   ([`docs/risultati-prove-hardware.md`](docs/risultati-prove-hardware.md); three more bugs fixed).
>   **Identical devices** (two identical USB network adapters, same VID:PID): `install --instance` changes only the chosen one (`wdi-simple -x` + `pnputil /add-driver` + `DiInstallDevice`); `--all-matching` keeps the old all-at-once behaviour. Full series on the two identical network adapters (22 Oct 2026): `winusb`, `libusbk` and `libusb-win32` on either one, `reinstall`, `restore`, two different drivers at once, `--json` and `cert-remove` all pass, and the other adapter is never touched. After `install --all-matching` the identical devices share one package, so `restore` refuses it (exit 2) until you add `--all-matching`: `restore --instance ID --all-matching --yes` puts all of them back (checked on the two adapters; details in `docs/risultati-prove-hardware.md` §9). Also checked: non-elevated run, composite without `--iface`, protected class, failing `wdi-simple`, `fili.toml`, Secure Boot on. `install --filter` + `restore` on a sacrificial USB flash drive (`USBSTOR` stays the driver, `libusb0` is added as upper filter and removed again). **`--filter` is not supported on network adapters**: `restore` hangs on the device restart (3 attempts on USB network adapters). **Not verified:** Windows 10, Memory Integrity, `--wcid` on a device that advertises WCID, ARM64/32-bit.
>   No warranty — GNU GPL v3 or later, see [`LICENSE`](LICENSE) and [`docs/licenza.md`](docs/licenza.md).

## What it is

Zadig is a GUI. `fili` gives you the same job as a command line, with explicit safety rails, logs and machine-readable
output, so it can be used in scripts and documented in a README ("run this to let tool X talk to the board").

It is a thin, auditable front-end in Python (standard library only). The actual driver package creation and installation is
done by **libwdi** (`wdi-simple.exe`), used as a separate program (a subprocess, never linked or embedded).

| Command | Changes the system? | What it does |
|---|---|---|
| `list` | no | present USB devices/interfaces, driver, service, status (Zadig-like filters) |
| `status` | no | driver package, version, date, provider, problem code of one device/interface |
| `diagnose` | no | explains driver failures: Device Manager code, NTSTATUS, `setupapi.dev.log` excerpts, event logs |
| `extract` | no (writes one INF in a folder you choose) | unsigned INF for inspection, **creates no certificate** |
| `install` | **yes** | replaces the driver (WinUSB, libusbK, libusb-win32, CDC) of one device/interface |
| `reinstall` | **yes** | puts back the driver currently bound |
| `restore` / `uninstall` | **yes** | removes the OEM driver package of one device and lets Windows re-detect it |
| `restart` | **yes** | enables a device that Windows shows as disabled (problem 22), otherwise restarts it; changes no driver |
| `usb-reset` | **yes** | recovers a device (or its external hub) that does not respond: stops stuck `pnputil` commands, disables and enables it; never touches the USB controller |
| `cert-remove` | **yes** (only with `--thumbprint`) | lists / removes the self-signed certificates created by libwdi |
| `licenses` | no | third-party components and their licenses |
| `sample-config` | no | prints a sample `fili.toml` |

Every command that changes the system needs `--yes`, needs Administrator rights, and supports `--dry-run`
(prints exactly what it would run and executes nothing).

## Installer (no build needed)

`dist\installer\fili-setup-<version>.exe` installs `fili.exe` (command line), `fili-gui.exe` (graphical interface) and
`wdi-simple.exe` in `C:\Program Files\fili`, with Start-menu shortcuts and a PATH entry (offered, selected by default, you can untick it). The installer **only
copies files**: it changes no driver and adds no certificate, and the uninstaller removes only what it installed
(including its PATH entry). Licenses and corresponding sources of the bundled third-party components (libwdi, libusb-win32,
libusbK) are in the `LICENSES` and `THIRD_PARTY` folders of the installation. To build it yourself:
`scripts\build_wdi_simple.sh`, `scripts\build_exe.ps1`, `python -I scripts\package_wdi_bundle.py --exe build\wdi-simple.exe --out dist\wdi-bundle --drivers-file docs\embedded-drivers.txt`,
then `scripts\build_installer.ps1` (needs PyInstaller and Inno Setup 6).

**Checksums (SHA-256).** The build writes `dist\SHA256SUMS` (installer, `fili.exe`, `fili-gui.exe`, `wdi-simple.exe`): publish it next to
the files and check a download with `sha256sum -c SHA256SUMS` or `Get-FileHash <file> -Algorithm SHA256`. The installation folder has its own
`SHA256SUMS` for every installed file (executables, licenses, sources), checked with `sha256sum -c SHA256SUMS` from that folder. The
checksums detect a corrupted or altered download; they are not a signature of the author (the files are not code-signed).

## Quick start

```powershell
# 1. get Python 3.9+ (3.11+ for fili.toml); run from the repository root
$env:PYTHONPATH = "src"            # or: pip install -e .
python -m fili list
python -m fili list --only-no-driver
python -m fili status --vid 0483 --pid 374B --iface 0

# 2. preview a driver replacement (changes nothing)
python -m fili install --vid 0483 --pid 374B --iface 0 --driver winusb --dry-run

# 3. when you have read the warning, built wdi-simple.exe, and opened an elevated terminal
python -m fili install --vid 0483 --pid 374B --iface 0 --driver winusb --yes

# diagnose a device that fails to start
python -m fili diagnose --vid 0416 --pid 9391 --since 2d --log-file fili.log

# undo
python -m fili restore --vid 0483 --pid 374B --iface 0 --yes
python -m fili cert-remove                       # list the self-signed certificates
python -m fili cert-remove --thumbprint <40 hex> --yes
```

Example target (one of many): the ST-LINK debug interface of a Nucleo board is `0483:374B`, interface `0`.

`wdi-simple.exe` must be built from libwdi first: [`docs/building-wdi-simple.md`](docs/building-wdi-simple.md).
Without it, `list`, `status`, `diagnose`, `extract` and every `--dry-run` still work.

## Global options

`--config FILE`, `--log-file FILE`, `--log-level DEBUG|INFO|WARN|ERROR`, `--log-format text|json`, `-v/--verbose`,
`--json` (one JSON document on stdout), `--silent`. They work before or after the sub-command.
`install`, `reinstall` and `restore` print their progress on stderr as `[2/4] step` (not with `--json` or `--silent`); the GUI
shows the same steps in a progress bar. The count is of steps, not a percentage: `wdi-simple` does not report one.
`fili.toml` (see `fili sample-config`) holds defaults; command-line options win, and a config file can never contain
the confirmation (`--yes`).

## For AI agents: `fili --skill`

`fili --skill` (alias `--skil`) prints a complete guide for an AI agent that has to drive fili on behalf of a person, and exits 0 without reading or changing anything. With `--json` the text is in `data.markdown`. It works with no sub-command and in any position (`fili list --skill`). The guide covers:

* the **rules**: look before touching, never add `--yes` or `--force` without the person's explicit approval of that exact command, Administrator, the self-signed certificate, only devices the person owns;
* the **workflow** `list` → `status` → `--dry-run` → ask → `--yes` → check the exit code and the `after` data → how to undo;
* how to **select** a device (`--vid/--pid`, `--iface` for composite devices, `--instance` for identical ones, `--all-matching`);
* every **command**, whether it changes the system, and the `--json` output format;
* the **exit codes** and what to do for each, and the **recovery** paths (`restore`, `usb-reset`, unplug and replug, `cert-remove`);
* the known **limits** (for example `--filter` on network adapters).

The exit codes and the version come from the program itself; a test checks that every command and every option named in the guide exists, so it cannot fall behind the CLI.

The repository also has an [`llms.txt`](llms.txt) at its root: a short summary with links to the documentation, for tools that read it.

## USB that stops responding: `fili usb-reset`

Windows has no USB service to restart: the stack is made of controller and hub drivers. When a device or `pnputil` hangs (`pnputil /restart-device` stayed stuck for over 15 minutes on a USB network adapter), `fili usb-reset --vid V --pid P [--instance ID] --dry-run` shows what it would do and `--yes` does it: it stops `pnputil` commands working on that device for longer than `--stuck-after` seconds (default 30), then disables and enables the device. `--hub` restarts the external hub it is plugged into instead (everything behind that hub disconnects for a moment; refused if a keyboard, mouse, disk or Bluetooth adapter is behind it, unless `--force`). The USB controller and its root hub are **never** restarted: that would also drop keyboard and mouse. `pnputil` commands have a time limit of 180 s and `wdi-simple` of 300 s: a command that does not finish is stopped, fili exits with 6 and points to `usb-reset`. **Limit:** if the vendor driver of the device is hung inside the kernel (seen with `--filter` on a USB network adapter), `pnputil /disable-device` times out too, on the device and on its hub; then only unplugging and replugging the device (or a reboot) helps.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | unexpected error (PowerShell failed, tool missing, I/O) |
| 2 | invalid arguments, or refused by a safety rule (protected class, shared driver package, unsupported driver for `extract`) |
| 3 | Administrator rights required |
| 4 | device / interface not found |
| 5 | ambiguous: several matching devices (use `--instance`) or a composite device without `--iface` |
| 6 | driver error: a command failed, or the device is not in the expected state afterwards (run `diagnose`) |
| 7 | cancelled: `--yes` missing |

## Logging and diagnostics

`--log-file` writes a timestamped log (`DEBUG/INFO/WARN/ERROR`, text or JSON lines) with the commands run, their exit codes,
the output of `pnputil` / `wdi-simple` and every error. After `install`, `reinstall` and `restore` the device is read back:
if Windows reports a problem code, the exit code is 6 and the log says why.
`diagnose` is read-only and explains the Device Manager problem code (10 FAILED_START, 28 not installed, 43 reported a
problem, 52 unsigned…), the NTSTATUS in `DEVPKEY_Device_ProblemStatus`, the current driver and its version/date, the last
sections of `C:\Windows\INF\setupapi.dev.log` for that VID/PID/instance (`--since`, `--last`) and, best effort, recent
Kernel-PnP and DriverFrameworks events. The log never contains environment variables or credentials.

## Zadig features

What is implemented, what is not, and what is untested: [`docs/zadig-features.md`](docs/zadig-features.md).

## Tests

```powershell
python -I tests/test_fili.py        # also the other files in tests/: test_twins, test_filter, test_gui, test_gui_tk (real window), test_leftover, test_progress, test_bundle, test_usbreset, test_skill
```
The tests never touch the system (a fake command runner; the real one is replaced by a function that fails the test).

## Contributing, license

[`CONTRIBUTING.md`](CONTRIBUTING.md) · license **GPL-3.0-or-later** ([`LICENSE`](LICENSE), [`docs/licenza.md`](docs/licenza.md)) · dependencies: [`NOTICE`](NOTICE).
Clean-room note: Zadig's source (GPL-3.0-or-later) was not copied or adapted; libwdi/wdi-simple (LGPL-3.0-or-later) is only
run as an external program.

## Code signing policy

*Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org).*
(Applied for; until it is granted the releases are not signed. See [`docs/firma-del-codice.md`](docs/firma-del-codice.md).)

* What is signed: `fili.exe`, `fili-gui.exe` and the installer, built from this repository by the GitHub Actions workflow
  [`release.yml`](.github/workflows/release.yml). `wdi-simple.exe` is built from libwdi (third-party code) and is **not** signed by this project.
* Team roles: author, reviewer and approver: [PyLuke73](https://github.com/PyLuke73) (sole maintainer). Every signing request is approved by hand.
* Privacy policy: see [`PRIVACY.md`](PRIVACY.md). In short, fili does not send any information to other networked systems. The only network access is a browser
  page you open yourself (the Ko-fi button, the links); the installer and the programs make no network request.

## Support the project

fili is free software. If it saved you time, you can support its development with a donation on
**[Ko-fi](https://ko-fi.com/lucacolombo35186)** (there is a ☕ button in the GUI too). Donations are optional and do not
change the license or give any warranty.

---

# fili (italiano)

**Sostituisce il driver di un dispositivo o di un'interfaccia USB da riga di comando, come Zadig ma scriptabile (Windows).**

> ## ⚠️ AVVISO DI SICUREZZA
> * L'installazione di un driver WinUSB / libusbK / libusb-win32 tramite libwdi **crea un certificato autofirmato e lo aggiunge
>   agli archivi *Root* e *TrustedPublisher* del computer**: tutto ciò che è firmato con quel certificato diventa attendibile
>   per questo PC. `fili cert-remove` elenca e rimuove questi certificati.
> * **Serve l'amministratore** e **si sostituisce il driver del dispositivo scelto**. Un bersaglio sbagliato può disattivare
>   tastiera, mouse, disco o Bluetooth (le classi protette sono rifiutate senza `--force`).
> * Da usare **solo su dispositivi propri**, prima su un dispositivo sacrificabile (vedi `docs/piano-prove-installazione.md`).
> * **Stato: pre-rilascio.** I comandi che modificano il sistema (`install` con WinUSB, libusbK e libusb-win32, `reinstall`,
>   `restore`, `cert-remove`) sono stati eseguiti per davvero **una volta, su un dispositivo USB virtuale in una macchina
>   virtuale Windows Server 2022** (vedi `docs/risultati-prove-installazione.md`, con due difetti trovati e corretti).
>   Poi su un **dispositivo fisico** (la webcam integrata, dispositivo composito, Windows 11 Pro): WinUSB, libusbK, libusb-win32,
>   `usbser`, `--name`, `reinstall`, `restore`, `cert-remove` (`docs/risultati-prove-hardware.md`, altri tre difetti corretti).
>   **Dispositivi identici** (due adattatori di rete USB identici, con lo stesso VID:PID): `install --instance` cambia solo quello scelto (`wdi-simple -x` + `pnputil /add-driver` + `DiInstallDevice`); `--all-matching` mantiene il vecchio comportamento (tutti insieme). Provati anche: esecuzione senza amministratore, composito senza `--iface`, classe protetta, `wdi-simple` che fallisce, `fili.toml`, Secure Boot attivo.
>   `install --filter` + `restore` su una chiavetta USB sacrificabile (il driver resta `USBSTOR`, `libusb0` si aggiunge come filtro superiore e si toglie). **`--filter` non è supportato sulle schede di rete**: `restore` si blocca al riavvio del dispositivo (3 tentativi su adattatori USB del produttore).
>   Serie completa sui due adattatori di rete identici (22/10/2026): `winusb`, `libusbk`, `libusb-win32` su ciascuno, `reinstall`, `restore`, due driver diversi insieme, `--json` e `cert-remove` passano, e l'altro adattatore non viene mai toccato. Dopo `install --all-matching` i dispositivi identici condividono un solo pacchetto, quindi `restore` lo rifiuta (codice 2) finché non aggiungi `--all-matching`: `restore --instance ID --all-matching --yes` li ripristina tutti (provato sui due adattatori; dettagli in `docs/risultati-prove-hardware.md` §9).
>   **Non verificati:** Windows 10, Memory Integrity, `--wcid` su un dispositivo che dichiara il WCID, ARM64/32 bit. Nessuna garanzia. Licenza: GPL-3.0-or-later (`LICENSE`, `docs/licenza.md`).

**Uso rapido:** `python -m fili list`, `status`, `diagnose` (sola lettura); `install ... --dry-run` mostra cosa farebbe senza
eseguire nulla; i comandi che modificano il sistema richiedono `--yes` e un terminale di amministratore. `extract` scrive un
INF non firmato per ispezione e **non crea certificati**. `install` richiede `wdi-simple.exe`, da compilare da libwdi
(`docs/building-wdi-simple.md`).

**Codici di uscita:** 0 ok · 1 errore imprevisto · 2 argomenti non validi o rifiuto di sicurezza · 3 non amministratore ·
4 dispositivo non trovato · 5 ambiguo (più dispositivi o composito senza `--iface`) · 6 errore del driver · 7 annullato (manca `--yes`).

**Log e diagnosi:** `--log-file` (testo o JSON), `-v`, `--log-level`; `diagnose` spiega i codici di errore di Windows
(es. 10, 28, 43, 52), l'NTSTATUS, il driver corrente e le righe di `setupapi.dev.log` relative al dispositivo.

**Per gli agenti AI:** `fili --skill` (alias `--skil`) stampa una guida completa per un'AI che deve usare fili al posto di una persona (regole, flusso di lavoro, selezione del dispositivo, comandi, formato `--json`, codici di uscita, recupero, limiti) ed esce con 0 senza toccare nulla. Con `--json` il testo è in `data.markdown`. La guida è in inglese; i codici di uscita e la versione vengono dal programma e un test controlla che ogni comando e ogni opzione citata esistano.

**Dispositivo disattivato:** `fili restart --vid V --pid P [--instance ID] --dry-run` mostra il piano; con `--yes` lo riattiva se Windows lo indica come disattivato (problema 22), altrimenti lo riavvia. Non cambia nessun driver. Nella finestra c'è il pulsante Restart.

**USB che non risponde:** `fili usb-reset --vid V --pid P [--instance ID] --dry-run` mostra cosa farebbe; con `--yes` ferma i `pnputil` appesi su quel dispositivo (più vecchi di `--stuck-after`, 30 s) e poi lo disattiva e riattiva. `--hub` riavvia invece l'hub esterno a cui è collegato (rifiutato se dietro c'è una tastiera, un mouse, un disco o un Bluetooth, salvo `--force`). Il controller USB e l'hub radice non si riavviano mai. I comandi `pnputil` hanno un limite di 180 s e `wdi-simple` di 300 s: se non finiscono vengono fermati, `fili` esce con 6 e indica `usb-reset`. **Limite:** se il driver del produttore è bloccato nel kernel (visto con `--filter` su un adattatore di rete USB) scade anche `pnputil /disable-device`, sul dispositivo e sul suo hub; allora serve scollegare e ricollegare il dispositivo (o riavviare).

**Installer.** `fili-setup-<versione>.exe` installa `fili.exe`, `fili-gui.exe` e `wdi-simple.exe` in
`C:\Program Files\fili`, con collegamenti nel menu Start e la voce nel PATH (proposta, selezionata di default, si può togliere). Copia solo file: non cambia driver né
certificati, e la disinstallazione toglie solo ciò che ha messo. Licenze e sorgenti dei componenti di terzi sono nelle cartelle
`LICENSES` e `THIRD_PARTY`. **Hash SHA-256:** la build scrive `dist\SHA256SUMS` (installer, eseguibili, `wdi-simple.exe`) da pubblicare
accanto ai file; la cartella installata ha un proprio `SHA256SUMS` con tutti i file. Servono a rilevare un download corrotto o alterato,
non sono una firma dell'autore (i file non sono firmati).

**Politica di firma del codice (Code signing policy).** *Firma del codice gratuita fornita da [SignPath.io](https://signpath.io), certificato di [SignPath Foundation](https://signpath.org)* (richiesta inviata: finché non è concessa, le release non sono firmate; vedi `docs/firma-del-codice.md`). Si firmano `fili.exe`, `fili-gui.exe` e l'installer, compilati da questo repository con il flusso `release.yml`; `wdi-simple.exe` viene da libwdi e **non** è firmato da questo progetto. Autore, revisore e approvatore: [PyLuke73](https://github.com/PyLuke73) (unico manutentore); ogni richiesta di firma è approvata a mano. Privacy: vedi `PRIVACY.md`; fili non invia informazioni ad altri sistemi in rete; l'unico accesso alla rete è una pagina del browser che apri tu (il pulsante Ko-fi, i link).

**Test:** `python -I tests/test_fili.py` e gli altri file in `tests\` (non toccano il sistema).

**Supporta il progetto:** fili è software libero. Se ti è stato utile puoi sostenerlo con una donazione su
**[Ko-fi](https://ko-fi.com/lucacolombo35186)** (nella GUI c'è anche il pulsante ☕). La donazione è facoltativa e non
cambia la licenza né dà alcuna garanzia.
