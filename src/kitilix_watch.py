# SPDX-License-Identifier: GPL-3.0-only
"""Refresh session metadata in response to Kitty shell and title events."""


def on_title_change(boss, window, data):
    if manager := boss.os_window_map.get(window.os_window_id):
        if manager.kitilix.sidebar is not None:
            manager.kitilix.invalidate_sidebar()


on_cwd_change = on_title_change
on_cmd_startstop = on_title_change
