# SPDX-License-Identifier: GPL-3.0-only
"""Kitilix preferences and geometry, stored independently of shell commands."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .constants import config_dir, unserialize_launch_flag

PREFERENCES = Path(config_dir) / "preferences.json"
LAYOUT = Path(config_dir) / "layout.json"
LAYOUTS = ("splits", "horizontal", "vertical", "grid", "stack")


def preferences():
    prefs = {"sidebar": False, "restore": True}
    try:
        saved = json.loads(PREFERENCES.read_text())
        for key in prefs:
            if isinstance(saved.get(key), bool):
                prefs[key] = saved[key]
    except (OSError, ValueError, AttributeError):
        pass
    return prefs


def write_json(path, data):
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
        staged = Path(output.name)
        try:
            json.dump(data, output, ensure_ascii=True, indent=2)
            output.write("\n")
            output.close()
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)


def panes(tab):
    # Kitty groups transient overlays with their underlying terminal.
    return [group.windows[0] for group in tab.windows.groups if group.windows]


def save_layout(manager):
    tabs = []
    for tab in manager:
        windows = panes(tab)
        if not windows:
            continue
        active = tab.windows.active_group
        tabs.append({
            "name": tab.name,
            "layout": tab.current_layout.full_name,
            "state": tab.serialize_layout_state_for_session(),
            "active": active.windows[0].id if active else windows[0].id,
            "panes": [{"id": window.id, "cwd": window.cwd_for_serialization} for window in windows],
        })
    if tabs:
        active_index = next((idx for idx, tab in enumerate(manager) if tab is manager.active_tab), 0)
        write_json(LAYOUT, {"version": 1, "active": active_index, "tabs": tabs})


def restore_layout(opts):
    if os.environ.get("KITILIX_RESTORE") != "1" or not preferences()["restore"] or not LAYOUT.is_file():
        return ()
    from .session import Session

    data = json.loads(LAYOUT.read_text())
    if data["version"] != 1 or not data["tabs"]:
        raise ValueError("Unsupported Kitilix layout format")

    session = Session()
    for saved in data["tabs"]:
        if saved["layout"] not in LAYOUTS or not saved["panes"] or not isinstance(saved["state"], dict):
            raise ValueError("Invalid tab in Kitilix layout")
        session.add_tab(opts, saved["name"])
        session.set_layout(saved["layout"])
        tab = session.tabs[-1]
        tab.layout_state = saved["state"]
        for index, window in enumerate(saved["panes"]):
            pane_id = int(window["id"])
            cwd = Path(window["cwd"])
            if not cwd.is_absolute() or not cwd.is_dir():
                cwd = Path.home()
            session.add_window([
                unserialize_launch_flag + json.dumps({"id": pane_id}),
                f"--cwd={cwd}",
            ])
            if pane_id == saved["active"]:
                tab.active_window_idx = index
    session.active_tab_idx = min(max(0, int(data["active"])), len(session.tabs) - 1)
    session.num_of_windows_in_definition = sum(len(tab.windows) for tab in session.tabs)
    return (session,)
