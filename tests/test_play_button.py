"""The header's Play NHL Legacy and the Puck Peak apps (0.98.1)."""
from types import SimpleNamespace

from legacy_roster.app import texts as X
from legacy_roster.app.update import UpdateController


class FakeHost(SimpleNamespace):
    def __init__(self, native=False, discs=None, command=('rpcs3.exe',)):
        super().__init__(native=native, plain=False, name='RPCS3', _discs=discs or {}, _command=list(command))

    def command(self):
        return self._command

    def games(self):
        return list(self._discs)

    def game_disc(self, title):
        return self._discs.get(title)


def test_play_boots_the_picked_rosters_game_in_rpcs3():
    host = FakeHost(discs={'BLES01530': 'eu.iso', 'BLUS31540': 'na.iso'})
    play = UpdateController._play_command
    assert play(None, host, SimpleNamespace(title_id='BLUS31540')) == ['rpcs3.exe', 'na.iso']
    assert play(None, host, None) == ['rpcs3.exe', 'eu.iso']                 # no roster picked: the first game
    assert play(None, FakeHost(), None) == ['rpcs3.exe']                      # RPCS3 does not say where the game is
    assert play(None, FakeHost(command=()), None) is None


def test_play_opens_the_ports_launcher():
    host = FakeHost(native=True, discs={'BLUS31540': 'folder'}, command=('NHLLauncher.exe',))
    assert UpdateController._play_command(None, host, None) == ['NHLLauncher.exe']


def test_play_is_grey_with_a_reason_until_the_game_is_found():
    view = UpdateController._play_view
    none = view(SimpleNamespace(rpcs3=None, busy=False), False)
    assert not none['can'] and 'Setup' in none['why'] and none['text'] == X.PLAY
    ready = view(SimpleNamespace(rpcs3=FakeHost(), busy=False), False)
    assert ready['can']
    assert not view(SimpleNamespace(rpcs3=FakeHost(), busy=True), False)['can']
    assert not view(SimpleNamespace(rpcs3=FakeHost(), busy=False), True)['can']


def test_only_the_two_other_apps_open():
    assert set(X.SISTER_APPS) == {'overtime', 'faceoff'}
    assert all(url.startswith('https://github.com/MatusRiedl/') for url in X.SISTER_APPS.values())


def test_this_program_says_up_to_date_only_when_github_answered(monkeypatch):
    from legacy_roster.app import selfupdate
    calls = iter([RuntimeError('offline'), {'tag_name': 'v0.0.1'}])

    def fetch(url):
        got = next(calls)
        if isinstance(got, Exception):
            raise got
        return got
    assert selfupdate.latest(fetch_json=fetch, fetch_text=lambda url: '') is None and selfupdate.answered is False
    selfupdate.latest(fetch_json=fetch, fetch_text=lambda url: '')
    assert selfupdate.answered is True
    view = UpdateController._program_view
    assert view(SimpleNamespace(newest=None)) is None
    assert view(SimpleNamespace(newest='newest')) == {'tone': 'good', 'text': "Up to date"}
    assert view(SimpleNamespace(newest='0.99.0'))['tone'] == 'caution'
