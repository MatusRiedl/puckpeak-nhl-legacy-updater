"""What the controllers need from the window: pushes to the page, file dialogs, opening folders.

Changes are not sent one by one: a controller marks its slice as changed, and one thread sends
everything that changed, at most 25 times a second, in one call (the newest state wins, the
details lines are sent together). Hundreds of progress lines cost the page a few redraws."""
import json
import os
import threading
import time
import webbrowser

from .. import savedata
from . import startlog

PUSH_EVERY = 0.04           # seconds between two pushes (25 a second at most)
KEEP_LINES = 5000           # details lines kept for a reload of the page


class WebHost:
    def __init__(self):
        self.window = None
        self.sources = {}           # slice name -> snapshot()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._dirty = set()
        self._lines, self._clear, self._events = [], False, []
        self.lines = []             # every details line of this run (the page asks for them on ready)
        self._pushing = False
        self.fallback = None        # why the simple window is to open once this one is closed (a start that failed)

    def attach(self, window):
        self.window = window

    def use_classic(self, reason):
        """Close the window; window/main.py then opens the simple one and writes `reason` into the error log."""
        self.fallback = reason
        if self.window is not None:
            self.window.destroy()

    def register(self, name, snapshot):
        self.sources[name] = snapshot

    # --- what the controllers call --------------------------------------------------------------
    def changed(self, name):
        with self._lock:
            self._dirty.add(name)
        self._wake.set()

    def log(self, *lines):
        with self._lock:
            self._lines.extend(lines)
            self.lines.extend(lines)
            if len(self.lines) > KEEP_LINES:
                del self.lines[:len(self.lines) - KEEP_LINES]
        self._wake.set()

    def log_clear(self):
        with self._lock:
            self._lines, self._clear = [], True
            self.lines = []
        self._wake.set()

    def send(self, event, payload=None):
        with self._lock:
            self._events.append([event, payload])
        self._wake.set()

    def ask_open(self, title, kinds=(), start=None):
        return self._dialog('open', kinds, start)

    def ask_folder(self, title, start=None):
        return self._dialog('folder', (), start)

    def ask_save(self, title, filename, kinds=(), start=None):
        return self._dialog('save', kinds, start, filename)

    def _dialog(self, kind, kinds, start, filename=''):
        import webview
        if self.window is None:
            return None
        mode = {'open': webview.FileDialog.OPEN, 'folder': webview.FileDialog.FOLDER, 'save': webview.FileDialog.SAVE}[kind]
        start = start if start and os.path.isdir(start) else os.path.expanduser('~')
        try:
            picked = self.window.create_file_dialog(mode, directory=start, save_filename=filename,
                                                    file_types=tuple(kinds))
        except ValueError:          # a file type pywebview does not take: ask without
            picked = self.window.create_file_dialog(mode, directory=start, save_filename=filename)
        if not picked:
            return None
        return picked if isinstance(picked, str) else picked[0]

    def open_path(self, path):
        savedata.open_path(path)

    def open_url(self, url):
        if savedata.WINDOWS or savedata.MAC:
            webbrowser.open(url)
            return
        try:                        # Linux: the browser must not inherit the program's own libraries (savedata.launch)
            savedata.open_path(url)
        except OSError:
            webbrowser.open(url)

    def quit(self):
        """Close the window for good (after an update started the new program)."""
        if self.window is not None:
            self.window.destroy()
        # safety net: the process must end even if the window library keeps it alive
        timer = threading.Timer(3.0, lambda: os._exit(0))
        timer.daemon = True
        timer.start()

    def every(self, seconds, work):
        def loop():
            while True:
                time.sleep(seconds)
                try:
                    work()
                except Exception:       # a timer never takes the window down
                    pass
        threading.Thread(target=loop, daemon=True).start()

    # --- the pushes ---------------------------------------------------------------------------------
    def first(self):
        """Everything, for a page that has just loaded (also after a reload)."""
        with self._lock:
            self._dirty.clear()
            self._lines, self._clear = [], False
            lines = list(self.lines)
        slices = {}
        for name, snapshot in self.sources.items():
            began = time.monotonic()
            slices[name] = snapshot()
            if time.monotonic() - began > 0.5:          # a slow slice is what keeps the page blue: say which
                startlog.note(f"the first data of '{name}' took {time.monotonic() - began:.1f}s")
        return {'slices': slices, 'log': {'lines': lines, 'clear': True}}

    def start_pushing(self):
        if self._pushing:
            return
        self._pushing = True
        threading.Thread(target=self._pusher, daemon=True).start()

    def take(self):
        """What changed since the last push, as one message (None: nothing)."""
        with self._lock:
            dirty, self._dirty = self._dirty, set()
            lines, self._lines = self._lines, []
            clear, self._clear = self._clear, False
            events, self._events = self._events, []
        if not (dirty or lines or clear or events):
            return None
        message = {}
        if dirty:
            message['slices'] = {name: self.sources[name]() for name in dirty if name in self.sources}
        if lines or clear:
            message['log'] = {'lines': lines, 'clear': clear}
        if events:
            message['events'] = events
        return message

    def _pusher(self):
        last = 0.0
        while True:
            self._wake.wait(0.5)
            self._wake.clear()
            wait = PUSH_EVERY - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
            message = self.take()
            if message is None or self.window is None:
                continue
            last = time.monotonic()
            script = "window.LR && window.LR.receive(" + json.dumps(message) + ")"
            try:
                self.window.run_js(script)
            except Exception:           # the window is closing
                pass
