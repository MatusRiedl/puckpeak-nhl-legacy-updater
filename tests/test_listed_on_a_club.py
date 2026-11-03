"""A player the game saved on a club AND on the free-agent list (a tester's roster: Joe Sakic on Colorado and on the list)
stays on his club with his deal. Before, the builder cleared the deal of everyone on the list and every Roster editor Save
was refused: "Joe Sakic (COL): a cap hit of $0.000M (and 2 more)"."""
from legacy_roster import layout as L
from legacy_roster.builder import Builder, Data
from legacy_roster.editor import model
from legacy_roster.roster import Roster
from legacy_roster.verify import structure

COLORADO = L.API_TO_SLOT['COL']


def _sakic_twice(base_bytes):
    """The base with Joe Sakic (a teamless legend) on Colorado and on the free-agent list, his deal as the legend record
    has it, as the game saved the tester's roster."""
    R = Roster(base_bytes)
    b = Builder(R, Data(season_year=2026))
    prow = next(i for i in range(R.P.cur_rec) if R.name(i) == 'Joe Sakic')
    link = b.new_link(R.P.get(prow, 'zIBw'))
    b.new_entry(COLORADO, link, prow)
    R.P.set(prow, 'BSXd', COLORADO + 1)
    b.fa_links.append(link)
    b.finish()
    return R.f.build(), R.P.get(prow, 'zIBw')


def _listed(R):
    return {R.link_to_pid.get(R.Q.get(i, 'TWSX')) for i in range(R.Q.cur_rec)}


def test_verify_names_a_free_agent_on_a_club(base_bytes):
    data, pid = _sakic_twice(base_bytes)
    assert ('fa on team', pid) in structure(Roster(data))[0]


def test_a_player_on_a_club_and_the_free_agent_list_keeps_his_club_and_deal(base_bytes):
    data, pid = _sakic_twice(base_bytes)
    before = Roster(data)
    deal = {f: before.P.get(before.p_by_id[pid], f) for f in ('BSXd', 'GDhI', 'dhKk')}
    assert pid in _listed(before) and deal['dhKk']
    res = model.apply_edits(data, {}, {}, 2026)
    assert res.problems == []                       # was: a cap hit of $0.000M, 0 seasons, the contract status
    R = Roster(res.data)
    prow = R.p_by_id[pid]
    assert pid not in _listed(R)
    assert [t for _, t in R.teams_of(prow)] == [COLORADO]
    assert {f: R.P.get(prow, f) for f in deal} == deal
    assert any(row[1] == 'taken off the free-agent list' and row[2] == 'Joe Sakic' for row in res.log)
    again = model.apply_edits(res.data, {}, {}, 2026)
    assert again.problems == [] and again.data == res.data


def test_a_step_that_leaves_a_club_player_on_the_free_agent_list_is_mended_before_the_contracts(base_bytes):
    """A step that lists a player who still has a club place (0.95.0: Nick Jensen and his prospect pool) no longer
    fails verify: contracts() takes him off the list, as the start of the build does with the game's own doubles."""
    R = Roster(base_bytes)
    b = Builder(R, Data(season_year=2026))
    club = next(t for t in sorted(L.CLUB) if t not in L.NHL_ALL and R.team_roster(t))
    e = next(i for i in range(R.U.cur_rec) if R.U.get(i, 'BSXd') == club)
    pid = b.pid_of_entry(e)
    b.fa_links.append(b.new_link(pid))
    b.contracts()
    assert pid not in {R.link_to_pid.get(link) for link in b.fa_links}
    assert any(row[1] == 'taken off the free-agent list' and row[2] == R.name(R.p_by_id[pid]) for row in b.log)
