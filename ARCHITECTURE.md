# Kitilix architecture

Kitilix is based on [Kitty 0.51.0](https://github.com/kovidgoyal/kitty/tree/v0.51.0).
The distribution's Kitty installation and the user's Kitty profile are
independent of Kitilix.

## Approaches considered

| Approach | Integration | Scope |
| --- | --- | --- |
| GTK4 controller with stock Kitty | Remote control handles windows, tabs, layouts, and focus through separate GTK and Kitty surfaces. | Uses stock Kitty with two windows. |
| Minimal fork of the Kitty UI | A single GLFW window contains the terminals, tabs, toolbar, and sidebar. | A patch for UI geometry, input, and rendering, plus Python modules. |

Kitty creates its windows through its bundled GLFW. The remote-control
protocol exchanges commands and metadata. Embedding the Kitty window in
GTK would require a separate integration surface. On Xorg, reparenting
would depend on the window manager, focus, and pixel handling.
[Kitty remote control](https://sw.kovidgoyal.net/kitty/remote-control/)

Kitilix uses the minimal fork. It keeps Kitty's window, PTYs, terminal
grids, shaders, and graphics protocol. The interface draws extra cells
through Kitty's compositor. Tab and pane drag operations and layouts use
Kitty's existing session-management operations.
[Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/)

## Upstream sources

- [Tab manager](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/tabs.py),
  [tab bar](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/tab_bar.py),
  and [Splits layout](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/layout/splits.py).
- [Mouse input](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/mouse.c),
  [window geometry](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/state.c),
  and [render loop](https://github.com/kovidgoyal/kitty/blob/v0.51.0/kitty/child-monitor.c).
- [GLFW X11 backend](https://github.com/kovidgoyal/kitty/tree/v0.51.0/glfw),
  [extensions](https://sw.kovidgoyal.net/kitty/mapping/), and
  [sessions](https://sw.kovidgoyal.net/kitty/sessions/).

## Components

- `patches/kitty.patch` adds the toolbar row to the horizontal tab bar,
  reserves the sidebar region, and routes mouse events for those regions.
  Tab and pane behavior uses Kitty's actions and layouts. The renderer
  uses the tab bar's cell API to draw the sidebar.
- `src/kitilix_ui.py` handles the toolbar, menus, metadata, and sidebar
  events. `src/kitilix_watch.py` invalidates sidebar metadata when the
  title, directory, or command changes. The sidebar reads data for visible
  rows. Tooltips use one-shot timers.
- `src/kitilix_session.py` stores layout data in JSON through atomic
  replacement and loads it into Kitty's native session structures. Saved
  IDs associate Splits layouts and proportions with new PTYs.
- `build.sh` checks SHA-256 digests, extracts Kitty into a versioned
  directory in `.build/`, and compiles the C modules against system
  libraries. It copies precompiled shaders, symbols, and `kitten` from
  the matching upstream release. The benchmark builds its upstream
  baseline from the same inputs with the upstream sources intact.

## Rendering, thumbnails, and input

Kitilix and Kitty share the event loop and OpenGL context. Buttons act on
the active tab through Kitty's internal `Boss` APIs. Remote control is
disabled in the default profile. Changing layouts keeps each pane's
`Screen` and PTY. Terminal input, IME, clipboard, and mouse
handling use Kitty's input path.

Opening the sidebar captures thumbnails for the tabs visible in the list,
including inactive tabs. The renderer draws each tab into a separate OpenGL
framebuffer, scales it on the GPU, and reads the thumbnail pixels. The
active tab keeps focus. Scrolling captures tabs when they enter the list,
and **Refresh thumbnails** takes new snapshots. Normal rendering continues
through Kitty's event loop.

## Persistence and portability

A saved layout belongs to a single window and opens new local shells.
The versioned JSON wraps Kitty 0.51.0's internal layout representation.
Before upgrading Kitty, compare its layout structures, mouse hooks, and
rendering lifecycle. Test restoration, resizing, drag operations, and
graphics after updating.

The Kitilix build compiles the X11 backend and uses the framebuffer
coordinates and GLFW callbacks for input and rendering on Xorg.

## Linux executable

`package.sh` builds a native ELF with a compressed archive in a read-only
section. The portable build targets the architecture's baseline instruction
set. Kitty's launcher uses a relative path and an internal RPATH to load the
bundled Python. EGL, Xorg, and graphics drivers come from the host system.

At startup, the ELF extracts its runtime into a directory with `0700`
permissions and runs the bundled `run.sh`. The launcher waits for Kitty
and removes that directory on exit. Preferences, layouts, and personal
overrides use the same XDG profile as the development launcher.
