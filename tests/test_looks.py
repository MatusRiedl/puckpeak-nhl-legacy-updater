"""The new jerseys and centre-ice logos (art/looks.py).

The files themselves are the game's and need the game's disc: set LEGACY_ROSTER_DISC to a disc image (read only); the tests
that need it skip without it. The drawing helpers are tested on small invented pictures."""
import os

import pytest

from legacy_roster import savedata
from legacy_roster.art import install, looks, rpsgl

PIL = pytest.importorskip('PIL')
from PIL import Image  # noqa: E402

DISC = os.environ.get('LEGACY_ROSTER_DISC')


def test_recolour_swaps_flat_colours_keeps_shading_and_blends_edges():
    masters = ((130, 17, 19), (27, 27, 27), (234, 234, 234))
    targets = ((0, 0, 200), (10, 200, 10), (255, 255, 0))
    img = Image.new('RGBA', (3, 1))
    img.putpixel((0, 0), (130, 17, 19, 255))
    img.putpixel((1, 0), (134, 21, 23, 128))                 # a little lighter than the master: stays a little lighter
    img.putpixel((2, 0), (182, 125, 126, 255))               # halfway between red and white: halfway between blue and yellow
    out = looks.recolour(img, masters, targets)
    assert out.getpixel((0, 0)) == (0, 0, 200, 255)
    assert out.getpixel((1, 0)) == (4, 4, 204, 128)          # the alpha is kept
    r, g, b, _ = out.getpixel((2, 0))
    assert 100 < r < 155 and 100 < g < 155 and 90 < b < 110


def test_arena_names_split_into_two_halves():
    assert looks.split_arena("The Delta Center") == ("DELTA", "CENTER")
    assert looks.split_arena("Climate Pledge Arena") == ("CLIMATE", "PLEDGE ARENA")
    assert looks.split_arena("T-Mobile Arena") == ("T-MOBILE", "ARENA")
    assert looks.split_arena("") == ("", "")


def test_the_centre_ice_logo_follows_the_games_own_rules():
    logo = Image.new('RGBA', (100, 80), (200, 30, 30, 255))
    img = looks.centre_logo(logo, "Delta Center", (30, 30, 30))
    assert img.size == (1024, 1024)
    assert img.getpixel((5, 5)) == looks.ICE + (0,)                   # ice-white under what is transparent
    assert img.getpixel((520, 5))[3] == 0 and img.getpixel((520, 512))[3] == 0     # the strip the red line crosses
    assert img.getpixel((520, 512))[0] > 150                          # ... carries the logo's colours
    assert img.getpixel((300, 512))[3] == 255 and img.getpixel((600, 300))[3] == 255
    assert looks.centre_logo(None, "", (0, 0, 0)).getpixel((300, 300)) == looks.ICE + (255,)


def test_a_kit_is_made_from_two_colours():
    kit = looks.kit_for((106, 179, 230), (32, 32, 32))
    assert kit.home.body == (32, 32, 32) and kit.home.trim == (106, 179, 230)
    assert kit.away.trim == looks.WHITE and kit.away.body == (106, 179, 230)


@pytest.fixture(scope='module')
def disc():
    if not DISC or not os.path.exists(DISC):
        pytest.skip("no game disc (set LEGACY_ROSTER_DISC to your NHL Legacy disc image)")
    from legacy_roster.art.lab import Disc
    return Disc(DISC)


def _look(art=22, versions=((3, False), (4, True))):
    logo = Image.new('RGBA', (120, 90), (20, 120, 200, 255))
    return looks.Look(art, looks.kit_for((106, 179, 230), (32, 32, 32)), (logo, logo), "The Delta Center", (32, 32, 32),
                      versions)


def test_every_file_keeps_the_size_and_layout_of_the_discs_and_is_made_the_same_way_twice(disc):
    maker = looks.Maker(disc)
    files = maker.files(_look(30, ((4, False), (5, True))))
    assert sorted(files) == sorted(looks.look_paths(_look(30, ((4, False), (5, True)))))
    for inner, data in files.items():
        if inner.endswith('.rpsgl'):
            mine, own = rpsgl.Rpsgl(data), rpsgl.Rpsgl(disc.render(inner))
            assert {k: (r['width'], r['height'], r['mips'], r['format'], r['size']) for k, r in mine.rasters.items()} == \
                   {k: (r['width'], r['height'], r['mips'], r['format'], r['size']) for k, r in own.rasters.items()}
            assert mine.build() == data
    assert looks.Maker(disc).files(_look(30, ((4, False), (5, True)))) == files          # rule 4: deterministic
    jersey = rpsgl.Rpsgl(files['rendering/jersey/texlib_1_30_4.rpsgl']).image('jersey_1_30_4_cm')
    assert jersey.getpixel((100, 100))[:3] != rpsgl.Rpsgl(disc.render('rendering/jersey/texlib_1_30_4.rpsgl')).image(
        'jersey_1_30_4_cm').getpixel((100, 100))[:3]


def test_utahs_old_crest_is_gone_from_every_map_and_the_helmet_and_rink_carry_the_new_logo(disc):
    maker = looks.Maker(disc)
    files = maker.files(_look(22, ((3, False),)))
    mine = rpsgl.Rpsgl(files['rendering/jersey/texlib_1_22_3.rpsgl'])
    own = rpsgl.Rpsgl(disc.render('rendering/jersey/texlib_1_22_3.rpsgl'))
    for name in ('jersey_1_22_3_sm', 'jersey_1_22_3_0_nm'):                       # the shine and relief of the old crest
        box = looks.CREST
        assert mine.image(name).crop(box).tobytes() != own.image(name).crop(box).tobytes()
        assert len(set(mine.image(name).crop((box[0] + 20, box[1] + 20, box[2] - 20, box[3] - 20)).tobytes())) < 40
    decal = rpsgl.Rpsgl(files['rendering/logo/texlib_22_1_3.rpsgl']).image('logo_22_1_3_0')
    assert decal.getchannel('A').getextrema()[1] == 255 and decal.getpixel((128, 64)) !=         rpsgl.Rpsgl(disc.render('rendering/logo/texlib_22_1_3.rpsgl')).image('logo_22_1_3_0').getpixel((128, 64))
    rink = rpsgl.Rpsgl(files['rendering/icesurface/icesurface_22_bm.rpsgl']).image('icesurface_22_bm').convert('RGB')
    old = rpsgl.Rpsgl(disc.render('rendering/icesurface/icesurface_22_bm.rpsgl')).image('icesurface_22_bm').convert('RGB')
    assert max(abs(a - b) for a, b in zip(rink.getpixel((20, 20)), old.getpixel((20, 20)))) < 8          # the rest is as it was
    assert max(abs(a - b) for a, b in zip(rink.getpixel((257, 240)), old.getpixel((257, 240)))) > 30     # the coyote is not
    assert sorted(files) == sorted(looks.look_paths(_look(22, ((3, False),))))


def test_installing_twice_writes_once_and_restoring_puts_the_game_back(disc, tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    root = tmp_path / 'rpcs3'
    (root / 'config').mkdir(parents=True)
    (root / 'dev_hdd0' / 'home' / '00000001' / 'savedata').mkdir(parents=True)
    (root / 'rpcs3.exe').write_bytes(b'MZ')
    title = 'BLUS31540' if 'USA' in DISC or 'NA' in os.path.basename(DISC) else 'BLES02153'
    (root / 'config' / 'games.yml').write_text(f'{title}: "{DISC.replace(chr(92), "/")}"\n', encoding='utf-8')
    found = savedata.find_rpcs3(str(root / 'rpcs3.exe'))
    look = _look(22, ((3, False),))
    n = looks.install_looks(found, title, [look], lambda msg: None)
    assert n == len(looks.look_paths(look))
    game = found.game_folder(title)
    centre = os.path.join(game, 'rendering', 'icesurface', 'centerlogo_22_cm.rpsgl')
    assert os.path.exists(centre) and os.path.exists(os.path.join(game, 'fe', 'ion', 'artassets', 'jerseys', 'jersey_1_22_3.big'))
    assert looks.install_looks(found, title, [look], lambda msg: None) == 0           # nothing to do the second time
    assert looks.install_looks(found, title, [_look(22, ((3, False),))._replace(arena="Other Arena")], lambda msg: None) == n
    install.remove(lambda msg: None)                                                  # "Restore the game's own pictures"
    assert not os.path.exists(centre) and install.installed() == 0


def _fake_rpcs3(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    root = tmp_path / 'rpcs3'
    (root / 'config').mkdir(parents=True)
    (root / 'dev_hdd0' / 'home' / '00000001' / 'savedata').mkdir(parents=True)
    (root / 'rpcs3.exe').write_bytes(b'MZ')
    title = 'BLUS31540' if 'USA' in DISC or 'NA' in os.path.basename(DISC) else 'BLES02153'
    (root / 'config' / 'games.yml').write_text(f'{title}: "{DISC.replace(chr(92), "/")}"\n', encoding='utf-8')
    return savedata.find_rpcs3(str(root / 'rpcs3.exe')), title


def test_a_players_own_jersey_and_ice_are_installed_and_put_back_when_chosen_away(disc, base_dir, tmp_path, monkeypatch):
    from legacy_roster import layout as L
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    slot = L.API_TO_SLOT['EDM']
    found, title = _fake_rpcs3(tmp_path, monkeypatch)
    maker = looks.Maker(disc)
    versions = looks.roster_versions(R, slot)
    variant, light = versions[0][0], versions[0][1]
    own = maker.own_colour_map(slot, variant).convert('RGB')
    own.paste((0, 200, 0), (100, 300, 200, 700))                        # a green bar painted on the game's own
    mine = tmp_path / 'mine.png'
    own.save(mine)
    ice = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
    ice.paste((200, 0, 200, 255), (200, 200, 800, 800))
    ice_png = tmp_path / 'ice.png'
    ice.save(ice_png)
    other = versions[-1][0]
    edit = {slot: {'uniforms': {'colours': {'primary': '#ff00ff'}, 'versions': {str(variant): 'file:' + str(mine),
                                                                                   str(other): 'colours'}},
                   'ice': {'use': 'file:' + str(ice_png), 'arena': 'Test Arena'}}}
    made = [m for m in looks.looks_from(R, edit, {}, {}) if m.art == slot]
    assert len(made) == 1 and made[0].files[0][0] == variant and made[0].versions == ((other, versions[-1][1]),)
    n = looks.install_looks(found, title, made, lambda msg: None)
    game = found.game_folder(title)
    jersey = os.path.join(game, 'rendering', 'jersey', f'texlib_1_{slot}_{variant}.rpsgl')
    centre = os.path.join(game, 'rendering', 'icesurface', f'centerlogo_{slot}_cm.rpsgl')
    bar = rpsgl.Rpsgl(open(jersey, 'rb').read()).image(f'jersey_1_{slot}_{variant}_cm').getpixel((150, 500))
    assert bar[1] > 150 and bar[0] < 80                                        # the player's green bar is in the game's file
    ring = rpsgl.Rpsgl(open(centre, 'rb').read()).image(f'centerlogo_{slot}_cm')
    assert ring.getpixel((500, 500))[3] == 0 and ring.getpixel((300, 500))[0] > 150      # own picture, strip made clear
    assert looks.install_looks(found, title, made, lambda msg: None) == 0       # installed already
    again = [m._replace(centre='game', files=()) for m in made]                 # chosen "the game's own" since
    looks.install_looks(found, title, again, lambda msg: None)
    assert not os.path.exists(jersey) and not os.path.exists(centre)             # the game's own is back
    assert os.path.exists(os.path.join(game, 'rendering', 'jersey', f'texlib_1_{slot}_{other}.rpsgl'))
    install.remove(lambda msg: None)
    assert install.installed() == 0 and n > 3


def test_a_goalies_own_mask_picture_is_installed_and_put_back_when_dropped(disc, tmp_path, monkeypatch):
    from legacy_roster.art import masks
    found, title = _fake_rpcs3(tmp_path, monkeypatch)
    pic = Image.new('RGB', (512, 512), (0, 200, 0))
    mine = tmp_path / 'mask.png'
    pic.save(mine)
    assert masks.own_picture(disc, 120).size == (512, 512)
    assert masks.install_masks(found, title, {291: 'file:' + str(mine)}, lambda msg: None) == 1
    path = os.path.join(found.game_folder(title), 'rendering', 'goaliehelmet', 'goaliehelmet_0_291_cm.rpsgl')
    shown = rpsgl.Rpsgl(open(path, 'rb').read()).image('goaliehelmet_0_291_cm').getpixel((256, 256))
    assert shown[1] > 150 and shown[0] < 80                                   # his green picture is in the game's file
    assert masks.install_masks(found, title, {291: 'file:' + str(mine)}, lambda msg: None) == 0     # installed already
    masks.install_masks(found, title, {}, lambda msg: None)                    # no goalie wears a picture any more
    assert not os.path.exists(path)
    install.remove(lambda msg: None)


# --- this season's jerseys from the look pack (art/lookpack.py) ------------------------------------------------------------
def test_pack_names_and_versions(base_dir):
    from legacy_roster.art import lookpack
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    assert lookpack.norm('Färjestad BK') == 'farjestadbk' == lookpack.norm('FARJESTAD  bk')
    # home, away and (0.92.0) the lowest Alternate version: the pack's third goes there
    assert looks.pack_versions(R, 27, 1) == {'dark': (4, False), 'light': (3, True), 'third': (5, False)}  # Toronto
    assert looks.art_style(R, 27) == 1 and looks.art_style(R, R.T.get(135, 'artid')) == 0                  # Canada: classic
    # Pittsburgh's default dark v3 is the Winter Classic team's (slot 218, Pittsburgh's art): v0 is the club's own
    assert looks.pack_versions(R, 23, 1) == {'dark': (0, False), 'light': (1, True), 'third': (6, False)}
    assert looks.pack_versions(R, 2, 1) == {'dark': (0, False), 'light': (1, True), 'third': (2, False)}   # Boston
    assert looks.pack_versions(R, 22, 1) == {'dark': (3, False), 'light': (4, True)}                       # Utah
    assert looks.pack_versions(R, 36, 1) == {} and looks.pack_versions(R, 162, 1) == {'dark': (4, False), 'light': (3, True)}


def test_the_pack_third_goes_on_the_alternate_version_and_every_other_version_stays_the_games_own(base_dir, tmp_path, make_look_pack):
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    pack = make_look_pack(tmp_path, {2: ('nhl', 'BOS', 1, {'dark': (20, 20, 20), 'light': (240, 240, 240)}, None),
                                     23: ('nhl', 'PIT', 1, {'dark': (20, 20, 20), 'light': (240, 240, 240),
                                                            'third': (250, 180, 0)}, None)})
    assert sorted(looks.pack_team(R, 2, pack).kits) == [0, 1]                  # Boston: the pack has no third, its Alternate (v2) stays the game's own
    assert sorted(looks.pack_team(R, 23, pack).kits) == [0, 1, 6]              # Pittsburgh: the third is on its Alternate version
    assert looks.default_use(2, 2, False, looks.pack_team(R, 2, pack).kits) == 'game'
    assert looks.default_use(23, 6, False, looks.pack_team(R, 23, pack).kits) == looks.PACK
    assert looks.default_use(23, 5, False, looks.pack_team(R, 23, pack).kits) == 'game'       # another version of the team: still the game's


def test_a_team_without_an_alternate_gets_a_row_for_the_packs_third_once(base_dir, tmp_path, make_look_pack):
    from legacy_roster import gamepatch
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    kits = {'dark': (20, 20, 20), 'light': (240, 240, 240), 'third': (250, 180, 0)}
    pack = make_look_pack(tmp_path, {1: ('nhl', 'WPG', 1, kits, None), 2: ('nhl', 'BOS', 1, kits, None)})
    rows = R.f['wgjx'].cur_rec
    assert looks.pack_versions(R, 1, 1) == {'dark': (3, False), 'light': (4, True)}       # Winnipeg: no Alternate
    added = looks.alternate_rows(R, pack)
    assert added == [(1, 1, 5)] and R.f['wgjx'].cur_rec == rows + 1                      # Boston has one: no row for it
    assert looks.pack_versions(R, 1, 1)['third'] == (5, True)
    mine = gamepatch.art_rows(R, 1)
    away = next(r for r in mine if r['TccF'] == 4 and r['LQDG'] == 1 and r['RLVc'] == 1)
    row = next(r for r in mine if r['TccF'] == 5)
    assert row['gZuU'] == looks.ALTERNATE and row['MSFy'] == 0 and row['XOdd'] == 5
    assert row['xnYt'] == max(r['xnYt'] for r in mine if r is not row) + 1
    assert {k: v for k, v in row.items() if k not in ('TccF', 'XOdd', 'xnYt', 'gZuU', 'MSFy')} == \
           {k: v for k, v in away.items() if k not in ('TccF', 'XOdd', 'xnYt', 'gZuU', 'MSFy')}
    assert looks.alternate_rows(R, pack) == []                                           # done once
    assert looks.alternate_rows(Roster(R.f.build()), pack) == []                         # also after a save and load
    assert looks.pack_team(R, 1, pack).kits[5].like == 4                                 # its files start from the away version's


def test_the_alternate_rows_leave_room_for_coachella_and_henderson(base_dir, tmp_path, make_look_pack):
    from legacy_roster import gamepatch
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    kits = {'dark': (20, 20, 20), 'light': (240, 240, 240), 'third': (250, 180, 0)}
    pack = make_look_pack(tmp_path, {1: ('nhl', 'WPG', 1, kits, None)})
    W = R.f['wgjx']
    row = {f: W.get(0, f) for f in W.fields}
    while W.cur_rec < looks.ROWS_MAX - looks.ROWS_KEPT:         # a roster with no spare row: a full table stops an update
        W.add_record(row)
    assert looks.alternate_rows(R, pack) == []
    assert gamepatch.art_fit(R)


def test_a_version_the_disc_lacks_borrows_the_files_of_another_with_its_own_number(disc):
    raw = disc.render(looks.JERSEY.format(s=1, a=23, v=1))
    f = rpsgl.Rpsgl(looks.renamed_variant(raw, 23, 1, 1, 9))
    assert all('_23_9' in name for name in f.rasters if name.startswith(('jersey', 'font'))) and f.rasters
    borrow = looks.Borrow(disc)
    assert not borrow.has(looks.JERSEY.format(s=1, a=23, v=9))
    borrow.lend(23, 1, 9, 1)
    for template in (looks.JERSEY, looks.PANT, looks.SOCK, looks.PREVIEW, looks.NAME, looks.DECAL):
        assert borrow.has(template.format(s=1, a=23, v=9)), template
    again = rpsgl.Rpsgl(borrow.render(looks.JERSEY.format(s=1, a=23, v=9)))
    assert list(again.rasters) == list(f.rasters) and disc.render(looks.JERSEY.format(s=1, a=23, v=1)) == raw
    borrow.lend(23, 1, 1, 0)                                          # a file the disc has itself is never replaced
    assert borrow.render(looks.JERSEY.format(s=1, a=23, v=1)) == raw


def test_every_league_is_editable_where_the_game_has_jerseys_and_the_team_wears_its_own(base_dir):
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    assert looks.team_art(R, 36) == (162, 1) and looks.team_art(R, 135) == (R.T.get(135, 'artid'), 0)
    assert looks.editable(R, 36) is None and looks.editable(R, 135) is None and looks.editable(R, 23) is None
    # outside the NHL home, away and the Alternate versions; the NHL keeps every version
    assert [(v, light) for v, light, _d in looks.team_versions(R, 36)] == [(3, True), (4, False)]      # (this club has no Alternate)
    assert len(looks.team_versions(R, 2)) == 4
    # the Winter Classic team wears Pittsburgh's art; Coachella Valley has no jerseys in the game
    assert looks.jersey_owner(R, 218) == 23 and 'Pittsburgh' in looks.editable(R, 218)
    assert looks.editable(R, 234) == "The game has no jerseys of its own for this team."
    assert looks.editable(R, None) == "Pick a team first."


def test_median_and_one_colour_number_sheets():
    pics = [Image.new('L', (4, 4), v) for v in (9, 1, 7, 3, 5)]
    assert looks.median_picture(pics).getextrema() == (5, 5)
    sheet = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    sheet.paste((240, 240, 240, 255), (10, 10, 50, 50))                     # one colour, no outline
    assert looks.sheet_colours(sheet) == ((244, 244, 244),)
    assert looks.recolour_sheet(sheet, (200, 20, 20), (0, 0, 0)).getpixel((30, 30)) == (196, 16, 16, 255)   # the cloth's shading kept
    assert looks.recolour_sheet(sheet, (200, 20, 20), (0, 0, 0)).getpixel((2, 2))[3] == 0


def test_a_number_sheet_gets_its_own_colours_for_names_digits_rings_and_small_digits():
    """The names are not the digits' colour, the digits have two rings, and a light kit's small digits are not swapped."""
    for light, digit, outline in ((False, (234, 234, 234), (27, 27, 27)), (True, (130, 17, 19), (27, 27, 27))):
        sheet = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
        sheet.paste(digit + (255,), (40, 5, 120, 40))                           # a letter
        sheet.paste(outline + (255,), (30, 140, 130, 250))                      # a digit: outline round its fill
        sheet.paste(digit + (255,), (36, 146, 124, 244))
        sheet.paste((234, 234, 234, 255), (40, 400, 120, 440))                  # a small digit: white fill, red outline
        sheet.paste((130, 17, 19, 255), (36, 396, 124, 444))
        sheet.paste((234, 234, 234, 255), (40, 400, 120, 440))
        out = looks.recolour_numbers(sheet, light, (220, 60, 28), (28, 36, 92), (236, 236, 236), (212, 212, 212))
        assert out.getpixel((80, 20))[:3] == (212, 212, 212)                    # the letter wears the names' colour
        assert out.getpixel((80, 200))[:3] == (220, 60, 28)                     # the digit its fill
        assert out.getpixel((32, 200))[:3] == (28, 36, 92)                      # the ring round it
        assert out.getpixel((30, 200)) == (236, 236, 236, 255)                  # the second ring: the digit's outer edge
        assert out.getpixel((80, 420))[:3] == (220, 60, 28)                     # the small digit's fill, dark and light alike
        assert out.getpixel((38, 420))[:3] == (28, 36, 92)                      # and its ring
        assert out.getpixel((2, 2))[3] == 0
        # nothing outside the chassis' glyphs: a ring grown outwards showed as a line under and over the number
        assert out.getchannel('A').tobytes() == sheet.getchannel('A').tobytes()
    plain = looks.recolour_numbers(sheet, True, (220, 60, 28), (28, 36, 92), None, (212, 212, 212))
    assert plain.getpixel((30, 200))[:3] == (28, 36, 92)                        # no second ring: the ring stays as it is


def test_a_packs_number_sheet_gets_the_marks_it_lacks_from_the_chassis():
    """O'Reilly's apostrophe: an empty cell of the pack's sheet takes the chassis' glyph in the letters' colour; a filled
    cell and a nameplate sheet stay as they are."""
    chassis = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    for box in ((4, 5, 26, 40), (387, 5, 395, 18), (380, 70, 400, 74)):        # A, the apostrophe, the hyphen (row 2)
        chassis.paste((240, 240, 240, 255), box)
    sheet = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    sheet.paste((10, 60, 200, 255), (6, 6, 25, 41))                            # the pack's A, blue; no marks
    out = looks.with_marks(sheet, chassis)
    assert out.getpixel((390, 10)) == (10, 60, 200, 255) and out.getpixel((390, 72)) == (10, 60, 200, 255)
    assert out.getpixel((15, 20)) == (10, 60, 200, 255) and out.getpixel((5, 5))[3] == 0   # the pack's own A as it was
    assert out.getpixel((390, 30))[3] == 0                                      # nothing beyond the chassis' glyph
    plate = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    plate.paste((200, 20, 20, 255), (0, 0, 512, 96))                           # a nameplate behind the letters
    assert looks.with_marks(plate, chassis).tobytes() == plate.tobytes()


def test_pack_looks_cover_every_league_and_leave_out_a_slot_holding_another_club(base_dir, tmp_path, make_look_pack):
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    pack = make_look_pack(tmp_path, {27: ('nhl', 'TOR', 1, {'dark': (0, 40, 120), 'light': (240, 240, 240), 'third': (20, 20, 20)},
                                 (0, 40, 120)),
                            32: ('ahl', R.team_name(32), 1, {'dark': (150, 10, 10), 'light': (240, 240, 240)}, (150, 10, 10)),
                            135: ('national', 'CAN', 0, {'dark': (200, 10, 10), 'light': (240, 240, 240)}, (200, 10, 10)),
                            33: ('ahl', 'Somebody Else', 1, {'dark': (1, 2, 3)}, None),
                            91: ('del', R.team_name(91), 0, {'dark': (10, 10, 150)}, (10, 10, 150)),
                            92: ('del', R.team_name(92), 0, {}, (10, 150, 10)),
                            105: ('extraliga', R.team_name(105), 0, {'dark': (150, 150, 10)}, (150, 150, 10))})
    skipped, no_ice = [], []
    made = {m.art: m for m in looks.looks_from(R, {}, {}, {}, look_pack=pack, skipped=skipped, no_ice=no_ice)}
    tor = made[27]
    assert sorted((k.variant, k.light) for k in tor.pack) == [(3, True), (4, False), (5, False)]     # the pack's third on the Alternate
    assert tor.centre.startswith('pack:i/27.webp#') and tor.versions == () and tor.style == 1
    utica, canada = made[R.T.get(32, 'artid')], made[R.T.get(135, 'artid')]
    assert utica.style == 1 and len(utica.pack) == 2 and canada.style == 0 and canada.centre == 'game'
    assert [s for s, _why in skipped] == [33] and R.T.get(33, 'artid') not in made
    # centre ice only where the game shows it at the club's own home games: the Extraliga's are the club's art; the
    # DEL's 14 clubs share the DEL's ice and the national teams the international one, so those keep the game's own
    assert made[R.T.get(105, 'artid')].centre.startswith('pack:i/105.webp#')
    assert made[R.T.get(91, 'artid')].centre == 'game' and len(made[R.T.get(91, 'artid')].pack) == 1
    assert R.T.get(92, 'artid') not in made and sorted(s for s, _why in no_ice) == [91, 92, 135]
    assert looks.shown_centre(R, 91) == looks.shown_centre(R, 92) == 197 and looks.shown_centre(R, 135) == 501
    assert looks.shown_centre(R, 27) == 27 and looks.shown_centre(R, 158) == R.T.get(158, 'artid')
    assert looks.shown_centre(R, 30) == 30 and looks.shown_centre(R, 31) == 31      # not their arena's art 16: lab round 58
    # the player chose the game's own for Toronto's dark version and its ice: only the others stay the pack's
    edits = {27: {'uniforms': {'versions': {'4': 'game'}}, 'ice': {'use': 'game'}}}
    tor = next(m for m in looks.looks_from(R, edits, {}, {}, look_pack=pack) if m.art == 27)
    assert sorted(k.variant for k in tor.pack) == [3, 5] and tor.centre == 'game'      # the Alternate stays the pack's
    # without a pack the NHL teams keep the game's own (Utah, Seattle, Vegas: from their colours) and nothing else is made
    assert all(m.art in looks.NEW_TEAMS for m in looks.looks_from(R, {}, {}, {}, look_pack=None))


def test_a_clubs_edits_are_kept_outside_the_nhl_too(base_dir, tmp_path, make_look_pack):
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    utica, canada = R.T.get(32, 'artid'), R.T.get(135, 'artid')
    pack = make_look_pack(tmp_path, {32: ('ahl', R.team_name(32), 1, {'dark': (150, 10, 10), 'light': (240, 240, 240)},
                                          (150, 10, 10)),
                                     91: ('del', R.team_name(91), 0, {'dark': (10, 10, 150)}, (10, 10, 150))})
    (v_light, _l, _d), (v_dark, _k, _e) = looks.team_versions(R, 32)
    mine = tmp_path / 'mine.png'
    Image.new('RGB', (512, 512), (0, 200, 0)).save(mine)
    edits = {32: {'uniforms': {'versions': {str(v_light): 'game', str(v_dark): 'file:' + str(mine)}},
                  'ice': {'use': 'game'}},
             135: {'uniforms': {'versions': {'1': 'file:' + str(mine), '0': 'colours'}}},     # Canada: the classic cut
             91: {'ice': {'use': 'file:' + str(mine)}},                                       # the DEL's shared ice
             218: {'uniforms': {'versions': {'0': 'file:' + str(mine)}}}}                     # Pittsburgh's jerseys
    no_ice = []
    made = {m.art: m for m in looks.looks_from(R, edits, {}, {}, look_pack=pack, no_ice=no_ice)}
    assert made[utica].pack == () and made[utica].files == ((v_dark, False, str(mine)),) and made[utica].centre == 'game'
    # the classic cut cannot be made from the colours: the game's own stays, the player's picture goes on
    assert made[canada].style == 0 and made[canada].versions == () and made[canada].files == ((1, False, str(mine)),)
    # the DEL club keeps the pack's jersey; its home games show the DEL's shared ice, so the player's picture goes there
    # (0.31.0: a look of its own at art 197, nothing but the ice)
    assert no_ice == [] and made[R.T.get(91, 'artid')].centre == 'game'
    assert len(made[R.T.get(91, 'artid')].pack) == 1
    assert made[197].centre == str(mine) and made[197].versions == made[197].files == made[197].pack == ()
    assert made.get(23) is None                     # an edit kept for the Winter Classic team changes nothing


def test_pack_files_in_both_cuts_keep_the_discs_layout_and_install_once(disc, base_dir, tmp_path, make_look_pack, monkeypatch):
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    pack = make_look_pack(tmp_path, {27: ('nhl', 'TOR', 1, {'dark': (0, 40, 120)}, (0, 40, 120)),
                            135: ('national', 'CAN', 0, {'light': (240, 240, 240)}, None)})
    made = [m for m in looks.looks_from(R, {}, {}, {}, look_pack=pack) if m.art in (27, R.T.get(135, 'artid'))]
    maker = looks.Maker(disc, pack)
    for look in made:
        files = maker.files(look)
        assert sorted(files) == sorted(maker.paths(look))
        assert looks.Maker(disc, pack).files(look) == files                            # rule 4: deterministic
        for inner, data in files.items():
            if inner.endswith('.rpsgl'):
                mine, own = rpsgl.Rpsgl(data), rpsgl.Rpsgl(disc.render(inner))
                assert {k: (r['width'], r['height'], r['mips'], r['format']) for k, r in mine.rasters.items()} == \
                       {k: (r['width'], r['height'], r['mips'], r['format']) for k, r in own.rasters.items()}
        k = look.pack[0]
        name = f"{look.style}_{look.art}_{k.variant}"
        jersey = rpsgl.Rpsgl(files[looks.JERSEY.format(s=look.style, a=look.art, v=k.variant)])
        colour = jersey.image(f"jersey_{name}_cm").getpixel((512, 300))[:3]
        assert max(abs(a - b) for a, b in zip(colour, pack.picture(k.member).getpixel((32, 18)))) < 40
        if look.style == 0:                                    # the classic cut: the clean relief, its own lettering
            assert jersey.image(f"jersey_{name}_0_nm").tobytes() != \
                rpsgl.Rpsgl(disc.render(looks.JERSEY.format(s=0, a=look.art, v=k.variant))).image(f"jersey_{name}_0_nm").tobytes()
    # the player's own picture on a classic-cut version (Canada's dark): the disc's sizes, the clean relief, made the same way
    mine = tmp_path / 'mine.png'
    Image.new('RGB', (300, 300), (0, 200, 0)).save(mine)
    canada = R.T.get(135, 'artid')
    own = looks.Look(canada, looks.PLAIN_KIT, (None, None), '', (32, 32, 32), (), ((1, False, str(mine)),), 'game', (), 0)
    files = maker.files(own)
    assert sorted(files) == sorted(maker.paths(own)) and looks.Maker(disc, pack).files(own) == files
    jersey = rpsgl.Rpsgl(files[looks.JERSEY.format(s=0, a=canada, v=1)])
    disc_jersey = rpsgl.Rpsgl(disc.render(looks.JERSEY.format(s=0, a=canada, v=1)))
    assert {k: (r['width'], r['height'], r['format']) for k, r in jersey.rasters.items()} == \
           {k: (r['width'], r['height'], r['format']) for k, r in disc_jersey.rasters.items()}
    green = jersey.image(f"jersey_0_{canada}_1_cm").getpixel((512, 300))[:3]
    assert max(abs(a - b) for a, b in zip(green, (0, 200, 0))) < 8                # the compression's rounding only
    found, title = _fake_rpcs3(tmp_path, monkeypatch)
    n = looks.install_looks(found, title, made, lambda msg: None, look_pack=pack)
    assert n == sum(len(maker.paths(m)) for m in made)
    assert looks.install_looks(found, title, made, lambda msg: None, look_pack=pack) == 0          # installed already
    install.remove(lambda msg: None)
    assert install.installed() == 0


def _number_sheet():
    """A stand-in for a pack kit's own number sheet: a white letter, a white digit with a blue ring, a black sleeve digit,
    no marks (apostrophe, period ...)."""
    sheet = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    sheet.paste((240, 240, 240, 255), (6, 6, 25, 41))
    sheet.paste((20, 60, 200, 255), (8, 52, 155, 361))
    sheet.paste((240, 240, 240, 255), (16, 60, 147, 353))
    sheet.paste((10, 10, 10, 255), (7, 379, 40, 432))
    return sheet


def test_a_pack_kit_wears_its_own_number_sheet_in_both_cuts(disc, base_dir, tmp_path, make_look_pack):
    """The kit's own names, digits, rings and sleeve digits (Pittsburgh's black sleeve digits, Utah's white digits with a
    blue ring), the marks it lacks from the chassis, nothing between the glyph rows (no line under the number) and an
    even relief (no stitched edges of the chassis' digits)."""
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    sheet = _number_sheet()
    pack = make_look_pack(tmp_path, {27: ('nhl', 'TOR', 1, {'dark': (0, 40, 120)}, None),
                                     135: ('national', 'CAN', 0, {'light': (240, 240, 240)}, None)},
                          fonts={(27, 'dark'): sheet, (135, 'light'): sheet})
    maker = looks.Maker(disc, pack)
    made = [m for m in looks.looks_from(R, {}, {}, {}, look_pack=pack) if m.art in (27, R.T.get(135, 'artid'))]
    assert sorted(m.style for m in made) == [0, 1]
    for look in made:
        k = look.pack[0]
        assert k.font.startswith('f/')
        files = maker.files(look)
        name = f"{look.style}_{look.art}_{k.variant}"
        jersey = rpsgl.Rpsgl(files[looks.JERSEY.format(s=look.style, a=look.art, v=k.variant)])
        font = jersey.image(f"font_{name}_cm")
        for xy, colour in (((80, 200), (240, 240, 240)), ((10, 200), (20, 60, 200)), ((20, 400), (10, 10, 10)),
                           ((15, 20), (240, 240, 240))):
            px = font.getpixel(xy)
            assert px[3] == 255 and max(abs(a - b) for a, b in zip(px, colour)) < 12, (look.style, xy, px)
        alpha = font.getchannel('A')
        assert alpha.crop((0, 362, 512, 378)).getextrema()[1] < 16          # clear between the number and the sleeve digits
        assert alpha.crop((380, 0, 400, 46)).getextrema()[1] > 128           # the chassis' apostrophe: the sheet had none
        relief = jersey.image(f"font_{name}_nm")
        assert all(hi - lo <= 6 for lo, hi in relief.getextrema())
    assert looks.Maker(disc, pack).files(made[0]) == maker.files(made[0])     # rule 4: deterministic


def test_utah_seattle_and_vegas_wear_the_packs_kit_on_every_version_made_from_the_colours(base_dir, tmp_path,
                                                                                          make_look_pack):
    """Play Now dressed Utah in variant 0, which was made from the colours while the pack's kit sat on variants 3 / 4."""
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    pack = make_look_pack(tmp_path, {22: ('nhl', 'UTA', 1, {'dark': (0, 0, 0), 'light': (240, 240, 240)}, None)})
    kits = looks.pack_team(R, 22, pack).kits
    assert sorted((v, k.variant, k.light) for v, k in kits.items()) == [(0, 0, False), (1, 1, True), (3, 3, False), (4, 4, True)]
    assert kits[0].member == kits[3].member and kits[1].member == kits[4].member
    versions, _files, packed = looks._choose(22, looks.team_versions(R, 22), {}, kits)
    assert versions == [] and sorted(k.variant for k in packed) == [0, 1, 3, 4]
    # the player's own choice still wins
    versions, _files, packed = looks._choose(22, looks.team_versions(R, 22), {'0': 'colours'}, kits)
    assert versions == [(0, False)] and sorted(k.variant for k in packed) == [1, 3, 4]


# --- the Select Jerseys picture of a pack kit: the pack's own menu picture on the game's figure -------------------------
def _menu_shirt(colour=(0, 200, 0)):
    """A stand-in for the pack's menu picture of a kit: a shirt of one colour on a clear ground."""
    pic = Image.new('RGBA', (300, 340), (0, 0, 0, 0))
    pic.paste(colour + (255,), (40, 30, 260, 300))
    return pic


def test_the_menu_picture_puts_the_packs_shirt_on_the_games_black_figure(disc):
    maker = looks.Maker(disc)
    chassis, mask = maker.preview_of_chassis(False), maker.mask()
    head_x, (left, top, right, bottom) = looks.menu_frame(chassis, mask)
    assert left < head_x < right and 20 < top < bottom < 230
    figure = looks.menu_figure(chassis, mask)
    assert sorted(side for side, _glove, _at in figure.gloves) == [0, 1]           # both gloves, moved under the cuffs
    img = looks.menu_picture(chassis, mask, _menu_shirt(), figure)
    assert img.size == (256, 256) and img.mode == 'RGBA'
    assert img.getpixel((round(head_x), (top + bottom) // 2)) == (0, 200, 0, 255)   # the pack's shirt where the game's was
    head = img.getpixel((round(head_x), top // 2))
    assert head[:3] == (0, 0, 0) and head[3] > 150                                 # the head stays the game's black
    assert img.getpixel((5, 5))[3] == 0
    again = maker.thumbnail(27, 4, False, looks.PACK, menu=_menu_shirt())          # the editor's picture is the same
    assert again.tobytes() == img.tobytes() == maker.menu_preview(_menu_shirt()).tobytes()   # rule 4: deterministic


def _with_menus(pack, menus):
    """The look pack `pack` with pack menu pictures added ({member: picture}), opened again."""
    import io
    import zipfile
    from legacy_roster.art.lookpack import LookPack
    pack.zip.close()
    with zipfile.ZipFile(pack.path, 'a') as z:
        for name, pic in sorted(menus.items()):
            buf = io.BytesIO()
            pic.save(buf, 'WEBP', lossless=True)
            z.writestr(name, buf.getvalue())
    return LookPack.open(pack.path)


def test_a_pack_kits_menu_picture_is_the_packs_own_and_the_recoloured_chassis_only_without_one(disc, base_dir, tmp_path,
                                                                                              make_look_pack):
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    (tmp_path / 'plain').mkdir()
    (tmp_path / 'menu').mkdir()
    teams = {27: ('nhl', 'TOR', 1, {'dark': (0, 40, 120), 'light': (240, 240, 240)}, None)}
    plain = make_look_pack(tmp_path / 'plain', teams)
    menu = _with_menus(make_look_pack(tmp_path / 'menu', teams), {'m/27_dark.webp': _menu_shirt()})

    def toronto(pack):
        return next(m for m in looks.looks_from(R, {}, {}, {}, look_pack=pack) if m.art == 27)
    with_menu, without = toronto(menu), toronto(plain)
    kits = {k.variant: k for k in with_menu.pack}
    assert kits[4].menu.startswith('m/27_dark.webp#') and kits[3].menu is None          # the light kit has none
    assert all(k.menu is None for k in without.pack)
    assert looks.look_digest(with_menu) != looks.look_digest(without)                   # a menu picture redraws the look
    maker = looks.Maker(disc, menu)
    files = maker.files(with_menu)
    assert looks.Maker(disc, menu).files(with_menu) == files                            # rule 4: deterministic
    head_x, (_left, top, _right, bottom) = looks.menu_frame(maker.preview_of_chassis(False), maker.mask())
    middle = (round(head_x), (top + bottom) // 2)
    dark, light = (files[looks.PREVIEW.format(s=1, a=27, v=v)] for v in (4, 3))
    assert looks.preview_picture(dark).getpixel(middle) == (0, 200, 0, 255)            # the pack's own shirt, not recoloured
    plain_files = looks.Maker(disc, plain).files(without)
    r, g, b, _a = looks.preview_picture(plain_files[looks.PREVIEW.format(s=1, a=27, v=4)]).getpixel(middle)
    assert b > g and b > r                                                              # without one: the kit's blue
    assert plain_files[looks.PREVIEW.format(s=1, a=27, v=3)] == light                   # ... as the light kit has today
    assert {k: v for k, v in plain_files.items() if 'jerseys/' not in k} == \
        {k: v for k, v in files.items() if 'jerseys/' not in k}                         # the 3D files do not change


def test_a_pack_kit_wears_its_own_socks_and_pants_and_a_kit_without_them_is_as_before(disc, base_dir, tmp_path,
                                                                                     make_look_pack, monkeypatch):
    """Testers, 2026-11-03: the Leafs in black pants, Boston's socks with Utah's one low stripe. A kit with its own sock
    (s/<slot>_<role>.webp, the game's layout) and pants colours wears them; the light kit without keeps today's files."""
    from legacy_roster.roster import Roster
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    (tmp_path / 'plain').mkdir()
    (tmp_path / 'legs').mkdir()
    teams = {27: ('nhl', 'TOR', 1, {'dark': (0, 40, 120), 'light': (240, 240, 240)}, None)}
    sock = Image.new('RGB', (1024, 1024), (200, 20, 20))
    sock.paste((240, 240, 240), (0, 512, 1024, 1024))                  # red above, white below
    plain = make_look_pack(tmp_path / 'plain', teams)
    legs = make_look_pack(tmp_path / 'legs', teams, legs={(27, 'dark'): (sock, [(0, 40, 120), (240, 240, 240)])})

    def toronto(pack):
        return next(m for m in looks.looks_from(R, {}, {}, {}, look_pack=pack) if m.art == 27)
    with_legs, without = toronto(legs), toronto(plain)
    kits = {k.variant: k for k in with_legs.pack}
    assert kits[4].sock.startswith('s/27_dark.webp#') and kits[4].pants == ((0, 40, 120), (240, 240, 240))
    assert kits[3].sock is None and kits[3].pants is None
    assert all(k.sock is None and k.pants is None for k in without.pack)
    assert looks.look_digest(with_legs) != looks.look_digest(without)                  # installed looks redraw once
    maker = looks.Maker(disc, legs)
    files = maker.files(with_legs)
    assert looks.Maker(disc, legs).files(with_legs) == files                           # rule 4: deterministic
    socks = rpsgl.Rpsgl(files[looks.SOCK.format(s=1, a=27, v=4)]).image("sock_1_27_4_cm").convert('RGB')
    w, h = socks.size
    r, g, b = socks.getpixel((w // 2, h // 5))
    assert r > 120 and g < 60 and b < 60, (r, g, b)                                    # the pack's red, shaded
    assert min(socks.getpixel((w // 2, h * 3 // 5))) > 150                             # ... and its white below
    pants = rpsgl.Rpsgl(files[looks.PANT.format(s=1, a=27, v=4)]).image("pant_1_27_4_cm").convert('RGB')
    main = max(pants.getcolors(1 << 20))[1]
    assert main[2] > 80 and main[2] > main[0] + 40, main                               # Toronto's blue, not black
    plain_files = looks.Maker(disc, plain).files(without)
    for template in (looks.SOCK, looks.PANT):
        assert files[template.format(s=1, a=27, v=3)] == plain_files[template.format(s=1, a=27, v=3)]
        assert files[template.format(s=1, a=27, v=4)] != plain_files[template.format(s=1, a=27, v=4)]
    found, title = _fake_rpcs3(tmp_path, monkeypatch)
    assert looks.install_looks(found, title, [with_legs], lambda msg: None, look_pack=legs) > 0
    assert looks.install_looks(found, title, [with_legs], lambda msg: None, look_pack=legs) == 0   # installed already
    install.remove(lambda msg: None)


def test_path_art_reads_the_art_id_of_every_file_a_look_writes():
    for template in (looks.JERSEY, looks.PANT, looks.SOCK, looks.CENTRE, looks.ICE_PICTURE, looks.DECAL, looks.PREVIEW):
        assert looks.path_art(template.format(s=1, a=23, v=4)) == 23, template
    assert looks.path_art("rendering/puck/puck_900_cm.rpsgl") == 900
    assert looks.path_art("fe/ion/artassets/playerheads/p1/p1.big") is None


def test_looks_teams_names_the_teams_with_jerseys_ice_or_a_crest_picture():
    from legacy_roster import pipeline
    teams = {'5': {'uniforms': {'colours': {'primary': '#ff0000'}}}, '7': {'ice': {'arena': 'X'}}, '8': {'full': 'Name'},
             '230': {'kit': {'crest': 'file:C:/a.png'}}, '231': {'kit': {'crest': 'logo:3'}}}
    assert pipeline.looks_teams(teams) == {5, 7, 230}
    assert pipeline.looks_teams(None) == frozenset()


def test_the_editors_save_puts_in_the_edited_teams_look_and_leaves_other_teams_files(disc, base_dir, tmp_path, monkeypatch):
    """Testers of 0.85.0: jerseys and ice chosen in the Roster editor did not reach the game on Save (only an update with
    the photos put them in). Save now installs the edited teams' looks alone (a full install takes 18 minutes); another
    team's files stay, and a team set back to the game's own gets the game's files back (rule 10)."""
    from legacy_roster import layout as L
    from legacy_roster import pipeline
    from legacy_roster.editor import model
    from legacy_roster.roster import Roster
    raw = open(os.path.join(base_dir, 'SYS-DATA'), 'rb').read()
    R = Roster(raw)
    edm, tor = L.API_TO_SLOT['EDM'], L.API_TO_SLOT['TOR']
    found, title = _fake_rpcs3(tmp_path, monkeypatch)
    game = found.game_folder(title)
    tor_variant = looks.roster_versions(R, tor)[-1][0]
    other = [m for m in looks.looks_from(R, {tor: {'uniforms': {'colours': {'primary': '#00ff00'},
                                                                'versions': {str(tor_variant): 'colours'}}}}, {}, {})
             if m.art == looks.team_art(R, tor)[0]]
    looks.install_looks(found, title, other, lambda msg: None)        # an earlier update's Toronto look
    tor_files = [os.path.join(game, *p.split('/')) for p in looks.look_paths(other[0])]
    assert tor_files and all(os.path.exists(f) for f in tor_files)

    variant = looks.roster_versions(R, edm)[-1][0]
    teams = {str(edm): {'uniforms': {'colours': {'primary': '#ff00ff'}, 'versions': {str(variant): 'colours'}}}}
    pics = pipeline.Pictures(found, title, [title], own_only=True, looks_for=pipeline.looks_teams(teams),
                             season_looks=False)
    built = model.apply_edits(raw, {}, teams, 2026, art=pics)
    assert not built.problems
    art, n, _noted = pics.put_in(built, lambda msg: None)
    jersey = os.path.join(game, 'rendering', 'jersey', f'texlib_1_{looks.team_art(R, edm)[0]}_{variant}.rpsgl')
    assert n == 1 and os.path.exists(jersey)
    assert all(os.path.exists(f) for f in tor_files)                  # Toronto's files are left as they were

    pics = pipeline.Pictures(found, title, [title], own_only=True, looks_for={edm}, season_looks=False)
    built = model.apply_edits(raw, {}, {}, 2026, art=pics)           # Edmonton set back to the game's own
    pics.put_in(built, lambda msg: None)
    assert not os.path.exists(jersey)                                 # the game's own file is back (there was none)
    assert all(os.path.exists(f) for f in tor_files)
    install.remove(lambda msg: None)
