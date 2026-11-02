"""The Penticton Vees in custom slot 251 (layout.VEES): in the WHL with art id 902 on a roster for the patched game, a custom
team without the patch where the game's lists can reach them (owner, 2026-11-02; lab round 59)."""
import os

import pytest

from legacy_roster import gamepatch, pipeline, schedule, stock
from legacy_roster import layout as L
from legacy_roster.app.calendar import VEES_NOTE
from legacy_roster.builder import Data
from legacy_roster.leagues import pools
from legacy_roster.matching import norm
from legacy_roster.roster import Roster

from .test_calendar_office import Editor, tabs


def members(R, team):
    return [R.p_by_id[R.link_to_pid[R.U.get(e, 'playerindex')]] for e in range(R.U.cur_rec) if R.U.get(e, 'team') == team]


def chl(pack):
    return Data(season_year=pack['season'], leagues={'chl': pack['leagues']['chl']})


def patched_data(pack):
    return Data(season_year=pack['season'], leagues={'chl': pack['leagues']['chl']}, schedule=pack['schedule'],
                calendar=schedule.ALL_PATCH)


@pytest.fixture(scope='module')
def vees(base_bytes, pack):
    res = pipeline.build(base_bytes, chl(pack), steps=['chl'])
    assert res.problems == []
    return res


@pytest.fixture(scope='module')
def patched(base_bytes, pack):
    """A roster for the patched game with the Vees."""
    res = pipeline.build(base_bytes, patched_data(pack), steps=['chl', pipeline.SCHEDULE], game_patch=True)
    out, problems, _ = pipeline.patch_roster(res, base_bytes, pack, pack['season'])
    assert problems == []
    return out


def test_the_vees_get_the_last_custom_slot_on_every_roster(vees, pack):
    R = Roster(vees.data)
    T = R.T
    assert L.is_vees(T)
    assert T.get(L.VEES, 'JkmY') == 'Penticton Vees' and T.get(L.VEES, 'RPbr') == 'PEN' and T.get(L.VEES, 'nnsx') == 'PEN'
    assert T.get(L.VEES, 'shortname') == 'PENTICTON' and T.get(L.VEES, 'artid') == L.OWN_ART[L.VEES]
    assert T.get(L.VEES, 'league') == L.CUSTOM_LEAGUE
    club = next(c for c in pack['leagues']['chl']['extra'] if c['art'] == 'PEN')
    names = {(norm(R.P.get(r, 'firstname')), norm(R.P.get(r, 'lastname'))) for r in members(R, L.VEES)}
    assert len(names & {(norm(p['first']), norm(p['last'])) for p in club['players']}) >= 20
    assert not any('Penticton' in str(row[2]) and 'No slot' in str(row[2]) for row in vees.log)


@pytest.fixture(scope='module')
def stock_bytes():
    disc = os.environ.get('LEGACY_ROSTER_DISC')
    if not disc or not os.path.exists(disc):
        pytest.skip("no game disc (set LEGACY_ROSTER_DISC to your NHL Legacy disc image)")
    return stock.from_disc(disc)


def test_the_game_s_own_roster_has_no_vees_for_the_unpatched_game(stock_bytes, pack):
    """Lab round 59: the unpatched lists walk as many ids as teams are on, so with 222-233 off slot 251 was never reached
    and an empty "Custom Team 1" appeared in its place."""
    T = Roster(pipeline.build(stock_bytes, chl(pack), steps=['chl']).data).T
    assert not T.get(L.VEES, 'NYKk')
    assert not any(T.get(t, 'NYKk') for t in range(L.TEAM_COUNT - 30, L.TEAM_COUNT))


def test_the_game_s_own_roster_has_them_for_the_patched_game_whose_lists_skip_slots_that_are_off(stock_bytes, pack):
    res = pipeline.build(stock_bytes, chl(pack), steps=['chl'], game_patch=True)
    R = Roster(res.data)
    assert L.is_vees(R.T) and not L.listed(R.T, L.VEES) and len(members(R, L.VEES)) >= 20
    assert not any(row[2] == "Penticton Vees" for row in res.log)


def test_they_are_listed_once_every_slot_before_them_is_on(vees):
    T = Roster(vees.data).T
    assert not L.listed(T, L.VEES)      # the CHL alone leaves the prospect pools' slots off, and the list of changes says so
    assert any(row[2] == "Penticton Vees" for row in vees.log)


def test_their_arena_is_their_own(vees):
    R = Roster(vees.data)
    row = R.T.get(L.VEES, 'arenaid')
    A = R.f['OEtS']
    assert A.get(row, 'arenaname') == 'South Okanagan Events Centre' and A.get(row, 'cityname') == 'Penticton, BC'
    assert not [t for t in range(R.T.cur_rec) if t != L.VEES and R.T.get(t, 'arenaid') == row]


def test_a_second_run_changes_nothing(vees, pack):
    res = pipeline.build(vees.data, chl(pack), steps=['chl'])
    assert res.problems == [] and res.data == vees.data


def test_their_names_are_written(vees):
    names = pipeline.names_of(vees.data)
    assert names['cities']['PENTICTON'] == 'Penticton Vees'
    assert ('PEN', 'Penticton Vees', 'Penticton', 'Vees', 'PEN') in names['teams']


def test_a_players_own_team_in_their_slot_stays(base_bytes, pack):
    R = Roster(base_bytes)
    R.T.set(L.VEES, 'NYKk', 1)
    R.T.set(L.VEES, 'JkmY', 'Bratislava Dragons')
    res = pipeline.build(R.f.build(), chl(pack), steps=['chl'])
    after = Roster(res.data)
    assert res.problems == [] and after.T.get(L.VEES, 'JkmY') == 'Bratislava Dragons' and not members(after, L.VEES)
    assert not L.is_vees(after.T)


def test_a_players_own_team_named_after_them_keeps_the_club(base_bytes, pack):
    R = Roster(base_bytes)
    R.T.set(240, 'NYKk', 1)
    R.T.set(240, 'JkmY', 'Penticton Warriors')
    res = pipeline.build(R.f.build(), chl(pack), steps=['chl'])
    after = Roster(res.data)
    assert res.problems == [] and len(members(after, 240)) >= 20
    assert after.T.get(240, 'JkmY') == 'Penticton Warriors'
    assert not after.T.get(L.VEES, 'NYKk') and not L.is_vees(after.T)


def test_a_prospect_pool_in_their_slot_moves_out(base_bytes, pack):
    """A full update of 0.92 or older left a pool in slot 251: every spare slot was in use."""
    R = Roster(base_bytes)
    R.T.set(L.VEES, 'NYKk', 1)
    for field, value in (('JkmY', 'Panthers System'), ('RPbr', 'FLAS'), ('nnsx', 'FLAS')):
        R.T.set(L.VEES, field, value)
    pool = next(t for t in L.EUROPE if pools.is_pool(R, t))
    prospects = [e for e in range(R.U.cur_rec) if R.U.get(e, 'team') == pool][:6]
    pids = {R.link_to_pid[R.U.get(e, 'playerindex')] for e in prospects}
    for e in prospects:
        R.U.set(e, 'team', L.VEES)
    res = pipeline.build(R.f.build(), chl(pack), steps=['chl'])
    after = Roster(res.data)
    assert res.problems == [] and L.is_vees(after.T) and after.T.get(L.VEES, 'JkmY') == 'Penticton Vees'
    moved = {after.link_to_pid[after.U.get(e, 'playerindex')]: after.U.get(e, 'team') for e in range(after.U.cur_rec)
             if after.link_to_pid[after.U.get(e, 'playerindex')] in pids}
    assert moved and L.VEES not in moved.values()
    again = pipeline.build(res.data, chl(pack), steps=['chl'])
    assert again.problems == [] and again.data == res.data


def test_without_the_chl_step_the_slot_stays_as_it_was(base_bytes, pack):
    res = pipeline.build(base_bytes, Data(season_year=pack['season'], leagues={'ahl': pack['leagues']['ahl']}), steps=['ahl'])
    assert not Roster(res.data).T.get(L.VEES, 'NYKk')


def test_on_a_patch_roster_they_are_a_bc_division_club_with_art_902(patched):
    R = Roster(patched)
    assert gamepatch.league_of(R, L.VEES) == gamepatch.WHL_BC == gamepatch.league_of(R, L.VEES_RINK)
    assert R.T.get(L.VEES, 'artid') == 902 and R.T.get(L.VEES, gamepatch.CREATED) == 0
    assert L.is_vees(R.T)
    assert gamepatch.check_league_fit(R) == [] and gamepatch.check_art_fit(R) == []
    assert sorted(row['TccF'] for row in gamepatch.art_rows(R, 902)) == sorted(L.CLUB_DONOR[L.VEES][1])
    assert {row[gamepatch.ROW_TEAM] for row in gamepatch.art_rows(R, 902)} == {L.VEES}


def test_reading_a_patch_roster_puts_them_back_as_the_builder_knows_them(patched):
    R = Roster(patched)
    gamepatch.unleague(R)
    gamepatch.unart(R)
    assert gamepatch.league_of(R, L.VEES) == gamepatch.CUSTOM_GROUPS
    assert R.T.get(L.VEES, 'artid') == L.OWN_ART[L.VEES] and R.T.get(L.VEES, gamepatch.CREATED) == 1
    assert gamepatch.art_rows(R, 902) == [] and L.is_vees(R.T)


def test_a_slot_251_of_someone_else_is_left_alone_by_the_patch(base_bytes):
    R = Roster(base_bytes)
    R.T.set(L.VEES, 'NYKk', 1)
    R.T.set(L.VEES, 'JkmY', 'Bratislava Dragons')
    gamepatch.league_fit(R)
    gamepatch.art_fit(R)
    assert gamepatch.league_of(R, L.VEES) == gamepatch.CUSTOM_GROUPS and R.T.get(L.VEES, 'artid') != 902
    assert gamepatch.check_league_fit(R) == [] and gamepatch.check_art_fit(R) == []


def test_their_names_read_the_same_from_a_patch_roster(vees, patched):
    assert ('PEN', 'Penticton Vees', 'Penticton', 'Vees', 'PEN') in pipeline.names_of(patched)['teams']



def test_the_calendar_tab_shows_their_68_real_games(vees, pack):
    ed = Editor(vees.data)
    ed.update = type('Update', (), {'pack': pack})()
    cal, _office, _host = tabs(ed)
    cal.follow(L.VEES)
    s = cal.snapshot()
    assert s['league'] == 'WHL' and s['league_note'] == VEES_NOTE and s['summary']['gp'] == 68
    assert s['summary']['home'] == 34 and cal.rail_numbers()[L.VEES]['text'] == '68'
    first = [g for m in s['months'] for g in m['games']][0]
    assert first['date'] == '2026-09-18' and first['vs'] == 'PG'
    cal.follow(min(L.WHL))                          # the other clubs' lists stay the roster's table
    assert not any('Penticton' in str(g) for m in cal.snapshot()['months'] for g in m['games'])


def test_no_vees_no_games(base_bytes, pack):
    ed = Editor(base_bytes)
    ed.update = type('Update', (), {'pack': pack})()
    cal, _office, _host = tabs(ed)
    cal.follow(L.VEES)
    assert cal.snapshot().get('why') and L.VEES not in cal.rail_numbers()
