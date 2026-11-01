"""The new window's pieces that need no window: the pushes to the page and the page's own files."""
import os
import re

from legacy_roster.window.host import WebHost

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'legacy_roster', 'web')


def test_changes_are_pushed_together_and_only_once():
    host = WebHost()
    calls = []
    host.register('update', lambda: calls.append('update') or {'n': len(calls)})
    host.register('editor', lambda: {'e': 1})
    assert host.take() is None
    host.changed('update')
    host.changed('update')
    host.log('one', 'two')
    host.send('details', {'open': True})
    message = host.take()
    assert message == {'slices': {'update': {'n': 1}}, 'log': {'lines': ['one', 'two'], 'clear': False},
                       'events': [['details', {'open': True}]]}
    assert host.take() is None
    first = host.first()
    assert set(first['slices']) == {'update', 'editor'} and first['log']['lines'] == ['one', 'two']


def test_the_page_names_only_its_own_files():
    """Everything the page loads is in web/ (the program works offline) and every import resolves."""
    with open(os.path.join(WEB, 'index.html'), encoding='utf-8') as f:
        page = f.read()
    for link in re.findall(r'(?:src|href)="([^"]+)"', page):
        assert not re.match(r'(https?:)?//', link), link
        assert os.path.exists(os.path.join(WEB, link)), link
    js = os.path.join(WEB, 'js')
    for name in os.listdir(js):
        with open(os.path.join(js, name), encoding='utf-8') as f:
            text = f.read()
        assert 'http://' not in text and 'cdn' not in text.lower(), name
        for target in re.findall(r"import(?:[^'\"]*from)?\s*\(?\s*'(\.[^']+)'", text):
            assert os.path.exists(os.path.normpath(os.path.join(js, target))), (name, target)


def test_every_call_of_the_page_is_offered_by_the_api():
    from legacy_roster.window.api import Api
    offered = {n for n in dir(Api) if not n.startswith('_')}
    js = os.path.join(WEB, 'js')
    called = set()
    for name in os.listdir(js):
        if name == 'demo.js':
            continue
        with open(os.path.join(js, name), encoding='utf-8') as f:
            called |= set(re.findall(r"call\('([a-z_]+)'", f.read()))
    assert called and called <= offered, called - offered


def test_the_setup_tabs_discord_button_opens_the_puck_peak_discord():
    from legacy_roster.window.api import Api

    class Host:
        opened = []

        def open_url(self, url):
            self.opened.append(url)

    host = Host()
    assert Api(host, None).open_discord() is None
    assert host.opened == ['https://gg.puckpeak.com']
    with open(os.path.join(WEB, 'js', 'shell.js'), encoding='utf-8') as f:
        assert "call('open_discord')" in f.read()
    with open(os.path.join(WEB, 'js', 'update.js'), encoding='utf-8') as f:
        assert '<${DiscordButton}/><${KofiButton}/></div>\n      <${RpcsCard}' in f.read()    # above "Where is RPCS3?" (owner, 0.50.2); Ko-fi beside Discord, one row (0.50.4)
    assert Api(host, None).open_kofi() is None and host.opened[-1] == 'https://ko-fi.com/iksperial'
    with open(os.path.join(WEB, 'js', 'shell.js'), encoding='utf-8') as f:
        assert "call('open_kofi')" in f.read()


def test_the_pages_server_takes_many_connections_at_once():
    """The page asks for its fonts and scripts at once; with Python's queue of 5 Windows refused the rest (lab 47c)."""
    import socket
    from wsgiref.simple_server import WSGIServer
    from legacy_roster.window import main
    was = WSGIServer.request_queue_size
    main.roomy_server()
    try:
        server = WSGIServer(('127.0.0.1', 0), None)
        socks = []
        try:
            for _ in range(30):                          # nobody accepts: every connection waits in the queue
                socks.append(socket.create_connection(server.server_address, timeout=5))
        finally:
            for s in socks:
                s.close()
            server.server_close()
    finally:
        WSGIServer.request_queue_size = was


def test_the_play_online_tab_is_wired_to_python():
    from legacy_roster.window.api import Api

    class Online:
        def __init__(self):
            self.said = []

        def refresh(self):
            self.said.append('refresh')

        def setup(self):
            self.said.append('setup')

        def create(self, public=None):
            self.said.append('create' if public is None else ('create', public))

        def set_public(self, on):
            self.said.append(('public', on))

        def refresh_list(self):
            self.said.append('list')

        def join(self, code):
            self.said.append(('join', code))

        def ready(self, on):
            self.said.append(('ready', on))

        def leave(self):
            self.said.append('leave')

    online = Online()
    api = Api(None, None, online=online)
    api.online_check(), api.online_setup(), api.online_create(), api.online_create(1), api.online_public(1), api.online_list()
    api.online_join('kdm qrs'), api.online_ready(1), api.online_leave()
    assert online.said == ['refresh', 'setup', 'create', ('create', True), ('public', True), 'list', ('join', 'kdm qrs'),
                           ('ready', True), 'leave']
    for name in ('js/online.js', 'js/main.js'):
        with open(os.path.join(WEB, name), encoding='utf-8') as f:
            text = f.read()
        assert ("call('online_setup')" in text) if name == 'js/online.js' else ("{ id: 'online', label: 'MULTIPLAYER', gold: true }" in text)



def test_on_linux_the_window_brings_its_own_qt_settings_and_rpcs3_gets_none_of_them(monkeypatch):
    """Linux: Qt WebEngine without its sandbox; each variable the program sets is recorded, so
    savedata.clean_environment keeps it from RPCS3 (a Qt program too). A player's own setting is left alone."""
    import sys
    import types
    from legacy_roster import savedata
    from legacy_roster.window import main
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setitem(sys.modules, 'PySide6', types.ModuleType('PySide6'))
    monkeypatch.setattr(savedata, 'OUR_VARIABLES', set())
    monkeypatch.delenv('QTWEBENGINE_DISABLE_SANDBOX', raising=False)
    monkeypatch.setenv('QT_API', 'pyside6')                          # the player's own
    assert main.linux_engine() == 'qt'
    assert os.environ['QTWEBENGINE_DISABLE_SANDBOX'] == '1' and savedata.OUR_VARIABLES == {'QTWEBENGINE_DISABLE_SANDBOX'}
    env = savedata.clean_environment()
    assert 'QTWEBENGINE_DISABLE_SANDBOX' not in env and env['QT_API'] == 'pyside6'


# --- the blank window (0.92.0): a start that never gets its data ends on a message or the simple window ------------

def test_the_start_trace_keeps_the_last_starts(tmp_path):
    from legacy_roster.window import startlog
    for _ in range(startlog.KEEP + 3):
        assert startlog.begin(['--x'])
        startlog.note("the page is loaded", 'loaded')
    with open(startlog.path(), encoding='utf-8') as f:
        text = f.read()
    assert text.count(startlog.HEADER) == startlog.KEEP
    assert text.rstrip().endswith("the page is loaded") and startlog.when('loaded') is not None


class FakeHost:
    def __init__(self, fail_reload=False):
        self.reloaded, self.destroyed, self.fallback = 0, 0, None
        self.window = self
        self.fail_reload = fail_reload

    def get_current_url(self):
        return None if self.fail_reload else 'http://127.0.0.1:1/index.html'

    def load_url(self, url):
        self.reloaded += 1

    def evaluate_js(self, script):
        if self.fail_reload:
            raise RuntimeError('no page')
        self.reloaded += 1

    def destroy(self):
        self.destroyed += 1

    def use_classic(self, reason):
        self.fallback = reason
        self.destroyed += 1


def test_a_page_that_gets_its_data_is_left_alone():
    from legacy_roster.window import startlog, watchdog
    startlog.begin()
    startlog.ready_called.set()
    startlog.ready_done.set()
    host = FakeHost()
    assert watchdog.Watchdog(host, 0.05, 0.05, restart=lambda: 1 / 0).run() == 'ok'
    assert host.reloaded == 0 and host.destroyed == 0 and host.fallback is None


def test_a_page_that_never_asks_is_loaded_again_then_the_program_starts_again_then_the_simple_window_opens():
    from legacy_roster.window import startlog, watchdog
    startlog.begin()
    started = []
    host = FakeHost()
    assert watchdog.Watchdog(host, 0.05, 0.05, restart=lambda: started.append(1) or True, was_retried=False).run() == 'again'
    assert host.reloaded == 1 and started == [1] and host.destroyed == 1 and host.fallback is None
    startlog.begin()
    host = FakeHost()
    assert watchdog.Watchdog(host, 0.05, 0.05, restart=lambda: False, was_retried=False).run() == 'classic'
    assert 'did not ask' in host.fallback
    startlog.begin()
    host = FakeHost(fail_reload=True)                   # the second start also failed: no third try, the simple window
    assert watchdog.Watchdog(host, 0.05, 0.05, restart=lambda: 1 / 0, was_retried=True).run() == 'classic'
    assert host.fallback and host.reloaded == 0
    assert 'threads' in open(startlog.path(), encoding='utf-8').read()


def test_a_page_that_asked_and_got_nothing_goes_to_the_simple_window_without_a_reload():
    from legacy_roster.window import startlog, watchdog
    startlog.begin()
    startlog.ready_called.set()
    host = FakeHost()
    assert watchdog.Watchdog(host, 0.05, 0.05, restart=lambda: 1 / 0).run() == 'classic'
    assert host.reloaded == 0 and 'did not arrive' in host.fallback


def test_a_late_answer_after_the_reload_is_a_start_that_worked():
    import threading
    from legacy_roster.window import startlog, watchdog
    startlog.begin()
    threading.Timer(0.08, startlog.ready_done.set).start()
    host = FakeHost()
    assert watchdog.Watchdog(host, 0.05, 0.5, restart=lambda: 1 / 0).run() == 'reloaded'
    assert host.reloaded == 1 and host.fallback is None


def test_a_start_with_the_graphics_off_that_worked_is_remembered():
    import os
    from legacy_roster.window import startlog, watchdog
    startlog.begin()
    startlog.ready_done.set()
    os.environ.pop(watchdog.BROWSER_ARGS, None)
    try:
        assert watchdog.Watchdog(FakeHost(), 0.05, 0.05, was_retried=True).run() == 'ok'
        watchdog.use_saved()
        assert watchdog.NO_GPU in os.environ[watchdog.BROWSER_ARGS]
    finally:
        os.environ.pop(watchdog.BROWSER_ARGS, None)
        from legacy_roster import datasource
        os.remove(datasource.app_dir(watchdog.NO_GPU_FILE))


def test_the_page_shows_what_failed_instead_of_staying_blue():
    """boot.js is a plain script before every module, the page's two start failures go to it, and Python's reply with
    an error is shown too (before, store.receive dropped it and the window stayed solid blue)."""
    with open(os.path.join(WEB, 'index.html'), encoding='utf-8') as f:
        page = f.read()
    assert page.index('js/boot.js') < page.index('type="module"') and 'id="boot"' in page
    with open(os.path.join(WEB, 'js', 'store.js'), encoding='utf-8') as f:
        assert '__lrFail(message.error)' in f.read()
    with open(os.path.join(WEB, 'js', 'bridge.js'), encoding='utf-8') as f:
        assert 'READY_WAIT' in f.read()
    from legacy_roster.window.api import Api
    assert {'log_js', 'classic', 'open_start_log'} <= {n for n in dir(Api) if not n.startswith('_')}


def test_a_file_the_build_listed_that_is_gone_is_told_at_start(tmp_path, monkeypatch):
    import importlib.util
    from legacy_roster.window import main
    spec = importlib.util.spec_from_file_location('make_manifest', os.path.join(os.path.dirname(WEB), '..', 'packaging', 'make_manifest.py'))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    (tmp_path / 'css').mkdir()
    (tmp_path / 'css' / 'app.css').write_text('x')
    (tmp_path / 'index.html').write_text('x')
    assert tool.write(str(tmp_path)) == ['css/app.css', 'index.html']
    assert 'manifest.txt' not in tool.listing(str(tmp_path))
    real = tool.listing()                                # every real file of the page is listed, none is a stray
    assert 'js/boot.js' in real and all(os.path.exists(os.path.join(WEB, *n.split('/'))) for n in real)
    monkeypatch.setattr(main, 'WEB', str(tmp_path))
    monkeypatch.setattr(main, 'NEEDED', [])
    assert main.missing_files() == []
    os.remove(tmp_path / 'css' / 'app.css')
    assert [os.path.relpath(p, tmp_path) for p in main.missing_files()] == [os.path.join('css', 'app.css')]


def test_the_page_server_of_pywebview_gets_the_roomy_queue():
    """The fix of 0.50.0 reaches the server pywebview really starts (checked on pywebview 6.2.1 in 0.92.0)."""
    import gc
    import time
    import pytest
    webview_http = pytest.importorskip('webview.http')
    from wsgiref.simple_server import WSGIServer
    from legacy_roster.window import main
    was = WSGIServer.request_queue_size
    main.roomy_server()
    try:
        webview_http.BottleServer.start_server([os.path.join(WEB, 'index.html')], None)
        time.sleep(1.0)
        sizes = [o.request_queue_size for o in gc.get_objects() if isinstance(o, WSGIServer)]
        assert sizes and min(sizes) == main.QUEUE
    finally:
        WSGIServer.request_queue_size = was
