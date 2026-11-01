"""A custom team's look (custom_kit.py, edits.json `kit`) and the centre ice several teams share (looks.ice_group)."""
import os

from legacy_roster import custom_kit as K
from legacy_roster import layout as L
from legacy_roster import pipeline, verify
from legacy_roster.art import crests, looks
from legacy_roster.roster import Roster


def test_three_colours_paint_every_piece_but_the_crest_home_and_away():
    a, b, c = (10, 20, 30), (200, 0, 0), (0, 200, 0)
    out = K.fill(a, b, c)
    assert set(out) == {(p, v) for p in K.PIECES if p != K.CREST for v in (K.HOME, K.AWAY)}
    for (piece, _v), zones in out.items():
        assert len(zones) == len(K.PIECES[piece][1])
    assert out[(9, K.HOME)][0] == a and out[(9, K.AWAY)][0] == K.WHITE      # home in the main colour, away on white
    assert K.fill(a, b, c) == out


def test_coachellas_home_jersey_is_navy():
    navy = L.OWN_COLOURS[234][0]
    assert L.OWN_KIT[234][(9, 1)][0] == L.OWN_KIT[234][(9, 1)][4] == navy     # the body and the shoulders (lab round 37)


def test_write_puts_the_designs_colours_pieces_and_crest_in(base_bytes):
    R = Roster(base_bytes)
    kit = {'jersey': [3, 7], 'pants': 2, 'socks': 4, 'font': 1, 'colours': ['#102030', '#c0c0c0', '#ff8800'],
           'pieces': {'9/1': ['#000000'], '10/2': ['#010203', None, '#040506'], '99/1': ['#ffffff'], 'x': []},
           'crest': 'logo:3'}
    words, picture = K.write(R, 222, kit)
    assert picture is None and "crest" in words and "colours in detail" in words
    d = K.design(R, 222)
    assert d['jersey'] == [3, 7] and (d['pants'], d['socks'], d['font'], d['logo']) == (2, 4, 1, 3)
    assert d['colours'] == [(16, 32, 48), (192, 192, 192)]
    got = K.colours(R, 222)
    assert got[(9, 1)][0] == (0, 0, 0) and got[(9, 1)][1] == (192, 192, 192)     # the piece on top of the team colours
    assert got[(10, 2)] == [(1, 2, 3), (192, 192, 192), (4, 5, 6)]
    assert got[(9, 2)][0] == K.WHITE
    assert got[(11, 1)][:3] == got[(11, 2)][:3] == [(16, 32, 48), (192, 192, 192), (255, 136, 0)]   # the game's logo
    # values the game has no use for are left out: the roster keeps its own
    before = K.design(R, 223)
    assert K.write(R, 223, {'jersey': [9, 12], 'pants': 6, 'crest': 'logo:54'}) == ([], None)
    assert K.design(R, 223) == before


def test_typed_team_colours_repaint_a_plain_team_but_leave_the_hand_made_jerseys_alone(base_bytes):
    colours = ['#102030', '#c0c0c0', '#ff8800']
    R = Roster(base_bytes)
    K.write(R, 222, {'colours': colours})
    assert K.colours(R, 222)[(9, K.HOME)][0] == (16, 32, 48)            # the owner's first complaint: a colour changes the jersey
    # Coachella Valley: the colours made by hand (layout.OWN_KIT) stay when only colours are typed
    rows = K._rows(R, 234)
    for key, zones in L.OWN_KIT[234].items():
        K._paint(R, rows[key], zones)
    assert K.hand_made(K.colours(R, 234), 234) == set(L.OWN_KIT[234])
    K.write(R, 234, {'colours': colours})
    for key, zones in L.OWN_KIT[234].items():
        assert K.colours(R, 234)[key] == [tuple(z) for z in zones][:len(K.colours(R, 234)[key])], key
    again = R.f.build()
    K.write(R, 234, {'colours': colours})
    assert R.f.build() == again                                           # a second run changes nothing
    # "Paint everything" (kit 'all') repaints them as well
    K.write(R, 234, {'colours': colours, 'all': True})
    assert K.colours(R, 234)[(9, K.HOME)][0] == (16, 32, 48)
    # a piece the player set by itself still wins over everything
    K.write(R, 234, {'colours': colours, 'pieces': {'9/1': ['#000000']}})
    assert K.colours(R, 234)[(9, K.HOME)][0] == (0, 0, 0)


def test_a_kit_on_a_slot_of_the_games_own_roster_is_drawn_as_designed(base_bytes):
    source = Roster(base_bytes)
    source.T.set(236, 'jerseystyle', 0)         # the game's own roster: 0 on every custom slot (a plain jersey in the game)
    R = Roster(source.f.build())
    K.write(R, 236, {'colours': ['#102030', '#c0c0c0', '#ff8800']})
    assert R.T.get(236, 'jerseystyle') == K.DRAWN == 1
    assert K.problems(R, source) == []
    R.T.set(222, 'jerseystyle', 0)              # never back to plain, never on a league's team
    R.T.set(10, 'jerseystyle', 1)
    found = K.problems(R, source)
    assert len(found) == 2 and all("jersey style" in p for p in found)


def test_a_logo_another_teams_crest_is_drawn_on_is_never_taken(base_bytes):
    R = Roster(base_bytes)
    assert K.write(R, 222, {'crest': 'logo:72'}, reserved={72, 80}) == ([], None)
    # a crest picture keeps the team's own logo while no other team wears it, else takes the lowest free one
    assert K.free_logo(R, 222, {72, 80}) == K.logo_of(R.T.get(222, 'artid'))
    R.T.set(223, 'artid', R.T.get(222, 'artid'))
    worn = {R.T.get(s, 'artid') for s in range(R.T.cur_rec)}
    first_free = next(n for n in K.LOGOS if K.FIRST_ART + n not in worn)
    assert K.free_logo(R, 222, {72, 80}) == first_free
    assert K.free_logo(R, 222, {first_free}) != first_free


def test_verify_refuses_designs_logos_and_rows_the_game_does_not_have(base_bytes):
    source = Roster(base_bytes)
    R = Roster(base_bytes)
    assert K.problems(R, source) == []
    R.T.set(223, 'pantsstyle', 7)               # no such pants
    R.T.set(10, 'font', (R.T.get(10, 'font') + 1) % 6)      # an NHL team's design: not the program's to change
    R.T.set(224, 'artid', K.FIRST_ART + 54)     # logo 54 has no files
    found = K.problems(R, source)
    assert len(found) == 3 and any("pants 7" in p for p in found) and any("art id 20055" in p for p in found)
    R = Roster(base_bytes)
    E = R.f[K.TABLE]
    E.set(0, 'equipment', E.get(0, 'equipment') % 11 + 1)
    assert K.problems(R, source) == ["the custom teams' colour table lost or moved a row"]
    R = Roster(base_bytes)
    R.T.set(223, 'artid', R.T.get(222, 'artid'))
    found = K.problems(R, source, crests={222: R.T.get(222, 'artid')})
    assert len(found) == 1 and "would show on" in found[0]


def test_a_kit_edit_reaches_the_roster_and_the_crests_and_changes_nothing_twice(base_bytes, data, tmp_path):
    from PIL import Image
    mine = tmp_path / 'crest.png'
    Image.new('RGBA', (300, 300), (200, 30, 30, 255)).save(mine)
    teams = {'222': {'kit': {'jersey': [2, 5], 'colours': ['#112233', '#ddeeff', '#ff0000'], 'crest': 'file:' + str(mine)}},
             '223': {'kit': {'crest': 'logo:' + str(K.logo_of(Roster(base_bytes).T.get(222, 'artid')))}},  # 222's: taken
             '10': {'kit': {'jersey': [1, 1]}}}                     # not a custom team: nothing
    first = pipeline.build(base_bytes, data, team_edits=teams)
    assert first.ok, first.problems[:5]
    R = Roster(first.data)
    art = R.T.get(222, 'artid')
    assert K.design(R, 222)['jersey'] == [2, 5] and first.builder.crest_pictures == {222: 'file:' + str(mine)}
    assert first.builder.logos[222] == 'file:' + str(mine)
    assert all(R.T.get(s, 'artid') != art for s in range(R.T.cur_rec) if s != 222)
    assert any(r[1] == 'edit skipped' and r[2] == R.team_name(223) for r in first.log)
    assert R.T.get(10, 'jerseybackhome') == Roster(base_bytes).T.get(10, 'jerseybackhome')
    assert (222, art) in [(s, a) for s, a, _c in crests.crest_teams(R, first.builder.crest_pictures)]
    # a crest picture keeps the crest's colours (the window makes them from the picture: pieces 11/1, 11/2)
    assert list(crests.palette(R, 222)) == K.colours(Roster(base_bytes), 222)[(11, 1)][:3]
    again = pipeline.build(first.data, data, team_edits=teams)
    assert again.ok and again.data == first.data


def test_verify_refuses_a_crest_picture_another_team_wears(built):
    R = Roster(built.data)
    R.T.set(223, 'artid', R.T.get(222, 'artid'))
    found, _ = verify.verify(R.f.build(), Roster(built.data), crests={222: R.T.get(222, 'artid')})
    assert any("would show on" in p for p in found)


def test_shared_ice_groups(base_dir):
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    art, nations = looks.ice_group(R, 135)
    assert art == 501 and 133 in nations and len(nations) == 21
    assert looks.ice_group(R, 91)[0] == 197 and len(looks.ice_group(R, 91)[1]) == 14
    assert looks.ice_group(R, 220) == (255, [220, 221])
    assert looks.ice_group(R, 5) is None and looks.ice_group(R, 32) is None
    assert looks.ice_group(R, 216) is None              # the Winter Classic team plays on the Rangers' ice
    assert "every national team" in looks.ice_note(R, 140) and "DEL" in looks.ice_note(R, 95)
    assert looks.ice_note(R, 221).startswith("EASHL 1 and EASHL 2") and looks.ice_note(R, 32) is None


def test_a_picture_on_a_shared_ice_goes_to_the_groups_file_lowest_slot_first(base_dir, tmp_path):
    from PIL import Image
    R = Roster(os.path.join(base_dir, 'SYS-DATA'))
    mine, other = tmp_path / 'mine.png', tmp_path / 'other.png'
    for path in (mine, other):
        Image.new('RGB', (512, 512), (0, 200, 0)).save(path)
    edits = {140: {'ice': {'use': 'file:' + str(other)}}, 135: {'ice': {'use': 'file:' + str(mine)}},
             95: {'ice': {'use': 'logo'}}}                 # a shared ice takes only a picture of the player's own
    no_ice = []
    made = looks.looks_from(R, edits, {}, {}, no_ice=no_ice)
    shared = [m for m in made if m.art == 501]
    assert len(shared) == 1 and shared[0].centre == str(mine) and looks.look_paths(shared[0]) == [
        looks.CENTRE.format(a=501)]
    assert sorted(s for s, _why in no_ice) == [95, 140]
    assert all(m.centre == 'game' for m in made if m.art != 501)
