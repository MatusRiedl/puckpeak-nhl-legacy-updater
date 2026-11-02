"""The picture parts of 0.76.0 (art/parts.py): arenas, bright ice and team masks from small downloaded packs, team names
on their own, and Restore of one part at a time. Synthetic discs as in test_art.py: no game files are needed."""
import hashlib
import io
import json
import os
import zipfile
from types import SimpleNamespace

import pytest

from legacy_roster import packs, pipeline
from legacy_roster.art import arenas, brightice, install, lab, masks, menus, parts, rpsgl
from legacy_roster.art.extrapack import ExtraPack

from .test_art import SizedDisc, fake_rpcs3

QUIET = lambda msg: None
TITLE = 'BLES02153'


@pytest.fixture(autouse=True)
def no_menu(monkeypatch):
    monkeypatch.setattr(menus, 'menu_files', lambda disc, mode: {})


class Files:
    """Stands in for the player's disc: the 3D files by inner path (their unpacked bytes), packed on request."""
    files = {}

    def __init__(self, _path):
        pass

    def render(self, inner):
        data = self.files.get(inner)
        return None if data is None else rpsgl.pack(data)


def make_zip(path, index, members=None):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('index.json', json.dumps(index))
        for name, data in (members or {}).items():
            z.writestr(name, data)
    return ExtraPack(path)


def loose(r, *rel):
    return os.path.join(r.game_folder(TITLE), *rel)


def arena_pack(tmp_path, base, art='3', runs=((0, 4), (100, 3)), new=b'NEWBYTES', ident='r1'):
    entry = {'base': hashlib.sha1(base).hexdigest(), 'id': ident, 'runs': [list(r) for r in runs], 'file': f"a/{art}.bin"}
    return make_zip(str(tmp_path / f"arenas-{ident}.zip"), {'format': 1, 'built': 'test', 'arenas': {art: entry}},
                    {f"a/{art}.bin": new[:sum(n for _o, n in runs)]})


# --- arenas ---------------------------------------------------------------------------------------------
def test_arena_runs_are_laid_over_the_discs_file_and_nothing_else(base_dir, tmp_path, monkeypatch):
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    base = bytes(range(256)) * 8
    Files.files = {arenas.STADIUM.format(a=3): base}
    monkeypatch.setattr(lab, 'Disc', Files)
    pack = arena_pack(tmp_path, base)
    assert arenas.install_arenas(r, TITLE, pack, QUIET) == 1
    path = loose(r, *arenas.STADIUM.format(a=3).split('/'))
    made = rpsgl.unpack(open(path, 'rb').read())
    want = bytearray(base)
    want[0:4], want[100:103] = b'NEWB', b'YTE'
    assert made == bytes(want) and len(made) == len(base)
    assert arenas.install_arenas(r, TITLE, pack, QUIET) == 0                 # the same pack again: nothing written


def test_an_arena_for_another_version_of_the_game_is_left_as_it_is(base_dir, tmp_path, monkeypatch):
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    Files.files = {arenas.STADIUM.format(a=3): b'a different file' * 50}
    monkeypatch.setattr(lab, 'Disc', Files)
    skipped = []
    pack = arena_pack(tmp_path, b'the file the pack was made for' * 20)
    assert arenas.install_arenas(r, TITLE, pack, QUIET, skipped=skipped) == 0
    assert [a for a, _why in skipped] == ['3'] and 'another version' in skipped[0][1]
    assert not os.path.exists(loose(r, *arenas.STADIUM.format(a=3).split('/')))


def test_an_arena_the_pack_no_longer_holds_goes_back_to_the_games_own(base_dir, tmp_path, monkeypatch):
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    base = bytes(range(256)) * 8
    Files.files = {arenas.STADIUM.format(a=3): base, arenas.STADIUM.format(a=4): base}
    monkeypatch.setattr(lab, 'Disc', Files)
    both = arena_pack(tmp_path, base, art='3', ident='r1')
    arenas.install_arenas(r, TITLE, both, QUIET)
    four = arena_pack(tmp_path, base, art='4', ident='r2')
    arenas.install_arenas(r, TITLE, four, QUIET)
    assert not os.path.exists(loose(r, *arenas.STADIUM.format(a=3).split('/')))
    assert os.path.exists(loose(r, *arenas.STADIUM.format(a=4).split('/')))


# --- bright ice ------------------------------------------------------------------------------------------
def png(color=(250, 250, 250, 255)):
    from PIL import Image
    out = io.BytesIO()
    Image.new('RGBA', (8, 8), color).save(out, 'PNG')
    return out.getvalue()


def ice_entry(art, ident='i1', size=16):
    return {'raster': f"centerlogo_{art}_cm", 'width': 1024, 'height': 1024, 'mips': 11, 'format': 'DXT5', 'size': size,
            'id': ident, 'file': f"c/{art}.bin"}


def ice_pack(tmp_path, arts=('7', '22'), ident='i1'):
    index = {'format': 1, 'built': ident, 'centres': {a: ice_entry(a, ident) for a in arts}}
    return make_zip(str(tmp_path / f"ice-{ident}.zip"), index, {f"c/{a}.bin": bytes(16) for a in arts})


def centre_key(art):
    return tuple(brightice.CENTRE.format(a=art).split('/'))


def test_new_centre_ice_wins_over_this_seasons_and_leaves_the_players_own(base_dir, tmp_path, monkeypatch):
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    Files.files = {}
    monkeypatch.setattr(lab, 'Disc', Files)
    monkeypatch.setattr(brightice, 'centre_file', lambda disc, art, entry, blob: f"ICE {art}".encode())
    writer = install._Writer([r.game_folder(TITLE)])
    writer.write(centre_key(22), b'this season', 'looks:abc')     # this season's centre ice, left from an earlier update
    writer.write(centre_key(7), b'my own', 'looks:def')            # the player's own picture for team 7
    writer.save()
    pack = ice_pack(tmp_path, arts=('7', '22', '29'))
    assert brightice.install_bright(r, TITLE, pack, QUIET, keep={7}) == 2      # 22 and 29
    assert open(loose(r, *centre_key(22)), 'rb').read() == b'ICE 22'
    assert open(loose(r, *centre_key(7)), 'rb').read() == b'my own'
    assert brightice.install_bright(r, TITLE, pack, QUIET, keep={7}) == 0      # the same again: nothing written
    assert brightice.install_bright(r, TITLE, ice_pack(tmp_path, arts=('22',), ident='i2'), QUIET, keep={7}) == 1
    assert not os.path.exists(loose(r, *centre_key(29)))                       # no longer in the pack: the game's again
    assert open(loose(r, *centre_key(7)), 'rb').read() == b'my own'            # never ours to drop
    assert brightice.covered(pack) == {7, 22, 29} and brightice.covered(None) == set()


def test_a_centre_ice_file_of_another_kind_or_an_old_pack_is_left_as_it_is(base_dir, tmp_path, monkeypatch):
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    Files.files = {}
    monkeypatch.setattr(lab, 'Disc', Files)

    def other_kind(disc, art, entry, blob):
        raise rpsgl.RpsglError("this copy of the game has another kind of centre-ice file")
    monkeypatch.setattr(brightice, 'centre_file', other_kind)
    skipped = []
    assert brightice.install_bright(r, TITLE, ice_pack(tmp_path, arts=('5',)), QUIET, skipped=skipped) == 0
    assert skipped == [('5', "this copy of the game has another kind of centre-ice file")]
    old = make_zip(str(tmp_path / 'ice-old.zip'), {'format': 1, 'built': 'x', 'hotspots': {}, 'centres': {'7': 'c/7.webp'}},
                   {'c/7.webp': b'x'})                          # the community's pictures of 0.76.0 (never published)
    assert brightice.install_bright(r, TITLE, old, QUIET) == 0
    assert not os.path.exists(loose(r, *centre_key(5))) and not os.path.exists(loose(r, *centre_key(7)))


INSTALL_BRIGHT = brightice.install_bright


def update_pictures(r, monkeypatch, tmp_path, looks_on, ice_on, own):
    """One update's pictures with this season's looks for art 7 and 22 (covered by the new centre ice) and 30 (not
    covered): looks.install_looks is a stand-in that writes the centre and rink files a look names (looks.look_paths) and
    puts back the ones it no longer makes, as the real one does. Returns how many files each installer wrote."""
    from legacy_roster.art import looks, lookpack, photopack
    path = str(tmp_path / 'ice-m1.zip')
    if not os.path.exists(path):
        ice_pack(tmp_path, arts=('7', '22'), ident='m1').close()
    monkeypatch.setattr(packs, 'path', lambda name: path if name == 'ice' else None)
    monkeypatch.setattr(pipeline.datasource, 'load_pack', lambda offline=True: {})
    monkeypatch.setattr(pipeline, 'Roster', lambda data: SimpleNamespace(team_name=str))
    monkeypatch.setattr(looks, 'club_logos', lambda R, leagues: {})
    monkeypatch.setattr(lookpack.LookPack, 'open', classmethod(lambda cls, path=None: None))
    monkeypatch.setattr(photopack.PhotoPack, 'open', classmethod(lambda cls, path=None: None))
    monkeypatch.setattr(photopack, 'PictureCache', lambda: None)
    centre = lambda art: 'C:/mine.png' if own and art == 7 else f'pack:c/{art}#1'
    monkeypatch.setattr(looks, 'looks_from', lambda R, edits, *a, **k: [
        looks.Look(art, None, (), '', None, (), centre=centre(art)) for art in (7, 22, 30)])
    wrote = {'looks': 0, 'ice': 0}

    def fake_install_looks(rpcs3, title, made, say, also=(), look_pack=None, only=None):
        writer = install._Writer([rpcs3.game_folder(title)])
        wanted = set()
        for m in made:
            for rel in looks.look_paths(m):
                key = tuple(rel.split('/'))
                wanted.add(rel)
                if not writer.current(key, f"looks:{m.centre}"):
                    writer.write(key, f"LOOK {m.art}".encode(), f"looks:{m.centre}")
                    wrote['looks'] += 1
        for key in writer.stale('looks:', wanted):
            writer.drop(tuple(key.split('/')))
        writer.save()
    monkeypatch.setattr(looks, 'install_looks', fake_install_looks)
    monkeypatch.setattr(brightice, 'install_bright', lambda *a, **k: wrote.__setitem__('ice', INSTALL_BRIGHT(*a, **k)))
    builder = SimpleNamespace(bad_pictures={}, mask_looks={}, logos={}, data=None,
                              looks_edits={7: {'ice': {'use': 'file:C:/mine.png'}}} if own else {})
    chosen = {p for p, on in ((parts.LOOKS, looks_on), (parts.BRIGHT_ICE, ice_on)) if on}
    result = SimpleNamespace(art=({}, {}, None), builder=builder, log=[], data=b'')
    pipeline.Pictures(r, TITLE, parts=chosen).put_in(result, QUIET)
    return wrote


@pytest.mark.parametrize('looks_on', [True, False])
@pytest.mark.parametrize('ice_on', [True, False])
@pytest.mark.parametrize('own', [True, False])
def test_each_centre_has_one_owner_whatever_is_switched_on(base_dir, tmp_path, monkeypatch, looks_on, ice_on, own):
    """The player's own centre (with this season's jerseys) wins, then the new centre ice for the teams it has, then this
    season's; a second update writes nothing."""
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    Files.files = {}
    monkeypatch.setattr(lab, 'Disc', Files)
    monkeypatch.setattr(brightice, 'centre_file', lambda disc, art, entry, blob: f"ICE {art}".encode())
    monkeypatch.setattr(brightice, 'rink_file', lambda disc, art: f"ICE {art}".encode())
    update_pictures(r, monkeypatch, tmp_path, looks_on, ice_on, own)
    owner = {}
    rink = tuple(brightice.RINK.format(a=22).split('/'))
    for art, key in ((7, centre_key(7)), (22, centre_key(22)), (30, centre_key(30)), ('rink', rink)):
        entry = install.load_manifest()['games'].get(r.game_folder(TITLE), {}).get('/'.join(key))
        owner[art] = (str(entry['source']).split(':')[0] if entry else None), key
    seven = 'looks' if looks_on and (own or not ice_on) else 'ice' if ice_on else None
    either = 'ice' if ice_on else 'looks' if looks_on else None
    rink_owner = 'looks' if looks_on else 'ice' if ice_on else None      # Utah's coyote goes whoever has the centre
    assert {art: who for art, (who, _k) in owner.items()} == {7: seven, 22: either, 30: 'looks' if looks_on else None,
                                                              'rink': rink_owner}
    for art, (who, key) in owner.items():
        if who:
            art = 22 if art == 'rink' else art
            assert open(loose(r, *key), 'rb').read() == f"{'LOOK' if who == 'looks' else 'ICE'} {art}".encode()
    again = update_pictures(r, monkeypatch, tmp_path, looks_on, ice_on, own)
    assert again == {'looks': 0, 'ice': 0}


def test_turning_the_new_centre_ice_off_gives_the_centre_back_to_this_seasons(base_dir, tmp_path, monkeypatch):
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    Files.files = {}
    monkeypatch.setattr(lab, 'Disc', Files)
    monkeypatch.setattr(brightice, 'centre_file', lambda disc, art, entry, blob: f"ICE {art}".encode())
    update_pictures(r, monkeypatch, tmp_path, True, True, False)
    assert open(loose(r, *centre_key(7)), 'rb').read() == b'ICE 7'
    update_pictures(r, monkeypatch, tmp_path, True, False, False)
    assert open(loose(r, *centre_key(7)), 'rb').read() == b'LOOK 7'
    assert open(loose(r, *centre_key(22)), 'rb').read() == b'LOOK 22'
    assert install.remove_parts([parts.BRIGHT_ICE], QUIET) == 0                # Restore: nothing is the ice's any more
    assert open(loose(r, *centre_key(7)), 'rb').read() == b'LOOK 7'
    update_pictures(r, monkeypatch, tmp_path, False, True, False)              # this season's off: the ice's again
    assert open(loose(r, *centre_key(22)), 'rb').read() == b'ICE 22'
    assert install.remove_parts([parts.BRIGHT_ICE], QUIET) == 2
    assert not os.path.exists(loose(r, *centre_key(22)))


def test_a_centre_goes_into_the_discs_own_file_and_nothing_else_changes():
    """The real thing on the player's disc (LEGACY_ROSTER_DISC): only the raster's bytes differ, the file stays packed."""
    iso = os.environ.get('LEGACY_ROSTER_DISC')
    if not iso or not os.path.exists(iso):
        pytest.skip("needs LEGACY_ROSTER_DISC")
    disc = lab.Disc(iso)
    raw = disc.render(brightice.CENTRE.format(a=3))
    f = rpsgl.Rpsgl(raw)
    r = f.rasters['centerlogo_3_cm']
    entry = dict({k: r[k] for k in brightice.FIELDS}, raster='centerlogo_3_cm', id='t', file='c/3.bin')
    blob = bytes(range(256)) * (r['size'] // 256) + bytes(r['size'] % 256)
    made = brightice.centre_file(disc, 3, entry, blob)
    assert made[:8] == raw[:8]                                 # packed as the disc's is
    old, new = rpsgl.unpack(raw), rpsgl.unpack(made)
    assert len(new) == len(old) and new[r['at']:r['at'] + r['size']] == blob
    assert new[:r['at']] == old[:r['at']] and new[r['at'] + r['size']:] == old[r['at'] + r['size']:]
    with pytest.raises(rpsgl.RpsglError):
        brightice.centre_file(disc, 3, dict(entry, mips=10), blob)


# --- team masks ------------------------------------------------------------------------------------------
def test_team_masks_leave_a_mask_picture_of_the_players_own(base_dir, tmp_path, monkeypatch):
    pytest.importorskip('PIL')
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    Files.files = {}
    monkeypatch.setattr(lab, 'Disc', Files)
    monkeypatch.setattr(masks, 'mask_file', lambda disc, n, picture: f"MASK {n}".encode())
    pack = make_zip(str(tmp_path / 'masks.zip'), {'format': 1, 'built': 'm1', 'masks': {'2': 'm/2.png', '9': 'm/9.png', '10': 'm/10.png'}},
                    {'m/2.png': png(), 'm/9.png': png(), 'm/10.png': png()})
    assert masks.install_team_masks(r, TITLE, pack, QUIET, own={9}) == 2
    assert open(loose(r, *masks.MASK.format(n=2).split('/')), 'rb').read() == b'MASK 2'
    assert not os.path.exists(loose(r, *masks.MASK.format(n=9).split('/')))
    assert masks.install_team_masks(r, TITLE, pack, QUIET, own={9}) == 0


# --- one part at a time -----------------------------------------------------------------------------------
def test_restoring_one_part_puts_back_only_its_files(base_dir, tmp_path, monkeypatch):
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    base = bytes(range(256)) * 8
    Files.files = {arenas.STADIUM.format(a=3): base}
    monkeypatch.setattr(lab, 'Disc', Files)
    arenas.install_arenas(r, TITLE, arena_pack(tmp_path, base), QUIET)
    writer = install._Writer([r.game_folder(TITLE)])
    other = ('fe', 'ion', 'artassets', 'teamlogos', 't22.big')
    writer.write(other, b'a logo', 'https://logo/uta.png#2')                  # a logo: the photos part
    writer.save()
    stadium = loose(r, *arenas.STADIUM.format(a=3).split('/'))
    assert install.remove_parts([parts.ARENAS], QUIET) == 1
    assert not os.path.exists(stadium) and os.path.exists(loose(r, *other))
    assert install.remove_parts([parts.ARENAS], QUIET) == 0                   # nothing of it is left
    assert install.remove_parts([parts.PHOTOS], QUIET) == 1 and not os.path.exists(loose(r, *other))


def test_every_installed_file_belongs_to_exactly_one_part():
    assert parts.belongs('looks:abc', parts.LOOKS) and not parts.belongs('looks:abc', parts.PHOTOS)
    assert parts.belongs('arenas:#1:3:x', parts.ARENAS) and not parts.belongs('arenas:#1:3:x', parts.PHOTOS)
    assert parts.belongs('names:abc', parts.NAMES) and parts.belongs('menus:#3hide', parts.NAMES)
    assert parts.belongs('https://photo/a.png#4', parts.PHOTOS) and parts.belongs('crests:x', parts.PHOTOS)
    assert parts.belongs('mask:#1:200:abc', parts.PHOTOS) and parts.belongs('teammask:#1:2:b', parts.TEAM_MASKS)
    assert not any(parts.belongs('overlay:#1:overlay_0.big:x:sn:y', p) for p in parts.ALL)    # a retired part's
    assert parts.packs_for({parts.NAMES}) == [] and parts.packs_for(parts.LEGACY) == ['photos', 'looks']
    assert parts.packs_for(set(parts.ALL)) == ['photos', 'looks', 'arenas', 'ice', 'masks']
    assert set(packs.NAMES) - {'portpatch'} == set(parts.PACK_OF.values())   # the port's patch is no picture part


# --- the update puts in only what is switched on ---------------------------------------------------------------
def result_of(names=None):
    return SimpleNamespace(art=({}, {}, names), builder=SimpleNamespace(bad_pictures={}, mask_looks={}), log=[], data=b'')


def test_pictures_do_only_the_parts_that_are_on(base_dir, tmp_path, monkeypatch):
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    names = SimpleNamespace(photos=pipeline.Pictures(r, TITLE, parts={parts.NAMES}).photos,
                            own=pipeline.Pictures(r, TITLE, parts={parts.NAMES}).own_only)
    assert names.photos is False and names.own            # team names alone: photos and logos stay as they are
    legacy = pipeline.Pictures(r, TITLE)
    assert legacy.parts == parts.LEGACY and legacy.photos and legacy.names_on
    mine = pipeline.Pictures(r, TITLE, own_only=True)
    assert mine.parts == frozenset() and mine.own_only and not mine.names_on

    called = []
    monkeypatch.setattr(install, 'install', lambda *a, **k: called.append(k) or (0, 0, 0))
    monkeypatch.setattr(pipeline, 'install_arenas', lambda *a, **k: called.append('arenas'))
    monkeypatch.setattr(pipeline, 'install_looks', lambda *a, **k: called.append('looks') or 0)
    pipeline.Pictures(r, TITLE, parts={parts.ARENAS}).put_in(result_of(), QUIET)
    assert called == ['arenas']                           # no names, no photos: install.install is not even called
    called.clear()
    pipeline.Pictures(r, TITLE, parts={parts.NAMES}).put_in(result_of({'teams': []}), QUIET)
    assert len(called) == 1 and called[0]['menus'] and called[0]['pictures'] is False and called[0]['names'] == {'teams': []}
    called.clear()
    assert pipeline.Pictures(r, TITLE, parts=()).put_in(result_of(), QUIET) == (None, 0, False)   # nothing of the player's
    assert called == []


def test_the_test_versions_scoreboard_is_put_back_by_the_next_pictures_install(base_dir, tmp_path, monkeypatch):
    r = fake_rpcs3(base_dir, tmp_path, monkeypatch)
    writer = install._Writer([r.game_folder(TITLE)])
    board = ('fe', 'ion', 'game', 'overlays', 'overlay_0.big')
    os.makedirs(os.path.dirname(loose(r, *board)), exist_ok=True)
    with open(loose(r, *board), 'wb') as f:
        f.write(b"the game's own")                                       # a loose file that was there before
    added = ('fe', 'ion', 'game', 'overlays', 'overlay_2.big')
    logo = ('fe', 'ion', 'artassets', 'teamlogos', 't22.big')
    writer.write(board, b'0.80.0 board', 'overlay:#2:overlay_0.big:abc:sn:-')
    writer.write(added, b'0.80.0 board 2', 'overlay:#2:overlay_2.big:def:sn:-')
    writer.write(logo, b'a logo', 'https://logo/uta.png#2')
    writer.save()
    monkeypatch.setattr(install, 'install', lambda *a, **k: (0, 0, 0))
    monkeypatch.setattr(pipeline, 'install_arenas', lambda *a, **k: None)
    pipeline.Pictures(r, TITLE, parts={parts.ARENAS}).put_in(result_of(), QUIET)
    assert open(loose(r, *board), 'rb').read() == b"the game's own" and not os.path.exists(loose(r, *added))
    assert os.path.exists(loose(r, *logo)) and install.installed() == 1    # the other parts stay
    assert install.remove_retired(QUIET) == 0                               # nothing of it is left
    assert install.remove_parts([parts.PHOTOS], QUIET) == 1


def test_the_command_lines_jerseys_bring_the_new_centre_ice_as_the_window_does(monkeypatch):
    from legacy_roster import cli
    flags = dict(names=False, looks=False, arenas=False, bright_ice=False, team_masks=False, photos=False)
    ask = lambda **on: cli._art_parts(SimpleNamespace(**{**flags, **on}))
    assert ask() is None
    assert ask(photos=True) == parts.LEGACY | {parts.BRIGHT_ICE}
    assert ask(looks=True) == {parts.LOOKS, parts.BRIGHT_ICE}
    assert ask(arenas=True) == {parts.ARENAS} and ask(bright_ice=True) == {parts.BRIGHT_ICE}
    asked = []
    monkeypatch.setattr(packs, 'manifest', lambda: {})
    monkeypatch.setattr(packs, 'sync', lambda *a, wanted=None, **k: (asked.append(set(wanted)), ([], None))[1])
    cli._download_packs()                       # `packs download` and export-files --photos
    assert asked == [set(parts.packs_for(parts.LEGACY | {parts.BRIGHT_ICE}))] and 'ice' in asked[0]
