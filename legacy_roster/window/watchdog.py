"""A window that never gets its data (solid blue or black, nothing to click) must not stay that way. After the window
shows, the page has FIRST seconds to ask Python for its data and get it. If it does not:
  1. the page is loaded again (and the stuck threads are written into logs/start.log);
  2. still nothing within SECOND seconds: if the page never even asked, the program starts itself again once with
     the browser's graphics turned off (the usual cause of a black window) and remembers that it worked;
  3. otherwise the window closes and the simple (classic) window opens, with the reason in the error log."""
import os
import subprocess
import sys
import threading

from .. import datasource, savedata
from . import startlog

FIRST, SECOND = 15.0, 20.0
RETRIED = 'LEGACY_ROSTER_RETRIED'                 # set in the program started again: no second retry
BROWSER_ARGS = 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'
NO_GPU = '--disable-gpu'
NO_GPU_FILE = 'window_no_gpu.txt'                 # in the program's folder: a start with the graphics off worked, start that way
# (a file of its own: the settings file is rewritten from the controller's copy and would lose the flag)


def retried():
    return os.environ.get(RETRIED) == '1'


def use_saved():
    """A start without graphics worked before: start that way again (the browser reads this variable itself)."""
    if os.path.exists(datasource.app_dir(NO_GPU_FILE)) and NO_GPU not in os.environ.get(BROWSER_ARGS, ''):
        os.environ[BROWSER_ARGS] = (os.environ.get(BROWSER_ARGS, '') + ' ' + NO_GPU).strip()
        startlog.note("starting with the browser's graphics off (an earlier start needed it)")


def restart_without_gpu():
    """Start this program again, once, with the graphics off. True when it started."""
    env = savedata.clean_environment()
    env[BROWSER_ARGS] = (env.get(BROWSER_ARGS, '') + ' ' + NO_GPU).strip()
    env[RETRIED] = '1'
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

    def reload(self):
        window = self.host.window
        try:
            url = window.get_current_url()
            if url:
                window.load_url(url)
                return True
        except Exception as err:
            startlog.note(f"could not load the page again with load_url: {err}")
        try:
            window.evaluate_js('location.reload()')
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

    def run(self):
        if startlog.ready_done.wait(self.first):
            self.outcome = 'ok'
            if self.was_retried:
                self.remember()
            return self.outcome
        called = startlog.ready_called.is_set()
        startlog.note(f"nothing after {self.first:.0f}s: the page {'asked for its data and got nothing' if called else 'never asked for its data'}",
                      'watchdog')
        startlog.dump_threads("the data did not arrive")
        startlog.note_processes()
        try:
            url = self.host.window.get_current_url()
        except Exception:
            url = None
        startlog.note(f"the page's address: {url}")
        if url and url.startswith('http'):
            startlog.probe(url)
        if not called:
            startlog.note("loading the page again" if self.reload() else "the page cannot be loaded again")
        if startlog.ready_done.wait(self.second):
            self.outcome = 'reloaded'
            startlog.note("the data arrived after the page was loaded again")
            return self.outcome
        called = startlog.ready_called.is_set()
        if not called and not self.was_retried:
            startlog.note("still nothing: starting the program again with the graphics off")
            if self.restart():
                self.outcome = 'again'
                self.host.window.destroy()
                return self.outcome
        reason = ("the page did not ask for its data" if not called else "the page's data did not arrive") \
            + f" within {self.first + self.second:.0f} seconds"
        startlog.note(f"opening the simple window: {reason}")
        self.outcome = 'classic'
        self.host.use_classic(reason)
        return self.outcome
