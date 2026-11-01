"""This season's captains (0.51.1): read from the NHL's game rosters, the AHL / CHL game summaries and the Extraliga's
match line-ups, counted over a team's last games, and worn on every team the update builds: the NHL, every club of a
league that ran, the national teams (led by their players' own captains)."""
import copy
import sys
from pathlib import Path

import pytest

from legacy_roster import layout as L
from legacy_roster import lines, pipeline, schema, verify
from legacy_roster.builder import Data
from legacy_roster.roster import Roster

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from providers import hockeytech as HT  # noqa: E402
from providers import hokejcz_lines as H  # noqa: E402
from providers import nhl_lines as N  # noqa: E402
from providers.letters import count_letters  # noqa: E402

LOWRY, SCHEIFELE, PIONK = 8476392, 8476460, 8477502


# --- the sources ------------------------------------------------------------------------------------------------
def report(visitor, home):
    """A small NHL.com game roster report: rows number / position / name, the two dressed columns, then scratches."""
    def column(rows):
        return ('<td valign="top" width="50%" class="border"><table>'
                + ''.join(f'<tr>\n<td align="center">{n}</td>\n<td align="center">C</td>\n<td>{name}</td>\n</tr>'
                          for n, name in rows) + '</table></td>')
    return ('<table><tr>' + column(visitor) + column(home) + '</tr></table>'
            '<table id="Scratches"><tr><td>' + column([(9, 'SCRATCHED CAPTAIN  (C)')]) + '</td></tr></table>')


def test_the_nhl_game_roster_names_the_letters_per_side():
    html = report([(17, 'ADAM LOWRY  (C)'), (55, 'MARK SCHEIFELE  (A)'), (44, 'JOSH MORRISSEY')],
                  [(91, 'JOHN DOE  (A)'), (14, 'JIM ROE')])
    visitor, home = N.read_letters(html)
    assert visitor == {17: 'C', 55: 'A'} and home == {91: 'A'}           # the scratches are left out
    assert N.read_letters('<html>nothing</html>') == ({}, {})


def test_the_letters_go_to_the_most_worn_c_and_the_most_worn_letters():
    games = [{1: 'C', 2: 'A', 3: 'A'}, {1: 'C', 2: 'A', 4: 'A'}, {1: 'C', 2: 'A'}]
    assert count_letters(games) == {1: 'C', 2: 'A', 4: 'A'}             # 3 and 4 tie on one A: the latest game wins
    assert count_letters([{5: 'A', 6: 'A'}, {5: 'A', 7: 'A'}]) == {5: 'A', 7: 'A', 6: 'A'}   # no captain: three A
    assert count_letters([]) == {}


def test_a_hockeytech_game_summary_names_each_sides_letters():
    summary = {'meta': {'home_team': '7', 'visiting_team': '8'},
               'home_team_lineup': {'players': [{'first_name': 'Sam', 'last_name': 'Wouters', 'status': 'C'},
                                                {'first_name': 'Ty', 'last_name': 'Plain', 'status': ''}]},
               'visitor_team_lineup': {'players': [{'first_name': 'Al', 'last_name': 'Other', 'status': 'A'}]}}
    assert HT.lineup_letters(summary, 7) == {('sam', 'wouters'): 'C'}
    assert HT.lineup_letters(summary, '8') == {('al', 'other'): 'A'}


def test_an_extraliga_match_roster_names_its_letters():
    side = {'101': {'name': 'Jan', 'surname': 'Brankar', 'birth_date': {'date': '1995-01-01'}, 'type': 'c'},
            '311': {'name': 'Roman', 'surname': 'Horák', 'birth_date': {'date': '1991-05-02 00:00:00'}, 'type': 'c'},
            '312': {'name': 'Petr', 'surname': 'Kolár', 'birth_date': {'date': '1993-01-01'}, 'type': 'A'},
            '313': {'name': 'Nikdo', 'surname': 'Nic', 'birth_date': {'date': '1999-01-01'}, 'type': ''}}
    got = H.letters_of(side)
    assert got[('Roman', 'Horák', 1991)] == 'C' and got[('Petr', 'Kolár', 1993)] == 'A'
    assert ('Nikdo', 'Nic', 1999) not in got


# --- the builder ------------------------------------------------------------------------------------------------
def entry_letters(R, team):
    """{(first, last): 'C' | 'A'} of a team in a built roster."""
    out = {}
    for e in range(R.U.cur_rec):
        if R.U.get(e, 'BSXd') == team and R.U.get(e, 'lcCm') in lines.LETTERS:
            prow = R.p_by_id[R.link_to_pid[R.U.get(e, 'TWSX')]]
            out[(R.P.get(prow, 'PedH').strip(), R.P.get(prow, 'RMbQ').strip())] = lines.LETTERS[R.U.get(e, 'lcCm')]
    return out


@pytest.fixture(scope='module')
def lettered(base_bytes, data, pack):
    if not pack.get('lines') or not pack.get('leagues', {}).get('ahl'):
        pytest.skip("the data pack has no lines or no AHL")
    nhl = copy.deepcopy(pack['lines'])
    for entry in nhl.values():
        entry['letters'] = {}
    nhl['WPG']['letters'] = {str(LOWRY): 'C', str(SCHEIFELE): 'A', str(PIONK): 'A'}
    mcdavid = next(p['id'] for p in pack['nhl']['EDM']['forwards'] if p['lastName']['default'] == 'McDavid')
    nhl['EDM']['letters'] = {'1': 'C', str(mcdavid): 'A'}                # a captain not on the team: three A
    leagues = copy.deepcopy(pack['leagues'])
    club = leagues['ahl']['teams'][0]
    skaters = [p for p in club['players'] if p['pos'] != 'G']
    for p in club['players']:
        p['letter'] = None
    skaters[-1]['letter'] = 'C'                                         # the list's last skater: rarely the best
    full = Data(nhl_players=data.nhl_players, ratings_list=data.ratings_list, iihf=data.iihf,
                season_year=data.season_year, leagues=leagues, drafts=data.drafts, contracts=data.contracts,
                club_lines=pack.get('club_lines') or {})
    full.real_lines = nhl
    result = pipeline.build(base_bytes, full, steps=pipeline.steps_for(pack))
    return full, result, club['slot'], skaters[-1]


def test_winnipeg_wears_its_real_letters_and_edmonton_three_alternates(lettered):
    full, result, _slot, _who = lettered
    assert result.ok, result.problems
    R = Roster(result.data)
    wpg = entry_letters(R, L.API_TO_SLOT['WPG'])
    assert wpg.get(('Adam', 'Lowry')) == 'C' and wpg.get(('Mark', 'Scheifele')) == 'A', wpg
    assert sorted(wpg.values()) == ['A', 'A', 'C']
    edm = entry_letters(R, L.API_TO_SLOT['EDM'])
    assert sorted(edm.values()) == ['A', 'A', 'A'] and edm.get(('Connor', 'McDavid')) == 'A', edm


def test_a_club_wears_its_lists_captain(lettered):
    full, result, slot, who = lettered
    R = Roster(result.data)
    got = entry_letters(R, slot)
    assert got.get((who['first'], who['last'])) == 'C', got
    assert list(got.values()).count('C') == 1 and len(got) == 3
    assert slot in result.builder.lettered
    assert any(name == 'Captains' for name, _text in result.lines())


def test_a_national_team_filled_now_is_led_by_a_club_or_nhl_captain(lettered):
    _full, result, _slot, _who = lettered
    b = result.builder
    if not b.national_lettered:
        pytest.skip("this base roster has no empty national team")
    R = Roster(result.data)
    worn = {}
    for e in range(R.U.cur_rec):
        if R.U.get(e, 'BSXd') not in L.NATIONAL and R.U.get(e, 'lcCm') == 1:
            worn[R.link_to_pid[R.U.get(e, 'TWSX')]] = True
    led = 0
    for team in b.national_lettered:
        ents = [e for e in range(R.U.cur_rec) if R.U.get(e, 'BSXd') == team]
        ids = {R.link_to_pid[R.U.get(e, 'TWSX')]: R.U.get(e, 'lcCm') for e in ents}
        dressed = {R.link_to_pid[R.U.get(e, 'TWSX')] for e in ents if R.U.get(e, 'jZSh')}
        captains = [p for p, v in ids.items() if v == 1]
        assert len(captains) == 1
        led += worn.get(captains[0], False) or not any(worn.get(p) for p in dressed)    # dressed skaters come first
    assert led == len(b.national_lettered)


def test_a_second_build_with_the_letters_changes_nothing(lettered, pack):
    full, result, _slot, _who = lettered
    again = pipeline.build(result.data, full, steps=pipeline.steps_for(pack))
    assert again.ok and again.data == result.data


def test_the_real_lines_are_still_on_at_the_end_of_the_build(lettered):
    """A step after lines_from_games that deals a team again lays them back on (contract_strays: with the pack of
    2026-11-01 Anaheim and Buffalo played dealt lines until the second update)."""
    full, result, _slot, _who = lettered
    b = result.builder
    rows = {p['nhl_id']: p['row'] for p in b.api if p.get('nhl_id') and p['row'] is not None}
    seen = 0
    for team in L.NHL_PRIMARY:
        wanted = full.real_lines[L.SLOT_TO_API[team]]['slots']
        named = {rows.get(wanted.get(n)) for n in schema.EVEN_STRENGTH}
        if named <= {b.prow_of_entry(e) for e in b.entries_on(team)}:
            slots, _letters = lines.lineup(b, team)
            assert {b.prow_of_entry(slots[n]) for n in schema.EVEN_STRENGTH} == named, L.SLOT_TO_API[team]
            seen += 1
    assert seen > 20


def test_verify_allows_any_letters_on_a_club(lettered):      # 0.81.0: the player's own choice (lab round 55)
    _full, result, slot, _who = lettered
    R = Roster(result.data)
    ents = [e for e in range(R.U.cur_rec) if R.U.get(e, 'BSXd') == slot]
    kind = {e: R.P.get(R.p_by_id[R.link_to_pid[R.U.get(e, 'TWSX')]], 'aljv') for e in ents}
    skaters = [e for e in ents if kind[e] != 4 and not R.U.get(e, 'lcCm')]
    for e in skaters:                                  # a whole club of captains
        R.U.set(e, 'lcCm', 1)
    goalie = next(e for e in ents if kind[e] == 4)
    R.U.set(goalie, 'lcCm', 2)                         # and a goalie's letter
    problems, _ = verify.structure(R)
    assert not [k for k in problems if k[0] in ('letters', 'goalie letter')]
