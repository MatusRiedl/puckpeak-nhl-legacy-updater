"""The picture packs downloaded from the program's file server (packs.py), against a small local web server."""
import functools
import hashlib
import http.server
import json
import os
import threading

import pytest

from legacy_roster import packs


@pytest.fixture
def site(tmp_path, monkeypatch):
    """A folder served at LEGACY_ROSTER_FILES_URL (plain http on this PC) and an empty pack folder."""
    root = tmp_path / 'site'
    root.mkdir()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv('LEGACY_ROSTER_FILES_URL', f"http://127.0.0.1:{server.server_address[1]}/")
    local = tmp_path / 'packs'
    local.mkdir()
    monkeypatch.setattr(packs, 'folder', lambda: str(local))
    yield root
    server.shutdown()
    server.server_close()


def publish(root, contents, size=None, sha=None, fmt=1):
    """Put packs ({name: bytes}) and their manifest on the site, as tools/publish_packs.py does."""
    listed = {}
    for name, data in contents.items():
        digest = hashlib.sha256(data).hexdigest()
        file = f"{name}-{digest[:12]}.zip"
        (root / file).write_bytes(data)
        listed[name] = {'file': file, 'size': len(data) if size is None else size, 'sha256': sha or digest,
                        'built': '2026-10-20'}
    (root / 'manifest.json').write_text(json.dumps({'format': fmt, 'packs': listed}), encoding='utf-8')
    return listed


def files(local):
    return sorted(os.listdir(local))


def test_both_packs_download_once_and_are_used(site):
    publish(site, {'photos': b'P' * 300_000, 'looks': b'L' * 1000})
    seen = []
    assert packs.sync(seen.append) == (['photos', 'looks'], None)
    assert seen[-1] == 1.0 and seen == sorted(seen)
    with open(packs.path('photos'), 'rb') as f:
        assert f.read() == b'P' * 300_000
    assert packs.have('looks') and packs.status()['looks'] == ('2026-10-20', 1000)
    assert packs.sync() == ([], None)                                    # nothing changed: nothing downloaded
    assert not [n for n in files(packs.folder()) if n.endswith('.part')]


def test_a_file_that_is_not_the_published_one_is_refused(site):
    publish(site, {'looks': b'L' * 1000}, sha='0' * 64)
    done, why = packs.sync()
    assert done == [] and 'not the one that was published' in why
    assert packs.path('looks') is None and files(packs.folder()) == []


def test_a_download_bigger_than_listed_stops(site):
    publish(site, {'looks': b'L' * 600_000}, size=1000)
    done, why = packs.sync()
    assert done == [] and 'bigger' in why
    assert files(packs.folder()) == []


def test_a_manifest_for_a_newer_program_or_no_server_downloads_nothing(site, monkeypatch):
    publish(site, {'looks': b'L' * 10}, fmt=2)
    assert packs.manifest() is None and packs.sync() == ([], 'offline')
    monkeypatch.setenv('LEGACY_ROSTER_FILES_URL', 'http://127.0.0.1:9/')
    assert packs.sync() == ([], 'offline')


def test_offline_the_pack_on_this_pc_is_used(site, monkeypatch):
    publish(site, {'looks': b'L' * 10})
    packs.sync()
    monkeypatch.setenv('LEGACY_ROSTER_FILES_URL', 'http://127.0.0.1:9/')
    assert packs.path('looks') and packs.sync() == ([], 'offline')


def test_a_new_pack_gets_a_new_name_and_the_old_one_goes(site):
    publish(site, {'looks': b'old'})
    packs.sync()
    old = packs.path('looks')
    held = open(old, 'rb')                       # the Jerseys window has it open: Windows cannot remove it now
    try:
        publish(site, {'looks': b'new pack'})
        assert packs.sync() == (['looks'], None)
        new = packs.path('looks')
        assert new != old and open(new, 'rb').read() == b'new pack'
    finally:
        held.close()
    packs.prune()                                # the next start
    assert files(packs.folder()) == sorted([os.path.basename(new), packs.STATE])


def test_a_pack_the_program_no_longer_has_is_cleared_away_and_never_fetched(site):
    publish(site, {'photos': b'P' * 5000, 'overlay': b'O' * 300})      # the server still lists the test versions' scoreboard
    assert packs.sync() == (['photos'], None) and 'overlay' not in packs.status()
    old = os.path.join(packs.folder(), 'overlay-f285aae725b5.zip')
    with open(old, 'wb') as f:
        f.write(b'O' * 300)
    state = json.load(open(os.path.join(packs.folder(), packs.STATE), encoding='utf-8'))
    state['overlay'] = {'local': os.path.basename(old), 'size': 300, 'built': '2026-10-27'}
    packs._save_state(state)
    packs.prune()
    assert files(packs.folder()) == sorted([os.path.basename(packs.path('photos')), packs.STATE])
    assert set(packs._state()) == {'photos'}


def test_a_stopped_download_leaves_nothing(site):
    publish(site, {'photos': b'P' * 600_000})
    with pytest.raises(packs.Cancelled):
        packs.sync(cancelled=lambda: True)
    assert packs.path('photos') is None and files(packs.folder()) == []


def test_remove_frees_the_space(site):
    publish(site, {'photos': b'P' * 5000, 'looks': b'L' * 1000})
    packs.sync()
    assert packs.remove_all() == 6000
    assert packs.path('photos') is None and set(packs.status().values()) == {None}
    assert packs.missing(packs.manifest()) == ['photos', 'looks']


def test_only_the_wanted_packs_are_downloaded_and_a_pack_the_server_lacks_is_fine(site):
    publish(site, {'photos': b'P' * 3000, 'looks': b'L' * 1000, 'arenas': b'A' * 500, 'masks': b'M' * 200})
    listed = packs.manifest()
    assert packs.missing(listed, ['arenas', 'ice']) == ['arenas']        # 'ice' is not on the server: not missing
    assert packs.size_of(listed, ['arenas', 'masks']) == 700
    assert packs.sync(wanted=['masks', 'arenas'], listed=listed) == (['arenas', 'masks'], None)
    assert packs.have('arenas') and packs.have('masks') and not packs.have('photos') and not packs.have('looks')
    assert packs.missing(listed) == ['photos', 'looks']                  # the rest still waits for its switch


def test_the_ports_patch_is_downloaded_only_when_asked_for(site):
    publish(site, {'photos': b'P' * 300, 'portpatch': b'D' * 100})
    listed = packs.manifest()
    assert packs.missing(listed) == ['photos']
    assert packs.missing(listed, ['portpatch']) == ['portpatch']


def test_a_developers_own_pack_wins_and_is_not_downloaded(site, tmp_path, monkeypatch):
    own = tmp_path / 'own'
    own.mkdir()
    (own / 'looks.zip').write_bytes(b'mine')
    monkeypatch.setenv('LEGACY_ROSTER_PACKS', str(own))
    publish(site, {'photos': b'P', 'looks': b'L'})
    assert packs.missing(packs.manifest()) == ['photos']
    assert packs.path('looks') == str(own / 'looks.zip')


def test_the_art_modules_open_the_downloaded_packs(site, tmp_path, make_look_pack):
    from legacy_roster.art.lookpack import LookPack
    from legacy_roster.art.photopack import PhotoPack
    assert LookPack.open() is None and PhotoPack.open() is None
    with open(make_look_pack(tmp_path, {22: ('nhl', 'UTA', 1, {'dark': (0, 0, 0)}, None)}).path, 'rb') as f:
        publish(site, {'looks': f.read()})
    packs.sync()
    assert len(LookPack.open()) == 1
