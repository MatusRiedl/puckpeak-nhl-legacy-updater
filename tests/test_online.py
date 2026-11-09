"""The Play online tab's controller (app/online.py) on a fake RPCS3 and the fake lobby server (tests/fake_lobby.py).
The roster is the host's: it goes up with his lobby and the friend's PC copies it; each fake PC keeps its online save in `pc`."""
import gzip
import os
import time
import zlib
from types import SimpleNamespace

import pytest

from tests.fake_lobby import server  # noqa: F401  (the fixture)
from legacy_roster import lobby, onlinecfg, patchinstall, savedata
from legacy_roster.app import online

EU = 'BLES02153'
BUILDS = {}                 # RPCS3 folder -> the build number its log would say (the default: 20402)


class FakeHost:
    def __init__(self):
        self.dirty = set()

    def changed(self, name):
        self.dirty.add(name)


def wait(condition, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


def _rpcs3(tmp_path, name='HostPlayer'):
    root = tmp_path / name
    (root / 'config').mkdir(parents=True)
    (root / 'config' / 'rpcn.yml').write_text(f"Version: 2\nNPID: {name}\nPassword: x\n")
    (root / 'config' / 'config.yml').write_text("Net:\n  PSN status: Disconnected\n")
    (root / 'rpcs3.exe').write_bytes(b'')
    return SimpleNamespace(folder=str(root), exe=str(root / 'rpcs3.exe'), plain=False, native=False, savedata=str(root / 'savedata'),
                           flatpak=False, command=lambda: [str(root / 'rpcs3.exe')], launch_dir=lambda: str(root),
                           game_disc=lambda title: 'game.iso' if title == EU else None,
                           game_folder=lambda title: str(root / 'dev_hdd0' / 'game' / title / 'USRDIR'))


def _crc(data):
    return format(zlib.crc32(data), '08x')


def _fake_put(self, rpcs3, title, data):
    self.pc['online'] = data


def _fake_installed(self, rpcs3, title):
    data = self.pc.get('online')
    return None if data is None else dict({'name': 'Puck Peak Online 2026-10-25', 'folder': 'BLES02153021', 'crc': _crc(data)},
                                          **self.pc.get('facts', {}))


def _controller(tmp_path, monkeypatch, name='HostPlayer', ready=True, patched=True, bring=b'roster of the host'):
    """A controller whose PC has the online entry on (unless `ready` is False), the game patch `patched`, and a roster picked
    in Setup whose bytes are `bring`."""
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    rpcs3 = _rpcs3(tmp_path, name)
    state = {'patched': patched, 'online': ready, 'version': '0.26', 'game': '01.00', 'stale': False}
    monkeypatch.setattr(patchinstall, 'state', lambda r: {EU: dict(state)})
    monkeypatch.setattr(patchinstall, 'auto_start', lambda r, t: False)
    monkeypatch.setattr(patchinstall, 'set_switches', lambda *a, **k: [])
    monkeypatch.setattr(onlinecfg, 'roster_crc', _crc)
    monkeypatch.setattr(onlinecfg, 'roster_check', _crc)
    monkeypatch.setattr(onlinecfg, 'rpcs3_build', lambda r: BUILDS.get(r.folder, 20402))
    monkeypatch.setattr(online.OnlineController, '_put_roster', _fake_put)
    monkeypatch.setattr(online.OnlineController, '_installed', _fake_installed)
    monkeypatch.setattr(online.OnlineController, '_address', staticmethod(lambda: '127.0.0.1'))
    sys_data = tmp_path / name / 'picked.sys'
    sys_data.write_bytes(bring)
    slot = SimpleNamespace(title_id=EU, name='Community 2026-27', folder='BLES02153001', sys_data=str(sys_data), disc=False)
    update = SimpleNamespace(rpcs3=rpcs3, versions=[EU], asked=[], ask=lambda *a: update.asked.append(a),
                             selected_slot=lambda: update.slot, usable={}, misfit=lambda s: None, slot=slot)
    ctl = online.OnlineController(FakeHost(), update, poll=0.05, autopoll=False)
    ctl.pc = {}
    ctl.fake_state = state
    BUILDS.pop(rpcs3.folder, None)
    return ctl


def _look(ctl):
    ctl.checked = False
    ctl.follow()
    wait(lambda: ctl.checked and not ctl.busy)


def test_the_tab_says_what_is_missing_in_order(tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch, ready=False)
    ctl.update.rpcs3 = None
    assert ctl.snapshot()['state'] == 'no-rpcs3'
    ctl.update.rpcs3 = _rpcs3(tmp_path / 'x')
    os.remove(os.path.join(ctl.update.rpcs3.folder, 'config', 'rpcn.yml'))
    _look(ctl)
    assert ctl.snapshot()['state'] == 'no-account' and 'Create account' in ctl.snapshot()['no_account']
    ctl.update.rpcs3 = _rpcs3(tmp_path / 'y')
    _look(ctl)
    snap = ctl.snapshot()
    assert snap['account'] == 'HostPlayer' and snap['state'] == 'not-set-up'
    assert snap['marks'] == {'online': False, 'patched': True, 'ready': False, 'game': 'closed'}


def test_a_set_up_pc_is_ready_and_says_which_roster_it_would_bring(tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch)
    _look(ctl)
    snap = ctl.snapshot()
    assert snap['state'] == 'ready' and snap['marks']['ready'] and snap['server'] in (True, False) and snap['build'] == 20402
    assert snap['bring'] == 'Community 2026-27' and snap['bring_why'] is None and snap['roster'] is None
    assert snap['patch'] == '0.26 exact'
    ctl.update.slot = None
    assert ctl.snapshot()['bring_why'] == online.PICK_ROSTER
    ctl.update.slot = SimpleNamespace(name="The game's own roster", folder='disc', disc=True)
    assert ctl.snapshot()['bring_why'] == online.OWN_ROSTER
    ctl.update.slot = SimpleNamespace(name='Old', folder='x', disc=False)
    ctl.update.misfit = lambda s: "This roster was made for the patch."
    assert ctl.snapshot()['bring_why'] == "This roster was made for the patch."


def test_the_patch_word_is_the_version_and_the_maths_or_none(tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch, patched=False)
    _look(ctl)
    assert ctl.snapshot()['patch'] == 'none'
    ctl.fake_state['patched'] = True
    _look(ctl)
    assert ctl.snapshot()['patch'] == '0.26 exact'


def test_setup_is_refused_while_rpcs3_runs_and_without_an_account(tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch, ready=False)
    _look(ctl)
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe')
    ctl.setup()
    assert 'Close RPCS3' in ctl.snapshot()['note']['text'] and not ctl.busy
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    ctl.account = None
    ctl.setup()
    assert 'Create account' in ctl.snapshot()['note']['text']


def test_setup_asks_before_it_patches_and_then_patches_ticks_the_online_entry_and_writes_the_config(tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch, ready=False, patched=False)
    _look(ctl)
    calls = []
    monkeypatch.setattr(patchinstall, 'install_patch', lambda r, titles, **k: calls.append(('patch', titles)))
    monkeypatch.setattr(patchinstall, 'set_online', lambda r, titles, on, **k: calls.append(('online', titles, on)))
    monkeypatch.setattr(patchinstall, 'set_switches', lambda r, titles, intro, login: calls.append(('intro', intro)))
    monkeypatch.setattr(onlinecfg, 'write_config', lambda r, title, address, **k: calls.append(('config', title, address)))
    ctl.setup()
    assert calls == [] and len(ctl.update.asked) == 1 and 'game patch' in ' '.join(ctl.update.asked[0][1])   # the question first
    ctl.update.asked[0][3]['yes']()
    wait(lambda: len(calls) == 4 and not ctl.busy)
    assert calls == [('patch', [EU]), ('online', [EU], True), ('intro', True), ('config', EU, '127.0.0.1')]       # no roster
    assert ctl.pc == {} and ctl.snapshot()['note']['text'] == "Ready to play online."


def test_setup_of_a_patched_game_asks_nothing_and_does_not_patch_again(tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch, ready=False, patched=True)
    _look(ctl)
    calls = []
    monkeypatch.setattr(patchinstall, 'install_patch', lambda *a, **k: calls.append('patch'))
    monkeypatch.setattr(patchinstall, 'set_online', lambda r, titles, on, **k: calls.append('online'))
    monkeypatch.setattr(onlinecfg, 'write_config', lambda r, title, address, **k: calls.append('config'))
    ctl.setup()
    wait(lambda: len(calls) == 2 and not ctl.busy)
    assert calls == ['online', 'config'] and ctl.update.asked == []


def test_online_play_needs_the_game_patch_for_a_lobby_and_for_joining(server, tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch, ready=True, patched=False)
    _look(ctl)
    assert ctl.snapshot()['state'] == 'not-set-up' and ctl.snapshot()['marks']['online'] and not ctl.snapshot()['marks']['ready']
    ctl.create()
    assert ctl.snapshot()['note']['text'] == online.PATCH_NEEDED and not ctl.code
    ctl.join('KDMQRS')
    assert ctl.snapshot()['note']['text'] == online.PATCH_NEEDED and not ctl.code
    assert [c for c in server.calls if 'name=check' not in c[1]] == []


def test_an_rpcs3_older_than_online_play_supports_is_refused_and_a_newer_one_goes_to_the_friend(server, tmp_path, monkeypatch):
    old = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    BUILDS[old.update.rpcs3.folder] = onlinecfg.MIN_RPCS3 - 1
    _look(old)
    old.create()
    snap = old.snapshot()
    assert 'older than online play supports' in snap['note']['text'] and snap['build_old'] and not old.code
    assert [c for c in server.calls if 'name=check' not in c[1]] == []
    BUILDS[old.update.rpcs3.folder] = 20402
    _look(old)
    old.create()
    wait(lambda: old.code)
    assert server.lobbies[old.code]['members'][0]['rpcs3'] == '20402'
    assert old.snapshot()['build_old'] is None and old.snapshot()['build_note'] is None


def test_different_rpcs3_builds_only_get_a_note_and_an_unknown_build_is_not_a_gate(server, tmp_path, monkeypatch):
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    BUILDS[guest.update.rpcs3.folder] = 20393
    guest.pc['online'] = b'roster of the host'
    _look(guest)
    guest.join(host.code)
    wait(lambda: guest.code and not guest.busy)
    note = guest.snapshot()['build_note']
    assert '20402' in note['text'] and '20393' in note['text'] and 'HostPlayer' in note['text']
    assert guest.snapshot()['lobby']['reason'] is None
    host.poll_once()
    assert 'GuestPlayer' in host.snapshot()['build_note']['text']
    BUILDS[guest.update.rpcs3.folder] = None            # RPCS3 was updated and not started since
    _look(guest)
    assert guest.build is None and guest.snapshot()['build_note']['text'] == online.BUILD_UNKNOWN and guest.build_problem() is None
    guest.ready()
    wait(lambda: not guest.busy)
    assert guest.snapshot()['lobby']['members'][1]['ready'] is True


def test_the_host_brings_his_roster_to_his_lobby_and_it_goes_up_for_the_friend(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch)
    _look(host)
    host.create()
    wait(lambda: host.code)
    snap = host.snapshot()
    assert snap['state'] == 'in-lobby' and snap['role'] == 'host' and snap['brought'] == 'Community 2026-27'
    assert snap['roster'] == 'Puck Peak Online 2026-10-25' and host.pc['online'] == b'roster of the host'
    assert snap['lobby']['roster'] == {'crc': _crc(b'roster of the host'), 'size': len(server.lobbies[host.code]['roster'])}
    assert gzip.decompress(server.lobbies[host.code]['roster']) == b'roster of the host'
    assert snap['steps'][0].startswith('The online roster') and 'Create Game Session' in ' '.join(snap['steps'])


def test_the_host_cannot_make_a_lobby_with_a_roster_that_does_not_fit_or_while_rpcs3_runs(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch)
    _look(host)
    host.update.slot = SimpleNamespace(name="The game's own roster", folder='disc', disc=True)
    host.create()
    assert host.snapshot()['note']['text'] == online.OWN_ROSTER and not host.code
    host.update.slot = SimpleNamespace(name='Old', folder='x', disc=False, sys_data='x')
    host.update.misfit = lambda s: "This roster was made for the patch."
    host.create()
    assert 'made for the patch' in host.snapshot()['note']['text'] and not host.code
    host.update.misfit = lambda s: None
    host.update.usable = {'x': "That roster is damaged."}
    host.create()
    assert 'damaged' in host.snapshot()['note']['text'] and not host.code
    host.update.usable = {}
    host.update.slot = SimpleNamespace(name='Community', folder='y', disc=False, sys_data=str(tmp_path / 'HostPlayer' / 'picked.sys'))
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe')
    host.create()
    assert host.snapshot()['note']['text'] == online.CLOSE_TO_BRING and not host.code
    assert [c for c in server.calls if 'name=check' not in c[1]] == [] and host.pc == {}
    ready = _controller(tmp_path / 'z', monkeypatch, ready=False)
    _look(ready)
    ready.create()
    assert 'Set up online first' in ready.snapshot()['note']['text'] and [c for c in server.calls if 'name=check' not in c[1]] == []


def test_a_roster_that_fails_to_go_up_closes_the_lobby_again(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch)
    _look(host)

    def broken(code, name, data):
        raise lobby.LobbyError('too_big', "That roster is too big.")

    monkeypatch.setattr(lobby, 'put_roster', broken)
    host.create()
    wait(lambda: host.snapshot()['note'] and not host.busy)
    assert host.snapshot()['note']['text'] == "That roster is too big." and host.code is None
    assert server.lobbies['KDMQRS']['members'] == []


def test_a_guest_joins_with_no_online_save_and_gets_the_hosts_roster(server, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(savedata, 'launch', lambda args, **kw: launched.append(args))
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    _look(guest)
    assert guest.pc == {}
    guest.join(' ' + host.code.lower() + ' ')
    wait(lambda: guest.pc.get('online') and not guest.busy and not guest.copying)
    assert guest.pc['online'] == b'roster of the host'
    wait(lambda: all(m['roster_ok'] for m in guest.snapshot()['lobby']['members']))
    snap = guest.snapshot()
    assert snap['role'] == 'guest' and snap['lobby']['reason'] is None and snap['roster'] == 'Puck Peak Online 2026-10-25'
    assert 'Browse Available Game Sessions' in ' '.join(snap['steps'])
    assert any(c[1].endswith('/me') for c in server.calls)
    host.ready()
    wait(lambda: not host.busy)
    assert launched == [] and host.snapshot()['state'] == 'in-lobby'
    guest.ready()
    wait(lambda: len(launched) == 1 and not guest.busy)
    assert guest.snapshot()['state'] == 'in-game'
    host.poll_once()                                    # the host's next look sees "starting" too
    wait(lambda: len(launched) == 2)
    assert all(a[:2] == [a[0], '--no-gui'] and a[2] == '--config' and a[-1] == 'game.iso' for a in launched)
    host.poll_once()
    assert len(launched) == 2                           # not started again for the same lobby
    config = open(launched[0][3]).read()
    assert "PSN status: RPCN" in config and "gosredirector.ea.com=127.0.0.1" in config


def test_a_guest_whose_patch_does_not_fit_the_hosts_roster_cannot_press_ready_until_he_patches_again(server, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(savedata, 'launch', lambda args, **kw: launched.append(args))
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    guest.pc['facts'] = {'patch_roster': True, 'rights': 6}          # the host's roster: patch 0.23 or newer
    guest.fake_state['rights'] = 5                                   # the guest's game: an older patch's db files
    _look(guest)
    guest.join(host.code)
    wait(lambda: guest.pc.get('online') and not guest.busy and not guest.copying)
    wait(lambda: guest.snapshot()['guest_problem'])
    snap = guest.snapshot()
    assert snap['guest_problem'] == online.GUEST_RIGHTS and snap['hint'] == online.GUEST_RIGHTS
    guest.ready()
    assert guest.snapshot()['note']['text'] == online.GUEST_RIGHTS
    assert not any(m['ready'] for m in guest.snapshot()['lobby']['members'])
    guest.fake_state['rights'] = 6                                   # Patch again in Game patch
    _look(guest)
    assert guest.snapshot()['guest_problem'] is None
    host.ready()
    wait(lambda: not host.busy)
    guest.ready()
    wait(lambda: len(launched) == 1 and not guest.busy)


def test_the_guest_check_compares_the_roster_itself_with_the_game_as_rpcs3_has_it(tmp_path, monkeypatch):
    guest = _controller(tmp_path, monkeypatch, 'GuestPlayer')
    guest.account = 'GuestPlayer'
    guest.lobby = {'code': 'KDMQRS', 'roster': {'crc': 'aabbccdd', 'size': 9},
                   'members': [{'name': 'HostPlayer', 'role': 'host'}, {'name': 'GuestPlayer', 'role': 'guest'}]}

    def problem(state, **roster):
        guest.state = dict({'patched': True, 'rights': 6, 'stale': False}, **state)
        guest.roster = dict({'name': 'x', 'folder': 'y', 'crc': 'AABBCCDD', 'patch_roster': True, 'rights': 6}, **roster)
        return guest.guest_problem()

    assert problem({}) is None
    assert problem({'patched': False}) == online.GUEST_UNPATCHED
    assert problem({}, patch_roster=False, rights=5) == online.GUEST_PATCHED
    assert problem({'patched': False}, patch_roster=False, rights=5) is None          # a normal roster, a game without the patch
    assert problem({'rights': None}) == online.GUEST_INCOMPLETE                       # rights not readable: not let through
    assert problem({'stale': True}) == online.GUEST_STALE
    assert problem({}, crc='11111111') is None                                        # not the host's roster yet: the copy comes first
    assert problem({}, patch_roster=None) is None                                     # unreadable: the copy's own check said so
    guest.lobby['members'] = [{'name': 'GuestPlayer', 'role': 'host'}]
    assert problem({'patched': False}) is None                                        # the host's own roster: misfit checked it


def test_a_guest_who_already_has_the_hosts_roster_downloads_nothing(server, tmp_path, monkeypatch):
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    guest.pc['online'] = b'roster of the host'
    _look(guest)
    guest.join(host.code)
    wait(lambda: guest.code and not guest.busy)
    assert not any(c[0] == 'GET' and c[1].split('?')[0].endswith('/roster') for c in server.calls)
    assert guest.snapshot()['lobby']['reason'] is None


def test_a_download_that_does_not_match_is_refused_and_not_tried_over_and_over(server, tmp_path, monkeypatch):
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    _look(guest)
    monkeypatch.setattr(lobby, 'get_roster', lambda code, name: b'something else')
    guest.join(host.code)
    wait(lambda: guest.snapshot()['note'] and not guest.copying and not guest.busy)
    assert 'did not arrive correctly' in guest.snapshot()['note']['text'] and guest.pc == {}
    guest.poll_once()
    guest.poll_once()
    assert guest.pc == {} and guest.copy_crc is not None                      # not tried again for the same roster


def test_a_guest_with_rpcs3_open_waits_and_copies_when_it_closes(server, tmp_path, monkeypatch):
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    _look(guest)
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe')
    guest.join(host.code)
    wait(lambda: guest.code and not guest.busy)
    assert guest.snapshot()['note']['text'] == online.CLOSE_TO_COPY and guest.pc == {}
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    guest.poll_once()
    wait(lambda: guest.pc.get('online') and not guest.copying)
    assert guest.pc['online'] == b'roster of the host'


def test_a_different_patch_version_blocks_ready_says_to_update_the_program_and_clears_when_it_is_the_same(server, tmp_path, monkeypatch):
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    guest.fake_state['version'] = '0.25'
    guest.pc['online'] = b'roster of the host'
    _look(guest)
    guest.join(host.code)
    wait(lambda: guest.code and not guest.busy)
    snap = guest.snapshot()
    assert not snap['lobby']['members'][1]['patch_ok'] and 'update the program' in snap['lobby']['reason']
    assert snap['hint'] == online.PATCH_HINT
    host.ready()
    guest.ready()
    wait(lambda: not guest.busy and not host.busy)
    assert guest.snapshot()['lobby']['state'] == 'open'
    guest.fake_state['version'] = '0.26'                # the player updated the program
    _look(guest)
    wait(lambda: guest.snapshot()['lobby'] and guest.snapshot()['lobby']['reason'] is None)
    assert guest.snapshot()['hint'] is None
    assert server.lobbies[host.code]['members'][1]['patch'] == '0.26 exact'


def test_the_host_leaving_closes_the_lobby_for_the_friend(server, tmp_path, monkeypatch):
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    guest.pc['online'] = b'roster of the host'
    _look(guest)
    guest.join(host.code)
    wait(lambda: guest.code and not guest.busy)
    host.leave()
    wait(lambda: server.lobbies[guest.code]['state'] == 'expired')
    guest.poll_once()
    snap = guest.snapshot()
    assert snap['state'] == 'ready' and snap['code'] is None and snap['note']['text'] == online.LOBBY_CLOSED


def test_an_open_game_is_not_started_a_second_time(server, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(savedata, 'launch', lambda args, **kw: launched.append(args))
    host = _controller(tmp_path, monkeypatch)
    made = _with_overlay(host, monkeypatch)
    _look(host)
    host.create()
    wait(lambda: host.code)
    crc = _crc(b'roster of the host')
    other = lobby.join(host.code, 'GuestPlayer', crc, host.patch_word(), 'EU 01.00')
    lobby.ready(host.code, 'GuestPlayer', True)
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe')
    host.ready()
    wait(lambda: host.snapshot()['state'] == 'in-game')
    assert launched == [] and 'Your game is open' in host.snapshot()['note']['text'] and other['members']
    assert host.watching and host.started_at and host.ended is None      # followed all the same: result window, overlay
    assert made and made[0].started


def test_a_lobby_the_server_forgot_is_dropped_with_a_word(server, tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch)
    _look(ctl)
    ctl.create()
    wait(lambda: ctl.code)
    server.lobbies.clear()
    ctl.poll_once()
    snap = ctl.snapshot()
    assert snap['state'] == 'ready' and snap['code'] is None and 'No lobby has that code' in snap['note']['text']
    ctl.join('abc')
    assert 'six letters' in ctl.snapshot()['note']['text']


def test_the_server_not_answering_keeps_the_lobby(server, tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch)
    _look(ctl)
    ctl.create()
    wait(lambda: ctl.code)
    monkeypatch.setenv('LEGACY_ROSTER_ONLINE_URL', 'http://127.0.0.1:9/api')
    ctl.poll_once()
    assert ctl.snapshot()['code'] and ctl.snapshot()['server'] is False


def test_the_games_log_turns_a_failed_sign_in_into_words(tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch)
    _look(ctl)
    ctl.lobby, ctl.code, ctl.launched = {'state': 'starting', 'members': []}, 'KDMQRS', 'KDMQRS'
    log = os.path.join(ctl.update.rpcs3.folder, 'log')
    os.makedirs(log)
    with open(os.path.join(log, 'RPCS3.log'), 'w') as f:
        f.write("RPCS3 v1\nrpcn: You are now logged in RPCN(HostPlayer | HostPlayer)!\n"
                "rpcn: Failed to get a reply from RPCN signaling\n")
    ctl._read_log()
    assert ctl.snapshot()['state'] == 'failed' and 'RPCN did not answer' in ctl.snapshot()['why']


def test_leaving_tells_the_server_and_the_window_closing_does_too(server, tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch)
    _look(ctl)
    ctl.create()
    wait(lambda: ctl.code)
    code = ctl.code
    ctl.leave()
    wait(lambda: any(c[1].endswith('/leave') for c in server.calls))
    assert ctl.snapshot()['state'] == 'ready' and server.lobbies[code]['members'] == []
    ctl.create()
    wait(lambda: ctl.code)
    assert ctl.closing() is True and server.lobbies['KDMQRS']['members'] == []


def test_the_online_roster_is_the_oldest_one_the_game_finds_after_its_settings_save(tmp_path):
    """Lab round 47a: the game boots the oldest roster written since its last boot; the settings save is rewritten after
    every boot, so the online save is put one second after it."""
    for name, age in (('BLES021531300', 100), ('BLES02153020', 500), ('BLES02153021', 5), ('BLES02153022', 50)):
        folder = tmp_path / name
        folder.mkdir()
        os.utime(folder, (time.time() - age, time.time() - age))
    assert savedata.boot_first(str(tmp_path), 'BLES02153021') is True
    settings = os.path.getmtime(tmp_path / 'BLES021531300')
    assert os.path.getmtime(tmp_path / 'BLES02153021') == pytest.approx(settings + 1, abs=0.01)
    assert not savedata.boot_first(str(tmp_path), 'BLES02153099')          # not there
    assert not savedata.boot_first(str(tmp_path), 'BLUS31540021')          # no settings save for that version


def test_a_public_lobby_shows_in_a_friends_list_and_is_joined_from_it(server, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(savedata, 'launch', lambda args, **kw: launched.append(args))
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    assert host.snapshot()['public'] is True            # public unless the host picks private (0.65)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    _look(guest)
    guest.shown = True
    guest.list_once()
    rows = guest.snapshot()['open']
    assert [r['code'] for r in rows] == [host.code] and rows[0]['host'] == 'HostPlayer' and rows[0]['joinable'] and rows[0]['why'] is None
    assert rows[0]['roster_name'] == 'Community 2026-27'
    guest.join(rows[0]['code'])
    wait(lambda: guest.code and not guest.busy)
    assert guest.snapshot()['role'] == 'guest'
    guest.list_once()                                   # a lobby is open: the list is not asked for again
    assert [c for c in server.calls if c[1].endswith('/lobbies')] == [('GET', '/api/lobbies')] * 1


def test_a_private_lobby_is_not_listed(server, tmp_path, monkeypatch):
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.set_public(False)
    host.create()
    wait(lambda: host.code)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    _look(guest)
    guest.shown = True
    guest.list_once()
    assert guest.snapshot()['open'] == [] and guest.snapshot()['open_error'] is None


def test_a_listed_lobby_of_another_patch_version_cannot_be_joined_and_another_game_only_warns(server, tmp_path, monkeypatch):
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    _look(guest)
    guest.open_lobbies = [
        {'code': 'KDMQRS', 'host': 'A', 'roster_name': 'r', 'patch': '0.25', 'version': 'EU 01.00', 'roster_size': 1, 'age_seconds': 1, 'members': 1, 'max': 2},
        {'code': 'TWXYZA', 'host': 'B', 'roster_name': 'r', 'patch': guest.patch_word(), 'version': 'EU 01.01', 'roster_size': 1, 'age_seconds': 1, 'members': 1, 'max': 2},
        {'code': 'QWERTY', 'host': 'C', 'roster_name': 'r', 'patch': guest.patch_word(), 'version': 'EU 01.00', 'roster_size': 1, 'age_seconds': 1, 'members': 1, 'max': 2}]
    patch_row, version_row, same_row = guest.rows()
    assert patch_row['joinable'] is False and 'Update the program' in patch_row['why']
    assert version_row['joinable'] is True and version_row['why'] is None
    assert 'EU 01.01' in version_row['warn'] and 'EU 01.00' in version_row['warn']
    assert same_row['joinable'] is True and same_row['why'] is None and 'warn' not in same_row


def test_the_lobby_card_warns_when_the_friend_plays_another_game(server, tmp_path, monkeypatch):
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    _look(guest)
    mine = guest.game_word()
    guest.lobby = {'members': [{'name': 'GuestPlayer', 'version': mine}, {'name': 'HostPlayer', 'version': 'NA 01.00' if mine != 'NA 01.00' else 'EU 01.00'}]}
    note = guest.snapshot()['game_note']
    assert note['tone'] == 'warn' and 'HostPlayer' in note['text'] and 'lose step' in note['text']
    guest.lobby['members'][1]['version'] = mine
    assert guest.snapshot()['game_note'] is None


def test_the_list_says_when_the_server_cannot_be_reached(tmp_path, monkeypatch):
    monkeypatch.setenv('LEGACY_ROSTER_ONLINE_URL', 'http://127.0.0.1:9/api')
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    _look(guest)
    guest.shown = True
    guest.list_once()
    assert 'not reachable' in guest.snapshot()['open_error']


def test_a_start_by_itself_ticks_the_start_entry_for_one_launch_and_unticks_it_after_the_boot(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch)
    ticks = []
    monkeypatch.setattr(patchinstall, 'auto_start', lambda r, t: True)
    monkeypatch.setattr(patchinstall, 'set_online_start', lambda r, titles, on: ticks.append((titles, on)))
    launched = []
    monkeypatch.setattr(savedata, 'launch', lambda args, **kw: launched.append(args))
    monkeypatch.setattr(savedata, 'boot_first', lambda *a: None)
    monkeypatch.setattr(onlinecfg, 'launch_args', lambda r, t, c: ['rpcs3', '--no-gui'])
    host.auto = True
    assert host.steps('host') == [online.BY_ITSELF]
    host.roster = {'name': 'Puck Peak Online', 'folder': 'BLES02153011', 'crc': 'aabbccdd'}
    assert host.steps('host') == [online.LOAD_ROSTER.format(name='Puck Peak Online'), online.BY_ITSELF]
    host.code, host.title = 'ABCDEF', EU
    host._start_game()
    assert launched and ticks == [([EU], True)] and host.by_itself
    log = os.path.join(host.rpcs3().folder, 'log', 'RPCS3.log')
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, 'w') as f:
        f.write('RPCS3 v0.0.1\nrpcn: You are now logged in RPCN(HostPlayer | x)\n')
    os.utime(log, (host.started_at - 3600, host.started_at - 3600))
    host._read_log()                                    # the last session's log: nothing is believed, nothing unticked
    assert ticks == [([EU], True)] and host.by_itself and host.log is None
    os.utime(log, (host.started_at + 5, host.started_at + 5))      # this session's log (a fixed time: the file system's clock is coarse)
    host._read_log()
    assert ticks[-1] == ([EU], False) and not host.by_itself


def test_a_tick_left_by_a_closed_program_is_taken_off_at_the_next_look_and_when_leaving(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch)
    ticks = []
    monkeypatch.setattr(patchinstall, 'set_online_start', lambda r, titles, on: ticks.append((tuple(titles), on)))
    _look(host)                                         # a fresh program: it never ticked anything, the entry may still be ticked
    assert ticks and all(not on for _, on in ticks)
    ticks.clear()
    host.leave()
    assert ticks == [((EU,), False)]
    ticks.clear()
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe')
    host.leave()                                        # not while RPCS3 runs: the game may be reading it
    assert ticks == []


def test_without_the_start_entry_the_steps_are_pressed_by_hand_and_nothing_is_ticked(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch)
    ticks = []
    monkeypatch.setattr(patchinstall, 'set_online_start', lambda r, titles, on: ticks.append(on))
    monkeypatch.setattr(savedata, 'launch', lambda args, **kw: None)
    monkeypatch.setattr(savedata, 'boot_first', lambda *a: None)
    monkeypatch.setattr(onlinecfg, 'launch_args', lambda r, t, c: ['rpcs3'])
    assert len(host.steps('guest')) > 1
    host.code, host.title = 'ABCDEF', EU
    host._start_game()
    assert ticks == [] and not host.by_itself


def test_a_game_that_stays_signed_in_on_a_menu_gets_the_steps_to_press_by_hand(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch)
    host.auto, host.launched, host.signed_at = True, 'ABCDEF', None
    member = {'name': host.account, 'role': 'host', 'progress': 'signed_in'}
    monkeypatch.setattr(host, '_member', lambda: member)
    assert not host.stalled() and host.steps('host') == [online.BY_ITSELF]
    host.signed_at = time.time() - 10
    assert not host.stalled()                                           # signed in a moment ago: the game is on its way
    host.signed_at = time.time() - online.STALL_AFTER - 5
    assert host.stalled()
    steps = host.steps('host')
    assert steps[:2] == [online.BY_ITSELF, online.STALLED] and 'Create Game Session' in ' '.join(steps)
    assert 'Browse Available Game Sessions' in ' '.join(host.steps('guest'))
    member['progress'] = 'hosting'                                      # the session is made: nothing to press
    assert not host.stalled() and host.steps('host') == [online.BY_ITSELF]


def test_the_games_own_roster_says_what_to_do_instead(tmp_path, monkeypatch):
    assert 'Update tab' in online.OWN_ROSTER and 'Setup' in online.OWN_ROSTER



def test_the_installed_online_roster_says_what_game_it_was_made_for(tmp_path, base_dir, monkeypatch):
    with open(os.path.join(base_dir, 'SYS-DATA'), 'rb') as f:
        data = f.read()
    sys_data = tmp_path / 'SYS-DATA'
    sys_data.write_bytes(data)
    slot = SimpleNamespace(title_id=EU, name='Puck Peak Online', folder='BLES02153021', sys_data=str(sys_data))
    monkeypatch.setattr(savedata, 'list_rosters', lambda where: [slot])
    found = online.OnlineController._installed(None, SimpleNamespace(savedata=str(tmp_path)), EU)
    assert found['crc'] == onlinecfg.roster_crc(data) and found['patch_roster'] is False and found['rights'] == 5


def _pair(server, tmp_path, monkeypatch):
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code and not host.busy)
    guest = _controller(tmp_path / 'b', monkeypatch, 'GuestPlayer')
    guest.pc['online'] = b'roster of the host'
    _look(guest)
    guest.join(host.code)
    wait(lambda: guest.code and not guest.busy)
    return host, guest


def _ranks(ctl, **kw):
    ctl.refresh_ranks(**kw)
    wait(lambda: not ctl._ranks_busy)


def test_chat_lines_go_both_ways_and_a_second_line_at_once_only_waits(server, tmp_path, monkeypatch):
    host, guest = _pair(server, tmp_path, monkeypatch)
    assert host.snapshot()['chat'] == [] and host.snapshot()['phrases'][0] == "Good game"
    host.say('  gg  ')
    wait(lambda: host.snapshot()['chat'])
    assert host.snapshot()['chat'][0]['mine'] and host.snapshot()['chat_wait']
    host.say('again at once')                           # the Send button rests: nothing sent, no red line
    guest.poll_once()
    lines = guest.snapshot()['chat']
    assert [(c['name'], c['text'], c['mine']) for c in lines] == [('HostPlayer', 'gg', False)] and host.snapshot()['note'] is None


def test_a_server_from_before_the_ranks_hides_chat_and_ranks_and_the_lobby_works_as_before(server, tmp_path, monkeypatch):
    server.ranks = False
    host, guest = _pair(server, tmp_path, monkeypatch)
    _ranks(host, board=True)
    snap = host.snapshot()
    assert snap['chat'] is None and snap['ranks'] is None and host.ranks_on is False and snap['note'] is None
    host.say('gg')                                      # no chat on that server: nothing is sent
    assert not any(c[1].endswith('/say') for c in server.calls)
    host.ready()
    wait(lambda: not host.busy)
    guest.ready()
    wait(lambda: guest.snapshot()['lobby']['state'] == 'starting')


def test_my_card_matches_and_the_board_come_from_the_server(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch, 'HostPlayer')
    _look(host)
    assert host.snapshot()['ranks'] is None                       # nothing read yet
    for _ in range(5):
        server.play('HostPlayer', 'Bo', 3, 1)
    server.play('Cy', 'Bo', 2, 1)
    _ranks(host, board=True)
    view = host.snapshot()['ranks']
    assert (view['card']['rating'], view['card']['tier'], len(view['history'])) == (1080, 'Rookie', 5)
    assert [r['name'] for r in view['top']] == ['HostPlayer', 'Bo', 'Cy'] and view['me'] is None
    # the rating card's bar runs from the tier's low end to the next tier
    assert view['tiers'] and all(set(t) == {'name', 'min'} for t in view['tiers'])
    assert any(t['name'] == 'Rookie' for t in view['tiers'])


def test_the_result_of_the_new_match_shows_once_and_follows_the_second_report(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch, 'HostPlayer')
    _look(host)
    server.play('HostPlayer', 'Bo', 1, 0)                         # an older match: not "the result"
    host.watching, host.baseline, host.started_at = True, online.PENDING, time.time()
    _ranks(host)
    assert host.snapshot()['result'] is None
    mid = server.play('HostPlayer', 'GuestPlayer', 3, 2, status='waiting')
    _ranks(host)
    res = host.snapshot()['result']
    assert res['line'] == online.RESULT_WAITING.format(opp='GuestPlayer') and res['delta'] is None
    server.settle('HostPlayer', mid)
    server.players['hostplayer']['rating'] += 16                  # the stand-in rates it now
    for row in server.matches['hostplayer']:
        if row['id'] == mid:
            row['delta'] = 16
    _ranks(host)
    res = host.snapshot()['result']
    assert (res['line'], res['before'], res['rating'], res['for'], res['against']) == (online.RESULT_WON, 1016, 1032, 3, 2)
    host.result_seen()
    _ranks(host)
    assert host.snapshot()['result'] is None


def test_a_box_score_shows_my_side_first_and_its_lines(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch, 'HostPlayer')
    _look(host)
    first = server.play('Bo', 'HostPlayer', 4, 2, team_a='BOS', team_b='TOR')
    newest = server.play('HostPlayer', 'Bo', 3, 1, stats={'HostPlayer': {'SHTS': 31, 'TOA': 754, 'PPG': 1, 'PPO': 4},
                                                          'Bo': {'SHTS': 22, 'HITS': 9}})
    _ranks(host)
    host.set_ranks_tab('box')                                   # the newest match by default
    wait(lambda: newest in host.boxes)
    box = host.snapshot()['ranks']['box']
    assert box['id'] == newest and box['newer'] is None and box['older'] == first and box['title'].startswith('vs Bo')
    assert [(x['name'], x['team'], x['score']) for x in box['sides']] == [('HostPlayer', 'MTL', 3), ('Bo', 'TOR', 1)]
    assert [(r['label'], r['me'], r['them']) for r in box['rows']] == [
        ('Shots', '31', '22'), ('Hits', '0', '9'), ('Power play', '1/4', '0/0'), ('Time on attack', '12:34', '0:00')]
    host.open_box(first)                                        # the older match: I was the away side
    wait(lambda: first in host.boxes)
    box = host.snapshot()['ranks']['box']
    assert [x['name'] for x in box['sides']] == ['HostPlayer', 'Bo'] and box['sides'][0]['score'] == 2
    assert box['rows'] == [] and box['note'] == online.BOX_EMPTY
    reads = sum(1 for c in server.calls if '/match' in c[1])
    host.open_box(first)                                        # read once per status
    assert sum(1 for c in server.calls if '/match' in c[1]) == reads
    reads = sum(1 for c in server.calls if '/match' in c[1])
    host.open_box('B9/9')                                       # not one of my matches: the newest shows, read before
    assert host.snapshot()['ranks']['box']['id'] == newest and sum(1 for c in server.calls if '/match' in c[1]) == reads


def test_the_box_score_picked_before_my_matches_came_is_read_when_they_come(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch, 'HostPlayer')
    _look(host)
    host.set_ranks_tab('box')
    assert host.box_view()['id'] is None
    mid = server.play('HostPlayer', 'Bo', 3, 1)
    _ranks(host)
    wait(lambda: mid in host.boxes)
    box = host.box_view()
    assert box['id'] == mid and not box['loading'] and box['sides'][0]['name'] == 'HostPlayer'


def test_a_server_without_box_scores_keeps_the_rest_of_the_ranks(server, tmp_path, monkeypatch):
    server.box_route = False
    host = _controller(tmp_path, monkeypatch, 'HostPlayer')
    _look(host)
    mid = server.play('HostPlayer', 'Bo', 3, 1)
    _ranks(host)
    host.open_box(mid)
    wait(lambda: not host.box_on)
    view = host.snapshot()['ranks']
    assert host.ranks_on and len(view['history']) == 1 and view['box'] == {'on': False, 'note': online.BOX_LATER}


def test_box_lines_and_my_stats():
    assert online.box_lines({}, {}) == []
    assert online.box_lines({'TOA': 65, 'BAG': 0, 'BAO': 2}, {'FO': 7}) == [
        {'label': 'Faceoffs won', 'me': '0', 'them': '7'}, {'label': 'Time on attack', 'me': '1:05', 'them': '0:00'},
        {'label': 'Breakaways', 'me': '0/2', 'them': '0/0'}]
    assert online.stats_view(None) == {'note': online.STATS_NONE}
    st = online.stats_view({'w': 7, 'l': 3, 'streak': -2, 'rating': 1040, 'peak': 1072, 'gf': 30, 'ga': 21, 'delta7': -12,
                            'form': 'WWL', 'curve': [[1, 1000], [2, 1016], 'bad'], 'teams': [{'name': 'MTL', 'w': 7, 'l': 3}]})
    assert [(t['label'], t['value'], t['sub']) for t in st['tiles']] == [
        ('Record', '7-3', '70 % won'), ('Streak', 'L2', 'in a row'), ('Best rating', '1072', 'now 1040'),
        ('Goals', '30-21', '+9 difference'), ('Last 7 days', '-12', 'rating')]
    assert st['form'] == ['W', 'W', 'L'] and st['curve'] == [1000, 1016] and st['opponents'] == [] and st['teams'][0]['w'] == 7


def test_rpcs3_closing_ends_the_game_view_and_the_watch_ends_with_a_final_result(tmp_path, monkeypatch):
    ctl = _controller(tmp_path, monkeypatch, 'HostPlayer')
    ctl.account, ctl.launched, ctl.watching = 'HostPlayer', 'KDMQRS', True
    ctl.lobby = {'code': 'KDMQRS', 'state': 'starting', 'members': [{'name': 'HostPlayer', 'role': 'host'}]}
    ctl.state = {'patched': True, 'online': True}
    ctl.started_at = time.time()
    ctl._watch_game()
    assert ctl.ended is None and ctl.view() == 'in-game'                     # RPCS3 is still starting
    ctl.started_at = time.time() - online.START_GRACE_RANKS - 1
    ctl._watch_game()
    assert ctl.ended and ctl.view() != 'in-game' and ctl.watching           # the result may still come
    ctl.result = {'id': 'B1/2', 'status': 'confirmed'}
    ctl._watch_game()
    assert not ctl.watching and ctl.launched == 'KDMQRS'                    # still no second start for this lobby


def test_hiding_from_the_board_is_kept_and_showing_again_waits_for_a_lobby(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch, 'HostPlayer')
    host.update.settings = {}
    _look(host)
    server.play('HostPlayer', 'Bo', 3, 1)
    host.set_hidden(True)
    wait(lambda: 'hostplayer' in server.hidden and not host._ranks_busy)
    assert host.update.settings[online.HIDDEN_KEY] is True and host.snapshot()['ranks']['hidden'] is True
    host.set_hidden(False)
    wait(lambda: host.snapshot()['note'])
    assert host.snapshot()['note']['text'] == online.SHOW_LATER and 'hostplayer' in server.hidden
    host.create()
    wait(lambda: host.code and not host.busy)
    _ranks(host)                                                   # with the lobby's token he sees his own card, marked hidden
    assert host.card['hidden'] is True
    host.poll_once()
    wait(lambda: 'hostplayer' not in server.hidden)


class FakeHud:
    """Stands in for hud.Hud: keeps what the controller told the overlay."""
    def __init__(self, on_hotkey):
        self.on_hotkey, self.chats, self.cards, self.started, self.stopped = on_hotkey, [], [], False, False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def chat(self, who, text, hold=6.0):
        self.chats.append((who, text))

    def result(self, data, hold=9.0):
        self.cards.append(data)


def _with_overlay(ctl, monkeypatch):
    made = []
    monkeypatch.setattr(online.hud, 'available', lambda: True)
    ctl.update.settings = {}
    ctl.make_hud = lambda on_hotkey: made.append(FakeHud(on_hotkey)) or made[-1]
    return made


def test_the_overlay_shows_only_the_friends_new_lines_and_the_hotkeys_send_the_phrases(server, tmp_path, monkeypatch):
    server.chat_gap = 0
    host, guest = _pair(server, tmp_path, monkeypatch)
    made = _with_overlay(guest, monkeypatch)
    host.say('before the game')
    wait(lambda: host.snapshot()['chat'])
    guest.poll_once()                                   # read before the game starts: never shown over it
    guest._hud_start()
    assert made and made[0].started and guest.snapshot()['overlay'] == {'can': True, 'on': True}
    host.chat_wait = 0
    host.say('gg')
    wait(lambda: len(host.snapshot()['chat']) == 2)
    guest.poll_once()
    assert made[0].chats == [('HostPlayer', 'gg')]
    made[0].on_hotkey(0)                                # Ctrl+Shift+F1 in the game
    wait(lambda: any(c.get('text') == online.PHRASES[0] for c in (guest.lobby or {}).get('chat') or []))
    guest.poll_once()
    assert made[0].chats == [('HostPlayer', 'gg')]      # my own line stays in the tab
    guest.set_overlay(False)
    assert made[0].stopped and guest.hud is None and guest.update.settings[online.OVERLAY_KEY] is False
    guest._hud_start()
    assert len(made) == 1                               # switched off: no overlay at the next start


def test_the_overlay_shows_the_result_card_once_when_the_match_is_rated(server, tmp_path, monkeypatch):
    host = _controller(tmp_path, monkeypatch, 'HostPlayer')
    made = _with_overlay(host, monkeypatch)
    _look(host)
    host.watching, host.baseline, host.started_at = True, online.PENDING, time.time()
    host._hud_start()
    _ranks(host)
    mid = server.play('HostPlayer', 'GuestPlayer', 3, 2, status='waiting')
    _ranks(host)
    assert made[0].cards == []                          # waits for the other report: only in the tab
    server.settle('HostPlayer', mid)
    server.players['hostplayer']['rating'] += 16
    for row in server.matches['hostplayer']:
        if row['id'] == mid:
            row['delta'] = 16
    _ranks(host)
    _ranks(host)
    assert len(made[0].cards) == 1
    card = made[0].cards[0]
    assert (card['sub'], card['rating_from'], card['rating_to']) == ('3 - 2 win', 1000, 1016)
    host.ended = time.time() - online.WATCH_AFTER - 1
    host._watch_game()
    assert made[0].stopped and host.hud is None


def test_the_result_card_has_the_bar_a_rank_up_and_placement_games():
    tiers = [{'name': 'Minor League', 'min': 0}, {'name': 'Rookie', 'min': 1000}, {'name': 'Pro', 'min': 1100}]
    view = {'result': 'W', 'for': 4, 'against': 2, 'before': 1089, 'rating': 1112, 'tier': 'Pro', 'next_tier': 'Top 6',
            'next_at': 1200, 'placing': 0, 'status': 'confirmed'}
    card = online.hud_card(view, tiers)
    assert (card['sub'], card['band_low'], card['rank_up']) == ('4 - 2 win', 1100, 'Pro')
    card = online.hud_card(dict(view, result='L', before=1120, rating=1105, status='forfeit'), tiers)
    assert card['sub'] == 'loss, you left' and 'rank_up' not in card
    card = online.hud_card(dict(view, placing=3), tiers)
    assert card['placing'] == 3 and card['placing_of'] == 5 and card['tier'] is None


def _port(tmp_path, monkeypatch, name='PortPlayer', named=True):
    """A controller on NHL Legacy Native (no rpcn.yml, no RPCS3 build), the name typed unless `named` is False."""
    ctl = _controller(tmp_path, monkeypatch, name)
    host = ctl.update.rpcs3
    host.native, host.patchable = True, True
    os.remove(os.path.join(host.folder, 'config', 'rpcn.yml'))
    ctl.update.settings = {online.NAME_KEY: name} if named else {}
    monkeypatch.setattr(onlinecfg, 'rpcs3_build', lambda r: pytest.fail("a port has no RPCS3 log"))
    monkeypatch.setattr(onlinecfg, 'write_config', lambda *a, **k: pytest.fail("a port has no RPCS3 config"))
    return ctl


def test_a_player_on_the_port_types_a_name(tmp_path, monkeypatch):
    ctl = _port(tmp_path, monkeypatch, named=False)
    _look(ctl)
    snap = ctl.snapshot()
    assert snap['native'] and snap['state'] == 'no-account' and snap['no_account'] == online.NAME_ASK and snap['build_note'] is None
    ctl.set_name('a b')
    assert ctl.snapshot()['state'] == 'no-account' and ctl.snapshot()['note']['text'] == online.BAD_NAME
    ctl.set_name(' Port-Player_1 ')
    assert ctl.snapshot()['state'] == 'ready' and ctl.snapshot()['note'] is None
    assert ctl.update.settings[online.NAME_KEY] == 'Port-Player_1'
    _look(ctl)
    assert ctl.account == 'Port-Player_1'


def test_a_name_stays_while_in_a_lobby(server, tmp_path, monkeypatch):
    ctl = _port(tmp_path, monkeypatch)
    _look(ctl)
    ctl.create()
    wait(lambda: ctl.code)
    ctl.set_name('OtherName')
    assert ctl.account == 'PortPlayer'


def test_a_port_our_patch_does_not_fit_cannot_go_online(tmp_path, monkeypatch):
    ctl = _port(tmp_path, monkeypatch)
    ctl.update.rpcs3.patchable = False
    assert ctl.snapshot()['state'] == 'no-rpcs3' and ctl.snapshot()['no_rpcs3'] == online.X.ONLINE_NATIVE


def test_a_lobby_starts_the_port_with_everything_it_needs(server, tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(savedata, 'launch', lambda args, **kw: started.append((args, kw)))
    monkeypatch.setattr(savedata, 'WINDOWS', True)
    host = _controller(tmp_path / 'a', monkeypatch, 'HostPlayer')
    _look(host)
    host.create()
    wait(lambda: host.code)
    guest = _port(tmp_path / 'b', monkeypatch)
    monkeypatch.setattr(patchinstall, 'auto_start', lambda r, t: r is guest.update.rpcs3)
    _look(guest)
    guest.join(host.code)
    wait(lambda: guest.pc.get('online') and not guest.busy and not guest.copying)
    host.ready()
    wait(lambda: not host.busy)
    guest.ready()
    wait(lambda: started and not guest.busy)
    args, kw = started[0]
    assert args == [guest.update.rpcs3.exe, '--username', 'PortPlayer'] and kw['cwd'] == guest.update.rpcs3.folder
    env = kw['env']
    assert env['NHL_PUCKPEAK_ONLINE'] == '127.0.0.1' and env['PS3_NP_ONLINE_ID'] == 'PortPlayer' and env['NHL_SKIP_INTRO'] == '1'
    assert env['NHL_PUCKPEAK_ROSTER'] == 'BLES02153021' and env['NHL_PUCKPEAK_START'] == '1'
    assert online.PORT_BY_ITSELF in guest.steps('guest') and online.BY_ITSELF not in guest.steps('guest')
    assert guest.signed_at > time.time()                            # the port has no log: the sign-in is counted from its boot
