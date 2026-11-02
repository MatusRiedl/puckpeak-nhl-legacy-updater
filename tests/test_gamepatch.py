"""The game patch (gamepatch.py): the patch file, and the roster made for the year 2026 (cli year-test)."""
import datetime
import os
import re
import shutil
from collections import Counter
from types import SimpleNamespace

import pytest

from legacy_roster import calendartest, gamepatch, savedata, schedule, stock
from legacy_roster.roster import Roster


def test_the_patch_file_names_the_game_and_sends_the_year_to_its_own_code():
    text = gamepatch.patch_text()
    assert f"PPU-{gamepatch.EU_HASH}:" in text and "BLES02153: [ 01.00 ]" in text
    assert "- [ calloc, 0x00731d04, 5 ]" in text            # RPCS3's name for code_alloc
    lines = text.splitlines()
    at = next(n for n, line in enumerate(lines) if 'calloc' in line)
    assert [line.split(',')[2].split(']')[0].strip() for line in lines[at + 1:at + 6]] == \
        ['0x3804f826', '0x28000010', '0x3ba4000b', '0x41800008', '0x609d0000']   # the game's own word last
    assert gamepatch.hooks()[0] == (0x731d04, 0x609d0000)
    assert "- [ be32, 0x0040cb7c, 0x38c3000b ]" in text      # the season's label: the league year + 11
    assert "- [ be32, 0x002e2b98, 0x306307ea ]" in text      # GetSeasonYear: 2026 + the months
    assert "- [ be32, 0x0016320c, 0x3b23000b ]" in text
    assert "- [ be32, 0x003721a4, 0x3863fff5 ]" in text      # the age: the birth year + 11, as the league year counts it


def test_the_na_version_gets_the_same_entries_under_its_own_hash():
    yaml = pytest.importorskip('yaml')
    for teams in (False, True):
        loaded = yaml.safe_load(gamepatch.patch_text(teams=teams))
        eu, na = loaded[f"PPU-{gamepatch.EU_HASH}"], loaded[f"PPU-{gamepatch.NA_HASH}"]
        assert list(eu) == list(na)
        for name in eu:
            assert list(eu[name]['Games']['NHL Legacy']) == ['BLES02153']      # (PyYAML reads 01.00 as a number)
            assert list(na[name]['Games']['NHL Legacy']) == ['BLUS31540']
            assert eu[name]['Patch'] == na[name]['Patch']
    only_eu = gamepatch.patch_text(titles=['BLES02153'])
    assert gamepatch.NA_HASH not in only_eu and 'BLUS31540' not in only_eu


def test_the_players_entry_holds_the_lab_entries_changes_in_one_switch():
    yaml = pytest.importorskip('yaml')
    lab = yaml.safe_load(gamepatch.patch_text(teams=True))
    mine = yaml.safe_load(gamepatch.player_patch_text())
    for title, hash_ in (('BLES02153', gamepatch.EU_HASH), ('BLUS31540', gamepatch.NA_HASH)):
        entries = mine[f"PPU-{hash_}"]
        assert list(entries) == ([gamepatch.PLAYER_ENTRY] + [name for name, *_ in gamepatch.INTRO_ENTRIES]
                                 + [gamepatch.ONLINE_ENTRY, gamepatch.ONLINE_START_ENTRY])
        played = [gamepatch.YEAR_ENTRY] + [name for name, *_ in gamepatch.TEAM_STAGES]
        assert entries[gamepatch.PLAYER_ENTRY]['Patch'] == [p for name in played for p in lab[f"PPU-{hash_}"][name]['Patch']]
        assert list(entries[gamepatch.PLAYER_ENTRY]['Games']['NHL Legacy']) == [title]
        for name, *_ in gamepatch.INTRO_ENTRIES:
            assert entries[name] == lab[f"PPU-{hash_}"][name]
    addresses = [a for a, _ in gamepatch.hooks()]
    assert len(addresses) == len(set(addresses))        # no two entries change the same word: their order is free
    assert '(test)' not in gamepatch.player_patch_text()


def test_update_101_gets_the_same_patch_at_its_own_addresses():
    """Update 1.01 is one program for EU and NA (its own PPU hash): one block naming both, the same entries and words, every
    place moved as patch101.py says (tools/port_patch.py, checked against the program by tools/audit_patch.py)."""
    yaml = pytest.importorskip('yaml')
    from legacy_roster import patch101
    assert set(patch101.ADDRESSES) == gamepatch.port_addresses()
    moves = [b - a for a, b in patch101.ADDRESSES.items()]
    assert min(moves) >= 0 and max(moves) <= 0x2030 and len(set(patch101.ADDRESSES.values())) == len(moves)
    mine = yaml.safe_load(gamepatch.player_patch_text())
    assert list(mine) == ["Version", f"PPU-{gamepatch.EU_HASH}", f"PPU-{gamepatch.NA_HASH}", f"PPU-{gamepatch.UPDATE_HASH}"]
    old, new = mine[f"PPU-{gamepatch.EU_HASH}"], mine[f"PPU-{gamepatch.UPDATE_HASH}"]
    assert list(old) == list(new)
    for name in new:
        assert list(new[name]['Games']['NHL Legacy']) == ['BLES02153', 'BLUS31540']
        if name == gamepatch.ONLINE_START_ENTRY:    # the start word's own address in 1.01 (tools/audit_patch.py checks it)
            assert [p[1:] for p in new[name]['Patch']] == [[w[0], w[2]] for w in gamepatch.ONLINE_START_101]
            continue
        if name == gamepatch.ONLINE_ENTRY:      # update 1.01 has its own two words (checked in its own test)
            continue
        assert len(old[name]['Patch']) == len(new[name]['Patch'])
        for (kind, a, word), (kind_101, a_101, word_101) in zip(old[name]['Patch'], new[name]['Patch']):
            assert kind == kind_101 and a_101 == gamepatch.at(a, '01.01')
            assert word == word_101 or kind == 'be32' and (a in gamepatch.VALUE_ADDRESSES or word >> 26 in (15, 16, 18, 24, 12))
    text = gamepatch.player_patch_text()
    assert "        BLES02153: [ 01.01 ]\n        BLUS31540: [ 01.01 ]" in text
    only_na = gamepatch.player_patch_text(['BLUS31540'])
    assert gamepatch.UPDATE_HASH in only_na and 'BLES02153' not in only_na
    assert gamepatch.player_patch_text(versions=('01.00',)).count('PPU-') == 2


def test_the_ported_words_go_where_the_games_went():
    at = gamepatch.at
    # a branch the patch writes (the news entry's b): the same place in its function, which moved with it
    assert gamepatch.ported_word(0x7e8d58, 0x480004d8, '01.01') == 0x480004d8
    target = gamepatch._target(0x7e8d58, 0x480004d8)
    word = gamepatch.ported_word(0x7e8d58, 0x480004d8, '01.01')
    assert gamepatch._target(at(0x7e8d58, '01.01'), word) == at(target, '01.01')
    # the login entry's function descriptors, and data words that are numbers
    assert gamepatch.ported_word(0x1cd411c, 0x020e9d80, '01.01') == at(0x020e9d80, '01.01')
    assert gamepatch.ported_word(0x1ab0688, 220, '01.01') == 220
    # our code calls the moved functions: lis + ori builds the 1.01 address, the dollars in the cap code stay
    skip = dict(gamepatch.caves())[0x1283bc]
    ported = gamepatch.ported_code(skip, '01.01')
    built = [(hi & 0xffff) << 16 | lo & 0xffff for (hi, _), (lo, _) in zip(ported, ported[1:])
             if hi >> 26 == 15 and lo >> 26 == 24]
    assert at(0x3d7770, '01.01') in built and 0x3d7770 not in built and at(gamepatch.LIST_END, '01.01') in built
    cap = next(code for a, code in gamepatch.caves() if a == 0x4a7240)
    assert gamepatch.ported_code(cap, '01.01') == cap
    assert gamepatch.ported_code(skip) == skip


def test_only_the_games_own_years_move():
    assert [gamepatch.year_of(y) for y in (1987, 2009, 2010, 2015, 2016, 2025, 2026, 2037)] == \
        [1987, 2009, 2021, 2026, 2027, 2036, 2026, 2037]
    assert gamepatch.year_of(gamepatch.year_of(2015)) == 2026          # a date joined twice does not drift


def test_the_year_shift_makes_ages_right_on_the_2026_calendar(base_bytes):
    R = Roster(base_bytes)
    P = R.P
    def row(first, last):
        return next(i for i in range(P.cur_rec) if P.get(i, 'RMbQ') == last and P.get(i, 'PedH') == first)
    crosby = row('Sidney', 'Crosby')
    before = [P.get(crosby, f) for f in gamepatch.GAME_YEARS]
    assert gamepatch.year_shift(R, stale=True)
    assert P.get(crosby, 'dnFq') + 1900 == 1987 - 11                # born 1987, on the league's clock: 39 in 2026 (2015)
    # undrafted, the game's portrait: the community updated Krug and Goodrow (lab round 25 made them ten years older), not Fiddler
    assert [P.get(row(f, l), 'dnFq') + 1900 + 11 for f, l in (('Torey', 'Krug'), ('Barclay', 'Goodrow'),
                                                             ('Vernon', 'Fiddler'))] == [1991, 1993, 1980]
    assert [P.get(crosby, f) for f in gamepatch.GAME_YEARS] == before    # contract years: the league's clock already
    picks = R.f['vaHq']
    assert {picks.get(i, 'dnFq') for i in range(picks.cur_rec)} == set(range(126, 132))
    assert gamepatch.check_years(R, 2026) == []
    gamepatch.year_shift(R, stale=False)                            # twice: the picks are eleven years off (lab round 18)
    assert "draft picks of other years than 2026-2031: [2037, 2038, 2039, 2040, 2041, 2042]" in gamepatch.check_years(R, 2026)


def test_the_year_test_saves_a_roster_and_the_patch_file(tmp_path, base_dir, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    monkeypatch.setenv('HOME', str(tmp_path))
    folder = str(tmp_path / 'savedata')
    shutil.copytree(base_dir, os.path.join(folder, 'BLES021530202'))
    slot = savedata.list_rosters(folder)[0]
    before = open(slot.sys_data, 'rb').read()
    said = []
    made = calendartest.year_test(folder, slot, said.append)
    assert made.name == "YEAR 2026"
    assert open(slot.sys_data, 'rb').read() == before                                    # the roster it started from stays
    assert gamepatch.check_years(Roster(open(made.sys_data, 'rb').read()), 2026) == []
    text = chr(10).join(said)
    assert 'Sidney Crosby born 1987' in text and 'NHL_Legacy_year_2026_patch.yml' in text
    patch = next(line for line in said if '.yml' in line).split('drop the file ')[1].split(' on that window')[0]
    assert open(patch, encoding='utf-8').read() == gamepatch.patch_text()


def test_the_32_team_test_saves_a_roster_for_the_patched_farm_league(tmp_path, base_dir, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    monkeypatch.setenv('HOME', str(tmp_path))
    folder = str(tmp_path / 'savedata')
    shutil.copytree(base_dir, os.path.join(folder, 'BLES021530202'))
    slot = savedata.list_rosters(folder)[0]
    source = Roster(open(slot.sys_data, 'rb').read())
    said = []
    made = calendartest.team32_test(folder, slot, said.append)
    assert made.name == calendartest.TEAMS_NAME
    R = Roster(open(made.sys_data, 'rb').read())
    assert gamepatch.check_farm(R) == [] and gamepatch.check_years(R, 2026) == []
    assert gamepatch.check_divisions(R) == [] and gamepatch.check_divisions(source) == [
        "NHL slot 30 is in group 2 / 2, not in a division", "NHL slot 31 is in group 1 / 1, not in a division",
        "NHL slot 22 is not named Utah Mammoth", "NHL slot 30 is not named Seattle Kraken",
        "NHL slot 31 is not named Vegas Golden Knights",                                 # the game's Arizona and All-Star names
        "division 3 has 7 teams, not 8", "division 4 has 7 teams, not 8"]                # the All-Star teams' groups
    assert [[R.T.get(n, f) for f in ('JkmY', 'ITNQ', 'nnsx', 'RPbr')] for n in (22, 30, 31)] == [
        ['Utah Mammoth', 'Utah', 'UTA', source.T.get(22, 'RPbr')], ['Seattle Kraken', 'Seattle', 'SEA', source.T.get(30, 'RPbr')],
        ['Vegas Golden Knights', 'Vegas', 'VGK', source.T.get(31, 'RPbr')]]   # the art code (the text file's keys) stays
    assert [(R.T.get(n, 'uTwO'), R.T.get(n, 'KMGC')) for n in (22, 30, 31)] == [(1, 4), (1, 3), (1, 3)]
    same = (22, 30, 31) + gamepatch.ALL_STAR_SLOTS + tuple(range(32, 62)) + tuple(gamepatch.LEAGUE_SLOTS)   # 32-61: the AHL's 2026-27
    # divisions; 234 / 235 in the AHL's Pacific (stage Y)
    assert all(R.T.get(n, f) == source.T.get(n, f) for n in range(R.T.cur_rec) if n not in same for f in ('uTwO', 'KMGC'))
    assert gamepatch.check_all_star(R) == [] and len(gamepatch.check_all_star(source)) == 4      # 2 places, 2 tables
    assert [(R.T.get(n, 'JkmY'), R.T.get(n, 'uTwO')) for n in gamepatch.ALL_STAR_SLOTS] == [
        ('Eastern All-Stars', 2), ('Western All-Stars', 1)]                    # as the game's own All-Star slots 30 / 31
    assert [[R.T.get(n, f) for f in ('artid', 'arenaid', 'tunnel', 'spotlight', 'audioid')] for n in gamepatch.ALL_STAR_SLOTS] == [
        [30, 30, 30, 30, 1378], [31, 30, 30, 30, 1323]]            # not EASHL's art 255 (the online crest): it never loads offline
    own = [(m, d, h) for m, d, h, a in schedule.read(R) if h == a]
    assert len(own) == 1 and own[0][0] in (0, 1) and not [g for g in schedule.read(R) if g[:2] == own[0][:2] and g[2] != g[3]]
    assert schedule.read(R, schedule.FAVOURITE) == schedule.read(R)
    later = schedule.read(R, gamepatch.FUTURE_TABLE)                   # every later season's calendar (stage R), a week later
    assert later == gamepatch.future_rows(schedule.read(R)) and len(later) == len(schedule.read(R))
    assert [g[2:] for g in later] == [g[2:] for g in schedule.read(R)] and (1, 28) not in {g[:2] for g in later}
    opener, moved = (datetime.date(2026, m + 1, d + 1) for m, d, *_ in (schedule.read(R)[0], later[0]))
    assert (moved - opener).days == 7 and moved.weekday() == opener.weekday() and moved >= datetime.date(2026, 10, 3)
    assert gamepatch.check_future(R) == [] and gamepatch.check_future(source) != []
    plain = Roster(R.f.build())                                         # the calendar as it is: season 2's preseason
    F = plain.f[gamepatch.FUTURE_TABLE]                                 # starts before the new year (round 27)
    for i, (month, day, _h, _a) in enumerate(schedule.read(R)):
        F.set(i, schedule.ROW['month'], month)
        F.set(i, schedule.ROW['day'], day)
    assert gamepatch.check_future(plain) == ["the next seasons' calendar (nhlfutureschedule) is not the 32-team calendar "
                                             "7 days later"]
    assert gamepatch.check_games(R) == [] and len(gamepatch.check_games(source)) == 20            # 84 games, room for them
    assert [R.f[t].max_rec for t in ('ihmS', 'Iwiq', 'byED')] == [1345, 1431, 1345] and len(schedule.read(R)) == 1345
    assert [source.f[t].max_rec for t in ('ihmS', 'byED')] == [1291, 1291]          # the game's own room without the patch
    assert (source.f.section_size, R.f.section_size) == (gamepatch.SAVE_SECTION, gamepatch.SECTION_SIZE)  # stage S's save
    assert len(open(made.sys_data, 'rb').read()) == 0x2C + gamepatch.SECTION_SIZE == stock.SAVE_SIZE + 2 * 54 * 8
    short = Roster(R.f.build())
    short.f.resize(gamepatch.SAVE_SECTION)
    assert gamepatch.check_games(short) == [f"the roster's save section has {gamepatch.SAVE_SECTION} bytes, not "
                                            f"{gamepatch.SECTION_SIZE} (the patched game takes it for a damaged save)"]
    assert sum(line.startswith('    All-Star game: ') and 'Eastern All-Stars v Western All-Stars' in line for line in said) == 1
    farm = {n: R.T.get(n, 'TxsC') - 1 for n in range(32)}
    assert farm[30] == farm[31] == -1                                  # the patch gives Seattle and Vegas their farm keys
    assert {n: f for n, f in farm.items() if n < 30} == {n: source.T.get(n, 'TxsC') - 1 for n in range(30)}
    assert sorted(f for n, f in farm.items() if n < 30) == list(range(32, 62))     # 30 clubs, each its own farm club
    A = R.f['AJKN']
    places = Counter(t for i in range(A.cur_rec) for t in (A.get(i, 'qkhY'), A.get(i, 'rOMv')))
    assert A.cur_rec == 1152 and set(places.values()) == {72} and sorted(places) == list(range(32))   # the AHL's own
    assert [R.T.get(s_, 'KMGC') for s_ in (60, 55, 42, 35)] == [13, 13, 11, 11]    # Abbotsford, Tucson Pacific; Cleveland,
    assert [gamepatch.league_of(R, s_) for s_ in (234, 235)] == [(1, 7, 8, 13)] * 2     # Hamilton North; Coachella /
    assert [gamepatch.league_of(source, s_) for s_ in (234, 235)] == [(13, 48, 48, 48)] * 2   # Henderson AHL Pacific
    assert gamepatch.check_league_fit(R) == [] and len(gamepatch.check_league_fit(source)) == 2
    assert {home for _m, _d, home, _a in schedule.read(R)} == set(range(32))           # Seattle and Vegas play at home
    assert sum(line.startswith('    Farm league: 32 AHL clubs, 1152 games') for line in said) == 1
    assert gamepatch.check_rights(R) == [] and R.P.field('WBbd').bits == gamepatch.RIGHTS_BITS     # Vegas fits (round 42)
    for farm, nhl in ((234, 30), (235, 31)):            # Coachella / Henderson hold Seattle's / Vegas's players
        own = [prow for _i, prow, *_ in R.team_roster(farm) if R.P.get(prow, 'WBbd') == nhl + 1]
        assert len(own) >= sum(gamepatch.FARM_DEPTH.values())
        assert all(R.P.get(prow, 'GDhI') and R.P.get(prow, 'dhKk') and R.P.get(prow, 'contractis2way') for prow in own)
    dressed = [sum(1 for x in r_.team_roster(31) if x[1] is not None) for r_ in (R, source)]
    assert dressed[0] <= dressed[1]                                                # Vegas: no farm depth added to it
    thin = Roster(R.f.build())
    for _i, prow, *_ in thin.team_roster(235):
        if thin.P.get(prow, 'aljv') == 4:
            thin.P.set(prow, 'WBbd', 0)                                            # Henderson's goalies: nobody's
    assert gamepatch.check_rights(thin) == ["NHL slot 31's farm club (slot 235) holds only 0 G (at least 1) of its players"]
    five = Roster(R.f.build())
    assert gamepatch.rights_narrow(five) > 0 and five.P.field('WBbd').bits == 5     # unpatch_roster: Vegas's rights go
    assert not any(five.P.get(prow, 'WBbd') > 31 for prow in range(five.P.cur_rec))
    assert gamepatch.check_rights(five)[0].startswith("player rights (cPbu.WBbd) have 5 bits")
    assert gamepatch.rights_wide(five) and gamepatch.rights_fit(five, calendartest.datasource.load_pack(offline=True)[
        'leagues']['ahl']['teams'], 2026) > 0 and gamepatch.check_rights(five) == []
    again = Roster(R.f.build())
    assert gamepatch.rights_fit(again, calendartest.datasource.load_pack(offline=True)['leagues']['ahl']['teams'], 2026) == 0
    assert gamepatch.farm_fit(again, [[d, h, a_] for d, h, a_ in calendartest.datasource.load_pack(offline=True)[
        'ahl_schedule']]) == 1152 and again.f.build() == R.f.build()      # a second run changes nothing
    gamepatch.future_fit(again)
    gamepatch.section_fit(again)
    assert gamepatch.league_fit(again) == 0 and again.f.build() == R.f.build()
    from legacy_roster.verify import verify
    moved = Roster(R.f.build())
    moved.T.set(233, 'jjMx', 1)                                       # any other custom team: never into a league
    assert "changed league" in " ".join(verify(moved.f.build(), source, farm_patch=True)[0])
    assert "changed league" not in " ".join(verify(R.f.build(), source, farm_patch=True)[0])
    back = Roster(R.f.build())
    assert gamepatch.unleague(back) == 2 and gamepatch.league_fit(back) == 2 and back.f.build() == R.f.build()
    assert "changed league" in " ".join(verify(R.f.build(), source)[0])     # the AHL only on a roster for the patch
    disc = os.environ.get('LEGACY_ROSTER_DISC')
    if disc:                       # the game's database carries this roster's next seasons' calendars (lab round 27)
        meta = gamepatch.fit_meta(gamepatch.disc_meta(disc))
        db = gamepatch.fit_db(gamepatch.disc_db(disc), meta, R)
        assert gamepatch.check_db(db, meta, R) == [] and gamepatch.fit_db(db, meta, R) == db
        made = SimpleNamespace(f=gamepatch._db(db))
        assert schedule.read(made, 'byED') == schedule.read(R, 'byED') and schedule.read(made, 'AJKN') == schedule.read(R, 'AJKN')
        assert [(made.f[t].cur_rec, made.f[t].max_rec) for t in ('byED', 'AJKN')] == [(1345, 1345), (1152, 1180)]
    patch = next(line for line in said if '.yml' in line).split('drop the file ')[1].split(' on that window')[0]
    assert open(patch, encoding='utf-8').read() == gamepatch.patch_text(teams=True)


def test_the_32_team_entries_change_only_numbers_and_never_one_address_twice():
    assert gamepatch._li(4, 7) == 0x38800007 and gamepatch._stw(4, 0x8c, 1) == 0x9081008c   # the game's own encodings
    addrs = [a for a, _ in gamepatch.hooks()]
    assert len(addrs) == len(set(addrs))
    for a, old, new, why in gamepatch.writes():
        assert new == gamepatch.NOP or (old ^ new) & 0xffff0000 == 0 or a in gamepatch.OTHER_INSTRUCTIONS, hex(a)
        assert old != new and why
    a = dict((addr, new) for addr, _, new, _ in gamepatch.STAGE_A)
    assert a[0x3c5f1c] & 0xffff == 32 * 0x14c + 0x24        # 32 money records, 32 flags (+ room), the word after them
    assert a[0x31b958] & 0xffff == 0x3e4c + 32
    b = [(old & 0xffff, new & 0xffff) for _, old, new, _ in gamepatch.STAGE_B]
    assert all(new == 0x5704 for old, new in b if old == 0x208)       # list A at the League's new end, room for 32 words
    assert all(new == 0x5784 for old, new in b if old == 0x284) and 0x5784 - 0x5704 == 32 * 4
    assert all(new == 0x5804 for old, new in b if old == 0x304) and 0x5804 + 32 * 4 == gamepatch.LEAGUE_SIZE
    assert (0x5704, 0x5884) in b and (0x5784, 0x5904) in b               # League and LeagueManager grow by the three lists
    assert 0x304 + 30 * 4 == 0x37c                                       # list C's 30 words end where the fields begin
    c = dict((addr, new & 0xffff) for addr, _, new, _ in gamepatch.STAGE_C)
    assert c[0x27fc04] == len(gamepatch.FARM_SLOTS) == 32 and c[0x288a1c] == 4 + 32 * 300
    assert not {a for a, *_ in gamepatch.STAGE_C} & set(range(0x22fb2c, 0x22fe30))   # the farm list is stage L's
    caves = {addr: code for addr, _, code, _ in gamepatch.STAGE_L_CAVES + gamepatch.STAGE_M_CAVES}
    for at, reg in ((0x22fbb8, 27), (0x22fda4, 28)):                      # farm number -> slot, place = number - 32
        assert [_run(caves[at], {reg: n})[0][4] for n in range(32, 64)] == list(gamepatch.FARM_SLOTS)
    assert list(gamepatch.FARM_SLOTS[30:]) == [234, 235] and gamepatch.FARM_PLACE[234] == 30
    divisions = [slots for *_, slots in gamepatch.FARM_DIVISIONS]
    assert sorted(s_ for slots in divisions for s_ in slots) == sorted(gamepatch.FARM_SLOTS)   # every club once
    l_ = dict((addr, new & 0xffff) for addr, _, new, _ in gamepatch.STAGE_L)
    for (count_at, _, at, own, disp), slots in zip(gamepatch._FARM_FILLS, divisions):
        reg, mem = _run(caves[at], {1: 0x1000}, {0x1000 + disp: 0x8000})
        assert l_[count_at] == len(slots) and [mem[0x8000 + 4 * k] for k in range(len(slots))] == list(slots)
        assert caves[at][-1][0] == own and len(mem) == len(slots) + 1   # only the division's own list; the game's word
    assert {g_[1] for g_ in gamepatch.FARM_DIVISIONS[:2]} == {8} and {g_[1] for g_ in gamepatch.FARM_DIVISIONS[2:]} == {9}
    m = dict((addr, new & 0xffff) for addr, _, new, _ in gamepatch.STAGE_M)
    assert all(v == 64 for a, v in m.items() if a != 0x27bac4) and m[0x27bac4] == 52    # 52: Chicago Wolves' slot
    for at, counter in ((0x27b9d8, 24), (0x27ba78, 23)):     # a club's farm key: its slot; none: its key + 32
        assert _run(caves[at], {4: 45, counter: 17})[0][4] == 45
        assert [_run(caves[at], {4: -1, counter: key + 1})[0][4] for key in (30, 31)] == [62, 63]
    assert [_run(caves[0x27d0b8], {6: slot})[0][6] for slot in (0, 29, 32, 61, 234, 235)] == [-2, 27, 32, 61, 62, 63]
    d = dict((addr, new & 0xffff) for addr, _, new, _ in gamepatch.STAGE_D)
    assert d[0xdca44] == gamepatch.SIM_SIZE + 32 * 4 and gamepatch.SIM_LIST_B >= 0x2b0 + 32 * 4   # list B at the new end
    moved = {old & 0xffff: new & 0xffff for _, old, new, _ in gamepatch.STAGE_D}
    assert moved[0x258] + 32 <= moved[0x276] and 32 * 0x14 <= moved[0x258]  # 32 records, then 32 bytes, then the fields
    assert moved[0x282] + moved[0xffff] == 0x282 + 0xffff                  # the table ends where it did
    assert 0x94 + 32 * 4 <= 0x118 and moved[0x110] + 8 <= 0x80             # a day's stack table of 32, its counter apart
    for addr, old, code, _ in gamepatch.STAGE_D_CAVES:                    # list B's three users: + 0x10000 - 0x5ac
        assert code[0][0] >> 16 in (0x3c7f, 0x3c63) and code[0][0] & 0xffff == 1
        assert code[1][0] & 0xffff == (gamepatch.SIM_LIST_B - 0x10000) & 0xffff and old & 0xffff == 0x328
    e = dict((addr, new) for addr, _, new, _ in gamepatch.STAGE_E)
    assert e[0x3ddc74] == gamepatch._li(7, 32)                            # home 30 / 31 is Seattle / Vegas, not All-Star
    f = dict((addr, new) for addr, _, new, _ in gamepatch.STAGE_F)
    assert f[0x129b44] == gamepatch._li(4, 32)                            # the favourite list counts teams below 32
    assert {f[a] & 0xffff for a in (0x12710c, 0x127118, 0x127130)} == {32}  # and puts teams 0-31 first
    g = {addr: (old, new) for addr, old, new, _ in gamepatch.STAGE_G}
    frame = gamepatch.PICK_FRAME + gamepatch.PICK_MORE
    assert g[0x2dd1fc][1] == 0xf8210001 | (-frame & 0xfffc) and g[0x2dd590][1] == 0x38210000 | frame   # stdu / addi r1
    assert frame - 0x80 - 32 * 200 == 0x1830 - 0x80 - 30 * 200 >= 8 * 8   # 32 teams of 200 bytes, then the 8 saved registers
    for addr, (old, new) in g.items():                                   # every save slot moves up by the two teams
        if old >> 26 in (58, 62) and old & 0x1f0000 == 0x10000 and old & 3 == 0:
            assert (new & 0xfffc) - (old & 0xfffc) == gamepatch.PICK_MORE, hex(addr)
    assert len(g) == 20
    h = {addr: (old, new) for addr, old, new, _ in gamepatch.STAGE_H}
    assert h[0x3bc428][1] == gamepatch._li(3, 32 * 12) and h[0x3bc448][1] == gamepatch._li(4, 32 * 12)  # 32 records of 12
    assert h[0x3bc53c][1] & 0xffff == 32                                  # each gets its team number
    i = {addr: (old, new) for addr, old, new, _ in gamepatch.STAGE_I}
    rows = gamepatch.CALENDAR_ROWS
    assert rows >= 1350 + 4 * 28 and rows * 0x1c <= 0xffff                # the copy + the preseason; fits ori's immediate
    assert i[0x2849f0][1] == 0x60630000 | rows * 0x1c and i[0x284a18][1] == gamepatch._li(5, rows)
    k = {addr: new for addr, _, new, _ in gamepatch.STAGE_K}
    assert k[0x3c4084] & 0xffff == k[0x3c4b84] & 0xffff == 32 and k[0x3c4408] & 0xffff == 7 * 32   # 32 teams, 7 rounds
    assert k[0x228050] & 0xffff == 32 and gamepatch.META_ROWS['leaguedraftpick'] == 6 * 7 * 32     # a Season's picks fit
    assert k[0x3c4e98] & 0xffff == k[0x3c4eb4] & 0xffff == 16 and k[0x3c5a9c] & 0xffff == 16 * 4  # 16 + 16 playoff teams
    assert 0x88 + 16 * 4 == 0xc0 + 2 * 4                  # the lottery's 15th and 16th lie on the first playoff record,
    cave = dict((addr, code) for addr, _, code, _ in gamepatch.STAGE_K_CAVES)   # so round 1 takes them right after the draw
    assert [w & 0xffff for w, _ in cave[0x3c50d4][2:6]] == [0xc0, 0x38, 0xc4, 0x3c] and k[0x3c5a34] == gamepatch._li(7, 14)
    odds = gamepatch.LOTTERY_ODDS
    assert len(odds) == 16 and sum(odds) == 1000 and list(odds) == sorted(odds, reverse=True)
    won = [_run_draw(cave[0x3c4f0c], drawn) for drawn in range(1000)]
    assert all(r5 == 0 for _, r5 in won)                  # the game's cmpwi r5,250 / blt then takes the drawn place
    assert [sum(place == n for place, _ in won) for n in range(16)] == list(odds)
    assert set(gamepatch.OTHER_INSTRUCTIONS) <= set(k) | {a for a, *_ in gamepatch.STAGE_Q} | {a for a, *_ in gamepatch.YEAR_LABELS} \
        | {a for a, *_ in gamepatch.STAGE_U} | {a for a, *_ in gamepatch.INTRO} | {a for a, *_ in gamepatch.STAGE_X} \
        | {a for a, *_ in gamepatch.STAGE_Y} | {a for a, *_ in gamepatch.NEWS}
    assert all(code[-1][0] == old for _, old, code, _ in gamepatch.STAGE_K_CAVES)   # each ends with the game's own word
    room = {addr: (old, new) for addr, old, new, _ in gamepatch.STAGE_S}     # data: a roster table's room, not code
    assert room == {a: (1291, schedule.PATCH_ROWS) for a in gamepatch.ROOM_WORDS} and set(room) <= set(gamepatch.DATA_WORDS)
    assert gamepatch.SAVE_SECTION == stock.SAVE_SIZE - 0x2C and gamepatch.CALENDAR_ROOM == stock.ROSTER_MAX['ihmS']
    rank = {addr: code for addr, _, code, _ in gamepatch.STAGE_T_CAVES}[0x140684]
    assert [_run(rank, {3: n})[0][26] for n in (0, 17, 30, 31, 32)] == [0, 17, 30, 30, 30]   # 30 teams a ranking at most
    assert rank[-1][0] == 0x607a0000 and 8 + gamepatch.RANK_ROOM * 0x1c == 0x350              # the room before the flags
    for base in (0x227e74, 0x2281d4):                     # a draft pick's key: (year mod 6) x 224 + its number
        words = [(old, new) for a, old, new, _ in gamepatch.STAGE_U if base <= a < base + 20]
        assert len(words) == 5
        for m in range(6):
            game, ours = _key({3: m}, [old for old, _ in words]), _key({3: m}, [new for _, new in words])
            assert game == {3: 210 * m, 4: -240 * m} and ours == {3: 224 * m, 4: -240 * m}
    keys = [224 * m + n for m in range(6) for n in range(gamepatch.PICKS_PER_YEAR)]
    assert len(set(keys)) == 6 * 7 * 32 == gamepatch.META_ROWS['leaguedraftpick'] and max(keys) < 2 ** 11   # XWot: 11 bits
    v = {addr: (old, new) for addr, old, new, _ in gamepatch.STAGE_V}   # the roster plan's "NHL team" = key below 32
    assert set(v) == {0x486cf8, 0x48c8b4, 0x494b84}
    assert all(old & 0xffff == 30 and new == old - 30 + 32 and old >> 26 == 11 for old, new in v.values())   # cmpwi rX,30 -> 32
    w = {addr: (old, new) for addr, old, new, _ in gamepatch.STAGE_W}
    query = {a: w.pop(a) for a in (0x2209c0, 0x2212d4)}                  # a player's team: one of the league's 64 (stage M)
    assert all(old == gamepatch._li(4, 60) and new == gamepatch._li(4, 64) for old, new in query.values())
    assert len(w) == 7 and all(old >> 26 == 11 and new - old == 2 and old & 0xffff in (29, 30) for old, new in w.values())
    assert w[0x458ec8] == (0x2c1d001e, 0x2c1d0020)                     # a Seattle / Vegas pro's NHL team (lab round 35)
    assert {a: new for a, _, new, _ in gamepatch.YEAR_LABELS}[0x33a4d0] == gamepatch._li(4, 16)   # the job list's room


def _signed(value, bits=16):
    return value - (1 << bits) if value & 1 << (bits - 1) else value


def _gate(words, start, stops, reg, mem):
    """Run PowerPC words ({address: word}; clrlwi, cmpwi with a cr field, lbz off r1 = 0, li, beq / bne, b, nop only)
    from `start` until an address of `stops`: (that address, the registers)."""
    reg, cr, at = dict(reg), {}, start
    while at not in stops:
        word = words[at]
        op, rt, ra = word >> 26, word >> 21 & 31, word >> 16 & 31
        if word == gamepatch.NOP:
            pass
        elif op == 21:                                            # clrlwi rA,rS,24
            assert word & 0xffff == 0x063e
            reg[ra] = reg[rt] & 0xff
        elif op == 11:                                            # cmpwi crN,rA,imm
            cr[rt >> 2] = (reg[ra] > _signed(word & 0xffff)) - (reg[ra] < _signed(word & 0xffff))
        elif op == 34:                                            # lbz rT,d(r1)
            assert ra == 1
            reg[rt] = mem[_signed(word & 0xffff)]
        elif op == 14 and ra == 0:                                # li
            reg[rt] = _signed(word & 0xffff)
        elif op == 16:                                            # beq (BO 12) / bne (BO 4) on crN's eq bit
            assert ra & 3 == 2 and rt in (4, 12)
            if (cr[ra >> 2] == 0) == (rt == 12):
                at += _signed(word & 0xfffc)
                continue
        elif op == 18:                                            # b
            at += _signed(word & 0x3fffffc, 26)
            continue
        else:
            raise AssertionError(hex(word))
        at += 4
    return at, reg


def test_coachella_and_henderson_are_listed_and_named_in_the_ahl():
    old = {a: o for a, o, _, _ in gamepatch.STAGE_Y}
    new = {a: n for a, _, n, _ in gamepatch.STAGE_Y}
    assert sorted(old) == list(range(0x128408, 0x128434, 4))                # the gate's 11 words, one after another
    check, out = 0x128434, 0x128604                                          # on to the league check / left out

    def kept(at, league, listed):                    # the league check (0x128518): its own league, list 16 takes all
        return at == check and listed in (16, league)
    for created in (0, 1):
        for league in (1, 13):                                               # the team's: the AHL, Custom
            for none in (0, 1):                                              # the caller wants no created team
                for listed in (1, 13, 16):                                   # the list's league
                    case = {22: created, 29: none, 31: listed}, {0x100: league}
                    was = _gate(old, 0x128408, (check, out), *case)[0]
                    now = _gate(new, 0x128408, (check, out), *case)[0]
                    assert created or now == was == check                   # a club: the league check, as before
                    assert kept(now, league, listed) == (listed in (16, league) if created and league != 13
                                                         else kept(was, league, listed)), (created, league, none, listed)
    assert _gate(old, 0x128408, (check, out), {22: 1, 29: 1, 31: 1}, {0x100: 1})[0] == out   # why they were in no list
    for addr, word, code, _ in gamepatch.STAGE_Y_CAVES[:len(gamepatch.NAME_SITES)]:   # the five names: the club way
        assert word == 0x88610110 and code[0][0] == word
        assert addr in {a for a, _ in gamepatch.NAME_SITES}
        words = {0x1000 + 4 * k: w for k, (w, _) in enumerate(code)}
        for flag, league, named in ((1, 13, 1), (1, 1, 0), (0, 1, 0), (0, 13, 0)):
            assert _gate(words, 0x1000, (0x1000 + 4 * len(code),), {}, {0x110: flag, 0x100: league})[1][3] == named
    R = SimpleNamespace(T=SimpleNamespace(rows={234: {}, 235: {}, 251: {}}), team_name=str)
    R.T.get = lambda slot, f: R.T.rows[slot].get(f, dict(zip(gamepatch.LEAGUE_FIELDS, gamepatch.CUSTOM_GROUPS))[f]
                                                 if f in gamepatch.LEAGUE_FIELDS else 1)
    R.T.set = lambda slot, f, value: R.T.rows[slot].__setitem__(f, value)
    assert gamepatch.check_league_fit(R) and gamepatch.league_fit(R) == 2 and gamepatch.league_fit(R) == 0
    assert gamepatch.check_league_fit(R) == [] and gamepatch.league_of(R, 234) == (1, 7, 8, 13)
    assert gamepatch.unleague(R) == 2 and gamepatch.league_of(R, 235) == gamepatch.CUSTOM_GROUPS == (13, 48, 48, 48)


def _walk(code, team, active):
    """Run the list walk's cave (lab round 41) with the id `team` in r20, the database answering 'switched on' for the
    ids in `active`: (where it goes on: 'next' = the game's own next word, else the address it jumps to, r20, r1, the
    functions it called)."""
    reg, mem, cr, at, calls, asked = {1: 0x8000, 19: 0, 20: team}, {}, 0, 0, [], []
    while at < len(code):
        word = code[at][0]
        op, rt, ra, imm = word >> 26, word >> 21 & 31, word >> 16 & 31, word & 0xffff
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 15:                                              # lis
            assert ra == 0
            reg[rt] = imm << 16
        elif op == 24:                                            # ori
            reg[ra] = reg.get(rt, 0) | imm
        elif op in (14, 12):                                      # addi, addic
            reg[rt] = reg.get(ra, 0) + simm
        elif op == 11:                                            # cmpwi
            cr = (reg[ra] > simm) - (reg[ra] < simm)
        elif op == 16:                                            # blt / bge / bne
            if {0x4180: cr < 0, 0x4080: cr >= 0, 0x4082: cr != 0}[word >> 16]:
                at += simm // 4
                continue
        elif op == 18:                                            # b
            at += (((word & 0x3fffffc) ^ 0x2000000) - 0x2000000) // 4
            continue
        elif op == 62:                                            # stdu r1,d(r1)
            assert word & 3 == 1 and rt == ra == 1
            reg[1] += ((imm & 0xfffc) ^ 0x8000) - 0x8000
        elif word == 0x80a50070:                                  # lwz r5,0x70(r5): exhibitionteams' table number
            assert reg[5] == 0x1a7ac9c
            reg[5] = 0x7228e37b
        elif op in (32, 36):                                      # lwz, stw off r1 (inside the cave's own room)
            assert ra == 1 and 0x70 <= simm < 0x140 and reg[1] == 0x8000 - 0x140
            if op == 32:
                reg[rt] = mem[simm]
            else:
                mem[simm] = reg[rt]
        elif op == 30:                                            # clrldi r4,r4,32
            assert word == 0x78840020
        elif word == 0x7ca507b4:                                  # extsw r5,r5
            pass
        elif word == 0x7d8903a6:                                  # mtctr r12
            reg['ctr'] = reg[12]
        elif word == 0x4e800421:                                  # bctrl: the game's functions
            calls.append(reg['ctr'])
            if reg['ctr'] == 0xdc302c:
                asked.append(reg[4])
            elif reg['ctr'] == 0xdc3814:
                asked.append(reg[4])
            reg[3] = int(asked[-5] == gamepatch.INDEX_HASH and asked[-3] in active and asked[-1] == 1
                         and asked[-2] == gamepatch.ACTIVE_HASH) if reg['ctr'] == 0xdc86a0 else 0x5000 + len(calls)
        elif word == 0x4e800420:                                  # bctr
            return reg['ctr'], reg[20], reg[1], calls
        else:
            raise AssertionError(hex(word))
        at += 1
    return 'next', reg[20], reg[1], calls


def test_the_team_lists_skip_switched_off_custom_slots():
    (addr, old, code, _), = [c for c in gamepatch.STAGE_Y_CAVES if c[0] == 0x1283bc]
    assert old == 0x2c130000 and code[-1][0] == old and (addr, old) in gamepatch.hooks()
    assert gamepatch.TEAMS_VERSION >= '0.22'
    from legacy_roster.art import loc
    assert (loc.key_hash('index'), loc.key_hash('active')) == (gamepatch.INDEX_HASH, gamepatch.ACTIVE_HASH)
    for team in (0, 31, 61, 221):                                 # every club and every season key: as before, no query
        assert _walk(code, team, set())[:2] == ('next', team) and not _walk(code, team, set())[3]
    own = {234, 235}                                              # a roster from the game's own: 222-233 switched off
    assert _walk(code, 222, own)[:3] == ('next', 234, 0x8000) and _walk(code, 235, own)[:3] == ('next', 235, 0x8000)
    every = set(range(222, 252))                                  # a community roster: each custom slot is its own
    assert all(_walk(code, team, every)[:2] == ('next', team) for team in every)
    assert _walk(code, 236, own)[:3] == (gamepatch.LIST_END, 252, 0x8000)   # none left: the walk ends
    assert _walk(code, 252, own)[0] == gamepatch.LIST_END
    calls = _walk(code, 222, {222})[3]
    assert set(calls) == set(gamepatch.SKIP_CALLS) and calls.count(0xdc86a0) == 1
    assert calls[-2:] == [0xdc86a0, 0xdc4e84]                     # the result is read, then dropped


def _key(reg, words):
    """Run the pick key's words (sldi, subfc, addc, mulli, nop) on the registers `reg`."""
    reg = dict(reg)
    for w in words:
        op, d, a, b = w >> 26, w >> 21 & 31, w >> 16 & 31, w >> 11 & 31
        if w == gamepatch.NOP:
            continue
        if op == 7:
            reg[d] = reg[a] * (((w & 0xffff) ^ 0x8000) - 0x8000)
        elif op == 30:                                   # rldicr: sldi a,s,n with s in the d place
            reg[a] = reg[d] << (b | (w >> 1 & 1) << 5)
        elif op == 31 and w >> 1 & 0x3ff == 8:           # subfc d,a,b: b - a
            reg[d] = reg[b] - reg[a]
        elif op == 31 and w >> 1 & 0x3ff == 10:          # addc
            reg[d] = reg[a] + reg[b]
        else:
            raise AssertionError(hex(w))
    return reg


def test_the_salary_cap_stage_answers_the_real_numbers_of_each_season():
    from legacy_roster import contracts
    (addr, old, code, _), = gamepatch.STAGE_X_CAVES
    assert (addr, old) == (0x4a7240, 0xf821ff61)          # the stdu: none of the game's function has run
    (jump, game, ours, _), = gamepatch.STAGE_X
    assert (jump, game) == (0x4a73b0, 0xf821ff81) and jump + ((ours & 0x03fffffc) - 0x04000000) == addr   # b 0x4a7240
    assert ours >> 26 == 18 and jump in gamepatch.OTHER_INSTRUCTIONS
    for row, values in gamepatch.CAP_TABLE.items():
        for season in range(-2, 9):
            assert _cap(code, row, season) == gamepatch.cap_of(row, season) == values[min(max(season, 0), 3)]
    assert _cap(code, 2, 0) == 0                          # no other row is asked for (0x4a7240 is called with 0 / 1)
    floor, cap, lowest, rookie = (gamepatch.cap_of(r, 0) for r in (0, 1, 3, 4))
    assert (floor, cap, lowest) == (contracts.FLOOR, contracts.CAP, contracts.MINIMUM) == (76_900_000, 104_000_000, 850_000)
    assert cap // 5 == contracts.MAXIMUM and gamepatch.LOWEST_SALARY == lowest            # 0x4a7498: the cap / 5
    assert [gamepatch.cap_of(1, n) for n in range(5)] == [104_000_000, 113_500_000, 127_500_000, 127_500_000, 127_500_000]
    assert all(gamepatch.cap_of(4, n) == gamepatch.cap_of(3, n) + 175_000 for n in range(4))   # entry level: + $175,000
    assert all(v % contracts.UNIT == 0 for values in gamepatch.CAP_TABLE.values() for v in values)
    assert any(ws is gamepatch.STAGE_X for _, ws, *_ in gamepatch.TEAM_STAGES)               # in the players' entry


def _cap(code, r4, r5):
    """Run the cap cave's words (cmpwi, bge / ble / bne +n, li, lis, ori, slwi, add, blr) with row r4, season r5: r3."""
    reg, at, cr = {4: r4, 5: r5}, 0, 0
    while True:
        word = code[at][0]
        op, rt, ra, imm = word >> 26, word >> 21 & 31, word >> 16 & 31, word & 0xffff
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if word == 0x4e800020:
            return reg[3]
        if op == 11:
            cr = (reg[ra] > simm) - (reg[ra] < simm)
        elif op == 16:
            if {0x4080: cr >= 0, 0x4081: cr <= 0, 0x4082: cr != 0}[word >> 16]:
                at += simm // 4
                continue
        elif op == 14 and ra == 0:
            reg[rt] = simm
        elif op == 15 and ra == 0:
            reg[rt] = simm << 16
        elif op == 24:
            reg[ra] = reg[rt] | imm
        elif word == 0x5486103a:                          # slwi r6,r4,2
            reg[6] = reg[4] << 2
        elif word == 0x7cc62a14:                          # add r6,r6,r5
            reg[6] += reg[5]
        else:
            raise AssertionError(hex(word))
        at += 1


def test_contract_columns_show_the_real_seasons():
    label = {a: (old, new) for a, old, new, _ in gamepatch.YEAR_LABELS}[0x402d24]
    assert label == (0x60770000, 0x3ae30000 | gamepatch.YEARS_LATER)          # ori r23,r3,0 -> addi r23,r3,11
    assert 0x402d24 in gamepatch.OTHER_INSTRUCTIONS and gamepatch.PATCH_VERSION == '0.9'
    text = gamepatch.patch_text()
    assert 'be32, 0x00402d24, 0x3ae3000b' in text


def _year_check(screen_year, league_year, month, last_month, patched=True):
    """GetTeamMatchIDByDate's year check (0x407944 .. 0x40799c) as the words run: True = the day is looked up."""
    words = {0x407954: 0x30630001, 0x407960: 0x809c0000, 0x407964: 0x63830000}
    if patched:
        words.update({a: new for a, _, new, _ in gamepatch.YEAR_LABELS if a in words})
    r3 = league_year + (words[0x407954] & 0xffff)                       # addic r3,r3,1 (12)
    if screen_year > r3:
        return False
    if words[0x407960] >> 26 == 12:                                     # addic r3,r3,-1, then b to 0x407978
        assert words[0x407964] == 0x48000014 and 0x407964 + 0x14 == 0x407978
        r3 = (r3 + ((words[0x407960] & 0xffff) - 0x10000)) & 0xffffffff
    else:
        r3 = league_year                                                # the game asks for the league year again
    return screen_year <= r3 or month < last_month


def test_the_calendar_screen_finds_the_games_of_the_year_it_shows():
    # the patch-off game: the screen shows 2015-16, the league year is 2015
    assert _year_check(2015, 2015, 10, 7, patched=False) and _year_check(2016, 2015, 3, 7, patched=False)
    assert not _year_check(2026, 2015, 10, 7, patched=False)            # the patched screen's year: no marks before 0.9
    # with the patch the screen shows 2026-27 (season 1) and 2027-28 (season 2)
    assert _year_check(2026, 2015, 10, 7) and _year_check(2027, 2015, 3, 7) and not _year_check(2027, 2015, 8, 7)
    assert _year_check(2027, 2016, 10, 7) and not _year_check(2029, 2016, 1, 7)
    text = gamepatch.patch_text()
    assert all(f'be32, 0x{a:08x}, 0x{new:08x}' in text for a, _, new, _ in gamepatch.YEAR_LABELS if 0x407954 <= a <= 0x407964)


def _run(code, reg, mem=None):
    """Run a cave's words (ori, li / addi, addic, cmpwi, ble / bge / blt +n, lwz, stw only) on the registers `reg` and the
    words `mem` ({address: word}): (registers, memory) at its end."""
    reg, mem, at, cr = dict(reg), dict(mem or {}), 0, 0
    while at < len(code):
        word = code[at][0]
        op, rt, ra, imm = word >> 26, word >> 21 & 31, word >> 16 & 31, word & 0xffff
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 24:                                              # ori rA,rS,imm
            reg[ra] = reg.get(rt, 0) | imm
        elif op in (14, 12):                                      # addi / li, addic
            reg[rt] = (reg.get(ra, 0) if ra or op == 12 else 0) + simm
        elif op == 11:                                            # cmpwi
            cr = (reg[ra] > simm) - (reg[ra] < simm)
        elif op == 16:                                            # bc: ble / bge / blt
            taken = {0x4081: cr <= 0, 0x4080: cr >= 0, 0x4180: cr < 0}[word >> 16]
            if taken:
                at += simm // 4
                continue
        elif op == 32:                                            # lwz
            reg[rt] = mem[reg[ra] + simm]
        elif op == 36:                                            # stw
            mem[reg[ra] + simm] = reg[rt]
        else:
            raise AssertionError(hex(word))
        at += 1
    return reg, mem


def _run_draw(code, r5):
    """Run the lottery cave's words (li, cmpwi, blt, addi only) with the drawn number in r5: (r4, r5) at its end."""
    reg, at, lt = {4: 0, 5: r5}, 0, False
    while at < len(code):
        word = code[at][0]
        op, rt, imm = word >> 26, word >> 21 & 31, word & 0xffff
        if word >> 16 in (0x3880, 0x38a0):               # li r4 / li r5
            reg[rt] = imm
        elif word >> 16 == 0x2c05:                        # cmpwi r5,imm
            lt = reg[5] < imm
        elif word >> 16 == 0x4180:                        # blt +imm
            if lt:
                at += imm // 4
                continue
        elif word == 0x38840001:                          # addi r4,r4,1
            reg[4] += 1
        else:
            raise AssertionError(hex(word))
        assert op in (14, 11, 16)
        at += 1
    return reg[4], reg[5]


def test_the_patch_file_with_the_32_team_entries():
    text = gamepatch.patch_text(teams=True, titles=['BLES02153'])
    plain = gamepatch.patch_text(titles=['BLES02153'])
    year, intro = plain.split(f"\n  {gamepatch.INTRO_ENTRY}:", 1)
    intro = f"\n  {gamepatch.INTRO_ENTRY}:" + intro
    assert text.startswith(year) and text.endswith(intro) and len(text) > len(plain)   # year entry, team entries, intro entries
    for name, ws, cs, notes in gamepatch.TEAM_STAGES:
        assert f"  {name}:" in text and ': ' not in name + notes and '#' not in name + notes
    yaml = pytest.importorskip('yaml')                               # RPCS3 loads no entry of a file it cannot read
    entries = yaml.safe_load(text)[f"PPU-{gamepatch.EU_HASH}"]
    assert list(entries) == [gamepatch.YEAR_ENTRY] + [stage[0] for stage in gamepatch.TEAM_STAGES] + [
        gamepatch.INTRO_ENTRY, gamepatch.LOGIN_ENTRY, gamepatch.NEWS_ENTRY]      # the intro entries last, each its own switch
    assert all(entry['Patch'] and entry['Notes'] for entry in entries.values())
    lines = text.splitlines()
    at = lines.index("      - [ calloc, 0x0022ff28, 3 ]   # the game's 0x38800007 goes to our code")
    assert [line.split(',')[2].split(']')[0].strip() for line in lines[at + 1:at + 4]] == \
        ['0x3880001f', '0x9081008c', '0x38800008']                   # Vegas, the Pacific's 8th team, 8 teams
    assert "      - [ be32, 0x0022fee0, 0x2c19001f ]" in text


@pytest.mark.skipif(not os.environ.get('LEGACY_ROSTER_DISC'), reason="needs the game disc (LEGACY_ROSTER_DISC)")
def test_the_database_description_gives_vegas_six_bits():
    disc = gamepatch.disc_meta(os.environ['LEGACY_ROSTER_DISC'])
    made = gamepatch.fit_meta(disc)
    assert gamepatch.check_meta(made) == [] and gamepatch.fit_meta(made) == made          # a second run changes nothing
    assert len(made) - len(disc) == len(' maxinsert="2"') + len('126') - len('62') + 2 * (len('114') - len('60')) and made[:3] == disc[:3]   # BOM, line ends
    text = made.decode('utf-8')
    farm = re.search(r'<table name="leagueteams".*?<field name="ahlaffiliate" [^>]*/>', text, re.S).group(0)
    assert 'depth="7"' in farm.splitlines()[-1] and 'rangehigh="126" rangelow="-1"' in farm   # farm keys 32-63
    for table, depth, high in (('leagueplayerbiotable', 6, 31), ('exhibitionplayerbiotable', 6, 31)):   # the Season's;
        proteam = re.search(rf'<table name="{table}".*?<field name="proteam" [^>]*/>', text, re.S)  # the roster's (r. 42)
        line = proteam.group(0).splitlines()[-1]
        assert f'depth="{depth}"' in line and f'rangehigh="{high}" rangelow="-1"' in line
    proteam = re.search(r'<table name="leagueplayerbiotable".*?<field name="proteam" [^>]*/>', text, re.S)
    line = proteam.group(0).splitlines()[-1]
    broken = text[:proteam.end() - len(line)] + line.replace('depth="6"', 'depth="5"') + text[proteam.end():]
    assert gamepatch.check_meta(broken.encode('utf-8')) == \
        ["leagueplayerbiotable.proteam: -1..31 does not fit in 5 bits"]                  # the lab's file of round 3
    assert (gamepatch.meta_rights(made), gamepatch.meta_rights(disc), gamepatch.meta_rights(b'')) == (6, 5, None)


@pytest.mark.skipif(not os.environ.get('LEGACY_ROSTER_DISC'), reason="needs the game disc (LEGACY_ROSTER_DISC)")
def test_the_database_gives_the_season_the_same_six_bits():
    disc = os.environ['LEGACY_ROSTER_DISC']
    meta, own = gamepatch.fit_meta(gamepatch.disc_meta(disc)), gamepatch.disc_db(disc)
    assert gamepatch.check_db(own, gamepatch.disc_meta(disc)) == []                     # the game's own files agree
    assert "table MMxP: field WBbd has 5 bits, the description 6" in gamepatch.check_db(own, meta)   # lab round 4
    assert "the game's calendar table ihmS has room for 1231 rows, not 1345" in gamepatch.check_db(own, meta)  # round 18
    made = gamepatch.fit_db(own, meta)
    grown = len(gamepatch.CALENDAR_TABLES) * (schedule.PATCH_ROWS - gamepatch.CALENDAR_STOCK) * 8
    assert gamepatch.check_db(made, meta) == [] and gamepatch.fit_db(made, meta) == made and len(made) == len(own) + grown
    before, after = gamepatch._db(own), gamepatch._db(made)
    changed = {t for t in after.order if after[t].field_defs != before[t].field_defs}
    assert changed == {'BDjM', 'MhGT', 'VeqU', 'cpwZ', 'uChp', 'sDbJ', 'MMxP', 'sbGR', 'WRGI', 'cPbu'}   # the 15 fields' only
    P, Q = before['cPbu'], after['cPbu']                        # the roster's players: rights in six bits (lab round 42)
    assert Q.fields['WBbd'].bits == 6 and all(Q.get(i, n) == P.get(i, n) for i in range(P.cur_rec) for n in P.fields)
    assert (after['WRGI'].fields['XfbS'].bits, after['WRGI'].rec_len) == (32, before['WRGI'].rec_len)   # Vegas's bit 31
    for tag in gamepatch.CALENDAR_TABLES:                       # room for 84 games (round 19), the 1,231 rows as they were
        assert (before[tag].max_rec, after[tag].max_rec, after[tag].cur_rec) == (1231, schedule.PATCH_ROWS, 1231)
        assert after[tag].records[:1231 * 8] == before[tag].records and not any(after[tag].records[1231 * 8:])
    assert all(after[t].build()[4:] == before[t].build()[4:] for t in after.order
               if t not in changed | set(gamepatch.CALENDAR_TABLES))                                  # 0-4: the chain
    old, new = before['MMxP'].fields, after['MMxP'].fields
    assert (new['WBbd'].bits, new['WfTt'].offset, new['axwp'].offset, new['uWgv'].offset) == \
        (6, old['WfTt'].offset + 1, old['axwp'].offset + 1, old['uWgv'].offset + 2)    # the fields after it move along


@pytest.mark.skipif(not os.environ.get('LEGACY_ROSTER_DISC'), reason="needs the game disc (LEGACY_ROSTER_DISC)")
def test_the_database_carries_the_patch_rosters_next_season_calendars():
    disc = os.environ['LEGACY_ROSTER_DISC']
    meta, own = gamepatch.fit_meta(gamepatch.disc_meta(disc)), gamepatch.disc_db(disc)
    plain = gamepatch.fit_db(own, meta)
    roster = SimpleNamespace(f=gamepatch._db(plain))      # a stand-in for the patch roster: other games, more AHL rows
    F, A = roster.f['byED'], roster.f['AJKN']
    for i in range(F.cur_rec):
        F.set(i, 'qkhY', (F.get(i, 'qkhY') + 1) % 32)
    A.grow(1180)                                           # the game's 1,120 and the description's 60 more
    while A.cur_rec < 1152:
        A.add_record({'qEfv': A.cur_rec, 'qkhY': A.cur_rec % 32, 'rOMv': (A.cur_rec + 1) % 32})
    assert gamepatch.check_db(plain, meta, roster) == [
        "the game's next seasons' NHL calendar (nhlfutureschedule) is not the patch roster's (1231 rows, the roster 1231)",
        "the game's AHL calendar (ahlschedule) is not the patch roster's (1120 rows, the roster 1152)"]   # run 11's season 2
    made = gamepatch.fit_db(own, meta, roster)
    assert gamepatch.check_db(made, meta, roster) == [] and gamepatch.fit_db(made, meta, roster) == made
    before, after = gamepatch._db(plain), gamepatch._db(made)
    assert [(after[t].cur_rec, after[t].max_rec) for t in ('byED', 'AJKN')] == [(1231, 1345), (1152, 1180)]
    assert schedule.read(SimpleNamespace(f=after), 'byED') == schedule.read(roster, 'byED') != schedule.read(roster)
    assert all(after[t].build()[4:] == before[t].build()[4:] for t in after.order if t not in gamepatch.NEXT_SEASON_TABLES)
    other = SimpleNamespace(f=gamepatch._db(plain))
    other.f['AJKN'].widen('rOMv', 6)
    with pytest.raises(ValueError, match="other fields"):   # a roster whose table has other fields is refused
        gamepatch.fit_db(own, meta, other)


def test_the_intro_entries_stand_apart_and_change_three_words_and_one_byte():
    text = gamepatch.patch_text()
    yaml = pytest.importorskip('yaml')
    entries = yaml.safe_load(text)[f"PPU-{gamepatch.EU_HASH}"]
    assert list(entries) == [gamepatch.YEAR_ENTRY, gamepatch.INTRO_ENTRY, gamepatch.LOGIN_ENTRY,
                             gamepatch.NEWS_ENTRY]                                # also with the year alone
    intro, login = entries[gamepatch.INTRO_ENTRY]['Patch'], entries[gamepatch.LOGIN_ENTRY]['Patch']
    assert intro == [['be32', 0x0220a64c, 0], ['be32', 0x00fb2f24, 0x48000024]]     # quick boot, no autosave notice
    assert login == [['be32', 0x01cd411c, 0x020e9d80]]                           # ShouldDoBootFlowLogin answers no
    assert entries[gamepatch.NEWS_ENTRY]['Patch'] == [['be32', 0x007e8d58, 0x480004d8]]   # the signed-out news always
    for beq, b in (gamepatch.INTRO[1][1:3], gamepatch.NEWS[0][1:3]):
        assert beq >> 26 == 16 and b >> 26 == 18 and beq & 0xfffc == b & 0x3fffffc     # beq becomes b, the same target
    ours = {a for _, ws, _ in gamepatch.INTRO_ENTRIES for a, *_ in ws}
    others = {a for a, _ in gamepatch.hooks()} - ours
    assert len(ours) == 4 and not ours & others and {0x220a64c, 0x1cd411c} <= set(gamepatch.DATA_WORDS)
    assert {0xfb2f24, 0x7e8d58} <= set(gamepatch.OTHER_INSTRUCTIONS)
    assert all(': ' not in name + notes and '#' not in name + notes for name, _, notes in gamepatch.INTRO_ENTRIES)


def test_the_next_seasons_calendar_is_trimmed_when_the_patched_game_saved_it_with_more_room(base_bytes):
    R = Roster(base_bytes)
    F = R.f[gamepatch.FUTURE_TABLE]
    F.grow(1459)                                                    # a roster the patched game saved itself
    gamepatch.future_fit(R)
    assert R.f[gamepatch.FUTURE_TABLE].max_rec == schedule.PATCH_ROWS


def test_the_online_entry_has_the_community_words_for_1_00_and_update_1_01():
    for title in gamepatch.HASHES:
        old = "\n".join(gamepatch.online_entry_lines(title, '01.00'))
        for addr, was, new, why in gamepatch.ONLINE:
            assert f"be32, 0x{addr:08x}, 0x{new:08x} ]   # was 0x{was:08x}" in old
        new = "\n".join(gamepatch.online_entry_lines(title, '01.01'))
        assert "0x0087b11c, 0x2c030001" in new and "0x0087a010, 0x2c030001" in new and "was" not in new
    assert [a for a, *_ in gamepatch.ONLINE] == [0x8bc4bc, 0x8bc494, 0x104f0bc, 0x211df0]
    text = gamepatch.player_patch_text()
    assert text.count(f"  {gamepatch.ONLINE_ENTRY}:") == 3        # EU 1.00, NA 1.00, update 1.01 (both titles in one)
    assert gamepatch.ONLINE_ENTRY not in gamepatch.patch_text(teams=True)   # the lab's file stays as it was
