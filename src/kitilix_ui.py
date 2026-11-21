# SPDX-License-Identifier: GPL-3.0-only
"""Chrome drawn on Kitty screens alongside the upstream terminal surfaces."""
import math
import os
import weakref
from pathlib import Path

from .constants import defconf
from .fast_data_types import (
    DECAWM, GLFW_MOUSE_BUTTON_LEFT, GLFW_PRESS, GLFW_RELEASE, Screen, TOP_EDGE,
    add_timer, capture_kitilix_tab, get_boss, get_options, remove_timer, set_kitilix_sidebar_data,
    set_kitilix_sidebar_image, set_kitilix_sidebar_visible, truncate_point_for_length,
    viewport_for_window, wakeup_main_loop, wcswidth,
)
from .kitilix_session import LAYOUT, PREFERENCES, panes, preferences, save_layout, write_json
from .rgb import to_color

TOOLBAR = (
    ("\uf03e", "Show / hide tab thumbnails", "sidebar"),
    ("\uf24d", "New tab", "tab"),
    ("\uf00a", "Choose pane layout", "layout"),
    ("\uf067", "New terminal", "new"),
    ("\uf0db", "Vertical divider · side-by-side panes", "vertical"),
    ("⊟", "Horizontal divider · stacked panes", "horizontal"),
    ("−", "Close pane", "close"),
    ("\uf2d0", "Maximize / restore pane", "zoom"),
    ("\uf0c7", "Save layout", "save"),
    ("⚙︎", "Preferences", "preferences"),
)
CLOSE_TAB = ("×", "Close tab", "close-tab")

BASE = 0x222B35
SIDE = 0x1D2731
TEXT = 0xE5EEF4
MUTED = 0xAAC0CA
TEAL = 0x77DFD1
HIGHLIGHT = 0x33525A


def cell_text(text, width):
    text = "".join(c if c.isprintable() or 0xE000 <= ord(c) <= 0xF8FF else " " for c in str(text))
    end = truncate_point_for_length(text, width)
    if end < len(text) and width > 1:
        return text[:truncate_point_for_length(text, width - 1)] + "…"
    return text[:end]


def draw(screen, row, column, text, fg=TEXT, bg=BASE, bold=False):
    if column >= screen.columns:
        return
    cursor = screen.cursor
    cursor.x, cursor.y = column, row
    cursor.fg, cursor.bg = (fg << 8) | 2, (bg << 8) | 2
    cursor.bold, cursor.italic = bold, False
    screen.draw(cell_text(text, screen.columns - column))


def install_watchers():
    from .window import global_watchers

    global_watchers.set_extra(str(Path(__file__).with_name("kitilix_watch.py")))


class Chrome:
    def __init__(self, manager):
        self.manager = weakref.proxy(manager)
        self.os_window_id = manager.os_window_id
        self.hover = self.tooltip_timer = self.pressed = None
        self.tip = self.status = ""
        self.status_timer = None
        self.scroll_offset = 0
        self.sidebar = None
        self.sidebar_top = self.cell_height = 0
        self.sidebar_rows = {}
        self.sidebar_signature = None
        self.sidebar_state = None
        self.sidebar_dirty = True
        self.previews = {}
        self.shown_previews = ()
        self.preview_timer = None
        self.preview_height = 0
        self.show_sidebar = preferences()["sidebar"]
        set_kitilix_sidebar_visible(self.os_window_id, self.show_sidebar)

    def destroy(self):
        for timer in (self.tooltip_timer, self.status_timer, self.preview_timer):
            if timer is not None:
                remove_timer(timer)

    def refresh(self):
        self.manager.mark_tab_bar_dirty()
        wakeup_main_loop()

    def invalidate_sidebar(self):
        self.sidebar_dirty = True
        self.refresh()

    def report(self, text):
        if self.status_timer is not None:
            remove_timer(self.status_timer)
        self.status = text
        self.status_timer = add_timer(self.clear_status, 3.0, False)
        self.refresh()

    def clear_status(self, _timer):
        self.status_timer = None
        self.status = ""
        self.refresh()

    def set_hover(self, button):
        if button == self.hover:
            return
        if self.tooltip_timer is not None:
            remove_timer(self.tooltip_timer)
            self.tooltip_timer = None
        self.hover = button
        self.tip = ""
        if button is not None:
            self.tooltip_timer = add_timer(self.show_tooltip, 0.40, False)
        self.refresh()

    def show_tooltip(self, _timer):
        self.tooltip_timer = None
        if self.hover is not None:
            self.tip = (*TOOLBAR, CLOSE_TAB)[self.hover][1]
            self.refresh()

    def pointer_left(self):
        self.pressed = None
        self.set_hover(None)

    def layout_sidebar(self):
        central, _, _, _, cell_width, cell_height = viewport_for_window(self.os_window_id)
        lines = central.height // cell_height
        columns = central.left // cell_width
        if not columns or lines < 2:
            if self.sidebar is not None:
                set_kitilix_sidebar_data(self.os_window_id, None, 0, 0, 0, 0)
                self.sidebar = None
                self.previews.clear()
                self.shown_previews = ()
                self.sidebar_rows.clear()
            return
        geometry = (columns, lines, cell_width, cell_height, central.top)
        if geometry != self.sidebar_state or self.sidebar is None:
            self.sidebar_state = geometry
            s = self.sidebar = Screen(None, lines, columns, 0, cell_width, cell_height)
            s.reset_mode(DECAWM)
            s.color_profile.default_bg = to_color("#1d2731")
            s.color_profile.default_fg = to_color("#e5eef4")
            self.sidebar_top, self.cell_height = central.top, cell_height
            self.previews.clear()
            self.shown_previews = ()
            self.sidebar_dirty = True
            set_kitilix_sidebar_data(self.os_window_id, s, 0, central.top, central.left, central.top + lines * cell_height)

    def button_width(self):
        return 3 if self.manager.tab_bar.screen.columns >= 3 * (len(TOOLBAR) + 1) + 1 else 2

    def update(self):
        bar = self.manager.tab_bar
        if bar.laid_out_once and bar.tab_bar_edge == TOP_EDGE:
            self.draw_toolbar(bar.screen)
        if self.sidebar is not None:
            self.update_sidebar()

    def draw_toolbar(self, screen):
        width = self.button_width()
        close_column = screen.columns - width
        draw(screen, 0, 0, " " * screen.columns)
        for index, (icon, _, action) in enumerate(TOOLBAR):
            if (index + 1) * width > close_column - 1:
                break
            enabled = action == "sidebar" and self.show_sidebar
            draw(screen, 0, index * width, (" " if width == 3 else "") + icon + " ",
                 TEAL if enabled or index == self.hover else TEXT,
                 HIGHLIGHT if enabled or index == self.hover else BASE)
        text_column = width * len(TOOLBAR) + 2
        if (text := self.status or self.tip) and text_column < close_column - 1:
            draw(screen, 0, text_column, cell_text(text, close_column - 1 - text_column), TEAL, HIGHLIGHT)
        if close_column > 0:
            draw(screen, 0, close_column - 1, "│", MUTED)
        draw(screen, 0, close_column, (" " if width == 3 else "") + CLOSE_TAB[0] + " ",
             TEXT if self.hover == len(TOOLBAR) else 0xF3ADB1, 0x843E48 if self.hover == len(TOOLBAR) else BASE)
        screen.cursor.fg = screen.cursor.bg = 0
        screen.cursor.y = screen.lines - 1

    def update_sidebar(self):
        s = self.sidebar
        active = self.manager.active_tab
        cards = [(tab, panes(tab)) for tab in self.manager]
        signature = (
            active.id if active else 0,
            tuple((tab.id, tab.name, len(windows), tab.active_window_for_cwd.id if tab.active_window_for_cwd else 0,
                   tuple(w.title for w in windows)) for tab, windows in cards),
        )
        if signature == self.sidebar_signature and not self.sidebar_dirty:
            return
        self.sidebar_signature = signature
        self.sidebar_dirty = False

        cols, lines, cell_width, cell_height, _ = self.sidebar_state
        preview_rows = min(6, max(1, lines - 6))
        self.preview_height = preview_rows * cell_height
        card_height = preview_rows + 4
        capacity = max(0, (lines - 2) // card_height)
        self.scroll_offset = min(self.scroll_offset, max(0, len(cards) - capacity))
        card_ids = {tab.id for tab, _ in cards}
        self.previews = {key: value for key, value in self.previews.items() if key in card_ids}
        self.sidebar_rows.clear()
        home = str(Path.home())
        for row in range(lines):
            draw(s, row, 0, " " * cols, TEXT, SIDE)
        draw(s, 0, 1, f"Tabs  {len(cards)}", TEAL, SIDE, True)
        draw(s, 1, 1, "↻  Refresh thumbnails", MUTED, SIDE)

        images = []
        visible = cards[self.scroll_offset:self.scroll_offset + capacity]
        for index, (tab, windows) in enumerate(visible):
            row = 2 + index * card_height
            focused = tab is active
            bg = HIGHLIGHT if focused else BASE
            for line in range(row, row + card_height - 1):
                draw(s, line, 0, " " * cols, TEXT, bg)
                self.sidebar_rows[line] = tab.id
            window = tab.active_window_for_cwd
            title = tab.name or (window.title if window else tab.effective_title)
            if not tab.name and title.startswith(("/", "~/")):
                title = Path(title).name or title
            draw(s, row, 1, f"{self.scroll_offset + index + 1}  {title}", TEXT, bg, True)
            label = "1 pane" if len(windows) == 1 else f"{len(windows)} panes"
            if window:
                process = os.path.basename(window.get_exe_of_child())
                if process:
                    label += f" · {process}"
                cwd = window.get_cwd_of_child() or window.child.cwd
                if cwd == home or cwd.startswith(home + "/"):
                    cwd = "~" + cwd[len(home):]
                while wcswidth(cwd) > cols - 2 and "/" in cwd:
                    cwd = "…" + cwd.partition("/")[2]
                draw(s, row + 2, 1, cwd, MUTED, bg)
            draw(s, row + 1, 1, label, TEAL if focused else MUTED, bg)
            if preview := self.previews.get(tab.id):
                images.append((row + 3, preview))
            elif tab.id not in self.previews:
                draw(s, row + 3, 1, "Capturing…", MUTED, bg)
            else:
                draw(s, row + 3, 1, "Preview unavailable", MUTED, bg)

        if tuple(images) != self.shown_previews:
            self.shown_previews = tuple(images)
            set_kitilix_sidebar_image(self.os_window_id, 0, b"", 0, 0, 0, 0, 0, 0)
            if active is not None and (window := active.active_window) is not None:
                for row, (pixels, width, height) in images:
                    columns = min(cols - 2, max(1, round(width / cell_width)))
                    rows = min(preview_rows, max(1, round(height / cell_height)))
                    set_kitilix_sidebar_image(self.os_window_id, window.id, pixels, width, height,
                                              row, (cols - columns) // 2, columns, rows)
        if self.preview_timer is None and any(tab.id not in self.previews for tab, _ in visible):
            self.preview_timer = add_timer(self.capture_visible_tabs, 0.06, False)

    def capture_visible_tabs(self, _timer):
        self.preview_timer = None
        if self.sidebar is None:
            return
        cols, _, cell_width, _, _ = self.sidebar_state
        for tab_id in dict.fromkeys(self.sidebar_rows.values()):
            if tab_id in self.previews:
                continue
            preview = capture_kitilix_tab(self.os_window_id, tab_id, (cols - 2) * cell_width, self.preview_height)
            if preview:
                pixels, width, height = preview
                stride = width * 4
                pixels = b"".join(pixels[y:y + stride] for y in range(len(pixels) - stride, -1, -stride))
                preview = pixels, width, height
            self.previews[tab_id] = preview
        self.invalidate_sidebar()

    def scroll(self, delta):
        self.scroll_offset = max(0, self.scroll_offset + (-1 if delta > 0 else 1))
        self.invalidate_sidebar()

    def mouse(self, x, y, button, action, in_sidebar):
        if in_sidebar:
            self.set_hover(None)
            if self.sidebar is None:
                return
            row = math.floor((y - self.sidebar_top) / self.cell_height)
            target = ("preview", 0) if row == 1 else ("focus-tab", self.sidebar_rows.get(row, 0))
        else:
            bar = self.manager.tab_bar
            if not bar.contains(x, y) or y >= bar.window_geometry.top + bar.cell_height:
                self.pointer_left()
                return
            column = (int(x) - bar.window_geometry.left) // bar.cell_width
            width = self.button_width()
            close_column = bar.screen.columns - width
            index = column // width
            if column >= close_column:
                self.set_hover(len(TOOLBAR))
                target = CLOSE_TAB[2], 0
            elif index < len(TOOLBAR) and (index + 1) * width <= close_column - 1:
                self.set_hover(index)
                target = TOOLBAR[index][2], 0
            else:
                self.set_hover(None)
                target = None
        if button == GLFW_MOUSE_BUTTON_LEFT:
            if action == GLFW_PRESS:
                self.pressed = target
            elif action == GLFW_RELEASE:
                pressed, self.pressed = self.pressed, None
                if target is not None and pressed == target:
                    self.activate(*target)

    def activate(self, action, tab_id=0):
        boss = get_boss()
        tab = self.manager.active_tab
        if tab is None:
            return
        if action in ("new", "vertical", "horizontal"):
            tab.goto_layout("splits")
            location = {"new": "split", "vertical": "vsplit", "horizontal": "hsplit"}[action]
            boss.new_window_with_cwd(f"!{location}")
        elif action == "tab":
            boss.new_tab_with_cwd()
        elif action == "close":
            boss.close_window_with_confirmation(ignore_shell=True)
        elif action == "close-tab":
            boss.close_tab(tab)
        elif action == "zoom":
            if tab.current_layout.name == "stack" and not tab._last_used_layout:
                tab.goto_layout("splits")
            else:
                tab.toggle_layout("stack")
        elif action == "sidebar":
            self.show_sidebar = not self.show_sidebar
            set_kitilix_sidebar_visible(self.os_window_id, self.show_sidebar)
            self.manager.resize()
            try:
                write_json(PREFERENCES, {**preferences(), "sidebar": self.show_sidebar})
            except OSError as error:
                boss.show_error("Kitilix preferences", str(error))
        elif action == "focus-tab" and (target := self.manager.tab_for_id(tab_id)):
            self.manager.set_active_tab(target)
        elif action == "preview":
            self.previews.clear()
            self.invalidate_sidebar()
        elif action == "layout":
            layouts = {"s": "splits", "a": "horizontal", "v": "vertical", "g": "grid", "u": "stack"}
            boss.choose("Pane layout",
                        lambda key: tab.goto_layout(layouts[key]) if key in layouts else None,
                        "s:Splits", "a:Arrange side by side", "v:Stack vertically", "g:Grid", "u:Use active pane only")
        elif action == "save":
            try:
                save_layout(self.manager)
                self.report(f"Layout saved · {LAYOUT.name}")
            except OSError as error:
                boss.show_error("Save layout", str(error))
        elif action == "preferences":
            self.open_preferences()

    def open_preferences(self):
        boss = get_boss()
        prefs = preferences()
        restore = "on" if prefs["restore"] else "off"

        def selected(key):
            if key in ("a", "d", "r"):
                delta = {"a": ("+", 1), "d": ("-", 1), "r": (None, 0)}
                boss.change_font_size(False, *delta[key])
            elif key == "l":
                try:
                    write_json(PREFERENCES, {**prefs, "restore": not prefs["restore"]})
                    self.report("Restore on startup " + ("disabled" if prefs["restore"] else "enabled"))
                except OSError as error:
                    boss.show_error("Kitilix preferences", str(error))
            elif key == "c":
                boss.edit_file(defconf)
            elif key == "n":
                boss.load_config_file()

        boss.choose("Kitilix preferences", selected,
                    "a:Increase font size", "d:Decrease font size", "r:Reset font size",
                    f"l:Load layout on startup ({restore})", "c:Edit configuration", "n:Reload configuration")
