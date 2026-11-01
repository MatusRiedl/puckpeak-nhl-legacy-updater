import os
from collections import Counter

import pytest

from legacy_roster import layout as L
from legacy_roster import draft, lines, pipeline, ratings, schema
from legacy_roster.builder import NHL_ARENAS, NHL_COLOURS, NHL_LOOK, Builder, Data
from legacy_roster.matching import closest, match
from legacy_roster.roster import Roster
from legacy_roster.verify import verify


def roster_of(R, team):
    return {prow for _, prow, _, _, _ in R.team_roster(team)}


def test_the_build_passes_every_integrity_check(built):
    assert built.problems == []
    assert built.info['empty_national_teams'] == []


def test_every_listed_nhl_player_is_on_his_team_and_nobody_else_is(built, data):
    R = Roster(built.data)
    people = match(R, [dict(p) for p in data.nhl_players])
    assert all(p['row'] is not None for p in people)
    kept = built.builder.contract_kept         # under contract for 2026-27, on no NHL.com roster (contract_keeps)
    assert kept and not set(kept) & {R.P.get(p['row'], 'zIBw') for p in people}
    for abbr, slot in L.API_TO_SLOT.items():
        held = {R.p_by_id[pid] for pid, t in kept.items() if t == slot}
        assert roster_of(R, slot) == {p['row'] for p in people if p['team'] == abbr} | held, abbr


def test_mirror_teams_copy_their_primary(built):
    R = Roster(built.data)
    for prim, mirrors in L.MIRRORS.items():
        for m in mirrors:
            assert roster_of(R, m) == roster_of(R, prim)


def test_hard_limits_no_new_team_and_no_team_changes_league(built, base_bytes):
    src, new = Roster(base_bytes), Roster(built.data)
    assert new.T.cur_rec == src.T.cur_rec == L.TEAM_COUNT
    assert new.T.column('league') == src.T.column('league')
    # the team table is not touched beyond the NHL teams' arena and colours (builder.nhl_identity: Seattle and Vegas
    # shared one arena row; Vegas gets its own)
    n = src.T.rec_len
    for t in range(32, L.TEAM_COUNT):
        assert new.T.records[t * n:(t + 1) * n] == src.T.records[t * n:(t + 1) * n]
    A = new.f['OEtS']
    own = {src.T.alias['arenaid']} | {src.T.alias[f"{kind}color_{c}"] for kind in ('primary', 'secondary') for c in 'rgb'}
    for slot in range(32):
        row = new.T.get(slot, 'arenaid')
        assert A.get(row, 'arenaname') == NHL_ARENAS[slot]
        if slot in NHL_LOOK:
            assert A.get(row, 'cityname') == NHL_LOOK[slot][1]
        assert [tuple(new.T.get(slot, f"{kind}color_{c}") for c in 'rgb') for kind in ('primary', 'secondary')] == \
            list(NHL_COLOURS[slot])
        assert all(new.T.get(slot, f) == src.T.get(slot, f) for f in src.T.fields if f not in own)
    assert len({new.T.get(slot, 'arenaid') for slot in range(32)}) == 32                    # each NHL team its own row


def test_nhl_and_national_teams_dress_a_legal_line_up(built):
    R = Roster(built.data)
    U, P = R.U, R.P
    for team in list(range(32)) + list(range(133, 154)):
        ents = [e for e in range(U.cur_rec) if U.get(e, 'team') == team]
        assert len(ents) <= L.MAX_PER_TEAM
        dressed = [e for e in ents if U.get(e, 'rosterstatus')]
        pos = Counter('FFFDG'[P.get(R.p_by_id[R.link_to_pid[U.get(e, 'playerindex')]], 'position')] for e in dressed)
        assert (len(dressed), pos['G']) == (20, 2) and pos['D'] >= 6, R.team_name(team)
        for slot in schema.LINE_SLOTS:
            assert sum(U.get(e, slot) for e in ents) == 1, (R.team_name(team), slot)
        assert sorted(U.get(e, 'key') for e in ents) == [team * 40 + k for k in range(len(ents))]


def test_published_attributes_are_stored_exactly(built, pack):
    R = Roster(built.data)
    S, G = R.f['yvSd'], R.f['yuHm']
    rows = {t.name: {t.get(i, 'game_id'): i for i in range(t.cur_rec)} for t in (S, G)}
    checked = 0
    for p in pack['ratings_list']:
        if len(p['attrs']) < 10 or not p['birth']:
            continue
        first, _, last = p['name'].partition(' ')
        found = R.find_player(first, last)
        if len(found) != 1:
            continue
        t, amap = (G, schema.LIST_GOALIE) if p['position'] == 'G' else (S, schema.LIST_SKATER)
        row = rows[t.name].get(R.P.get(found[0], 'game_id'))
        if row is None:
            continue
        for label, value in p['attrs'].items():
            if label in amap:
                assert t.get(row, amap[label]) == max(0, min(63, value - schema.RATING_BASE)), (p['name'], label)
        checked += 1
    assert checked > 250


def test_fields_nobody_publishes_are_left_alone(built, base_bytes):
    src, new = Roster(base_bytes), Roster(built.data)
    created = {src.P.get(r, 'game_id') for r in built.builder.created}
    for tname in ('yvSd', 'yuHm'):
        a, b = src.f[tname], new.f[tname]
        for field in ('c_potential', 'growthtier', 'trait0', 'playerstyle'):
            changed = [i for i in range(a.cur_rec) if a.get(i, field) != b.get(i, field) and a.get(i, 'game_id') not in created]
            assert not changed, (tname, field)


def test_new_players_do_not_inherit_the_previous_owner_of_their_record(built, data):
    R = Roster(built.data)
    drafts = draft.Drafts(data.drafts, data.season_year)
    assert built.builder.created
    for prow in built.builder.created:
        P = R.P
        assert 'ZZ' not in P.get(prow, 'lastname')
        assert (P.get(prow, 'hasportrait'), P.get(prow, 'artid'), P.get(prow, 'audioid')) == (0, 0, 0)
        assert P.get(prow, 'headid') >= 60000
        assert P.get(prow, 'nhlgamesplayedcareer') == 0
        # his own draft (draft.py), or none: never the previous owner's
        want = drafts.wanted(P, prow) or (255, 0, 0, 0)
        assert tuple(P.get(prow, f) for f in draft.FIELDS) == want, R.name(prow)


def test_roster_entries_carry_the_players_own_style(built):
    R = Roster(built.data)
    style = {}
    for tname in ('yvSd', 'yuHm'):
        t = R.f[tname]
        style.update({t.get(i, 'game_id'): t.get(i, 'playerstyle') for i in range(t.cur_rec)})
    for e in range(R.U.cur_rec):
        assert R.U.get(e, 'playerstyle') == style[R.link_to_pid[R.U.get(e, 'playerindex')]]


def test_a_second_run_on_its_own_output_changes_nothing(built, data):
    again = pipeline.build(built.data, data)
    assert again.problems == []
    assert again.builder.maintain
    assert again.data == built.data


def test_steps_can_be_run_on_their_own(base_bytes, data):
    only_ratings = pipeline.build(base_bytes, Data(ratings_list=data.ratings_list, season_year=data.season_year),
                                  steps=[pipeline.RATINGS])
    assert only_ratings.problems == []
    src, new = Roster(base_bytes), Roster(only_ratings.data)
    assert new.U.records == src.U.records and new.P.records == src.P.records     # nobody moved
    assert new.f['yvSd'].records != src.f['yvSd'].records
    nothing = pipeline.build(base_bytes, Data(), steps=[])
    assert nothing.data == base_bytes


def test_a_record_another_person_matches_more_closely_is_not_his(base_bytes):
    R = Roster(base_bytes)
    P = R.P
    row = next(i for i in range(P.cur_rec) if len(P.get(i, 'PedH')) >= 4 and P.get(i, 'RMbQ'))
    first, last = P.get(row, 'PedH'), P.get(row, 'RMbQ')
    birth = (P.get(row, 'dnFq') + 1910, P.get(row, 'pLKJ') + 1, P.get(row, 'iwsK') + 1)
    cousin = dict(first=first[0] + 'zq', last=last, birth=(birth[0] + 1, 1, 1))  # last name + year + initial only
    alone = match(R, [dict(cousin)])[0]
    assert alone['how'] == 'last+year' and alone['row'] is not None
    own, other = closest(match(R, [dict(first=first, last=last, birth=birth), dict(cousin)]))
    assert own['row'] == row and other['row'] is None          # Aatu Räty's record is not Aku Räty's


def test_nhl_players_get_the_position_nhl_com_lists(built, data):
    R = Roster(built.data)
    people = match(R, [dict(p) for p in data.nhl_players])
    for p in people:
        if p['pos'] != 'G':
            assert R.P.get(p['row'], 'position') == L.POS_CODE[p['pos']], (p['first'], p['last'])
    smith = [p for p in people if (p['first'], p['last'], p['team']) == ('Cole', 'Smith', 'CHI')]
    if smith:                                       # the owner's report: Chicago had one right wing too few
        assert R.P.get(smith[0]['row'], 'position') == 2
        assert any(r[1] == 'position changed' and r[2] == 'Cole Smith' for r in built.builder.log)


def test_wingers_play_their_own_side_on_the_nhl_lines(built):
    R = Roster(built.data)
    U, P = R.U, R.P
    right, possible = 0, 0
    for team in range(32):
        ents = [e for e in range(U.cur_rec) if U.get(e, 'team') == team]
        pos = {e: P.get(R.p_by_id[R.link_to_pid[U.get(e, 'playerindex')]], 'position') for e in ents}
        possible += sum(min(4, list(pos.values()).count(side)) for side in (1, 2))
        for k in range(1, 5):
            for slot, want in ((f"l{k}lw", 1), (f"l{k}rw", 2)):
                right += pos[next(e for e in ents if U.get(e, slot))] == want
    assert right >= possible * 0.85                 # a much better winger may still cross over
    chicago = [e for e in range(U.cur_rec) if U.get(e, 'team') == 6]
    rw = [e for e in chicago if P.get(R.p_by_id[R.link_to_pid[U.get(e, 'playerindex')]], 'position') == 2]
    assert len(rw) >= 3 and all(U.get(e, 'rosterstatus') for e in rw)


def test_generic_line_builder_puts_wingers_on_their_side():
    assert lines.wing_side({schema.SLOT_TAG['l2lw'], schema.SLOT_TAG['pp1rw']}) == 1
    assert lines.wing_side({schema.SLOT_TAG['pp1rw']}) == 2
    assert lines.wing_side({schema.SLOT_TAG['l1c']}) is None


def test_generic_line_builder_follows_the_stock_rules(base_bytes):
    R = Roster(base_bytes)
    b = Builder(R, Data())
    for team in (0, 11, 142):                       # two NHL teams and a national team
        slots = lines.build_lines(b, team)
        assert set(slots) == set(schema.LINE_SLOTS)
        dressed = set(slots.values())
        pos = Counter(R.P.get(b.prow_of_entry(e), 'position') for e in dressed)
        assert len(dressed) == 20 and pos[4] == 2 and pos[3] == 6
        assert slots['g1'] != slots['g2'] and {R.P.get(b.prow_of_entry(slots[g]), 'position') for g in ('g1', 'g2')} == {4}
        for group in (schema.EVEN_STRENGTH, schema.POWER_PLAY, schema.POWER_PLAY_4, schema.PENALTY_KILL_4,
                      schema.OVERTIME, schema.SHOOTOUT, schema.EXTRA_ATTACKER):
            holders = [slots[s] for s in group]
            assert len(set(holders)) == len(holders), group
        for e in b.entries_on(team):
            assert bool(R.U.get(e, 'rosterstatus')) == (e in dressed)
        # the best forward leads the first power play and the shootout list is forwards only
        assert all(R.P.get(b.prow_of_entry(slots[s]), 'position') < 3 for s in schema.SHOOTOUT)


def test_line_builder_refuses_a_team_that_cannot_dress_twenty(base_bytes):
    R = Roster(base_bytes)
    b = Builder(R, Data())
    with pytest.raises(lines.NotEnoughPlayers):
        lines.build_lines(b, 132)                   # Valerenga: empty in the base


def test_verify_reports_what_it_is_given(built, base_bytes, data):
    src = Roster(base_bytes)
    R = Roster(built.data)
    R.U.set(0, 'key', R.U.get(1, 'key'))            # two entries with the same id
    R.T.set(40, 'league', 3)                        # an AHL team moved to another league
    problems, _ = verify(R.f.build(), src, data.nhl_players)
    assert "duplicate roster entry ids" in problems
    assert any("changed league" in p for p in problems)
    assert verify(b'not a save', src)[0][0].startswith("the save cannot be read back")


def young_free_agent(R):
    """The link of the youngest free agent (an old one may retire in the update)."""
    links = [R.Q.get(k, 'TWSX') for k in range(R.Q.cur_rec)]
    return max(links, key=lambda l: (R.P.get(R.p_by_id[R.link_to_pid[l]], 'year'), -l))


def community_style(base_bytes):
    """The base roster changed the way the community's 2026-27 roster is: the Ducks copy (225) out
    of step with Anaheim (half its players gone, a free agent on it), Italy and France emptied,
    Czech Republic dressed but without line slots."""
    R = Roster(base_bytes)
    U = R.U
    flags = [n for n, f in U.fields.items() if f.bits == 1 and n != 'jZSh']
    ducks = [i for i in range(U.cur_rec) if U.get(i, 'BSXd') == 225]
    U.set(ducks[0], 'TWSX', young_free_agent(R))          # someone who is only on the copy
    gone = ducks[1:13] + [i for i in range(U.cur_rec) if U.get(i, 'BSXd') in (139, 142)]
    for i in range(U.cur_rec):
        if U.get(i, 'BSXd') == 136:
            for f in flags:
                U.set(i, f, 0)
    for i in sorted(gone, reverse=True):
        U.delete_record(i)
    return R.f.build()


def test_a_community_roster_with_unfinished_teams_is_updated(base_bytes, data):
    src = community_style(base_bytes)
    L.check_base(Roster(src))                              # recognised by the copy's name
    res = pipeline.build(src, data)
    assert res.problems == []
    R = Roster(res.data)
    assert roster_of(R, 225) == roster_of(R, 0)
    for team in (136, 139, 142):                           # Czech lines dealt; Italy, France refilled (IIHF)
        assert res.info['teams'][team]['dressed'] == 20 and res.info['teams'][team]['slots'] == 71, team
    fa = {R.link_to_pid.get(R.Q.get(i, 'TWSX')) for i in range(R.Q.cur_rec)}
    alone = Roster(src).link_to_pid[young_free_agent(Roster(src))]
    assert alone in fa and not [i for i in range(R.U.cur_rec) if R.link_to_pid.get(R.U.get(i, 'TWSX')) == alone]
    assert pipeline.build(res.data, data).data == res.data


def test_a_country_without_enough_players_keeps_its_empty_squad(base_bytes, data):
    no_iihf = Data(nhl_players=data.nhl_players, ratings_list=data.ratings_list, iihf={}, season_year=data.season_year)
    res = pipeline.build(community_style(base_bytes), no_iihf, steps=['national'])
    assert res.problems == []
    assert res.info['teams'][142]['players'] == 0          # Italy: no IIHF roster, too few Italians in the save
    assert any("left empty" in line and "Italy" in line for line in res.summary())


def test_a_roster_with_some_copies_missing_is_refused_with_an_explanation(base_bytes):
    R = Roster(base_bytes)
    for e in [e for e in range(R.U.cur_rec) if R.U.get(e, 'team') == 229][::-1]:
        R.U.delete_record(e)                        # no Utah copy: neither the community's nor the game's layout
    with pytest.raises(L.LayoutError, match="custom copies"):
        pipeline.build(R.f.build(), Data())
    assert L.check_base(Roster(base_bytes)) == L.COMMUNITY


def test_overall_only_players_land_on_their_overall(built, pack):
    """Someone published with just an overall has his attributes shifted until his level fits it."""
    R = Roster(built.data)
    S = R.f['yvSd']
    rows = {S.get(i, 'game_id'): i for i in range(S.cur_rec)}
    k = ratings.overall_offset(pack['ratings_list'])[False]
    seen = 0
    for p in pack['ratings_list']:
        if p['attrs'] or p['position'] == 'G' or not p['birth']:
            continue
        first, _, last = p['name'].partition(' ')
        found = R.find_player(first, last)
        if len(found) != 1 or R.P.get(found[0], 'game_id') not in rows:
            continue
        assert abs(p['ovr'] - k - ratings.level(S, rows[R.P.get(found[0], 'game_id')])) <= 0.5, p['name']
        seen += 1
    assert seen > 200


def find(R, first, last):
    return [r for r in range(R.P.cur_rec) if R.P.get(r, 'firstname') == first and R.P.get(r, 'lastname') == last]


def test_free_agents_are_players_who_can_still_sign(built, data):
    """Nobody on the free-agent list would retire; last season's unsigned NHL players under 38 are on it
    (testers, 0.7.0: retired free agents stayed, Reimer was missing), the ones of 38 and over retired
    (testers, 0.85.0: Kopitar and Toews signed in Be a Pro; owner, 2026-10-28)."""
    R, b = Roster(built.data), built.builder
    fa = {R.link_to_pid.get(R.Q.get(k, 'TWSX')) for k in range(R.Q.cur_rec)}
    assert not [R.name(R.p_by_id[p]) for p in fa if b.would_retire(p)]
    for first, last in (('Gustav', 'Nyquist'),):
        assert any(R.P.get(r, 'game_id') in fa for r in find(R, first, last)), last
    for first, last in (('Anze', 'Kopitar'), ('Jonathan', 'Toews'), ('Jonathan', 'Quick')):
        rows = find(R, first, last)
        assert not [r for r in rows if R.P.get(r, 'game_id') in fa or R.teams_of(r)], last
    unsigned = [p for p in data.nhl_last if not p['team']]
    assert unsigned and any(r[1] == 'free agent added' for r in built.log)


def test_a_younger_player_on_the_retired_list_retires(built, data):
    """The data pack's list (`retired`, tools/retired.json) retires an unsigned player under 38 too."""
    b = built.builder
    nyquist = next(p for p in b.last_season_people if p['last'] == 'Nyquist')
    assert id(nyquist) not in b.retired_people(data)
    listed = Data(season_year=data.season_year, retired=[{'first': 'Gustav', 'last': 'Nyquist', 'birth': [1989, 9, 1]}])
    assert id(nyquist) in b.retired_people(listed)


def test_players_get_their_real_draft(built):
    R = Roster(built.data)
    for (first, last), want in ((('Will', 'Smith'), (123, 1, 4, 26)), (('Aleksander', 'Barkov'), (113, 1, 2, 13)),
                                (('Macklin', 'Celebrini'), (124, 1, 1, 26))):
        rows = [r for r in find(R, first, last) if R.teams_of(r)]
        assert rows and tuple(R.P.get(rows[0], f) for f in draft.FIELDS) == want, last


def test_nhl_players_get_nhl_com_size_and_hand(built, data):
    R = Roster(built.data)
    people = match(R, [dict(p) for p in data.nhl_players])
    checked = 0
    for p in people:
        if p['row'] is None or not p.get('height_in') or not p.get('weight_lb'):
            continue
        P = R.P
        assert P.get(p['row'], 'QBpy') == max(0, min(31, p['height_in'] - 54)), p['last']
        assert P.get(p['row'], 'WZNs') == max(0, min(255, p['weight_lb'] - 120)), p['last']
        if p.get('shoots') in ('L', 'R'):
            assert P.get(p['row'], 'pkRG') == (p['shoots'] == 'R'), p['last']
        checked += 1
    assert checked > 700


def test_a_goalie_who_changed_club_wears_its_colours(built):
    R, b = Roster(built.data), built.builder
    G, T = R.f['lVMf'], R.T
    rows = {G.get(i, 'game_id'): i for i in range(G.cur_rec)}
    now = b.home_teams()
    moved = [(pid, team) for pid, team in now.items() if R.P.get(R.p_by_id[pid], 'position') == 4 and pid in rows
             and (b.orig_home.get(pid) != team or R.p_by_id[pid] in b.created)]
    assert moved
    for pid, team in moved:
        club = {tuple(T.get(team, f"{k}color_{c}") for c in 'rgb') for k in ('primary', 'secondary')}
        for part in b.GEAR_PARTS:
            for z in range(1, 10):
                colour = tuple(G.get(rows[pid], f"{part}zone{z}color_{c}") for c in 'rgb')
                assert max(colour) - min(colour) < 40 or colour in club, (R.name(R.p_by_id[pid]), part, z)


def test_verify_finds_a_free_agent_listed_twice(built, base_bytes):
    R = Roster(built.data)
    R.Q.add_record({'TWSX': R.Q.get(0, 'TWSX')})
    problems, _ = verify(R.f.build(), Roster(base_bytes))
    assert any('free-agent list twice' in p for p in problems)


@pytest.fixture
def save_folder(tmp_path, base_dir, monkeypatch):
    """A pretend save folder with the base roster; the program's own files in a temp folder, RPCS3 closed."""
    import shutil
    from legacy_roster import savedata
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    folder = tmp_path / 'savedata'
    shutil.copytree(base_dir, folder / 'BLES021530202')
    return str(folder)


def test_an_update_in_place_changes_the_chosen_roster_after_a_backup(save_folder, base_bytes, data, tmp_path):
    from legacy_roster import savedata
    backups = str(tmp_path / 'backups')
    res = pipeline.update(save_folder, 'BLES021530202', pipeline.CORE_STEPS, None, data=data, in_place=True,
                          backup_root=backups)
    assert res.build.ok
    assert res.in_place and not res.unchanged and res.slot.folder == 'BLES021530202'
    assert [s.folder for s in savedata.list_rosters(save_folder)] == ['BLES021530202']          # no new folder
    assert open(res.slot.sys_data, 'rb').read() == res.build.data != base_bytes
    assert res.slot.name == savedata.list_rosters(save_folder)[0].name                      # the name stays
    assert open(os.path.join(res.backup, 'SYS-DATA'), 'rb').read() == base_bytes
    assert 'updated in place' in res.saved_where()
    again = pipeline.update(save_folder, 'BLES021530202', pipeline.CORE_STEPS, None, data=data, in_place=True,
                            backup_root=backups)
    assert again.unchanged and again.backup is None and len(os.listdir(backups)) == 1          # nothing to do twice


def test_an_update_in_place_refuses_what_it_cannot_do_and_writes_nothing(save_folder, base_bytes, data, monkeypatch):
    from legacy_roster import savedata
    sysdata = lambda: open(os.path.join(save_folder, 'BLES021530202', 'SYS-DATA'), 'rb').read()
    with pytest.raises(savedata.InPlaceError, match="other version|own version"):
        pipeline.update(save_folder, 'BLES021530202', pipeline.CORE_STEPS, None, data=data, in_place=True,
                        targets=['BLES02153', 'BLUS31540'])
    with pytest.raises(savedata.InPlaceError, match="game's own roster"):
        pipeline.update(save_folder, None, pipeline.CORE_STEPS, None, data=data, in_place=True,
                        disc=savedata.DiscSlot('BLES02153', 'x.iso'))
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe')
    with pytest.raises(savedata.InPlaceError, match="Close RPCS3"):
        pipeline.update(save_folder, 'BLES021530202', pipeline.CORE_STEPS, None, data=data, in_place=True)
    dry = pipeline.update(save_folder, 'BLES021530202', pipeline.CORE_STEPS, None, data=data, in_place=True, dry_run=True)
    assert dry.slot is None and sysdata() == base_bytes


def test_the_photos_line_says_how_many_teams_wear_this_seasons_jerseys():
    res = pipeline.UpdateResult(None, None, None, 'x', art=(12, 3, 0))
    assert res.art_line() == "Photos and logos: 12 pictures installed, 3 were installed already."
    res.look_teams = 214
    assert res.art_line() == "Photos and logos: 12 pictures installed, 3 were installed already. 214 teams wear this season's jerseys."
