"""Coachella Valley and Henderson as art 900 and 901 on a roster for the patched game (0.50.4, lab round 48): the roster side
(gamepatch.art_fit / unart, verify), the files made from the donor clubs' (art/clubart.py) and the looks that paint them."""
import copy
import os
import re

import pytest
from PIL import Image

from legacy_roster import gamepatch, pipeline, schedule
from legacy_roster import layout as L
from legacy_roster.art import clubart, looks, rpsgl
from legacy_roster.roster import Roster
from legacy_roster.verify import verify

DISC = os.environ.get('LEGACY_ROSTER_DISC')


@pytest.fixture(scope='module')
def patched(base_bytes, data, pack):
    """(bytes of a roster made for the game patch, the roster it was made from)."""
    patch = copy.copy(data)
    patch.schedule, patch.leagues, patch.calendar = pack['schedule'], {'ahl': pack['leagues']['ahl']}, schedule.ALL_PATCH
    res = pipeline.build(base_bytes, patch, list(pipeline.CORE_STEPS) + [pipeline.SCHEDULE, 'ahl'], game_patch=True)
    out, problems, _ = pipeline.patch_roster(res, base_bytes, pack, patch.season_year)
    assert problems == []
    return out, res.data


def test_the_patch_roster_gives_the_two_clubs_art_ids_of_their_own_and_their_donors_jersey_rows(patched):
    out, plain = patched
    R, P = Roster(out), Roster(plain)
    assert [(R.T.get(s, 'artid'), R.T.get(s, 'BERR')) for s in (234, 235)] == [(900, 0), (901, 0)]
    assert [(P.T.get(s, 'artid'), P.T.get(s, 'BERR')) for s in (234, 235)] == [(20073, 1), (20081, 1)]
    assert gamepatch.check_art_fit(R) == [] and len(gamepatch.check_art_fit(P)) == 4
    for art, donor, variants, slot in ((900, 162, (3, 4), 234), (901, 141, (0, 1), 235)):
        rows, theirs = gamepatch.art_rows(R, art), gamepatch.art_rows(R, donor)
        assert sorted(r['TccF'] for r in rows) == list(variants) and all(r['gXCm'] == slot for r in rows)
        assert [dict(r, LQDG=0, gXCm=0) for r in rows] == [dict(r, LQDG=0, gXCm=0) for r in theirs if r['TccF'] in variants]
    assert R.f['wgjx'].cur_rec == P.f['wgjx'].cur_rec + 4
    assert looks.team_art(R, 234) == (900, 1) and [v for v, _l, _d in looks.team_versions(R, 234)] == [3, 4]
    assert looks.editable(R, 235) is None and looks.editable(P, 235) is not None


def test_art_fit_once_and_unart_put_every_byte_back(patched):
    out, plain = patched
    R = Roster(out)
    assert gamepatch.art_fit(R) == 0 and R.f.build() == out                  # a second run changes nothing
    gamepatch.unart(R)
    assert gamepatch.art_fit(R) == 6 and R.f.build() == out
    gamepatch.unart(R)
    assert [R.T.get(s, 'artid') for s in (234, 235)] == [L.OWN_ART[234], L.OWN_ART[235]]
    assert [R.T.get(s, 'BERR') for s in (234, 235)] == [1, 1] and R.f['wgjx'].cur_rec == Roster(plain).f['wgjx'].cur_rec
    assert gamepatch.unart(R) == 0
    assert gamepatch.unshifted(out) == plain or Roster(gamepatch.unshifted(out)).f['wgjx'].cur_rec == R.f['wgjx'].cur_rec


def _first_rows(W):
    first = {}
    for i in range(W.cur_rec):
        first.setdefault(W.get(i, 'LQDG'), i)
    return first


def test_a_table_an_older_update_filled_makes_room_from_this_seasons_thirds(patched):
    """0.92.0 left this season's Alternate rows room for 4 club rows (Coachella Valley, Henderson); since 0.95.0 the Vees need
    2 more. A tester's patched update stopped with "wgjx: table full (749)" (docs/notes/wgjx-full.md)."""
    out, _plain = patched
    R = Roster(out)
    gamepatch.unart(R)
    W = R.f['wgjx']
    own, first = W.cur_rec, _first_rows(W)
    need = len(gamepatch._club_rows_missing(R))
    added = []
    for art in sorted(first):                       # Alternate rows as looks.alternate_rows adds them, at the end
        if W.cur_rec >= W.max_rec - need + 2:       # 2 rows short, as the Vees' were
            break
        W.add_record(dict({f: W.get(first[art], f) for f in W.fields}, gZuU=2, MSFy=0, TccF=20, XOdd=20))
        added.append(art)
    dropped = []
    assert gamepatch.art_fit(R, dropped) and gamepatch.check_art_fit(R) == []
    assert W.cur_rec == W.max_rec and [art for _slot, art, _v in dropped] == added[::-1][:2]     # the last added first
    filled = R.f.build()
    gamepatch.unart(R)
    assert W.cur_rec == W.max_rec - need and W.cur_rec == own + len(added) - 2   # the roster's own rows are all there
    again = []
    assert gamepatch.art_fit(R, again) and again == [] and R.f.build() == filled              # the next update: the same


def test_a_table_full_of_the_rosters_own_rows_says_so(patched):
    out, _plain = patched
    R = Roster(out)
    gamepatch.unart(R)
    W = R.f['wgjx']
    row = {f: W.get(0, f) for f in W.fields}
    while W.cur_rec < W.max_rec:
        W.add_record(row)
    with pytest.raises(L.LayoutError, match='jersey versions is full'):
        gamepatch.art_fit(R)


def test_verify_allows_the_art_ids_on_the_patched_roster_only(patched, base_bytes):
    out, plain = patched
    source = Roster(base_bytes)
    assert not [p for p in verify(out, source, farm_patch=True)[0] if 'art id' in p or 'jersey rows' in p]
    stranger = Roster(plain)
    stranger.T.set(234, 'artid', 900)
    assert any('art id 900' in p for p in verify(stranger.f.build(), source)[0])        # not on an unpatched roster
    other = Roster(out)
    other.T.set(233, 'artid', 901)                                                       # another team with 901
    assert any('art id 901' in p for p in verify(other.f.build(), source, farm_patch=True)[0])
    broken = Roster(out)
    gamepatch.unart(broken)
    broken.T.set(234, 'artid', 900)
    assert any('jersey rows' in p for p in gamepatch.check_art_fit(broken))


# --- the files ----------------------------------------------------------------------------------------------------------
def test_a_path_of_art_900_is_read_from_the_donor_club_s_file():
    assert clubart.donor_path("rendering/jersey/texlib_1_900_3.rpsgl") == (900, 162, "rendering/jersey/texlib_1_162_3.rpsgl")
    assert clubart.donor_path("rendering/logo/texlib_901_1_0.rpsgl") == (901, 141, "rendering/logo/texlib_141_1_0.rpsgl")
    assert clubart.donor_path("rendering/jersey/texlib_1_1900_3.rpsgl") is None
    assert clubart.donor_path("rendering/jersey/texlib_1_22_3.rpsgl") is None
    assert clubart.extra_paths(22) == [] and len(clubart.extra_paths(900)) == 5
    assert clubart.NAME.format(a=901, v=1) in clubart.extra_paths(901)


@pytest.mark.skipif(not DISC, reason="needs LEGACY_ROSTER_DISC")
def test_the_donor_s_textures_are_renamed_to_the_new_art_id_and_keep_their_size():
    from legacy_roster.art.lab import Disc
    disc = Disc(DISC)
    alias = clubart.AliasDisc(disc)
    for art, donor, variant in ((900, 162, 3), (900, 162, 4), (901, 141, 0), (901, 141, 1)):
        for template in (looks.JERSEY, looks.PANT, looks.SOCK, looks.DECAL, clubart.NAME):
            new = template.format(s=1, a=art, v=variant)
            old = template.format(s=1, a=donor, v=variant)
            assert alias.has(new) and disc.has(old) and not disc.has(new)
            made, original = rpsgl.Rpsgl(alias.render(new)), rpsgl.Rpsgl(disc.render(old))
            assert len(made.data) == len(original.data) and made.header == original.header, new
            assert bytes(made.data[made.header:]) == bytes(original.data[original.header:])      # the pictures are the donor's
            assert set(made.rasters) == {n.replace(str(donor), str(art)) for n in original.rasters}, new
            assert all(str(art) in name and str(donor) not in name for name in made.rasters), made.rasters
            assert not re.search(clubart.number(donor).encode(), bytes(made.data[:made.header])), new
        assert alias.find(looks.PREVIEW.format(s=1, a=art, v=variant)) == disc.find(looks.PREVIEW.format(s=1, a=donor, v=variant))
    assert alias.render(looks.JERSEY.format(s=1, a=22, v=3)) == disc.render(looks.JERSEY.format(s=1, a=22, v=3))
    extra = clubart.extra_files(alias, 900)
    assert sorted(extra) == sorted(clubart.extra_paths(900))


# --- the looks ----------------------------------------------------------------------------------------------------------
@pytest.fixture
def crest(monkeypatch):
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    for x in range(8, 56):
        for y in range(8, 56):
            img.putpixel((x, y), (200, 16, 46, 255))
    monkeypatch.setattr(looks, '_logos', lambda link, pack, cache: (img, img))
    return img


def test_the_two_clubs_get_a_look_from_their_colours_and_their_crest_on_the_patched_roster(patched, crest):
    out, plain = patched
    R, P = Roster(out), Roster(plain)
    links = {234: 'crest:coachella', 235: 'crest:henderson'}
    made = {look.art: look for look in looks.looks_from(R, {}, links, {})}
    assert sorted(a for a in made if a in clubart.ARTS) == [900, 901]
    assert made[900].versions == ((3, True), (4, False)) and made[901].versions == ((0, True), (1, False))
    assert made[900].centre == 'make' and made[900].style == 1 and made[900].logos[0] is crest
    navy, red = L.OWN_COLOURS[234]
    assert made[900].kit == looks.kit_for(red, navy) and made[900].kit.home.body == navy      # dark: the main colour all over
    assert made[900].kit != made[901].kit
    assert not [look for look in looks.looks_from(P, {}, links, {}) if look.art in clubart.ARTS]     # not unpatched
    nothing = {look.art for look in looks.looks_from(R, {}, {}, {})}
    assert not nothing & set(clubart.ARTS)                                                              # no crest, no look
    mine = {234: {'uniforms': {'versions': {'3': 'game'}}}}
    again = {look.art: look for look in looks.looks_from(R, mine, links, {})}
    assert again[900].versions == ((4, False),)                                                          # the player's pick wins
    assert looks.look_digest(made[900]) != looks.look_digest(made[901])
    assert set(looks.look_paths(made[900])) >= set(clubart.extra_paths(900))


@pytest.mark.skipif(not DISC, reason="needs LEGACY_ROSTER_DISC")
def test_the_maker_paints_the_donor_clubs_files_in_their_colours_under_the_new_art_id(patched, crest):
    from legacy_roster.art.lab import Disc
    out, _plain = patched
    R = Roster(out)
    made = {look.art: look for look in looks.looks_from(R, {}, {234: 'crest:a', 235: 'crest:b'}, {})}
    maker = looks.Maker(Disc(DISC))
    for art in (900, 901):
        look = made[art]
        files = maker.files(look)
        assert sorted(files) == sorted(maker.paths(look)), set(files) ^ set(maker.paths(look))
        donor_variants = L.CLUB_DONOR[{900: 234, 901: 235}[art]][1]
        for variant in donor_variants:
            for template in (looks.JERSEY, looks.PANT, looks.SOCK, looks.DECAL):
                path = template.format(s=1, a=art, v=variant)
                assert path in files, path
                names = rpsgl.Rpsgl(files[path]).rasters
                assert names and all(str(art) in n for n in names), (path, list(names))
            assert looks.PREVIEW.format(s=1, a=art, v=variant) in files
        assert looks.CENTRE.format(a=art) in files
        assert all(str(art) in p for p in files)                        # nothing written under another club's art id
        assert set(clubart.extra_paths(art)) <= set(files)
