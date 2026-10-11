# Licenza / License

> **Stato: licenza scelta dal titolare: MIT** (Copyright (c) 2026 PyLuke73), testo in `LICENSE`. Scelta compatibile
> con l'architettura attuale: nessun codice di Zadig (GPL) copiato, libwdi (LGPL) usata solo come programma esterno.
> Restano aperti: la provenienza di `INF_TEMPLATE` (vedi sotto) e gli obblighi LGPL se si distribuisce un binario di
> `wdi-simple.exe`. Questo documento non è un parere legale.
>
> *English summary:* the project is licensed under the **MIT License** (`LICENSE`). Valid as long as no GPL code from
> Zadig is copied and libwdi (LGPL) stays a separate program. Open points: provenance of `INF_TEMPLATE`, and LGPL duties if a
> `wdi-simple.exe` binary is shipped. The text below lists the options considered, the dependency obligations, and a release
> checklist. Not legal advice.

## 1. Fatti verificati nel repository di libwdi (tag v1.5.1, commit `9b23b82`)

| Componente | Licenza (intestazione del file) | Come lo usiamo |
|---|---|---|
| `libwdi/*.c` (libreria) | GNU LGPL v3 o successiva | **non usata direttamente**: è dentro `wdi-simple.exe` |
| `examples/wdi-simple.c` | GNU LGPL v3 o successiva | compilato dall'utente, eseguito come **programma esterno** (sottoprocesso) |
| `examples/zadig.c` (Zadig) | **GNU GPL v3 o successiva** | **non copiato né adattato** (clean room): solo comportamento e documentazione |
| `examples/getopt/*` | GNU LGPL / GNU C Library | dentro `wdi-simple.exe` |
| driver incorporabili (WinUSB co-installer del WDK, libusb0.sys, libusbK.sys, usbser) | licenze proprie, **non presenti nel repository**: arrivano da cartelle esterne indicate in `configure` (`--with-wdkdir`, `--with-libusb0`, `--with-libusbk`) | **da verificare uno per uno** quando si costruisce un binario da distribuire |
| dati `vid_data.c` (elenco vendor ID, da usb.ids) | da verificare | dentro `wdi-simple.exe` |

Cosa abbiamo e non abbiamo fatto: nessuna riga di `zadig.c` è stata copiata o adattata. Per l'elenco delle funzioni
(`docs/zadig-features.md`) sono stati consultati i testi dei menu (`zadig.rc`), l'esempio `zadig.ini` e, con ricerche
mirate in `zadig.c`, solo i nomi delle azioni e delle opzioni (es. "Install", "Replace", "Reinstall", "Upgrade",
`extract_only`, `list_all`). Il codice di usbdrv è stato scritto da zero. Chi vuole una provenienza documentata può far
rivedere il confronto a una persona che non ha visto il sorgente di Zadig.
Nota di cautela: il generatore di INF di `extract` (`src/usbdrv/extract.py`) è stato scritto seguendo la struttura standard
di un INF WinUSB della documentazione Microsoft, ma l'autore ha avuto sotto gli occhi anche `libwdi/winusb.inf.in`
(LGPL). Se si vuole una provenienza inattaccabile, **far riscrivere o rivedere `INF_TEMPLATE` a chi non l'ha visto**
oppure confrontarlo con l'esempio ufficiale Microsoft.

## 2. Perché il nostro codice può restare libero

Lanciare `wdi-simple.exe` come processo separato (nessun link, nessun codice incorporato) **non** rende il nostro codice
un'opera derivata della libreria LGPL: le licenze di libwdi riguardano libwdi. Lo stesso vale per `pnputil` e PowerShell.
Lo scenario cambia se: (a) si copia codice di libwdi/Zadig nel nostro sorgente; (b) si incorpora/si collega la libreria;
(c) si distribuisce `wdi-simple.exe` insieme al nostro programma (allora valgono gli obblighi LGPL **per quel binario**,
senza toccare la licenza del nostro codice).

## 3. Opzioni per la licenza di usbdrv

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

**Solo sorgenti di usbdrv (senza binari di terzi)** — consigliato per la prima pubblicazione:
- il file `LICENSE` scelto + le intestazioni di copyright;
- `NOTICE` con le dipendenze (già presente);
- gli utenti costruiscono da soli `wdi-simple.exe` (nessun obbligo LGPL per noi).

**Se si distribuisce anche `wdi-simple.exe`** (binario LGPL-3.0-or-later):
- includere il **testo della LGPL-3.0** (e della GPL-3.0 che essa richiama) e un avviso di copyright di libwdi;
- indicare che il binario usa libwdi e dove ottenere il **sorgente corrispondente** (stessa versione/tag); è prudente includerlo
  o fare un'offerta scritta valida (3 anni è la prassi GPL; la LGPL-3 richiede di rendere disponibile il sorgente);
- se il binario incorpora i driver: rispettare le licenze di ciascuno e **le condizioni di ridistribuzione del WDK**
  (Microsoft) per i co-installer WinUSB; elencarli in `NOTICE` dopo averle verificate;
- permettere al destinatario di ricostruire/sostituire la libreria (LGPL-3): documentare come ricompilare (`docs/building-wdi-simple.md`);
- firmare e pubblicare gli hash dei binari (vedi checklist).

## 5. Checklist "cosa devo fare al rilascio"

- [ ] Decidere la licenza e sostituire `LICENSE` con il testo completo; aggiungere `license` in `pyproject.toml`.
- [ ] Mettere nome/anno del titolare nelle intestazioni dove richiesto (non inventare il nome: usare quello reale).
- [ ] Verificare che nessun file contenga codice copiato da Zadig/libwdi (ricerca di commenti `Pete Batard`, `libwdi`, `LGPL`, `GPL`).
- [ ] Rivedere `INF_TEMPLATE` (provenienza, §1).
- [ ] Aggiornare `NOTICE` con le licenze **verificate** dei driver incorporati nel binario che si distribuisce.
- [ ] Se si distribuisce `wdi-simple.exe`: testo LGPL/GPL, avviso, link/offerta del sorgente, versione/tag esatti, istruzioni di ricostruzione.
- [ ] Controllare che README e `--help` mostrino l'avviso di sicurezza (certificato autofirmato, amministratore, solo dispositivi propri).
- [ ] Marcare nel README ciò che è stato provato davvero e ciò che no (`docs/piano-prove-installazione.md`).
- [ ] Un avvocato o un servizio di compliance se il progetto è commerciale o ridistribuito da un'azienda.
