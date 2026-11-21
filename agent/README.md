# Guida alla manutenzione

`run.sh` applica `packaging/kitilix.conf` e poi il file personale sotto
`XDG_CONFIG_HOME/kitilix` o `~/.config/kitilix`. Avvia il launcher Kitty
compilato da `build.sh` e antepone il relativo `kitten` al PATH dei figli.
`package.sh` usa una build portatile del motore per creare l’ELF
`dist/kitilix`. `install.sh` copia quel file e registra la voce di menu.

- Toolbar, selezione, anteprima, menu e preferenze sono in
  `src/kitilix_ui.py`. Il refresh deriva da resize, input e stato di Kitty.
  Riservare i timer agli eventi a scatto singolo.
- La patch aggiunge gli hook nativi alla release fissata in `build.sh`.
  Varianti sorgente e binaria devono provenire dalla stessa release
  perché le strutture interne e le risorse compilate possono cambiare.
- `src/kitilix_session.py` riapre shell locali con la disposizione salvata.
  L'aggiornamento del layout o delle preferenze usa un file temporaneo
  nella stessa directory, poi una sostituzione atomica.
- Gli asset upstream estratti e le build stanno in `.build/`.
  Le prove usano XDG isolati e un socket remoto locale in una directory
  privata. Il protocollo remoto è disattivato nel profilo ordinario.

## Verifiche di sviluppo

```bash
./build.sh
./tests/run-x11.sh
shellcheck build.sh run.sh package.sh install.sh tests/run-x11.sh
desktop-file-validate packaging/kitilix.desktop
git diff --check
```

Per il collaudo della distribuzione, esegui `./package.sh` e passa
`KITILIX_TEST_LAUNCHER="$PWD/dist/kitilix"` allo script dei test. Il
collaudo controlla l’interprete incluso e la rimozione del runtime.
Usa un `XDG_DATA_HOME` sotto `.build/` per provare l'installazione.
Per le prestazioni, `python3 tests/benchmark.py` costruisce il riferimento
upstream e lo misura sulla stessa sessione X11. Aggiorna README e
ARCHITECTURE quando cambiano uso, configurazione, punto d'integrazione
o comandi di verifica. Riporta l'ambiente e la differenza tra verifica
su Xvfb e verifica sulla GPU.
