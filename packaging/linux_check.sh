#!/usr/bin/env bash
# The Linux program's check, after packaging/build.sh: unpack the tar.gz, open the window on a pretend screen (Xvfb),
# and pass only when the NEW window drew its page (window/main.smoke writes logs/smoke.txt); the classic window or no
# window fails. Also takes a picture of the screen and runs the program once with --help (the command line). Run it in a plain box of the
# system to try (needs xvfb, xwd and ImageMagick's convert):
#   bash packaging/linux_check.sh dist/BluelineLegacy-<version>-linux.tar.gz window.png
set -uo pipefail
archive=$1
picture=${2:-window.png}
work=$(mktemp -d)
logs=${XDG_DATA_HOME:-$HOME/.local/share}/NHLLegacyRosterUpdater/logs
rm -f "$logs/smoke.txt" "$logs/error.log"
tar xzf "$archive" -C "$work"
app=$work/BluelineLegacy

Xvfb :7 -screen 0 1600x1000x24 >/dev/null 2>&1 &
screen=$!
sleep 2
DISPLAY=:7 LEGACY_ROSTER_SMOKE=10 "$app/BluelineLegacy" >"$work/out.txt" 2>&1 &
program=$!
for _ in $(seq 1 120); do
    [ -s "$logs/smoke.txt" ] && break
    kill -0 $program 2>/dev/null || break
    sleep 1
done
sleep 2
DISPLAY=:7 xwd -root -silent | convert xwd:- "$picture"
for _ in $(seq 1 30); do                # the new window closes by itself after 10 s; the classic one never
    kill -0 $program 2>/dev/null || break
    sleep 1
done
kill $program $screen 2>/dev/null

status=0
if [ -s "$logs/smoke.txt" ]; then
    echo "window: $(cat "$logs/smoke.txt")"
    buttons=$(sed -n 's/.*buttons \([0-9]*\).*/\1/p' "$logs/smoke.txt")
    [ "${buttons:-0}" -ge 10 ] || { echo "FAIL: the page drew only ${buttons:-no} buttons"; status=1; }
else
    echo "FAIL: the new window did not open"; status=1
fi
# the page counted its buttons, but was it drawn? A black screen (no OpenGL for Qt, 2026-10-27) has no spread of colours
spread=$(convert "$picture" -format '%[fx:standard_deviation]' info: 2>/dev/null)
if awk "BEGIN{exit !(${spread:-0} < 0.02)}"; then
    echo "FAIL: the screen stayed blank (colour spread ${spread:-unknown})"; status=1
fi
if grep -q "classic window" "$logs/error.log" 2>/dev/null; then
    echo "FAIL: the classic window was used"; status=1
fi
[ $status = 0 ] || { echo "--- program output"; tail -40 "$work/out.txt"; echo "--- error.log"; tail -40 "$logs/error.log" 2>/dev/null; }
"$app/BluelineLegacy" --help >/dev/null || { echo "FAIL: the command line (the program with arguments) does not start"; status=1; }
rm -rf "$work"
[ $status = 0 ] && echo "PASS"
exit $status
