#!/usr/bin/env bash
# Build the standalone Linux app: a program that runs on a machine without
# Python installed.
#
#   tools/build_app.sh              # folder + CLI, packed as tar.gz
#   tools/build_app.sh --appimage   # ... and a single-file AppImage
#
# In dist/ afterwards:
#   Sortiton/                          unpacked GUI (start Sortiton/Sortiton)
#   sortiton                           the command line, one file
#   sortiton-<version>-linux-<arch>.tar.gz
#   Sortiton-<version>-<arch>.AppImage (only with --appimage)
#
# tkinter and mutagen go inside, ffmpeg does not - the app calls ffprobe/ffmpeg
# on the target machine. Needs PyInstaller (requirements-dev.txt) and, for the
# AppImage, appimagetool in $PATH or in $APPIMAGETOOL. The version is read from
# sortiton/__init__.py.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Use the project venv when there is one: PyInstaller and mutagen sit in it.
if [ -x "$ROOT/.venv/bin/python3" ]; then
    PATH="$ROOT/.venv/bin:$PATH"
fi

want_appimage=0
case "${1:-}" in
    "") ;;
    --appimage) want_appimage=1 ;;
    *)
        printf 'usage: %s [--appimage]\n' "$(basename "$0")" >&2
        exit 2
        ;;
esac

version="$(python3 -c 'import sortiton; print(sortiton.__version__)')"
arch="$(uname -m)"
tarball="sortiton-$version-linux-$arch.tar.gz"
appimage="Sortiton-$version-$arch.AppImage"
dist="$ROOT/dist"

# mutagen is imported inside the functions that use it (it is optional), so
# PyInstaller never sees it: --collect-submodules has to take the whole package
# along. The linting tools have no business in the app.
common=(
    --noconfirm --clean
    --distpath "$dist"
    --specpath "$ROOT/build"
    --collect-submodules mutagen
    --exclude-module pylint
    --exclude-module astroid
)

step() {
    printf '\n== %s ==\n' "$1"
}

rm -rf "$ROOT/build" "$dist"
mkdir -p "$dist"

step "GUI (folder build)"
# Keep the console - Linux has no "windowed" flag, and started from a terminal
# the program then still shows what it does.
# --add-data wants an absolute source path, --specpath moves the working
# directory of the spec file to build/.
python3 -m PyInstaller "${common[@]}" \
    --name Sortiton \
    --workpath "$ROOT/build/work-gui" \
    --add-data "$ROOT/assets/icon.png:assets" \
    sortiton_gui.py

step "CLI (single file)"
python3 -m PyInstaller "${common[@]}" \
    --name sortiton \
    --onefile \
    --workpath "$ROOT/build/work-cli" \
    sortiton.py

step "Pack"
# Both artefacts are checked first: a build that quietly produced a folder
# instead of a program would land in the release as a folder.
[ -x "$dist/Sortiton/Sortiton" ] || { printf '   no GUI program in %s\n' "$dist/Sortiton" >&2; exit 1; }
[ -f "$dist/sortiton" ] || { printf '   no CLI program at %s/sortiton\n' "$dist" >&2; exit 1; }
stage="$dist/Sortiton-$version-linux-$arch"
mkdir -p "$stage"
cp -r "$dist/Sortiton" "$stage/Sortiton"
install -m 0755 "$dist/sortiton" "$stage/sortiton"
install -m 0644 README.md LICENSE "$stage/"
tar -czf "$dist/$tarball" -C "$dist" "$(basename "$stage")"
rm -rf "$stage"

if [ "$want_appimage" = 1 ]; then
    step "AppImage"
    apdir="$ROOT/build/AppDir"
    tool="${APPIMAGETOOL:-$(command -v appimagetool || true)}"
    if [ -z "$tool" ]; then
        printf '   appimagetool not found - put it into $PATH or set $APPIMAGETOOL:\n' >&2
        printf '   https://github.com/AppImage/appimagetool/releases (continuous)\n' >&2
        exit 1
    fi
    rm -rf "$apdir"
    mkdir -p "$apdir"
    cp -r "$dist/Sortiton/." "$apdir/"
    install -m 0755 packaging/AppRun "$apdir/AppRun"
    install -m 0644 packaging/sortiton.desktop "$apdir/sortiton.desktop"
    install -m 0644 assets/icon.png "$apdir/sortiton.png"
    # --appimage-extract-and-run builds without FUSE (containers, CI).
    ARCH="$arch" "$tool" --appimage-extract-and-run "$apdir" "$dist/$appimage"
fi

step "Result"
found=0
for file in "$dist/$tarball" "$dist/$appimage"; do
    if [ -f "$file" ]; then
        printf '   %5s  %s\n' "$(du -h "$file" | cut -f1)" "${file#"$ROOT"/}"
        found=$((found + 1))
    fi
done
printf '   %5s  dist/Sortiton/Sortiton\n' "$(du -sh "$dist/Sortiton" | cut -f1)"
printf '   the target machine still needs ffmpeg (reading and writing tags)\n'
[ "$found" -gt 0 ]
