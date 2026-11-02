"""The Draft & Pro tab's Be a Pro careers without a window toolkit: the player's running Be a Pro careers of the picked
roster's game version, the pro's name, ratings and XP to spend changed, and the career saved back (careersave.py).

A career is only ever written when the player presses Save on it and says yes to the question (AGENTS.md rule 1):
`verify.career_problems` first, then `savedata.update_career` (a backup of the whole folder in the program's backups,
the newest 10 kept, never while RPCS3 runs or while the game may still be writing it). Reading a career takes a few
seconds (its league database), so reading and saving run in the background. Listing the careers reads only their
folder names, first bytes and PARAM.SFO.
"""
import datetime
import os
import threading

from .. import careersave, datasource, ratings, savedata, verify
from . import jobs
from .season import where as save_folder

SLICE = 'career'
NO_RPCS3 = "Pick RPCS3 and a roster in Setup first."
NO_CAREER = ("No Be a Pro career found for this version of the game. Start one in the game (Career > Live the Life > "
             "New Pro) and save it, then look again.")
READING = "Reading the career..."
SAVING = "Saving the career..."
ASK_TITLE = "Save this career?"
ASK_LINES = ("The program changes this Be a Pro career in RPCS3's save folder. First it copies the whole career to its "
             "own backups (the newest 10 are kept), and it checks the change. RPCS3 must be closed.",
             "Then load it in the game: Career > Live the Life > Load Pro.")
SAVED = ("Saved. Load it in the game: Career > Live the Life > Load Pro. The career as it was is in the program's "
         "backups.")
CLOSED = "a career can only be saved while the game is closed."
NOT_SAVED_TITLE = "Career not saved"
NOT_SAVED_LINES = ("Your changes to the Be a Pro career are not saved.",
                   "Close anyway (they are lost), or cancel and press Save this career.")
LABELS = {'acceleration': "Acceleration", 'aggression': "Aggressiveness", 'agility': "Agility", 'balance': "Balance",
          'bodychecking': "Body checking", 'defawareness': "Defensive awareness", 'deking': "Deking",
          'discipline': "Discipline", 'durability': "Durability", 'endurance': "Endurance", 'faceoffs': "Faceoffs",
          'fightingskill': "Fighting skill", 'handeye': "Hand-eye", 'offawareness': "Offensive awareness",
          'passing': "Passing", 'poise': "Poise", 'puckcontrol': "Puck control", 'shotblocking': "Shot blocking",
          'slapaccuracy': "Slap shot accuracy", 'slapshotpower': "Slap shot power", 'speed': "Speed",
          'stickchecking': "Stick checking", 'strength': "Strength", 'wristaccuracy': "Wrist shot accuracy",
          'wristshotpower': "Wrist shot power"}
POOL_LABELS = {'offense': "Offense", 'defense': "Defense", 'athletic': "Athletic"}
NAMES = ('first', 'last')


class CareerController:
    def __init__(self, host, editor):
        self.host, self.editor = host, editor
        self.lock = threading.RLock()
        self.saves = None               # careersave.Save list (newest first) of where it last looked, None: not yet
        self.looked = None              # (savedata folder, title ids) it looked in
        self.folder = None              # the career picked (its folder name)
        self.career = None              # its careersave.Career, read in the background
        self.raw = None                 # the bytes it was read from (update_career's `expected`)
        self.draft = {}                 # field -> value typed and not saved: 'first', 'last', the XP pools, ratings
        self.busy = None                # READING / SAVING
        self.note = None                # {'text', 'tone'}: the last result
        self.close_anyway = False

    def changed(self):
        self.host.changed(SLICE)

    # --- the careers ---------------------------------------------------------------------------------------------
    def look(self, fresh=False):
        """List the careers of the picked roster's game version (again with `fresh`, or when that changed)."""
        place = save_folder(self.editor)
        with self.lock:
            if not fresh and self.saves is not None and place == self.looked:
                return
            self.looked = place
            try:
                self.saves = careersave.find(*place) if place else []
            except OSError:
                self.saves = []
            if self.folder and not any(s.folder == self.folder for s in self.saves) and not self.busy:
                self.folder = self.career = self.raw = None
                self.draft = {}
        self.changed()

    def _save_of(self, folder):
        return next((s for s in self.saves or [] if s.folder == folder), None)

    def open(self, folder):
        """Read the career `folder` (in the background); changes not saved of another career are dropped."""
        with self.lock:
            save = self._save_of(folder)
            if save is None or self.busy:
                return
            self.folder, self.career, self.raw, self.draft, self.note = folder, None, None, {}, None
            self.busy = READING
        self.changed()

        def done(career):
            with self.lock:
                if self.folder == folder:
                    self.career, self.raw = career, career.raw
                self.busy = None
            self.changed()
        jobs.run(lambda: careersave.read(save), done, self._failed, expected=(careersave.CareerError, OSError))

    def _failed(self, message):
        with self.lock:
            self.busy = None
            self.note = {'text': message, 'tone': 'bad'}
        self.changed()

    # --- changes -------------------------------------------------------------------------------------------------
    def set(self, field, value):
        """A name ('first', 'last'), the XP to spend of a pool ('offense', 'defense', 'athletic') or a skater's rating
        (careersave.RATINGS), as typed."""
        with self.lock:
            if self.career is None or self.busy:
                return
            pro = self.career.pro
            if field in NAMES:
                text = ' '.join(str(value or '').split())
                try:
                    data = text.encode('latin1')
                except UnicodeEncodeError:
                    self.note = {'text': "A name can use only letters the game has (no č, ť, ž ...).", 'tone': 'warn'}
                    return self.changed()
                if not data or len(data) >= careersave.NAME_SIZE:
                    self.note = {'text': f"A name has 1 to {careersave.NAME_SIZE - 1} letters.", 'tone': 'warn'}
                    return self.changed()
                current = getattr(pro, field)
            elif field in careersave.POOLS:
                try:
                    text = int(value)
                except (TypeError, ValueError):
                    return self.changed()
                text = max(0, min(careersave.MAX_XP, text))
                current = pro.xp[field]
            elif field in pro.ratings:
                try:
                    text = int(value)
                except (TypeError, ValueError):
                    return self.changed()
                current = pro.ratings[field]
                if text != current and not careersave.LOWEST <= text <= careersave.HIGHEST:
                    self.note = {'text': f"Ratings go from {careersave.LOWEST} to {careersave.HIGHEST}.", 'tone': 'warn'}
                    return self.changed()
            else:
                return
            if text == current:
                self.draft.pop(field, None)
            else:
                self.draft[field] = text
            self.note = None
        self.changed()

    def undo(self):
        with self.lock:
            self.draft, self.note = {}, None
        self.changed()

    def _built(self):
        """(the changed career's bytes, the kinds of edit) from the draft."""
        career = careersave.Career(self.raw)
        names = {k: v for k, v in self.draft.items() if k in NAMES}
        pools = {k: v for k, v in self.draft.items() if k in careersave.POOLS}
        rated = {k: v for k, v in self.draft.items() if k in careersave.RATINGS}
        if names:
            career.set_name(**names)
        if pools:
            career.set_xp(pools)
        if rated:
            career.set_ratings(rated)
        return career.build(), [k for k, on in (('name', names), ('xp', pools), ('ratings', rated)) if on]

    def save(self):
        """Ask first (rule 1), then save the career."""
        with self.lock:
            if self.career is None or not self.draft or self.busy:
                return
            if getattr(self.editor.update, 'running', False):
                self.note = {'text': f"{savedata.close_first()}: {CLOSED}", 'tone': 'warn'}
                return self.changed()
        self.editor.update.ask(ASK_TITLE, list(ASK_LINES), [("Save this career", 'save', 'primary'),
                                                             ("Cancel", 'cancel', '')], {'save': self._save_now})

    def _save_now(self):
        with self.lock:
            if self.career is None or not self.draft or self.busy:
                return
            save, raw, sizes = self._save_of(self.folder), self.raw, self.career.pieces
            if save is None:
                return
            label = careersave.renamed_label(save, self.career.pro.last, self.draft.get('last', self.career.pro.last))
            self.busy = SAVING
        self.changed()

        def work():
            new, kinds = self._built()
            problems = verify.career_problems(raw, new, kinds, sizes)
            if problems:
                raise careersave.CareerError("The change did not pass the career check, so nothing was saved: "
                                             + "; ".join(problems[:3]))
            savedata.update_career(os.path.dirname(save.path), save.folder, new, raw, datasource.app_dir('backups'),
                                   label=label)
            career = careersave.Career(new)         # as written (a re-read waits for the files to settle)
            career.pieces = sizes
            return career

        def done(career):
            with self.lock:
                self.career, self.raw, self.draft = career, career.raw, {}
                self.note = {'text': SAVED, 'tone': 'good'}
                self.busy = None
            self.look(fresh=True)
        jobs.run(work, done, self._failed, expected=(careersave.CareerError, savedata.InPlaceError, OSError))

    # --- closing the window --------------------------------------------------------------------------------------
    def closing(self):
        """May the window close now? Not while a career is being saved, and not with changes not saved before the
        player said so."""
        with self.lock:
            if self.editor.update.quitting:
                return True
            if self.busy == SAVING:
                self.editor.update.ask("Please wait", ["A Be a Pro career is being saved. Close the window when it is "
                                                       "done."], [("OK", 'ok', 'primary')], {})
                return False
            if self.close_anyway or not self.draft:
                return True
        self.editor.update.ask(NOT_SAVED_TITLE, list(NOT_SAVED_LINES),
                               [("Close anyway", 'close', ''), ("Cancel", 'cancel', 'primary')],
                               {'close': self._close_now})
        return False

    def _close_now(self):
        with self.lock:
            self.close_anyway = True
        self.host.quit()

    # --- what the page shows -------------------------------------------------------------------------------------
    def _pro_view(self):
        pro = self.career.pro
        value = lambda f: self.draft.get(f, getattr(pro, f) if f in NAMES else pro.xp[f])
        return {                        # no Overall: the game works it out from the ratings when the career loads
            'first': value('first'), 'last': value('last'), 'name': pro.name,
            'type': ratings.style_label(pro.type, pro.goalie), 'jersey': pro.jersey,
            'birthplace': pro.birthplace.title(), 'goalie': pro.goalie,         # (a patched game shifts the year)
            'ratings': [{'key': k, 'label': LABELS[k], 'value': self.draft.get(k, pro.ratings[k]),
                         'was': pro.ratings[k]} for k in careersave.RATINGS if k in pro.ratings],
            'pools': [{'key': k, 'label': POOL_LABELS[k], 'value': value(k), 'was': pro.xp[k]}
                      for k in careersave.POOLS],
            'changed': sorted(self.draft),
        }

    def snapshot(self):
        with self.lock:
            if self.looked is None and self.saves is None:
                rows, why = [], None
            else:
                rows = [{'folder': s.folder, 'name': s.name,
                         'saved': f"{datetime.datetime.fromtimestamp(s.modified):%Y-%m-%d %H:%M}"}
                        for s in self.saves or []]
                why = None if rows else (NO_RPCS3 if self.looked is None else NO_CAREER)
            return {'rows': rows, 'why': why, 'picked': self.folder, 'busy': self.busy,
                    'pro': self._pro_view() if self.career is not None else None,
                    'dirty': bool(self.draft), 'note': self.note, 'max_xp': careersave.MAX_XP,
                    'name_size': careersave.NAME_SIZE - 1, 'lowest': careersave.LOWEST,
                    'highest': careersave.HIGHEST}
