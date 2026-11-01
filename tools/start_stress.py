"""Start the window again and again and count the starts that never got their data (the blue / black window).

    python tools/start_stress.py --exe dist\\PuckPeakLegacyUpdater.exe --runs 30
    python tools/start_stress.py --source --runs 5                       # .venv's python -m legacy_roster
    python tools/start_stress.py --exe ... --fail ready-hang --runs 1    # the way out of a failed start, on purpose

Each run uses a temporary LOCALAPPDATA (so it never touches the player's folder), no update check and no download,
and kills the whole process tree afterwards (a browser process left behind would cause the very symptom measured). A run
counts as good when logs/start.log says the page drew its data (or, with --fail, when the expected way out was taken).
--fail: ready-hang (the program never answers the page), ready-error (it answers with an error), blank (the page
file is missing in the first start: the page never asks, the second start must work), render (the first tab cannot
draw), js-type (this PC names .js files wrongly: the page must come up all the same), engine (WebView2 cannot start),
lost-file (the browser does not get a file once: the page loads itself again), lost-always (it never gets it),
lost-stall (the page loads itself again and hangs: the watchdog's reload must still reach it).
0 = nothing wrong, 1 = a start failed."""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONE = "the page drew its data"
SLOW = 10                                   # seconds; a normal start takes about 4
CLASSIC = "opening the simple window"
EXPECTED = {'ready-hang': [CLASSIC], 'ready-error': ["FAIL"],
            'blank': ["starting the program again with the graphics off", "the browser engine is", DONE],
            'render': ["page: FAIL Error in the page", CLASSIC],
            'js-type': ["this PC says .js files are text/plain", DONE],
            'lost-file': ["loaded again, try 1", DONE], 'lost-always': ["loaded again, try 5", CLASSIC],
            'lost-stall': ["loading the page again", "the page came up after the wait"],
            'engine': ["pywebview: WebView2 initialization failed", "starting the program again", CLASSIC]}


def webview_processes():
    out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout.lower()
    return out.count('msedgewebview2.exe')


def kill_tree(proc):
    subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        pass


def log_path(home):
    return os.path.join(home, 'NHLLegacyRosterUpdater', 'logs', 'start.log')


def log_of(home):
    try:
        with open(log_path(home), encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def one(command, home, fail, wait):
    env = dict(os.environ, LOCALAPPDATA=home, TEMP=home, TMP=home,      # a killed exe leaves its 44 MB of unpacked files there
               LEGACY_ROSTER_RELEASE_URL='http://127.0.0.1:9/none')
    env.pop('LEGACY_ROSTER_SMOKE', None)
    if fail:
        env['LEGACY_ROSTER_FAIL'] = fail
    if os.path.exists(log_path(home)):
        os.remove(log_path(home))           # only this run's starts count (a retry is a second start)
    began = time.monotonic()
    proc = subprocess.Popen(command, env=env, cwd=ROOT, creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    want = EXPECTED.get(fail, [DONE])
    seen = False
    try:
        while time.monotonic() - began < wait:
            text = log_of(home)
            if all(word in text for word in want):
                seen = True
                time.sleep(1.5)             # let it draw
                break
            time.sleep(0.5)
    finally:
        kill_tree(proc)
        for pid in re.findall(r"pid (\d+)", log_of(home)):         # a program that started itself again is not our child
            subprocess.run(['taskkill', '/F', '/T', '/PID', pid], capture_output=True)
    return seen, time.monotonic() - began


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--exe', help="the built program (dist\\PuckPeakLegacyUpdater.exe)")
    ap.add_argument('--source', action='store_true', help="run from source with .venv's python")
    ap.add_argument('--runs', type=int, default=30)
    ap.add_argument('--fail', choices=sorted(EXPECTED), help="fail on purpose")
    ap.add_argument('--wait', type=float, help="seconds to wait for each start (default 30, 90 with --fail)")
    args = ap.parse_args()
    if args.source:
        command = [os.path.join(ROOT, '.venv', 'Scripts', 'python.exe'), '-m', 'legacy_roster']
    else:
        command = [args.exe or os.path.join(ROOT, 'dist', 'PuckPeakLegacyUpdater.exe')]
        if not os.path.exists(command[0]):
            sys.exit(f"{command[0]} is not there: build it first or use --source")
    wait = args.wait or (90 if args.fail else 30)
    before = webview_processes()
    print(f"{args.runs} starts of {' '.join(command)}" + (f", failing on purpose: {args.fail}" if args.fail else '')
          + f"  (WebView2 processes already running: {before})")
    good, home = 0, tempfile.mkdtemp(prefix='start_stress_')
    try:
        for n in range(1, args.runs + 1):
            ok, seconds = one(command, home, args.fail, wait)
            good += ok
            print(f"  {n:2d}: {'ok ' if ok else 'BAD'} {seconds:5.1f}s")
            if not ok:
                print('      ' + (log_of(home).strip().splitlines() or ['(no start.log)'])[-1])
            elif seconds > SLOW and not args.fail:      # it may have got stuck and been saved by the watchdog
                print('\n'.join('      ' + line for line in log_of(home).strip().splitlines()))
        left = webview_processes() - before
        print(f"{good} of {args.runs} good; WebView2 processes left behind: {max(left, 0)}")
        if good < args.runs:
            print(log_of(home)[-3000:])
        return 0 if good == args.runs else 1
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
