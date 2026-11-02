"""The Roster editor tab without a window toolkit: what the page shows, and what its buttons do.

It shows the roster save picked in Setup as it is (the game's own roster too), plus the edits made
in this visit (`session`). The edits are kept on this PC (edits.py) and applied to every later update as
well, but earlier ones are not shown on top of a roster: they are in it once it was saved. Saving writes
what is shown after the same safety checks as an update, into the roster itself (a backup copy first,
savedata.update_in_place) or as a new roster, as the Update tab's choice says.

The page keeps what is typed on the card and sends it along with Apply, Save and a pick of another player
(`card`: see editor/card.py); a card that was typed on but not applied is applied first, as before. Slow work
(reading, rebuilding, saving, pictures) runs in a worker thread; the slices `editor` and `picture` say what
to show (the picture is a slice of its own, so the card's picture is not sent again with every change).

The six team tabs (Roster, Lines, Strategy, Jerseys & ice, Calendar, Front office) share one team list on the left
(the slice `rail`). This controller owns the picked league and team; the other tabs are "followers" (`follow_with`):
the follower of the tab in view gets follow(team) when the team changes or a roster is read, the others hide(), and all
get roster_changed() after a roster was read again (an edit, a save, another roster). Only the visible tab does work.
"""
import io
import os
import random
import threading

from .. import datasource, edits, faces, gamepatch, pipeline, ratings, savedata
from .. import layout as L
from ..art import looks, parts, portraits
from ..art.install import ArtError
from ..editor import card as C
from ..editor import model
from ..roster import Roster
from . import dataurl, jobs, settings as S

SLICE, PICTURE, RAIL = 'editor', 'picture', 'rail'
TEAM_TABS = ('roster', 'lines', 'strategy', 'jerseys', 'calendar', 'office', 'prospects')
RAIL_TIPS = {'roster': 'players', 'lines': 'players', 'strategy': 'players', 'jerseys': 'players', 'calendar': 'games',
             'office': 'cap space', 'prospects': 'players'}
FREE_AGENTS_VIEW = {'id': model.FREE_AGENTS, 'code': 'FA', 'name': "Free agents", 'colours': ['#3a4a5c', '#8aa0b8'],
                    'league': "Free agents"}
PORTRAIT = (512, 256)
NO_ROSTER = "Pick RPCS3 and a roster in Setup first."
ROSTER_FILE = ("These tabs show the roster file the export starts from. Your edits are kept in My edits and go into the "
               "export (Update tab); the file itself is not changed.")
PHOTO_PICKED = "Press Apply to keep the photo. It goes into the game when you press Save."
NO_FACE = "No face found in this picture: pick a photo with the face near the top."
PRO_TEAM = ("Be a Pro can pick him only on an NHL team (Be a NHL Pro) or a CHL club (Be a CHL Pro): put your pro on "
            "one of those.")
UNSAVED_TITLE = "Not saved yet"
UNSAVED_LINES = ["{n} not in the roster yet. The game reads only what is saved: Save puts {them} into the roster "
                 "(with RPCS3 closed).", "Your edits stay in My edits either way and go into every update."]
LOOK_NOT_HERE = ("A created look is only for a player made in this program: the game keeps it on its own Create Player "
                 "places. Pick a generic head or another player's face with Face of a player... instead.")
COUNTRIES = sorted(L.NAT_CODE)
STYLE_CHOICES = {kind: [[n, ratings.style_choice(n, kind == 'G')] for n in numbers]
                 for kind, numbers in ratings.FREE_STYLES.items()}
FACE_FOUND = 60                 # players listed in the Face of a player window
FACE_PICS = 'face_pics'         # slice: {head (str): data: link}, the game's own pictures of the generic heads
# the game's Create Player menu has a picture of a head under its head id (211 of the 213 generic heads; docs/notes/faces.md)
FACE_MENU = 'fe/ion/artassets/createplayer/head/head{}.big'
LOOK_PICS = 'look_pics'         # slice: {part: {number (str): data: link}}, the Create Player menu's own pictures
# the menu's pictures of a created look's parts: the head shapes are head<k> (custom head 20000 + 50 k), the colours a
# grid of 6 in faces.COLOURS order, the eyes eyecolor<number + 1>; each is 96 x 48 with the swatch on the left
LOOK_MENU = {'hair_colour': 'haircolor/haircolor{}', 'facial_hair_colour': 'facialhaircolor/facialhaircolor{}',
             'eyebrow_colour': 'eyebrowcolor/eyebrowcolor{}', 'eyes': 'eyecolor/eyecolor{}'}
LOOK_ROWS = [{'key': key, 'label': faces.LOOK_WORDS[key], 'choices': [[n, word] for n, word in choices],
              'pictures': key == 'shape' or key in LOOK_MENU}
             for key, (_tag, choices) in faces.LOOK.items()]


class RosterFile:
    """The roster file (SYS-DATA) an export starts from, shown by the team tabs like a roster save; never saved to."""
    file, disc = True, False

    def __init__(self, path):
        self.folder = self.sys_data = path
        self.name = f"Roster file {os.path.basename(os.path.dirname(path)) or path}"
        self.region = 'file'
        self.title_id = savedata.title_of('EU')


def heads_up(built, lead=""):
    """'Heads up: Ottawa has 1 goalie and 20 skaters: the game hangs ...' for a team the player's edits left short
    (verify's info['heads_up']; free editing saves it anyway), or ''."""
    lines = ((getattr(built, 'info', None) or {}).get('heads_up') or []) if built is not None else []
    if not lines:
        return ""
    more = f" (and {len(lines) - 1} more team{'s' if len(lines) > 2 else ''})" if len(lines) > 1 else ""
    return f"{lead}Heads up: {lines[0]}{more}."


class EditorController:
    def __init__(self, host, update):
        self.host, self.update = host, update
        self.lock = threading.RLock()
        update.editor = self
        self.uniforms = None            # the Jerseys and ice controller (app/uniforms.py), once there is one
        self.looks_touched = set()      # slots whose jerseys / ice / kit the Jerseys tab changed since the last Save put
                                        # pictures in: a team set back to the game's own has no edit left to say so
        self.equipment = None           # the Equipment controller (app/equipment.py)
        self.edits = edits.load()
        self.teams = edits.load_teams()
        pack = update.pack or {}
        self.offset = ratings.overall_offset(pack.get('ratings_list') or []) if pack else None
        self.season = pack.get('season')
        self.pending_photo = None       # a picture chosen for the player on the card, not applied yet
        self.source = None              # (savedata folder, roster folder, file stamp) the view was made from
        self.slot = None                # that roster (savedata.Slot, DiscSlot, or RosterFile in an export from a file)
        self.raw = None                 # Snapshot of the save as it is
        self.raw_source = None
        self.raw_bytes = None           # its SYS-DATA, as read (an update in place checks it is still that)
        self.view = None                # (BuildResult, Snapshot): the roster with this visit's edits
        self.session = set()            # keys (edits.py) of the player edits made since the roster was opened
        self.session_teams = set()      # slots of the team edits made since then
        self.pictures = None            # editor.pictures.Pictures of the shown roster's game
        self.picture = None             # {'token', 'url', 'caption'} of the card's picture
        self.picture_token = 0          # the picture on the card belongs to the latest request only
        self.after_busy = None          # what to do once the running job is finished
        self.busy = False
        self.saving_pictures = False    # a Save is putting the player's own pictures into the game
        self.league = None
        self.team = None
        self.player = None              # model.Player on the card
        self.card_open = False          # the card shows a player (or a new one, with player None)
        self.card_key = 0               # changes whenever the card is filled again (the page drops what was typed)
        self.new_who = None             # the player just added: the card shows him once the roster is rebuilt
        self.new_preset = None          # a new player's card starts with these ({'title', 'note', 'values'}), or None
        self.new_extra = None           # and his edit gets these on Apply (Draft & Pro: 'prospect', 'pro')
        self.next_note = None           # (text, tone) the next rebuild says instead of its own line (Draft & Pro's maker)
        self.found = None               # the players found by a search (None: the team's players show)
        self.query = ''
        self.rows, self.row_players = [], {}
        self.name = savedata.default_name() + " edited"
        self.name_touched = False
        self.status = (NO_ROSTER, 'info')
        self.modal = None               # the Team, My edits or Face of a player window: dict, or None
        self.face_pick = None           # the face picked in that window, for the card: {seq, head, skin, eyes, note}
        self.face_seq = 0
        self.face_pics = {}             # head (str) -> data: link: the game's pictures of the generic heads
        self.face_pics_from = None      # the Pictures (editor/pictures.py) they were read with: read once per game
        self.face_loading = None        # the Pictures being read now
        self.look_pick = None           # the look made in the Look window, for the card: {seq, look, note}
        self.new_look = None            # the look a new player's card starts with (a plain random one)
        self.look_pics = {}             # part -> {number (str): data: link}: the Create Player menu's pictures
        self.look_pics_from = None
        self.look_loading = None
        self._looks_left = (None, {})   # (Snapshot, {'S', 'G': created looks left}): worked out once per roster
        self.tab = None                 # the tab in view (None: no page has said yet; the followers are left alone)
        self.followers = {}             # team tab -> its controller (follow / hide / roster_changed / drafts)
        self._reloaded = False          # a roster was read since the followers were last told
        self._views = (None, {})        # (Snapshot, {slot: team_view}) for the team list
        self.close_anyway = False       # the player chose to close the window with edits not saved

    # --- helpers ------------------------------------------------------------------------------------
    def changed(self):
        self.host.changed(SLICE)
        self.host.changed(RAIL)

    def set_status(self, text, tone='info'):
        self.status = (text, tone)
        self.changed()

    @property
    def snap(self):
        return self.view[1] if self.view else None

    def edited_keys(self):
        """Person keys the shown roster has for players edited in this visit (a renamed player has a new key)."""
        return set(self.session) | set(C.renamed(self.edits, self.session))

    def edit_key(self, p):
        """The key an edit of `p` is stored under: his original name if he was renamed before."""
        return p.who if p.who in self.edits else C.renamed(self.edits).get(p.who, p.who)

    def choices(self):
        """Team choices of the card: slot -> 'NHL · Boston Bruins' (and 'FA' -> Free agents)."""
        snap = self.snap
        out = {model.FREE_AGENTS: "Free agents"}
        if snap is not None:
            for t in range(len(snap.team_names)):
                if t in snap.copies or not snap.team_names[t].strip():
                    continue
                out[t] = f"{snap.team_league[t]} · {snap.team_names[t]}"
        return out

    @staticmethod
    def pro_team(team):
        """Can Be a Pro pick a player of `team` (lab rounds 44 / 46: NHL rosters and CHL juniors only)?"""
        return isinstance(team, int) and (team in L.NHL_PRIMARY or team in L.CHL)

    def _is_pro(self, p):
        """Is the card (player `p`, None for a new one) the player's own pro?"""
        if p is None:
            return bool((self.new_extra or {}).get('pro'))
        return bool((self.edits.get(self.edit_key(p)) or {}).get('pro'))

    def _pro_choices(self, current):
        """The card's team choices for the pro: NHL teams and CHL clubs (and the team he is on now, if not one)."""
        out = [[k, v] for k, v in self.choices().items() if self.pro_team(k) or k == current]
        return out

    def _edits_saved(self, players=True):
        edits.save(self.edits) if players else edits.save(teams=self.teams)
        self.update.changed()           # the Update tab's My edits row

    # --- loading ------------------------------------------------------------------------------------
    def opened(self):
        """The tab came into view: (re)load if the chosen roster changed."""
        with self.lock:
            upd = self.update
            path = upd.roster_file()        # an export from a roster file: the tabs show that file (a tester saw 2014-15)
            slot = RosterFile(path) if path else upd.selected_slot()
            if slot is None or (upd.rpcs3 is None and path is None):
                self.slot = None
                if not self.busy:
                    self.view, self.source = None, None
                    self.set_status(NO_ROSTER)
                return
            source = (upd.rpcs3.savedata if upd.rpcs3 else None, slot.folder, self._stamp(slot))
            self.slot = slot
            if source != self.source:       # another roster, or the file changed (an update, the game, a save here)
                self.source, self.view, self.pictures = source, None, None
                self.session, self.session_teams = set(), set()
                self.name_touched = False
                self.player, self.card_open, self.found, self.query = None, False, None, ''
                self.pending_photo = None
                self._clear_picture()
                self.load()
            self._sync_name()
            self.changed()

    @staticmethod
    def _stamp(slot):
        """Size and time of a roster save's file, so a changed file is read again (None for the game's own roster)."""
        try:
            st = os.stat(slot.sys_data)
            return st.st_size, st.st_mtime_ns
        except (OSError, TypeError, AttributeError):
            return None

    def _sync_name(self):
        if not self.name_touched and self.slot is not None:
            self.name = self.slot.name if self.update.in_place(self.slot) else savedata.default_name() + " edited"

    def _work(self, text, job, done):
        """Run `job()` in a worker thread; `done(result)` afterwards (under the lock)."""
        if self.busy:
            return
        self.busy = True
        self.set_status(text)
        self.update.changed()           # the Update tab waits for the editor before it touches a roster

        def finished(result):
            with self.lock:
                self.busy = False
                done(result)
                then, self.after_busy = self.after_busy, None
                self.changed()
            self.update.changed()
            self._followers_now()
            if then:
                then()

        def failed(message):
            with self.lock:
                self.busy = False
                self.after_busy = None
                self.set_status(f"That did not work: {message}", 'bad')
            self.update.changed()
        jobs.run(job, finished, failed)

    def _with_edits(self, raw_bytes):
        """The roster with the edits made since it was opened (the earlier ones are in it already). A roster file an
        export starts from gets every edit of My edits, as the export applies them."""
        mine = {k: v for k, v in self.edits.items() if k in self.session}
        teams = {k: v for k, v in self.teams.items() if k in self.session_teams}
        if getattr(self.slot, 'file', False) and self.update.use_edits:
            mine, teams = dict(self.edits), dict(self.teams)
        return model.apply_edits(raw_bytes, mine, teams, self.season)

    def load(self):
        slot, source = self.slot, self.source

        def job():
            raw = savedata.read_roster(slot)
            return raw, self._with_edits(raw)
        self._work("Reading the roster...", job, lambda r: self._loaded(source, *r))

    def _loaded(self, source, raw, built):
        if source != self.source:           # another roster was picked meanwhile: read that one
            self.after_busy = self.load if self.source else None
            return
        patched = getattr(built, 'patched', False)      # Coachella Valley / Henderson under the AHL, as the game shows them
        if self.raw is None or self.raw_source != self.source:
            # a roster made for the game patch is shown with this program's years, as its update reads it
            self.raw = model.Snapshot(gamepatch.unshifted(raw), self.offset, self.season, farm_ahl=patched)
            self.raw_source = self.source
            self.raw_bytes = raw
            missing = self._not_saved() - self.session
            if missing:                     # made in an earlier visit, never saved into this roster: shown and saved now
                self.session |= missing
                self.after_busy = self.load
        self.view = (built, model.Snapshot(built.data, self.offset, self.season, farm_ahl=patched))
        self._reloaded = True
        self.show()

    def _not_saved(self):
        """Keys of the new players of My edits (a pro, a class player, one made on the card) that the roster as read
        lacks. They count as this visit's edits, so the Save bar says they are not saved yet and Save puts them in
        (after a restart this visit's list starts empty)."""
        raw = self.raw
        if raw is None:
            return set()
        now = {old: new for new, old in C.renamed(self.edits).items()}
        return {k for k, e in self.edits.items()
                if e.get('new') and k not in raw.by_who and now.get(k, k) not in raw.by_who}

    def refresh(self):
        """After an edit: rebuild the shown roster with the edits."""
        if self.busy:
            self.after_busy = self.load
            return
        self.load()

    # --- showing ------------------------------------------------------------------------------------
    def show(self):
        snap = self.snap
        if snap is None:
            return
        leagues = snap.leagues()
        if self.league not in leagues:
            self.league = leagues[0]
        built = self.view[0]
        note, self.next_note = self.next_note, None
        if built.problems:
            more = f" (and {len(built.problems) - 1} more)" if len(built.problems) > 1 else ""
            self.set_status(f"Not playable yet: {built.problems[0]}{more}", 'bad')
        elif note:
            self.set_status(*note)
        elif heads_up(built) and (self.session or self.session_teams):
            self.set_status(heads_up(built), 'warn')
        else:
            self.set_status("Showing the roster as it is" + (f", with your {len(self.session)} edits not saved yet"
                                                            if self.session or self.session_teams else "")
                            + ". Pick a team, then a player.")
        self._show_teams()
        if getattr(self.slot, 'file', False) and not built.problems and not note:
            self.set_status(ROSTER_FILE)
        if self.new_who is not None and self.player is None and self.card_open:
            p = snap.by_who.get(self.new_who)       # the player just added: show him as the roster has him
            if p is not None:
                self.player = p
                self._fill_card(p)
            self.new_who = None
        elif self.player is not None:               # the same player as this view has him (team, rating, picture)
            p = snap.by_who.get(self.player.who)
            if p is not None:
                self.player = p
                self._fill_card(p)

    def _show_teams(self):
        teams = self.snap.teams_in(self.league)
        if self.team not in teams:
            self.team = teams[0] if teams else None
        if self.found is not None:
            self.found = self.snap.search(self.query)
            self._show_players(self.found)
        else:
            self._show_players(self.snap.roster(self.team) if self.team is not None else [], self.team)

    def _show_players(self, players, team=None):
        snap = self.snap
        renamed = C.renamed(self.edits, self.session)
        diff = model.compare(self.raw, snap, team, renamed) if team is not None and self.raw else \
            {'joined': {}, 'left': [], 'changed': {}}
        edited = self.edited_keys()
        rows = []
        for p in players:
            tag, note = '', ''
            if p.who in diff['joined']:
                tag, note = ('new', "new to the game") if diff['joined'][p.who] == 'new to the game' else \
                    ('joined', f"from {diff['joined'][p.who]}")
            elif p.who in diff['changed']:
                tag, note = 'changed', C.change_note(self.raw.by_who.get(renamed.get(p.who, p.who)), p,
                                                     diff['changed'][p.who])
            if team is None:
                note = ", ".join(snap.team_name(t) for t in p.clubs) or "free agent"
            if p.who in edited:
                tag, note = 'edited', ("your edit; " + note).rstrip('; ')
            rows.append((p, tag, note))
        for p in diff['left']:
            now = snap.by_who.get(p.who)
            where = ", ".join(snap.team_name(t) for t in now.clubs) if now else ''
            rows.append((p, 'left', f"left: now {where or 'free agent'}" if now else "left"))
        self.row_players = {}
        self.rows = []
        for i, (p, tag, note) in enumerate(rows):
            ident = str(i)
            self.row_players[ident] = (p, tag)
            self.rows.append({'id': ident, 'who': p.who, 'pos': p.pos, 'num': p.num, 'name': p.name,
                              'age': p.age(snap.season_year), 'nat': p.country, 'ovr': p.ovr or '', 'note': note,
                              'tag': tag})

    def set_league(self, league):
        with self.lock:
            if self.snap is None or league not in self.snap.leagues():
                return
            self.league, self.found, self.query = league, None, ''
            self._show_teams()
            self.changed()
        self._followers_now()

    def pick_team(self, team):
        with self.lock:
            team = C.team_value(team)
            if self.snap is None or team is None:
                return
            if team not in self.snap.teams_in(self.league):     # a team of another league (Front office's links)
                league = "Free agents" if team == model.FREE_AGENTS else self.snap.team_league.get(team)
                if league is None or team not in self.snap.teams_in(league):
                    return
                self.league = league
            self.team, self.found, self.query = team, None, ''
            self._show_players(self.snap.roster(team), team)
            self.changed()
        self._followers_now()

    def search(self, text):
        with self.lock:
            if self.snap is None:
                return
            self.query = str(text or '').strip()
            if not self.query:              # an empty search: back to the team
                self.found = None
                self._show_teams()
                self.changed()
                return
            self.found = self.snap.search(self.query)
            self._show_players(self.found)
            self.set_status(f"{len(self.found)} players found" if self.found else "Nobody by that name in this roster.")

    def rail_step(self, step):
        """Alt+Up / Alt+Down: the team before or after the picked one in the list."""
        with self.lock:
            snap = self.snap
            if snap is None:
                return
            teams = snap.teams_in(self.league)
            if not teams:
                return
            at = teams.index(self.team) if self.team in teams else 0
            team = teams[max(0, min(len(teams) - 1, at + (1 if step > 0 else -1)))]
        if team != self.team:
            self.pick_team(team)

    # --- the team tabs: the team list and the followers ----------------------------------------------
    def follow_with(self, tab, follower):
        """`follower` shows the picked team on tab `tab` (it has follow(team), hide(), roster_changed(); drafts()
        and rail_numbers() if it has them)."""
        self.followers[tab] = follower

    def show_tab(self, tab):
        """The page shows tab `tab`: a team tab reads the roster picked in Setup (if it changed), its follower
        follows the team, the others rest."""
        with self.lock:
            self.tab = str(tab or '')
        if self.tab in TEAM_TABS:
            self.opened()
        self._followers_now()
        self.host.changed(RAIL)

    def roster_key(self):
        """Which roster the team tabs show ((savedata folder, roster folder)); None without one. A follower drops
        what it keeps for teams when this changes."""
        return self.source[:2] if self.source else None

    def _followers_now(self):
        """Tell the followers what to show. Never called with the lock held: a follower takes its own lock first."""
        with self.lock:
            if self.tab is None:            # no page (the tests drive the windows themselves)
                return
            tab, followers = self.tab, dict(self.followers)
            team = self.team if self.snap is not None else None
            reloaded, self._reloaded = self._reloaded, False
        for f in followers.values():
            if reloaded:
                f.roster_changed()
        for name, f in followers.items():
            if name == tab:
                f.follow(team)
            else:
                f.hide()
        self.host.changed(RAIL)

    def team_view(self, team):
        """{id, code, name, colours: [main, second], league} of a team for the code chips (no logos)."""
        snap = self.snap
        if snap is None or team is None:
            return None
        if team == model.FREE_AGENTS:
            return dict(FREE_AGENTS_VIEW)
        if self._views[0] is not snap:
            self._views = (snap, {})
        cache = self._views[1]
        if team not in cache:
            R, name = snap.R, snap.team_name(team)
            try:
                code = getattr(snap, 'team_codes', {}).get(team) or str(R.T.get(team, 'abbrname') or '').strip()
            except (KeyError, IndexError, ValueError):
                code = ''
            try:
                colours = ['#%02x%02x%02x' % tuple(c) for c in looks.team_colours(R, team)]
            except (KeyError, IndexError, ValueError, TypeError):
                colours = ['#2c4560', '#ffffff']
            cache[team] = {'id': team, 'code': (code or name[:3]).upper()[:4], 'name': name, 'colours': colours,
                           'league': snap.team_league.get(team, '')}
        return dict(cache[team])

    def _parents(self, snap):
        """{AHL club: its NHL team} of the shown roster."""
        T, out = snap.R.T, {}
        for nhl in sorted(L.NHL_PRIMARY):
            try:
                farm = T.get(nhl, 'ahlaffiliate') - 1
            except (KeyError, IndexError, ValueError):
                continue
            if farm >= 0:
                out.setdefault(farm, nhl)
        for farm, nhl in L.AHL_PARENT_EXTRA.items():
            out.setdefault(farm, nhl)
        return out

    def rail_view(self):
        """The team list: the league, its teams with a code chip and one number for the tab in view."""
        tab = self.tab or 'roster'
        follower = self.followers.get(tab)
        numbers, dirty = {}, set()
        # asked before the lock is taken: a follower takes its own lock, and may take this one after it
        if follower is not None and hasattr(follower, 'rail_numbers') and tab in ('calendar', 'office'):
            try:
                numbers = follower.rail_numbers() or {}
            except Exception:
                numbers = {}
        if follower is not None and hasattr(follower, 'drafts'):
            try:
                dirty = set(follower.drafts())
            except Exception:
                dirty = set()
        with self.lock:
            snap = self.snap
            if snap is None:
                return {'loaded': False, 'busy': self.busy, 'status': self.status[0], 'league': None, 'leagues': [],
                        'rows': [], 'tip': RAIL_TIPS.get(tab, '')}
            parents = self._parents(snap)
            rows = []
            for t in snap.teams_in(self.league) if self.league else []:
                view = self.team_view(t)
                if tab in ('calendar', 'office'):
                    number = numbers.get(t, numbers.get(str(t)))
                else:
                    number = {'text': str(len(snap.rosters.get(t, []))), 'tip': 'players'}
                farm = parents.get(t) if view['league'] == 'AHL' else None
                rows.append(dict(view, sel=t == self.team, number=number, dirty=t in dirty,
                                 farm=self.team_view(farm)['code'] if farm is not None else None))
            return {'loaded': True, 'busy': self.busy, 'status': self.status[0], 'league': self.league,
                    'leagues': [{'value': x, 'label': x} for x in snap.leagues()], 'rows': rows, 'team': self.team,
                    'tip': 'club payroll' if tab == 'office' and self.league != 'NHL' else RAIL_TIPS.get(tab, '')}

    # --- the player card ----------------------------------------------------------------------------
    def pick_player(self, ident, typed=None):
        with self.lock:
            if self.snap is None or ident not in self.row_players:
                return
            p, tag = self.row_players[ident]
            if tag == 'left':
                p = self.snap.by_who.get(p.who)
                if p is None:
                    return
            if self.card_open and self.player is not None and p.who == self.player.who:
                return                      # the same row again: the card is kept as typed
            lost = None
            if self.card_open and typed and self.apply(typed, quiet=True) == 'error':
                lost = f"The changes to {self.player.name if self.player else 'the new player'} were not taken: " \
                       + self.status[0]
            self.new_preset = self.new_extra = None
            self.player, self.card_open, self.new_who = p, True, None
            self._fill_card(p)
            if lost:
                self.set_status(lost, 'bad')
            self.changed()

    def new_player(self, preset=None, extra=None):
        """An empty card for a new player. `preset` ({'title', 'note', 'values'}) starts it with other values, and
        `extra` goes into his edit on Apply (the Draft & Pro tab: a prospect block, or 'pro')."""
        with self.lock:
            if self.snap is None:
                return
            self.player, self.card_open, self.new_who = None, True, None
            self.new_preset, self.new_extra = preset, extra
            self._fill_card(None)
            self.changed()

    def open_person(self, key, typed=None):
        """The card shows the player whose edit is kept under `key` (the Draft & Pro tab's lists). One the shown roster
        does not have yet (made in an earlier visit, not saved into this roster) joins this visit's edits: the roster is
        rebuilt with him, and then he shows."""
        with self.lock:
            if self.snap is None or key not in self.edits:
                return
            now = {old: new for new, old in C.renamed(self.edits).items()}.get(key, key)
            p = self.snap.by_who.get(now)
            if self.card_open and self.player is not None and p is not None and p.who == self.player.who:
                return
            lost = None
            if self.card_open and typed and self.apply(typed, quiet=True) == 'error':
                lost = f"The changes to {self.player.name if self.player else 'the new player'} were not taken: " \
                       + self.status[0]
            self.new_preset = self.new_extra = None
            if p is None:
                self.session.add(key)
                self.player, self.card_open, self.new_who = None, True, now
                self._fill_card(None)
                self.refresh()
            else:
                self.player, self.card_open, self.new_who = p, True, None
                self._fill_card(p)
            if lost:
                self.set_status(lost, 'bad')
            self.changed()

    def _fill_card(self, p):
        self.pending_photo = None
        self.face_pick = self.look_pick = None
        self.new_look = faces.random_look(random.Random()) if p is None else None
        self.card_key += 1
        self._show_picture(p)

    def _card_view(self):
        if not self.card_open or self.snap is None:
            return None
        snap, p = self.snap, self.player
        goalie = p is not None and p.pos == 'G'
        labels = model.GOALIE_ATTRIBUTES if goalie else model.SKATER_ATTRIBUTES
        if p is None:
            team = self.team if isinstance(self.team, int) else model.FREE_AGENTS
            preset = self.new_preset or {}
            return {'key': self.card_key, 'new': True, 'title': preset.get('title') or "New player",
                    'note': preset.get('note') or "Takes a spare player record (the save has a fixed number). Give a "
                                                  "name, birthdate, team and overall; ratings are optional.",
                    'values': {'first': '', 'last': '', 'num': '', 'pos': 'C', 'shoots': 'L', 'birth': '',
                               'country': 'CAN', 'height': '', 'weight': '', 'team': team, 'ovr': '70',
                               'style': '', 'head': '', 'skin': '', 'eyes': '', 'ratings': {},
                               'look': self.new_look if self.looks_left()['S'] else None,
                               **(preset.get('values') or {})},
                    'face_note': "A generic head, unless you pick one", 'face_pick': self.face_pick,
                    'created': True, 'look_pick': self.look_pick, 'looks_left': self.looks_left(),
                    'labels': list(model.SKATER_ATTRIBUTES), 'goalie_labels': list(model.GOALIE_ATTRIBUTES),
                    'undo': False, 'photo_pending': bool(self.pending_photo),
                    'teams': self._pro_choices(team) if self._is_pro(None) else None}
        key = self.edit_key(p)
        teams = p.clubs
        return {'key': self.card_key, 'new': False, 'title': p.name, 'who': p.who,
                'note': (", ".join(snap.team_name(t) for t in teams) or "Free agent")
                        + (f"   ·   OVR {p.ovr} (the game works out its own from the ratings and the type)" if p.ovr else "")
                        + ("   ·   you edited this player (not saved yet)" if key in self.session else ""),
                'values': {'first': p.first, 'last': p.last, 'num': str(p.num), 'pos': p.pos, 'shoots': p.shoots,
                           'birth': "%04d-%02d-%02d" % p.birth, 'country': p.country,
                           'height': str(C.cm(p.height_in)), 'weight': str(C.kg(p.weight_lb)),
                           'team': teams[0] if teams else model.FREE_AGENTS, 'ovr': str(p.ovr or ''),
                           'style': '' if p.style is None else str(p.style),
                           **{k: str(v) for k, v in p.face.items()}, 'look': p.look,
                           'ratings': {a: str(p.ratings.get(a, '')) for a in labels}},
                'style_note': "" if p.style is None else "Edit Lines shows it next to his rating",
                'face_note': self.face_note(p.face['head'], p), 'face_pick': self.face_pick,
                'created': p.created, 'look_pick': self.look_pick, 'looks_left': self.looks_left(),
                'labels': list(labels), 'goalie_labels': list(model.GOALIE_ATTRIBUTES),
                'undo': key in self.session, 'photo_pending': bool(self.pending_photo),
                'equipment': p.equipment is not None,
                'contract': {'shown': 'office' in self.followers,
                             'edited': bool((self.edits.get(key) or {}).get('contract'))},
                'teams': self._pro_choices(teams[0] if teams else model.FREE_AGENTS) if self._is_pro(p) else None}

    def apply(self, typed, quiet=False):
        """Take the card's values into the edits. Says what happened: 'applied' (the roster is being rebuilt),
        'nothing' (the card has no change) or 'error' (the status line says why). `quiet`: the player did not
        press Apply (Save or another player did); a card without a real change is left alone."""
        with self.lock:
            if self.snap is None or not self.card_open:
                return 'nothing'
            p = self.player
            goalie = (typed or {}).get('pos') == 'G' if p is None else p.pos == 'G'
            labels = model.GOALIE_ATTRIBUTES if goalie else model.SKATER_ATTRIBUTES
            values, problem = C.read(typed or {}, labels, p is None, self.choices(), p.ratings if p else None,
                                     self.snap.heads)
            if problem:
                self.set_status(problem, 'bad')
                return 'error'
            if values['look'] and p is not None and not p.created:
                self.set_status(LOOK_NOT_HERE, 'bad')
                return 'error'
            if self._is_pro(p) and not self.pro_team(values['team']):
                self.set_status(PRO_TEAM, 'bad')
                return 'error'
            if p is None:                       # a new player
                who, edit = C.new_player(values, self.pending_photo)
                if self.snap.by_who.get(who):
                    self.set_status("That player is in the roster already: edit him instead.", 'bad')
                    return 'error'
                edit.update(self.new_extra or {})
                self.new_preset = self.new_extra = None
                self.edits[who] = edit
                self.new_who = who
                key = who
            else:
                key = self.edit_key(p)
                edit, real = C.player_edit(p, values, self.edits.get(key), self.pending_photo)
                if not real and (quiet or ('team' not in edit and key not in self.edits)):
                    if not quiet:
                        self.set_status("Nothing changed.")
                    return 'nothing'
                self.edits[key] = edit
            self.session.add(key)
            self.pending_photo = None
            self._edits_saved()
            self.refresh()
            self.changed()
            return 'applied'

    def undo(self):
        with self.lock:
            p = self.player
            if p is None:
                return
            key = self.edit_key(p)
            if key in self.edits and key in self.session:      # an edit made before is in the roster: it stays there
                del self.edits[key]
                self.session.discard(key)
                self._edits_saved()
                self.refresh()

    # --- pictures -----------------------------------------------------------------------------------
    def pick_picture(self, title, face=False):
        """A picture file the player picks, kept in the program's folder: its 'file:' link, or None. `face`: a
        player's photo, which must show a head the game's portrait can be made from."""
        start = os.path.expanduser('~')
        path = self.host.ask_open(title, ['Pictures (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif)'], start)
        if not path:
            return None
        try:
            from PIL import Image
            with Image.open(path) as img:
                img.load()
                if face:
                    from ..art import images
                    if images.portrait(img, (256, 128)) is None:
                        self.set_status(NO_FACE, 'bad')
                        return None
        except Exception:
            self.set_status("That file is not a picture this program can read (PNG, JPG, WebP).", 'bad')
            return None
        return edits.keep_picture(path)

    def choose_photo(self):
        with self.lock:
            if not self.card_open:
                return
        link = self.pick_picture("A photo for this player", face=True)
        if link:
            with self.lock:
                self.pending_photo = link
                self._show_picture(self.player)
                self.set_status(PHOTO_PICKED, 'warn')

    def _pictures(self):
        """Pictures of the game the shown roster belongs to (None before RPCS3 is found)."""
        rpcs3 = self.update.rpcs3
        if rpcs3 is None or self.source is None:
            return None
        from ..editor.pictures import Pictures
        title_id = self.slot.title_id if getattr(self.slot, 'file', False) else self.source[1][:9]
        if self.pictures is None or self.pictures.title_id != title_id or self.pictures.rpcs3 is not rpcs3:
            self.pictures = Pictures(rpcs3, title_id)
        return self.pictures

    def _clear_picture(self):
        self.picture_token += 1
        self.picture = {'token': self.picture_token, 'url': None, 'caption': '', 'loading': False}
        self.host.changed(PICTURE)

    def _show_picture(self, p):
        """The picture for player `p` (None: a new player), as the game shows it: his own if he has one, else
        what the game shows now. It is made in a worker thread; only the latest request is shown."""
        own = self.pending_photo or ((self.edits.get(self.edit_key(p)) or {}).get('photo') if p is not None else None)
        if p is None and not own:
            self._clear_picture()
            return
        self.picture_token += 1
        token = self.picture_token
        self.picture = {'token': token, 'url': (self.picture or {}).get('url'), 'caption': "Loading the picture...",
                        'loading': True}
        self.host.changed(PICTURE)
        try:
            pictures = self._pictures()
        except Exception:
            pictures = None

        def job():
            try:
                from ..editor.pictures import NO_GAME, Pictures
                if own:
                    pic, caption = Pictures.mine(own)
                elif pictures is None:
                    pic, caption = None, NO_GAME
                else:
                    pic, caption = pictures.current(p.artid, p.hasportrait)
                return dataurl.picture(pic, PORTRAIT), caption
            except Exception:
                return None, "The picture could not be read."

        def run():
            url, caption = job()
            with self.lock:
                if token != self.picture_token:     # the card shows someone else by now
                    return
                self.picture = {'token': token, 'url': url, 'caption': caption, 'loading': False}
            self.host.changed(PICTURE)
        threading.Thread(target=run, daemon=True).start()

    def picture_view(self):
        return self.picture

    # --- the Team window -----------------------------------------------------------------------------
    def team_open(self):
        with self.lock:
            if not isinstance(self.team, int) or self.snap is None:
                self.set_status("Pick a team first.", 'warn')
                return
            slot, snap = self.team, self.snap
            T = snap.R.T
            mine = dict(self.teams.get(str(slot)) or {})
            self.modal = {'kind': 'team', 'slot': slot, 'name': snap.team_name(slot),
                          'fields': {part: mine.get(part) or T.get(slot, field)
                                     for part, field in (('full', 'fullname'), ('city', 'shortname'),
                                                         ('abbr', 'abbrname'))},
                          'logo': None, 'logo_text': '', 'mine': bool(self.teams.get(str(slot)))}
            self._logo_link = mine.get('logo')
            self._team_logo()
            self.changed()

    def _team_logo(self):
        link, modal = self._logo_link, self.modal
        if not link or modal is None:
            return
        modal['logo_text'] = "Loading..."

        def run():
            try:
                from PIL import Image
                from ..art import images
                url, text = dataurl.picture(images.logo(Image.open(link[5:]), 't', (256, 256)), (192, 192)), ''
            except Exception:
                url, text = None, "(your logo)"
            with self.lock:
                if self.modal is modal:
                    modal['logo'], modal['logo_text'] = url, text
                    self.changed()
        threading.Thread(target=run, daemon=True).start()

    def team_choose_logo(self):
        with self.lock:
            if (self.modal or {}).get('kind') != 'team':
                return
        link = self.pick_picture("A logo for this team")
        if link:
            with self.lock:
                self._logo_link = link
                self._team_logo()
                self.changed()

    def team_apply(self, values):
        with self.lock:
            modal = self.modal
            if (modal or {}).get('kind') != 'team' or self.snap is None:
                return
            slot = modal['slot']
            T = self.snap.R.T
            mine = dict(self.teams.get(str(slot)) or {})
            for part, field in (('full', 'fullname'), ('city', 'shortname'), ('abbr', 'abbrname')):
                value = str((values or {}).get(part) or '').strip()
                if value and value != T.get(slot, field):
                    mine[part] = value
                else:
                    mine.pop(part, None)
            if self._logo_link:
                mine['logo'] = self._logo_link
            if mine:
                self.teams[str(slot)] = mine
                self.session_teams.add(str(slot))
            else:
                self.teams.pop(str(slot), None)
            self._edits_saved(players=False)
            self.modal = None
            self.refresh()
            self.changed()

    def team_undo(self):
        with self.lock:
            modal = self.modal
            if (modal or {}).get('kind') != 'team':
                return
            slot = str(modal['slot'])
            self.teams.pop(slot, None)
            self.session_teams.discard(slot)
            self._edits_saved(players=False)
            self.modal = None
            self.refresh()
            self.changed()

    def close_modal(self):
        with self.lock:
            self.modal = None
            self.changed()

    # --- Face of a player -----------------------------------------------------------------------------
    def face_note(self, head, p=None):
        """Whose head `head` is, in words for the card."""
        if head >= faces.GENERIC:
            return f"Generic head {head}"
        others = [q.name for q in self.snap.wearers(head) if p is None or q.who != p.who]
        if not others:
            return "His own head" if p is not None else f"Head {head}"
        return "Same head as " + ", ".join(others[:2]) + (f" and {len(others) - 2} more" if len(others) > 2 else "")

    def face_open(self):
        """The Face of a player window. The generic heads show as the game's own pictures (its Create Player menu's,
        from the player's disc), read once in a worker thread; without the disc they are picked by number."""
        with self.lock:
            if self.snap is None or not self.card_open:
                return
            generic = faces.generic(self.snap.R)
            pick, p = (self.face_pick or {}).get('head'), self.player
            current = int(pick) if pick else (p.face['head'] if p is not None else None)
            try:
                pictures = self._pictures()
                disc = pictures is not None and pictures.rpcs3.game_disc(pictures.title_id)
            except Exception:
                pictures, disc = None, None
            if not disc:
                pics = 'none'
            elif self.face_pics_from is pictures and self.face_pics:
                pics = 'ready'
            else:
                pics = 'loading'
            start = pics == 'loading' and self.face_loading is not pictures
            if start:
                self.face_loading = pictures
            self.modal = {'kind': 'face', 'query': '', 'found': [], 'generic': generic, 'current': current,
                          'pics': pics, 'note': self._face_pics_note(pics)}
            self.changed()
        if start:
            threading.Thread(target=self._read_face_pictures, args=(pictures, generic), daemon=True).start()

    @staticmethod
    def _face_pics_note(pics):
        if pics == 'none':
            return "RPCS3 does not say where your game is, so the heads are not shown as pictures. Pick a number."
        return "Reading the game's pictures of the heads..." if pics == 'loading' else ""

    def _read_face_pictures(self, pictures, heads):
        try:
            found = pictures.disc_work(lambda disc: self._face_menu_pictures(disc, heads))
        except Exception:
            found = {}
        with self.lock:
            if self.face_loading is pictures:
                self.face_loading = None
            if found:
                self.face_pics, self.face_pics_from = found, pictures
            modal = self.modal
            if (modal or {}).get('kind') == 'face' and modal.get('pics') == 'loading':
                pics = 'ready' if found else 'none'
                self.modal = dict(modal, pics=pics, note=self._face_pics_note(pics))
                self.changed()
        self.host.changed(FACE_PICS)

    @staticmethod
    def _face_menu_pictures(disc, heads):
        """{head (str): data: link} of the heads the game's Create Player menu has a picture of (cache.big
        `createplayer/head/head<id>`: 256 x 128, the head on the left; cut to the head)."""
        from PIL import Image
        from ..art import dds
        from ..art.bigf import ArtFile
        arc = disc.archives['cache.big']
        out = {}
        for head in heads:
            name = FACE_MENU.format(head)
            if name not in arc.entries:
                continue
            try:
                data = ArtFile(arc.read(name)).image()
                h = dds.Header(data)
                if h.fourcc is None and h.bits == 32 and h.masks == (0xff0000, 0xff00, 0xff, 0xff000000):
                    # plain 32-bit pixels: Pillow's own reader takes 30 ms for each of these
                    img = Image.frombuffer('RGBA', (h.width, h.height), data[128:128 + h.width * h.height * 4],
                                           'raw', 'BGRA', 0, 1)
                else:
                    img = Image.open(io.BytesIO(data))
                    img.load()
                img = img.convert('RGBA')
                box = img.getchannel('A').getbbox()
            except Exception:
                continue
            if box:
                out[str(head)] = dataurl.picture(img.crop(box))
        return out

    def face_pics_view(self):
        return self.face_pics

    def face_search(self, text):
        with self.lock:
            modal = self.modal
            if (modal or {}).get('kind') != 'face' or self.snap is None:
                return
            snap = self.snap
            found = [p for p in snap.search(text, limit=400)        # a created look's head is his alone
                     if p.face['head'] in snap.heads and p.face['head'] not in faces.CUSTOM_HEADS][:FACE_FOUND]
            found.sort(key=lambda p: (p.face['head'] >= faces.GENERIC, p.name))
            self.modal = dict(modal, query=text, found=[
                {'who': p.who, 'name': p.name, 'pos': p.pos,
                 'team': ", ".join(snap.team_name(t) for t in p.clubs) or "Free agent",
                 'face': ("generic head" if p.face['head'] >= faces.GENERIC else "his own head"),
                 **p.face} for p in found])
            self.changed()

    def face_pick_player(self, who):
        """The card takes the head, skin and eyes of player `who` (not applied until Apply)."""
        with self.lock:
            q = self.snap.by_who.get(who) if self.snap is not None else None
            if q is None or (self.modal or {}).get('kind') != 'face':
                return
            self._picked(dict(q.face), f"Face of {q.name} (press Apply)")

    def face_pick_generic(self, head):
        """The card takes the generic head `head`; skin and eyes stay."""
        with self.lock:
            try:
                head = int(head)
            except (TypeError, ValueError):
                return
            if self.snap is None or head not in self.snap.heads or (self.modal or {}).get('kind') != 'face':
                return
            self._picked({'head': head}, f"Generic head {head} (press Apply)")

    def _picked(self, face, note):
        self.face_seq += 1
        self.face_pick = {'seq': self.face_seq, **{k: str(v) for k, v in face.items()}, 'note': note}
        self.modal = None
        self.changed()

    # --- a created look (the game's Create Player "Custom Head") --------------------------------------------
    def looks_left(self):
        """{'S': skaters, 'G': goalies}: how many more players made here can have a created look (the game's Create
        Player records still free in the shown roster, those kept for the game itself left out)."""
        snap = self.snap
        if snap is None:
            return {'S': 0, 'G': 0}
        if self._looks_left[0] is not snap:
            self._looks_left = (snap, {kind: len(faces.free_reserved(snap.R, kind == 'G')) for kind in ('S', 'G')})
        return dict(self._looks_left[1])

    def look_open(self, look=None):
        """The Look window, starting from `look` (the card's, as typed; None: the game's default). The Create Player
        menu's pictures (head shapes, colours, eyes) come from the player's disc, read once in a worker thread."""
        with self.lock:
            if self.snap is None or not self.card_open:
                return
            p = self.player
            if p is not None and not p.created:
                self.set_status(LOOK_NOT_HERE, 'bad')
                return
            whole, _problems = faces.clean_look(look if isinstance(look, dict) else None)
            try:
                pictures = self._pictures()
                disc = pictures is not None and pictures.rpcs3.game_disc(pictures.title_id)
            except Exception:
                pictures, disc = None, None
            if not disc:
                pics = 'none'
            elif self.look_pics_from is pictures and self.look_pics:
                pics = 'ready'
            else:
                pics = 'loading'
            start = pics == 'loading' and self.look_loading is not pictures
            if start:
                self.look_loading = pictures
            self.modal = {'kind': 'look', 'look': whole, 'rows': LOOK_ROWS, 'words': faces.look_words(whole),
                          'pics': pics, 'note': self._look_pics_note(pics)}
            self.changed()
        if start:
            threading.Thread(target=self._read_look_pictures, args=(pictures,), daemon=True).start()

    @staticmethod
    def _look_pics_note(pics):
        if pics == 'none':
            return "RPCS3 does not say where your game is, so the choices are shown as words."
        return "Reading the game's pictures..." if pics == 'loading' else ""

    def _read_look_pictures(self, pictures):
        try:
            found = pictures.disc_work(self._look_menu_pictures)
        except Exception:
            found = {}
        with self.lock:
            if self.look_loading is pictures:
                self.look_loading = None
            if found:
                self.look_pics, self.look_pics_from = found, pictures
            modal = self.modal
            if (modal or {}).get('kind') == 'look' and modal.get('pics') == 'loading':
                pics = 'ready' if found else 'none'
                self.modal = dict(modal, pics=pics, note=self._look_pics_note(pics))
                self.changed()
        self.host.changed(LOOK_PICS)

    @staticmethod
    def _look_menu_pictures(disc):
        """{part: {number (str): data: link}} of the Create Player menu's pictures on the player's disc."""
        from PIL import Image
        from ..art.bigf import ArtFile
        arc = disc.archives['cache.big']
        root = FACE_MENU.rsplit('/', 2)[0]

        def picture(name, swatch):
            name = f"{root}/{name}.big"
            if name not in arc.entries:
                return None
            try:
                img = Image.open(io.BytesIO(ArtFile(arc.read(name)).image()))
                img.load()
                img = img.convert('RGBA')
            except Exception:
                return None
            if swatch:                  # the swatch is the left square
                img = img.crop((0, 0, img.height, img.height))
            else:
                box = img.getchannel('A').getbbox()
                img = img.crop(box) if box else img
            return dataurl.picture(img)
        out = {'shape': {}}
        for n, head in enumerate(faces.SHAPES, 1):
            url = picture(f"head/head{(head - 20000) // 50}", False)
            if url:
                out['shape'][str(n)] = url
        for part, pattern in LOOK_MENU.items():
            numbers = ([n for n, _w in faces.COLOURS] if part != 'eyes' else list(faces.EYE_WORDS))
            out[part] = {}
            for i, n in enumerate(numbers, 1):
                url = picture(pattern.format(n + 1 if part == 'eyes' else i), True)
                if url:
                    out[part][str(n)] = url
        return out if any(out.values()) else {}

    def look_pics_view(self):
        return self.look_pics

    def look_set(self, part, value):
        with self.lock:
            modal = self.modal
            if (modal or {}).get('kind') != 'look':
                return
            try:
                value = int(value)
            except (TypeError, ValueError):
                return
            if faces.look_wrong({part: value}):
                return
            look = dict(modal['look'], **{part: value})
            self.modal = dict(modal, look=look, words=faces.look_words(look))
            self.changed()

    def look_random(self):
        with self.lock:
            modal = self.modal
            if (modal or {}).get('kind') != 'look':
                return
            look = faces.random_look(random.Random())
            self.modal = dict(modal, look=look, words=faces.look_words(look))
            self.changed()

    def look_done(self):
        """The card takes the window's look (not applied until Apply)."""
        with self.lock:
            modal = self.modal
            if (modal or {}).get('kind') != 'look':
                return
            self.face_seq += 1
            self.look_pick = {'seq': self.face_seq, 'look': dict(modal['look']), 'note': "Created look (press Apply)"}
            self.modal = None
            self.changed()

    # --- contracts (the Front office's contract window) ---------------------------------------------------
    def _contract_key(self, key):
        """(edit key, player) of the player `key` names (his key in the shown roster, or an edit key)."""
        p = self.snap.by_who.get(key) if self.snap is not None else None
        return (self.edit_key(p), p) if p is not None else (key, None)

    def contract_of(self, key):
        """The contract set by hand for player `key` ({cap, years, two_way, ext}), or None."""
        with self.lock:
            k, _p = self._contract_key(key)
            deal = (self.edits.get(k) or {}).get('contract')
            return dict(deal) if deal else None

    def contract_edit(self, key, deal, team=None):
        """Keep `deal` ({"cap", "years", "two_way", "ext": [years, cap, two_way] or None}; None: take it back) as player
        `key`'s contract in My edits. Save writes it into the roster (edits.json players[key]["contract"]). `team`: the
        slot he signs with (a free agent, a player on no club): he moves there too (players[key]["team"])."""
        with self.lock:
            k, p = self._contract_key(key)
            e = dict(self.edits.get(k) or {'label': p.name if p is not None else str(key)})
            if team is not None:
                e['team'] = int(team)
            if deal is None:
                e.pop('contract', None)
            else:
                ext = deal.get('ext')
                e['contract'] = {'cap': int(deal['cap']), 'years': int(deal['years']),
                                 'two_way': 1 if deal.get('two_way') else 0,
                                 'ext': [int(ext[0]), int(ext[1]), 1 if ext[2] else 0] if ext else None}
            if set(e) <= {'label'}:
                self.edits.pop(k, None)
                self.session.discard(k)
            else:
                self.edits[k] = e
                self.session.add(k)
            self._edits_saved()
            if self.source:
                self.refresh()
            self.changed()
            return True

    def contract_open(self, key):
        """The card's "Contract...": the Front office's contract window for player `key`. The office follows his
        club first (his NHL team before any other) when it shows another (its tab may not be in view)."""
        office = self.followers.get('office')
        if office is None:
            return
        with self.lock:
            snap, tab = self.snap, self.tab
            p = snap.by_who.get(key) if snap is not None else None
            clubs = sorted(p.clubs, key=lambda t: (t not in L.NHL_PRIMARY, t)) if p is not None else []
            club = clubs[0] if clubs else None
        if club is not None and getattr(office, 'team', None) != club:
            office.follow(club)
            if tab != 'office':
                office.hide()
        office.contract_open(key)

    # --- My edits -------------------------------------------------------------------------------------
    def edits_open(self):
        with self.lock:
            self.modal = {'kind': 'edits'}
            self.changed()

    def _edits_view(self):
        items = []
        for slot, e in sorted(self.teams.items(), key=lambda kv: int(kv[0])):
            name = self.snap.team_name(int(slot)) if self.snap else f"team {slot}"
            items.append({'kind': 'team', 'key': slot, 'name': name, 'what': "team: " + ", ".join(sorted(e))})
        for who, e in sorted(self.edits.items(), key=lambda kv: kv[1].get('label', kv[0])):
            items.append({'kind': 'player', 'key': who, 'name': e.get('label', who),
                          'what': ", ".join(C.what_changed(e) + (['contract'] if e.get('contract') else []))})
        return items

    def edits_remove(self, kind, key):
        with self.lock:
            if kind == 'team':
                self.teams.pop(key, None)
                self.session_teams.discard(key)
                self._edits_saved(players=False)
            else:
                self.edits.pop(key, None)
                self.session.discard(key)
                self._edits_saved()
            if self.source:
                self.refresh()
            self.changed()

    # --- Jerseys and ice -----------------------------------------------------------------------------
    def uniforms_open(self):
        with self.lock:
            if not isinstance(self.team, int) or self.snap is None:
                self.set_status("Pick a team first.", 'warn')
                return
            owner, why = looks.window_team(self.snap.R, self.team)
            if why:
                self.set_status(why, 'warn')
                return
            team = self.team
        if self.uniforms is not None:
            self.uniforms.open(owner, picked=team)

    # --- saving ---------------------------------------------------------------------------------------
    def set_save_mode(self, mode):
        self.update.set_save_mode(mode)         # the same choice as on the Update tab
        with self.lock:
            self.name_touched = False
            self._sync_name()
            self.changed()

    def set_name(self, text):
        with self.lock:
            self.name = str(text or '')
            self.name_touched = True
            self.changed()

    def save(self, typed=None, applied=False):
        with self.lock:
            view = self.view
            if view is None or self.source is None or self.busy:
                return
            if self.card_open and typed and not applied:
                # what is typed on the card but was not applied counts: it is applied first, then the saving goes on
                state = self.apply(typed, quiet=True)
                if state == 'error':
                    return                      # the status line says what is wrong with the card
                if state == 'applied':
                    self.after_busy = lambda: self.save(applied=True)      # when the roster is rebuilt with it
                    return
            built = view[0]
            if getattr(self.slot, 'file', False):
                self.set_status(ROSTER_FILE, 'warn')
                return
            if self.raw_bytes is not None and gamepatch.is_patch_roster(Roster(self.raw_bytes)):
                self._save_patch_roster()
                return
            if built.problems:
                self.set_status("This roster does not pass the safety checks, so it cannot be saved: "
                                + built.problems[0], 'bad')
                return
            folder = self.source[0]
            source, upd = self.slot, self.update
            typed_name = self.name.strip()
            in_place = upd.in_place(source)
            targets = [source.title_id] if in_place else upd.save_targets(source) or [source.title_id]
            mine, teams = self._picture_edits()
            looks_for = pipeline.looks_teams(teams) | frozenset(self.looks_touched)
            touched = set(self.looks_touched)
            rpcs3, raw, season = upd.rpcs3, self.raw_bytes, self.season
            # the player's own pictures (and the jerseys, ice and crests of the teams he gave them) go into the game with
            # the roster, photos and logos off too, RPCS3 closed
            own = portraits.mine(mine, teams) or bool(looks_for)
            pictures = own and rpcs3 is not None and not rpcs3.plain and not savedata.running_rpcs3()
            if (in_place or pictures) and upd.busy:
                self.set_status("The Update tab is working. Save when it is done.", 'bad')
                return
            if in_place and savedata.running_rpcs3():
                self.set_status(f"{savedata.close_first()}: a roster can only be updated while the game is closed.", 'bad')
                return
            if not in_place:
                try:
                    for t in targets:           # room in the game's list for every version, before any is saved
                        savedata.next_free(folder, t)
                except savedata.RosterFull as err:
                    self.set_status(str(err), 'bad')
                    return
            later = (" Your own pictures, jerseys and ice go into the game when you save with RPCS3 closed."
                     if own and not pictures and rpcs3 is not None and not rpcs3.plain else "")
            season_looks = parts.LOOKS in upd.parts_on()

            def with_pictures():
                """The roster to save and the pictures that go in after it (None: the shown roster as it is)."""
                if not pictures:
                    return built, None, None
                title = next((t for t in targets if rpcs3.game_disc(t)), targets[0])
                try:
                    pics = pipeline.Pictures(rpcs3, title, targets, own_only=True, looks_for=looks_for,
                                             season_looks=season_looks)
                except ArtError as err:
                    return built, None, str(err)
                rebuilt = model.apply_edits(raw, mine, teams, season, art=pics)
                if rebuilt.problems:
                    raise RuntimeError("the roster with your pictures does not pass the safety checks: "
                                       + rebuilt.problems[0])
                return rebuilt, pics, None

            def put_in(result, pics, note):
                """(what _picture_status says about the pictures, how many teams' jerseys and ice went in)."""
                if pics is None:
                    return note, 0
                art, look_teams, _noted = pics.put_in(result, lambda msg: None)
                with self.lock:
                    self.looks_touched -= touched
                return art, look_teams

            self.saving_pictures = pictures
            if in_place:
                rename = typed_name if self.name_touched and typed_name and typed_name != source.name else None

                def job():
                    try:
                        result, pics, note = with_pictures()
                        saved = savedata.update_in_place(folder, source, result.data, rename, expected=raw,
                                                         backup_root=datasource.app_dir('backups'))
                        art = put_in(result, pics, note)
                        return saved, pipeline.write_report(result, f"{source.folder}_edited"), art
                    finally:
                        self.saving_pictures = False

                def done(r):
                    (slot, backup, changed), _report, (art, look_teams) = r
                    later_ = later + heads_up(built, " ")
                    self.set_status((f"Updated \"{slot.name}\" ({slot.folder}, {slot.region})"
                                     + (f"; the old roster is kept in {backup}" if backup else "")
                                     + ". In the game: start it; if it is not the roster in use, Customize > Save/Load/Delete > "
                                     "Load > Rosters.") if changed else "Nothing to save: the roster is the same.",
                                    'good')
                    self._picture_status(art, later_, look_teams)
                    self.session, self.session_teams, self.source = set(), set(), None       # read it again
                    self.name_touched = False
                    self.after_busy = self._rescan
                self._work("Saving...", job, done)
                return
            name = savedata.clean_name(typed_name or savedata.default_name())

            def job():
                try:
                    result, pics, note = with_pictures()
                    slots = [savedata.install(folder, source, result.data, name, title_id=t) for t in targets]
                    art = put_in(result, pics, note)
                    return slots, pipeline.write_report(result, f"{slots[0].folder}_edited"), art
                finally:
                    self.saving_pictures = False

            def done(r):
                slots, _report, (art, look_teams) = r
                where = " and ".join(f"{s.folder}, {s.region}" for s in slots)
                self.set_status(f"Saved as \"{slots[0].name}\" ({where}). In the game: Customize > Save/Load/Delete > "
                                "Load > Rosters.", 'good')
                self._picture_status(art, later + heads_up(built, " "), look_teams)
                self._open_saved(slots[0].folder)
            self._work("Saving...", job, done)

    def _save_patch_roster(self):
        """Save a roster made for the game patch (under the lock): its shown build has no patch part (the 32-team
        calendar, the AHL, the year), so the edits go in as an update with no update step does it
        (pipeline.update: the patch part runs, the roster stays for the game as RPCS3 has it), in place or as new."""
        upd, source = self.update, self.slot
        if upd.rpcs3 is None or source is None:
            self.set_status(NO_ROSTER, 'bad')
            return
        if upd.busy:
            self.set_status("The Update tab is working. Save when it is done.", 'bad')
            return
        in_place = upd.in_place(source)
        if in_place and savedata.running_rpcs3():
            self.set_status(f"{savedata.close_first()}: a roster can only be updated while the game is closed.", 'bad')
            return
        targets = [source.title_id] if in_place else upd.save_targets(source) or [source.title_id]
        typed_name = self.name.strip()
        if in_place:
            name = typed_name if self.name_touched and typed_name and typed_name != source.name else None
        else:
            name = savedata.clean_name(typed_name or savedata.default_name())
        mine, teams = self._picture_edits()
        rpcs3, parts_on = upd.rpcs3, upd.parts_on()
        touched = set(self.looks_touched)

        def job():
            r = pipeline.update(rpcs3.savedata, source.folder, [], name, None, my_edits=mine or None,
                                team_edits=teams or None, targets=targets, in_place=in_place,
                                rpcs3=None if rpcs3.plain else rpcs3, art_parts=parts_on, also_looks=touched)
            if r.slot is not None and r.own_pictures and not isinstance(r.art, str):
                with self.lock:
                    self.looks_touched -= touched
            return r

        def done(r):
            if r.slot is None:
                self.set_status("This roster does not pass the safety checks, so it cannot be saved: "
                                + (r.build.problems[0] if r.build.problems else "see the List of changes"), 'bad')
                return
            if in_place:
                self.set_status((f"Updated \"{r.slot.name}\" ({r.slot.folder}, {r.slot.region})"
                                 + (f"; the old roster is kept in {r.backup}" if r.backup else "")
                                 + ". In the game: start it; if it is not the roster in use, Customize > Save/Load/"
                                 "Delete > Load > Rosters.") if not r.unchanged else
                                "Nothing to save: the roster is the same.", 'good')
                self.session, self.session_teams, self.source = set(), set(), None      # read it again
                self.name_touched = False
                self.after_busy = self._rescan
            else:
                self.set_status(f"Saved as \"{r.slot.name}\" ({r.saved_where()}). In the game: Customize > "
                                "Save/Load/Delete > Load > Rosters.", 'good')
            self._picture_status(r.art if r.own_pictures else None, heads_up(r.build, " "),
                                 r.look_teams if r.own_pictures and not isinstance(r.art, str) else 0)
            if not in_place:
                self._open_saved(r.slot.folder)
        self._work("Saving...", job, done)

    def _picture_edits(self):
        """The edits a Save applies: this visit's, and the earlier edits of players in this roster that have a photo,
        and of teams with a logo, jerseys, a centre ice or a custom kit (Jerseys & ice; their pictures go into the game on
        Save too, with the colours, arena and kit they set; before, only an update put them in)."""
        mine = {k: v for k, v in self.edits.items() if k in self.session}
        teams = {k: v for k, v in self.teams.items() if k in self.session_teams}
        snapshot = self.view[1] if self.view else None
        here = set(snapshot.by_who) if snapshot else set()
        now = {key: who for who, key in C.renamed(self.edits).items()}       # a renamed player's name in the roster
        for key, e in self.edits.items():
            who = now.get(key, key)
            if e.get('photo') and key not in mine and who in here:
                mine.setdefault(who, {'photo': e['photo']})     # the photo alone, under the name he has now
        for key, e in self.teams.items():
            if key in teams:
                continue
            kept = {k: e[k] for k in ('logo', 'uniforms', 'ice', 'kit') if e.get(k)}
            if kept:
                teams[key] = kept
        return mine, teams

    def _picture_status(self, art, later="", look_teams=0):
        """The status line after a Save, with a word about the player's own pictures and the jerseys and ice of the
        `look_teams` teams he gave them."""
        text, tone = self.status
        if isinstance(art, str):
            text, tone = text + " Your own pictures were not installed: " + art, 'warn'
        elif art or look_teams:
            written, already, failed = art or (0, 0, 0)
            if written or already:
                text += " Your own pictures are in the game now."
            if look_teams:
                text += f" Jerseys and ice of {look_teams} team{'s' if look_teams > 1 else ''} are in the game now."
            if failed:
                text, tone = text + f" {failed} of your pictures could not be made: pick another photo.", 'warn'
        self.set_status(text + later, tone if not later else 'warn')

    def _open_saved(self, folder):
        """After "Save as a new roster" (under the lock): Setup picks the new roster and the team tabs open it, so this
        visit's edits count as saved and the next ones go into it (before, the old roster stayed open and its Save bar said
        "1 not saved yet" for good: a tester, 2026-10-28)."""
        self.session, self.session_teams, self.source = set(), set(), None
        self.name_touched = False
        self.next_note = self.status        # "Saved as ..." stays on the line when the new roster shows
        self.after_busy = lambda: self._rescan(pick=folder)

    def _rescan(self, pick=None):
        """The Update tab lists the rosters again (a new one, a new time); the editor reads the saved one again, or
        `pick` (a roster folder) once Setup has picked it."""
        upd = self.update
        if pick is not None and upd.rpcs3 is not None:      # the new roster is listed once the scan is done
            upd.set_rpcs3(upd.rpcs3.where, quiet=True, then=lambda: (upd.select(pick), self.opened()))
            return
        if upd.rpcs3 is not None:
            upd.set_rpcs3(upd.rpcs3.where, quiet=True)
        self.opened()

    def closing(self):
        """May the window close now? Not while a roster is being saved, and not before the player has answered
        whether edits that are not in the roster yet should be saved first."""
        with self.lock:
            if self.update.quitting or self.close_anyway:
                return True
            if self.busy and self.status[0] == "Saving...":
                self.update.ask("Please wait", ["The Roster editor is saving a roster. Close the window when it is "
                                                "done."], [("OK", 'ok', 'primary')], {})
                return False
            n = len(self.session) + len(self.session_teams)
            if not n or self.view is None or self.busy or getattr(self.slot, 'file', False):
                return True
            what = "1 edit is" if n == 1 else f"{n} edits are"
            self.update.ask(UNSAVED_TITLE, [UNSAVED_LINES[0].format(n=what, them="it" if n == 1 else "them"),
                                            UNSAVED_LINES[1]],
                            [("Save now", 'save', 'primary'), ("Close anyway", 'close', ''), ("Cancel", 'cancel', '')],
                            {'save': self.save, 'close': self._close_now})
            return False

    def _close_now(self):
        with self.lock:
            self.close_anyway = True
        self.host.quit()

    # --- what the page shows ----------------------------------------------------------------------------
    def _uniforms_why(self, snap, team):
        """Why the picked team's jerseys cannot be changed (looks.window_team), or None; kept per roster and team."""
        if snap is None or team is None:
            return "Pick a team first."
        key = (id(snap), team)
        cached = getattr(self, '_why_cache', None)
        if cached is None or cached[0] != key:
            self._why_cache = cached = (key, looks.window_team(snap.R, team)[1])
        return cached[1]

    def snapshot(self):
        with self.lock:
            snap, upd = self.snap, self.update
            slot = self.slot
            in_place = upd.in_place(slot) if slot is not None else False
            from_file = getattr(slot, 'file', False)
            ready = snap is not None and not self.busy
            built = self.view[0] if self.view else None
            team_slot = self.team if isinstance(self.team, int) else None
            uniforms_why = self._uniforms_why(snap, team_slot)
            choices = self.choices()
            modal = self.modal
            if modal is not None and modal.get('kind') == 'edits':
                modal = dict(modal, items=self._edits_view())
            return {
                'busy': self.busy,
                'loaded': snap is not None,
                'roster': {'name': slot.name, 'region': slot.region, 'folder': slot.folder} if slot else None,
                'status': {'text': self.status[0], 'tone': self.status[1]},
                'progress': {'value': 0, 'active': self.busy, 'indeterminate': self.busy},
                'leagues': snap.leagues() if snap else [],
                'league': self.league,
                'teams': [{'id': t, 'name': snap.team_name(t), 'count': len(snap.rosters.get(t, []))}
                          for t in snap.teams_in(self.league)] if snap and self.league else [],
                'team': self.team,
                'team_name': snap.team_name(self.team) if snap and self.team is not None else '',
                'query': self.query,
                'searching': self.found is not None,
                'rows': self.rows if snap else [],
                'selected': self.player.who if self.card_open and self.player is not None else None,
                'card': self._card_view(),
                'choices': {'teams': [[k, v] for k, v in choices.items()], 'countries': COUNTRIES,
                            'positions': list(C.POSITIONS), 'styles': STYLE_CHOICES,
                            'skins': list(faces.SKINS), 'eyes': list(faces.EYES), 'look_rows': LOOK_ROWS},
                'edits_count': len(self.edits) + len(self.teams),
                'unsaved': 0 if from_file else len(self.session) + len(self.session_teams),
                'team_tools': {'team': team_slot is not None and snap is not None,
                               'uniforms': uniforms_why is None, 'uniforms_why': uniforms_why or ''},
                'save': {'mode': S.IN_PLACE if in_place else S.AS_NEW, 'file': ROSTER_FILE if from_file else '',
                         'mode_enabled': ready and slot is not None and not getattr(slot, 'disc', False) and not upd.busy,
                         'name': self.name,
                         'button': {'text': "Save to this roster" if in_place else "Save as new roster",
                                    'enabled': ready and built is not None and not upd.busy and not from_file}},
                'modal': modal,
            }
