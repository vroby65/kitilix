# SPDX-License-Identifier: GPL-3.0-only
"""Build the native modules and launcher against the workstation's libraries."""
from functools import partial
import os
import sys

source, simde, profile = sys.argv[1:]
os.chdir(source)
sys.path.insert(0, source)

import setup

# The matching upstream release already supplies compiled shaders and kitten.
setup.build_static_kittens = lambda *args, **kwargs: None
if profile == "portable":
    setup.build = partial(setup.build, native_optimizations=False)
sys.argv = [
    "setup.py", "build", "--disable-link-time-optimization", "--ignore-compiler-warnings",
    "--extra-include-dirs", simde,
]
setup.main()
