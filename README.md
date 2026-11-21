# Kitilix

[English](https://github.com/vroby65/kitilix/tree/main) · [Release](https://github.com/vroby65/kitilix/releases/latest)

Kitilix è un terminale Linux con barra strumenti, schede e pannelli nella stessa
finestra di Kitty. Usa Kitty 0.51.0 per rendering OpenGL, PTY, input e
protocollo grafico.

## Eseguibile Linux

Scarica [kitilix-linux-x86_64-it](https://github.com/vroby65/kitilix/releases/latest/download/kitilix-linux-x86_64-it)
per Linux x86-64 e Xorg. Il rilascio contiene un singolo eseguibile ELF.

```bash
chmod +x kitilix-linux-x86_64-it
./kitilix-linux-x86_64-it
```

Il file include Kitty, `kitten`, Python, font e shader. Il runtime si
estrae in una directory privata sotto `TMPDIR` (per impostazione
predefinita `/tmp`) e viene rimosso all'uscita. All’avvio servono Bash,
GNU tar e le librerie grafiche del sistema. Il file è compilato e
collaudato su Mint 22.3 con glibc 2.39.

Le impostazioni personali si trovano in `~/.config/kitilix/`, oppure
sotto `XDG_CONFIG_HOME` se impostata. Comprendono `kitty.conf`,
`preferences.json` e `layout.json`.

- `./package.sh` genera `dist/kitilix` dalle sorgenti.
- `./install.sh` copia l'ELF in
  `${XDG_DATA_HOME:-~/.local/share}/kitilix/kitilix` e registra la voce
  di menu con la relativa icona.

## Avvio in sviluppo

```bash
git clone --branch italiano https://github.com/vroby65/kitilix.git
cd kitilix
./run.sh
```

La prima esecuzione scarica gli archivi verificati di Kitty e SIMDe e
compila il motore in `.build/`. Le esecuzioni successive usano la build
locale. L'installazione di Kitty della distribuzione può essere usata
contemporaneamente.

Sono disponibili gli stessi argomenti per `run.sh` e per l’eseguibile.

- `--fresh` apre un terminale nella home senza caricare il layout.
- Un percorso di directory apre un terminale lì, anche se esiste un
  layout salvato.

### Dipendenze

Linux Mint 22.3 su x86_64 e X11 è la piattaforma collaudata. Per compilare servono
Python 3.12 con gli header, GCC, pkg-config, gli strumenti base Debian e le
librerie di sviluppo elencate qui con i nomi Debian/Ubuntu/Mint.

```text
build-essential curl xz-utils patch pkg-config python3-dev
libharfbuzz-dev libfontconfig-dev libfreetype-dev libpng-dev liblcms2-dev
libxxhash-dev libssl-dev zlib1g-dev libcairo2-dev libpixman-1-dev
libdbus-1-dev libx11-xcb-dev libxcursor-dev libxrandr-dev libxi-dev
libxinerama-dev libxkbcommon-x11-dev libgl1-mesa-dev
```

Per l’avvio serve una sessione Xorg con OpenGL funzionante. La
compilazione usa gli shader, il font dei simboli e `kitten` della stessa
release ufficiale. I pacchetti di sistema vanno gestiti separatamente.

## Interfaccia

Passa il mouse sulle icone per leggere l'azione. Da sinistra trovi
**Miniature**, **Nuova scheda** e **Disposizioni**. Seguono Nuovo terminale,
i due comandi di suddivisione, Chiudi pannello, Massimizza o ripristina
pannello, Salva layout e Preferenze. La **× all’estrema destra** chiude
la scheda attiva con i suoi pannelli.

- **Suddivisioni e disposizioni.** Trascina il separatore di due pannelli.
  Il pulsante delle disposizioni offre Suddivisioni, Affiancati,
  Sovrapposti, Griglia e Un solo pannello. Con quattro pannelli la griglia
  ha due righe e due colonne. Cambiare disposizione mantiene le sessioni.
- **Schede e pannelli.** Clicca una scheda per attivarla, fai doppio clic
  per rinominarla e trascinala sulla barra per riordinarla. Trascina
  l'intestazione di un pannello su un altro pannello o sulla scheda di
  destinazione. Per spostarlo da tastiera, usa `Ctrl+Shift+F` /
  `Ctrl+Shift+B`. `Ctrl+Shift+←` / `Ctrl+Shift+→` cambiano scheda.
- **Sidebar.** Il pulsante mostra una miniatura cliccabile per ogni
  scheda, con tutti i suoi pannelli. La sidebar mostra anche titolo,
  processo e directory dove disponibili. Le miniature
  vengono acquisite anche per le schede inattive. Usa la rotellina per
  raggiungere le altre e **Aggiorna miniature** per acquisirle di nuovo.
- **Preferenze.** Cambia la dimensione del carattere per la finestra
  corrente, abilita il ripristino all'avvio, modifica o ricarica
  `kitty.conf`. Per impostare una dimensione permanente usa `font_size`
  in quel file.
- **Input e shell.** `Ctrl+Shift+C` copia la selezione e
  `Ctrl+Shift+V` incolla. Kitty usa la shell dell'utente. Puoi scegliere
  esplicitamente `shell fish` o `shell /bin/bash` in `kitty.conf`.

## Configurazione e ripristino

`~/.config/kitilix/` contiene `kitty.conf`, `preferences.json` e
`layout.json` quando salvi. Si applica `XDG_CONFIG_HOME`, se impostata.
`kitty.conf` viene letto dopo i valori predefiniti del progetto.

**Salva layout** salva le schede della finestra corrente, i loro nomi,
le disposizioni e le proporzioni, il pannello attivo e le directory
locali rilevate. All'avvio successivo vengono aperte **nuove shell**.
Processi in esecuzione, variabili della shell, scrollback e immagini
precedenti terminano con la sessione. Le directory che non esistono più
vengono sostituite dalla home.

## Immagini e collaudo

Dentro Kitilix esegui `kitten icat immagine.png` oppure
`kitten icat immagine.jpg`. Per mantenere le immagini visibili anche
quando restringi un pannello usa `kitten icat --align left immagine.png`.
Le immagini seguono le normali regole di posizionamento e scrollback
di Kitty. Un'immagine ancorata a colonne che escono dal pannello può
essere tagliata mentre il pannello è stretto.

```bash
./tests/run-x11.sh
./tests/run-x11.sh images
KITILIX_TEST_LAUNCHER="$PWD/dist/kitilix" ./tests/run-x11.sh
XDG_DATA_HOME="$PWD/.build/install-test" ./install.sh
TMPDIR="$PWD/.build/tmp" xvfb-run -a python3 tests/benchmark.py
```

Il collaudo richiede `xvfb`, `xauth`, `xdotool`, `xclip` e
`python3-pil`. Compila Kitilix, apre un display X11 isolato e usa input
X11 e screenshot reali. La modalità `images` verifica i pixel di PNG e
JPEG dopo resize, split, cambio scheda e scroll, oltre alle miniature delle
schede attiva e inattiva.
`fish`, se disponibile, viene provata nel test completo.
I file del collaudo restano in `.build/`.

Il benchmark confronta Kitty 0.51.0 con Kitilix avviato tramite
`run.sh`, compilati con gli stessi flag. Misura la mediana del tempo
fino alla prima finestra X11 mappata, la memoria PSS del processo
principale e la sua CPU a riposo.
Su Mint 22.3 con Xvfb, in cinque avvii misurati per variante, le mediane
sono state 419 ms e 98,7 MiB per Kitty, 491 ms e 98,4 MiB per Kitilix.
Nessun tick CPU è stato rilevato nell'intervallo a riposo di 2 secondi.
Per misurare sul display X11 corrente,
esegui `python3 tests/benchmark.py` durante una sessione inattiva.

## Licenza

GPL-3.0-only per il codice Kitilix. La patch si applica al sorgente Kitty
GPLv3 della [release 0.51.0](https://github.com/kovidgoyal/kitty/releases/tag/v0.51.0).
Il font Symbols Nerd Font Mono conserva la propria licenza MIT
in [LICENSE.symbols](packaging/LICENSE.symbols).
L'eseguibile include gli avvisi di licenza di Python.
Il repository contiene il sorgente delle modifiche e gli script per
riprodurre la build.

Vedi [ARCHITECTURE.md](ARCHITECTURE.md) per i confini della patch e
[AGENTS.md](AGENTS.md) per il flusso di sviluppo.
