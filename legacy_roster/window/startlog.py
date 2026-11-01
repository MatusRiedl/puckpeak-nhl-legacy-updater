"""The start trace: logs/start.log keeps what the last starts of the window did and when (the window shown, the page
loaded, the page asking for its data, the data sent), so a window that stays blue or black leaves something to read.
Standard library only; nothing here may ever stop a start."""
import datetime
import faulthandler
import os
import subprocess
import sys
import threading
import time

from .. import __version__, datasource

KEEP = 20               # starts kept in the file
HEADER = "== start "

_lock = threading.Lock()
_t0 = time.monotonic()
_seen = {}              # event name -> seconds after the start (the first time)
ready_called = threading.Event()        # the page asked for its data (Api.ready)
ready_done = threading.Event()          # ... and got it


def path():
    return datasource.app_dir('logs', 'start.log')


def begin(argv=()):
    """A new block at the end of the file; the oldest starts beyond KEEP go. Returns False when the file cannot be
    written."""
    global _t0
    _t0 = time.monotonic()
    _seen.clear()
    ready_called.clear()
    ready_done.clear()
    try:
        old = ''
        if os.path.exists(path()):
            with open(path(), encoding='utf-8', errors='replace') as f:
                old = f.read()
        blocks = [HEADER + b for b in old.split(HEADER) if b.strip()]
        blocks = blocks[-(KEEP - 1):]
        head = (f"{HEADER}{datetime.datetime.now().isoformat(timespec='seconds')}  version {__version__}  "
                f"pid {os.getpid()}  {'exe' if getattr(sys, 'frozen', False) else 'source'}  "
                f"args {' '.join(argv) or '-'}\n")
        with _lock, open(path(), 'w', encoding='utf-8') as f:
            f.write(''.join(b if b.endswith('\n') else b + '\n' for b in blocks) + head)
        return True
    except OSError:
        return False


def note(text, event=None):
    """One line: the seconds since the start and `text`. `event` also remembers the time (the first one counts)."""
    seconds = time.monotonic() - _t0
    if event is not None:
        with _lock:
            _seen.setdefault(event, seconds)
    try:
        with _lock, open(path(), 'a', encoding='utf-8') as f:
            f.write(f"  +{seconds:6.2f}s  {text}\n")
    except OSError:
        pass


def when(event):
    """Seconds after the start when `event` first happened, or None."""
    with _lock:
        return _seen.get(event)


def dump_threads(why):
    """What every thread of the program is doing right now (faulthandler's traceback), into the file: a page that
    waits for data that never comes shows here which call is stuck."""
    try:
        with _lock, open(path(), 'a', encoding='utf-8') as f:
            f.write(f"  +{time.monotonic() - _t0:6.2f}s  threads ({why}):\n")
            f.flush()
            faulthandler.dump_traceback(file=f, all_threads=True)
    except (OSError, ValueError, RuntimeError):
        pass


def probe(url):
    """Ask the page's own local server for the page and its first script, the way a browser would, and write what came
    back (status, type, size): a server that is gone, or an antivirus / proxy that changed the answers, shows here."""
    import urllib.error
    import urllib.parse
    import urllib.request
    base = url.rsplit('/', 1)[0] + '/'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # the program's own server: never a proxy
    for name in (url.rsplit('/', 1)[-1] or 'index.html', 'js/main.js', 'css/app.css'):
        target = urllib.parse.urljoin(base, name)
        try:
            with opener.open(target, timeout=5) as reply:
                body = reply.read()
                note(f"server: {name} -> {reply.status} {reply.headers.get('Content-Type')} {len(body)} bytes")
        except (OSError, urllib.error.URLError, ValueError) as err:
            note(f"server: {name} -> {err}")


def processes():
    """Windows: how many copies of this program and of Edge's WebView2 are running now (a browser process left over
    from an earlier start can hold the window's profile). Slow: call it in a thread."""
    if os.name != 'nt':
        return None
    me = os.path.basename(sys.executable).lower() if getattr(sys, 'frozen', False) else None
    try:
        out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=15,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    names = [line.split('","')[0].strip('"').lower() for line in out.splitlines() if line.strip()]
    return {'webview2': names.count('msedgewebview2.exe'), 'copies': names.count(me) if me else None}


def note_processes():
    """Write `processes()` into the trace, in the background."""
    def work():
        found = processes()
        if found is not None:
            note(f"running now: {found['webview2']} WebView2 process(es)"
                 + (f", {found['copies']} copy/copies of {os.path.basename(sys.executable)}" if found['copies'] is not None else ''))
    threading.Thread(target=work, daemon=True).start()
