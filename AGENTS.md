# Sviluppo di Kitilix

Kitilix è un fork della sola interfaccia di Kitty, con piattaforma di
riferimento Linux Mint MATE su X11. L'architettura e le fonti sono in
[ARCHITECTURE.md](ARCHITECTURE.md).
Leggi [agent/README.md](agent/README.md) prima di cambiare il progetto.

- Lavora nella directory del progetto e preserva i file di Kitty e Tilix
  installati sul sistema.
- Concentra le azioni, le preferenze e la persistenza nei moduli `src/kitilix_*.py`.
  Aggiorna `patches/kitty.patch` quando serve un punto d'integrazione upstream.
- Per una regressione, riproduci il problema nel percorso di uso reale.
  Verifica che la modifica mantenga il rendering, l'input e le PTY originali.
- Esegui `./build.sh`, `./tests/run-x11.sh` e `git diff --check`.
  Usa `./tests/run-x11.sh images` per il solo protocollo grafico.
