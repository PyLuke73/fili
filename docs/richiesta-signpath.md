# Richiesta di firma gratuita a SignPath Foundation (archivio)

> **Archivio.** La richiesta è stata inviata a ottobre 2026 e **non è stata accolta**: la firma di SignPath Foundation non è disponibile
> per fili. Il progetto resta non firmato durante la fase di pre-release (vedi la sezione «Code signing» del README). Questo file si conserva
> come riferimento, nel caso si riprovi, e per le risposte già preparate; le condizioni di SignPath possono essere cambiate nel frattempo.
> Un'eventuale nuova richiesta richiede di rileggere https://signpath.org/terms e di aggiornare i campi qui sotto.

Modulo: https://signpath.org/apply (condizioni: https://signpath.org/terms). Sotto, i campi del modulo (come risultano dal PDF
della pagina) con la risposta pronta. **Il repository deve essere pubblico prima dell'invio.** I campi con `*` sono obbligatori.

| Campo | Risposta |
|---|---|
| Project Name* | `fili` (Una ricerca su Google deve identificare il progetto: cercare "fili USB driver" dopo la pubblicazione e, se serve, usare "fili USB driver replacement"). |
| Repository URL* | `https://github.com/PyLuke73/fili` |
| Homepage URL* | `https://github.com/PyLuke73/fili` (la pagina del repository va bene; meglio non usare l'indirizzo della singola release) |
| Download URL | `https://github.com/PyLuke73/fili/releases` (la pagina deve dire che il progetto usa SignPath Foundation: vedi sotto) |
| Privacy Policy URL | `https://github.com/PyLuke73/fili/blob/main/PRIVACY.md` (il modulo rifiuta gli indirizzi con `#`; la politica di firma è nella sezione "Code signing policy" del README) |
| Wikipedia URL | lasciare vuoto |
| Tagline* | `Replace the driver of a USB device on Windows, from the command line or a small window.` |
| Category* | scegliere dall'elenco la voce più vicina a "system utilities" / "drivers / hardware tools" |
| Description* | `fili replaces the driver of a USB device or interface on Windows (WinUSB, libusbK, libusb-win32 or the serial driver), like Zadig but scriptable. It has a command line and a small graphical window, shows exactly what it will do before changing anything, refuses to touch keyboards, mice, disks and Bluetooth unless forced, and can undo its changes.` |
| Reputation* | vedi il testo qui sotto |
| First Name*, Last Name*, Email* | i tuoi dati (account SignPath); non vanno scritti nel repository |
| Company Name | vuoto (progetto personale) |
| Maintainer Type | "Individual" / singola persona, se c'è |
| Build System* | `GitHub Actions` |
| Primary Discovery Channel* | la risposta vera (come hai conosciuto SignPath Foundation) |

## Testo per "Reputation"

> fili is a new project (first pre-release 0.1.0, October 2026), so it has no download history yet. What exists: an open
> repository under GPL-3.0-or-later with about 170 automated tests, a documented test plan and reports of real-hardware tests
> (docs/ in the repository), and a reproducible build on GitHub Actions. It is a scriptable alternative to Zadig, a tool the
> community already trusts for the same task. Unsigned, Windows SmartScreen warns about every download, which is what the
> signature would fix. I will add links to discussions or articles as soon as they exist.

È onesto: un progetto così nuovo potrebbe essere rimandato per mancanza di reputazione. Più segnali (stelle, un post su un forum
di libusb o di sviluppo USB, qualche download) aiutano; si può anche fare la richiesta qualche settimana dopo la pubblicazione.

## Prima dell'invio

1. Controllo finale che nel repository e nella storia non ci siano dati personali (lo rifaccio io subito prima).
2. Rendere pubblico il repository (Settings, Danger Zone, Change visibility).
3. Il file `docs/SignPath Foundation.pdf` è la copia della pagina del modulo: non è parte del progetto, **non va pubblicato**; toglierlo dalla cartella prima della pubblicazione.
4. Download URL: la pagina delle release deve dire che si usa SignPath Foundation. Si aggiunge alle note della release **dopo** l'approvazione
   ("Free code signing provided by SignPath.io, certificate by SignPath Foundation"); fino ad allora il README dice "richiesta inviata, non ancora concessa".

## Punti che il revisore potrebbe sollevare

* *"Bypass security measures" / "change system configuration":* fili installa driver e un certificato autofirmato (come Zadig, che usa libwdi). È
  dichiarato nel README, nella prima pagina dell'installer e prima di ogni modifica (anteprima, conferma, classi protette rifiutate senza `--force`), e `fili cert-remove` lo toglie.
* *"Own binaries only":* per questo `wdi-simple.exe` non si firma.
* *Reputazione:* vedi sopra.
* *"Trasferimenti di dati" (termini di SignPath):* dalla v0.2.0 esiste un controllo degli aggiornamenti, ma parte solo su richiesta dell'utente
  (`fili update`, voce di menu della finestra) o con la casella "Check for updates at startup", **spenta di default**. Fa una sola richiesta anonima
  all'API pubblica di GitHub, non invia dati dell'utente e non scarica né installa nulla. È descritto in `PRIVACY.md` e nella sezione "Code signing policy" del README.
