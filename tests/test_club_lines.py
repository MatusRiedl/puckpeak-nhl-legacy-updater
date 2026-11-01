"""Real lines for the clubs outside the NHL (0.51.0): the Extraliga's match line-ups, a larger database's lines for the
rest, laid over the lines the league steps dealt, club by club and group by group."""
import copy
import sys
from pathlib import Path

import pytest

from legacy_roster import pipeline, schema
from legacy_roster.builder import Data
from legacy_roster.matching import norm
from legacy_roster.roster import Roster

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from providers import hokejcz_lines as H  # noqa: E402

SLOTS_FILE = Path(__file__).resolve().parent.parent / 'tools' / 'club_slots.json'


def side(lines=4, pairs=3):
    """One side of a roster file: goalies 101 / 102, pairs 211.., forward lines 311.. (left, middle, right)."""
    def player(k):
        return {'name': f"First{k}", 'surname': f"Last{k}", 'birth_date': {'date': f"{1990 + k % 10}-01-01 00:00:00"}}
    out = {'101': player(1), '102': player(2)}
    for n in range(1, pairs + 1):
        out[f"2{n}1"], out[f"2{n}2"] = player(10 * n), player(10 * n + 1)
    for n in range(1, lines + 1):
        for k in (1, 2, 3):
            out[f"3{n}{k}"] = player(100 * n + k)
    return out


def test_a_match_line_up_becomes_the_clubs_slots():
    got = H.lines_of(side())
    assert got['g1'] == ['First1', 'Last1', 1991] and got['g2'][1] == 'Last2'
    assert got['l1lw'][1] == 'Last101' and got['l1c'][1] == 'Last102' and got['l1rw'][1] == 'Last103'   # left, middle, right
    assert got['l4rw'][1] == 'Last403' and got['l3rd'][1] == 'Last31'
    assert got['l1ld'][1] == 'Last10' and got['l1rd'][1] == 'Last11'
    assert len(got) == 2 + 12 + 6                                   # no fourth pair, no extra skaters


def test_a_place_without_a_player_is_left_out():
    rows = side()
    del rows['322']
    assert 'l2c' not in H.lines_of(rows) and 'l2lw' in H.lines_of(rows)


def test_the_days_clubs_are_found_by_name_short_name_or_shortcut():
    known = H.club_slots(SLOTS_FILE)
    assert H.club_of({'name': 'HC Sparta Praha', 'short_name': 'Sparta', 'shortcut': 'SPA'}, known) == '115'
    assert H.club_of({'name': 'Banes Motor České Budějovice', 'short_name': 'Motor ČB', 'shortcut': 'CEB'}, known) == '118'
    assert H.club_of({'name': 'Unknown', 'short_name': '?', 'shortcut': '?'}, known) is None


def test_the_match_line_ups_replace_even_strength_and_goalies_and_keep_the_special_teams():
    base = {'115': {'date': 'd', 'slots': {'l1c': ['A', 'B', 1], 'g1': ['G', 'H', 1], 'pp1c': ['P', 'Q', 1]}}}
    match = {'115': {'date': 'm', 'slots': {**{f"l{n}{s}": ['X', f"{n}{s}", 1] for n in (1, 2, 3) for s in
                                              ('lw', 'c', 'rw', 'ld', 'rd')},
                                            **{f"l4{s}": ['X', f"4{s}", 1] for s in ('lw', 'c', 'rw')},
                                            'g1': ['X', 'g1', 1], 'g2': ['X', 'g2', 1]}}, '999': {'slots': {'g1': ['Y']}}}
    out = H.merge(base, match)
    assert out['115']['slots']['l1c'] == ['X', '1c', 1] and out['115']['slots']['g1'] == ['X', 'g1', 1]
    assert out['115']['slots']['pp1c'] == ['P', 'Q', 1] and out['115']['source'] == 'database l:match g:match'
    assert out['999']['slots'] == {}                       # a half category is not taken over


@pytest.fixture(scope='module')
def clubbed(base_bytes, data, pack):
    if not pack.get('club_lines'):
        pytest.skip("the data pack has no club lines")
    full = Data(nhl_players=data.nhl_players, ratings_list=data.ratings_list, iihf=data.iihf,
                season_year=data.season_year, leagues=pack['leagues'], drafts=pack.get('drafts'),
                contracts=data.contracts, club_lines=pack['club_lines'])
    return full, pipeline.build(base_bytes, full, steps=pipeline.steps_for(pack))


def test_clubs_play_the_lines_the_data_names(clubbed, pack):
    full, result = clubbed
    assert result.ok, result.problems
    b = result.builder
    assert len(b.club_lined) >= 150, (len(b.club_lined), b.club_refused)
    ahl = {t['slot'] for t in pack['leagues']['ahl']['teams']}
    # the AHL plays real lines; a club the stored lines left behind keeps its deal (8 of Grand Rapids' 18 had gone by 2026-11-01)
    assert len(ahl - set(b.club_lined)) <= 2, sorted(ahl - set(b.club_lined))
    R = Roster(result.data)
    checked = wrong = 0
    for slot in b.club_lined:
        wanted = pack['club_lines'][str(slot)]['slots']
        who = {}
        for e in range(R.U.cur_rec):
            if R.U.get(e, 'BSXd') == slot:
                prow = R.p_by_id.get(R.link_to_pid.get(R.U.get(e, 'TWSX')))
                who[e] = (norm(R.P.get(prow, 'PedH')), norm(R.P.get(prow, 'RMbQ')))
        for names in (schema.EVEN_STRENGTH,):
            first = {n: wanted.get(n) for n in names}
            if None in first.values():
                continue
            asked = [(norm(w[0]), norm(w[1])) for w in first.values()]
            if not set(asked) <= set(who.values()) or len(set(asked)) != len(asked):
                continue                                              # a group is played when all its players are there
            for n in names:
                if n.endswith(('ld', 'rd')):
                    continue
                tag = schema.SLOT_TAG[n]
                holder = [who[e] for e in who if R.U.get(e, tag)]
                checked += 1
                wrong += not (holder and holder[0] == (norm(first[n][0]), norm(first[n][1])))
    assert checked > 150 and wrong <= 0.03 * checked, (wrong, checked)    # a place for a kind of player he is not stays open


def test_a_second_build_on_the_club_lines_changes_nothing(clubbed, pack):
    full, result = clubbed
    again = pipeline.build(result.data, full, steps=pipeline.steps_for(pack))
    assert again.ok and again.data == result.data


def test_clubs_whose_lines_name_nobody_they_have_keep_their_lines(base_bytes, data, pack, clubbed):
    full, result = clubbed
    ghosts = copy.deepcopy(pack['club_lines'])
    for entry in ghosts.values():
        entry['slots'] = {n: [f"Nobody{k}", f"Nowhere{k}", 1990] for k, n in enumerate(entry['slots'])}
    broken = copy.copy(full)
    broken.club_lines = ghosts
    plain = copy.copy(full)
    plain.club_lines = {}
    a = pipeline.build(base_bytes, broken, steps=pipeline.steps_for(pack))
    b = pipeline.build(base_bytes, plain, steps=pipeline.steps_for(pack))
    assert a.ok and a.builder.club_lined == [] and a.data == b.data


def test_a_group_with_a_few_players_gone_is_completed_and_one_with_many_gone_is_dropped(clubbed, pack):
    full, result = clubbed
    b = result.builder
    slot = next(s for s in b.club_lined if str(s) in pack['club_lines'])
    key = {}
    names = list(pack['club_lines'][str(slot)]['slots'])
    rows = {}
    for e in b.entries_on(slot):
        rows.setdefault({4: 'G', 3: 'D'}.get(b.P.get(b.prow_of_entry(e), 'aljv'), 'F'), []).append(b.prow_of_entry(e))
    key.update({n: rows['G'][0] for n in ('g1',)})                    # goalie group: one of two open (50 % > 40 %): dropped
    key.update({n: rows['F'][k % len(rows['F'])] for k, n in enumerate(schema.POWER_PLAY[:7])})   # power play: 3 of 10 open
    b.fill_real_gaps(slot, key)
    assert 'g1' not in key and 'g2' not in key
    assert all(n in key for n in schema.POWER_PLAY) and len({key[n] for n in schema.POWER_PLAY}) == len(schema.POWER_PLAY)
