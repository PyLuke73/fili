# Checklist: prove della GUI e dell'installer (da fare sulla build di rilascio)

Da eseguire con gli eseguibili in `dist\` (non con `python -m fili`), in un terminale **normale** per le sezioni A e B e in uno
da **amministratore** per la sezione C. Dispositivo di prova: chiavetta USB sacrificabile oppure i due adattatori Ethernet-USB
identici (la rete passa dal Wi-Fi). Mai tastiera, mouse o disco di avvio.

Legenda: **[auto]** = lo esegue uno script/test automatico; **[man]** = serve una persona davanti allo schermo.

## 0. Prima di iniziare

- [ ] Commit di rilascio pulito (`git status` senza modifiche), eseguibili ricostruiti da quel commit
      (`scripts\build_exe.ps1`, `scripts\build_installer.ps1`).
- [ ] **[auto]** `python -I tests/test_fili.py` e gli altri sei file di `tests\` verdi.
- [ ] **[auto]** `dist\SHA256SUMS` corrisponde ai file (`sha256sum -c`, dalla cartella `dist`).
- [ ] Annotare: `winver`, architettura, `fili --version`, hash di `fili-setup-<versione>.exe`.
- [ ] Stato di partenza: elenco dei certificati libwdi (`fili cert-remove`), `PATH` di sistema, assenza di `C:\Program Files\fili`.

## A. Installer: procedura guidata [man]

Con `fili-setup-<versione>.exe` (doppio clic; SmartScreen può avvisare: gli eseguibili non sono firmati).

- [ ] A1. L'avviso di SmartScreen/UAC compare e si può proseguire; il nome dell'editore è «sconosciuto».
- [ ] A2. Le pagine si leggono (lingua, licenza, cartella `C:\Program Files\fili`, task, riepilogo) e **Indietro** funziona.
- [ ] A3. La pagina dei task mostra: voce nel PATH (**è attiva di default**: decidere se va bene), collegamenti nel menu Start.
- [ ] A4. L'installazione termina senza chiedere il riavvio; la pagina finale non lancia nulla con diritti elevati.
- [ ] A5. In `C:\Program Files\fili` ci sono `fili.exe`, `fili-gui.exe`, `wdi-simple.exe`, `LICENSES`, `THIRD_PARTY`, `SHA256SUMS`.
      **[auto]** `sha256sum -c SHA256SUMS` da quella cartella: tutti OK.
- [ ] A6. Menu Start: i collegamenti si aprono (`fili-gui`) e quello della documentazione/licenze (se c'è) apre il file giusto.
- [ ] A7. Dopo aver riaperto un terminale, `fili --version` funziona (solo se il task PATH era spuntato).
- [ ] A8. «App installate» mostra fili con versione corretta ed editore; **non** è stato installato nessun driver, né aggiunto
      nessun certificato (**[auto]** confronto con lo stato di partenza).
- [ ] A9. Reinstallare sopra la stessa versione: nessun errore, nessun duplicato nel menu Start né nel `PATH`.
- [ ] A10. Disinstallare da «App installate»: scompaiono cartella, collegamenti e voce di PATH (**[auto]** `PATH` identico a prima);
      eventuali file creati dall'utente (log, `fili.toml`) restano.

Parte **[auto]** già verificata con l'installer silenzioso (`/VERYSILENT /DIR=...`): file, hash, PATH, disinstallazione.

## B. GUI (`fili-gui.exe`) [man] e [auto]

**[auto]** La logica è coperta da `tests/test_gui.py`; la finestra vera (tkinter, esecutore finto, conferme risposte da codice) da
`tests/test_gui_tk.py`: avvio e elenco, hub, selezione, anteprima/annulla/conferma di Install e Restore, barra di avanzamento,
utente non amministratore, classe protetta, «All matching» in Restore, Certificates/Licenses/Diagnose, salvataggio, copia riga,
Help/About/Ko-fi, pulsanti disabilitati durante un lavoro. Restano **[man]** l'aspetto grafico, UAC («Restart as Administrator»)
e le prove su un dispositivo vero (B8-B13).

Come utente normale:

- [ ] B1. Parte, il titolo è «fili <versione>», l'elenco dei dispositivi si riempie (qualche secondo).
- [ ] B2. «Hubs» mostra/nasconde gli hub; l'elenco si aggiorna senza bloccare la finestra.
- [ ] B3. Selezionare una riga: i campi cambiano; senza selezione, **Install/Restore** danno «Select a device first».
- [ ] B4. Clic destro su una riga e copia: il testo copiato è quello della riga. Ctrl+C nell'area dei risultati copia la selezione.
- [ ] B5. **Install** su un dispositivo sacrificabile senza essere amministratore: compare l'anteprima (stesso testo del `--dry-run`)
      e l'avviso «servono i diritti di amministratore»; nulla cambia.
- [ ] B6. «Diagnose», «Certs», «Licenses», «About» si aprono e il testo è leggibile; «Save output» salva un file valido.
- [ ] B7. Il pulsante ☕ apre Ko-fi nel browser.

Da amministratore (menu «elevate» oppure terminale elevato), su un dispositivo sacrificabile:

- [ ] B8. **Install** (winusb): anteprima → conferma → la barra di avanzamento mostra «[n/m] …» e finisce; il dispositivo cambia driver.
- [ ] B9. **Reinstall** e **Restore**: la barra arriva in fondo, il driver originale torna, l'elenco si aggiorna.
- [ ] B10. Annullare alla domanda di conferma: nessun comando eseguito.
- [ ] B11. Con i due adattatori identici: **All matching** spuntato → Install e poi Restore con la stessa casella riportano entrambi
      al driver originale (prova del 22/10 in GUI). Senza la casella, Restore dopo All matching dà il rifiuto con il suggerimento.
- [ ] B12. Durante un comando lungo la finestra risponde (si muove, si ridimensiona); chiudendola a metà non resta nulla appeso.
- [ ] B13. Dopo la prova: `fili list` e `fili cert-remove` come all'inizio; rimuovere i certificati nuovi con `--thumbprint`.

## C. Build di rilascio su altri sistemi [man]

Per ogni sistema (Windows 10, Windows 11 con Memory Integrity attiva, Windows in inglese):

- [ ] C1. `python scripts\driver_matrix.py --vid V --pid P` (winusb, libusbk, libusb-win32, restore) sulla chiavetta sacrificabile.
- [ ] C2. Sezioni A e B ridotte: installazione guidata, avvio della GUI, un Install/Restore dalla finestra.
- [ ] C3. Registrare piattaforma e esiti in `docs/risultati-prove-hardware.md`.

## Quali prove NON vanno ripetute a ogni ricostruzione

I comandi da riga di comando sono già coperti dai test automatici (118) e dalla serie su hardware del 22/10. Dopo una
ricostruzione che non tocca `ops.py`, `cli.py` o `wdi-simple.exe` bastano: sezione 0, A5, A10, B1 e B8-B9 una volta.
Se cambia `ops.py` o `cli.py`, ripetere anche i casi di CLI toccati (vedi `docs/risultati-prove-hardware.md` §9).
