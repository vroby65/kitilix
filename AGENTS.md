# Developing Kitilix

Kitilix adds a desktop interface to Kitty. The reference platform is
Linux Mint MATE on X11. For the architecture and upstream references,
see [ARCHITECTURE.md](ARCHITECTURE.md). Read [agent/README.md](agent/README.md)
before modifying the project.

- Keep project work in the checkout. Preserve the system Kitty and Tilix files.
- Keep actions, preferences, and persistence in `src/kitilix_*.py`. Update
  `patches/kitty.patch` when an upstream integration point is needed.
- Reproduce regressions through the normal entry point. Verify that changes
  preserve Kitty's rendering, input, and PTYs.
- Run `./build.sh`, `./tests/run-x11.sh`, and `git diff --check`.
  Use `./tests/run-x11.sh images` for graphics protocol testing.
