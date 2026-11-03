"""Online play's pieces that need no server and no running RPCS3 (onlinecfg.py): account, config, launch line, log, CRC."""
import os
import struct
from types import SimpleNamespace

import pytest

from legacy_roster import onlinecfg, tdb

EU = 'BLES02153'

CONFIG = "\n".join([
    "Audio:",
    "  Master Volume: 100",
    "Net:",
    "  Bind address: 192.168.1.15",
    "  DNS address: 8.8.8.8",
    "  IP swap list: example.org=1.2.3.4 && gosredirector.ea.com=9.9.9.9",
    "  Internet enabled: Disconnected",
    "  PSN status: Disconnected",
    "  UPNP Enabled: false",
    "Savestate:",
    "  Maximum SaveState Files: 4",
    ""])


def test_the_blit_box_is_ticked_when_the_resolution_scale_is_not_100():
    cfg = "Video:\n  Disable Blit Engine Upscaling: false\n  Renderer: Vulkan\n  Resolution Scale: 300\nVFS:\n  x: 1\n"
    out = onlinecfg.blit_config(cfg)
    assert "  Disable Blit Engine Upscaling: true\n" in out and "Resolution Scale: 300" in out and out.endswith("VFS:\n  x: 1\n")
    assert onlinecfg.blit_config(out) == out
    assert onlinecfg.blit_config(cfg.replace('300', '100')) == cfg.replace('300', '100')       # the default scale: as it is
    assert "Disable Blit Engine Upscaling: true" in onlinecfg.blit_config("Video:\n  Resolution Scale: 200\n")   # a missing key is added
    assert onlinecfg.blit_config("Audio:\n  Master Volume: 100\n") == "Audio:\n  Master Volume: 100\n"
    assert "\r\n" in onlinecfg.blit_config(cfg.replace("\n", "\r\n"))


def _rpcs3(tmp_path, config=CONFIG, custom=None, rpcn="Version: 2\nHost: np.rpcs3.net\nNPID: GuestPlayer\nPassword: secret\n"):
    root = tmp_path / 'rpcs3'
    (root / 'config' / 'custom_configs').mkdir(parents=True)
    (root / 'config' / 'config.yml').write_text(config, encoding='utf-8', newline='')
    if custom is not None:
        (root / 'config' / 'custom_configs' / f'config_{EU}.yml').write_text(custom, encoding='utf-8', newline='')
    if rpcn is not None:
        (root / 'config' / 'rpcn.yml').write_text(rpcn, encoding='utf-8')
    return SimpleNamespace(folder=str(root), exe=str(root / 'rpcs3.exe'), flatpak=False, command=lambda: [str(root / 'rpcs3.exe')],
                           game_disc=lambda title: 'D:/games/nhl.iso' if title == EU else None)


def test_the_account_is_the_npid_and_nothing_else_is_read(tmp_path):
    assert onlinecfg.account(_rpcs3(tmp_path)) == 'GuestPlayer'
    assert onlinecfg.account(_rpcs3(tmp_path / 'a', rpcn="NPID: \"Quoted\"\n")) == 'Quoted'
    assert onlinecfg.account(_rpcs3(tmp_path / 'b', rpcn="Version: 2\nNPID: \n")) is None
    assert onlinecfg.account(_rpcs3(tmp_path / 'c', rpcn=None)) is None


def test_the_net_block_is_set_for_our_server_and_every_other_line_stays():
    out = onlinecfg.net_config(CONFIG, '203.0.113.5')
    old, new = CONFIG.splitlines(), out.splitlines()
    assert len(old) == len(new) and out.endswith('\n')
    changed = [(a, b) for a, b in zip(old, new) if a != b]
    assert [b for _, b in changed] == ["  IP swap list: example.org=1.2.3.4 && gosredirector.ea.com=203.0.113.5",
                                       "  Internet enabled: Connected", "  PSN status: RPCN", "  UPNP Enabled: true"]
    assert onlinecfg.net_config(out, '203.0.113.5') == out                 # a second time changes nothing
    assert "gosredirector.ea.com=9.9.9.9" not in onlinecfg.net_config(CONFIG, '10.0.0.1')


def test_a_missing_net_block_or_key_is_added_and_windows_line_endings_stay():
    bare = onlinecfg.net_config("Audio:\n  Master Volume: 100\n", '1.2.3.4')
    assert bare == ("Audio:\n  Master Volume: 100\nNet:\n  Internet enabled: Connected\n  PSN status: RPCN\n"
                    "  UPNP Enabled: true\n  IP swap list: gosredirector.ea.com=1.2.3.4\n")
    some = onlinecfg.net_config("Net:\n  PSN status: RPCN\nSavestate:\n  X: 1\n", '1.2.3.4')
    assert some == ("Net:\n  PSN status: RPCN\n  Internet enabled: Connected\n  UPNP Enabled: true\n"
                    "  IP swap list: gosredirector.ea.com=1.2.3.4\nSavestate:\n  X: 1\n")
    crlf = onlinecfg.net_config(CONFIG.replace("\n", "\r\n"), '1.2.3.4')
    assert "\r\n" in crlf and "\n" not in crlf.replace("\r\n", "")
    assert onlinecfg.net_config('', '1.2.3.4').startswith("Net:\n")


def test_the_app_writes_its_own_config_and_the_players_files_stay(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    rpcs3 = _rpcs3(tmp_path, custom="Net:\n  PSN status: Disconnected\n")
    kept = {p: open(p, 'rb').read() for p in (os.path.join(rpcs3.folder, 'config', 'config.yml'),
                                               os.path.join(rpcs3.folder, 'config', 'custom_configs', f'config_{EU}.yml'))}
    path = onlinecfg.write_config(rpcs3, EU, '203.0.113.5')
    assert path.endswith(f'config_{EU}.yml') and str(tmp_path / 'local') in path and 'rpcs3' not in path.lower().split('local')[-1]
    assert "PSN status: RPCN" in open(path).read() and "Master Volume" not in open(path).read()   # the custom config's base
    assert {p: open(p, 'rb').read() for p in kept} == kept
    plain = onlinecfg.write_config(_rpcs3(tmp_path / 'x'), 'BLUS31540', '203.0.113.5')   # no custom config: config.yml
    assert "Master Volume: 100" in open(plain).read()


def test_the_launch_line_boots_the_game_with_the_apps_config(tmp_path):
    rpcs3 = _rpcs3(tmp_path)
    assert onlinecfg.launch_args(rpcs3, EU, 'C:/x/config.yml') == [rpcs3.exe, '--no-gui', '--config', 'C:/x/config.yml',
                                                                  'D:/games/nhl.iso']
    assert '--fullscreen' in onlinecfg.launch_args(rpcs3, EU, 'c.yml', fullscreen=True)
    assert onlinecfg.launch_args(rpcs3, 'BLUS31540', 'c.yml') is None                 # no game
    assert onlinecfg.launch_args(SimpleNamespace(exe=None, command=lambda: None, game_disc=lambda t: 'd'), EU, 'c.yml') is None


LOG = "\n".join([
    "· 0:00:00.000000 RPCS3 v0.0.30 old boot",
    "·S 0:00:21.484998 {TID: 1} rpcn: You are now logged in RPCN(Someone | Someone)!",
    "· 0:01:00.000000 RPCS3 v0.0.34-17000 Alpha",
    "·! 0:00:01.184825 sys_net: P2P port 3658 was bound!",
    "·! 0:00:21.240012 {TID: 2} rpcn: Attempting to login!",
    "·S 0:00:21.484998 {TID: 2} rpcn: You are now logged in RPCN(GuestPlayer | GuestPlayer)!"])


def test_the_log_says_who_signed_in_in_this_boot_and_when_it_went_wrong():
    ok = onlinecfg.log_state(LOG)
    assert ok == {'name': 'GuestPlayer', 'bound': True, 'signaling': True, 'refused': None, 'fatal': False, 'old': False}
    tester = onlinecfg.log_state("RPCS3 v1\n·E 4 {TID: 1} rpcn: Server returned protocol version: 34, expected: 32")
    assert tester['old'] is True and tester['name'] is None
    assert onlinecfg.log_state("RPCS3 v1\n·! 4 rpcn: connect: Protocol version matches")['old'] is False
    assert onlinecfg.log_state(LOG + "\n·! 1 rpcn: Disconnected")['name'] is None
    bad = onlinecfg.log_state(LOG + "\n·E 2 {x} rpcn: Failed to get a reply from RPCN signaling")
    assert bad['signaling'] is False and bad['name'] == 'GuestPlayer'
    assert onlinecfg.log_state("RPCS3 v1\n·E 3 rpcn: Login error: wrong password")['refused'].startswith('Login error')
    assert onlinecfg.log_state("RPCS3 v1\n·E 3 RPCS3: Fatal Error")['fatal'] is True
    assert onlinecfg.log_state('') == {'name': None, 'bound': False, 'signaling': True, 'refused': None, 'fatal': False, 'old': False}


def test_the_log_is_read_while_another_program_holds_it_open(tmp_path):
    path = tmp_path / 'RPCS3.log'
    with open(path, 'wb') as held:
        held.write("RPCS3 v1\n\u00b7 rpcn: You are now logged in RPCN(Ä | Ä)!\n".encode())
        held.flush()
        assert 'logged in RPCN(Ä' in onlinecfg.read_shared(str(path))


def test_the_rpcs3_build_is_read_from_the_start_of_the_log(tmp_path):
    rpcs3 = _rpcs3(tmp_path)
    (tmp_path / 'rpcs3' / 'log').mkdir()
    (tmp_path / 'rpcs3' / 'rpcs3.exe').write_bytes(b'')
    assert onlinecfg.rpcs3_build(rpcs3) is None                                   # no log yet
    log = tmp_path / 'rpcs3' / 'log' / 'RPCS3.log'
    log.write_text('RPCS3 v0.0.43-20402-d00d8023 Alpha | master' + chr(10) + 'x' * 100000, encoding='utf-8')
    os.utime(tmp_path / 'rpcs3' / 'rpcs3.exe', (1, 1))
    assert onlinecfg.rpcs3_build(rpcs3) == 20402
    os.utime(tmp_path / 'rpcs3' / 'rpcs3.exe', (log.stat().st_mtime + 100,) * 2)  # updated, not started since
    assert onlinecfg.rpcs3_build(rpcs3) is None
    os.utime(tmp_path / 'rpcs3' / 'rpcs3.exe', (1, 1))
    log.write_text('no version line here', encoding='utf-8')
    assert onlinecfg.rpcs3_build(rpcs3) is None
    assert onlinecfg.MIN_RPCS3 <= 20402


def test_only_the_start_of_a_log_is_read_when_a_limit_is_given(tmp_path):
    path = tmp_path / 'RPCS3.log'
    head = b'RPCS3 v0.0.43-1-x' + bytes([10])
    path.write_bytes(head + b'y' * 5_000_000)
    assert len(onlinecfg.read_shared(str(path), 4096)) < 2_000_000
    assert len(onlinecfg.read_shared(str(path))) == 5_000_000 + len(head)


def test_the_roster_crc_is_the_one_in_the_save_header():
    body = bytes(range(64))
    data = bytearray(0x2C) + body
    struct.pack_into('>II', data, 0x24, len(body), tdb.crc32_bzip2(body))
    assert onlinecfg.roster_crc(bytes(data)) == f'{tdb.crc32_bzip2(body):08x}'
    data[0x30] ^= 1
    with pytest.raises(ValueError):
        onlinecfg.roster_crc(bytes(data))
    with pytest.raises(ValueError):
        onlinecfg.roster_crc(b'short')


def test_a_friends_roster_is_parsed_before_it_is_used(base_bytes):
    assert onlinecfg.roster_check(base_bytes) == onlinecfg.roster_crc(base_bytes)
    body = bytes(range(64))
    junk = bytearray(0x2C) + body                   # a right CRC around nothing that is a roster
    struct.pack_into('>II', junk, 0x24, len(body), tdb.crc32_bzip2(body))
    assert onlinecfg.roster_crc(bytes(junk))
    with pytest.raises(ValueError):
        onlinecfg.roster_check(bytes(junk))


def test_the_log_is_followed_a_piece_at_a_time_and_a_new_log_starts_over(tmp_path):
    path = tmp_path / 'RPCS3.log'
    lines = LOG.split('\n')
    path.write_bytes(('\n'.join(lines[:4]) + '\n').encode())
    tail = onlinecfg.LogTail(str(path))
    assert tail.read() == dict(onlinecfg.log_state(''), bound=True)          # the old boot's sign-in is forgotten
    with open(path, 'ab') as f:
        f.write((lines[4] + '\n' + lines[5][:30]).encode())                   # half a line: waits for its end
    assert tail.read()['name'] is None
    with open(path, 'ab') as f:
        f.write((lines[5][30:] + '\n').encode())
    assert tail.read() == onlinecfg.log_state(LOG) and tail.read()['name'] == 'GuestPlayer'
    with open(path, 'ab') as f:
        f.write(b'\xc2\xb7! 1 rpcn: Disconnected\n')
    assert tail.read()['name'] is None
    path.write_bytes(b'\xc2\xb7 0 RPCS3 v0.0.34 again\n')                       # RPCS3 started again: a shorter, new log
    assert tail.read() == onlinecfg.log_state('RPCS3 v0.0.34')


def test_borderless_fullscreen_changes_only_the_vulkan_line():
    text = ("Video:\r\n  Renderer: Vulkan\r\n  Vulkan:\r\n    Adapter: Some GPU\r\n    Exclusive Fullscreen Mode: Automatic\r\n"
            "    Use Re-BAR for GPU uploads: true\r\n  Write Color Buffers: false\r\n")
    out = onlinecfg.borderless_config(text)
    assert out == text.replace('Exclusive Fullscreen Mode: Automatic', 'Exclusive Fullscreen Mode: Disable')
    assert onlinecfg.borderless_config("Video:\n  Renderer: Vulkan\n") == "Video:\n  Renderer: Vulkan\n"


def test_online_matches_use_the_exact_spu_maths():
    key = onlinecfg.MATHS_KEY + ': Accurate'
    cfg = "Core:\n  PPU Threads: 2\n  SPU XFloat Accuracy: Approximate\n  Z: 1\nVideo:\n  Renderer: Vulkan\n"
    out = onlinecfg.maths_config(cfg)
    assert out == cfg.replace('Approximate', 'Accurate')
    assert onlinecfg.maths_config(out) == out
    assert onlinecfg.maths_config("Core:\n  PPU Threads: 2\nVideo:\n  X: 1\n") == f"Core:\n  {key}\n  PPU Threads: 2\nVideo:\n  X: 1\n"
    assert onlinecfg.maths_config("Video:\n  X: 1\n") == f"Core:\n  {key}\nVideo:\n  X: 1\n"     # a player's config without the block
    assert onlinecfg.maths_config('').startswith("Core:\n")
    assert "\r\n" in onlinecfg.maths_config(cfg.replace("\n", "\r\n"))


def test_a_name_for_the_port_follows_rpcns_rules():
    assert onlinecfg.good_name('Port-Player_1') and onlinecfg.good_name('abc') and onlinecfg.good_name('a' * 16)
    assert not any(onlinecfg.good_name(n) for n in ('', None, 'ab', 'a' * 17, 'a b', 'name!'))


def test_the_port_starts_with_what_its_lobby_needs():
    host = SimpleNamespace(exe=os.path.join('x', 'NHLLegacy.exe'))
    args, env = onlinecfg.port_launch(host, '1.2.3.4', 'Name', os.path.join('saves', 'BLUS315400207'), True)
    assert args == [host.exe, '--username', 'Name']
    assert env['NHL_PUCKPEAK_ONLINE'] == '1.2.3.4' and env['PS3_NET_ONLINE'] == '1' and env['PS3_NP_ONLINE_ID'] == 'Name'
    assert env['NHL_PUCKPEAK_ROSTER'] == 'BLUS315400207' and env['NHL_PUCKPEAK_START'] == '1' and env['NHL_SKIP_INTRO'] == '1'
    _, env = onlinecfg.port_launch(host, '1.2.3.4', 'Name')
    assert 'NHL_PUCKPEAK_ROSTER' not in env and 'NHL_PUCKPEAK_START' not in env
