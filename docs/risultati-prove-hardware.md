# Risultati delle prove su hardware fisico (13/10/2026)

*English summary at the end.*

*Nota sulla riservatezza: i dispositivi di prova sono indicati con etichette generiche (`<webcam>`, `<chiavetta>`, `<telefono>`, `<bootloader>`, `<adattatore>`) e senza numeri di serie, nomi di produttori o impronte di certificati; i VID:PID di esempio (`0483:374B`, `ABCD:1234`) sono generici.*

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

## 9. Dispositivi identici: batteria completa (22/10/2026)

Due adattatori Ethernet-USB identici (`<adattatore>`, istanze «A» e «B», driver del produttore `oem44.inf`),
Windows 11 Pro x64, terminale PowerShell con diritti di amministratore, Wi-Fi come rete di riserva. Ogni comando con un
timeout di 4 minuti; dopo ogni passo si rilegge servizio, pacchetto e codice problema di A e di B. I codici di uscita sono
quelli scritti da `fili` nel proprio log (`done (exit N)`). Log in `logs/twins_*.log`.

| Prova | Esito |
|---|---|
| `install` senza `--instance` (codice 5), senza `--yes` (7), `--filter` senza `--all-matching` (2), `reinstall` su driver del produttore (2), `restore` senza `--instance` (5) | PASS |
| Dry-run di `install`, `install --all-matching`, `install --filter --all-matching`; `status` | PASS (codice 0, nessuna modifica) |
| `install --instance` con winusb, libusbK e libusb-win32, su A e su B (6 casi) | PASS: cambia solo il bersaglio, l'altro resta sul driver del produttore |
| `restore --instance` dopo ciascuno dei 6 casi | PASS: il bersaglio torna a `oem44.inf`, problema 0 |
| `reinstall --instance` di A su WinUSB | PASS |
| A su WinUSB e B su libusbK insieme; `restore` di A | PASS: B resta su libusbK |
| A e B entrambi su WinUSB (due installazioni per istanza); `restore` di A | PASS: B resta su WinUSB, il pacchetto di B non viene toccato |
| `install --instance A --json` | PASS |
| `install --instance A --all-matching` (winusb) | PASS: A e B su WinUSB, **stesso pacchetto** |
| `restore` di A, poi di B, dopo `--all-matching` (prima della correzione) | FAIL (difetto 8): codice 2 su entrambi, corretto sotto |
| `restore --all-matching` dopo `install --all-matching` (dopo la correzione) | PASS: senza il flag codice 2 con il suggerimento, dry-run che elenca il gemello, con il flag codice 0 e A e B su `oem44.inf` |
| `cert-remove --thumbprint` del certificato creato dalla prova | PASS |

**Difetto 8 (corretto il 22/10/2026).** Dopo `install --all-matching`, A e B sono legati allo stesso pacchetto (`oem123.inf`).
`restore` rifiutava di rimuoverlo perché lo usa anche l'altro dispositivo («package oem123.inf is also used by: …. Refusing to
remove it.»), su entrambi: con `fili` non c'era modo di annullare un `--all-matching`. Correzione: `restore --all-matching`
(anche `uninstall`, e la casella «All matching» della GUI). Con il flag il pacchetto condiviso si rimuove solo se gli altri
dispositivi che lo usano sono **tutti gemelli** del bersaglio (stesso VID:PID e interfaccia); un dispositivo diverso sullo stesso
pacchetto resta un motivo di rifiuto. Senza il flag il rifiuto resta, e il messaggio indica `restore --all-matching` quando gli
altri sono gemelli. Il piano elenca i gemelli che torneranno al driver originale. Verificato con 4 test nuovi
(`tests/test_twins.py`, tutti i test: 118 verdi) e sui due adattatori: `install --all-matching`, `restore` senza flag (2, per A
e per B), dry-run, `restore --all-matching` (0; A e B su `oem44.inf`, problema 0), `cert-remove` del certificato creato (0).

Stato finale: A e B sul driver del produttore (`oem44.inf`, problema 0). I pacchetti libwdi creati dalla prova sono stati rimossi
dai `restore`; il pacchetto `oem55.inf` del 19/10 (sezione 5) è ancora nell'archivio driver. Un certificato libwdi presente
all'inizio (`<impronta>`, probabilmente creato dal tentativo di `--filter` del 21/10) non c'era più alla fine: `fili` non lo ha
rimosso (rimuove solo con `cert-remove --thumbprint`, e ne è stato rimosso uno solo, `<impronta>`); la causa non è stata accertata.

**`--filter --all-matching` sugli adattatori di rete (21/10/2026), terza prova: non riuscito, come le due precedenti.**
`wdi-simple --filter` mette `libusb0` come filtro superiore solo sull'adattatore A e `fili` non torna più (ucciso dopo 4 minuti);
l'adattatore B non viene toccato. `restore` toglie `libusb0` dal registro, ma `pnputil /restart-device` si blocca. Il driver di
rete del produttore non gestisce il riavvio con il filtro; la chiavetta di archiviazione (sezione 7) funziona. **`--filter` non è
supportato sulle schede di rete.** Se si blocca, `pnputil /restart-device` va terminato e l'adattatore ricollegato.

Non provati: Windows 10, Memory Integrity (HVCI attivo, qui spenta), ARM64 e 32 bit, `--wcid` su un dispositivo che dichiara il
WCID (nessuno disponibile).

## 10. Ricostruzione dopo `restore --all-matching` (22/10/2026)

`fili.exe` e `fili-gui.exe` (PyInstaller 6.16) e l'installer (Inno Setup 6) ricostruiti dal commit `029d39a`; `wdi-simple.exe` e il
bundle non sono cambiati (i `docs` del bundle sono uguali a quelli del repository). `dist\SHA256SUMS` riscritto.

| Prova | Esito |
|---|---|
| `fili.exe --version`, `restore --help` mostra `--all-matching` | PASS |
| Installer silenzioso in una cartella di prova (con i task predefiniti) | PASS: file attesi, `sha256sum -c SHA256SUMS` OK per tutti i 14 file, `fili.exe` installato con `--all-matching` |
| Il task PATH è attivo di default | la cartella è stata aggiunta al `PATH` di sistema |
| Disinstallazione silenziosa | PASS: cartella e voce di disinstallazione rimosse, `PATH` identico a prima (tipo `REG_SZ`) |

Non provato in questa ricostruzione: la procedura guidata interattiva, le azioni dalla finestra della GUI, Windows 10.

## 11. `usb-reset` e limiti di tempo dei comandi (22/10/2026)

Due adattatori Ethernet-USB identici (`<adattatore>`, «A» e «B») dietro lo stesso hub esterno, Wi-Fi come rete di riserva.
Automatico: `tests/test_usbreset.py` (23 test con esecutore finto) e `tests/test_skill.py` (10); tutti i test: 171 verdi.

| Prova | Esito |
|---|---|
| `usb-reset --dry-run` e `--dry-run --hub` (sola lettura) | PASS: trova l'hub esterno sopra gli adattatori e i due dispositivi dietro di esso |
| `usb-reset --instance B --yes` su un adattatore sano | PASS: exit 0 in 57 s, driver originale, problema 0 |
| `usb-reset --instance B --hub --yes` | PASS: exit 0 in 79 s, entrambi gli adattatori tornano, problema 0 |
| `install --filter --all-matching` su A | come le tre prove precedenti: `libusb0` messo su A e `wdi-simple` non finisce (fermato dallo script dopo 100 s); su B nulla |
| `restore` di A dopo il filtro | **exit 6 dopo 206 s** invece di restare appeso oltre 15 minuti: il filtro è tolto dal registro, `pnputil /restart-device` scade dopo 180 s con il suggerimento di usare `usb-reset` |
| `usb-reset --instance A --yes` sul dispositivo bloccato | **exit 6 dopo 199 s**: anche `pnputil /disable-device` scade |
| `usb-reset --instance A --hub --yes` | **exit 6 dopo 222 s**: scade anche la disattivazione dell'hub; nessun processo rimasto, hub e adattatori restano `OK` con problema 0 |

**Conclusione.** I limiti di tempo risolvono il problema di `fili` che restava appeso; `usb-reset` risolve i blocchi in cui il
dispositivo o l'hub rispondono ancora a disattiva/attiva. Quando il driver del produttore è bloccato nel kernel (il caso
di `--filter` su una scheda di rete) nessun comando di Windows ottiene risposta, né sul dispositivo né sull'hub: serve scollegare e
ricollegare il dispositivo (o riavviare). Il controller USB non viene mai riavviato da `fili`. Dopo la prova «Ethernet 2» (A) ha
lo stato di rete vuoto finché non lo si ricollega.

## 12. Ricostruzione con `usb-reset`, limiti di tempo e `--skill` (22/10/2026)

`fili.exe`, `fili-gui.exe` (PyInstaller 6.16) e l'installer (Inno Setup 6) ricostruiti dal commit che contiene `usb-reset`;
`wdi-simple.exe` e il bundle non sono cambiati. `dist\SHA256SUMS` riscritto (installer, `fili.exe`, `fili-gui.exe`, `wdi-simple.exe`).

| Prova | Esito |
|---|---|
| `fili.exe --version`, `--skill` (anche con `--json`), `usb-reset --help`, `list --json` | PASS |
| Installer silenzioso in una cartella di prova | PASS: `sha256sum -c SHA256SUMS` OK per tutti i 17 file; `fili.exe` installato con `--skill` |
| `fili-gui.exe` installato | PASS: parte e resta in esecuzione |
| Disinstallazione silenziosa | PASS: voce di disinstallazione rimossa, `PATH` identico a prima. Nota sulla prova: `fili-gui.exe` (PyInstaller onefile) lancia un processo figlio; se si chiude solo il processo padre il figlio tiene bloccato il file e la cartella resta: chiudere la finestra prima di disinstallare |

Non provato in questa ricostruzione: la procedura guidata interattiva dell'installer, Windows 10, Memory Integrity.

## 13. Procedura guidata dell'installer e azioni dalla finestra della GUI (22/10/2026)

**Procedura guidata (interattiva, Windows 11 Pro, lingua italiana).** Pilotata dall'esterno con i messaggi Win32 (i controlli
Delphi di Inno Setup non sono visibili a UI Automation) e screenshot della sola finestra (`PrintWindow`).

| Prova | Esito |
|---|---|
| Pagine: lingua → contratto di licenza (MIT, «Avanti» disabilitato finché non si accetta) → informazioni → cartella → processi aggiuntivi → riepilogo → «Installazione completata» | PASS |
| Pulsante «Indietro» dalla pagina della cartella (torna alla pagina precedente, poi si prosegue) | PASS |
| Processi aggiuntivi: **la voce nel PATH è selezionata di default**, l'icona sul desktop no; «Esegui fili» a fine installazione è disattivato | PASS (README corretto: il PATH è proposto, non facoltativo di default) |
| Dopo l'installazione: 20 file, `sha256sum -c SHA256SUMS` OK per i 17 file elencati, collegamenti nel menu Start, voce in «App installate» (versione ed editore corretti), cartella nel `PATH` di sistema | PASS |
| Nessun driver e nessun certificato toccati (elenco dei pacchetti driver e dei certificati identico a prima) | PASS |
| Reinstallazione sopra la stessa versione | PASS: una sola voce nel `PATH`, 4 collegamenti, 1 voce in «App installate» |
| Disinstallazione interattiva («Vuoi rimuovere completamente fili…?» → Sì → «Disinstallazione completata») | PASS: cartella rimossa, `PATH` identico a prima, menu Start e voce in «App installate» rimossi, certificati invariati |

L'installer scrive nel registro solo la propria voce di disinstallazione (`HKLM\...\Uninstall\{AppId}_is1`, quella che compare in
«App installate») e, con il task PATH, il valore `Path` di `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment` (stesso tipo
di valore di prima). Al termine della disinstallazione non resta nessuna chiave `fili` né `PyLuke73` in `HKLM` o `HKCU`.

**Azioni dalla finestra della GUI su un dispositivo vero.** App vera con l'esecutore vero, pulsanti premuti con `invoke` (stesso percorso
del clic) e conferme risposte da codice; finestra nascosta. Dispositivo: telefono Android già su WinUSB (`<telefono>`).

| Prova | Esito |
|---|---|
| Avvio, elenco di 14 righe, selezione del dispositivo, driver `libusbk` | PASS |
| Install: anteprima, finestra di conferma (una sola), barra «Step 1 of 2: installing the driver with wdi-simple» | PASS |
| Install: esito | **non riuscito per colpa del dispositivo**: `wdi-simple` risponde «Operation timed out» (exit 4294967289); la GUI mostra l'errore e la barra dice «Stopped: see the output below.»; il dispositivo resta intatto. Lo stesso comando da riga di comando resta fermo in `wdi-simple` come nella GUI (fermato dopo 300 s). Certificati creati dai tentativi rimossi con `cert-remove` |
| Restore dopo l'Install fallito | PASS (comportamento corretto): codice 2, «not an OEM package (inf='winusb.inf'): nothing to remove» |

**Non provato:** un Install e un Restore dalla finestra che finiscano bene su un dispositivo vero (il telefono non ha risposto al cambio di
driver in questa sessione, gli adattatori di rete sono noti per bloccarsi, la chiavetta non era collegata); il clic con il mouse sui widget
(Tk non espone i controlli: la finestra è stata comandata con `invoke`, come nei 20 test di `tests/test_gui_tk.py`); Windows 10; Memory Integrity.
