"""Open the window: the page in `web/`, the controllers of `app/`, pywebview between them."""
import os
import sys

from .. import __version__, datasource
from ..app import texts as X
from . import startlog, watchdog, webview2

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')
DATA = os.path.join(os.path.dirname(WEB), 'data')
NEEDED = [os.path.join(WEB, *p) for p in (('index.html',), ('js', 'main.js'), ('vendor', 'react.production.min.js'),
                                          ('vendor', 'react-dom.production.min.js'), ('img', 'logo.png'))] \
    + [os.path.join(DATA, 'datapack.json.gz')]
WIDTH, HEIGHT, MIN_SIZE = 1080, 780, (940, 640)
BACKGROUND = '#07111f'
TITLE_BAR = 0x2e1a0a        # the title bar's colour on Windows 11 (#0a1a2e as Windows writes it: blue, green, red)


MANIFEST = 'manifest.txt'       # every file of web/, one path per line (packaging/make_manifest.py, made by build.ps1)


def missing_files():
    """The program's own files that are not there (an antivirus or a cleaner removed them from the
    temporary folder the exe unpacks into): the few it cannot start without, and every file the build listed."""
    gone = [p for p in NEEDED if not os.path.exists(p)]
    try:
        with open(os.path.join(WEB, MANIFEST), encoding='utf-8') as f:
            listed = [line.strip() for line in f if line.strip()]
    except OSError:
        listed = []             # a source folder has none: only the few above
    gone += [p for p in (os.path.join(WEB, *name.split('/')) for name in listed)
             if not os.path.exists(p) and p not in gone]
    return gone


def classic(reason):
    """The old window, while it is kept (0.10.x), when the new one cannot start; False without it."""
    try:
        import customtkinter  # noqa: F401
        from ..gui import main as old
    except ImportError:
        return False
    if reason:
        try:
            with open(datasource.app_dir('logs', 'error.log'), 'a', encoding='utf-8') as f:
                f.write(f"The new window could not start ({reason}); the classic window was used.\n")
        except OSError:
            pass
    note = None
    if reason:
        note = ("The full window did not start on this PC, so the simple one opened. Updating a roster works the same.\n"
                f"What happened is in {startlog.path()}")
    old(note=note)
    return True


def dark_title_bar(window):
    """Windows: a dark title bar in the colour of the panels (Windows 10 takes the dark mode only)."""
    if os.name != 'nt':
        return
    try:
        import ctypes
        hwnd = window.native.Handle.ToInt64()
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))        # dark mode
        colour = ctypes.c_int(TITLE_BAR)
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colour), ctypes.sizeof(colour))  # caption colour (Windows 11)
    except Exception:
        pass


LARGEST, SHARE = (1760, 1100), (0.9, 0.94)


def fit(area):
    """(x, y, width, height) of the screen's free area (no taskbar) -> the window's (width, height, x, y): most of
    it, centred, at least the old 1080 x 780 where that fits."""
    ax, ay, aw, ah = area
    w = min(LARGEST[0], max(min(WIDTH, aw), int(aw * SHARE[0])))
    h = min(LARGEST[1], max(min(HEIGHT, ah), int(ah * SHARE[1])))
    w, h = max(w, MIN_SIZE[0]), max(h, MIN_SIZE[1])
    return w, h, ax + max(0, (aw - w) // 2), ay + max(0, (ah - h) // 2)


def work_area(webview):
    """The main screen's free area in the window's units (Windows: its WorkingArea; elsewhere the screen less 80)."""
    screens = list(webview.screens)
    screen = next((s for s in screens if s.x == 0 and s.y == 0), screens[0])
    frame = getattr(screen, 'frame', None)
    try:
        return int(frame.X), int(frame.Y), int(frame.Width), int(frame.Height)
    except AttributeError:
        return int(screen.x), int(screen.y), int(screen.width), int(screen.height) - 80


def window_box(webview):
    try:
        return fit(work_area(webview))
    except Exception:
        return WIDTH, HEIGHT, None, None


def linux_engine():
    """Linux: the program brings its own web engine (Qt WebEngine through PySide6, packaging/build.sh), since many
    systems lack WebKitGTK and a bundled one cannot start its helpers (0.80.0 opened the classic window that way).
    'qt' when PySide6 is there, else None (from source: pywebview picks GTK or Qt itself)."""
    if not sys.platform.startswith('linux'):
        return None
    try:
        import PySide6  # noqa: F401
    except ImportError:
        return None
    from .. import savedata
    # the engine's sandbox needs user namespaces, which Ubuntu 24.04 and containers refuse to programs outside the
    # system; the page is the program's own, links open in the player's browser
    for var, value in (('QT_API', 'pyside6'), ('QTWEBENGINE_DISABLE_SANDBOX', '1')):
        if var not in os.environ:
            os.environ[var] = value
            savedata.OUR_VARIABLES.add(var)
    return 'qt'


def smoke(window, gui, seconds):
    """The build's check (packaging/linux_check.sh, LEGACY_ROSTER_SMOKE=<seconds>): once the page has drawn, write what
    shows into logs/smoke.txt, keep the window `seconds` for a picture, then close it."""
    import time
    window.events.loaded.wait(90)
    time.sleep(3)
    try:
        buttons = window.evaluate_js("document.querySelectorAll('button').length")
    except Exception as err:
        buttons = f"failed: {err}"
    with open(datasource.app_dir('logs', 'smoke.txt'), 'w', encoding='utf-8') as f:
        f.write(f"window {gui or 'default'} buttons {buttons}\n")
    time.sleep(seconds)
    window.destroy()


QUEUE = 64


def roomy_server():
    """pywebview's local server listens with Python's default queue of 5 connections; the page asks for more files at
    once, Windows refuses what does not fit and the window stayed blank (lab round 47c)."""
    from wsgiref.simple_server import WSGIServer
    WSGIServer.request_queue_size = QUEUE


def main(argv=None, after=None):
    """`after(window, controllers)`: run in a thread once the window shows (tools/window_shot.py)."""
    argv = sys.argv[1:] if argv is None else argv
    startlog.begin(argv)
    startlog.note(f"Python {sys.version.split()[0]}, WebView2 runtime {webview2.version() or 'not found'}")
    startlog.note_processes()
    if '--classic' in argv:
        if not classic(None):
            webview2.message("Puck Peak Legacy Updater", "The classic window is not part of this program.")
        return
    gone = missing_files()
    if gone:
        startlog.note("files missing: " + ", ".join(os.path.relpath(p, WEB) for p in gone[:12]))
        webview2.message("Puck Peak Legacy Updater", X.MISSING_FILES)
        return
    if not webview2.available():
        if classic("no WebView2 Runtime"):
            return
        if webview2.message("Puck Peak Legacy Updater",
                            "This program needs Microsoft Edge WebView2 Runtime, a free part of Windows from Microsoft.\n\n"
                            "Open the download page now? Install the \"Evergreen Bootstrapper\", then start this "
                            "program again.", ask=True):
            import webbrowser
            webbrowser.open(webview2.DOWNLOAD)
        return
    gui = linux_engine()
    try:
        import webview
    except ImportError as err:
        if not classic(f"pywebview missing: {err}"):
            sys.exit("The window needs the 'pywebview' package:  pip install pywebview\n"
                     "(the command line works without it:  python -m legacy_roster list --rpcs3 <rpcs3.exe>)")
        return

    from ..app import selfupdate
    from ..app.update import UpdateController
    from ..app.editor import EditorController
    from ..app.uniforms import UniformsController
    from ..app.equipment import EquipmentController
    from ..app.lines import LinesController
    from ..app.strategy import StrategyController
    from ..app.calendar import CalendarController
    from ..app.office import OfficeController
    from ..app.prospects import ProspectsController
    from ..app.career import CareerController
    from ..app.online import OnlineController
    from ..app.season import SeasonSource
    from .api import Api
    from .host import WebHost

    host = WebHost()
    update = UpdateController(host)
    editor = EditorController(host, update)
    uniforms = UniformsController(host, editor)
    equipment = EquipmentController(host, editor)
    lines = LinesController(host, editor)
    strategy = StrategyController(host, editor)
    season = SeasonSource(editor)                    # the player's own Season / Be a GM save, read only
    calendar = CalendarController(host, editor, season)
    office = OfficeController(host, editor, season)
    career = CareerController(host, editor)          # running Be a Pro careers (saved only on the player's Save)
    prospects = ProspectsController(host, editor, career)
    online = OnlineController(host, update)           # Play online: account, setup, lobby, the game (a follower: works while its tab shows)
    editor.follow_with('online', online)
    host.register('update', update.snapshot)
    host.register('editor', editor.snapshot)
    host.register('picture', editor.picture_view)
    host.register('face_pics', editor.face_pics_view)
    host.register('look_pics', editor.look_pics_view)
    host.register('uniforms', uniforms.snapshot)
    host.register('thumbs', uniforms.thumbs_view)
    host.register('equipment', equipment.snapshot)
    host.register('equip_pics', equipment.pics_view)
    host.register('lines', lines.snapshot)
    host.register('strategy', strategy.snapshot)
    host.register('rail', editor.rail_view)
    host.register('calendar', calendar.snapshot)
    host.register('office', office.snapshot)
    host.register('contract', office.contract_snapshot)
    host.register('prospects', prospects.snapshot)
    host.register('career', career.snapshot)
    host.register('online', online.snapshot)
    api = Api(host, update, editor, uniforms, equipment, lines, strategy, calendar, office, prospects, career, online)
    width, height, x, y = window_box(webview)
    page = 'missing.html' if os.environ.get('LEGACY_ROSTER_FAIL') == 'blank' else 'index.html'    # tools/start_stress.py
    window = webview.create_window(f"Puck Peak Legacy Updater {__version__}",
                                   url=os.path.join(WEB, page), js_api=api, width=width, height=height,
                                   x=x, y=y, min_size=MIN_SIZE, background_color=BACKGROUND, text_select=False)
    host.attach(window)
    window.events.closing += lambda: update.closing() and editor.closing() and career.closing() and online.closing()
    window.events.shown += lambda: dark_title_bar(window)
    window.events.shown += lambda: startlog.note("the window is shown", 'shown')
    window.events.loaded += lambda: startlog.note("the page is loaded", 'loaded')
    watch = None
    update.start_up()
    host.every(15, update.tick)
    selfupdate.clean_leftovers()
    update.check_for_update()
    update.download_pictures()
    controllers = {'host': host, 'update': update, 'editor': editor, 'uniforms': uniforms, 'equipment': equipment,
                   'lines': lines, 'strategy': strategy, 'calendar': calendar, 'office': office,
                   'prospects': prospects, 'career': career, 'online': online}
    roomy_server()
    watchdog.use_saved()
    if after is None and os.environ.get('LEGACY_ROSTER_SMOKE'):
        after = lambda win, _c: smoke(win, gui, float(os.environ['LEGACY_ROSTER_SMOKE']))   # noqa: E731
    if after is None and os.environ.get('LEGACY_ROSTER_NO_WATCHDOG') != '1':
        watch = watchdog.Watchdog(host)
    startlog.note("starting the window")
    try:
        webview.start(func=(lambda: after(window, controllers)) if after else (watch.start if watch else None), gui=gui,
                      http_server=True, private_mode=True, storage_path=datasource.app_dir('webview'),
                      debug=os.environ.get('LEGACY_ROSTER_DEVTOOLS') == '1',
                      icon=os.path.join(DATA, 'app.ico' if os.name == 'nt' else 'app_256.png'))
    except Exception as err:
        from ..app import jobs
        jobs.log_unexpected(err)
        startlog.note(f"pywebview failed: {err}")
        if not classic(f"pywebview failed: {err}"):
            webview2.message("Puck Peak Legacy Updater",
                             f"The window could not start: {err}\n\nPlease send us the error log: "
                             f"{datasource.app_dir('logs', 'error.log')}")
        return
    startlog.note("the window was closed")
    if host.fallback and not (watch and watch.outcome == 'again'):
        if not classic(host.fallback):
            webview2.message("Puck Peak Legacy Updater",
                             f"The window could not start ({host.fallback}).\n\nPlease send us the start log: "
                             f"{startlog.path()}")
