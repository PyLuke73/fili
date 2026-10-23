# Firma del codice (SignPath)

fili chiede la firma gratuita di **SignPath Foundation** per i progetti open source. Questo file spiega come è collegata
la build e cosa va configurato quando la richiesta viene accettata. Fino ad allora il flusso `.github/workflows/release.yml`
compila e **non firma**.

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
