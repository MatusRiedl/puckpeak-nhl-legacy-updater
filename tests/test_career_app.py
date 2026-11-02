"""The Draft & Pro tab's Be a Pro careers (app/career.py) on made-up careers in a temp folder: listed, opened, changed,
asked about and saved (with a backup), refused while RPCS3 runs, and the window's close question."""
import os
import types

import pytest

from legacy_roster import careersave as K
from legacy_roster import savedata
from legacy_roster.app import career as CA
from legacy_roster.app.prospects import ProspectsController
from tests.test_app import FakeHost, wait
from tests.test_careersave import career_bytes
from tests.test_seasonsave import write_save


class FakeUpdate:
    def __init__(self):
        self.running, self.quitting, self.dialog, self.answers = False, False, None, {}

    def ask(self, title, lines, buttons, answers):
        self.dialog = {'title': title, 'lines': list(lines), 'buttons': [b[1] for b in buttons]}
        self.answers = answers

    def answer(self, answer):
        todo = self.answers.get(answer)
        self.dialog, self.answers = None, {}
        if todo:
            todo()


@pytest.fixture
def careers(tmp_path, monkeypatch):
    saves = tmp_path / 'savedata'
    saves.mkdir()
    write_save(str(saves), 'BLES021530500', career_bytes(), 'LPRO11', chunk=1024, when=1_700_000_000)
    write_save(str(saves), 'BLUS315400501', career_bytes(), 'LPRO12', chunk=1024, when=1_700_000_500)  # other version
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    monkeypatch.setattr(CA.datasource, 'app_dir', lambda *parts: str(tmp_path.joinpath('app', *parts)))
    editor = types.SimpleNamespace(update=FakeUpdate(), source=(str(saves), 'BLES021530200'), snap=None, season=2026,
                                   slot=types.SimpleNamespace(title_id='BLES02153'))
    host = FakeHost()
    host.quit = lambda: setattr(host, 'quitted', True)
    return CA.CareerController(host, editor), str(saves), tmp_path


def _opened(car):
    car.look()
    car.open(car.saves[0].folder)
    wait(lambda: not car.busy, 30)
    assert car.career is not None, car.note
    return car


def test_lists_the_picked_versions_careers_and_shows_the_pro(careers):
    car, saves, _ = careers
    assert car.snapshot()['rows'] == [] and car.snapshot()['why'] is None      # not looked yet
    car.look()
    s = car.snapshot()
    assert [r['folder'] for r in s['rows']] == ['BLES021530500'] and s['rows'][0]['name'] == 'LPRO11'
    _opened(car)
    pro = car.snapshot()['pro']
    assert (pro['first'], pro['last'], pro['jersey']) == ('Theo', 'Lpro1', 88)
    assert [x['value'] for x in pro['pools']] == [699, 678, 623]
    assert len(pro['ratings']) == len(K.RATINGS) and all(r['label'] for r in pro['ratings'])
    assert 'overall' not in pro                     # the game works it out again when the career loads
    assert not car.snapshot()['dirty']


def test_no_rpcs3_and_no_career_say_what_to_do(careers):
    car, saves, _ = careers
    car.editor.source, car.editor.update.rpcs3 = None, None
    car.look(fresh=True)
    assert car.snapshot()['why'] == CA.NO_RPCS3
    car.editor.source, car.editor.slot.title_id = (saves, 'x'), 'BLJS00000'
    car.look(fresh=True)
    assert car.snapshot()['why'] == CA.NO_CAREER


def test_typed_values_are_checked_and_undo_drops_them(careers):
    car, _, _ = _opened_careers(careers)
    car.set('offense', '1200')
    car.set('defense', 'abc')                       # not a number: nothing
    car.set('athletic', 10 ** 9)                    # clamped
    car.set('first', '  Theo  ')                    # the same name: nothing to save
    car.set('last', 'Žák')                          # a letter the game lacks
    assert car.note['tone'] == 'warn'
    car.set('last', 'x' * 30)
    car.set('passing', '39')                        # below the game's range
    assert car.note['tone'] == 'warn'
    car.set('passing', '95')
    car.set('speed', str(car.career.pro.ratings['speed']))         # as it is: nothing to save
    assert car.draft == {'offense': 1200, 'athletic': K.MAX_XP, 'passing': 95}
    rated = {r['key']: r for r in car.snapshot()['pro']['ratings']}
    assert rated['passing']['value'] == 95 and rated['passing']['was'] != 95
    car.draft.pop('passing')
    pro = car.snapshot()['pro']
    assert pro['changed'] == ['athletic', 'offense'] and pro['pools'][0]['was'] == 699
    car.undo()
    assert car.draft == {} and not car.snapshot()['dirty']


def _opened_careers(careers):
    car, saves, tmp = careers
    return _opened(car), saves, tmp


def test_save_asks_first_then_backs_up_and_writes_only_the_edit(careers):
    car, saves, tmp = _opened_careers(careers)
    folder = os.path.join(saves, 'BLES021530500')
    before = b''.join(open(p, 'rb').read() for p in K.data_files(folder))
    car.set('offense', 900)
    car.set('last', 'Brannick')
    car.set('passing', 95)
    car.save()
    upd = car.editor.update
    assert upd.dialog['title'] == CA.ASK_TITLE and 'save' in upd.dialog['buttons']
    assert b''.join(open(p, 'rb').read() for p in K.data_files(folder)) == before      # nothing before the answer
    upd.answer('save')
    wait(lambda: not car.busy, 30)
    assert car.note == {'text': CA.SAVED, 'tone': 'good'} and car.draft == {}
    after = b''.join(open(p, 'rb').read() for p in K.data_files(folder))
    pro = K.Career(after).pro
    assert (pro.last, pro.xp['offense'], pro.xp['defense'], pro.ratings['passing']) == ('Brannick', 900, 678, 95)
    assert K.Save(folder).name == 'BRANNICK1'       # the game's label "LPRO11" follows the new last name
    backups = os.listdir(tmp / 'app' / 'backups')
    assert len(backups) == 1 and backups[0].startswith('BLES021530500_')
    kept = os.path.join(tmp / 'app' / 'backups', backups[0])
    assert b''.join(open(p, 'rb').read() for p in K.data_files(kept)) == before
    assert car.snapshot()['pro']['last'] == 'Brannick'


def test_cancel_and_a_running_rpcs3_leave_the_career_alone(careers, monkeypatch):
    car, saves, _ = _opened_careers(careers)
    folder = os.path.join(saves, 'BLES021530500')
    before = b''.join(open(p, 'rb').read() for p in K.data_files(folder))
    car.set('offense', 900)
    car.save()
    car.editor.update.answer('cancel')
    car.editor.update.running = True                # seen at the last scan: no question at all
    car.save()
    assert car.editor.update.dialog is None and car.note == {'text': f"Close RPCS3 first: {CA.CLOSED}", 'tone': 'warn'}
    car.editor.update.running = False
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe')        # started since: update_career says so
    car.save()
    car.editor.update.answer('save')
    wait(lambda: not car.busy, 30)
    assert car.note['tone'] == 'bad' and 'Close RPCS3' in car.note['text'] and car.draft == {'offense': 900}
    assert b''.join(open(p, 'rb').read() for p in K.data_files(folder)) == before


def test_closing_with_changes_not_saved_asks_first(careers):
    car, _, _ = _opened_careers(careers)
    assert car.closing()
    car.set('defense', 700)
    assert not car.closing() and car.editor.update.dialog['title'] == CA.NOT_SAVED_TITLE
    car.editor.update.answer('close')
    assert getattr(car.host, 'quitted', False) and car.closing()


def test_draft_and_pro_lists_the_careers_last_and_looks_when_they_show(careers):
    car, _, _ = careers
    pr = ProspectsController(car.host, car.editor, car)
    assert pr._views()[-2:] == ['pro', 'careers']
    pr.shown = True
    pr.show('careers')
    assert pr.view == 'careers' and car.saves is not None and len(car.saves) == 1
    pr.add()                                        # nothing to add in the careers' view
    assert ProspectsController(car.host, car.editor)._views()[-1] == 'pro'        # without careers: as before
