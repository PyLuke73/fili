# Privacy policy

fili does not collect, store or send any information about you or your computer.

* **No network access by itself.** `fili.exe`, `fili-gui.exe`, `wdi-simple.exe` and the installer make no network request on their own: no telemetry,
  no crash reports, no automatic update check. Nothing is transferred to other networked systems unless you ask for it (next point).
* **Update check, only when you ask.** `fili update` and *Help > Check for updates* in the window send one anonymous HTTPS request to the public
  GitHub API (`api.github.com/repos/PyLuke73/fili/releases`) and compare the newest published version with the installed one. The request carries
  no data about you, your devices or your PC; GitHub sees your IP address and the program name and version (`fili/<version>`), as for any web visit, and
  has its own [privacy statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement). Nothing is downloaded or installed.
  The window also has a box *Help > Check for updates at startup*: it is **off** until you turn it on, and then checks at most once a day. The choice and the
  time of the last check are kept in `%APPDATA%\fili\settings.json` on your computer. The command line never checks by itself.
* **Only when you ask.** The Ko-fi button and the links in the program open a web page in your own browser. That page belongs
  to the site you open and has its own privacy policy.
* **Local files only.** The log file written with `--log-file` and the files written by `extract` or "Save output" stay on your computer, where you choose.
* **System changes.** Installing a driver adds a self-signed certificate to the trusted stores of this PC (`fili cert-remove` lists and
  removes it). This is stated before every change and nothing is changed without your confirmation.
* **Third-party components.** libwdi, libusb-win32 and libusbK are installed with the program and do not send data either. Their licences are in the `LICENSES` folder of the installation.

If this ever changes, this file will say so first, and any new network feature will be off unless you turn it on.

# Informativa sulla privacy (italiano)

fili non raccoglie, non conserva e non invia alcuna informazione su di te o sul tuo computer. Da solo non fa richieste di rete (né
telemetria, né controllo automatico degli aggiornamenti): il pulsante Ko-fi e i collegamenti aprono una pagina nel tuo browser solo se li usi.
Il controllo degli aggiornamenti parte solo se lo chiedi: `fili update` o *Help > Check for updates* inviano una richiesta anonima all'API pubblica di
GitHub e confrontano l'ultima versione pubblicata con la tua; non viene inviato alcun dato su di te o sul PC (GitHub vede il tuo indirizzo IP, come in ogni
visita a un sito) e non si scarica né si installa nulla. Nella finestra c'è anche la casella *Check for updates at startup*: è **spenta** finché non la accendi e,
se accesa, controlla al massimo una volta al giorno; la scelta è salvata in `%APPDATA%\fili\settings.json`. La riga di comando non controlla mai da sola.
I file di log e quelli salvati restano sul tuo computer. L'installazione di un driver aggiunge un certificato autofirmato agli archivi
attendibili del PC (`fili cert-remove` lo elenca e lo toglie), con avviso e conferma prima di ogni modifica.
