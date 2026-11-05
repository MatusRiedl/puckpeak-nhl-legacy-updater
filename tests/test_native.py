"""NHL Legacy Native, the PC port, as a second place for the program to work in (savedata.Native, native.py)."""
import json
import os
import shutil
import struct
import subprocess
import zipfile

import pytest

from legacy_roster import native, packs, patchinstall, pipeline, savedata
from legacy_roster.art import install

INI = """[paths]
eboot = data/eboot.elf
disc = game
hdd0 = data/hdd0
hdd1 = data/hdd1
user = user
[video]
[launcher]
game_source = D:\\somewhere\\game.iso
"""


def fake_native(root, ini=INI):
    """A pretend install of the port: the launcher's Install done, no save yet."""
    root.mkdir(parents=True, exist_ok=True)
    for name in ('NHLLegacy.exe', 'NHLLauncher.exe'):
        (root / name).write_bytes(b'MZ')
    (root / 'nhl_settings.ini').write_text(ini, encoding='utf-8', newline='')
    (root / 'data' / 'update' / 'USRDIR').mkdir(parents=True)
    (root / 'data' / 'eboot.elf').write_bytes(b'\x7fELF')
    (root / 'game' / 'PS3_GAME').mkdir(parents=True)
    (root / 'user').mkdir()
    return root


@pytest.fixture
def port(tmp_path):
    yield fake_native(tmp_path / 'Native')
    install.use_host(None)


@pytest.mark.parametrize('pick', ['NHLLauncher.exe', 'NHLLegacy.exe', '.', 'user', 'data/update'])
def test_the_port_is_found_from_its_programs_and_folders(port, pick):
    found = savedata.find_rpcs3(str(port / pick))
    assert found.native and not found.plain and not found.patchable
    assert found.folder == str(port) and found.where == str(port / 'NHLLauncher.exe')
    assert found.savedata == str(port / 'user' / 'gamedata' / 'dev_hdd0' / 'home' / '00000001' / 'savedata')
    assert found.game_folder('BLUS31540') == str(port / 'mods' / 'Puck Peak' / 'USRDIR')
    assert found.game_disc('BLUS31540') == str(port / 'game') and found.game_disc('BLES02153') is None
    assert found.games() == ['BLUS31540'] and [s.title_id for s in found.disc_slots()] == ['BLUS31540']


def test_the_folder_the_zip_made_is_enough(port):
    assert savedata.find_rpcs3(str(port.parent)).folder == str(port)


def test_a_full_path_in_the_ini_is_followed(tmp_path):
    disc, user = tmp_path / 'my game', tmp_path / 'my saves'
    (disc / 'PS3_GAME').mkdir(parents=True)
    user.mkdir()
    port = fake_native(tmp_path / 'Native', INI.replace('disc = game', f'disc = {disc}').replace('user = user', f'user = {user}'))
    shutil.rmtree(port / 'game')
    found = savedata.find_rpcs3(str(port))
    assert found.game_disc('BLUS31540') == str(disc)
    assert found.savedata.startswith(str(user))


def test_an_install_that_is_not_finished_says_what_to_do(port):
    os.remove(port / 'data' / 'eboot.elf')
    with pytest.raises(savedata.Rpcs3Error, match='press Install'):
        savedata.find_rpcs3(str(port))


def test_an_rpcs3_folder_stays_rpcs3(tmp_path):
    (tmp_path / 'rpcs3.exe').write_bytes(b'MZ')
    (tmp_path / 'games').mkdir()
    with pytest.raises(savedata.NoGameError):
        savedata.find_rpcs3(str(tmp_path / 'rpcs3.exe'))


def test_the_port_takes_no_game_patch(port):
    found = savedata.find_rpcs3(str(port))
    assert patchinstall.patched_titles(found) == [] and patchinstall.stale_titles(found) == []
    assert patchinstall.installed(found) is False
    with pytest.raises(patchinstall.PatchError, match='NHL Legacy Native'):
        patchinstall.check(found, ['BLUS31540'])
    with pytest.raises(patchinstall.PatchError, match='NHL Legacy Native'):
        patchinstall.set_online(found, ['BLUS31540'], True)


def test_a_running_game_of_the_port_is_named(monkeypatch):
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: r'D:\game\NHLLegacy.exe')
    assert savedata.close_first() == "Close NHL Legacy first"
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: r'D:\game\rpcs3.exe')
    assert savedata.close_first() == "Close RPCS3 first"


def test_each_game_keeps_its_own_list_of_pictures(port, tmp_path):
    rpcs3 = savedata.Rpcs3(str(tmp_path / 'r' / 'rpcs3.exe'), 'x', '00000001')
    found = savedata.find_rpcs3(str(port))
    install.use_host(found)
    writer = install._Writer([found.game_folder('BLUS31540')])
    writer.write(('fe', 'loc', 'nhl_en.db'), b'text', 'names:one')
    writer.save()
    assert installed_here(found) == 1
    assert os.path.isfile(port / 'mods' / 'Puck Peak' / 'USRDIR' / 'fe' / 'loc' / 'nhl_en.db')
    install.use_host(rpcs3)
    assert installed_here(found) == 0
    assert not install.load_manifest()['games']       # RPCS3's list never hears of the port
    install.use_host(found)
    assert installed_here(found) == 1


def installed_here(host):
    return sum(len(files) for files in install.load_manifest()['games'].values())


def test_nothing_goes_into_the_ports_data_folder(port):
    found = savedata.find_rpcs3(str(port))
    assert found.holds(found.game_folder('BLUS31540'))
    assert not found.game_folder('BLUS31540').startswith(str(port / 'data'))
    assert not found.savedata.startswith(str(port / 'data'))


def test_the_update_s_texts_are_read_from_the_port(port, monkeypatch):
    found = savedata.find_rpcs3(str(port))
    seen = []
    real = os.path.isfile
    monkeypatch.setattr(install.os.path, 'isfile', lambda p: seen.append(p) or real(p))
    install.use_host(found)
    assert install.update_texts([found.game_folder('BLUS31540')]) == {}
    assert str(port / 'data' / 'update' / 'USRDIR' / 'patch.big') in seen


def lines(port):
    return (port / 'nhl_settings.ini').read_bytes().decode().split('\r\n')


def test_our_mod_goes_first_only_when_another_mod_could_cover_it(port):
    found = savedata.find_rpcs3(str(port))
    (port / 'mods' / 'Puck Peak').mkdir(parents=True)
    assert native.first_in_order(found) is False
    (port / 'mods' / 'Imported from update folder').mkdir()
    assert native.first_in_order(found) is True
    assert native.order_of(found) == ['Puck Peak']
    assert native.first_in_order(found) is False


def test_the_order_keeps_the_players_mods_and_the_rest_of_the_ini(tmp_path):
    ini = '[paths]\r\nuser = user\r\n[launcher]\r\nmod_order = Big Mod|Puck Peak|Small Mod\r\nroster = Big Mod\r\n[mods]\r\nBig Mod = 0\r\n'
    port = fake_native(tmp_path / 'Native', ini)
    (port / 'mods' / 'Big Mod').mkdir(parents=True)
    found = savedata.Native(str(port))
    assert native.first_in_order(found) is True
    assert lines(port) == ['[paths]', 'user = user', '[launcher]', 'mod_order = Puck Peak|Big Mod|Small Mod',
                           'roster = Big Mod', '[mods]', 'Big Mod = 0', '']


def test_an_ini_with_no_launcher_section_gets_one(tmp_path):
    port = fake_native(tmp_path / 'Native', '[paths]\nuser = user\n')
    (port / 'mods' / 'Other').mkdir(parents=True)
    found = savedata.Native(str(port))
    assert native.first_in_order(found) is True
    assert native.order_of(found) == ['Puck Peak']
    assert savedata.read_ini(found.ini)['paths']['user'] == 'user'


def test_an_ini_we_cannot_read_is_left_alone(port):
    (port / 'mods' / 'Other').mkdir(parents=True)
    before = b'[launcher]\nname = \xff\xfe\n'
    (port / 'nhl_settings.ini').write_bytes(before)
    assert native.first_in_order(savedata.Native(str(port))) is False
    assert (port / 'nhl_settings.ini').read_bytes() == before


def test_notes_name_what_stands_in_the_way(tmp_path):
    ini = INI + 'roster = Big Mod\n[mods]\nPuck Peak = 0\n'
    port = fake_native(tmp_path / 'Native', ini)
    (port / 'mods' / 'Puck Peak').mkdir(parents=True)
    (port / 'mods' / 'Imported from update folder' / 'USRDIR' / 'db').mkdir(parents=True)
    (port / 'mods' / 'Imported from update folder' / 'USRDIR' / 'db' / 'nhlng.db').write_bytes(b'x')
    said = ' '.join(native.notes(savedata.Native(str(port))))
    assert 'switched off' in said and '"Big Mod"' in said and '32-team game patch' in said


def test_a_clean_install_has_no_notes(port):
    assert native.notes(savedata.Native(str(port))) == []


def test_compose_runs_the_launcher_without_a_window(port, monkeypatch):
    calls = []
    monkeypatch.setattr(native.savedata, 'WINDOWS', True)
    monkeypatch.setattr(subprocess, 'run', lambda args, **kw: calls.append((args, kw)) or subprocess.CompletedProcess(args, 0))
    assert native.compose(savedata.Native(str(port))) is True
    args, kw = calls[0]
    assert args[1:] == ['--compose', '--install', str(port)] and kw['cwd'] == str(port)


def test_a_failed_compose_says_what_to_do_and_goes_on(port, monkeypatch):
    said = []
    monkeypatch.setattr(native.savedata, 'WINDOWS', True)
    monkeypatch.setattr(subprocess, 'run', lambda args, **kw: subprocess.CompletedProcess(args, 1))
    assert native.compose(savedata.Native(str(port)), said.append) is False
    assert 'Press PLAY' in said[0]


def test_an_empty_mod_goes_away(port):
    found = savedata.Native(str(port))
    os.makedirs(found.game_folder('BLUS31540'))
    native.clear_mod(found)
    assert not os.path.exists(found.mod)


def test_a_mod_with_files_stays(port):
    found = savedata.Native(str(port))
    os.makedirs(found.game_folder('BLUS31540'))
    with open(os.path.join(found.game_folder('BLUS31540'), 'x'), 'wb') as f:
        f.write(b'x')
    native.clear_mod(found)
    assert os.path.isfile(os.path.join(found.game_folder('BLUS31540'), 'x'))


def test_the_launcher_starts_the_game(port):
    found = savedata.Native(str(port))
    assert found.command() == [str(port / 'NHLLauncher.exe')] and found.launch_dir() == str(port)


def test_rosters_the_launcher_put_aside_are_seen(port):
    (port / 'user' / 'rosters' / 'Big Mod').mkdir(parents=True)
    assert savedata.Native(str(port)).extra_savedata == [str(port / 'user' / 'rosters' / 'Big Mod')]


@pytest.fixture
def window(port, tmp_path, monkeypatch, pack):
    """The Update tab's controller on the port, with a pretend window."""
    from legacy_roster.app import settings as S
    from legacy_roster.app.update import UpdateController
    from .test_app import FakeHost, wait
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    monkeypatch.setattr(S, 'save', lambda values: None)
    rpcs3 = tmp_path / 'rpcs3' / 'rpcs3.exe'
    rpcs3.parent.mkdir()
    rpcs3.write_bytes(b'')
    upd = UpdateController(FakeHost(), settings={'rpcs3': str(port), 'hosts': {'rpcs3': str(rpcs3)}}, pack=pack, photos=False)
    upd.start_up()
    wait(lambda: not upd.scanning and upd.rpcs3 is not None)
    return upd


def test_setup_says_which_game_it_is_and_what_it_cannot_do(window):
    view = window.snapshot()['rpcs3']
    assert view['kind'] == 'NHL Legacy Native' and 'online play' in view['native'] and view['other'] == 'RPCS3'
    assert view['warnings'] == [] and not view['needs_game']


def test_the_game_patch_tab_explains_itself_on_the_port(window):
    from legacy_roster.app import texts as X
    view = window.snapshot()['patch']
    assert view['state']['text'] == X.PATCH_NATIVE
    assert view['buttons'] == [] and view['checks'] == [] and view['regions'] == []
    told = ' '.join(item for section in view['info']['sections'] for item in section['items'])
    assert 'next to NHLLegacy.exe' in told and 'launcher' in told
    assert not any(word in told for word in ('patches folder', 'EU and NA', 'Skip the intro', 'Online play still works'))
    window.patch()
    assert not window.busy and window.dialog is None


def test_the_hints_name_the_game_in_use(window):
    steps = window.snapshot()['steps']
    assert 'NHL Legacy Native must be closed' in steps[0]['hint']
    assert not any('RPCS3' in (row['hint'] or '') for row in steps)


def test_a_full_mod_list_shows_on_setup(window, port):
    with open(port / 'nhl_settings.ini', 'a', encoding='utf-8') as f:
        f.write('roster = Big Mod\n')
    assert '"Big Mod"' in window.snapshot()['rpcs3']['warnings'][0]


def test_switch_goes_to_the_other_game_picked_before(window):
    from .test_app import wait
    window.switch_host()
    wait(lambda: not window.scanning)
    assert window.problem or not window.rpcs3.native       # rpcs3.exe alone: it has no game yet, and that is said


def test_online_says_it_needs_rpcs3(window):
    from legacy_roster.app import texts as X
    from legacy_roster.app.online import OnlineController
    from .test_app import FakeHost
    online = OnlineController(FakeHost(), window)
    assert online.rpcs3() is None and online.no_rpcs3() == X.ONLINE_NATIVE


def test_a_roster_saved_for_the_port_is_the_north_american_one(port, base_bytes, data):
    found = savedata.find_rpcs3(str(port))
    os.makedirs(found.savedata)
    source = savedata.DiscSlot('BLUS31540', str(port / 'game'))
    source.read = lambda: base_bytes
    done = pipeline.update(found.savedata, disc=source, steps=['nhl'], data=data, offline=True, rpcs3=found, targets=['BLES02153'],
                           name='On the port')
    assert done.slot.folder.startswith('BLUS315400')
    assert os.path.isfile(os.path.join(found.savedata, done.slot.folder, 'SYS-DATA'))
    assert done.patch is None


def build_of(port, stamp=0x6ae7cb75, image=0x1a657000):
    """The pretend install's NHLLegacy.exe as a build of the program: only the two numbers savedata.exe_id reads."""
    head = bytearray(0x200)
    head[:2] = b'MZ'
    struct.pack_into('<I', head, 0x3c, 0x80)
    head[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<I', head, 0x88, stamp)
    struct.pack_into('<I', head, 0xd0, image)
    (port / 'NHLLegacy.exe').write_bytes(bytes(head))


@pytest.fixture
def patched_port(port, tmp_path, monkeypatch):
    """A port our patch file fits, with the patch file's pack at hand and no network, launcher or disc work."""
    build_of(port)
    folder = tmp_path / 'packs'
    folder.mkdir()
    with zipfile.ZipFile(folder / 'portpatch.zip', 'w') as z:
        z.writestr('index.json', json.dumps({'version': '0.26', 'stamp': '6ae7cb75', 'image': '1a657000'}))
        z.writestr(patchinstall.PORT_FILE, b'our patch file')
    monkeypatch.setenv('LEGACY_ROSTER_PACKS', str(folder))
    monkeypatch.setattr(packs, 'sync', lambda wanted=None: ([], None))
    monkeypatch.setattr(patchinstall, 'db_files', lambda disc, roster: (b'meta', b'db'))
    monkeypatch.setattr(patchinstall, 'installed_rights',
                        lambda rpcs3, title: 6 if os.path.isfile(os.path.join(rpcs3.game_folder(title), 'db', 'nhlng-meta.xml')) else None)
    monkeypatch.setattr(native, 'compose', lambda host, say=print: True)
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    found = savedata.find_rpcs3(str(port))
    install.use_host(found)
    yield found


def test_only_the_build_the_patch_file_was_made_for_can_be_patched(port):
    assert not savedata.find_rpcs3(str(port)).patchable             # not a program at all
    build_of(port, stamp=1)
    assert not savedata.find_rpcs3(str(port)).patchable
    build_of(port)
    assert savedata.find_rpcs3(str(port)).patchable


def test_patch_and_unpatch_on_the_port(patched_port, port):
    title = savedata.NATIVE_TITLE
    assert patchinstall.state(patched_port) == {title: patchinstall.state(patched_port)[title]}
    assert not patchinstall.state(patched_port)[title]['patched'] and not patchinstall.installed(patched_port)
    patchinstall.install_patch(patched_port, [title], roster=b'roster', say=lambda line: None)
    st = patchinstall.state(patched_port)[title]
    assert st['patched'] and st['version'] == '0.26' and st['game'] == '01.01' and not st['stale'] and st['news']
    assert (port / patchinstall.PORT_FILE).read_bytes() == b'our patch file'
    assert (port / 'mods' / 'Puck Peak' / 'USRDIR' / 'db' / 'nhlng.db').read_bytes() == b'db'
    assert patchinstall.patched_titles(patched_port) == [title]
    assert not (port / 'patches').exists() and not (port / 'config').exists()
    patchinstall.remove(patched_port, say=lambda line: None)
    assert not (port / patchinstall.PORT_FILE).exists() and not (port / 'mods' / 'Puck Peak').exists()
    assert not patchinstall.patched_titles(patched_port) and not patchinstall.installed(patched_port)


def test_a_patched_port_is_still_patched_after_a_restart(patched_port, port):
    """0.95.2 read RPCS3's list at the first scan after a start (the port's list was chosen only later), so a patched port
    showed 'not patched'. The state follows the port asked about, whatever game the program used last."""
    title = savedata.NATIVE_TITLE
    patchinstall.install_patch(patched_port, [title], roster=b'roster', say=lambda line: None)
    install.use_host(None)                                  # a new start: no game chosen yet
    found = savedata.find_rpcs3(str(port))
    assert patchinstall.state(found)[title]['patched'] and patchinstall.installed(found)
    again = savedata.find_rpcs3(str(port).swapcase() if os.name == 'nt' else str(port))     # the same folder spelled another way
    assert patchinstall.state(again)[title]['patched']


def test_the_launcher_must_be_closed_it_holds_the_patch_file(patched_port, port, monkeypatch):
    title = savedata.NATIVE_TITLE
    patchinstall.install_patch(patched_port, [title], roster=b'roster', say=lambda line: None)
    launcher = str(port / savedata.NATIVE_LAUNCHER)
    monkeypatch.setattr(savedata, 'WINDOWS', True)
    monkeypatch.setattr(savedata, '_windows_processes', lambda: [(1, launcher)])
    with pytest.raises(patchinstall.PatchError, match='launcher'):
        patchinstall.remove(patched_port, say=lambda line: None)
    with pytest.raises(patchinstall.PatchError, match='launcher'):
        patchinstall.install_patch(patched_port, [title], roster=b'roster', say=lambda line: None)
    assert (port / patchinstall.PORT_FILE).exists() and patchinstall.patched_titles(patched_port) == [title]
    monkeypatch.setattr(savedata, '_windows_processes', lambda: [(1, r'D:\another\NHLLauncher.exe')])   # another install's
    patchinstall.remove(patched_port, say=lambda line: None)
    assert not (port / patchinstall.PORT_FILE).exists()


def test_a_file_of_that_name_that_was_there_comes_back(patched_port, port):
    (port / patchinstall.PORT_FILE).write_bytes(b'somebody else\'s')
    patchinstall.install_patch(patched_port, [savedata.NATIVE_TITLE], roster=b'roster', say=lambda line: None)
    patchinstall.remove(patched_port, say=lambda line: None)
    assert (port / patchinstall.PORT_FILE).read_bytes() == b'somebody else\'s'


def test_a_pack_for_another_build_changes_nothing(patched_port, port, tmp_path):
    with zipfile.ZipFile(tmp_path / 'packs' / 'portpatch.zip', 'w') as z:
        z.writestr('index.json', json.dumps({'version': '0.26', 'stamp': '00000001', 'image': '1a657000'}))
        z.writestr(patchinstall.PORT_FILE, b'our patch file')
    with pytest.raises(patchinstall.PatchError, match='not the one'):
        patchinstall.install_patch(patched_port, [savedata.NATIVE_TITLE], roster=b'roster', say=lambda line: None)
    assert not (port / patchinstall.PORT_FILE).exists() and not (port / 'mods').exists()


def test_no_pack_says_so_and_changes_nothing(patched_port, port, monkeypatch):
    monkeypatch.delenv('LEGACY_ROSTER_PACKS')
    monkeypatch.setattr(packs, 'path', lambda name: None)
    with pytest.raises(patchinstall.PatchError, match='could not be downloaded'):
        patchinstall.install_patch(patched_port, [savedata.NATIVE_TITLE], roster=b'roster', say=lambda line: None)
    assert not (port / patchinstall.PORT_FILE).exists()


def test_a_port_that_changed_under_the_patch_can_only_be_unpatched(patched_port, port):
    title = savedata.NATIVE_TITLE
    patchinstall.install_patch(patched_port, [title], roster=b'roster', say=lambda line: None)
    build_of(port, stamp=2)
    st = patchinstall.state(patched_port)[title]
    assert st['stale'] and not st['patched'] and patchinstall.stale_titles(patched_port) == [title]
    with pytest.raises(patchinstall.PatchError, match='not the one'):
        patchinstall.install_patch(patched_port, [title], roster=b'roster', say=lambda line: None)
    patchinstall.remove(patched_port, say=lambda line: None)
    assert not (port / patchinstall.PORT_FILE).exists()


def test_the_game_patch_tab_patches_a_port_that_fits(window, port, monkeypatch):
    from legacy_roster.app import texts as X
    from .test_app import wait
    assert window.snapshot()['patch']['state']['text'] == X.PATCH_NATIVE       # the pretend program is no build of ours
    build_of(port)
    window.rescan() if hasattr(window, 'rescan') else window.set_rpcs3(str(port))
    wait(lambda: not window.scanning and window.rpcs3.patchable)
    view = window.snapshot()['patch']
    assert [b['label'] for b in view['buttons']] == ["Patch the game"] and view['checks'] == []
    assert not any('Skip the intro' in item for section in view['info']['sections'] for item in section['items'])
    items = [item for section in view['info']['sections'] for item in section['items']]
    assert [item for item in items if 'RPCS3' in item] == [     # the port's own text, not RPCS3's renamed
        "Online play needs the patch here: it is what lets NHL Legacy Native play online, also with RPCS3 players."]


def test_the_patch_file_is_the_ports_online_entry(patched_port, port, monkeypatch):
    title = savedata.NATIVE_TITLE
    assert not patchinstall.state(patched_port)[title]['online'] and not patchinstall.auto_start(patched_port, title)
    patchinstall.install_patch(patched_port, [title], roster=b'roster', say=lambda line: None)
    assert patchinstall.state(patched_port)[title]['online']
    assert not patchinstall.auto_start(patched_port, title)         # a fake disc: no screens, the steps are pressed by hand
    monkeypatch.setattr(patchinstall, 'screens_in', lambda host, t: True)
    assert patchinstall.auto_start(patched_port, title)
    assert patchinstall.set_online_start(patched_port, [title], True) == []
    assert not (port / 'config').exists() and not (port / 'patches').exists()
    assert patchinstall.set_online(patched_port, [title], True, say=lambda line: None) == [title]
