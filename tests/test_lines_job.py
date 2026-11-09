"""tools/lines_job.py: the server's daily lines job (docs/notes/lines-job.md). No network: a small made-up pack and
fetch results stand in for the published pack and the line sources."""
import copy
import datetime
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import clean_check  # noqa: E402
import lines_job  # noqa: E402
from legacy_roster import datasource  # noqa: E402

WHEN = datetime.datetime(2026, 11, 9, 10, 0, tzinfo=datetime.timezone.utc)
CODES = ('ANA', 'BOS', 'CBJ', 'MTL', 'TOR', 'WPG')


def nhl_entry(base, date='2026-11-01', source='l:announced pp:games', letters=None):
    """An NHL team's entry with every even-strength slot and both goalies filled by distinct ids from `base`."""
    slots = {name: base + n for n, name in enumerate(lines_job.EVEN)}
    slots['pp1c'] = base + 50
    return {'date': date, 'source': source, 'games': 5, 'slots': slots,
            'letters': letters if letters is not None else {str(base): 'C', str(base + 1): 'A'}}


def club_entry(tag, date='2026-10-01', special=True):
    """A club's entry from the database: even strength, goalies and (when `special`) a power play."""
    slots = {name: ['First', f"{tag}{n}", 1999] for n, name in enumerate(lines_job.EVEN)}
    if special:
        slots['pp1c'] = ['Power', f"{tag}pp", 1998]
    return {'date': date, 'source': 'database', 'slots': slots}


def match_entry(tag, date='2026-11-08'):
    """An Extraliga club's match line-up as hokejcz_lines.lines gives it (even strength and goalies only)."""
    return {'date': date, 'game': 1, 'games': 5,
            'slots': {name: ['Match', f"{tag}{n}", 2001] for n, name in enumerate(lines_job.EVEN)}, 'letters': {}}


def make_pack():
    lines = {code: nhl_entry(1000 * (k + 1)) for k, code in enumerate(CODES)}
    clubs = {'40': club_entry('ahl'), '105': club_entry('cz'), '106': club_entry('cy')}
    return {'format': datasource.PACK_FORMAT, 'season': 2026, 'generated': '2026-11-05T09:00:00Z',
            'sources': {'lines': {'date': '2026-11-01', 'count': len(lines)},
                        'club_lines': {'date': '2026-11-01', 'count': len(clubs)},
                        'nhl': {'date': '2026-11-05', 'count': 32}},
            'lines': lines, 'club_lines': clubs, 'nhl': {'teams': list(CODES)}}


def test_refresh_lays_in_the_fetched_lines_and_leaves_every_other_club_alone():
    pack = make_pack()
    before = copy.deepcopy(pack)
    new_tor = nhl_entry(9000, date='2026-11-09')
    new, report = lines_job.refresh(pack, {'TOR': new_tor}, {'105': match_entry('m')}, WHEN)
    assert pack == before                                   # the pack itself is not changed
    assert new['lines']['TOR'] == new_tor
    assert new['lines']['BOS'] == pack['lines']['BOS']
    assert new['club_lines']['40'] == pack['club_lines']['40']
    assert new['club_lines']['106'] == pack['club_lines']['106']
    cz = new['club_lines']['105']
    assert cz['slots']['l1c'] == ['Match', 'm1', 2001]      # even strength from the match
    assert cz['slots']['pp1c'] == ['Power', 'czpp', 1998]   # the power play stays the database's
    assert 'database' in cz['source'] and 'l:match' in cz['source'] and cz['date'] == '2026-11-08'
    assert report['nhl'] == ['TOR'] and report['extraliga'] == ['105']
    assert new['generated'] == '2026-11-09T10:00:00Z'
    assert new['sources']['lines']['date'] == '2026-11-09' and new['sources']['club_lines']['date'] == '2026-11-09'
    assert new['sources']['nhl'] == pack['sources']['nhl']
    assert (new['format'], new['season'], new['nhl']) == (pack['format'], pack['season'], pack['nhl'])


def test_a_team_whose_lines_name_a_player_twice_or_are_empty_keeps_its_entry():
    pack = make_pack()
    twice = nhl_entry(9000, date='2026-11-09')
    twice['slots']['l2c'] = twice['slots']['l1c']
    new, report = lines_job.refresh(pack, {'TOR': twice, 'WPG': {'date': '2026-11-09', 'slots': {}}}, {}, WHEN)
    assert new['lines']['TOR'] == pack['lines']['TOR'] and new['lines']['WPG'] == pack['lines']['WPG']
    assert set(report['nhl_kept']) == {'TOR', 'WPG'} and report['nhl'] == []
    assert new['sources']['lines'] == pack['sources']['lines']    # nothing laid in: the date stays


def test_a_category_the_fetch_lacks_stays_the_packs_older_one():
    pack = make_pack()
    goalies_only = nhl_entry(9000, date='2026-11-09', source='g:announced pp:announced')
    goalies_only['slots'] = {k: v for k, v in goalies_only['slots'].items() if not k.startswith('l')}
    goalies_only['slots']['l1c'] = 9999                         # a part of even strength is not a whole
    new, report = lines_job.refresh(pack, {'NJD': goalies_only, 'TOR': goalies_only}, {}, WHEN)
    tor = new['lines']['TOR']
    assert {k: v for k, v in tor['slots'].items() if k.startswith('l')} == \
        {k: v for k, v in pack['lines']['TOR']['slots'].items() if k.startswith('l')}
    assert tor['slots']['g1'] == goalies_only['slots']['g1'] and tor['date'] == '2026-11-09'
    assert tor['source'] == 'g:announced pp:announced l:older'
    assert report['nhl_older'] == {'TOR': ['l']} and report['nhl'] == ['NJD', 'TOR']
    assert new['lines']['NJD'] == goalies_only                  # a team the pack has no lines for: as fetched
    assert lines_job.whole(tor) and lines_job.guards(pack, new) == []


def test_a_team_the_games_gave_no_captains_keeps_the_packs_letters():
    pack = make_pack()
    new, _ = lines_job.refresh(pack, {'TOR': nhl_entry(9000, date='2026-11-09', letters={})}, {}, WHEN)
    assert new['lines']['TOR']['letters'] == pack['lines']['TOR']['letters']
    assert new['lines']['TOR']['slots']['l1c'] == 9001


def test_build_datapack_lays_its_lines_as_the_job_does_and_a_second_build_changes_nothing():
    """tools/build_datapack.py's `--refresh lines` calls lay_nhl with letters=False (its give_letters fills a team
    without captains from the larger database)."""
    pack = make_pack()
    lacking = nhl_entry(9000, date='2026-11-09', letters={})
    lacking['slots'] = {k: v for k, v in lacking['slots'].items() if not k.startswith('l')}
    fetched = {'TOR': lacking, 'WPG': {'date': '2026-11-09', 'slots': {}}}
    lines, report = lines_job.lay_nhl(pack['lines'], fetched, letters=False)
    assert lines['TOR']['letters'] == {} and lines['TOR']['source'].endswith('l:older')
    assert lines['WPG'] == pack['lines']['WPG'] and lines['BOS'] == pack['lines']['BOS']
    assert report['nhl_older'] == {'TOR': ['l']} and set(report['nhl_kept']) == {'WPG'}
    again, _ = lines_job.lay_nhl(lines, fetched, letters=False)  # the next build reads the pack this one wrote
    assert again == lines


def test_guards_pass_a_good_refresh():
    pack = make_pack()
    new, _ = lines_job.refresh(pack, {'TOR': nhl_entry(9000, date='2026-11-09')}, {}, WHEN)
    assert lines_job.guards(pack, new) == []


@pytest.mark.parametrize('spoil, says', [
    (lambda p: p.update(season=2027), 'season'),
    (lambda p: p.update(format=datasource.PACK_FORMAT + 1), 'format'),
    (lambda p: p['sources']['lines'].update(count=2), 'lines: 2 entries'),
    (lambda p: p['sources'].pop('nhl'), 'nhl: in the published pack, missing now'),
    (lambda p: [e.update(source='l:games') for e in p['lines'].values()], 'announced'),
    (lambda p: [e['slots'].pop('l4rw') for e in p['lines'].values()], 'whole even strength'),
    (lambda p: p['lines']['TOR'].update(source=clean_check._G + '27'), 'must not ship'),
])
def test_guards_refuse_a_pack_that_lost_something_or_changed_its_kind(spoil, says):
    pack = make_pack()
    new = copy.deepcopy(pack)
    spoil(new)
    problems = lines_job.guards(pack, new)
    assert any(says in p for p in problems), problems


def test_the_pack_file_reads_back_as_written_and_is_always_the_same_bytes(tmp_path):
    pack = make_pack()
    data = datasource.pack_bytes(pack)
    path = tmp_path / 'datapack.json.gz'
    path.write_bytes(data)
    assert datasource.read_pack(str(path)) == pack
    assert datasource.pack_bytes(datasource.read_pack(str(path))) == data


def test_write_pack_replaces_the_pack_in_one_step_and_keeps_the_one_before(tmp_path, monkeypatch):
    path = str(tmp_path / 'datapack.json.gz')
    first, second = make_pack(), make_pack()
    second['generated'] = '2026-11-09T10:00:00Z'
    lines_job.write_pack(path, first)
    lines_job.write_pack(path, second)
    assert datasource.read_pack(path) == second
    assert datasource.read_pack(path + '.prev') == first
    assert sorted(os.listdir(tmp_path)) == ['datapack.json.gz', 'datapack.json.gz.prev']
    monkeypatch.setattr(datasource, 'usable', lambda pack: False)       # a pack that does not read back
    with pytest.raises(ValueError):
        lines_job.write_pack(path, first)
    assert datasource.read_pack(path) == second
    assert sorted(os.listdir(tmp_path)) == ['datapack.json.gz', 'datapack.json.gz.prev']


def test_a_publish_keeps_the_servers_newer_lines_and_only_those():
    local, server = make_pack(), make_pack()
    server['lines']['TOR'] = nhl_entry(9000, date='2026-11-09')         # the job's, newer
    local['lines']['MTL'] = nhl_entry(8000, date='2026-11-08')          # the maintainer's, newer
    server['club_lines']['105'] = club_entry('new', date='2026-11-09')
    server['sources']['lines']['date'] = '2026-11-09'
    merged, taken = lines_job.take_newer(local, server, WHEN)
    assert taken == ['lines:TOR', 'club_lines:105']
    assert merged['lines']['TOR'] == server['lines']['TOR']
    assert merged['lines']['MTL'] == local['lines']['MTL']
    assert merged['club_lines']['105'] == server['club_lines']['105']
    assert merged['club_lines']['40'] == local['club_lines']['40']
    assert merged['sources']['lines']['date'] == '2026-11-09'
    assert merged['generated'] == '2026-11-09T10:00:00Z'
    assert local['lines']['TOR'] == make_pack()['lines']['TOR']         # the local pack itself is not changed
    same, none = lines_job.take_newer(local, make_pack(), WHEN)
    assert same is local and none == []


def run(tmp_path, fetch, **kw):
    path = str(tmp_path / 'files' / 'datapack.json.gz')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(datasource.pack_bytes(make_pack()))
    archive = str(tmp_path / 'archive')
    with open(path, 'rb') as f:
        before = f.read()
    result = lines_job.run_once(path, archive=archive, fetch=fetch, when=WHEN, **kw)
    with open(os.path.join(archive, 'status.json'), encoding='utf-8') as f:
        status = json.load(f)
    with open(path, 'rb') as f:
        after = f.read()
    return result, status, before, after, path, archive


def test_a_run_publishes_good_lines_and_keeps_a_copy(tmp_path):
    result, status, before, after, path, archive = run(
        tmp_path, lambda season: ({'TOR': nhl_entry(9000, date='2026-11-09')}, {'105': match_entry('m')}))
    assert result == 'published' and status['result'] == 'published'
    assert datasource.read_pack(path)['lines']['TOR']['slots']['l1c'] == 9001
    with open(path + '.prev', 'rb') as f:
        assert f.read() == before
    assert sorted(os.listdir(archive)) == ['datapack-20261109T100000Z.json.gz', 'status.json']


def test_a_run_with_nothing_new_leaves_the_pack(tmp_path):
    pack = make_pack()
    result, status, before, after, _, _ = run(tmp_path, lambda season: ({'TOR': pack['lines']['TOR']}, {}))
    assert result == 'unchanged' and status['result'] == 'unchanged' and after == before


def test_a_run_that_fails_a_guard_leaves_the_pack(tmp_path):
    games_only = {code: nhl_entry(9000 + 100 * k, date='2026-11-09', source='l:games') for k, code in enumerate(CODES)}
    result, status, before, after, path, _ = run(tmp_path, lambda season: (games_only, {}))
    assert result == 'refused' and status['result'] == 'refused' and after == before
    assert any('announced' in p for p in status['problems'])
    assert not os.path.exists(path + '.prev')


@pytest.mark.parametrize('fetch', [lambda season: ({}, {}), lambda season: 1 / 0])
def test_a_run_whose_sources_fail_leaves_the_pack(tmp_path, fetch):
    result, status, before, after, _, _ = run(tmp_path, fetch)
    assert result == 'failed' and status['result'] == 'failed' and after == before


def test_a_dry_run_writes_nothing(tmp_path):
    result, status, before, after, path, archive = run(
        tmp_path, lambda season: ({'TOR': nhl_entry(9000, date='2026-11-09')}, {}), dry_run=True)
    assert result == 'published' and status['result'] == 'dry run' and after == before
    assert not os.path.exists(path + '.prev')
    assert os.listdir(archive) == ['status.json']


def test_the_next_run_is_today_at_the_hour_or_else_tomorrow():
    at = '10:00'
    assert lines_job.next_run(WHEN.replace(hour=9, minute=59), at) == WHEN
    assert lines_job.next_run(WHEN, at) == WHEN + datetime.timedelta(days=1)
    assert lines_job.next_run(WHEN.replace(hour=23), at) == WHEN + datetime.timedelta(days=1)
