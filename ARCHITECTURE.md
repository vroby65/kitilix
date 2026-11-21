# Architettura di Kitilix

La base è [Kitty 0.51.0](https://github.com/kovidgoyal/kitty/tree/v0.51.0).
Il terminale della distribuzione e la configurazione di Kitty sono indipendenti
da Kitilix.

## Soluzioni valutate

| Soluzione | Integrazione | Impatto |
| --- | --- | --- |
| Controller GTK4 con Kitty originale | Il protocollo remoto controlla finestre, schede, operazioni di layout e focus. GTK e Kitty rimangono superfici distinte. | Nessuna modifica a Kitty, con due finestre separate. |
| Fork minimo della GUI di Kitty | La stessa finestra GLFW contiene i terminali, le schede, la barra strumenti e la sidebar. | Patch confinata a geometria, input e rendering degli elementi di interfaccia, più un modulo Python. |

Kitty crea le proprie finestre tramite il GLFW incluso nel progetto. Il
[protocollo remoto](https://sw.kovidgoyal.net/kitty/remote-control/) scambia
comandi e metadati, senza fornire un widget GTK o una superficie da
incorporare. Su Xorg il reparenting dipenderebbe dal window manager,
dal focus e dalla gestione dei pixel.

Kitilix adotta il fork minimo. La finestra, le PTY, le griglie dei terminali,
gli shader e il [protocollo grafico](https://sw.kovidgoyal.net/kitty/graphics-protocol/)
sono quelli upstream. La UI aggiunge celle allo stesso compositing di Kitty.
Il codice per il drag di schede e pannelli e i layout upstream restano il
punto d'ingresso per la gestione delle sessioni.

## Sorgenti consultati

- [Gestore delle schede](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/tabs.py),
  [barra delle schede](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/tab_bar.py)
  e [layout Splits](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/layout/splits.py).
- [Input del mouse](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/mouse.c),
  [geometria](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/state.c)
  e [loop di rendering](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/child-monitor.c).
- [Backend GLFW X11](https://github.com/kovidgoyal/kitty/tree/v0.51.0/glfw),
  [estensioni](https://sw.kovidgoyal.net/kitty/mapping/) e
  [sessioni](https://sw.kovidgoyal.net/kitty/sessions/).

## Componenti

- `patches/kitty.patch` aggiunge la prima riga alla barra delle schede
  orizzontale, riserva la regione della sidebar e instrada solo il mouse
  su queste aree. Il renderer carica la sidebar tramite la stessa API
  di celle usata dalle schede. Le schede, i divisori e le finestre
  interne usano le normali azioni e i normali layout di Kitty.
- `src/kitilix_ui.py` gestisce la barra, i menu, i metadati e gli eventi
  della sidebar. `src/kitilix_watch.py` la invalida sugli eventi di
  titolo, directory e comando. I metadati si leggono per le righe
  visibili. Il tooltip usa un timer a scatto singolo.
- `src/kitilix_session.py` salva i dati in JSON con sostituzione atomica
  e ricarica le strutture native di sessione. Gli ID serializzati
  ricollegano il layout Splits e le proporzioni alle nuove PTY.
- `build.sh` verifica le somme SHA-256, estrae Kitty in una directory
  versionata di `.build/` e compila i moduli C con le librerie di sistema.
  Copia gli shader già compilati, i simboli e `kitten` dalla release
  corrispondente. Gli stessi input, senza patch, costruiscono la
  variante upstream del benchmark.

## Rendering, anteprime e input

La UI e Kitty condividono il loop eventi e il contesto OpenGL. I
pulsanti operano sulla scheda attiva tramite le API interne del
`Boss`, con la sessione remota disattivata nella configurazione
predefinita. I pannelli conservano le loro `Screen` e PTY quando
cambiano disposizione. Tastiera, IME, clipboard e mouse delle
applicazioni nelle PTY seguono il percorso upstream.

All’apertura della sidebar Kitilix acquisisce le miniature delle
schede presenti nell’elenco visibile, comprese quelle inattive. Il
renderer dipinge i pannelli in un framebuffer OpenGL separato, riduce
l’immagine sulla GPU e legge soltanto i pixel della miniatura, lasciando
la scheda attiva invariata. Le anteprime sono istantanee. La rotellina
acquisisce le schede appena entrate nella lista e il comando
**Aggiorna miniature** ripete l’acquisizione. Il render ordinario
prosegue attraverso il loop upstream.

## Persistenza e portabilità

Il layout salvato riguarda una finestra e contiene dati per riaprire
shell locali. Le disposizioni sono serializzate con il formato
interno di Kitty 0.51.0 e l'involucro JSON ha una sua versione.
Prima di aggiornare Kitty, confrontare struttura dei layout, hook del
mouse e lifecycle del rendering e ripetere le prove di ripristino,
ridimensionamento, drag e immagini.

La build Kitilix compila il backend X11 e usa le coordinate del
framebuffer e le callback GLFW per l’input e il rendering su Xorg.

## Eseguibile Linux

`package.sh` assembla un ELF nativo con un archivio compresso
incorporato in una sezione di sola lettura. La build portatile usa
il set di istruzioni di base dell’architettura di destinazione.
Il launcher di Kitty usa un percorso relativo per il Python incluso
e un RPATH interno. EGL, Xorg e i driver arrivano dal sistema.

All’avvio l’ELF estrae i componenti in una directory con permessi
`0700` e lancia `run.sh` da lì. Il launcher attende Kitty e rimuove
la directory quando termina. Preferenze, layout e modifiche
personali usano lo stesso profilo XDG dell’avvio in sviluppo.
