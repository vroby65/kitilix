#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$root"
case "${1:-all}" in all|gui|images) ;; *) printf 'Uso: %s [all|gui|images]\n' "$0" >&2; exit 2 ;; esac
./build.sh
mkdir -p .build/tmp
export TMPDIR="$root/.build/tmp"
# The tests use their own X11 display and use a private socket only while running.
exec xvfb-run -a -s '-screen 0 1280x900x24 +extension GLX' python3 tests/test_x11.py "${1:-all}"
