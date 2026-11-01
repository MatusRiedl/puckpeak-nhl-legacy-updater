"""A window that never comes up (solid blue or black, nothing to click) must not stay that way. After the start, the page
has FIRST seconds to get its data and draw it (it says so itself: Api.page_up). If it does not:
  1. the page is loaded again (and the stuck threads are written into logs/start.log);
  2. still nothing within SECOND seconds: if the page never even asked, the program starts itself again once with
     the browser's graphics turned off (the usual cause of a black window) and remembers that it worked;
  3. otherwise the window closes and the simple (classic) window opens, with the reason in the error log.
A browser engine that gave up (startlog.engine_failed) goes straight to step 2: nothing can load in it."""
import ctypes
import os
import shutil
import subprocess
import sys
import threading
import time

from .. import datasource, savedata
from . import startlog

FIRST, SECOND = 15.0, 20.0
RETRIED = 'LEGACY_ROSTER_RETRIED'                 # set in the program started again: no second retry
AFTER_ENGINE = 'engine'                           # its value when the browser engine gave up: says nothing about the graphics
BROWSER_ARGS = 'QTWEBENGINE_CHROMIUM_FLAGS' if sys.platform.startswith('linux') else 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'
NO_GPU = '--disable-gpu'
NO_GPU_FILE = 'window_no_gpu.txt'                 # in the program's folder: a start with the graphics off worked, start that way
# (a file of its own: the settings file is rewritten from the controller's copy and would lose the flag)
FOLDER = 'webview'                                # in the program's folder: one folder per start, named by its process


def retried():
    return os.environ.get(RETRIED, '')


def graphics_off():
    return NO_GPU in os.environ.get(BROWSER_ARGS, '')


def running(pid):
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            pass
        return True
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)         # PROCESS_QUERY_LIMITED_INFORMATION
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
    return bool(handle)


def sweep(base):
    """What starts that crashed or were ended left (a window that closes deletes its own folder)."""
    for name in os.listdir(base):
        if name.isdigit() and not running(int(name)):
            shutil.rmtree(os.path.join(base, name), ignore_errors=True)


def browser_folder():
    """The browser's own folder, a new one for every start. In a folder shared by all starts, a browser still closing
    held it (the last start, the start that failed, the copy an update replaced) and WebView2 refused to start
    ("0x800700AA: The requested resource is in use"), which leaves the blue window; and a window deletes the folder
    as it closes, under a start already using it."""
    base = datasource.app_dir(FOLDER)
    threading.Thread(target=sweep, args=(base,), daemon=True).start()
    return os.path.join(base, str(os.getpid()))


def use_saved():
    """A start without graphics worked before: start that way again (the browser reads this variable itself)."""
    if os.path.exists(datasource.app_dir(NO_GPU_FILE)) and not graphics_off():
        os.environ[BROWSER_ARGS] = (os.environ.get(BROWSER_ARGS, '') + ' ' + NO_GPU).strip()
        startlog.note("starting with the browser's graphics off (an earlier start needed it)")


def restart_without_gpu():
    """Start this program again, once, with the graphics off. True when it started."""
    env = savedata.clean_environment()
    env[BROWSER_ARGS] = (env.get(BROWSER_ARGS, '') + ' ' + NO_GPU).strip()
    env[RETRIED] = AFTER_ENGINE if startlog.engine_failed.is_set() else '1'
    args = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, '-m', 'legacy_roster']
    flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    try:
        savedata.launch(args, env=env, close_fds=True, creationflags=flags)
    except OSError as err:
        startlog.note(f"could not start again: {err}")
        return False
    return True


class Watchdog:
    def __init__(self, host, first=FIRST, second=SECOND, restart=restart_without_gpu, was_retried=None):
        self.host = host
        self.first, self.second = first, second
        self.restart = restart
        self.was_retried = retried() if was_retried is None else was_retried
        self.outcome = None             # 'ok', 'reloaded', 'again', 'classic'
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        return self

    def wait(self, seconds):
        """Until the page is up (True), the browser engine gave up or the time is over (False)."""
        end = time.monotonic() + seconds
        while time.monotonic() < end and not startlog.engine_failed.is_set():
            if startlog.page_up.wait(0.05):
                return True
        return startlog.page_up.is_set()

    def reload(self):
        """Under a new address, not one of boot.js's own reloads (?again=N): asked for the one it already has, the
        browser does nothing, and pywebview, which waits for that page to load, stops answering the page that is there."""
        try:
            window = self.host.window
            window.load_url(window.real_url.split('?')[0] + '?reloaded=1')
            return True
        except Exception as err:
            startlog.note(f"could not load the page again: {err}")
        return False

    def remember(self):
        """The start with the graphics off worked: the next starts use it too."""
        flag = datasource.app_dir(NO_GPU_FILE)
        if not os.path.exists(flag):
            try:
                with open(flag, 'w', encoding='utf-8') as f:
                    f.write("The window needed the browser's graphics off to start. Delete this file to try them again.\n")
                startlog.note("this start worked with the graphics off: the next starts do the same")
            except OSError:
                pass

    def worked(self, outcome):
        self.outcome = outcome
        if self.was_retried and self.was_retried != AFTER_ENGINE:
            self.remember()
        return outcome

    def run(self):
        if self.wait(self.first):
            return self.worked('ok')
        if startlog.engine_failed.is_set():
            return self.way_out()
        called = startlog.ready_called.is_set()
        startlog.note(f"nothing after {self.first:.0f}s: the page "
                      + ("asked for its data and did not draw it" if called else "never asked for its data"), 'watchdog')
        startlog.dump_threads("the page did not come up")
        startlog.note_processes()
        startlog.note_unanswered()
        url = getattr(self.host.window, 'real_url', None)
        startlog.note(f"the page's address: {url}")
        if url and url.startswith('http'):
            startlog.probe(url)
        if not called:
            startlog.note("loading the page again" if self.reload() else "the page cannot be loaded again")
        if self.wait(self.second):
            startlog.note("the page came up after the wait")
            return self.worked('reloaded')
        return self.way_out()

    def way_out(self):
        called = startlog.ready_called.is_set()
        if not called and not self.was_retried:
            startlog.note("still nothing: starting the program again with the graphics off")
            if self.restart():
                self.outcome = 'again'
                self.host.window.destroy()
                return self.outcome
        if startlog.engine_failed.is_set():
            reason = "the browser engine did not start"
        else:
            reason = ("the page did not ask for its data" if not called else "the page did not draw its data") \
                + f" within {self.first + self.second:.0f} seconds"
        startlog.note(f"opening the simple window: {reason}")
        self.outcome = 'classic'
        self.host.use_classic(reason)
        return self.outcome
