"""Builder.mend (0.95.1): what a step leaves behind that verify would refuse and that has one safe answer is put right
before the roster is written, with a row under "Repairs" in the list of changes, instead of the whole update failing.
Tester rosters kept stopping on such leftovers (Joe Sakic, "Kraken has 49 players", Nick Jensen). Each test makes one
leftover by hand on the community base, as a faulty step would, and checks that verify passes after the mend."""
from legacy_roster import layout as L
from legacy_roster.builder import REPAIRS, Builder, Data
from legacy_roster.roster import Roster
from legacy_roster.verify import verify

AHL_CLUB = 32


def _builder(base_bytes):
    R = Roster(base_bytes)
    return R, Builder(R, Data(season_year=2026))


def _player_on(R, team, goalie=False):
    """(entry, pid, row) of the first player of `team` who is on no other team (a goalie or a skater)."""
    for e in range(R.U.cur_rec):
        if R.U.get(e, 'BSXd') != team:
            continue
        pid = R.link_to_pid[R.U.get(e, 'TWSX')]
        row = R.p_by_id[pid]
        if (R.P.get(row, 'aljv') == 4) == goalie and len(R.entries_by_pid[pid]) == 1:
            return e, pid, row
    raise LookupError(team)


def _finish(R, b, base_bytes):
    """Mend, write, verify: (problems, the repair rows)."""
    made = b.mend(Roster(base_bytes))
    b.finish()
    problems, _ = verify(R.f.build(), Roster(base_bytes))
    rows = [r for r in b.log if r[-1] == REPAIRS]
    assert made == len(rows)
    return problems, rows


def test_a_roster_with_nothing_wrong_needs_no_repair(base_bytes):
    R, b = _builder(base_bytes)
    problems, rows = _finish(R, b, base_bytes)
    assert problems == [] and rows == []


def test_a_club_player_left_on_the_free_agent_list_and_listed_twice_is_listed_once_or_not_at_all(base_bytes):
    R, b = _builder(base_bytes)
    _, pid, _ = _player_on(R, AHL_CLUB)
    b.fa_links.append(b.new_link(pid))                       # a step listed a club player
    free = R.link_to_pid[b.fa_links[0]]
    b.fa_links.append(b.new_link(free))                      # and a free agent twice
    problems, rows = _finish(R, b, base_bytes)
    assert problems == []
    listed = [R.link_to_pid.get(R.Q.get(k, 'TWSX')) for k in range(R.Q.cur_rec)]
    assert pid not in listed and listed.count(free) == 1
    assert any(r[1] == 'free agent listed twice: one entry removed' for r in rows)


def test_a_team_listing_a_player_twice_keeps_one_place(base_bytes):
    R, b = _builder(base_bytes)
    _, pid, row = _player_on(R, AHL_CLUB)
    b.new_entry(AHL_CLUB, b.new_link(pid), row)
    problems, rows = _finish(R, b, base_bytes)
    assert problems == []
    assert [t for _, t in Roster(R.f.build()).teams_of(row)] == [AHL_CLUB]
    assert [r[1] for r in rows] == ['listed twice: one place removed']


def test_a_player_put_on_two_teams_stays_on_the_team_his_contract_names(base_bytes):
    R, b = _builder(base_bytes)
    _, pid, row = _player_on(R, AHL_CLUB + 1)
    assert R.P.get(row, 'BSXd') == AHL_CLUB + 2
    b.new_entry(AHL_CLUB, b.new_link(pid), row)             # a step put him on a second AHL club
    problems, rows = _finish(R, b, base_bytes)
    assert problems == []
    assert [t for _, t in Roster(R.f.build()).teams_of(row)] == [AHL_CLUB + 1]
    assert [r[1] for r in rows] == ['on two teams: kept on one']


def test_a_contract_naming_another_team_follows_the_player_and_an_nhl_player_without_one_gets_one(base_bytes):
    R, b = _builder(base_bytes)
    _, _, row = _player_on(R, AHL_CLUB)
    R.P.set(row, 'BSXd', AHL_CLUB + 2)                       # his deal names the next club
    _, _, nhl_row = _player_on(R, 3)
    for f in ('GDhI', 'dhKk'):
        R.P.set(nhl_row, f, 0)                               # an NHL player left with no deal
    problems, rows = _finish(R, b, base_bytes)
    assert problems == []
    assert R.P.get(row, 'BSXd') == AHL_CLUB + 1
    assert R.P.get(nhl_row, 'GDhI') and R.P.get(nhl_row, 'dhKk') and R.P.get(nhl_row, 'BSXd') == 4
    assert sorted(r[1] for r in rows) == ['contract moved to his team', 'given a contract']


def test_what_the_source_already_had_is_left_alone(base_bytes):
    """A double the roster came with (the game saved it; verify allows it) is no leftover of ours: no repair."""
    R0, b0 = _builder(base_bytes)
    _, pid, row = _player_on(R0, AHL_CLUB)
    b0.new_entry(AHL_CLUB + 1, b0.new_link(pid), row)
    b0.finish()
    doubled = R0.f.build()
    R, b = _builder(doubled)
    _, rows = _finish(R, b, doubled)
    assert rows == []
    assert sorted(t for _, t in Roster(R.f.build()).teams_of(row)) == [AHL_CLUB, AHL_CLUB + 1]
    assert L.CLUB >= {AHL_CLUB, AHL_CLUB + 1}
