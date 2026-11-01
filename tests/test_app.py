"""The new window's controllers (app/) with a pretend window: what the page is told, what its buttons do.
Needs the base roster (conftest.py); nothing is written outside the test's own folder."""
import json
import os
import shutil
import time

import pytest

from legacy_roster import savedata


class FakeHost:
    """What a controller needs from the window, with the answers of file dialogs set by the test."""

    def __init__(self):
        self.dirty, self.lines, self.opened = set(), [], []
        self.pick = None

    def changed(self, name):
        self.dirty.add(name)

    def log(self, *lines):
        self.lines.extend(lines)

    def log_clear(self):
        self.lines = []

    def send(self, event, payload=None):
        pass

    def ask_open(self, *args, **kwargs):
        return self.pick

    def ask_folder(self, *args, **kwargs):
        return self.pick

    def ask_save(self, *args, **kwargs):
        return self.pick

    def open_path(self, path):
        self.opened.append(path)

    def open_url(self, url):
        self.opened.append(url)


def wait(condition, seconds=120):
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError("timed out")


@pytest.fixture
def app(base_dir, tmp_path, monkeypatch, pack):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    sd = tmp_path / 'rpcs3' / 'dev_hdd0' / 'home' / '00000001' / 'savedata'
    shutil.copytree(base_dir, sd / os.path.basename(base_dir))
    exe = tmp_path / 'rpcs3' / 'rpcs3.exe'
    exe.write_bytes(b'')
    from legacy_roster.app import settings as S
    monkeypatch.setattr(S, 'save', lambda values: None)
    from legacy_roster.app.editor import EditorController
    from legacy_roster.app.uniforms import UniformsController
    from legacy_roster.app.update import UpdateController
    host = FakeHost()
    upd = UpdateController(host, settings={'rpcs3': str(exe)}, pack=pack, photos=False)
    ed = EditorController(host, upd)
    uni = UniformsController(host, ed)
    upd.start_up()
    wait(lambda: not upd.scanning and upd.slots)
    yield host, upd, ed, uni, str(sd)
    try:                                # a rescan a save started ends inside the test's folder
        wait(lambda: not upd.scanning and not ed.busy, 60)
    except AssertionError:
        pass


def idle(ed):
    def calm():
        with ed.lock:               # `busy` goes off just before the result is taken in, under the lock
            return not ed.busy and ed.after_busy is None
    wait(lambda: calm() and (time.sleep(0.05) or calm()))


def test_the_update_tab_lists_the_roster_and_says_nothing_about_other_versions(app):
    _host, upd, _ed, _uni, _sd = app
    s = upd.snapshot()
    json.dumps(s)
    assert [r['folder'] for r in s['rosters']] == [os.path.basename(upd.slots[0].folder)]
    assert s['selected'] == upd.slots[0].folder
    assert s['rpcs3']['note'] is None           # the "Found 2 rosters ..." line is gone
    assert s['save']['button']['enabled']


def test_the_roster_card_counts_the_ten_rosters_the_game_lists(app):
    from legacy_roster.app import settings as S
    _host, upd, _ed, _uni, sd = app
    room = upd.snapshot()['room']
    assert room['counts'] == [{'region': 'EU', 'text': '1 of 10', 'tone': 'good'}] and room['text'] is None and 'at most 10' in room['tip']
    for n in range(10, 19):                     # nine more folders: the 10th and later the game does not list
        shutil.copytree(upd.slots[0].path, os.path.join(sd, f'BLES0215302{n:02d}'))
    upd.set_rpcs3(upd.rpcs3.where, quiet=True)
    wait(lambda: not upd.scanning and len(upd.slots) >= 10)
    upd.set_save_mode(S.AS_NEW)
    s = upd.snapshot()
    assert s['room']['counts'][0]['tone'] == 'bad' and s['room']['tone'] == 'bad'
    assert not s['save']['button']['enabled'] and 'only 10 rosters' in s['status']['text']
    upd.set_save_mode(S.IN_PLACE)
    assert upd.snapshot()['save']['button']['enabled']          # updating a roster in place still works
    for n in range(19, 21):
        shutil.copytree(upd.slots[0].path, os.path.join(sd, f'BLES0215302{n:02d}'))
    upd.set_rpcs3(upd.rpcs3.where, quiet=True)
    wait(lambda: not upd.scanning and len(upd.slots) >= 12)
    rows = {r['folder']: r for r in upd.snapshot()['rosters']}
    assert rows['BLES021530220']['chip']['kind'] == 'hidden' and 'does not show' in rows['BLES021530220']['problem']
    assert rows['BLES021530218']['chip'] is None or rows['BLES021530218']['chip']['kind'] != 'hidden'


def test_editor_shows_teams_and_a_card_and_applies_an_edit(app):
    host, upd, ed, _uni, _sd = app
    ed.opened()
    idle(ed)
    s = ed.snapshot()
    json.dumps(s)
    assert s['loaded'] and s['league'] == 'NHL' and s['rows']
    row = next(r for r in s['rows'] if r['pos'] == 'D')
    ed.pick_player(row['id'])
    card = ed.snapshot()['card']
    assert card['title'] == row['name'] and card['values']['num'] == str(row['num'])
    key = card['key']
    # a defenseman's card goes through unchanged (the game's own ratings may be below 40)
    assert ed.apply(dict(card['values']), quiet=True) == 'nothing'
    new_num = '12' if card['values']['num'] != '12' else '13'
    assert ed.apply(dict(card['values'], num=new_num)) == 'applied'
    idle(ed)
    s = ed.snapshot()
    assert s['card']['key'] != key and s['card']['values']['num'] == new_num and s['card']['undo']
    assert any(r['tag'] == 'edited' for r in s['rows'])
    assert s['edits_count'] == 1 and 'update' in host.dirty
    ed.undo()
    idle(ed)
    assert ed.snapshot()['edits_count'] == 0


def test_the_card_changes_a_players_type_and_takes_another_players_face(app):
    _host, _upd, ed, _uni, _sd = app
    ed.opened()
    idle(ed)
    s = ed.snapshot()
    assert [n for n, _ in s['choices']['styles']['D']] == list(range(1, 11))      # free editing: any skater type
    assert dict(s['choices']['styles']['F'])[6] == 'PLY · Playmaker' and s['choices']['skins'][0] == 1
    row = next(r for r in s['rows'] if r['pos'] == 'D')
    ed.pick_player(row['id'])
    card = ed.snapshot()['card']
    assert card['values']['style'] in ('1', '2', '3', '4') and card['values']['head'] and card['face_note']
    other = next(p for p in ed.snap.by_who.values() if p.face['head'] < 60000 and p.face['head'] in ed.snap.heads
                 and p.face['head'] != int(card['values']['head']))
    ed.face_open()
    assert ed.snapshot()['modal']['kind'] == 'face' and ed.snapshot()['modal']['generic'][0] >= 60000
    ed.face_search(other.last)
    found = ed.snapshot()['modal']['found']
    assert any(f['who'] == other.who for f in found)
    json.dumps(ed.snapshot())
    ed.face_pick_player(other.who)
    s = ed.snapshot()
    pick = s['card']['face_pick']
    assert s['modal'] is None and pick['head'] == str(other.face['head']) and other.name in pick['note']
    style = '1' if card['values']['style'] != '1' else '2'
    typed = dict(card['values'], style=style, head=pick['head'], skin=pick['skin'], eyes=pick['eyes'])
    assert ed.apply(typed) == 'applied'
    idle(ed)
    s = ed.snapshot()
    assert s['card']['values']['style'] == style and s['card']['values']['head'] == pick['head']
    assert s['card']['face_note'].startswith("Same head as") and s['card']['face_pick'] is None
    edit = next(iter(ed.edits.values()))
    assert edit['set']['style'] == int(style) and edit['set']['head'] == other.face['head']
    assert ed.apply(dict(s['card']['values'], style='11')) == 'error'       # no such type
    assert ed.apply(dict(s['card']['values'], style='7')) == 'applied'      # a forward's type on a defenceman: free


def test_a_card_typed_on_but_not_applied_is_applied_on_save_as_new(app):
    _host, upd, ed, _uni, sd = app
    upd.set_save_mode('new')
    ed.opened()
    idle(ed)
    row = ed.snapshot()['rows'][0]
    ed.pick_player(row['id'])
    values = ed.snapshot()['card']['values']
    old = upd.selected
    before = {s.folder for s in savedata.list_rosters(sd)}
    ed.save(dict(values, first='Changed'))
    wait(lambda: len(savedata.list_rosters(sd)) == len(before) + 1 and not ed.busy)
    assert ed.status[1] == 'good' and ed.status[0].startswith("Saved as")
    assert any(e['set'].get('first') == 'Changed' for e in ed.edits.values())
    # Setup and the team tabs go on with the new roster, so the edit counts as saved (a tester: "1 not saved yet" stayed)
    new = ({s.folder for s in savedata.list_rosters(sd)} - before).pop()
    wait(lambda: upd.selected == new and ed.slot is not None and ed.slot.folder == new and ed.view is not None
         and not upd.scanning)
    idle(ed)
    assert old != new and ed.snapshot()['unsaved'] == 0 and ed.status[0].startswith("Saved as")
    assert any(p.first == 'Changed' for p in ed.raw.players.values())


def test_an_export_from_a_roster_file_shows_that_file_in_the_team_tabs(app, tmp_path):
    """A tester picked an updated roster file for the export and the Roster tab still showed the roster of Setup (the
    game's own, 2014-15): the team tabs show the file now, never save into it, and say the edits go into the export."""
    from legacy_roster.app.editor import ROSTER_FILE
    from legacy_roster.editor import model
    _host, upd, ed, _uni, _sd = app
    raw = open(upd.selected_slot().sys_data, 'rb').read()
    snap = model.Snapshot(raw)
    first = snap.players[snap.rosters[0][0]]
    made = model.apply_edits(raw, {first.who: {'label': first.name, 'set': {'first': 'Picked'}}}, {}, 2026)
    assert not made.problems
    path = tmp_path / 'file' / 'SYS-DATA'
    path.parent.mkdir()
    path.write_bytes(made.data)
    upd.set_export_only(True)
    wait(lambda: not upd.scanning)
    upd.use_export_file(str(path))
    assert upd.roster_file() == str(path)
    ed.show_tab('roster')
    idle(ed)
    assert getattr(ed.slot, 'file', False) and any(p.first == 'Picked' for p in ed.raw.players.values())
    s = ed.snapshot()
    assert s['save']['file'] == ROSTER_FILE and not s['save']['button']['enabled'] and s['unsaved'] == 0
    ed.save()
    assert ed.status[0] == ROSTER_FILE and path.read_bytes() == made.data
    upd.select(upd.slots[0].folder)                 # a roster of RPCS3 picked again: the tabs show it
    ed.show_tab('roster')
    idle(ed)
    assert not getattr(ed.slot, 'file', False) and not any(p.first == 'Picked' for p in ed.raw.players.values())


def test_a_bad_card_is_named_when_another_player_is_picked(app):
    _host, _upd, ed, _uni, _sd = app
    ed.opened()
    idle(ed)
    rows = ed.snapshot()['rows']
    ed.pick_player(rows[0]['id'])
    ed.pick_player(rows[1]['id'], dict(ed.snapshot()['card']['values'], birth='soon'))
    assert ed.status[1] == 'bad' and "were not taken" in ed.status[0]
    assert ed.snapshot()['card']['title'] == rows[1]['name']


def test_search_team_window_and_my_edits(app):
    _host, _upd, ed, _uni, _sd = app
    ed.opened()
    idle(ed)
    ed.search('a')
    assert ed.snapshot()['searching'] and ed.snapshot()['rows']
    ed.search('')
    assert not ed.snapshot()['searching']
    ed.team_open()
    m = ed.snapshot()['modal']
    assert m['kind'] == 'team' and m['fields']['abbr']
    ed.team_apply({'full': 'Test Team', 'city': '', 'abbr': ''})
    idle(ed)
    assert ed.teams[str(ed.team)] == {'full': 'Test Team'} and ed.snapshot()['team_name'] == 'Test Team'
    ed.edits_open()
    items = ed.snapshot()['modal']['items']
    assert [i['kind'] for i in items] == ['team']
    ed.edits_remove('team', items[0]['key'])
    idle(ed)
    assert ed.teams == {}


def test_new_player_shows_on_the_card_once_added(app):
    _host, _upd, ed, _uni, _sd = app
    ed.opened()
    idle(ed)
    ed.new_player()
    card = ed.snapshot()['card']
    assert card['new'] and card['values']['ovr'] == '70'
    values = dict(card['values'], first='Zed', last='Testman', num='91', birth='2005-01-02')
    assert ed.apply(values) == 'applied'
    idle(ed)
    card = ed.snapshot()['card']
    assert card['title'] == 'Zed Testman' and not card['new']


def test_a_new_player_gets_a_created_look_from_the_look_window(app):
    from legacy_roster import faces
    from legacy_roster.app.editor import LOOK_NOT_HERE
    _host, _upd, ed, _uni, _sd = app
    ed.opened()
    idle(ed)
    ed.new_player()
    card = ed.snapshot()['card']
    look = card['values']['look']
    assert card['created'] and card['looks_left']['S'] > 0 and card['looks_left']['G'] > 0
    assert look and faces.look_wrong(look) is None and set(look) == set(faces.DEFAULT_LOOK)
    ed.look_open(look)
    m = ed.snapshot()['modal']
    json.dumps(ed.snapshot())
    assert m['kind'] == 'look' and m['look'] == look and m['words'] == faces.look_words(look)
    assert [r['key'] for r in m['rows']] == list(faces.LOOK)
    hair = next(n for n, _w in faces.LOOK['hair'][1] if n != look['hair'])
    ed.look_set('hair', hair)
    ed.look_set('hair', 99)                     # not one of the game's choices: ignored
    assert ed.snapshot()['modal']['look'] == dict(look, hair=hair)
    ed.look_done()
    s = ed.snapshot()
    assert s['modal'] is None and s['card']['look_pick']['look'] == dict(look, hair=hair)
    values = dict(card['values'], first='Ivo', last='Looksmith', num='92', birth='2005-01-02',
                  look=s['card']['look_pick']['look'])
    assert ed.apply(values) == 'applied'
    idle(ed)
    card = ed.snapshot()['card']
    assert card['title'] == 'Ivo Looksmith' and card['created'] and card['values']['look'] == dict(look, hair=hair)
    edit = next(e for e in ed.edits.values() if e.get('label') == 'Ivo Looksmith')
    assert edit['look'] == dict(look, hair=hair) and not set(edit['set']) & set(faces.FIELDS)
    # a player of an ordinary record keeps the Face window: no look for him
    row = next(r for r in ed.snapshot()['rows'] if r['name'] != 'Ivo Looksmith')
    ed.pick_player(row['id'])
    card = ed.snapshot()['card']
    assert not card['created'] and card['values']['look'] is None
    ed.look_open(look)
    assert ed.snapshot()['modal'] is None and ed.status[0] == LOOK_NOT_HERE
    assert ed.apply(dict(card['values'], look=look)) == 'error'


def test_the_draft_and_pro_tab_makes_class_players_and_a_pro(app):
    from legacy_roster import draftclass, layout as L
    from legacy_roster.app.prospects import PRO, ProspectsController
    from legacy_roster.editor import card as C, model
    host, _upd, ed, _uni, _sd = app
    ed.opened()
    idle(ed)
    pr = ProspectsController(host, ed)
    s = pr.snapshot()
    json.dumps(s)
    year = ed.snap.season_year + 1
    assert [v['value'] for v in s['views']] == [*draftclass.class_years(year - 1), PRO]
    assert s['view'] == year and s['rows'] == [] and s['warn']          # the base roster is not for the patched game
    assert s['room']['skaters'] > 0 and s['room']['goalies'] > 0
    # a new prospect: the editor's card, filled for this draft, and the tier set before Apply
    pr.add()
    card = ed.snapshot()['card']
    assert card['new'] and card['title'] == f"New prospect for the {year} draft"
    assert card['values']['birth'] == f"{year - 18}-03-01" and card['values']['team'] in L.CHL
    pr.set('tier', 1)
    b = pr.snapshot()['prospect']
    assert (b['tier'], b['potential'], b['lo'], b['hi']) == (1, 59, 59, 59) and 'went 2nd overall' in b['hint']
    assert ed.apply(dict(card['values'], first='Ola', last='Testberg', num='77')) == 'applied'
    idle(ed)
    key = next(k for k, e in ed.edits.items() if e.get('label') == 'Ola Testberg')
    assert ed.edits[key]['prospect'] == {'tier': 1}
    s = pr.snapshot()
    row = s['rows'][0]
    # shown with this visit's edits, not in the roster's file yet: the tab says Save puts him in
    assert len(s['rows']) == 1 and row['key'] == key and row['state'] == 'unsaved' and s['unsaved']
    assert (row['tier'], row['potential']) == (1, 59)
    assert s['selected'] == key and s['views'][0]['count'] == 1
    assert not ed.view[0].problems
    pid = next(q for q, v in ed.view[0].builder.prospects['players'].items() if v[0] == 'Ola Testberg')
    assert ed.view[0].builder.prospects['players'][pid][1:] == (year, 1, 59)
    # another tier: the potential goes to the new band's top, then a potential inside the band
    pr.set('tier', 2)
    idle(ed)
    assert ed.edits[key]['prospect'] == {'tier': 2}
    pr.set('potential', 54)
    idle(ed)
    assert ed.edits[key]['prospect'] == {'tier': 2, 'potential': 54}
    pr.set('potential', 99)                     # kept inside the band
    idle(ed)
    assert ed.edits[key]['prospect'] == {'tier': 2, 'potential': 56}
    # one made in an earlier visit and not in this roster: listed as waiting, joins the roster when picked
    values, problem = C.read({'first': 'Per', 'last': 'Laterson', 'num': '78', 'pos': 'D', 'shoots': 'R',
                              'birth': f"{year - 18}-07-01", 'country': 'SWE', 'team': min(L.WHL), 'ovr': '48'},
                             model.SKATER_ATTRIBUTES, True, ed.choices())
    assert problem is None
    later, entry = C.new_player(values, None)
    ed.edits[later] = dict(entry, prospect={'tier': 4})
    assert {r['key']: r['state'] for r in pr.snapshot()['rows']}[later] == 'waiting'
    pr.pick(later)
    idle(ed)
    assert ed.snapshot()['card']['title'] == 'Per Laterson'
    assert {r['key']: r['state'] for r in pr.snapshot()['rows']}[later] == 'unsaved'
    # the class after, and back
    pr.step(1)
    assert pr.snapshot()['view'] == year + 1
    pr.step(-1)
    # My pro: one only, on an NHL team; taking him out undoes him (made in this visit)
    pr.show(PRO)
    pr.add()
    card = ed.snapshot()['card']
    assert card['title'] == "My pro" and card['values']['team'] in L.NHL_PRIMARY
    assert ed.apply(dict(card['values'], first='Theo', last='Protest', num='88')) == 'applied'
    idle(ed)
    s = pr.snapshot()
    assert [r['name'] for r in s['rows']] == ['Theo Protest'] and not s['can_add']
    # not saved yet: no "where to find him" until the roster's file has him; the other starts are explained
    assert s['rows'][0]['state'] == 'unsaved' and s['unsaved'] and 'Be a NHL Pro, ' not in s['note']
    assert 'Load Pro lists the careers you saved' in s['note']
    pro = s['rows'][0]['key']
    assert ed.edits[pro]['pro'] is True and not ed.view[0].problems
    # Be a Pro picks only NHL roster players and CHL juniors: the card offers those, Apply refuses another team
    from legacy_roster.app.editor import PRO_TEAM
    card = ed.snapshot()['card']
    assert card['teams'] and all(t in L.NHL_PRIMARY or t in L.CHL for t, _ in card['teams'])
    assert ed.apply(dict(card['values'], team=model.FREE_AGENTS)) == 'error' and ed.status[0] == PRO_TEAM
    assert ed.apply(dict(card['values'], team=min(L.SHL))) == 'error'
    pr.add()
    assert 'pro already' in ed.status[0]
    pr.remove(pro)
    idle(ed)
    assert pro not in ed.edits and pr.snapshot()['rows'] == [] and pr.snapshot()['can_add']


def test_my_pro_is_not_saved_until_the_roster_has_him_also_after_a_restart(app):
    from legacy_roster.app.editor import UNSAVED_TITLE, EditorController
    from legacy_roster.app.prospects import PRO, ProspectsController
    host, upd, ed, _uni, _sd = app
    ed.opened()
    idle(ed)
    pr = ProspectsController(host, ed)
    pr.show(PRO)
    pr.add()
    card = ed.snapshot()['card']
    assert ed.apply(dict(card['values'], first='Theo', last='Protest', num='88')) == 'applied'
    idle(ed)
    # the window is closed and opened again before Save: the new visit counts him as not saved yet
    ed2 = EditorController(host, upd)
    ed2.opened()
    idle(ed2)
    pr2 = ProspectsController(host, ed2)
    pr2.show(PRO)
    s = pr2.snapshot()
    assert [r['state'] for r in s['rows']] == ['unsaved'] and s['unsaved']
    assert ed2.snapshot()['unsaved'] == 1 and not ed2.view[0].problems
    # closing the window asks first; Cancel keeps it open
    assert ed2.closing() is False and upd.dialog['title'] == UNSAVED_TITLE
    assert [b['answer'] for b in upd.dialog['buttons']] == ['save', 'close', 'cancel']
    upd.answer(upd.dialog['id'], 'cancel')
    assert upd.dialog is None and not ed2.close_anyway
    # Save: the roster's file has him, the tab says where Be a Pro lists him, and the window closes without a question
    upd.set_save_mode('update')
    sys_data = upd.selected_slot().sys_data
    stamp = os.stat(sys_data).st_mtime_ns
    ed2.save()
    wait(lambda: os.stat(sys_data).st_mtime_ns != stamp and not ed2.busy
         and ed2.status[0] != "Saving...")
    ed2.opened()
    idle(ed2)
    s = pr2.snapshot()
    assert [r['state'] for r in s['rows']] == ['in'] and not s['unsaved']
    assert "Be a NHL Pro, " in s['note'] and '70-79' in s['note']
    assert ed2.snapshot()['unsaved'] == 0 and ed2.closing() is True
    wait(lambda: not upd.scanning)


def test_the_draft_and_pro_tab_makes_a_random_class_and_shares_it_as_a_file(app, tmp_path):
    from legacy_roster import draftclass
    from legacy_roster.app.prospects import ProspectsController
    host, _upd, ed, _uni, _sd = app
    ed.opened()
    idle(ed)
    pr = ProspectsController(host, ed)
    year = pr.snapshot()['view']
    real = {draftclass.plain(p.name) for p in ed.snap.by_who.values()}
    # the maker's window: count, strength, number; the tier split follows them
    looks = ed.looks_left()
    pr.make_open()
    m = pr.snapshot()['maker']
    json.dumps(m)
    assert m['year'] == year and m['count'] == 32 and sum(t['count'] for t in m['split']) == 32
    pr.make_set('count', 16)
    pr.make_set('strength', 'strong')
    pr.make_set('seed', 4242)
    pr.make_set('strength', 'legendary')                # not a choice: left as it was
    m = pr.snapshot()['maker']
    assert (m['count'], m['strength'], m['seed']) == (16, 'strong', 4242)
    pr.make()
    idle(ed)
    s = pr.snapshot()
    assert s['maker'] is None and len(s['rows']) == 16 and 'Made 16 players' in ed.status[0]
    assert all(r['state'] == 'unsaved' for r in s['rows']) and s['unsaved'] and not ed.view[0].problems
    assert not {draftclass.plain(r['name']) for r in s['rows']} & real
    made = {r['name'] for r in s['rows']}
    assert all(draftclass.is_draft_club(t) for r in s['rows'] for t in pr._clubs(r['key'], ed.edits[r['key']]))
    assert len(ed.view[0].builder.prospects['players']) == 16
    # each made player has a created look: the game's Create Player records, so no spare record is needed
    from legacy_roster import faces
    assert all(faces.look_wrong(ed.edits[r['key']].get('look') or {'hair': 1}) is None for r in s['rows'])
    goalies = sum(1 for r in s['rows'] if ed.edits[r['key']]['set']['pos'] == 'G')
    assert ed.looks_left() == {'S': looks['S'] - 16 + goalies, 'G': looks['G'] - goalies}
    full = {'skaters': 1, 'goalies': 0, 'spare': {'S': 0, 'G': 0}, 'looks': {'S': 1, 'G': 0}}     # every league's update
    pr._room = lambda: full
    assert pr._no_room([{'pos': 'C', 'look': faces.DEFAULT_LOOK}]) is None
    assert 'too few for 2 skaters' in pr._no_room([{'pos': 'C', 'look': faces.DEFAULT_LOOK}, {'pos': 'D'}])
    del pr._room
    # export, then import into the next draft: births move a year, the names are skipped where they exist
    host.pick = str(tmp_path / 'class')
    pr.export_class()
    text = (tmp_path / 'class.json').read_text(encoding='utf-8')
    name, file_year, players = draftclass.read_class(text)
    assert file_year == year and len(players) == 16 and {f"{p['card']['first']} {p['card']['last']}" for p in players} == made
    assert all(p['club'] and p['club']['league'] for p in players)
    pr.step(1)
    pr.import_text(text, 'class.json')
    r = pr.snapshot()['report']
    assert r['lines'][0]['text'].startswith('0 players added') and r['lines'][1]['text'].startswith('Skipped')
    assert r['lines'][-1]['text'] == '... and 4 more skipped.'
    pr.close()
    for p in players:                                   # other people, the same class
        p['card']['first'] += 'son'
    players[0]['club'] = {'league': 'OHL', 'name': 'A club nobody has'}
    pr.import_text(draftclass.class_file("Shared", year, players), 'shared.json')
    idle(ed)
    s = pr.snapshot()
    lines = [line['text'] for line in s['report']['lines']]
    assert lines[0].startswith(f"16 players added to the {year + 1} draft") and 'moved 1 year later' in lines[1]
    assert 'on another club' in lines[2]
    assert len(s['rows']) == 16 and s['view'] == year + 1 and not ed.view[0].problems
    assert len(ed.view[0].builder.prospects['players']) == 32
    # a file that is no class file
    pr.import_text('{"hello": 1}', 'other.json')
    assert pr.snapshot()['report']['lines'][0]['tone'] == 'bad'
    pr.close()
    assert pr.snapshot()['report'] is None


def test_jerseys_and_ice_keep_only_what_differs(app):
    _host, _upd, ed, uni, _sd = app
    ed.opened()
    idle(ed)
    ed.pick_team(0)
    ed.uniforms_open()
    wait(lambda: uni.snapshot() and uni.snapshot()['loaded'])
    s = uni.snapshot()
    json.dumps(s)
    assert s['rows'] and s['ice']['mode'] == 'game'
    assert uni._collect() == ({}, {})
    uni.set_colour('primary', '#ff0000')
    uni.pick(s['rows'][0]['variant'], 'colours')
    uni.set_arena('Test Arena')
    uniforms, ice = uni._collect()
    assert uniforms['colours'] == {'primary': '#ff0000'} and ice == {'arena': 'Test Arena'}
    assert uniforms['versions'] == {str(s['rows'][0]['variant']): 'colours'}
    uni.apply()
    assert uni.snapshot() is None and ed.teams['0']['ice'] == {'arena': 'Test Arena'}
    ed.uniforms_open()
    wait(lambda: uni.snapshot() and uni.snapshot()['loaded'])
    assert uni.snapshot()['colours']['primary']['hex'] == '#ff0000'
    uni.undo()
    assert '0' not in ed.teams


def test_jerseys_and_ice_offer_this_seasons_where_the_look_pack_has_them(app, tmp_path, monkeypatch, make_look_pack):
    _host, _upd, ed, uni, _sd = app
    made = make_look_pack(tmp_path, {27: ('nhl', 'TOR', 1, {'dark': (0, 40, 120), 'light': (240, 240, 240)}, (0, 40, 120))})
    monkeypatch.setenv('LEGACY_ROSTER_PACKS', os.path.dirname(made.path))
    ed.opened()
    idle(ed)
    ed.pick_team(27)
    ed.uniforms_open()
    wait(lambda: uni.snapshot() and uni.snapshot()['loaded'])
    s = uni.snapshot()
    json.dumps(s)
    rows = {r['variant']: r for r in s['rows']}
    assert rows[4]['mode'] == rows[3]['mode'] == 'pack' and rows[4]['options'][0] == ['pack', "This season's"]
    assert rows[5]['mode'] == 'game' and rows[5]['options'][0][0] == 'game'          # no third kit in this pack
    assert s['ice']['mode'] == 'pack' and uni._collect() == ({}, {})                 # the pack's is what the update does
    uni.pick(5, 'pack')                                                              # not offered: nothing changes
    uni.pick(4, 'game')
    uni.pick_ice('game')
    assert uni._collect() == ({'versions': {'4': 'game'}}, {'use': 'game'})
    uni.undo()


def test_jerseys_and_ice_offer_this_seasons_alternate_where_the_look_pack_has_a_third(app, tmp_path, monkeypatch, make_look_pack):
    _host, _upd, ed, uni, _sd = app
    made = make_look_pack(tmp_path, {27: ('nhl', 'TOR', 1, {'dark': (0, 40, 120), 'light': (240, 240, 240), 'third': (20, 20, 20)},
                                          (0, 40, 120))})
    monkeypatch.setenv('LEGACY_ROSTER_PACKS', os.path.dirname(made.path))
    ed.opened()
    idle(ed)
    ed.pick_team(27)
    ed.uniforms_open()
    wait(lambda: uni.snapshot() and uni.snapshot()['loaded'])
    rows = {r['variant']: r for r in uni.snapshot()['rows']}
    assert rows[5]['mode'] == 'pack' and rows[5]['options'][0] == ['pack', "This season's"]       # Toronto's Alternate (v5)
    assert rows[5]['label'].startswith('Alternate') and uni._collect() == ({}, {})
    uni.pick(5, 'game')
    assert uni._collect() == ({'versions': {'5': 'game'}}, {})
    uni.undo()


def test_jerseys_and_ice_open_for_every_league_with_home_and_away_only(app, tmp_path, monkeypatch, make_look_pack):
    from PIL import Image
    from legacy_roster.art import looks
    host, _upd, ed, uni, _sd = app
    made = make_look_pack(tmp_path, {135: ('national', 'CAN', 0, {'dark': (200, 10, 10), 'light': (240, 240, 240)},
                                           (200, 10, 10))})
    monkeypatch.setenv('LEGACY_ROSTER_PACKS', os.path.dirname(made.path))
    ed.opened()
    idle(ed)
    wait(lambda: ed.snap is not None)
    snap = ed.snap
    R = snap.R

    def pick(slot):
        ed.set_league(snap.team_league[slot])
        ed.pick_team(slot)
        assert ed.team == slot
    # a team that wears another team's jerseys opens that team's window; a custom team has its own form (0.31.0)
    assert ed._uniforms_why(snap, 218) is None and ed._uniforms_why(snap, 234) is None
    assert looks.window_team(R, 218) == (23, None)
    # an AHL club: its home and away only, by its art id
    pick(36)
    assert ed.snapshot()['team_tools']['uniforms'] and ed.snapshot()['team_tools']['uniforms_why'] == ''
    ed.uniforms_open()
    wait(lambda: uni.snapshot() and uni.snapshot()['loaded'])
    s = uni.snapshot()
    json.dumps(s)
    assert s['art'] == 162 and [r['variant'] for r in s['rows']] == [3, 4] and not s['ice']['locked']
    uni.close()
    # Canada (the classic cut): no "From the colours", this season's template, the international ice locked to the game's own
    pick(135)
    ed.uniforms_open()
    wait(lambda: uni.snapshot() and uni.snapshot()['loaded'])
    s = uni.snapshot()
    assert s['art'] == R.T.get(135, 'artid') and len(s['rows']) == 2
    row = s['rows'][0]
    assert 'colours' not in [o[0] for o in row['options']] and row['mode'] == 'pack'
    assert row['templates'] == ['pack', 'game']
    # the international ice is every national team's: the game's own or a picture for all of them (0.31.0)
    assert not s['ice']['locked'] and s['ice']['options'] == [['game', "The game's own"], ['file', "My picture..."]]
    assert 'every national team' in s['ice']['group']
    uni.pick_ice('colours')                                                   # refused: a shared ice takes a picture
    assert uni._collect() == ({}, {})
    host.pick = str(tmp_path / 'canada.png')
    uni.template(row['variant'], 'pack')
    wait(lambda: os.path.exists(host.pick))
    wait(lambda: 'Saved' in (uni.snapshot()['note'] or ''))
    assert Image.open(host.pick).size == (1024, 1024)
    assert Image.open(host.pick).getpixel((512, 512)) == looks._full_size(made.picture(uni.kits[row['variant']].member)).getpixel((512, 512))
    uni.close()


def test_a_custom_teams_look_and_a_shared_ice_are_kept_for_the_whole_group(app, tmp_path):
    from PIL import Image
    from legacy_roster import custom_kit as K
    from legacy_roster.art import looks
    host, _upd, ed, uni, _sd = app
    ed.opened()
    idle(ed)
    wait(lambda: ed.snap is not None)
    snap = ed.snap

    def pick(slot):
        ed.set_league(snap.team_league[slot])
        ed.pick_team(slot)
        assert ed.team == slot
        ed.uniforms_open()
        wait(lambda: uni.snapshot() and uni.snapshot()['loaded'])
        return uni.snapshot()
    # Coachella Valley: the create-a-team form, its own crest, designs, team colours, a piece by itself
    s = pick(234)
    json.dumps(s)
    assert s['kind'] == 'custom' and s['crest']['value'] == 'own' and s['crest']['own']
    assert '72' in s['crest']['logos'] and '80' not in s['crest']['logos']        # Henderson's crest is not offered
    assert [d['part'] for d in s['designs']] == ['home', 'away', 'pants', 'socks', 'font']
    uni.kit('design', 'home', 4)
    uni.kit('design', 'pants', 9)                                                  # refused: the game has 0-5
    uni.kit('colour', 0, '#102030')
    uni.kit('paint')
    uni.kit('side', 2)
    uni.kit('zone', 9, 1, '#abcdef')
    uni.kit('zone', 11, 1, '#000000')                                              # refused: the crest's own colours
    s = uni.snapshot()
    jersey = next(p for p in s['pieces'] if p['piece'] == 9)
    assert s['side'] == 2 and jersey['touched'] and jersey['zones'][0]['hex'] == '#abcdef'
    assert next(p for p in s['pieces'] if p['piece'] == K.CREST)['locked']
    uni.apply()
    kit = ed.teams['234']['kit']
    assert kit['jersey'][0] == 4 and 'pants' not in kit and kit['colours'][0] == '#102030'
    assert kit['pieces'] == {'9/2': ['#abcdef'] + kit['pieces']['9/2'][1:]} and 'crest' not in kit
    # opened again: what was kept stays, a game logo can be picked, a crest picture brings its own colours
    s = pick(234)
    assert s['designs'][0]['value'] == 4
    uni.kit('logo', 5)
    assert uni.snapshot()['crest']['value'] == '5'
    host.pick = str(tmp_path / 'crest.png')
    Image.new('RGBA', (64, 64), (200, 20, 20, 255)).save(host.pick)
    uni.kit_picture()
    s = uni.snapshot()
    assert s['crest']['value'] == 'mine' and uni.team_kit.kit['pieces']['11/1'][0] == '#c81414'
    uni.undo()                                      # the window is open: everything kept for the team goes
    assert 'kit' not in (ed.teams.get('234') or {})
    # team colours typed without "Paint everything" are kept too (a tester's colours went back at every Save), and a
    # piece set by itself stays set
    s = pick(234)
    uni.kit('side', 1)
    uni.kit('zone', 9, 2, '#00ff00')
    uni.apply()
    s = pick(234)
    assert not s['dirty']
    uni.kit('colour', 1, '#d51836')
    s = uni.snapshot()
    assert s['dirty'] and s['team'][1]['hex'] == '#d51836'
    stripe = next(p for p in s['pieces'] if p['piece'] == 9)['zones']
    assert stripe[1]['hex'] == '#00ff00'                                    # set by itself: not repainted
    uni.kit('colour', 2, 'not a colour')                                    # cannot be read: the kept one stays
    uni.apply()
    kit = ed.teams['234']['kit']
    assert kit['colours'][1] == '#d51836' and kit['pieces']['9/1'][1] == '#00ff00'
    s = pick(234)
    assert s['team'][1]['text'] == '#d51836'
    uni.undo()
    # the national teams share one ice: a picture set at Canada is shown at Finland, and saved there it moves
    s = pick(135)
    host.pick = str(tmp_path / 'ice.png')
    Image.new('RGBA', (1024, 1024), (0, 0, 0, 0)).save(host.pick)
    uni.pick_ice('file')
    uni.apply()
    assert ed.teams['135']['ice']['use'].startswith('file:')
    s = pick(138)
    assert s['ice']['mode'] == 'file' and s['ice']['group']
    uni.apply()
    assert ed.teams['138']['ice']['use'].startswith('file:') and 'ice' not in (ed.teams.get('135') or {})
    pick(135)
    uni.undo()                                      # at another team of the group: the game's own for all of them
    assert not any((ed.teams.get(str(t)) or {}).get('ice') for t in looks.ice_group(snap.R, 138)[1])


def test_equipment_choices_go_to_the_player_and_the_team_and_can_be_taken_back(app):
    from legacy_roster.app.equipment import EquipmentController
    host, _upd, ed, _uni, _sd = app
    eq = EquipmentController(host, ed)
    ed.opened()
    idle(ed)
    ed.pick_team(0)
    row = next(r for r in ed.snapshot()['rows'] if r['pos'] == 'D')
    ed.pick_player(row['id'])
    assert ed.snapshot()['card']['equipment']
    eq.open()
    wait(lambda: eq.snapshot() and eq.snapshot()['loaded'])
    s = eq.snapshot()
    json.dumps(s)
    assert [r['choice'] for r in s['rows']][:2] == ['stick', 'tape'] and not s['can_player'] and not s['can_team']
    now = {r['choice']: r['value'] for r in s['rows']}
    eq.pick('tape', 1 - now['tape'])
    eq.pick('stick', 105)
    assert eq.snapshot()['can_player'] and eq.snapshot()['can_team']
    eq.apply_player()
    idle(ed)
    key = ed.edit_key(eq._player())
    assert ed.edits[key]['equipment'] == {'tape': 1 - now['tape'], 'stick': 105}
    wait(lambda: eq._player().equipment['stick'] == 105)    # the roster is read again with the edit in it
    eq.pick('sock_tuck', 3)
    eq.pick('stick', 86)
    eq.apply_team()
    idle(ed)
    wait(lambda: eq._player().equipment['sock_tuck'] == 3)
    assert ed.teams['0']['equipment'] == {'sock_tuck': 3}   # the stick is not a team choice
    assert eq.snapshot()['undo']
    eq.undo()
    idle(ed)
    assert not ed.edits and 'equipment' not in (ed.teams.get('0') or {}) and eq.snapshot() is None


def test_the_lines_window_moves_only_the_picked_place_checks_the_rules_and_keeps_the_lines(app):
    from legacy_roster.app.lines import LinesController
    host, _upd, ed, _uni, _sd = app
    ln = LinesController(host, ed)
    ed.opened()
    idle(ed)
    ed.pick_team(0)
    ln.open()
    s = ln.snapshot()
    json.dumps(s)
    assert s['problems'] == [] and [t['id'] for t in s['tabs']][0] == 'even' and not s['mine']
    l1, l2 = ln.slots['l1lw'], ln.slots['l2lw']
    ln.pick_slot('l1lw')
    ln.place(l2)                                    # he plays in the lines already: nobody else moves, he is there twice
    assert (ln.slots['l1lw'], ln.slots['l2lw']) == (l2, l2)
    assert any('is twice in lines' in p for p in ln.snapshot()['problems'])
    ln.pick_slot('l2lw')
    ln.place(l1)                                    # the player gives the other place to the one who left: fixed
    assert (ln.slots['l1lw'], ln.slots['l2lw']) == (l2, l1) and ln.snapshot()['problems'] == []
    ln.pick_slot('pp2c')                            # a special-team group may use one player twice
    ln.place(ln.slots['pp1c'])
    assert ln.slots['pp2c'] == ln.slots['pp1c'] and ln.snapshot()['problems'] == []
    dressed = {ln.slots[x] for x in ln.slots if x[0] in 'lg' and not x.startswith('pk')}
    scratch = next((w for w, p in ln.players.items() if w not in dressed and p['pos'] != 'G'), None)
    if scratch is not None:                         # a scratch comes in: only the picked place changes (no cascade)
        out = ln.slots['l1c']
        before = dict(ln.slots)
        ln.pick_slot('l1c')
        ln.place(scratch)
        assert ln.slots['l1c'] == scratch
        assert {s: w for s, w in ln.slots.items() if s != 'l1c'} == {s: w for s, w in before.items() if s != 'l1c'}
        if any(w == out for s, w in ln.slots.items() if s not in ('l1c',) and not s.startswith(('l', 'g'))):
            assert 'special-team places' in ln.snapshot()['carry']
            ln.carry()                              # the player asks: he takes the places of the one he replaced
            assert out not in [w for s, w in ln.slots.items() if not s.startswith(('l', 'g'))]
            assert ln.snapshot()['carry'] is None
    fwd, dman = ln.slots['l2c'], ln.slots['l1ld']   # a defenceman's place picked for a forward: nobody else moves
    before = dict(ln.slots)
    ln.pick_slot('l1ld')
    ln.place(fwd)
    assert ln.slots['l1ld'] == fwd and ln.slots['l2c'] == fwd
    assert {s: w for s, w in ln.slots.items() if s != 'l1ld'} == {s: w for s, w in before.items() if s != 'l1ld'}
    assert any('is twice in lines' in p for p in ln.snapshot()['problems'])
    ln.slots['l1ld'] = dman
    goalie = ln.slots['g1']
    ln.pick_slot('l3lw')
    ln.slots['l3lw'] = goalie                       # what the window would never do: the check names it
    assert any('goalie' in p for p in ln.snapshot()['problems']) and not ln.snapshot()['can_apply']
    ln.pick_slot('l3lw')
    ln.open()                                       # opened again: the roster's lines
    ln.pick_slot('l1lw')
    ln.place(l2)
    ln.pick_slot('l2lw')
    ln.place(l1)
    ln.set_letter(l2, 'C')
    assert ln.letters[l2] == 'C'                    # 0.81.0: another captain does not take the letter off the first
    assert ln.snapshot()['can_apply']
    ln.apply()
    idle(ed)
    assert ed.teams['0']['lines']['slots']['l1lw'] == l2 and ed.teams['0']['lines']['letters'][l2] == 'C'
    assert ed.view[0].ok, ed.view[0].problems[:3]
    ln.undo()
    idle(ed)
    assert 'lines' not in (ed.teams.get('0') or {}) and ln.snapshot() is None


def test_the_strategies_window_keeps_only_what_changed(app):
    from legacy_roster import strategy
    from legacy_roster.app.strategy import StrategyController
    host, _upd, ed, _uni, _sd = app
    st = StrategyController(host, ed)
    ed.opened()
    idle(ed)
    ed.pick_team(0)
    st.open()
    s = st.snapshot()
    json.dumps(s)
    assert [x['title'] for x in s['sections']][:2] == ['Team Strategies', 'Forward Line 1'] and not s['can_apply']
    team = s['sections'][0]['rows']                 # the game's own menu order, then what the menu does not show
    assert [r['label'] for r in team][:9] == ['Forecheck', 'Neutral Zone', 'Neutral zone or forecheck', 'Off Pressure',
                                              'Defensive Pressure', 'Defensive Strategy', 'Penalty Kill', 'Powerplay',
                                              'PP Carry or PP Dump']
    assert [r['hidden'] for r in team] == [False] * 9 + [True] * 5
    was = st.values['oz_forecheck']
    st.set('oz_forecheck', (was + 1) % 4)
    st.set('forward2_bias4', 99)                    # past the slider's end: not taken
    st.set('forward2_bias4', 9)
    assert st.snapshot()['can_apply']
    st.apply()
    idle(ed)
    assert ed.teams['0']['strategy'] == {'oz_forecheck': (was + 1) % 4, 'forward2_bias4': 9}
    wait(lambda: strategy.read(ed.snap.R, 0)['forward2_bias4'] == 9)
    st.undo()
    idle(ed)
    assert 'strategy' not in (ed.teams.get('0') or {})


def test_a_goalies_equipment_window_has_the_mask_and_keeps_his_own_mask_picture(app, tmp_path):
    from legacy_roster.app.equipment import EquipmentController
    host, _upd, ed, _uni, _sd = app
    eq = EquipmentController(host, ed)
    ed.opened()
    idle(ed)
    ed.pick_team(0)
    idle(ed)                    # the last test's save may still be reading the roster again
    row = next(r for r in ed.snapshot()['rows'] if r['pos'] == 'G')
    ed.pick_player(row['id'])
    assert ed.snapshot()['card']['equipment']
    eq.open()
    wait(lambda: eq.snapshot() is not None)
    s = eq.snapshot()
    json.dumps(s)
    assert s['goalie'] and [r['choice'] for r in s['rows']][:2] == ['mask', 'pads'] and not s['can_player']
    picture = tmp_path / 'mask.png'
    picture.write_bytes(b'x')
    ed.pick_picture = lambda title: 'file:' + str(picture)
    eq.choose_mask_picture()
    assert eq.snapshot()['can_player'] and eq.snapshot()['mask_picture'] == str(picture)
    eq.pick('pads', 7)
    eq.apply_player()
    idle(ed)
    key = ed.edit_key(eq._player())
    assert ed.edits[key]['mask_picture'] == 'file:' + str(picture) and ed.edits[key]['equipment'] == {'pads': 7}
    eq.undo()
    idle(ed)
    assert not ed.edits


def test_a_move_that_leaves_a_team_without_two_goalies_goes_through_with_a_heads_up(app):
    """Free editing (2026-10-29): the move is the player's choice; the status line warns that the game hangs a game
    played with that team."""
    _host, _upd, ed, _uni, _sd = app
    ed.opened()
    wait(lambda: ed.snap is not None)
    idle(ed)
    team = next(t for t in ed.snap.teams_in('NHL') if sum(1 for q in ed.snap.roster(t) if q.pos == 'G') == 2)
    goalie = next(q for q in ed.snap.roster(team) if q.pos == 'G')
    other = next(t for t in ed.snap.teams_in('NHL') if t != team)
    ed.pick_team(team)
    idle(ed)
    row = next(r for r in ed.snapshot()['rows'] if r['who'] == goalie.who)
    ed.pick_player(row['id'])
    card = ed.snapshot()['card']
    assert ed.apply(dict(card['values'], team=str(other))) == 'applied'
    idle(ed)
    status = ed.snapshot()['status']
    assert status['text'].startswith("Heads up: ") and '1 goalie' in status['text'] and status['tone'] == 'warn', status
    assert ed.snapshot()['edits_count'] == 1


def test_a_window_that_has_started_the_new_version_closes_even_though_it_was_busy(app, monkeypatch):
    from legacy_roster.app import selfupdate
    host, upd, ed, _uni, _sd = app
    quit_called = []
    host.quit = lambda: quit_called.append(upd.closing())
    monkeypatch.setattr(selfupdate, 'install', lambda release, progress: None)
    release = selfupdate.Release((9, 9, 9), 'v9.9.9', '', 'page', 'url', 1, 'abc')
    upd.install_update(release)
    wait(lambda: quit_called)
    assert quit_called == [True] and ed.closing() and not upd.busy and upd.dialog is None


def test_a_newer_version_is_offered_once_the_question_on_screen_is_answered(app, monkeypatch):
    """The start's look at GitHub found a question showing: the offer waits for it (0.50.2 dropped it)."""
    import threading
    from legacy_roster.app import selfupdate
    host, upd, _ed, _uni, _sd = app
    release = selfupdate.Release((9, 9, 9), 'v9.9.9', 'New things', 'page', 'url', 1, 'abc')
    monkeypatch.setattr(selfupdate, 'latest', lambda: release)
    upd.ask("Something else", ["first"], [("OK", 'ok', 'primary')], {})
    first = upd.dialog['id']
    looking = threading.Thread(target=upd._look_for_update, args=(False, 0.01), daemon=True)
    looking.start()
    looking.join(0.2)
    assert looking.is_alive() and upd.dialog['title'] == "Something else"
    upd.answer(first, 'ok')
    wait(lambda: upd.dialog)
    looking.join(5)
    assert upd.dialog['title'] == "Version 9.9.9 is out" and not looking.is_alive()


def test_the_equipment_window_offers_the_games_own_words_for_tucks_and_tape():
    from legacy_roster import equipment as E
    assert [w for _, w in E.OPTIONS['jersey_tuck']] == ["None", "Left", "Right", "Full"]
    assert [w for _, w in E.OPTIONS['sock_tuck']] == ["Full", "None", "Front", "Back"]       # lab round 51: 0 is the tucked one
    assert [w for _, w in E.OPTIONS['visor']] == ["Straight visor", "Curved visor", "No visor"]
    assert [w for _, w in E.OPTIONS['visor_tint']][:3] == ["Clear", "Grey", "Yellow"] and len(E.OPTIONS['visor_tint']) == 8
    assert E.OPTIONS['shoulder_pads'][1] == (1, "Big") and E.GOALIE_OPTIONS['neck'] == [(0, "Off"), (1, "On")]
    assert E.menu_path('visor', 0) .endswith('visor2.big') and E.menu_path('visor', 2).endswith('visor1.big')
    assert len(E.OPTIONS['tape']) == 10 and E.OPTIONS['tape'][:2] == [(0, "Black"), (1, "White")]
    from legacy_roster.app.equipment import ORDER
    assert all(c in E.CHOICES for c in ORDER) and {'visor_tint', 'shoulder_pads', 'pant_length'} <= set(ORDER)


def test_step_2_patches_the_game_asks_first_sets_its_switches_and_unpatches(app, monkeypatch):
    from legacy_roster import patchinstall
    from legacy_roster.app import settings as S
    _host, upd, _ed, _uni, _sd = app
    card = lambda: upd.snapshot()['patch']
    assert all(r['key'] != 'game_patch' for r in upd.snapshot()['steps'])      # no longer a step of the update
    assert card()['state']['text'].startswith("Not patched") and not card()['patched']
    assert [c['key'] for c in card()['checks']] == [S.SKIP_INTRO, S.NO_LOGIN]
    assert [c['on'] for c in card()['checks']] == [True, False]
    assert [c['label'] for c in card()['checks']] == ["Skip the intro", "No pop ups at start"]

    installed, switched, removed = [], [], []
    state = {'BLES02153': {'patched': False, 'version': None, 'intro': False, 'login': False}}
    def install(rpcs3, titles, roster=None, intro=True, login=False, say=print, pack=None):
        installed.append((list(titles), intro, login))
        for t in titles:
            state[t] = {'patched': True, 'version': patchinstall.gamepatch.TEAMS_VERSION, 'intro': intro, 'login': login}
        return list(titles)
    monkeypatch.setattr(patchinstall, 'install_patch', install)
    monkeypatch.setattr(patchinstall, 'state', lambda rpcs3: {t: dict(v) for t, v in state.items()})
    monkeypatch.setattr(patchinstall, 'set_switches', lambda rpcs3, titles, intro, login:
                        switched.append((list(titles), intro, login)) or list(titles))
    monkeypatch.setattr(patchinstall, 'remove', lambda rpcs3, say=print: removed.append(rpcs3) or 2)
    upd.versions = ['BLES02153']
    assert [(b['label'], b['kind']) for b in card()['buttons']] == [("Patch the game", 'gold')]

    upd.set_patch_switch(S.NO_LOGIN, True)                  # not patched: only remembered for the next Patch
    assert upd.no_login and switched == []
    upd.patch()                                             # the first time: a question
    assert installed == [] and upd.dialog['title'] == "32 teams and the year 2026"
    upd.answer(upd.dialog['id'], 'yes')
    wait(lambda: not upd.busy and upd.status and upd.status[0].startswith("Done: the EU game is patched"))
    assert upd.result is None                               # no panel: step 2 says it, the rosters keep their room
    wait(lambda: not upd.scanning)
    assert installed == [(['BLES02153'], True, True)]
    assert card()['patched'] and card()['state']['text'].startswith("Patched: EU (intro skipped, no pop-ups at start)")
    assert [b['label'] for b in card()['buttons']] == ["Unpatch"]
    upd.set_patch_switch(S.SKIP_INTRO, False)               # patched: into RPCS3 at once
    assert switched == [(['BLES02153'], False, True)] and not upd.skip_intro
    upd.patch()                                             # asked once only
    wait(lambda: len(installed) == 2 and not upd.busy)

    state['BLES02153']['version'] = '0.17'                  # an older patch: Patch again
    upd.set_rpcs3(upd.rpcs3.where, quiet=True)
    wait(lambda: not upd.scanning)
    upd.versions = ['BLES02153']
    assert [(b['label'], b['kind']) for b in card()['buttons']] == [("Patch again", 'gold'), ("Unpatch", 'gold-line')]
    assert card()['state']['tone'] == 'amber'
    upd.unpatch()
    upd.answer(upd.dialog['id'], 'yes')
    wait(lambda: not upd.busy and upd.status and upd.status[0].startswith("Done: the game patch is out"))
    assert upd.result is None
    assert len(removed) == 1


def test_after_patch_a_roster_that_no_longer_fits_is_marked_and_offered_an_update_in_place(app, monkeypatch):
    """The owner, 2026-10-21: a roster updated before patching showed "damaged" in the patched game. The roster list
    marks it, and Patch / Unpatch ask to update the roster picked (in place, whatever the save mode)."""
    from legacy_roster import patchinstall, pipeline
    from legacy_roster.app import settings as S, texts as X
    host, upd, _ed, _uni, _sd = app
    slot = upd.selected_slot()
    row = lambda: next(r for r in upd.snapshot()['rosters'] if r['folder'] == slot.folder)
    assert row()['misfit'] is None                          # not patched, a normal roster: fits
    state = {slot.title_id: {'patched': False, 'version': None, 'intro': False, 'login': False}}
    def install(rpcs3, titles, roster=None, intro=True, login=False, say=print, pack=None):
        for t in titles:
            state[t] = {'patched': True, 'version': patchinstall.gamepatch.TEAMS_VERSION, 'intro': intro, 'login': login}
        return list(titles)
    monkeypatch.setattr(patchinstall, 'install_patch', install)
    monkeypatch.setattr(patchinstall, 'state', lambda rpcs3: {t: dict(v) for t, v in state.items()})
    sent, updates = [], []
    monkeypatch.setattr(host, 'send', lambda event, payload=None: sent.append((event, payload)))
    monkeypatch.setattr(pipeline, 'update', lambda *a, **k: updates.append((a, k)) or (_ for _ in ()).throw(OSError("stop")))
    upd.settings[S.PATCH_ASKED] = True
    upd.save_mode = S.AS_NEW                                # the question updates in place all the same
    upd.versions = [slot.title_id]
    upd.patch()
    wait(lambda: not upd.busy and not upd.scanning and upd.dialog is not None)
    assert row()['misfit'] == X.MISFIT_PATCHED
    upd.versions = [slot.title_id]                          # the made-up RPCS3 lists no game: the Game patch tab
    assert [x['misfit'] for x in upd.snapshot()['patch']['regions'][0]['rosters'] if x['name'] == slot.name] == [True]
    assert upd.dialog['title'] == f"Update \"{slot.name}\" now?"
    assert [b['label'] for b in upd.dialog['buttons']] == ["Update it now", "Later"]
    upd.answer(upd.dialog['id'], 'yes')
    wait(lambda: updates and not upd.busy)
    args, kwargs = updates[0]
    assert args[1] == slot.folder and args[3] is None       # this roster, its own name
    assert kwargs['in_place'] and kwargs['targets'] == [slot.title_id]
    assert ('focus_tab', {'tab': 'update'}) in sent
    assert upd._fit is None and upd.save_mode == S.AS_NEW   # once only; the player's save mode is kept

    upd.answer(upd.dialog['id'], 'no') if upd.dialog else None
    upd.patch_rosters = {slot.folder}                       # a 32-team roster in a game without the patch
    state[slot.title_id]['patched'] = False
    upd.patch_state = {t: dict(v) for t, v in state.items()}
    assert row()['misfit'] == X.MISFIT_UNPATCHED
    # a roster made for patch 0.22 (five-bit rights) in a game with 0.23's db files (six): "damaged" too
    upd.patch_state[slot.title_id].update(patched=True, rights=6)
    upd.roster_rights = {slot.folder: 5}
    assert row()['misfit'] == X.MISFIT_VERSION
    assert "another version of the game patch" in X.fit_ask(slot.name, X.MISFIT_VERSION)[0]
    upd.roster_rights = {slot.folder: 6}
    assert row()['misfit'] is None
    # a tester's NA game, 2026-10-23: patched by 0.50.0 (1.00 only), then update 1.01 installed: every roster, Patch again
    upd.patch_state[slot.title_id].update(patched=False, stale=True, game='01.01')
    assert row()['misfit'] == X.MISFIT_STALE
    upd.patch_rosters = set()
    assert row()['misfit'] == X.MISFIT_STALE
    card = upd.snapshot()['patch']
    assert [b['label'] for b in card['buttons']] == ["Patch again", "Unpatch"] and card['state']['tone'] == 'amber'
    assert card['regions'][0]['state'].startswith("The game has update 1.01")


def test_step_2_says_what_is_missing_without_rpcs3_and_while_it_runs(app, monkeypatch):
    from legacy_roster.app import texts as X
    _host, upd, _ed, _uni, _sd = app
    upd.versions = ['BLES02153']
    upd.running = True                  # seen at the last scan: the buttons stay on, a press checks and says it
    card = upd.snapshot()['patch']
    assert card['note'] is None and card['buttons'] and all(b['enabled'] for b in card['buttons'])
    assert 'running' not in upd.snapshot()['rpcs3']
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe')
    upd.patch()
    assert upd.result['title'] == "Close RPCS3 first"
    upd.hide_result()
    upd.set_export_only(True)
    card = upd.snapshot()['patch']
    assert card['state']['text'] == X.EXPORT_PATCH_OFF and card['buttons'] == []   # export mode: a tick box, no buttons
    # the "?" says what the patch does, also before RPCS3 is picked
    assert card['info']['title'] == X.PATCH_INFO_TITLE
    assert [s['head'] for s in card['info']['sections']] == [head for head, _ in X.PATCH_INFO]


def test_a_roster_made_for_the_game_patch_is_saved_from_the_editor_through_the_update(app, pack, tmp_path,
                                                                                       monkeypatch):
    from legacy_roster import gamepatch, patchinstall, pipeline, schedule
    from legacy_roster.builder import Data
    from legacy_roster.roster import Roster
    disc = os.environ.get('LEGACY_ROSTER_DISC')
    if not disc:
        pytest.skip("needs the game disc (LEGACY_ROSTER_DISC): the patch's db files are made from it")
    _host, upd, ed, _uni, _sd = app
    (tmp_path / 'rpcs3' / 'config').mkdir(exist_ok=True)
    (tmp_path / 'rpcs3' / 'config' / 'games.yml').write_text(f"BLES02153: {disc}\n")
    slot = upd.selected_slot()
    raw = open(slot.sys_data, 'rb').read()
    built = pipeline.build(raw, Data(season_year=pack['season'], schedule=pack['schedule'], calendar=schedule.ALL_PATCH,
                                     leagues={'ahl': pack['leagues']['ahl']}), [pipeline.SCHEDULE, 'ahl'])
    data, problems, _ = pipeline.patch_roster(built, raw, pack, pack['season'])
    assert not problems
    with open(slot.sys_data, 'wb') as f:
        f.write(data)
    patchinstall.install_patch(upd.rpcs3, [slot.title_id], roster=data, say=lambda m: None)
    upd.set_rpcs3(upd.rpcs3.where, quiet=True)
    wait(lambda: not upd.scanning)
    assert upd.patch_rosters == {slot.folder} and upd.roster_rights[slot.folder] == 6
    assert next(r for r in upd.snapshot()['rosters'] if r['folder'] == slot.folder)['tag'] == "32 teams"
    ed.opened()
    idle(ed)
    s = ed.snapshot()
    assert s['loaded'], ed.status
    assert not any(r['tag'] for r in s['rows']), [(r['name'], r['tag']) for r in s['rows'] if r['tag']][:5]   # the same years
    row = s['rows'][0]
    ed.pick_player(row['id'])
    said = []                                       # the save's 'good' word is soon replaced by the re-read's
    set_status = ed.set_status
    monkeypatch.setattr(ed, 'set_status', lambda text, kind='info': (said.append((text, kind)), set_status(text, kind)))
    ed.save(dict(ed.snapshot()['card']['values'], first='Patched'))
    wait(lambda: any(kind != 'info' for _t, kind in said), seconds=600)
    wait(lambda: not ed.busy and ed.after_busy is None)
    assert next(kind for _t, kind in said if kind != 'info') == 'good', said
    R = Roster(open(slot.sys_data, 'rb').read())
    assert gamepatch.is_patch_roster(R)                         # still for the patched game
    assert any(R.name(i) == f"Patched {row['name'].split(' ', 1)[1]}" for i in range(R.P.cur_rec))


def test_the_window_opens_big_and_centred_in_the_free_part_of_the_screen():
    from legacy_roster.window import main
    assert main.fit((0, 0, 1707, 912)) == (1536, 857, 85, 27)          # 2560 x 1440 at 150 %, taskbar below
    w, h, x, y = main.fit((0, 0, 1366, 728))                            # a 768-line laptop: the whole height
    assert (w, h) == (1229, 728) and x == (1366 - 1229) // 2 and y == 0
    assert main.fit((0, 0, 3840, 2100))[:2] == main.LARGEST            # never huge
    assert main.fit((0, 0, 1024, 600)) == (1024, 640, 0, 0)            # smaller than the smallest window: from the top left
    assert main.fit((1920, 40, 1920, 1040))[2:] == (1920 + 96, 40 + 31)   # a screen that does not start at 0, 0


# --- the RPCS3 remembered: never a temp folder in the exe, tests never reach the real settings (2026-10-22) -------------
def test_tests_keep_the_programs_own_folder_in_a_temp_folder():
    import tempfile
    from legacy_roster import datasource
    temp = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
    assert os.path.normcase(os.path.abspath(datasource.app_dir())).startswith(temp + os.sep)


def test_the_exe_neither_uses_nor_remembers_an_rpcs3_in_the_temp_folder(app, tmp_path, monkeypatch):
    import sys
    import tempfile
    from legacy_roster.app import settings as S
    from legacy_roster.app import update as U
    _host, upd, _ed, _uni, _sd = app
    exe = str(tmp_path / 'rpcs3' / 'rpcs3.exe')
    assert not U.temporary(exe)                         # from source (tests, window_shot): fine
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(tempfile, 'gettempdir', lambda: str(tmp_path))
    assert U.temporary(exe) and not U.temporary(r'D:\PS3\RPCS3\rpcs3.exe') and not U.temporary(None)
    saved = []
    monkeypatch.setattr(S, 'save', lambda values: saved.append(dict(values)))
    tried = []
    monkeypatch.setattr(upd, 'set_rpcs3', lambda path, quiet=False: tried.append(path))
    running = tmp_path / 'running' / 'rpcs3.exe'
    running.parent.mkdir()
    running.write_bytes(b'')                            # start_up only follows a running RPCS3 whose file is on this PC
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: str(running))
    upd.settings['rpcs3'] = exe
    upd.start_up()
    assert tried == [str(running)]         # the temp one is passed over: the running RPCS3 instead
    del upd.set_rpcs3                                   # (not monkeypatch.undo: the fixture's folders would go too)
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    upd.settings.pop('rpcs3', None)
    upd.set_rpcs3(exe)
    wait(lambda: not upd.scanning)
    assert upd.rpcs3 and upd.slots and 'rpcs3' not in upd.settings and not any('rpcs3' in s for s in saved)


# --- "Photos, logos and team names": first, highlighted, its pictures downloaded automatically (packs.py) --------------
def test_the_photos_row_is_first_highlighted_and_off_until_the_player_ticks_it(base_dir, tmp_path, monkeypatch, pack):
    from legacy_roster.app import texts as X
    from legacy_roster.app.update import UpdateController
    upd = UpdateController(FakeHost(), settings={}, pack=pack)          # nothing remembered: a first start
    row = upd._steps_view(False, False)[0]
    assert row['key'] == 'pictures' and row['featured'] and not row['on'] and row['bar'] is None
    assert row['sub'] == X.PHOTOS_OFF
    assert [c['key'] for c in row['children']] == ['photos', 'looks', 'arenas', 'team_masks']     # 0.80.0: no ice row
    names = upd._steps_view(False, False)[1]                            # team names: a row of their own, on to start with
    assert names['key'] == 'names' and names['on'] and not names.get('featured') and 'children' not in names
    assert not any(r.get('featured') for r in upd._steps_view(False, False)[1:])
    upd.set_step('pictures', True)                                      # the group switch: every part inside goes on
    row = upd._steps_view(False, False)[0]
    assert row['on'] and all(c['on'] for c in row['children'])
    assert row['sub'].startswith("Downloaded automatically (about")
    assert upd._steps_view(False, False)[1]['on']                       # and the names are not part of it
    upd.set_step('looks', False)                                        # one part off again: the group says how many
    row = upd._steps_view(False, False)[0]
    assert row['on'] and row['sub'].startswith("3 of 4 parts on. ") and not upd.art_on['bright_ice']
    upd.set_step('looks', True)                                         # this season's and the new centre ice go together
    assert upd.art_on['looks'] and upd.art_on['bright_ice'] and {'looks', 'ice'} <= set(upd.packs_wanted())
    upd.set_step('pictures', False)                                     # off: all parts off, the names stay
    assert not any(c['on'] for c in upd._steps_view(False, False)[0]['children']) and upd.art_on['names']
    upd.set_step('pictures', True)
    assert upd._steps_view(True, False)[0]['sub'] == X.PHOTOS_EXPORT and not upd._steps_view(True, False)[0]['on']


def test_restore_on_the_group_row_marks_every_part_in_it_and_again_undoes_it(base_dir, tmp_path, monkeypatch, pack):
    from legacy_roster.app.update import UpdateController
    upd = UpdateController(FakeHost(), settings={}, pack=pack)
    monkeypatch.setattr(upd, 'download_pictures', lambda: None)
    upd.set_step('pictures', True)
    upd.toggle_restore('pictures')
    assert set(upd.marks) == {'photos', 'looks', 'arenas', 'bright_ice', 'team_masks'} and not upd.parts_on() - {'names'}
    assert upd._steps_view(False, False)[0]['restoring']
    upd.toggle_restore('pictures')
    assert not upd.marks
    upd.toggle_restore('names')                                         # names keep their own Restore
    assert set(upd.marks) == {'names'}
    upd.set_step('looks', True)
    upd.toggle_restore('looks')                                         # this season's: the new centre ice with it
    assert set(upd.marks) == {'names', 'looks', 'bright_ice'} and not upd.art_on['bright_ice']
    upd.toggle_restore('looks')
    assert set(upd.marks) == {'names'}


def test_the_new_centre_ice_follows_this_seasons_switch_also_from_an_older_settings_file(pack):
    from legacy_roster.app.update import UpdateController
    upd = UpdateController(FakeHost(), settings={'steps': {'looks': True, 'bright_ice': False}}, pack=pack)
    assert upd.art_on['bright_ice'] and {'looks', 'bright_ice'} <= upd.parts_on()
    upd = UpdateController(FakeHost(), settings={'steps': {'looks': False, 'bright_ice': True}}, pack=pack)
    assert not upd.parts_on() & {'looks', 'bright_ice'}


def test_a_settings_file_of_a_test_version_with_the_scoreboard_on_loads_without_it(pack):
    from legacy_roster.app.update import UpdateController
    saved = {'steps': {'looks': True, 'overlay': True}, 'overlay_logo': 'puckpeak', 'overlay_logo_file': None}
    upd = UpdateController(FakeHost(), settings=saved, pack=pack)       # 0.78.0 / 0.80.0 test versions had a scoreboard row
    rows = upd._steps_view(False, False)
    keys = {r['key'] for r in rows} | {k['key'] for r in rows for k in r.get('children') or ()}
    assert 'overlay' not in keys and 'overlay' not in upd.parts_on() and 'overlay' not in upd.packs_wanted()
    upd.set_step('pictures', True)
    assert 'overlay' not in saved['steps']


def test_photos_start_off_for_a_player_who_had_them_on_and_a_new_choice_is_kept(base_dir, tmp_path, monkeypatch, pack):
    from legacy_roster.app.update import UpdateController
    saved = {'steps': {'photos': True}}                                 # 0.60 and older saved the old default
    upd = UpdateController(FakeHost(), settings=saved, pack=pack)
    assert not upd.photos and saved['steps']['photos'] is False and saved['photos_default']
    upd.set_step('photos', True)                                        # ticked on purpose after the change: kept
    again = UpdateController(FakeHost(), settings=saved, pack=pack)
    assert again.photos


def test_the_photos_row_never_says_where_its_pictures_come_from_or_what_they_are():
    from legacy_roster.app import texts as X
    said = [X.photos_will(), X.photos_will(157_000_000), X.PHOTOS_RUNNING, X.PHOTOS_READY, X.PHOTOS_RETRY, X.PHOTOS_OFF,
            X.PHOTOS_WAITING, X.PHOTOS_SHORT, X.PHOTOS_EXPORT, X.PHOTOS_NEEDS_RPCS3, X.LOOKS_MISSING,
            X.PICTURE_NOT_SERVED, X.pictures_short(sorted(X.PACK_TITLES))]
    for text in said:
        low = text.lower()
        assert not any(word in low for word in ('server', 'http', 'puckpeak', '.com', 'pack', 'zip', 'internet'))
    assert all("automatically" in t for t in said[:5])


def _site(tmp_path, monkeypatch, payload):
    """packs.py's server, played by a local web server with one pack ({name: bytes})."""
    import functools
    import hashlib
    import http.server
    import threading
    root = tmp_path / 'site'
    root.mkdir()
    listed = {}
    for name, data in payload.items():
        digest = hashlib.sha256(data).hexdigest()
        (root / f"{name}.zip").write_bytes(data)
        listed[name] = {'file': f"{name}.zip", 'size': len(data), 'sha256': digest, 'built': '2026-10-20'}
    (root / 'manifest.json').write_text(json.dumps({'format': 1, 'packs': listed}), encoding='utf-8')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv('LEGACY_ROSTER_FILES_URL', f"http://127.0.0.1:{server.server_address[1]}/")
    return server


def test_the_pictures_download_by_themselves_only_while_the_switch_is_on(tmp_path, monkeypatch, pack):
    from legacy_roster import packs
    from legacy_roster.app import texts as X
    from legacy_roster.app.update import UpdateController
    server = _site(tmp_path, monkeypatch, {'photos': b'P' * 2_000_000, 'looks': b'L' * 1000, 'arenas': b'A' * 1000})
    (tmp_path / 'packs').mkdir()
    monkeypatch.setattr(packs, 'folder', lambda: str(tmp_path / 'packs'))
    try:
        upd = UpdateController(FakeHost(), settings={'steps': {'photos': False, 'names': False}}, pack=pack)
        upd.download_pictures()                                         # off: nothing happens
        assert not upd._fetching and set(packs.status().values()) == {None}
        seen = []
        upd.host.changed = lambda name: seen.append(upd._steps_view(False, False)[0]['children'][0]['sub'])      # the photos part
        upd.set_step('looks', True)                                     # jerseys alone: only their pack comes
        wait(lambda: not upd._fetching, 30)
        with upd.lock:
            pass
        assert packs.have('looks') and not packs.have('photos') and not packs.have('arenas')
        assert upd._steps_view(False, False)[0]['children'][1]['sub'] == X.PICTURE_NOT_SERVED    # the ice is not listed
        upd.set_step('photos', True)                                    # on: the download starts by itself
        wait(lambda: not upd._fetching, 30)
        with upd.lock:                  # the thread clears _fetching first, then sets fetch and tells the page
            pass
        assert upd.fetch == 'ready' and packs.have('photos') and packs.have('looks') and not packs.have('arenas')
        assert any(s.startswith("Downloading automatically...") for s in seen) and seen[-1] == X.PHOTOS_READY
    finally:
        server.shutdown()
        server.server_close()


def test_an_update_pressed_during_the_download_waits_for_it(app, monkeypatch):
    from legacy_roster.app import texts as X
    _host, upd, _ed, _uni, _sd = app
    started = []
    monkeypatch.setattr(upd, 'download_pictures', lambda: None)       # the download is "running" in this test
    upd.photos, upd._fetching, upd.fetch, upd.fetch_at = True, True, 'running', 0.3
    upd.start()
    assert upd.busy and upd.waiting is False and upd.status[0] == X.PHOTOS_WAITING.format(pct=30)
    assert upd.snapshot()['save']['button']['text'] == "Updating..."
    monkeypatch.setattr(upd, 'start', lambda everything=False, waited=False: started.append((everything, waited)))
    monkeypatch.setattr('legacy_roster.packs.prune', lambda: None)
    monkeypatch.setattr('legacy_roster.packs.manifest', lambda timeout=20: None)       # the line dropped
    upd._download()
    assert started == [(False, True)] and not upd.busy and upd.fetch == 'failed'
    assert upd._steps_view(False, False)[0]['sub'].endswith(X.PHOTOS_RETRY)


def test_the_jerseys_window_says_this_seasons_come_with_the_photos(app):
    from legacy_roster.app import texts as X
    _host, _upd, ed, uni, _sd = app
    ed.opened()
    idle(ed)
    ed.pick_team(27)
    ed.uniforms_open()
    wait(lambda: uni.snapshot() and uni.snapshot()['loaded'])
    assert uni.snapshot()['pack_note'] == X.LOOKS_MISSING
    uni.close()


def test_the_editors_save_puts_the_players_own_photo_into_the_game(app, tmp_path, monkeypatch):
    """Testers of 0.10.4: a photo picked in the Roster editor never showed in the game (only an update with photos
    and logos on put it in). Save now puts it in, RPCS3 closed; a picture without a face is refused when picked."""
    pytest.importorskip('PIL')
    from PIL import Image
    from legacy_roster.app import editor as E
    from legacy_roster.art import install
    from legacy_roster.roster import Roster
    from .test_art import SizedDisc, head_photo
    host, upd, ed, _uni, sd = app
    rpcs3 = tmp_path / 'rpcs3'
    (rpcs3 / 'config').mkdir(exist_ok=True)
    (rpcs3 / 'config' / 'games.yml').write_text(f"BLES02153: {(tmp_path / 'disc.iso').as_posix()}\n")
    (tmp_path / 'disc.iso').write_bytes(b'not read: SizedDisc stands in')
    monkeypatch.setattr(install, 'Disc', SizedDisc)
    monkeypatch.setattr(install.PhotoPack, 'open', classmethod(lambda cls, *a, **k: None))
    upd.set_save_mode('new')
    ed.opened()
    idle(ed)
    ed.pick_player(ed.snapshot()['rows'][0]['id'])
    name = ed.snapshot()['card']['title']

    Image.new('RGBA', (200, 200), (0, 0, 0, 0)).save(tmp_path / 'blank.png')       # a cut-out with nobody in it
    host.pick = str(tmp_path / 'blank.png')
    ed.choose_photo()
    assert ed.status == (E.NO_FACE, 'bad') and not ed.pending_photo
    head_photo().save(tmp_path / 'terry.png')
    host.pick = str(tmp_path / 'terry.png')
    ed.choose_photo()
    assert ed.status == (E.PHOTO_PICKED, 'warn') and ed.pending_photo

    before = set(s.folder for s in savedata.list_rosters(sd))
    ed.save(ed.snapshot()['card']['values'])
    wait(lambda: len(savedata.list_rosters(sd)) == len(before) + 1 and not ed.busy and ed.status[0] != "Saving...")
    assert "Your own pictures are in the game now." in ed.status[0], ed.status
    new = next(s for s in savedata.list_rosters(sd) if s.folder not in before)
    R = Roster(savedata.read_roster(new))
    prow = next(i for i in range(R.P.cur_rec) if R.name(i) == name and R.teams_of(i))
    aid = R.P.get(prow, 'artid')
    assert R.P.get(prow, 'hasportrait') == 1
    heads = rpcs3 / 'dev_hdd0' / 'game' / 'BLES02153' / 'USRDIR' / 'fe' / 'ion' / 'artassets' / 'playerheads'
    assert (heads / install.portrait_folder(aid) / f"p{aid}.big").exists()

    # RPCS3 running: the roster is saved, the pictures wait for a save with it closed
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe')
    wait(lambda: not ed.busy and not upd.scanning and ed.source is not None)    # the new roster is open (_open_saved)
    assert ed.slot.folder == new.folder
    before = set(s.folder for s in savedata.list_rosters(sd))
    ed.save()
    wait(lambda: len(savedata.list_rosters(sd)) == len(before) + 1 and not ed.busy and ed.status[0] != "Saving...")
    assert ed.status[1] == 'warn' and "when you save with RPCS3 closed" in ed.status[0]
    wait(lambda: not upd.scanning)      # the save's rescan (it once outlived the test and wrote the real settings)


# --- the nine tabs: the team list on the left and the tabs that follow it ---------------------------------------------
def _tabs(app):
    from legacy_roster.app.lines import LinesController
    from legacy_roster.app.office import OfficeController
    from legacy_roster.app.strategy import StrategyController
    from legacy_roster.window.api import Api
    host, upd, ed, uni, _sd = app
    ln, st = LinesController(host, ed), StrategyController(host, ed)
    office = OfficeController(host, ed)
    api = Api(host, upd, editor=ed, uniforms=uni, lines=ln, strategy=st, office=office)
    api.tab('roster')
    idle(ed)
    return host, ed, uni, ln, st, office, api


def test_every_tab_of_the_page_is_taken_and_the_team_tabs_read_the_roster(app):
    _host, ed, _uni, _ln, _st, _office, api = _tabs(app)
    for tab in ('setup', 'update', 'patch', 'roster', 'lines', 'strategy', 'jerseys', 'calendar', 'office', 'editor'):
        assert api.tab(tab) is None                 # no error for the page
    assert ed.tab == 'roster'                       # the old name of the Roster tab
    rail = ed.rail_view()
    json.dumps(rail)
    assert rail['loaded'] and rail['league'] == 'NHL' and any(r['sel'] for r in rail['rows'])
    assert all(r['code'] and r['number']['text'].isdigit() for r in rail['rows'])


def test_a_team_picked_on_the_left_moves_the_tab_in_view_and_keeps_the_pick_across_tabs(app):
    from legacy_roster import layout as L
    _host, ed, _uni, ln, st, _office, api = _tabs(app)
    edm, cgy = L.API_TO_SLOT['EDM'], L.API_TO_SLOT['CGY']
    api.rail_team(edm)
    api.tab('lines')
    assert ln.snapshot()['team'] == edm
    api.rail_team(cgy)
    assert ln.snapshot()['team'] == cgy and st.shown != cgy     # the hidden Strategy tab rests
    api.tab('strategy')
    assert st.snapshot()['team'] == cgy and ed.team == cgy
    api.rail_step(1)                                # Alt+Down: the next team of the list
    teams = ed.snap.teams_in(ed.league)
    assert ed.team == teams[teams.index(cgy) + 1] and st.snapshot()['team'] == ed.team


def test_lines_changed_but_not_applied_stay_with_their_team(app):
    from legacy_roster import layout as L
    _host, ed, _uni, ln, _st, _office, api = _tabs(app)
    edm, cgy = L.API_TO_SLOT['EDM'], L.API_TO_SLOT['CGY']
    api.rail_team(edm)
    api.tab('lines')
    l1, l2 = ln.slots['l1lw'], ln.slots['l2lw']
    ln.pick_slot('l1lw')
    ln.place(l2)
    assert ln.snapshot()['touched']
    api.rail_team(cgy)
    assert not ln.snapshot()['touched'] and edm in ln.drafts()
    assert next(r for r in ed.rail_view()['rows'] if r['id'] == edm)['dirty']
    api.tab('roster')
    api.rail_team(edm)
    api.tab('lines')                                # back: the change is still there, not applied
    s = ln.snapshot()
    assert s['touched'] and (ln.slots['l1lw'], ln.slots['l2lw']) == (l2, l2) and l1 != l2
    assert 'lines' not in (ed.teams.get(str(edm)) or {})


def test_the_jerseys_tab_reads_a_team_only_while_it_shows(app, monkeypatch):
    from legacy_roster import layout as L
    _host, ed, uni, _ln, _st, _office, api = _tabs(app)
    opened = []
    real = uni.open
    monkeypatch.setattr(uni, 'open', lambda *a, **k: (opened.append(a[0]), real(*a, **k))[1])
    api.rail_team(L.API_TO_SLOT['EDM'])
    time.sleep(uni.DELAY * 2)
    assert opened == [] and uni.snapshot() is None  # never shown: nothing read
    api.tab('jerseys')
    api.rail_team(L.API_TO_SLOT['CGY'])             # clicking along the list: only the team it stops at is read
    wait(lambda: (uni.snapshot() or {}).get('loaded'))
    assert opened == [L.API_TO_SLOT['CGY']]
    api.tab('roster')
    api.rail_team(L.API_TO_SLOT['TOR'])
    time.sleep(uni.DELAY * 2)
    assert opened == [L.API_TO_SLOT['CGY']]


def test_the_contract_button_on_the_card_opens_the_contract_of_his_club(app):
    from legacy_roster import layout as L
    _host, ed, _uni, _ln, _st, office, api = _tabs(app)
    api.rail_team(L.API_TO_SLOT['EDM'])
    row = next(r for r in ed.snapshot()['rows'] if r['pos'] != 'G')
    ed.pick_player(row['id'])
    card = ed.snapshot()['card']
    assert card['contract']['shown'] and not card['contract']['edited']
    api.contract_open(card['who'])                  # from the Roster tab: the hidden office follows his club first
    c = office.contract_snapshot()
    json.dumps(c)
    assert c['name'] == row['name'] and office.team == L.API_TO_SLOT['EDM']
    api.contract_close()
    assert office.contract_snapshot() is None
    junior = min(L.OHL)                             # owner, 2026-10-22: any club's player has a contract to change
    api.rail_team(junior)
    row = ed.snapshot()['rows'][0]
    ed.pick_player(row['id'])
    card = ed.snapshot()['card']
    assert card['contract']['shown']
    api.contract_open(card['who'])
    c = office.contract_snapshot()
    assert c['name'] == row['name'] and office.team == junior


def test_a_missing_folder_error_names_the_folder_and_is_logged(tmp_path, monkeypatch):
    import threading
    from legacy_roster.app import jobs
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    monkeypatch.setenv('HOME', str(tmp_path))
    told = []

    def work():
        open(str(tmp_path / 'nowhere' / 'file.txt'))
    jobs.run(work, failed=told.append, expected=(FileNotFoundError,)).join(10)
    assert told and 'nowhere' in told[0]
    logs = list((tmp_path / 'local').rglob('error.log'))
    assert logs and 'FileNotFoundError' in logs[0].read_text(encoding='utf-8')

def test_every_failure_leaves_a_block_with_what_the_program_was_doing(tmp_path, monkeypatch):
    from legacy_roster import __version__
    from legacy_roster.app import jobs
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'local'))
    monkeypatch.setenv('HOME', str(tmp_path))

    def work():
        raise ValueError("a broken roster")
    told = []
    jobs.run(work, failed=told.append, expected=(ValueError,), context=lambda: ["roster: Mine", "rpcs3: G:/RPCS3"]).join(10)
    assert told == ["a broken roster"]
    text = next((tmp_path / 'local').rglob('error.log')).read_text(encoding='utf-8')
    assert f"version {__version__}" in text and "roster: Mine" in text and "rpcs3: G:/RPCS3" in text
    assert "ValueError: a broken roster" in text


def test_a_failure_after_the_save_keeps_the_roster_saved_and_says_so(app, data, monkeypatch, tmp_path):
    """A tester (0.51.0): "[WinError 3] The system cannot find the path specified" after "Saved as ..." and the window
    said "Nothing was saved". What fails after the save is told in red under the saved roster's title, and logged."""
    from legacy_roster import pipeline
    from legacy_roster.app import texts as X
    host, upd, _ed, _uni, sd = app
    real = pipeline.write_report

    def broken(result, title, *args, **kw):
        if title.startswith(('failed', 'dryrun')):
            return real(result, title, *args, **kw)
        raise FileNotFoundError(3, "The system cannot find the path specified", 'X:/gone/reports')
    monkeypatch.setattr(pipeline, 'write_report', broken)
    slot = upd.slots[0]
    result = pipeline.update(sd, slot.folder, [], "After the save", data=data)
    assert result.slot is not None and os.path.isdir(result.slot.path)             # saved
    assert result.after and 'X:/gone/reports' in result.after[0][1]
    upd._context = lambda: ["roster: the test's"]
    upd._done(result, False)
    r = upd.result
    assert r['good'] and r['title'].startswith("Saved as") and "Nothing was saved" not in r['title']
    assert any('X:/gone/reports' in line for line in r['bad'])
    assert any(line.startswith(X.SAVED_DESPITE.split('{')[0]) for line in r['bad'])
    text = next((tmp_path / 'local').rglob('error.log')).read_text(encoding='utf-8')
    assert "roster: the test's" in text and 'FileNotFoundError' in text
