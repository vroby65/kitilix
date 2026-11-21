# Kitilix

[Italiano](https://github.com/vroby65/kitilix/tree/italiano) · [Releases](https://github.com/vroby65/kitilix/releases/latest)

Kitilix is a Linux terminal with a toolbar, tabs, and panes in a single Kitty
window. It uses Kitty 0.51.0 for OpenGL rendering, PTYs, input, and the terminal
graphics protocol.

## Linux executable

Download [kitilix-linux-x86_64-en](https://github.com/vroby65/kitilix/releases/latest/download/kitilix-linux-x86_64-en)
for Linux x86-64 and Xorg. The release provides a single ELF executable.

```bash
chmod +x kitilix-linux-x86_64-en
./kitilix-linux-x86_64-en
```

The file bundles Kitty, `kitten`, Python, fonts, and shaders. At startup it
extracts its runtime into a private directory under `TMPDIR`, which defaults
to `/tmp`. The launcher removes that directory on exit. It uses Bash, GNU tar,
and the host graphics libraries. The build was tested on Linux Mint 22.3 with
glibc 2.39.

Personal settings live in `~/.config/kitilix/`, or under `XDG_CONFIG_HOME`
when set. The profile contains `kitty.conf`, `preferences.json`, and
`layout.json` once you save a layout.

- `./package.sh` builds `dist/kitilix` from source.
- `./install.sh` copies the ELF to
  `${XDG_DATA_HOME:-~/.local/share}/kitilix/kitilix` and installs a desktop
  menu entry with its icon.

## Run from source

```bash
git clone https://github.com/vroby65/kitilix.git
cd kitilix
./run.sh
```

The first run downloads the verified Kitty and SIMDe archives and builds the
engine in `.build/`. Later runs reuse that build. Kitilix has its own profile
and can run alongside your distribution's Kitty.

Both the release executable and `run.sh` accept the same arguments.

- `--fresh` opens a terminal in your home directory without loading a saved layout.
- A directory argument opens a terminal there, even when you have a saved layout.

### Dependencies

Linux Mint 22.3 on x86-64 and X11 is the tested platform. Building requires
Python 3.12 with headers, GCC, pkg-config, standard Debian tools, and the
following development packages. The names apply to Debian, Ubuntu, and Mint.

```text
build-essential curl xz-utils patch pkg-config python3-dev
libharfbuzz-dev libfontconfig-dev libfreetype-dev libpng-dev liblcms2-dev
libxxhash-dev libssl-dev zlib1g-dev libcairo2-dev libpixman-1-dev
libdbus-1-dev libx11-xcb-dev libxcursor-dev libxrandr-dev libxi-dev
libxinerama-dev libxkbcommon-x11-dev libgl1-mesa-dev
```

Running Kitilix requires an Xorg session with working OpenGL. The build uses
shaders, the symbols font, and `kitten` from the same official Kitty release.
Manage system packages through your distribution.

## Interface

Hover over an icon to see what it does. The first three toolbar buttons are
**Thumbnails**, **New tab**, and **Layouts**. The remaining buttons open a
terminal, split a pane in either direction, close a pane, maximize or restore
a pane, save the layout, and open preferences. The **× at the far right**
closes the active tab and its panes.

- **Splits and layouts.** Drag the divider between two panes to resize them.
  The layout menu offers Splits, Side by side, Stacked vertically, Grid, and
  Active pane only. Four panes form a 2×2 grid. Changing the layout keeps the
  sessions running.
- **Tabs and panes.** Click a tab to activate it, double-click to rename it,
  or drag it on the tab bar to reorder it. Drag a pane's title bar onto
  another pane or onto a target tab to move it. Use `Ctrl+Shift+F` and
  `Ctrl+Shift+B` to move panes with the keyboard. Use `Ctrl+Shift+Left`
  and `Ctrl+Shift+Right` to switch tabs.
- **Sidebar.** Each tab has a clickable thumbnail showing all its panes,
  including inactive tabs. The sidebar also shows the title, process,
  and working directory when Kitty can detect them. Scroll for more tabs and
  choose **Refresh thumbnails** to capture new snapshots.
- **Preferences.** Adjust font size for the current window, toggle layout
  restoration, and edit or reload `kitty.conf`. Set `font_size` in that
  file to keep a font size across launches.
- **Input and shells.** `Ctrl+Shift+C` copies a selection and
  `Ctrl+Shift+V` pastes. Kitty uses your login shell. You can set
  `shell fish` or `shell /bin/bash` in `kitty.conf`.

## Configuration and layout restoration

Kitilix reads your `kitty.conf` after the bundled defaults. **Save layout**
records the current window's tabs, names, pane layouts and proportions, active
pane, and detected local working directories. The next launch opens **new
shells**. Running processes, shell variables, scrollback, and images end with
their sessions. Missing working directories fall back to your home directory.

## Graphics and testing

Inside Kitilix, run `kitten icat image.png` or `kitten icat image.jpg`.
Use `kitten icat --align left image.png` to keep images visible when you
narrow a pane. Images follow Kitty's positioning and scrollback rules.
Images anchored at columns beyond the current pane width can be clipped.

```bash
./tests/run-x11.sh
./tests/run-x11.sh images
KITILIX_TEST_LAUNCHER="$PWD/dist/kitilix" ./tests/run-x11.sh
XDG_DATA_HOME="$PWD/.build/install-test" ./install.sh
TMPDIR="$PWD/.build/tmp" xvfb-run -a python3 tests/benchmark.py
```

The tests require `xvfb`, `xauth`, `xdotool`, `xclip`, and
`python3-pil`. They build Kitilix and use real X11 input and screenshots on
an isolated display. The `images` test measures PNG and JPEG pixels after
resize, splits, tab changes, and scrolling. It also checks thumbnails for
active and inactive tabs. The full suite tests `fish` when available. Test
outputs stay in `.build/`.

The benchmark compares Kitty 0.51.0 against Kitilix launched via `run.sh`.
Both engines use the same compiler flags. It measures the median time until
X11 maps the first window, the main process's proportional set size (PSS),
and idle CPU usage. Across five measured Xvfb launches on Mint 22.3, the
medians were 419 ms and 98.7 MiB for Kitty and 491 ms and 98.4 MiB for
Kitilix. The two-second idle samples recorded zero CPU ticks. To repeat the
benchmark on your current X11 display, run `python3 tests/benchmark.py`.

## License

Kitilix code is GPL-3.0-only. The patches apply to the GPLv3
[Kitty 0.51.0 source release](https://github.com/kovidgoyal/kitty/releases/tag/v0.51.0).
Symbols Nerd Font Mono retains its [MIT license](packaging/LICENSE.symbols).
The executable includes Python's license notices. The repository provides
the changes and scripts needed to rebuild the binaries.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the scope of the fork and
[AGENTS.md](AGENTS.md) for the development workflow.
