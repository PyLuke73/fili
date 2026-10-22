# Licenza / License

> **Stato: licenza scelta dal titolare: GPL-3.0-or-later** (Copyright (c) 2026 PyLuke73), testo in `LICENSE`.
> Fino al commit `04a8f9b` il progetto era pubblicato con licenza MIT: chi ha scaricato quelle versioni le conserva con
> i termini MIT; da questa modifica in poi il codice è GPL. Compatibile con le dipendenze: libwdi (LGPL-3.0-or-later) è
> usata come programma esterno, libusb-win32 (GPL) e libusbK (BSD) sono driver ridistribuiti con le loro licenze.
> Questo documento non è un parere legale.
>
> *English summary:* the project is licensed under the **GNU GPL v3 or later** (`LICENSE`). Releases up to commit `04a8f9b`
> were published under the MIT License and stay available under it for whoever obtained them. The text below lists the
> options considered, the dependency obligations, and a release checklist. Not legal advice.

## 1. Fatti verificati nel repository di libwdi (tag v1.5.1, commit `9b23b82`)

| Componente | Licenza (intestazione del file) | Come lo usiamo |
|---|---|---|
| `libwdi/*.c` (libreria) | GNU LGPL v3 o successiva | **non usata direttamente**: è dentro `wdi-simple.exe` |
| `examples/wdi-simple.c` | GNU LGPL v3 o successiva | compilato dall'utente, eseguito come **programma esterno** (sottoprocesso) |
| `examples/zadig.c` (Zadig) | **GNU GPL v3 o successiva** | **non copiato né adattato** (clean room): solo comportamento e documentazione |
| `examples/getopt/*` | GNU LGPL / GNU C Library | dentro `wdi-simple.exe` |
| driver incorporabili (libusb0.sys, libusbK.sys, usbser; i co-installer WinUSB del WDK non più, vedi sotto) | licenze proprie, **non presenti nel repository**: arrivano da cartelle esterne indicate in `configure` (`--with-wdkdir`, `--with-libusb0`, `--with-libusbk`) | **da verificare uno per uno** quando si costruisce un binario da distribuire |
| dati `vid_data.c` (elenco vendor ID, da usb.ids) | da verificare | dentro `wdi-simple.exe` |

Cosa abbiamo e non abbiamo fatto: nessuna riga di `zadig.c` è stata copiata o adattata. Per l'elenco delle funzioni
(`docs/zadig-features.md`) sono stati consultati i testi dei menu (`zadig.rc`), l'esempio `zadig.ini` e, con ricerche
mirate in `zadig.c`, solo i nomi delle azioni e delle opzioni (es. "Install", "Replace", "Reinstall", "Upgrade",
`extract_only`, `list_all`). Il codice di fili è stato scritto da zero. Chi vuole una provenienza documentata può far
rivedere il confronto a una persona che non ha visto il sorgente di Zadig.
**Template INF (risolto).** La prima versione di `INF_TEMPLATE` (`src/fili/extract.py`) era stata scritta da chi aveva
visto anche `libwdi/winusb.inf.in` (LGPL). È stata **riscritta da zero** da chi non ha consultato quel file (la riscrittura è stata fatta in una sessione che non ha mai letto `winusb.inf.in`), partendo dalla struttura documentata da Microsoft in «WinUSB (Winusb.sys) Installation»
(`Include/Needs = winusb.inf`, sezioni `.Services`, `.Wdf`, `.HW`). Le direttive e i nomi di sezione sono quelli imposti dal
formato INF; testo, commenti, nomi delle sezioni locali e valori sono nostri; rimossi `ClassInstall32` e i co-installer (inutili
su Windows 10/11). La provenienza è scritta nel commento sopra `INF_TEMPLATE`. **Validazione con il WDK (11/10/2026).** Eseguito `infverif.exe` 10.0.26100.6584 (WDK 10.0.26100, scaricato dal pacchetto NuGet
`Microsoft.Windows.WDK.x64`, senza installare nulla) con le modalità `/w` (driver Windows) e `/u` (universale) su un INF generato
da `fili extract`, con e senza `--wcid`. Esito: **nessun errore e nessun avviso**, a patto di aggiungere una riga
`CatalogFile`; senza, resta solo `ERROR(1233) Missing directive CatalogFile`, previsto perché l'INF generato è volutamente
senza catalogo e senza firma (solo per ispezione). Le prime versioni dell'INF davano anche `WARNING(1324)` (manca
`PnpLockdown=1`), `WARNING(2083)` (sezioni non usate) e `WARNING(2084)` (servizio `winusb.sys` senza CopyFiles): corretti
aggiungendo `PnpLockdown = 1`, generando solo il blocco GUID usato e passando a `Needs = WINUSB.NT.Services`, lo stesso schema
che usa il `winusb.inf` di Windows per ADB e Billboard. Nota: eseguito da Git Bash, `infverif` mostrava `ERROR(1000) INF '' c...` su qualsiasi INF: era un **artefatto della shell** (Git Bash converte `/w`, `/u` in percorsi di file). Lanciato da PowerShell l'errore non compare, nemmeno sul `winusb.inf` di Windows usato come controllo (che invece dà gli errori attesi per un INF Microsoft: provider, catalogo, ecc.). I risultati qui sopra sono quelli di PowerShell, anche con `/h` (requisiti WHQL): nessun errore con `CatalogFile`. Limiti: `infverif`
controlla sintassi e regole, **non prova l'installazione**: la prova su un dispositivo resta da fare (piano di prove).

## 2. Perché il nostro codice può restare libero

Lanciare `wdi-simple.exe` come processo separato (nessun link, nessun codice incorporato) **non** rende il nostro codice
un'opera derivata della libreria LGPL: le licenze di libwdi riguardano libwdi. Lo stesso vale per `pnputil` e PowerShell.
Lo scenario cambia se: (a) si copia codice di libwdi/Zadig nel nostro sorgente; (b) si incorpora/si collega la libreria;
(c) si distribuisce `wdi-simple.exe` insieme al nostro programma (allora valgono gli obblighi LGPL **per quel binario**,
senza toccare la licenza del nostro codice).

## 3. Opzioni per la licenza di fili

| Opzione | Pro | Contro |
|---|---|---|
| **MIT** | semplicissima, massima adozione, compatibile con tutto | nessuna protezione dei brevetti, nessun obbligo di restituire le modifiche |
| **Apache-2.0** | come MIT ma con concessione esplicita di brevetti e protezione del marchio; ben vista nelle aziende | testo più lungo; incompatibile con GPL-2.0 (ok con GPL-3.0) |
| **GPL-3.0-or-later** | le modifiche ridistribuite restano libere; stessa famiglia di Zadig; nessun attrito se in futuro si volesse riusare codice GPL | chi la integra in software non-GPL non può; meno adatta a uno strumento che si vuole "mettere nei README di tutti" |
| (LGPL-3.0-or-later) | allineata a libwdi | pensata per librerie; poco sensata per una CLI |

Raccomandazione prudente (non vincolante): **MIT o Apache-2.0** se l'obiettivo è la massima diffusione; **GPL-3.0-or-later**
se si vuole che ogni derivato resti libero. In ogni caso: chi sceglie deve essere il titolare dei diritti.
Se in futuro si volesse riusare codice di Zadig, la licenza dovrebbe essere GPL-3.0-or-later (per questo la regola
clean-room in `CONTRIBUTING.md`).

## 4. Obblighi per la distribuzione

**Solo sorgenti di fili (senza binari di terzi)** — consigliato per la prima pubblicazione:
- il file `LICENSE` scelto + le intestazioni di copyright;
- `NOTICE` con le dipendenze (già presente);
- gli utenti costruiscono da soli `wdi-simple.exe` (nessun obbligo LGPL per noi).

**Se si distribuisce anche `wdi-simple.exe`** (binario LGPL-3.0-or-later). Usa lo script, che applica i punti seguenti e
**rifiuta** di creare il pacchetto se manca qualcosa:
`python -I scripts/package_wdi_bundle.py --exe wdi-simple.exe --out dist/wdi-bundle --drivers-file drivers.txt`
(il pacchetto viene creato in una cartella temporanea e rinominato solo a lavoro finito; non installa nulla).
Cosa contiene: `wdi-simple.exe`, `LICENSES/LGPL-3.0.txt` e `GPL-3.0.txt`, `NOTICE`, `LICENSE`,
`THIRD_PARTY/libwdi-SOURCE.txt` (versione, commit, copyright, offerta scritta), l'archivio dei **sorgenti** di libwdi della
stessa versione (scaricato dal tag o passato con `--source-archive`), `THIRD_PARTY/embedded-drivers.txt` (l'elenco dei driver
incorporati con la licenza di ciascuno, **che devi scrivere tu dopo averli verificati**), `docs/building-wdi-simple.md`,
`SHA256SUMS`. Test: `python -I tests/test_bundle.py` (file finti, nessuna rete). Gli obblighi elencati:
- includere il **testo della LGPL-3.0** (e della GPL-3.0 che essa richiama) e un avviso di copyright di libwdi;
- indicare che il binario usa libwdi e dove ottenere il **sorgente corrispondente** (stessa versione/tag); è prudente includerlo
  o fare un'offerta scritta valida (3 anni è la prassi GPL; la LGPL-3 richiede di rendere disponibile il sorgente);
- se il binario incorpora i driver: rispettare le licenze di ciascuno ed elencarli in `NOTICE` dopo averle verificate (i
  co-installer WinUSB del WDK non sono più incorporati: vedi l'aggiornamento seguente);
- permettere al destinatario di ricostruire/sostituire la libreria (LGPL-3): documentare come ricompilare (`docs/building-wdi-simple.md`);
- firmare e pubblicare gli hash dei binari (vedi checklist).

### Aggiornamento (20/10/2026): installer con binari

Per chi vuole solo installare e usare, `scripts/build_installer.ps1` produce `dist/installer/fili-setup-<versione>.exe` (Inno
Setup) che include `wdi-simple.exe` e quindi **accetta gli obblighi della tabella seguente**: usa il pacchetto di
`package_wdi_bundle.py` (testi LGPL/GPL, `NOTICE`, offerta scritta e sorgente di libwdi 1.5.1) più il **sorgente di
libusb-win32 1.4.0.0** (`libusb0.sys` è GPL; hash fissato nello script), e mostra `packaging/INSTALLER_NOTICE.txt`. L'installer
copia soltanto file. Non è una consulenza legale.

**Co-installer WinUSB del WDK: risolto togliendoli (20/10/2026).** Prima il binario incorporava `WdfCoInstaller01011.dll` e
`winusbcoinstaller2.dll` (codice Microsoft «Distributable Code», con obbligo di manleva verso Microsoft per chi li ridistribuisce).
Servono solo a Windows XP/Vista, quindi `scripts/build_wdi_simple.sh` ora li esclude per default: `scripts/strip_coinstallers.py`
li toglie dall'elenco dei file incorporati e dai template INF/CAT di libwdi (modifica a libwdi documentata e riproducibile; il
sorgente di libwdi nel bundle resta quello originale e la patch è nel repository). Il binario scende da ~3,9 MB a ~1,1 MB e non
contiene più nessun file Microsoft (controllato cercando `WdfCoInstaller` e `winusbcoinstaller` nei byte). Prova su Windows 11
x64 con la chiavetta sacrificabile (`scripts/driver_matrix.py`): winusb, libusbk e libusb-win32 si installano e si ripristinano
(PASS), salute USB invariata. **Resta da fare** la stessa prova su Windows 10 (la VM) prima di una release. Chi ha bisogno di
Windows < 10 ricompila con `WITH_COINSTALLERS=1` (e `fetch_wdi_deps.ps1 -WithCoInstallers`) assumendosi le condizioni Microsoft:
nel sorgente pubblico resta quindi questa strada, senza che il repository contenga file Microsoft (si scaricano alla build).

### Decisione originale: sorgente da compilare, non binario

Nel repository e nel pacchetto Python **non c'è nessun binario di terzi**: `wdi-simple.exe` si scarica e si compila con
`scripts/fetch_wdi_deps.ps1` e `scripts/build_wdi_simple.sh` (`docs/building-wdi-simple.md`). Così gli obblighi sotto
ricadono su chi compila e poi distribuisce il proprio binario, non su questo progetto. Un binario pronto si può offrire a
parte (una "release" con il pacchetto di `package_wdi_bundle.py`) solo accettando gli obblighi della tabella seguente.
**Sostituibilità (LGPL-3):** `wdi-simple.exe` resta un file separato che `fili` lancia come programma esterno
(`--wdi`, `$FILI_WDI`, config): chiunque può sostituirlo con una propria compilazione di libwdi senza toccare `fili`.

### Driver incorporabili (verificati il 13/10/2026; elenco completo in `docs/embedded-drivers.txt`)

| Driver | Licenza | Cosa comporta ridistribuirlo |
|---|---|---|
| ~~WinUSB: co-installer del WDK 8.0~~ (`WdfCoInstaller01011.dll`, `winusbcoinstaller2.dll`) **non più incorporati** dal 20/10/2026; condizioni se li reincorpori: | Microsoft Windows Driver Frameworks 1.11, «Distributable Code» | niente modifiche, solo Windows, avviso di copyright, **manleva verso Microsoft**, no licenze copyleft sul codice distribuito; servono solo a Windows vecchi (XP/Vista), non a 10/11 |
| libusb-win32 1.4.0.0 | driver `libusb0.sys` **GPL**; libreria e installer LGPL | testo delle licenze e **sorgente corrispondente** di libusb-win32 1.4.0.0 |
| libusbK 3.1.0.0 | doppia: **New BSD** o GPL, a scelta (lo dichiarano le intestazioni dei sorgenti del driver) | scelta BSD: mantenere avviso e testo, già copiato in `LICENSES/BSD-3-Clause-libusbK.txt` (dal tag V3.1.0.0) e `AUTHORS-libusbK.txt`; non usare il nome dell'autore per promuovere il prodotto |
| CDC (`usbser`) | driver di Windows | niente: non viene ridistribuito |

**Come lo gestisce Zadig (solo comportamento osservato, nessun codice o testo copiato):** il programma ha una finestra di
informazioni con i componenti e la licenza di ciascuno, il testo completo delle licenze, e dichiara che i driver sono
ridistribuibili con i loro termini. Facciamo lo stesso in tre punti: (1) `docs/embedded-drivers.txt` finisce nel pacchetto come
`THIRD_PARTY/embedded-drivers.txt`; (2) `fili licenses` stampa componenti e licenze senza toccare il sistema; (3) i testi
delle licenze stanno in `LICENSES/`. Strada che riduce gli obblighi: compilare `wdi-simple.exe` con **un solo gruppo di
driver** (libwdi accetta anche solo `--with-libusbk`) e togliere dall'elenco gli altri.

## 5. Checklist "cosa devo fare al rilascio"

- [x] Licenza GPL-3.0-or-later scelta (passaggio da MIT): `LICENSE` e `license` in `pyproject.toml` fatti.
- [ ] Controllare che il titolare del copyright («PyLuke73») sia quello voluto (nome reale o handle).
- [ ] Verificare che nessun file contenga codice copiato da Zadig/libwdi (ricerca di commenti `Pete Batard`, `libwdi`, `LGPL`, `GPL`).
- [x] `INF_TEMPLATE` riscritto dalla documentazione Microsoft (§1); da validare con `infverif` e con la prova di installazione.
- [x] `NOTICE` e `docs/embedded-drivers.txt` con le licenze verificate dei driver (13/10/2026); testo BSD di libusbK copiato da libusbK V3.1.0.0 (`LICENSES/`).
- [ ] Se si distribuisce `wdi-simple.exe`: usare `scripts/package_wdi_bundle.py` (testi LGPL/GPL, avviso, offerta e sorgente, versione e commit, istruzioni di ricostruzione, elenco dei driver verificati) e pubblicare `SHA256SUMS`.
- [ ] Controllare che README e `--help` mostrino l'avviso di sicurezza (certificato autofirmato, amministratore, solo dispositivi propri).
- [ ] Marcare nel README ciò che è stato provato davvero e ciò che no (`docs/piano-prove-installazione.md`).
- [ ] Un avvocato o un servizio di compliance se il progetto è commerciale o ridistribuito da un'azienda.
