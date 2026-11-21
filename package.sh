#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cd "$root"

./build.sh --portable
mkdir -p dist
exec 8>.build/package.lock
flock 8
stage=$(mktemp -d "$root/.build/package.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT

mkdir "$stage/runtime"
python3 src/stage-elf.py "$(readlink -f .build/engine-portable)" "$stage/runtime"
tar --format=posix -czf "$stage/payload.tar.gz" -C "$stage/runtime" .
cat > "$stage/payload.S" <<'ASM'
.section .rodata.kitilix,"a",%progbits
.balign 16
.global kitilix_payload_start, kitilix_payload_end
kitilix_payload_start:
.incbin "payload.tar.gz"
kitilix_payload_end:
.section .note.GNU-stack,"",%progbits
ASM
(cd "$stage" && cc -O2 -Wall -Wextra -Werror "$root/src/elf-launcher.c" payload.S -o kitilix)
mv -fT -- "$stage/kitilix" dist/kitilix
printf '%s/dist/kitilix\n' "$root"
