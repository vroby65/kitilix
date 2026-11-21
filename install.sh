#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cd "$root"

"$root/package.sh"
image="$root/dist/kitilix"
data="${XDG_DATA_HOME:-$HOME/.local/share}"
app="$data/kitilix"
mkdir -p -- "$app" "$data/applications" "$data/icons/hicolor/128x128/apps"

stage=$(mktemp -d -- "$app/.install.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT
install -m 755 "$image" "$stage/kitilix"
mv -fT -- "$stage/kitilix" "$app/kitilix"

python3 - "$app/kitilix" packaging/kitilix.desktop "$stage/kitilix.desktop" <<'PY'
import sys
from pathlib import Path

launcher, template, output = sys.argv[1:]
escaped = launcher.replace("%", "%%").translate(str.maketrans({c: "\\" + c for c in '\\"$`'}))
escaped = escaped.replace("\\", "\\\\")
Path(output).write_text(Path(template).read_text().replace("Exec=kitilix\n", f'Exec="{escaped}"\n'))
PY
install -m 644 "$stage/kitilix.desktop" "$data/applications/kitilix.desktop"
install -m 644 packaging/kitilix.png "$data/icons/hicolor/128x128/apps/kitilix.png"
printf 'Kitilix installato. Avvio da menu o da %s/kitilix\n' "$app"
