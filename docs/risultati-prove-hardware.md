# Risultati delle prove su hardware fisico (13/10/2026)

*English summary at the end.*

Seconda serie di prove reali, dopo quelle nella macchina virtuale (`risultati-prove-installazione.md`). Questa volta su
un **dispositivo fisico**: la webcam integrata del PC di prova. Al termine il sistema è stato riportato allo stato iniziale.

## 1. Ambiente

| Voce | Valore |
|---|---|
| Sistema | Windows 11 Pro, italiano, x64; Secure Boot **disattivato**; Memory Integrity (HVCI) **non attiva** |
| Dispositivo | Webcam integrata del PC, `<webcam>`, dispositivo composito (`usbccgp`); interfaccia `MI_00`, classe Camera, driver di partenza `usbvideo` (Microsoft, `usbvideo.inf`) |
| Antivirus | antivirus di terze parti installato |
| Strumento | `wdi-simple.exe` di libwdi v1.5.1 (lo stesso della VM), terminale PowerShell 7 con diritti di amministratore |
| Altri dispositivi USB | un lettore di schede, un mouse/tastiera HID, un adattatore Bluetooth: **mai toccati** |

Sul PC c'erano già quattro certificati libwdi di altri strumenti e i relativi pacchetti: sono rimasti intatti.

## 2. Esito

| Prova | Esito | Note |
|---|---|---|
| `install --driver winusb --iface 0` | PASS | al secondo tentativo, vedi difetto 1; driver `WinUSB`, pacchetto libwdi, stato OK |
| `install --driver libusbk` | PASS | `libusbK` 3.1.0.0, stato OK |
| `install --driver libusb-win32` | PASS | `libusb0` 1.4.0.0, stato OK |
| `install --name "..."` | PASS | il nome finisce in `DEVPKEY_Device_DeviceDesc`; il nome amichevole di Windows resta quello originale |
| `install --driver usbser` | PASS (errore atteso) | il pacchetto si installa, ma `usbser` non può avviarsi su un'interfaccia video: problema 10 FAILED_START, `fili` esce con 6 e lo segnala; `restore` ripristina |
| `install --wcid` | errore atteso | la webcam non espone l'ID compatibile WCID: libwdi risponde «Resource already exists» (-13); nessuna modifica al driver |
| `reinstall` | PASS | crea un secondo pacchetto (`oem191.inf`) |
| `restore` (dopo ogni prova, anche dopo `reinstall`) | PASS | torna a `usbvideo` / `usbvideo.inf` / Microsoft; nessun pacchetto libwdi rimasto per `<webcam>` |
| composito senza `--iface` | PASS | codice 5 |
| `cert-remove` | PASS dopo la correzione 2 | rimossi solo i certificati creati da queste prove; i quattro preesistenti sono rimasti |

## 3. Difetti trovati e corretti

1. **`install` fallito una volta con -15 (`WDI_ERROR_NEEDS_ADMIN`).** Primo tentativo, dopo circa 23 s. Non si è più
   ripresentato in una decina di esecuzioni identiche, anche con le pipe di Python e con il terminale elevato. Causa **non
   dimostrata**: sul PC c'è un antivirus di terze parti, che compare nei log di Code Integrity, e l'ipotesi è che abbia analizzato l'installer appena
   estratto. Correzione: `install` ritenta una volta e spiega la possibile causa (antivirus).
2. **`cert-remove` elencava zero certificati (`Cert:` non disponibile).** I certificati c'erano, ma un `powershell` 5.1
   avviato da PowerShell 7 eredita `PSModulePath` e non carica l'unità `Cert:`; l'errore era nascosto da
   `SilentlyContinue`. Nella VM non si vedeva perché non c'è PowerShell 7. Correzione: elenco e rimozione usano
   direttamente `X509Store` di .NET. Test di regressione.
3. **`restore` rifiutava un pacchetto `usbser`.** Il pacchetto era di libwdi ma il servizio `usbser` non era nell'elenco
   riconosciuto. Correzione: si riconosce anche dal provider `libwdi`. Test di regressione.
4. **Messaggio poco chiaro con `--wcid`** su un dispositivo senza WCID: ora `install` spiega che `--wcid` richiede un
   dispositivo che annuncia l'ID compatibile.

Durante le prove ho anche lanciato per errore un `install` vero credendo di fare una prova senza privilegi (l'attività
pianificata è partita comunque elevata): nessun danno, rientrava nello stesso tipo di prova.

## 4. Cosa **non** è stato provato

- `--filter` su un dispositivo del PC: provata più avanti su chiavette sacrificabili (sezioni 5 e 7).
- Esecuzione **senza** diritti di amministratore (codice 3): coperta solo dai test automatici; in questo ambiente non sono
  riuscito a ottenere un processo non elevato.
- Windows 10, Windows con Memory Integrity attiva o Secure Boot attivo, ARM64, Windows a 32 bit, altre lingue.
- Dispositivi con interfaccia non video (qui l'unica prova fisica è una webcam), dispositivo scollegato durante l'installazione.

## 5. Seconda serie: chiavetta USB e prova senza amministratore (14/10/2026)

Dispositivo: chiavetta USB (archiviazione di massa), `<chiavetta>`, volume FAT32 con dati. Il contenuto non e' stato toccato
(nessuna scrittura, nessuna formattazione); dopo ogni prova il volume e' tornato `Healthy`.

| Prova | Esito | Note |
|---|---|---|
| `install --driver winusb` (senza `--force`) | PASS | la classe e' `USB`, non e' una classe protetta; il volume sparisce finche' dura WinUSB |
| `restore` | PASS | torna `USBSTOR` / `usbstor.inf` / Microsoft, volume di nuovo presente e integro |
| `install --driver libusb-win32 --filter` | **errore rilevato** | libusb0 si installa come filtro superiore, ma la chiavetta va in problema 39 (DRIVER_FAILED_LOAD); `fili` esce con 6 e lo segnala. Causa del mancato caricamento non indagata |
| `restore` dopo `--filter` | **difetto 5, corretto** | rifiutava ("not an OEM package") e il filtro restava. Ora `restore` rileva `libusb0` tra gli UpperFilters, lo toglie (gli altri filtri restano) e riavvia il dispositivo |
| esecuzione **senza** amministratore | PASS | con UAC disattivato (`EnableLUA=0`) non esistono processi non elevati: provato con un token ristretto (`CreateRestrictedToken` LUA_TOKEN). `--dry-run` avvisa "NOT elevated" e esce 0; `--yes` esce 3 senza modificare nulla |
| GUI (`fili-gui`) | avvio verificato | lista dispositivi (circa 8 s); le azioni usano la CLI con anteprima e conferma; logica coperta da `tests/test_gui.py`. Non provate le azioni dalla finestra |

Pulizia: nessun pacchetto libwdi rimasto; rimosso solo il certificato `CN=<chiavetta>`; i quattro certificati di
altri strumenti sono intatti.

Ancora **non** provati: Windows 10, Memory
Integrity, Secure Boot, ARM64/32 bit.

## 6. Terza serie: telefono Android `<telefono>` (14/10/2026)

Il dispositivo usava gia' il WinUSB di Windows (`winusb.inf`, Microsoft, nessun pacchetto OEM). Cambiato solo il driver sul PC.

| Prova | Esito | Note |
|---|---|---|
| `install --driver libusbk` | PASS | `libusbK` 3.1.0.0; il provider del pacchetto e' `libusbK`, non `libwdi` |
| `reinstall` | PASS | secondo pacchetto (`oem191.inf`) |
| `restore` | **difetto 6, corretto** | rimuoveva solo il pacchetto in uso: il dispositivo restava su libusbK con il primo (`oem181.inf`) e `fili` diceva OK. Il ciclo dei pacchetti residui riconosceva solo il provider `libwdi`; ora conta anche il servizio (winusb, libusbk, libusb0) |
| `restore` (con la correzione) | PASS | torna a `winusb.inf` / Microsoft, nessun pacchetto rimasto |
| `install --driver libusb-win32` e `restore` | PASS | `libusb0` 1.4.0.0, poi di nuovo `winusb.inf` |

Pulizia: rimosso solo il certificato `CN=<telefono>`; i quattro preesistenti sono intatti. Il telefono non e' stato
toccato (solo il driver sul PC).

## 7. Quarta serie: dispositivo con bootloader di firmware `<bootloader>` (14/10/2026)

Dispositivo senza driver (problema 28), bootloader di firmware. Caso classico da Zadig.

| Prova | Esito | Note |
|---|---|---|
| `install --driver winusb` (da "nessun driver") | PASS | problema 0; il dispositivo resta presente e stabile (30 s) |
| `restore` | **il dispositivo non torna** | `fili` esce 0 e avvisa che il dispositivo non e' piu' elencato; subito dopo la rimozione del pacchetto Windows lo vede come `0000:0002`, "richiesta descrittore dispositivo non riuscita" (ripetuto 3 volte). Si risolve staccando e riattaccando il cavo, e il dispositivo torna senza driver (problema 28 -> OK senza servizio) |

Isolato installando e ripristinando in due passi distinti: l'installazione non fa danni, il guasto compare con la
rimozione del driver (`pnputil /delete-driver /uninstall /force`). E' un comportamento del dispositivo, non di fili: dopo
un cambio di driver Windows lo riavvia e il bootloader non risponde piu'. Il messaggio di `fili` ora suggerisce di staccare
e riattaccare il dispositivo. libusbK e libusb-win32 su questo dispositivo non ancora provati.

---

**English summary.** Second set of real runs, on a **physical device**: the PC's built-in webcam (`<webcam>`,
composite, interface `MI_00`, Windows 11 Pro, Secure Boot and HVCI off, third-party antivirus installed). `install` with WinUSB,
libusbK, libusb-win32, `--name`, `usbser` (installs, the device reports problem 10 as expected), `reinstall`, `restore` and
`cert-remove` pass; `--wcid` fails cleanly because the camera has no WCID. Fixes: retry on libwdi -15 (seen once, not
reproduced, probably the antivirus), `cert-remove` listing nothing when started from PowerShell 7 (the `Cert:` drive was
missing: now uses `X509Store`), `restore` of a libwdi `usbser` package, clearer `--wcid` error. The system was restored to its
initial state. Not tested: identical devices, `--filter`, non-elevated run, Windows 10 / HVCI / Secure Boot, ARM64.

**Second series (14 Oct 2026).** USB flash drive `<chiavetta>`: WinUSB install/restore pass; `--filter` installs libusb0 as an
upper filter and the drive reports problem 39 (reported, exit 6); `restore` could not undo it (defect 5, fixed:
it now removes `libusb0` from UpperFilters and restarts the device). Non-elevated run verified with a restricted token
(exit 3, dry-run warns). GUI starts and lists devices.

**Third series.** Android phone `<telefono>` (in-box WinUSB): libusbK and libusb-win32 install/restore pass; after `reinstall`, `restore` left the device on the first libusbK package because only the `libwdi` provider was recognised (defect 6, fixed: the service counts too).

## 5. Due dispositivi identici (B13) — 19/10/2026

Due adattatori Ethernet-USB identici (`<adattatore>`, due istanze con numero di serie diverso: «A» e «B»), Windows 11 Pro x64.

- `install` senza `--instance`: codice 5, nulla cambia (PASS).
- **Difetto trovato:** `install --instance <#3>` con `wdi-simple` (senza `-x`) installava WinUSB su **entrambi** i dispositivi,
  perché `wdi-simple` e `UpdateDriverForPlugAndPlayDevices` lavorano per ID hardware, e `restore --instance` si rifiutava di
  togliere il pacchetto condiviso. `pnputil /add-driver /install` ha lo stesso limite (nessuna opzione per l'istanza).
- **Correzione:** con dispositivi identici `install` prepara e firma il pacchetto con `wdi-simple -x`, lo mette nell'archivio
  driver con `pnputil /add-driver` (senza `/install`) e lo associa a quella sola istanza con `DiInstallDevice`
  (`DI_ENUMSINGLEINF`, così non può vincere un altro pacchetto). `--all-matching` richiede il vecchio comportamento
  e lo dichiara; `--filter` lo richiede obbligatoriamente.
- **Rieseguito:** #3 → `WinUSB` / `oem55.inf` / provider libwdi, #2 invariato (driver del produttore, `oem44.inf`); `restore --instance`
  riporta il #3 al driver del produttore; il certificato nuovo rimosso con `cert-remove`. Stato finale uguale a quello iniziale.
- Il pacchetto resta nell'archivio driver con lo stesso ID hardware dell'altro dispositivo finché non si fa `restore`: se il
  dispositivo gemello viene ricollegato Windows sceglie per rango, e il driver del produttore (più recente) vince.

## 6. Altre prove sul sistema reale (19/10/2026)

Windows 11 Pro x64, Secure Boot attivo, HVCI disattivato, antivirus di terze parti.

| Prova | Esito |
|---|---|
| B11 `install` senza amministratore (per istanza e `--all-matching`) | PASS: codice 3, driver e certificati invariati |
| B14 composito senza `--iface` | PASS: codice 5 |
| B16 classe protetta (HID) senza `--force` | PASS: codice 2 |
| B17 scollegamento durante l'installazione (**rimozione simulata** con `pnputil /remove-device`, non fisica) | PASS: codice 6, messaggio con il comando di pulizia, recuperabile |
| B18 `wdi-simple` che esce con codice ≠ 0 | PASS dopo la correzione: lo stdout del programma ora arriva nel log a livello ERROR |
| B20 `fili.toml` (default applicati, CLI prevale, `yes` rifiutato) | PASS |
| WinUSB / libusbK / libusb-win32 / usbser su una sola istanza | PASS |
| `install --filter --all-matching` | non provato sugli adattatori di rete (vedi sotto); `--filter` su un dispositivo singolo: PASS, sezione 7 |

### `--filter` sugli adattatori di rete: non riuscito

Provato sui due adattatori Ethernet-USB, **non** è riuscito:

- primo tentativo: ha messo il filtro `libusb0` sul solo adattatore A e `fili` non è più tornato;
- secondo tentativo: `wdi-simple --filter` risponde «Other error» (codice -99), exit 6, nessuna modifica;
- `restore` toglie il filtro dal registro, ma `pnputil /restart-device` sull'adattatore di rete è rimasto appeso oltre 15 minuti.

Il blocco era legato al driver di rete del produttore, non a `fili`: la sezione 7 lo conferma su un dispositivo senza driver proprietario.
Non provati: Windows 10, Memory Integrity (HVCI attivo), ARM64 e 32 bit.

## 7. `--filter` su una chiavetta sacrificabile (20/10/2026)

Dispositivo: chiavetta USB `ABCD:1234` (archiviazione di massa, `usbstor.inf`, volume FAT32), Windows 11 Pro x64,
terminale PowerShell con diritti di amministratore. Prima della prova: nessun `UpperFilters`, due certificati libwdi di altri strumenti
(di altri strumenti).

| Passo | Esito |
|---|---|
| `install --driver libusb-win32 --filter --force --yes` | `wdi-simple --filter` riesce; `UpperFilters = libusb0`, driver ancora `USBSTOR`, stato OK, problema 0, volume sano e leggibile. **`fili` però usciva con 6**: difetto 7 sotto |
| `restore --force --yes` | PASS: codice 0, `libusb0` tolto dal registro, `pnputil /restart-device` termina subito (nessun blocco), `USBSTOR` e volume sani |
| `cert-remove --thumbprint <impronta> --yes` | PASS: rimosso solo il certificato di `ABCD:1234`; gli altri due intatti |

Stato finale uguale a quello iniziale: nessun filtro, nessun pacchetto `ABCD` nell'archivio driver, stesso driver `USBSTOR`.

**Difetto 7, corretto.** Il controllo finale di `install` si aspettava `libusb0` come servizio del dispositivo, ma con `--filter` il driver
resta quello originale e `libusb0` è solo un filtro superiore: un'installazione riuscita usciva con «the device uses 'USBSTOR', expected
'libusb0'» e codice 6. Ora con `--filter` il servizio non viene confrontato; due test in `tests/test_filter.py`.

**Nota sulla seconda serie (altra chiavetta, `<chiavetta>`).** Lì lo stesso comando portava la chiavetta in problema 39 (DRIVER_FAILED_LOAD). Su questa
chiavetta no: l'esito dipende dal dispositivo e dal suo driver, quindi `--filter` resta un'opzione da usare con `status` e `restore` a portata di mano.

## 8. Versioni compilate e installer (20/10/2026)

Windows 11 Pro x64, PyInstaller `--onefile`, Inno Setup 6.7.3. Dopo ogni passo un controllo in sola lettura confronta
tutti i dispositivi USB collegati, i servizi `USBHUB3`/`USBXHCI`/`usbccgp` e il volume della chiavetta con lo stato iniziale; le prove si
sarebbero fermate al primo peggioramento (mai successo: le segnalazioni erano dispositivi collegati o scollegati da chi provava).

| Prova | Esito |
|---|---|
| `fili.exe`: `--version`, `list` (anche `--json`), `status`, `licenses`, `cert-remove` (elenco) | PASS |
| `fili.exe` con i due adattatori identici: `install` senza `--instance` (codice 5); dry-run per istanza, `--all-matching`, `--filter` senza `--all-matching` (codice 2) e con; `reinstall` (codice 2, driver del produttore); senza `--yes` (codice 7); classe protetta senza `--force` (codice 2) | PASS (14 casi) |
| `fili-gui.exe`: parte, finestra «fili 0.1.0», risponde | PASS (controlli interni non leggibili: Tk non li espone all'accessibilità) |
| Installer silenzioso con task PATH, in una cartella di prova | PASS: file attesi, voce di disinstallazione, `PATH` aggiornato mantenendo il tipo `REG_SZ`, `fili.exe` installato trova `wdi-simple.exe` accanto a sé, hash uguali a `SHA256SUMS` |
| Disinstallazione silenziosa | PASS: cartella e voce rimosse, `PATH` identico a prima |
| Driver nell'archivio e certificati prima/dopo installazione e disinstallazione | invariati (nessuna modifica di sistema oltre a file, voce di disinstallazione e `PATH`) |

Non provato: installazione interattiva (procedura guidata), Windows 10, ARM64/32 bit, firma del codice (gli `.exe` e l'installer non sono
firmati: SmartScreen può avvisare).
