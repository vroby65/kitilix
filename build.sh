#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$root"

profile=native
case "${1:-kitilix}" in
    kitilix) engine_link=.build/engine; patches=(patches/kitty.patch patches/kitty-x11.patch) ;;
    --upstream) engine_link=.build/engine-upstream; patches=() ;;
    --portable) engine_link=.build/engine-portable; patches=(patches/kitty.patch patches/kitty-x11.patch); profile=portable ;;
    *) printf 'Usage: %s [--upstream|--portable]\n' "${0##*/}" >&2; exit 2 ;;
esac

version=0.51.0
case "$(uname -m)" in
    x86_64) arch=x86_64; binary_hash=c285daaf1b699997614939c8d1cd92dd8b99302ff12f18efcc3f69382aa72b1d ;;
    aarch64) arch=arm64; binary_hash=2a3eab469c37b548c5ceecff4b500a5b6b5c50f99cc17e0213e06a4c9662d31a ;;
    *) printf 'Unsupported Linux architecture.\n' >&2; exit 1 ;;
esac

mkdir -p .build/downloads
exec 9>.build/build.lock
flock 9
assets=".build/downloads"
upstream="https://github.com/kovidgoyal/kitty/releases/download/v$version"

download() {
    local url=$1 file=$2 checksum=$3
    if ! printf '%s  %s\n' "$checksum" "$file" | sha256sum --status -c; then
        curl -fL --retry 2 "$url" -o "$file.part"
        printf '%s  %s\n' "$checksum" "$file.part" | sha256sum -c
        mv -- "$file.part" "$file"
    fi
}

revision=$(
    {
        printf '%s %s\n' "$arch" "$profile"
        sha256sum src/build-engine.py build.sh "${patches[@]}"
    } | sha256sum | cut -d' ' -f1
)
engine="$root/.build/engine-$revision"
if [[ ! -f "$engine/.ready" ]]; then
    download "$upstream/kitty-$version.tar.xz" "$assets/source.tar.xz" 084807db816a3de9f1a253eff232f17fe9f76ccd77da8101511f830431097ecf
    download "$upstream/kitty-$version-$arch.txz" "$assets/kitty-$arch.txz" "$binary_hash"
    download https://github.com/simd-everywhere/simde/releases/download/v0.8.2/simde-amalgamated-0.8.2.tar.xz "$assets/simde.tar.xz" 59068edc3420e75c5ff85ecfd80a77196fb3a151227a666cc20abb313a5360bf

    resources="$root/.build/resources-$arch"
    if [[ ! -f "$resources/.ready" ]]; then
        mkdir -p "$resources"
        tar -xJf "$assets/kitty-$arch.txz" -C "$resources" bin/kitten lib/kitty/shaders lib/kitty/fonts
        tar -xJf "$assets/simde.tar.xz" -C "$resources"
        touch "$resources/.ready"
    fi

    ln -sfn simde-amalgamated-0.8.2 "$resources/simde"
    mkdir -p "$engine"
    tar -xJf "$assets/source.tar.xz" --strip-components=1 -C "$engine"
    for patch_file in "${patches[@]}"; do
        patch --batch --forward -d "$engine" -p1 < "$patch_file"
    done
    cp -a "$resources"/lib/kitty/{shaders,fonts} "$engine/"
    install -Dm 755 "$resources/bin/kitten" "$engine/kitty/launcher/kitten"
    python3 "$root/src/build-engine.py" "$engine" "$resources" "$profile"
    touch "$engine/.ready"
fi
if (( ${#patches[@]} )); then
    for module in "$root"/src/kitilix_*.py; do
        ln -sfn -- "$module" "$engine/kitty/${module##*/}"
    done
fi
ln -sfn -- "${engine##*/}" "$engine_link"
