# Maintenance guide

`run.sh` reads `packaging/kitilix.conf` followed by the personal file in
`XDG_CONFIG_HOME/kitilix` or `~/.config/kitilix`. It starts the Kitty launcher
built by `build.sh` and puts the matching `kitten` on child processes' PATH.
`package.sh` uses a portable engine build to create `dist/kitilix`.
`install.sh` copies the ELF and registers its desktop menu entry.

- Toolbar, selection, previews, menus, and preferences live in
  `src/kitilix_ui.py`. Refresh on resize, input, or Kitty state changes.
  Reserve timers for one-shot events.
- The patch adds native hooks to the release pinned in `build.sh`. Source
  and binary resources must come from the same release because internal
  structures and compiled resources may change.
- `src/kitilix_session.py` opens new local shells using the saved layout.
  Updates to layouts and preferences write a temporary file in the same
  directory, then replace the target atomically.
- Extracted upstream assets and builds stay in `.build/`. Tests isolate
  XDG data and use a local remote-control socket in a private directory.
  Remote control is disabled in the standard profile.

## Development checks

```bash
./build.sh
./tests/run-x11.sh
shellcheck build.sh run.sh package.sh install.sh tests/run-x11.sh
desktop-file-validate packaging/kitilix.desktop
git diff --check
```

For release testing, run `./package.sh` and pass
`KITILIX_TEST_LAUNCHER="$PWD/dist/kitilix"` to the test runner. It checks the
bundled Python and cleanup of the extracted runtime. Use an `XDG_DATA_HOME`
under `.build/` to test installation. For performance testing,
`python3 tests/benchmark.py` builds the upstream baseline and measures it
on the same X11 display as Kitilix. Document the display and distinguish
Xvfb results from hardware GPU results.

Update the README and architecture guide when usage, configuration, upstream
integration points, or validation commands change.
