# Firma del codice (SignPath) - archivio

> **Archivio.** La richiesta di firma gratuita a SignPath Foundation non è stata accolta (vedi `docs/richiesta-signpath.md`). fili è **non firmato
> durante la fase di pre-release**. Questo file descrive come la build è predisposta per una firma esterna, se in futuro si ottiene da SignPath
> o da un altro servizio. Il flusso `.github/workflows/release.yml` compila e **non firma** finché le variabili e i segreti qui sotto non sono impostati;
> con un altro certificato cambierebbero solo i due passaggi «Firma …» del flusso.

fili aveva chiesto la firma gratuita di **SignPath Foundation** per i progetti open source. Sotto: come è collegata la build e cosa andrebbe
configurato se la firma venisse concessa.

## Cosa si firma

| File | Si firma? | Perché |
|---|---|---|
| `fili.exe`, `fili-gui.exe` | sì | compilati da questo repository |
| `fili-setup-<versione>.exe` | sì | compilato da questo repository |
| `wdi-simple.exe` | **no** | compilato da libwdi (codice di terzi): SignPath firma solo software costruito dal proprio sorgente |

## Configurazione dopo l'approvazione

1. In SignPath: creare il progetto e collegare il repository `PyLuke73/fili` con il connettore "GitHub Actions trusted build system".
2. In SignPath: due configurazioni di artefatto (file ZIP con `fili.exe` + `fili-gui.exe`; file ZIP con l'installer), con
   restrizioni sui metadati: `ProductName` = `fili`, `ProductVersion` uguale in tutti i file (li scrive `scripts/make_version_info.py`
   e le righe `VersionInfo*` di `packaging/fili.iss`).
3. In SignPath: una politica di firma con **approvazione manuale** di ogni richiesta.
4. In GitHub (Settings, Secrets and variables, Actions):
   * segreto `SIGNPATH_API_TOKEN`;
   * variabili `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_POLICY_SLUG`,
     `SIGNPATH_EXE_CONFIG_SLUG`, `SIGNPATH_SETUP_CONFIG_SLUG`.
   Appena `SIGNPATH_ORGANIZATION_ID` è impostata, il flusso invia gli eseguibili e l'installer a SignPath e aspetta l'approvazione.
5. Attivare l'autenticazione a più fattori su GitHub e su SignPath (condizione del programma).

## Come si pubblica una versione

1. Aumentare `__version__` in `src/fili/__init__.py` e fare il commit.
2. `git tag vX.Y.Z` e `git push origin vX.Y.Z`: il flusso compila, chiede la firma, e crea la release **in bozza** con
   l'installer e `SHA256SUMS`. Si completano le note e si pubblica a mano.
3. Verifica di un download: `Get-FileHash fili-setup-X.Y.Z.exe -Algorithm SHA256` e, se firmato, le proprietà del file (Firme digitali).
4. Dopo la pubblicazione della release, `fili update` e il pulsante "Update available" della finestra la mostrano agli utenti che lo chiedono
   (controllo a richiesta; l'avviso all'avvio è disattivato di default, vedi `PRIVACY.md`). Funziona solo con il repository pubblico.
   Una bozza non è visibile: l'utente vede la versione solo dopo che la release è pubblicata (le pre-release contano, con l'indicazione "(pre-release)").

## Alternative a SignPath (valutate a ottobre 2026)

Da verificare di nuovo sui siti prima di decidere: prezzi e condizioni cambiano.

| Opzione | Costo indicativo | Note per fili |
|---|---|---|
| Azure Artifact Signing (ex Trusted Signing) | circa 10 $/mese | per i singoli sviluppatori solo USA e Canada (aziende anche UE e Regno Unito) |
| Certum «Open Source Code Signing» | da circa 49 € (cloud, SimplySign) o 69 € (carta e lettore) | persona fisica, progetto open source non commerciale (revoca se si firma software commerciale); nel certificato compare il tuo nome con il prefisso «Open Source Developer»; il cloud richiede l'app SimplySign sul telefono, quindi probabilmente la firma va fatta a mano e non in GitHub Actions: da chiedere a Certum |
| Certificato OV (DigiCert, Sectigo, GlobalSign) | circa 150-300 $/anno | valido ovunque; la chiave sta su chiavetta o servizio cloud |
| Microsoft Store (MSIX) | firma gratuita | probabilmente inadatto: fili richiede i permessi di amministratore; non verificato |

In ogni caso SmartScreen costruisce la reputazione col tempo: la firma toglie «editore sconosciuto» ma non fa sparire subito gli avvisi.
