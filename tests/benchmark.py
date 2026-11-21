#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Compare identical Kitty versions on the current X11 display."""
import os
from pathlib import Path
import statistics
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic, sleep

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / ".build/engine-upstream/kitty/launcher/kitty"
RUNS = 5
IDLE_SECONDS = 2


def cpu_ticks(pid):
    stat = Path(f"/proc/{pid}/stat").read_text().rpartition(") ")[2].split()
    return int(stat[11]) + int(stat[12])


def pss_mib(pid):
    fields = Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines()
    return int(next(line.split()[1] for line in fields if line.startswith("Pss:"))) / 1024


def sample(label, launcher, base):
    config = base / label / "config"
    kitilix_config = config / "kitilix"
    kitilix_config.mkdir(parents=True, exist_ok=True)
    conf = kitilix_config / "kitty.conf"
    conf.write_text("shell /bin/bash --noprofile --norc\ncursor_blink_interval 0\nremember_window_size no\nlinux_display_server x11\n")
    env = {
        **os.environ,
        "XDG_CONFIG_HOME": str(config),
        "XDG_CACHE_HOME": str(base / label / "cache"),
        "KITTY_CONFIG_DIRECTORY": str(kitilix_config),
        "KITTY_CACHE_DIRECTORY": str(base / label / "cache" / "kitilix"),
    }
    started = monotonic()
    with (base / f"{label}.log").open("ab") as log:
        p = subprocess.Popen(launcher, env=env, cwd=ROOT, stdout=log, stderr=log)
    try:
        deadline = monotonic() + 8
        while True:
            visible = subprocess.run(("xdotool", "search", "--onlyvisible", "--pid", str(p.pid)),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if visible.returncode == 0:
                break
            if p.poll() is not None or monotonic() >= deadline:
                raise RuntimeError((base / f"{label}.log").read_text())
            sleep(0.008)
        ms = (monotonic() - started) * 1000
        sleep(0.30)
        ram = pss_mib(p.pid)
        ticks = cpu_ticks(p.pid)
        now = monotonic()
        sleep(IDLE_SECONDS)
        cpu = 100 * (cpu_ticks(p.pid) - ticks) / (os.sysconf("SC_CLK_TCK") * (monotonic() - now))
        return ms, ram, cpu
    finally:
        p.terminate()
        p.wait(timeout=5)


def main():
    for command in (("./build.sh",), ("./build.sh", "--upstream")):
        subprocess.run(command, cwd=ROOT, check=True)
    with TemporaryDirectory(prefix="bench-", dir=ROOT / ".build") as temp:
        base = Path(temp)
        config = base / "kitty/config/kitilix/kitty.conf"
        variants = {
            "kitty": (str(ORIGINAL), "--config", str(ROOT / "packaging/kitilix.conf"), "--config", str(config),
                      "-o", "enabled_layouts=splits,horizontal,vertical,grid,stack", "-o", "tab_bar_min_tabs=1",
                      "-o", "tab_bar_edge=top", "-o", "tab_bar_style=separator"),
            "kitilix": (str(ROOT / "run.sh"), "--fresh"),
        }
        samples = {label: [] for label in variants}
        for cycle in range(RUNS + 1):
            items = list(variants.items())
            for label, launcher in items[::1 if cycle % 2 == 0 else -1]:
                result = sample(label, launcher, base)
                if cycle:
                    samples[label].append(result)
        print(f"{RUNS} campioni per variante, un avvio iniziale escluso")
        print("Variante      Apertura (ms)    PSS (MiB)       CPU inattiva (%)")
        for label, values in samples.items():
            opening, memory, cpu = map(statistics.median, zip(*values))
            print(f"{label:<12}  {opening:>11.1f}      {memory:>9.1f}            {cpu:>7.2f}")


if __name__ == "__main__":
    main()
