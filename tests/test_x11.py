#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Drive real Kitilix windows with X11 input and inspect Kitty state and pixels."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from tempfile import mkdtemp
from time import monotonic, sleep

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
KITTEN = ROOT / ".build/engine/kitty/launcher/kitten"
LAUNCHER = Path(os.environ.get("KITILIX_TEST_LAUNCHER", ROOT / "run.sh")).resolve()


def command(*args, **kwargs):
    return subprocess.check_output(args, timeout=8, **kwargs)


def wait_for(check, description, timeout=8):
    end = monotonic() + timeout
    while monotonic() < end:
        if result := check():
            return result
        sleep(0.07)
    raise AssertionError(description)


class App:
    def __init__(self, base, *args, shell="/bin/bash --noprofile --norc"):
        self.base = base
        conf = base / "config/kitilix"
        conf.mkdir(parents=True, exist_ok=True)
        self.saved = conf / "layout.json"
        self.preferences = conf / "preferences.json"
        self.socket = base / "rc"
        (conf / "kitty.conf").write_text(
            f"shell {shell}\nallow_remote_control socket-only\nlisten_on unix:{self.socket}\n"
            "linux_display_server x11\nremember_window_size no\n"
            "cursor_blink_interval 0\nenable_audio_bell no\n"
        )
        self.log = base / "kitilix.log"
        env = {**os.environ, "XDG_CONFIG_HOME": str(base / "config"), "XDG_CACHE_HOME": str(base / "cache")}
        with self.log.open("ab") as log:
            self.process = subprocess.Popen((str(LAUNCHER), *args), cwd=base, env=env, stdout=log, stderr=log)
        self.engine_pid = None
        self.runtime = None

    def __enter__(self):
        try:
            socket = wait_for(self.find_socket, "Test socket did not appear")
            self.engine_pid = int(socket.name.rpartition("-")[2])
            self.address = f"unix:{socket}"
            self.wid = command("xdotool", "search", "--sync", "--onlyvisible", "--pid",
                               str(self.engine_pid)).decode().splitlines()[-1]
            if self.engine_pid != self.process.pid:
                proc = Path("/proc") / str(self.engine_pid)
                engine = (proc / "exe").readlink().parents[2]
                self.runtime = engine.parent
                assert self.runtime.stat().st_mode & 0o777 == 0o700, "Private temporary runtime"
                assert not (engine / "kitty/glfw-wayland.so").exists(), "X11-only runtime"
                python_lib = engine / "python/lib/libpython3.12.so.1.0"
                assert str(python_lib) in (proc / "maps").read_text(), "Bundled Python interpreter"
            self.x("windowfocus", self.wid)
            self.measure_cells()
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def find_socket(self):
        for candidate in self.base.glob(f"{self.socket.name}-*"):
            pid = candidate.name.rpartition("-")[2]
            if pid.isdecimal() and (Path("/proc") / pid).is_dir() and candidate.is_socket():
                return candidate
        return None

    def __exit__(self, exc, *_):
        if self.process.poll() is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=4)
        if exc is not None:
            print(self.log.read_text(), file=sys.stderr)
        log = self.log.read_text()
        if exc is None and self.runtime:
            assert not self.runtime.exists(), "Bundled runtime cleanup"
        if exc is None and "Traceback (most recent call last)" in log:
            raise AssertionError(log)

    def measure_cells(self):
        pane = wait_for(self.active_pane, "No active terminal")
        with self.shot("measure", pane["id"]) as img:
            self.cw = img.width // pane["columns"]
            self.ch = img.height // pane["lines"]

    def x(self, *args):
        return command("xdotool", *map(str, args))

    def remote(self, *args):
        return command(str(KITTEN), "@", "--to", self.address, *map(str, args)).decode()

    def tabs(self):
        return json.loads(self.remote("ls"))[0]["tabs"]

    def active_tab(self):
        return next((tab for tab in self.tabs() if tab["is_active"]), None)

    def active_pane(self):
        tab = self.active_tab()
        return next((pane for pane in tab["windows"] if pane["is_active"]), None) if tab else None

    def click(self, x, y, button=1):
        self.x("mousemove", "--window", self.wid, x, y, "click", button)

    def size(self):
        fields = dict(line.split("=", 1) for line in self.x("getwindowgeometry", "--shell", self.wid).decode().splitlines())
        return int(fields["WIDTH"]), int(fields["HEIGHT"])

    def toolbar(self, index):
        margin = (self.size()[0] % self.cw) // 2
        self.click(margin + (3 * index + 1) * self.cw + self.cw // 2, self.ch // 2)

    def shot(self, name, pane_id=None):
        path = self.base / f"{name}.png"
        match = (f"--match=id:{pane_id}",) if pane_id is not None else ()
        self.remote("screenshot", *match, path)
        return Image.open(path)

    def type(self, text):
        self.x("type", "--clearmodifiers", "--delay", 1, text)

    def key(self, *keys):
        self.x("key", "--clearmodifiers", *keys)

    def send(self, text, pane_id=None):
        pane_id = self.active_pane()["id"] if pane_id is None else pane_id
        self.remote("send-text", f"--match=id:{pane_id}", text)

    def contents(self, pane_id, history=False):
        return self.remote("get-text", f"--match=id:{pane_id}", "--extent=all" if history else "--extent=screen")

    def pane_count(self, count):
        return wait_for(lambda: (tab := self.active_tab()) and len(tab["windows"]) == count and tab,
                        f"Expected {count} panes")

    def layout(self, key, expected):
        self.toolbar(2)
        sleep(0.20)  # allow the Kitty ask process to enter its event loop
        self.key(key)
        return wait_for(lambda: (tab := self.active_tab()) and tab["layout"] == expected and tab, expected)

    def drag(self, x0, y0, x1, y1):
        self.x("mousemove", "--window", self.wid, x0, y0, "mousedown", 1)
        sleep(0.10)
        self.x("mousemove", "--window", self.wid, (x0 + x1) // 2, (y0 + y1) // 2)
        sleep(0.15)
        self.x("mousemove", "--window", self.wid, x1, y1)
        sleep(0.18)
        self.x("mouseup", 1)


def pane_pids(tab):
    return {pane["id"]: pane["pid"] for pane in tab["windows"]}


def neighbors(tab):
    return {pane["id"]: pane["neighbors"] for pane in tab["windows"]}


def check_gui(base):
    directory = base / "directory with spaces"
    directory.mkdir()
    with App(base, str(directory)) as app:
        first = app.active_pane()
        assert first["cwd"] == str(directory)
        app.x("mousemove", "--window", app.wid, app.cw * 7, app.ch // 2)
        sleep(0.6)
        with app.shot("toolbar") as img:
            assert len(img.crop((0, 0, app.cw * 31, app.ch)).getcolors(10_000)) > 10
            assert len(img.crop((app.cw * 32, 0, app.cw * 70, app.ch)).getcolors(10_000)) > 10

        app.toolbar(4)
        pair = app.pane_count(2)
        assert len({p["lines"] for p in pair["windows"]}) == 1
        before = [p["columns"] for p in pair["windows"]]
        width, height = app.size()
        app.drag(width // 2, height // 2, width // 2 + 100, height // 2)
        wait_for(lambda: [p["columns"] for p in app.active_tab()["windows"]] != before, "Drag the divider")
        print("OK directory startup, icons, vertical divider, and mouse resizing")

        app.toolbar(5)
        triple = app.pane_count(3)
        assert len({p["lines"] for p in triple["windows"]}) > 1
        app.toolbar(3)
        four = app.pane_count(4)
        pids = pane_pids(four)

        grid = app.layout("g", "grid")
        assert len(grid["windows"]) == 4
        assert max(p["lines"] for p in grid["windows"]) - min(p["lines"] for p in grid["windows"]) <= 1
        assert max(p["columns"] for p in grid["windows"]) - min(p["columns"] for p in grid["windows"]) <= 1
        horizontal = app.layout("a", "horizontal")
        assert len({p["lines"] for p in horizontal["windows"]}) == 1
        vertical = app.layout("v", "vertical")
        assert len({p["columns"] for p in vertical["windows"]}) == 1
        app.toolbar(7)
        wait_for(lambda: app.active_tab()["layout"] == "stack", "Maximize a pane")
        app.toolbar(7)
        wait_for(lambda: app.active_tab()["layout"] == "vertical", "Restore after zoom")
        splits = app.layout("s", "splits")
        assert pane_pids(splits) == pids
        baseline_dimensions = [(p["columns"], p["lines"]) for p in splits["windows"]]
        print("OK 2×2 grid, side-by-side and stacked layouts, zoom retains the PTYs")

        original = neighbors(splits)
        app.key("ctrl+shift+f")
        moved = wait_for(
            lambda: (t := app.active_tab()) and neighbors(t) != original and t,
            "Native pane movement",
        )
        assert pane_pids(moved) == pids
        # A second movement in the opposite direction returns the same topology.
        app.key("ctrl+shift+b")
        wait_for(lambda: neighbors(app.active_tab()) == original, "Reverse pane reordering")

        app.toolbar(1)
        wait_for(lambda: len(app.tabs()) == 2, "New tab")
        app.key("ctrl+alt+shift+t")
        wait_for(lambda: len(app.active_tab()["windows"]) == 2, "Tab title editor")
        app.key("ctrl+u")
        app.type("Work")
        app.key("Return")
        wait_for(lambda: app.active_tab()["title"] == "Work", "Rename a tab")
        second = app.active_pane()["id"]

        app.toolbar(0)
        wait_for(lambda: app.preferences.is_file() and json.loads(app.preferences.read_text())["sidebar"], "Sidebar visible")
        app.click(app.cw * 3, app.ch * 5)
        wait_for(lambda: app.active_tab()["id"] != 2, "Switch tabs from the sidebar")
        app.key("ctrl+shift+Right")
        wait_for(lambda: app.active_tab()["title"] == "Work", "Quick tab switch")
        app.toolbar(0)
        wait_for(lambda: not json.loads(app.preferences.read_text())["sidebar"], "Sidebar hidden")
        print("OK pane movement, tabs, renaming, and sidebar selection")

        columns = app.active_pane()["columns"]
        app.toolbar(9)
        wait_for(lambda: len(app.active_tab()["windows"]) == 2, "Preferences menu")
        app.key("a")
        wait_for(lambda: (t := app.active_tab()) and len(t["windows"]) == 1 and
                 t["windows"][0]["columns"] < columns, "Increase font size from Preferences")
        app.measure_cells()
        app.toolbar(9)
        wait_for(lambda: len(app.active_tab()["windows"]) == 2, "Menu for resetting the font size")
        app.key("r")
        wait_for(lambda: (t := app.active_tab()) and len(t["windows"]) == 1 and
                 t["windows"][0]["columns"] == columns, "Reset font size from Preferences")
        app.measure_cells()
        app.toolbar(9)
        wait_for(lambda: len(app.active_tab()["windows"]) == 2, "Layout restoration menu")
        app.key("l")
        wait_for(lambda: not json.loads(app.preferences.read_text())["restore"], "Disable restoration")
        app.toolbar(9)
        wait_for(lambda: len(app.active_tab()["windows"]) == 2, "Preferences reopened")
        app.key("l")
        wait_for(lambda: json.loads(app.preferences.read_text())["restore"], "Re-enable restoration")

        app.type("cd -- " + shlex.quote(str(base)))
        app.key("Return")
        wait_for(lambda: app.active_pane()["cwd"] == str(base), "Real keyboard input and working directory")
        app.type("printf 'PASTE-%s\\n' ")
        subprocess.run(("xclip", "-silent", "-selection", "clipboard"), input=b"VERIFIED", check=True, timeout=5, stderr=subprocess.DEVNULL)
        app.key("ctrl+shift+v", "Return")
        wait_for(lambda: "PASTE-VERIFIED" in app.contents(second), "Paste from the X11 clipboard")
        app.send("clear; printf '\\nCOPY-VERIFIED\\n'\r")
        wait_for(lambda: "COPY-VERIFIED" in app.contents(second).splitlines(), "Line ready to select")
        with app.shot("before-copy"):
            pass
        # With padding of 5 pt, the string begins in the second visible terminal row.
        app.drag(app.cw, app.ch * 4, app.cw * 18, app.ch * 4)
        selection = app.remote("get-text", "--extent=selection")
        assert "COPY-VERIFIED" in selection, repr(selection)
        app.key("ctrl+shift+c")
        assert b"COPY-VERIFIED" in command("xclip", "-o", "-selection", "clipboard")
        app.toolbar(8)
        saved = wait_for(lambda: app.saved.is_file() and json.loads(app.saved.read_text()), "Layout written")
        assert len(saved["tabs"]) == 2 and saved["tabs"][1]["name"] == "Work"
        app.toolbar(4)
        app.pane_count(2)
        app.toolbar(6)
        app.pane_count(1)
        assert len(app.tabs()) == 2
        app.toolbar(4)
        app.pane_count(2)
        with app.shot("close-tab-button-on-right") as img:
            assert len(img.crop((img.width - app.cw * 3, 0, img.width, app.ch)).getcolors(1000)) > 5
        app.click(app.size()[0] - app.cw * 3 // 2, app.ch // 2)
        wait_for(lambda: len(app.tabs()) == 1, "Close a tab with two panes")
        print("OK preferences, input, X11 clipboard, save, and close")

    with App(base) as app:
        tabs = app.tabs()
        assert len(tabs) == 2 and tabs[1]["title"] == "Work" and tabs[1]["is_active"]
        assert [(p["columns"], p["lines"]) for p in tabs[0]["windows"]] == baseline_dimensions
        assert app.active_pane()["cwd"] == str(base)
        assert not set(pane_pids(tabs[0]).values()) & set(pids.values())
        assert "COPY-VERIFIED" not in app.contents(app.active_pane()["id"], history=True)

    if shutil.which("fish"):
        with App(base, "--fresh", str(directory), shell="fish --no-config") as app:
            pane = app.active_pane()
            assert pane["cwd"] == str(directory)
            wait_for(lambda: "fish" in app.active_pane()["cmdline"][0], "Start fish")
            app.type("printf 'FISH-%s\\n' working")
            app.key("Return")
            wait_for(lambda: "FISH-working" in app.contents(pane["id"]).splitlines(), "Run a command in fish")
    print("OK restore layout, proportions, and working directory with new shells and --fresh")
    check_drag(base)
    check_config(base)


def check_drag(base):
    with App(base, "--fresh", str(base)) as app:
        app.remote("set-tab-title", "Alpha")
        app.toolbar(4)
        pair = app.pane_count(2)
        first_tab = pair["id"]
        source = pair["windows"][0]
        app.toolbar(1)
        wait_for(lambda: len(app.tabs()) == 2, "Second tab for drag and drop")
        app.remote("set-tab-title", "Beta")
        second_tab = app.active_tab()["id"]
        app.key("ctrl+shift+Left")
        wait_for(lambda: app.active_tab()["id"] == first_tab, "Source tab for drag and drop")

        tab_row = app.ch + app.ch // 2
        app.drag(app.cw * 6, app.ch * 2 + app.ch // 2, app.cw * 15, tab_row)
        wait_for(lambda: any(t["id"] == second_tab and pane_pids(t).get(source["id"]) == source["pid"]
                             for t in app.tabs()), "Transfer pane by dragging")
        app.drag(app.cw * 15, tab_row, app.cw // 2, tab_row)
        wait_for(lambda: [t["id"] for t in app.tabs()] == [second_tab, first_tab], "Reorder tabs by dragging")
    print("OK drag a pane between tabs and reorder tabs")



def check_config(base):
    with App(base, "--fresh") as app:
        conf = app.saved.with_name("kitty.conf")
        conf.write_text(conf.read_text() + "font_size 12.0\neditor /usr/bin/nano\n")
        columns = app.active_pane()["columns"]
        app.toolbar(9)
        wait_for(lambda: len(app.active_tab()["windows"]) == 2, "Configuration reload menu")
        app.key("n")
        wait_for(lambda: (t := app.active_tab()) and len(t["windows"]) == 1 and
                 t["windows"][0]["columns"] < columns, "Reload configuration")
        app.measure_cells()

        if Path("/usr/bin/nano").is_file():
            app.toolbar(9)
            wait_for(lambda: len(app.active_tab()["windows"]) == 2, "Configuration editor menu")
            app.key("c")

            def editor_window():
                for window in json.loads(app.remote("ls")):
                    for tab in window["tabs"]:
                        for pane in tab["windows"]:
                            if pane["cmdline"][0] == "/usr/bin/nano" and str(conf) in pane["cmdline"]:
                                return pane["id"]
                return None

            editor_id = wait_for(editor_window, "Open the actual user config in an editor")
            app.remote("send-text", f"--match=id:{editor_id}", "\x18")
            wait_for(lambda: not editor_window(), "Close the editor")
    print("OK reload configuration and open the editor when present")

def fixture(path, color):
    image = Image.new("RGB", (84, 48), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 9, 28, 25), fill=(255, 255, 255))
    image.save(path, quality=96)


def image_colors(img):
    red = green = 0
    for r, g, b in img.convert("RGB").getdata():
        red += r > 220 and g < 55 and b < 60
        green += g > 210 and r < 60 and b < 70
    return red, green


def check_images(base):
    png = base / "image.png"
    jpeg = base / "image.jpg"
    fixture(png, (244, 20, 25))
    fixture(jpeg, (16, 234, 31))
    with App(base, "--fresh", str(base)) as app:
        pane = app.active_pane()
        window_id = pane["id"]
        app.send(f"clear; kitten icat --align left {shlex.quote(png.name)}; kitten icat --align left {shlex.quote(jpeg.name)}; echo IMAGES-READY\r")
        wait_for(lambda: "IMAGES-READY" in app.contents(window_id).splitlines(), "Run kitten icat")

        def pixels(stage):
            with app.shot(stage, window_id) as img:
                return min(image_colors(img)) > 350

        wait_for(lambda: pixels("png-and-jpeg"), "PNG and JPEG pixels")
        app.x("windowsize", "--sync", app.wid, 1090, 730)
        wait_for(lambda: pixels("after-resize"), "Pixels after resizing the window")
        app.toolbar(4)
        app.pane_count(2)
        app.layout("g", "grid")
        wait_for(lambda: pixels("after-layout"), "Images survive splits and layout changes")
        app.remote("set-tab-title", "PNG and JPEG")
        app.toolbar(1)
        wait_for(lambda: len(app.tabs()) == 2, "New tab over the image tab")
        second = app.active_pane()["id"]
        app.remote("set-tab-title", "Second tab")
        app.send("clear; kitten icat --align left image.jpg; echo SECOND-TAB\r", second)
        wait_for(lambda: "SECOND-TAB" in app.contents(second).splitlines(), "Image in the second tab")
        active = app.active_tab()["id"]
        processes = [pane_pids(tab) for tab in app.tabs()]
        app.toolbar(0)
        wait_for(lambda: app.preferences.is_file(), "Image sidebar")

        def previews():
            with app.shot("tab-thumbnails") as img:
                first = img.crop((0, app.ch * 7, app.cw * 29, app.ch * 13))
                second = img.crop((0, app.ch * 17, app.cw * 29, app.ch * 23))
                return min(image_colors(first)) > 12 and image_colors(second)[1] > 12 and image_colors(second)[0] < 10

        wait_for(previews, "Two distinct thumbnails including the inactive tab")
        assert app.active_tab()["id"] == active
        assert [pane_pids(tab) for tab in app.tabs()] == processes
        app.send("kitten icat --clear; clear; kitten icat --align left image.png; echo UPDATED\r", second)
        wait_for(lambda: "UPDATED" in app.contents(second).splitlines(), "Content changed")
        app.click(app.cw * 6, app.ch * 3 + app.ch // 2)

        def refreshed():
            with app.shot("refreshed-thumbnail") as img:
                red, green = image_colors(img.crop((0, app.ch * 17, app.cw * 29, app.ch * 23)))
                return red > 12 and green < 10

        wait_for(refreshed, "Thumbnails refresh with new pixels")
        app.click(app.cw * 10, app.ch * 8)
        wait_for(lambda: app.active_tab()["id"] != active, "Select a tab from its thumbnail")
        app.toolbar(0)
        wait_for(lambda: pixels("after-tab-switch"), "Images survive tab changes")

        app.send("for i in {1..40}; do echo line-$i; done\r", window_id)
        wait_for(lambda: "line-40" in app.contents(window_id), "Fill scrollback")
        assert not pixels("before-scroll")
        app.x("mousemove", "--window", app.wid, app.cw * 18, app.ch * 8, "click", "--repeat", 14, 4)
        wait_for(lambda: pixels("after-scroll"), "Images return when scrolling up with the wheel")
        for count in (3, 4):
            app.toolbar(1)
            wait_for(lambda: len(app.tabs()) == count, f"Tab {count} for scrolling")
        last_tab = app.active_tab()["id"]
        app.key("ctrl+shift+Left")
        app.toolbar(0)
        wait_for(lambda: json.loads(app.preferences.read_text())["sidebar"], "Thumbnails for four tabs")
        app.click(app.cw * 10, app.ch * 8, button=5)
        app.click(app.cw * 10, app.ch * 28)
        wait_for(lambda: app.active_tab()["id"] == last_tab, "Select the fourth thumbnail after scrolling")
        print("OK PNG, JPEG, resize, splits, grid, scrolling, and refreshing real tab thumbnails")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, check in (("gui", check_gui), ("images", check_images)):
        if mode not in (name, "all"):
            continue
        base = Path(mkdtemp(prefix=f"{name}-", dir=ROOT / ".build"))
        try:
            check(base)
        finally:
            print(f"Logs and screenshots: {base}")
