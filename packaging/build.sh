#!/usr/bin/env bash
# Build the Linux program into dist/ (PyInstaller builds for the system it runs on). Run it in the box
# packaging/linux/Dockerfile (Ubuntu 22.04: the program then runs on systems with glibc 2.35 or newer), then check it
# with packaging/linux_check.sh; MAINTAINING.md "The Linux program" has the steps. GitHub does not build it (0.80.0's
# from there opened the classic window on players' PCs), and there is no Mac program since 0.80.1 (owner).
#   dist/BluelineLegacy/                     a folder: the window (the page in legacy_roster/web through pywebview
#                                                   and its own web engine, Qt WebEngine from PySide6: nothing to install
#                                                   for the player; with arguments it is the command line) + README-LINUX.txt
#   dist/BluelineLegacy-<version>-linux.tar.gz   that folder, to attach to the release
# No picture pack goes inside: the program downloads its pictures (legacy_roster/packs.py), as the Windows exe does.
#
#   bash packaging/build.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(uname)" != "Linux" ]; then
    echo "This builds the Linux program; build it on Linux (packaging/linux/Dockerfile)." >&2
    exit 1
fi

py=.venv-build/bin/python
if [ ! -x "$py" ]; then
    "${PYTHON:-python3}" -m venv .venv-build
fi
# The window's web engine goes inside (window/main.linux_engine). Not GTK: a bundled WebKitGTK cannot start its helper
# programs and most players lack the system's (0.80.0 fell back to the classic window that way).
"$py" -m pip install --quiet --upgrade pip pyinstaller "pywebview==6.2.1" "customtkinter>=6.0,<7" "pillow>=11.2" certifi \
    "PySide6-Essentials==6.8.1" "PySide6-Addons==6.8.1" "qtpy==2.4.2"

version=$("$py" -c "import legacy_roster; print(legacy_roster.__version__)")
cacert=$("$py" -c "import certifi; print(certifi.where())")
web="$PWD/legacy_roster/web"
data="$PWD/legacy_roster/data"         # full paths: PyInstaller reads relative ones from its spec folder (build/)
if ls "$data"/*.zip* >/dev/null 2>&1; then
    echo "$data holds a zip: packs never go inside the program (private/packs)." >&2
    exit 1
fi
"$py" tools/clean_check.py || { echo "tools/clean_check.py found words that must not ship (see above)" >&2; exit 1; }
"$py" packaging/make_manifest.py     # the page's file list: the window checks it at start (window/main.missing_files)

# PIL._tkinter_finder: Pillow's bridge to Tk, imported only on a fallback path that PyInstaller does
# not see; without it the classic window stops at start ("invalid command name PyImagingPhoto").
qt=()
for m in QtCore QtGui QtWidgets QtNetwork QtWebChannel QtWebEngineCore QtWebEngineWidgets QtPrintSupport; do
    qt+=(--hidden-import "PySide6.$m")
done
rm -rf dist/BluelineLegacy dist/*-linux.tar.gz
# a folder, not one file: one file would unpack the ~300 MB engine into /tmp at every start
"$py" -m PyInstaller --noconfirm --clean --onedir --windowed \
    --add-data "$data:legacy_roster/data" --add-data "$cacert:legacy_roster/data" --add-data "$web:legacy_roster/web" \
    --hidden-import PIL.PngImagePlugin --hidden-import PIL.JpegImagePlugin \
    --hidden-import PIL.WebPImagePlugin --hidden-import PIL.GifImagePlugin \
    --hidden-import PIL.DdsImagePlugin --hidden-import legacy_roster.art.images \
    --hidden-import legacy_roster.art.looks --hidden-import legacy_roster.art.lookpack --hidden-import PIL._tkinter_finder \
    --collect-all webview --collect-all customtkinter "${qt[@]}" \
    --exclude-module gi --exclude-module PyQt5 --exclude-module PyQt6 \
    --distpath dist --workpath build --specpath build \
    --name BluelineLegacy packaging/launcher.py

# the system's own libraries stay the player's: the graphics driver (Mesa) loads into the program and needs the
# system's newer libstdc++ / libgbm / X11 / fontconfig; with this box's older copies inside, Qt got no OpenGL and drew a
# black window on Arch and Fedora (2026-10-27). libxcb-cursor and libxcb-util stay inside (many systems lack them).
for lib in 'libstdc++.so.6' libgcc_s.so.1 libgbm.so.1 'libdrm*.so*' 'libX11*.so*' 'libXau.so*' 'libXdmcp.so*' \
           'libxcb.so*' 'libxcb-[!cu]*.so*' 'libxkbcommon*.so*' libexpat.so.1 libfontconfig.so.1 libfreetype.so.6 \
           'libglib-2.0.so*' 'libgobject-2.0.so*' 'libgio-2.0.so*' 'libgmodule-2.0.so*' 'libgthread-2.0.so*' libz.so.1 \
           'libdbus-1.so*' 'libGL*.so*' 'libEGL*.so*' 'libOpenGL*.so*' 'libwayland-*.so*' 'libasound.so*'; do
    rm -f dist/BluelineLegacy/_internal/$lib
done

# every library the program's parts link to must be inside or a part of every Linux (libc, X11, GL): a library this box
# lacks was left out by PyInstaller and the window fails on players' PCs (Qt WebEngine's libatomic, 2026-10-27). Qt's
# GTK look-alike theme and its printing support are optional: Qt skips them on a PC without GTK 3 / CUPS.
inside=$(find dist/BluelineLegacy/_internal -name '*.so*' -printf '%h\n' | sort -u | paste -sd:)
missing=$(find dist/BluelineLegacy/_internal -name '*.so*' -type f \
              -not -path '*/plugins/platformthemes/*' -not -path '*/plugins/printsupport/*' -print0 \
          | while IFS= read -r -d '' lib; do
                LD_LIBRARY_PATH="$inside" ldd "$lib" 2>/dev/null | grep 'not found' | sed "s|\$|   (for ${lib#dist/})|" || true
            done)
if [ -n "$missing" ]; then
    echo "Libraries the program needs are missing (install them in packaging/linux/Dockerfile):" >&2
    echo "$missing" >&2
    exit 1
fi

cp packaging/linux/README-LINUX.txt dist/BluelineLegacy/
tar czf "dist/BluelineLegacy-$version-linux.tar.gz" -C dist BluelineLegacy
ls -l dist
echo "version $version"
