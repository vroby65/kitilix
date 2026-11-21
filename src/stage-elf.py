# SPDX-License-Identifier: GPL-3.0-only
"""Prepare the portable Kitty runtime and its embedded Python interpreter."""
import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

source, app = (Path(arg).resolve() for arg in sys.argv[1:])
origin = Path(__file__).resolve().parents[1]


def ignore_kitty_sources(_folder, entries):
    return [
        name for name in entries
        if name == "__pycache__" or Path(name).suffix in (".c", ".h", ".go", ".pyi", ".pyc", ".mod", ".sum")
    ]


def ignore_python_sources(_folder, entries):
    return [
        name for name in entries
        if name in ("__pycache__", "sitecustomize.py", "dist-packages", "site-packages")
        or name.startswith("config-")
    ]


engine = app / "engine"
engine.mkdir()
shutil.copy2(source / "__main__.py", engine)
for name in ("kitty", "kittens"):
    shutil.copytree(source / name, engine / name, ignore=ignore_kitty_sources)
for name in ("fonts", "logo", "shaders", "shell-integration", "terminfo"):
    shutil.copytree(source / name, engine / name)

# Use the same upstream launcher, compiler flags and Python ABI as the Kitty
# extensions. Only the launcher needs to know the Python home inside the image.
build = source / "build"
output = app.parent / "launcher-main.o"
compiles = json.loads((build / "compile_commands.json").read_text())
compile_main = next(x["arguments"] for x in compiles if x["file"] == "kitty/launcher/main.c")
main_object = compile_main[-1]
subprocess.run(
    [*compile_main[:-1], str(output), '-DSET_PYTHON_HOME="python"'],
    cwd=source, check=True,
)
links = json.loads((build / "link_commands.json").read_text())
link_launcher = next(x["arguments"] for x in links if x["arguments"][-1] == "kitty/launcher/kitty")
launcher = engine / "kitty/launcher/kitty"
subprocess.run(
    [
        *(str(output) if arg == main_object else arg for arg in link_launcher[:-2]),
        "-Wl,--disable-new-dtags,-rpath,$ORIGIN/../../python/lib",
        "-o", str(launcher),
    ],
    cwd=source, check=True,
)

python_lib = engine / "python/lib"
python_lib.mkdir(parents=True)
stdlib = Path(sysconfig.get_path("stdlib"))
shutil.copytree(stdlib, python_lib / stdlib.name, ignore=ignore_python_sources)
soname = sysconfig.get_config_var("INSTSONAME")
library = Path(sysconfig.get_config_var("LIBDIR")) / soname
shutil.copy2(library.resolve(strict=True), python_lib / soname)
python_license = Path(f"/usr/share/doc/python{sysconfig.get_python_version()}/copyright")
shutil.copy2(python_license, app / "LICENSE.python")

config = app / "packaging"
config.mkdir()
for name in ("kitilix.conf", "kitilix.png"):
    shutil.copy2(origin / "packaging" / name, config)
shutil.copy2(origin / "packaging/LICENSE.symbols", app)
shutil.copy2(origin / "LICENSE", app)
shutil.copy2(origin / "run.sh", app / "run.sh")
