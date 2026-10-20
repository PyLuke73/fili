# Risultati delle prove di installazione (11/10/2026)

*English summary at the end.*

Prima esecuzione **reale** dei comandi che modificano il sistema. Le prove sono state fatte in una macchina
virtuale usa e getta, non su un PC di lavoro.

## 1. Ambiente

| Voce | Valore |
|---|---|
| Sistema | Windows Server 2022 Standard Evaluation (esperienza desktop), italiano, x64 |
| Macchina virtuale | VirtualBox 7.2.20, 1 CPU, 4 GB RAM, USB xHCI, Guest Additions 7.2.20 |
| Dispositivo di prova | **tablet USB virtuale** di VirtualBox (`80EE:0021`, classe HID, driver di partenza `HidUsb` / `input.inf`). Esiste solo nella macchina virtuale |
| Python | 3.12.2 portatile (embeddable), solo libreria standard |
| `wdi-simple.exe` | libwdi v1.5.1 compilato a mano (SHA-256 `3cae635b…19af9`), driver incorporati: WDK 8.0 redist, libusb-win32 1.4.0.0, libusbK 3.1.0.0 (build del 13/10/2026; dal 20/10/2026 senza co-installer WDK, vedi `docs/licenza.md`) |
| Esecuzione | tutto con `VBoxManage guestcontrol`, account amministratore (reindirizzando l'output) |

Perché non una chiavetta USB reale: il passaggio della chiavetta (USB 3) dal PC alla macchina virtuale è rimasto
bloccato in VirtualBox («dispositivo occupato da una richiesta precedente»), anche dopo il riavvio dei servizi e con
filtri USB. La chiavetta è stata restituita al PC senza modifiche (stessa quantità di dati e stessi elementi di prima).

## 2. Esito

| ID | Prova | Esito | Note |
|---|---|---|---|
| P1 | `status` su un dispositivo | PASS | driver, pacchetto, versione e provider corretti |
| P2 | `install --dry-run` su classe HID **senza** `--force` | PASS | rifiutato, codice 2, messaggio chiaro |
| P3 | `install --dry-run --force` | PASS | mostra piano, avviso e comando; non esegue nulla |
| P4 | `install --force` **senza** `--yes` | PASS | rifiutato, codice 7 |
| P5 | `extract` | PASS | scrive solo `fili.inf` non firmato; nessun certificato creato |
| P6 | `install` WinUSB (vero) | PASS | 70-76 s; driver WinUSB, stato OK; certificato in Root e TrustedPublisher |
| P6b | `install` libusbK (vero) | PASS | driver `libusbK`, stato OK |
| P6c | `install` libusb-win32 (vero) | PASS | driver `libusb0`, stato OK |
| P6d | `reinstall` | PASS | crea un secondo pacchetto (vedi difetto 2) |
| P7 | `restore` dry-run / senza `--yes` / vero | PASS dopo le correzioni | vedi difetti 1 e 2 |
| P8 | `cert-remove` elenco / dry-run / senza `--yes` / thumbprint sbagliato / vero | PASS | thumbprint sbagliato rifiutato (codice 2); i certificati spariscono da entrambi i depositi |
| P9 | `diagnose` dopo l'installazione | PASS | codice problema 0, pacchetto e provider, righe di `setupapi.dev.log`, eventi di Windows |
| P10 | log: `--log-file`, formato JSON | PASS | righe JSON tutte valide |
| P11 | ciclo completo ripetuto 3 volte (install → reinstall → restore → cert-remove) | PASS | archivio driver e certificati puliti alla fine |

Dopo ogni `restore` il dispositivo è tornato su `HidUsb` / `input.inf` (Microsoft) e `pnputil /enum-drivers` non
mostrava più pacchetti `libwdi`.

## 3. Difetti trovati e corretti

1. **Codifica dell'output (`restore` finiva con codice 2).** `pnputil` scrive in italiano con la codepage OEM (cp850).
   `fili` decodificava l'output come UTF-8 (con sostituzione) e poi non riusciva a stampare il carattere `U+FFFD` su
   uno stdout reindirizzato a cp1252 (`'charmap' codec can't encode …`). Il ripristino veniva eseguito ma il comando
   si interrompeva prima di `pnputil /scan-devices` e restituiva errore. **Correzione:** decodifica UTF-8, in
   alternativa la codepage OEM (`decode_output`); gli stream di uscita sostituiscono i caratteri non codificabili
   (`_safe_streams`). Tre test di regressione (`TestEncoding`).
2. **`restore` dopo un `reinstall` lasciava il dispositivo su WinUSB.** `reinstall` crea un secondo pacchetto
   libwdi; `restore` rimuoveva solo quello attivo, e Windows riagganciava l'altro: il comando dava codice 0 ma il
   dispositivo non era tornato al driver originale. **Correzione:** dopo la rimozione, finché il dispositivo è legato
   a un pacchetto `oemNN.inf` con provider `libwdi`, lo rimuove (massimo 5 passaggi, poi errore con codice 6).
   Due test di regressione.
3. **`diagnose` stampava troppi eventi.** Aggiunta l'opzione `--max-events` (predefinito 10).

Entrambe le correzioni sono state riprovate sul sistema vero (ciclo 3, ripetuto da zero).

## 4. Cosa **non** è stato provato

- **Hardware USB reale.** Il bersaglio è un dispositivo virtuale. Mancano: un dispositivo fisico, un dispositivo composito
  con più interfacce (`--iface`), due dispositivi identici (VID/PID ambiguo, `--instance`).
- **Windows 10/11 client.** Provato solo Windows Server 2022. Il piano resta valido per Windows 10 e 11 (sono sistemi
  diversi per criteri di firma, Secure Boot, Core Isolation / Memory Integrity: quest'ultima può bloccare driver di
  kernel non firmati come libusbK e libusb-win32).
- **ARM64, Windows a 32 bit.** `wdi-simple.exe` è stato compilato solo per x64.
- **Esecuzione senza privilegi di amministratore** (il codice 3 è coperto solo dai test automatici con un esecutore
  finto), dispositivo scollegato durante l'installazione, installazione di `--wcid`, `--filter`, `--name`, `usbser` (CDC).
- **Rete e lingua.** Windows in italiano; altre lingue non provate.

## 5. Da fare prima del rilascio

- Ripetere la matrice su Windows 10 e 11 (anche con Memory Integrity attiva) e su un dispositivo fisico, composito.
- Verificare le licenze dei driver incorporati (`docs/licenza.md`) prima di distribuire un binario di `wdi-simple.exe`.
- Provare le opzioni non coperte (sezione 4).

---

**English summary.** First real run of the system-changing commands, in a throw-away Windows Server 2022 VM, on a
VirtualBox virtual USB tablet (`80EE:0021`, HID, started on `HidUsb`). `install` (WinUSB, libusbK, libusb-win32),
`reinstall`, `restore`, `cert-remove`, `diagnose`, `extract`, the refusals (HID class without `--force`, no `--yes`,
wrong thumbprint) and JSON logging all pass. Two real bugs were found and fixed: (1) output decoding/printing with
a redirected, localized `pnputil` (`restore` exited 2); (2) `restore` after `reinstall` left the device bound to an older
libwdi package (now removed in a loop). Not tested: physical devices, composite/ambiguous devices, Windows 10/11
client editions, ARM64/32-bit, non-admin runs.
