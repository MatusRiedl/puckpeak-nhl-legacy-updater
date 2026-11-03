"""Shared fixtures.

Most tests need a real roster save of the supported family. It cannot be shipped with the
project (it is another modder's work on top of the game's data), so those tests are skipped unless one
is found: set LEGACY_ROSTER_BASE to a roster save folder, or keep one in work/backup/.
"""
import os
import tempfile

import pytest

from legacy_roster import datasource, pipeline
from legacy_roster.builder import Data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get('LEGACY_ROSTER_BASE') or os.path.join(ROOT, 'work', 'backup', 'BLES021530202')


def pytest_configure(config):
    """The program's own folder (settings, caches, reports, edits) is one temp folder for the whole run, set before any
    test and never set back: a thread a test leaves running writes there, never into this PC's real settings (a test's
    pretend RPCS3 once landed in the owner's settings.json, 2026-10-22). Tests that need their own folder still set
    one."""
    home = tempfile.mkdtemp(prefix='legacy-roster-tests-')
    for name in ('LOCALAPPDATA', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME'):
        os.environ[name] = home
    if os.name != 'nt':
        os.environ['HOME'] = home       # a Mac keeps the program's folder (and RPCS3's) under ~


@pytest.fixture(scope='session')
def base_dir():
    if not os.path.exists(os.path.join(BASE, 'SYS-DATA')):
        pytest.skip("no base roster save available (set LEGACY_ROSTER_BASE)")
    return BASE


@pytest.fixture(scope='session')
def base_bytes(base_dir):
    with open(os.path.join(base_dir, 'SYS-DATA'), 'rb') as f:
        return f.read()


@pytest.fixture(scope='session')
def pack():
    return datasource.read_pack(datasource.BUNDLED_PACK)


@pytest.fixture(scope='session')
def data(pack):
    """The bundled pack only (its NHL snapshot instead of live rosters): fully reproducible."""
    return Data(nhl_players=datasource.flatten_nhl(pack['nhl']), ratings_list=pack['ratings_list'],
                iihf=pack['iihf'], season_year=pack['season'], nhl_last=pack.get('nhl_last'),
                drafts=pack.get('drafts'), contracts=pack.get('contracts'), retired=pack.get('retired'))


@pytest.fixture(scope='session')
def built(base_bytes, data):
    return pipeline.build(base_bytes, data)


@pytest.fixture(scope='session')
def _empty_packs(tmp_path_factory):
    return str(tmp_path_factory.mktemp('packs'))


@pytest.fixture(autouse=True)
def _no_packs(monkeypatch, _empty_packs):
    """The picture packs this PC downloaded (packs.py) are on some PCs only: no test reads them; a test that needs
    one makes its own (`make_look_pack`, test_packs.py)."""
    from legacy_roster import packs
    monkeypatch.delenv('LEGACY_ROSTER_PACKS', raising=False)
    monkeypatch.setattr(packs, 'folder', lambda: _empty_packs)


@pytest.fixture
def make_look_pack():
    return _make_look_pack


def _make_look_pack(tmp_path, teams, fonts=None, legs=None):
    """A small look pack like private/build_looks.py writes: `teams` {slot: (league, name, style, {role: colour},
    ice colour or None)}; every jersey a flat colour, the ice a filled square. `fonts` {(slot, role): picture}: the kits
    that have a number sheet of their own. `legs` {(slot, role): (sock picture, [pants main, pants stripe])}: the kits
    with their own socks and pants (0.95.0)."""
    import io
    import json
    import zipfile
    from PIL import Image
    index, files = {}, {}
    for slot, (league, name, style, kits, ice) in teams.items():
        entry = {'league': league, 'name': name, 'style': style, 'kits': {}, 'ice': ice is not None}
        for role, colour in kits.items():
            buf = io.BytesIO()
            Image.new('RGB', (64, 64), colour).save(buf, 'WEBP', lossless=True)
            files[f'j/{slot}_{role}.webp'] = buf.getvalue()
            entry['kits'][role] = {'numbers': [[250, 250, 250], [10, 10, 10]]}
            if (slot, role) in (fonts or {}):
                buf = io.BytesIO()
                fonts[slot, role].save(buf, 'WEBP', lossless=True)
                files[f'f/{slot}_{role}.webp'] = buf.getvalue()
            if (slot, role) in (legs or {}):
                sock, pants = legs[slot, role]
                buf = io.BytesIO()
                sock.save(buf, 'WEBP', lossless=True)
                files[f's/{slot}_{role}.webp'] = buf.getvalue()
                entry['kits'][role].update(sock=True, pants=[list(c) for c in pants])
        if ice is not None:
            pic = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
            pic.paste(ice + (255,), (300, 300, 700, 700))
            buf = io.BytesIO()
            pic.save(buf, 'WEBP', lossless=True)
            files[f'i/{slot}.webp'] = buf.getvalue()
        index[str(slot)] = entry
    path = tmp_path / 'looks.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('index.json', json.dumps({'format': 1, 'built': '2026-10-17', 'teams': index}))
        for name, data in sorted(files.items()):
            z.writestr(name, data)
    from legacy_roster.art.lookpack import LookPack
    return LookPack.open(str(path))
