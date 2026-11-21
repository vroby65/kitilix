#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

usage() {
    printf 'Uso: %s [--fresh] [--] [CARTELLA]\n' "${KITILIX_PROGRAM:-${0##*/}}"
}

export KITILIX_RESTORE=1
case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    --fresh) KITILIX_RESTORE=0; shift ;;
esac
if [[ ${1:-} == -- ]]; then shift; fi
if (( $# > 1 )); then usage >&2; exit 2; fi
if (( $# )); then
    directory=$(cd -- "$1" && pwd -P)
    KITILIX_RESTORE=0
else
    directory=$HOME
fi

if [[ -x $root/engine/kitty/launcher/kitty ]]; then
    engine="$root/engine"
else
    "$root/build.sh" >&2
    engine=$(readlink -f "$root/.build/engine")
fi

export KITTY_CONFIG_DIRECTORY="${XDG_CONFIG_HOME:-$HOME/.config}/kitilix"
export KITTY_CACHE_DIRECTORY="${XDG_CACHE_HOME:-$HOME/.cache}/kitilix"
mkdir -p -- "$KITTY_CONFIG_DIRECTORY"
if [[ ! -e $KITTY_CONFIG_DIRECTORY/kitty.conf ]]; then
    (set -o noclobber; printf '# Preferenze personali di Kitilix.\n' > "$KITTY_CONFIG_DIRECTORY/kitty.conf") 2>/dev/null ||
        [[ -e $KITTY_CONFIG_DIRECTORY/kitty.conf ]]
fi
if [[ ! -e $KITTY_CONFIG_DIRECTORY/kitty.app.png ]]; then
    (set -o noclobber; cat "$root/packaging/kitilix.png" > "$KITTY_CONFIG_DIRECTORY/kitty.app.png") 2>/dev/null ||
        [[ -e $KITTY_CONFIG_DIRECTORY/kitty.app.png ]]
fi
export PATH="$engine/kitty/launcher:$PATH"
exec "$engine/kitty/launcher/kitty" --class kitilix --name kitilix --title Kitilix --directory "$directory" \
    --config "$root/packaging/kitilix.conf" --config "$KITTY_CONFIG_DIRECTORY/kitty.conf" \
    -o enabled_layouts=splits,horizontal,vertical,grid,stack \
    -o tab_bar_min_tabs=1 -o tab_bar_edge=top -o tab_bar_style=separator \
    -o startup_session=none -o restore_session_after_logout=no -o linux_display_server=x11
