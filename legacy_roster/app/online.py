"""The "Play online" tab without a window toolkit (private/Multiplayer.txt; docs/notes/multiplayer.md, S1 results): the player's
online account, the one-press setup, a lobby of two by code, the launch of RPCS3 into the game, and what RPCS3's log says.

Nothing of the player's RPCS3 is changed except through patchinstall (the online entry of the game patch, with the backups
that has) and the roster install (a save of the app's own, "Puck Peak Online ..."; the host's roster is copied into it when
he makes a lobby, the friend's when she joins: pressing Make a lobby / Join is the player's yes, and update_in_place keeps a
backup copy). The roster is the host's: it travels through the lobby server (lobby.py), and both players must have the same
roster CRC and the same game patch before they can be Ready. Online play needs the game patch (owner, 2026-10-25): Set up
online puts it in (after a question) with the online entry. The RPCS3 build is read from its log and told to the friend; a
build older than onlinecfg.MIN_RPCS3 is refused, a different one only gets a note. The game is started with the app's own config
file (onlinecfg.write_config); the player's config files are only read. The lobby calls go to the server (lobby.py)
and may run while RPCS3 runs; copying a roster needs RPCS3 closed.

The pairing in the game (S1): the host presses Create Game Session, the guest Browse Available Game Sessions and Join.
`steps` says which, by role. The tab is a follower of the team list only to know when it shows (`follow` / `hide`).
"""
import datetime
import os
import socket
import struct
import subprocess
import threading
import time
import urllib.parse

from .. import datasource, gamepatch, hud, lobby, onlinecfg, patchinstall, savedata
from ..roster import Roster
from ..stock import StockError
from . import jobs
from . import settings as S
from . import texts as X

SLICE = 'online'
POLL = 2.0                              # seconds between asking the server while a lobby is open
STALL_AFTER = 90                        # seconds signed in, with the session still not made or joined, after which the steps are shown to press by hand
START_GRACE = 180                       # seconds after a launch in which the start entry is left ticked (RPCS3 needs time to appear)
LIST_POLL = 5.0                         # seconds between asking for the public lobbies while the tab shows and none is open
ROSTER_NAME = "Puck Peak Online"
NO_RPCS3 = "Pick RPCS3 in Setup first."
NO_ACCOUNT = ("Make your online account once in RPCS3: Configuration > RPCN > Account > Create account. Pick a name and a "
              "password, type your e-mail, then paste the token from the e-mail. Come back here and press Check again.")
CLOSE_RPCS3 = "Close RPCS3 first: the online setup can only be changed while the game is closed."
CLOSE_TO_COPY = "Close RPCS3 so your friend's roster can be copied."
CLOSE_TO_BRING = "Close RPCS3 so your roster can be copied for the lobby."
PICK_ROSTER = "Pick the roster you want to play with in Setup first."
OWN_ROSTER = ("The game's own roster cannot be shared as it is. Press Update in the Update tab once (it makes a roster of your own, "
              "your game's roster stays as it is), then pick that roster in Setup.")
LOBBY_CLOSED = "Your friend left, so the lobby closed. Make a new one, or join another code."
GAME_DIFFERS = "Plays {theirs}; you have {mine}. Different games may lose step during the match."
GAME_NOTE = "{friend} plays {theirs}, you play {mine}. Different games may lose step during the match: the same region and version is safest."
PATCH_DIFFERS = "Plays with game patch {theirs}; you have {mine}. Update the program to the newest version."
PATCH_HINT = "You and your friend have different game patch versions. Update the program to the newest version, then press Ready."
PATCH_NEEDED = "Online play needs the game patch. Press Set up online."
HIDDEN_KEY = 'online_hidden'           # settings: the player keeps his name off the public leaderboard
OVERLAY_KEY = 'online_overlay'         # settings: partner chat and the result over the game (Windows; default on)
CHAT_LENGTH = 140                       # the server keeps 30 lines of at most 140 characters
CHAT_GAP = 1.0                          # seconds the Send button rests after a line (the server takes one each 0.7 s)
PHRASES = ["Good game", "Rematch?", "Nice one!", "Unlucky", "One sec", "Ready?"]
RANKS_POLL = 30.0                       # seconds between reading my card / matches / the board while the tab shows
WATCH_POLL = 10.0                       # ... while a game started from a lobby runs (matches only; the card when a new one comes)
WATCH_AFTER = 600                       # seconds after RPCS3 closed that a result still waiting is looked for
START_GRACE_RANKS = 60                  # seconds after a launch before "RPCS3 is not running" means the game ended
HISTORY_ROWS = 10
BOARD_ROWS = 10
RANKS_TABS = ('mine', 'stats', 'box', 'board')      # the Ranks card's views: my matches, my stats, a box score, the leaderboard
# The box score's lines: the game's versus stats (CPRT). The names come from the game's own field table (NHL 19 has the same);
# no real match has filled them in the lab yet (idle play sent zeros). A line shows when either side has it.
BOX_LINES = (('Shots', 'SHTS'), ('Hits', 'HITS'), ('Faceoffs won', 'FO'), ('Penalty minutes', 'PIMS'),
             ('Power play', ('PPG', 'PPO')), ('Short-handed goals', 'SHG'), ('Passes', ('PSSC', 'PSSA')),
             ('Time on attack', 'TOA'), ('Blocked shots', 'BS'), ('Breakaways', ('BAG', 'BAO')), ('Penalty shots', ('PSG', 'PSA')))
BOX_EMPTY = "The game sent no stats for this match (a match that ends early sends none)."
BOX_LATER = "Box scores come with the next server update."
BOX_NONE = "The server has no box score for this match."
STATS_NONE = "Your stats show after your first rated match."
PENDING = object()                      # the line a new result is after: not read yet
SHOW_LATER = "You show on the leaderboard again the next time you are in a lobby."
RESULT_WON = "You won. Both reports agree, so it counts."
RESULT_LOST = "You lost. Both reports agree, so it counts."
RESULT_WAITING = "Waiting for {opp}'s report. It counts once both reports agree."
RESULT_LEFT = "{opp} left the game. It counts as your win in an hour, unless their own report says otherwise."
RESULT_DISPUTED = "The two reports do not agree on the score, so this match does not count."
RESULT_DESYNC = "The game lost step between the two PCs (desync), so this match counts for nobody."
RESULT_VOIDED = "This match has no winner, so it counts for nobody."
RESULT_FORFEIT_WON = "{opp} left the game: it counts as your win."
RESULT_FORFEIT_LOST = "You left the game: it counts as a loss."
GUEST_UNPATCHED = "Your friend's roster is for the patched game, and your game is not patched. Patch it in Game patch."
GUEST_PATCHED = ("Your friend's roster is for the game without the patch, and online play needs the patch. Your friend: update "
                 "the roster in the program with the game patch in, then make a new lobby.")
GUEST_RIGHTS = ("Your friend's roster was made for another version of the game patch than yours. Both of you: update the "
                "program, press Patch again in Game patch, then make a new lobby.")
GUEST_INCOMPLETE = "Your game patch is missing a part. Press Patch again in Game patch."
GUEST_STALE = "Your game patch is for another version of the game. Press Patch again in Game patch."
PATCH_ASK = ["Online play needs the game patch: 32 teams and the year 2026. This puts it into RPCS3 (every version of the game "
             "you have) with the online part.",
             "While it is patched, the game shows rosters made without the patch as damaged. Update a roster in the Update tab "
             "to make it fit again.",
             "Unpatch (Game patch tab) puts the game back as it was. RPCS3 must be closed."]
BUILD_OLD = ("Your RPCS3 (build {mine}) is older than online play supports (build {need}). Update it in RPCS3: Help > Check for "
             "Updates, then press Check again.")
BUILD_DIFFERS = "{friend}'s RPCS3 is build {theirs}, yours is build {mine}. If the game drops out, update the older one."
BUILD_UNKNOWN = "The program cannot see your RPCS3 version yet. Start RPCS3 once and press Check again."
LOAD_ROSTER = ("The online roster \"{name}\" loads by itself when the game starts. If you see another roster, load it: "
               "Customize > Save/Load/Delete > Load > Rosters > \"{name}\".")
BY_ITSELF = ("Nothing to press: the game starts, signs in and takes you to Select Teams with your friend. Pick your team and side. "
             "The first start after a game or RPCS3 update can take up to half an hour while RPCS3 prepares the game: wait, it is not stuck.")
STALLED = "Is the game still on a menu? Then press these yourself:"
STEPS_ALL = ("Press X on the welcome screen, if there is one.", "Play > Online > Online Versus Play.",
             "Move to \"Ranked Online Play Now Search\" and press X.")
STEPS_HOST = ("Choose Create Game Session and press X.", "Press X on the settings screen and wait for your friend.")
STEPS_GUEST = ("Choose Browse Available Game Sessions and press X.", "Pick your friend's session and press X to join.")
PROGRESS = {'offline': "Not in the game yet", 'in_game': "In the game", 'signed_in': "Signed in", 'hosting': "Waiting for a friend",
            'browsing': "Looking for the session", 'joined': "Joined", 'playing': "Playing", 'gone': "Left"}
COUNTDOWN = 3


class OnlineController:
    def __init__(self, host, update, poll=POLL, autopoll=True, list_poll=LIST_POLL, make_hud=None):
        self.host, self.update = host, update
        # make_hud(on_hotkey) -> the overlay over the game (hud.Hud); None: the real one, only when the controller polls
        # by itself (tests that do not poll never open windows)
        self.make_hud = make_hud
        self.hud = None
        self._chat_seen = 0             # seq of the newest chat line seen: the overlay shows only lines after it
        self._hud_shown = None          # id of the match whose result card the overlay showed
        self.lock = threading.RLock()
        self.poll_every, self.autopoll, self.list_every = poll, autopoll, list_poll
        self.shown = False
        self.busy = None                # what runs now ("Setting up..."), None when nothing
        self.note = None                # {'text', 'tone'}: the last result
        self.checked = False            # looked at the PC at least once
        self.account = None             # the RPCN name in RPCS3's rpcn.yml
        self.title = None               # the game version the lobby is played with (title id)
        self.state = {}                 # patchinstall.state()[title]
        self.build = None               # the RPCS3 build number from its log (None: not known)
        self.roster = None              # {'name', 'folder', 'crc'} of the installed online roster, None without one
        self.brought = None             # the name of the roster the host brought to his lobby
        self.copying = None             # "Getting your friend's roster...", None when nothing is copied
        self.copy_crc = None            # the host's roster CRC the guest's copy was tried for (not tried again for it)
        self._sent_me = None            # the (patch, game) last sent to the server with update_me
        self.server = None              # True / False / None: the lobby server answered at the last look
        self.lobby = None               # the server's lobby as last seen
        self.code = None                # its code
        self.launched = None            # the code the game was started for
        self.log = None                 # onlinecfg.log_state of the running game's log
        self._tail = None               # onlinecfg.LogTail of this start's log
        self.auto = False               # the game can start by itself into the lobby's search (looked up in refresh)
        self.started_at = 0.0           # time.time() of the launch: only a log written after it says anything about this start
        self.signed_at = None           # time.time() when the log first showed the sign-in of this start
        self.by_itself = False          # the game was started with the online start entry ticked (it is unticked after the boot)
        self.countdown = None
        self._timer = None
        self.public = True              # the next lobby made is listed for everybody (0.65: public unless the host picks private)
        self.open_lobbies = []          # the public lobbies waiting for a friend, as the server listed them
        self.open_error = None          # why the list could not be read (None when it could)
        self._list_timer = None
        self.chat_wait = 0.0            # time.time() until which the Send button rests
        self.ranks_on = None            # True / False / None: the server has the ranks (0.90) / has not / not asked yet
        self.card = None                # my rank card from the server (None: no rated game yet)
        self.history = []               # my matches, newest first
        self.board = None               # the leaderboard as last read
        self.ranks_at = 0.0
        self._ranks_busy = False
        self._ranks_timer = None
        self._card_for = None           # (id, status) of my newest match when the card was read
        self._hide_sent = None          # (name, hidden) last told to the server
        self.watching = False           # a game started from a lobby runs (or just ended): matches are read often
        self.ended = None               # time.time() when RPCS3 closed after that start
        self.baseline = None            # my newest match id before the start (PENDING: not read yet)
        self.result = None              # the history row of the new match, shown until put away
        self.results_seen = set()
        self.ranks_tab = 'mine'         # the Ranks card's view (RANKS_TABS)
        self.box_id = None              # the match whose box score shows
        self.boxes = {}                 # match id -> (its status when read, the box score or None when the server has none)
        self.box_busy = None            # the match id being read
        self.box_on = True              # False: the server has no box scores (before the update that adds /match)

    def changed(self):
        self.host.changed(SLICE)

    # --- the tab shows or rests ----------------------------------------------------------------------------------
    def follow(self, team=None):
        with self.lock:
            self.shown = True
        self.refresh()
        self._arm_list(0.3)
        self._arm_ranks(0.5)

    def hide(self):
        with self.lock:
            self.shown = False
            watching = self.watching
        self._stop_list_timer()
        if not watching:
            self._stop_ranks_timer()

    def roster_changed(self):
        pass

    def closing(self):
        """The window closes: leave an open lobby (best effort) and stop asking the server."""
        self._stop_timer()
        self._stop_list_timer()
        self._stop_ranks_timer()
        self._clear_start()
        self._hud_stop()
        code, who = self.code, self.account
        if code and who:
            try:
                lobby.leave(code, who)
            except lobby.LobbyError:
                pass
        return True

    # --- what the PC and the server say ---------------------------------------------------------------------------
    def rpcs3(self):
        rpcs3 = getattr(self.update, 'rpcs3', None)
        return None if rpcs3 is None or getattr(rpcs3, 'plain', False) or getattr(rpcs3, 'native', False) else rpcs3

    def no_rpcs3(self):
        """What the tab says when no RPCS3 is picked (the port has no online play)."""
        return X.ONLINE_NATIVE if getattr(getattr(self.update, 'rpcs3', None), 'native', False) else NO_RPCS3

    def refresh(self):
        """Look again: the account, the patch, the online roster and the server (in the background)."""
        with self.lock:
            if self.busy:
                return
            rpcs3 = self.rpcs3()
            versions = list(getattr(self.update, 'versions', []) or [])
            self.busy = "Looking..."
        self.changed()

        def work():
            self._clear_start()
            found = {'account': None, 'title': None, 'state': {}, 'roster': None, 'server': None, 'build': None, 'auto': False}
            if rpcs3 is None:
                return found
            found['account'] = onlinecfg.account(rpcs3)
            found['build'] = onlinecfg.rpcs3_build(rpcs3)
            states = patchinstall.state(rpcs3)
            titles = [t for t in versions if t in states] or [t for t in states if rpcs3.game_disc(t)]
            ready = [t for t in titles if states[t]['online']]
            title = (ready or titles or [None])[0]
            found['title'], found['state'] = title, states.get(title, {})
            if title:
                found['roster'] = self._installed(rpcs3, title)
                found['auto'] = patchinstall.auto_start(rpcs3, title)
            found['server'] = self._server_up()
            return found

        def done(found):
            with self.lock:
                self.busy = None
                self.checked = True
                for key, value in found.items():
                    setattr(self, key, value)
            self.changed()
            self._sync_me()

        def failed(message):
            with self.lock:
                self.busy = None
                self.checked = True
                self.note = {'text': message, 'tone': 'bad'}
            self.changed()

        jobs.run(work, done, failed, expected=(OSError, patchinstall.PatchError))

    def _installed(self, rpcs3, title):
        """The online roster in the save folder: {'name', 'folder', 'crc', 'patch_roster': made for the game patch, 'rights': the
        bits of its player rights} (None for what cannot be read), or None without one."""
        for slot in savedata.list_rosters(rpcs3.savedata):
            if slot.title_id == title and slot.name.startswith(ROSTER_NAME):
                found = {'name': slot.name, 'folder': slot.folder, 'crc': None, 'patch_roster': None, 'rights': None}
                try:
                    with open(slot.sys_data, 'rb') as f:
                        data = f.read()
                    found['crc'] = onlinecfg.roster_crc(data)
                    R = Roster(data)
                    found['patch_roster'], found['rights'] = gamepatch.is_patch_roster(R), R.P.field(gamepatch.RIGHTS).bits
                except (OSError, ValueError, KeyError, IndexError, struct.error, AttributeError):
                    pass
                return found
        return None

    @staticmethod
    def _server_up():
        """Does the lobby server answer (any answer, also "no such lobby", counts)?"""
        try:
            lobby.status('AAAAAA', 'check')
        except lobby.Unreachable:
            return False
        except lobby.LobbyError:
            return True
        return True

    # --- the setup -------------------------------------------------------------------------------------------------
    def marks(self):
        """The player's own marks: the online entry is on, the game is patched, both ('ready': a lobby can be made or joined).
        The roster and the patch version are the lobby's business."""
        online = bool(self.state.get('online') and not self.state.get('stale'))
        patched = bool(self.state.get('patched') and not self.state.get('stale'))
        return {'online': online, 'patched': patched, 'ready': online and patched,
                'game': 'open' if savedata.running_rpcs3() else 'closed'}

    def build_problem(self):
        """Why this RPCS3 is too old for online play (None when it is fine or not known)."""
        if self.build is not None and self.build < onlinecfg.MIN_RPCS3:
            return BUILD_OLD.format(mine=self.build, need=onlinecfg.MIN_RPCS3)
        return None

    def build_note(self):
        """{'text', 'tone'} about the RPCS3 builds of the two players (None: nothing to say)."""
        if self.build is None:
            return {'text': BUILD_UNKNOWN, 'tone': 'warn'}
        friend = next((m for m in (self.lobby or {}).get('members', []) if m['name'] != self.account), None)
        theirs = str((friend or {}).get('rpcs3') or '')
        if theirs and theirs != str(self.build):
            return {'text': BUILD_DIFFERS.format(friend=friend['name'], theirs=theirs, mine=self.build), 'tone': 'warn'}
        return None

    def game_note(self):
        """{'text', 'tone'} when the two players run another region or game version (a warning: they can still play)."""
        friend = next((m for m in (self.lobby or {}).get('members', []) if m['name'] != self.account), None)
        theirs, mine = str((friend or {}).get('version') or ''), self.game_word()
        if theirs and theirs != mine:
            return {'text': GAME_NOTE.format(friend=friend['name'], theirs=theirs, mine=mine), 'tone': 'warn'}
        return None

    def guest_problem(self):
        """Why this guest's game cannot load the host's roster copied to this PC, or None (also for the host, and before the copy
        is here). The lobby only compares patch versions; this compares the roster itself with the game as RPCS3 has it now, so a
        guest who patches or unpatches in the lobby is checked again. Stricter than UpdateController.misfit: player rights that
        cannot be read do not pass."""
        me, theirs, mine = self._member(), (self.lobby or {}).get('roster'), self.roster
        if me is None or me.get('role') != 'guest' or not theirs or not mine \
                or str(mine.get('crc') or '').lower() != str(theirs.get('crc') or '').lower() or mine.get('patch_roster') is None:
            return None
        if self.state.get('stale'):
            return GUEST_STALE
        patched, made = bool(self.state.get('patched')), mine['patch_roster']
        if made and not patched:
            return GUEST_UNPATCHED
        if patched and not made:
            return GUEST_PATCHED
        if made:
            game, own = self.state.get('rights'), mine.get('rights')
            if not game:
                return GUEST_INCOMPLETE
            if game != own:
                return GUEST_RIGHTS
        return None

    def patch_word(self):
        """The patch as the lobby compares it: the patch version, or "none" without the 32-team patch."""
        return (self.state.get('version') or 'patched') if self.state.get('patched') else 'none'

    def setup(self):
        """The "Set up online" button: the game patch (after a question) with the online entry, and the app's config. The
        roster comes with the lobby."""
        with self.lock:
            rpcs3 = self.rpcs3()
            if self.busy or rpcs3 is None:
                return
            if savedata.running_rpcs3():
                self.note = {'text': CLOSE_RPCS3, 'tone': 'bad'}
                self.changed()
                return
            if not self.account:
                self.note = {'text': NO_ACCOUNT, 'tone': 'bad'}
                self.changed()
                return
            patch = not self.marks()['patched']
        if patch:
            self.update.ask("Patch the game for online play?", PATCH_ASK,
                            [("Patch the game", 'yes', 'primary'), ("Cancel", 'no', 'plain')], {'yes': self._setup})
            return
        self._setup()

    def _setup(self):
        with self.lock:
            rpcs3 = self.rpcs3()
            if self.busy or rpcs3 is None:
                return
            titles, title = list(self.update.versions), self.title or (self.update.versions or [None])[0]
            patch = not self.marks()['patched']
            intro, login = getattr(self.update, 'skip_intro', True), getattr(self.update, 'no_login', False)
            self.busy = "Setting up online play..." if not patch else "Patching the game and setting up online play..."
            self.note = None
        self.changed()

        def work():
            if patch:       # no question about the picked roster afterwards: the online save holds the host's roster
                patchinstall.install_patch(rpcs3, titles, intro=intro, login=login)
            patchinstall.set_online(rpcs3, titles, True)
            patchinstall.set_switches(rpcs3, titles, True, login)       # the intro skip: the lobby's start needs the quick boot
            onlinecfg.write_config(rpcs3, title, self._address())
            return True

        def done(_):
            with self.lock:
                self.busy = None
                self.note = {'text': "Ready to play online.", 'tone': 'good'}
            rescan = getattr(self.update, 'set_rpcs3', None)
            if patch and rescan:        # the Update tab marks the rosters the patched game cannot load
                rescan(rpcs3.where, quiet=True)
            self.refresh()

        def failed(message):
            with self.lock:
                self.busy = None
                self.note = {'text': message, 'tone': 'bad'}
            self.changed()

        jobs.run(work, done, failed, expected=(patchinstall.PatchError, datasource.Offline, StockError, OSError, ValueError))

    def _put_roster(self, rpcs3, title, data):
        """Install `data` as the online roster of `title`: a new save, or in place over the one that is there (backup first)."""
        have = self.roster
        slots = savedata.list_rosters(rpcs3.savedata)
        if have:
            slot = next(s for s in slots if s.folder == have['folder'])
            savedata.update_in_place(rpcs3.savedata, slot, data, name=slot.name, expected=None)
            return
        source = next((s for s in slots if s.title_id == title), None) or next(iter(slots), None)
        if source is None:
            raise OSError("Save a roster in the game once first, so there is a save to copy the pictures from.")
        savedata.install(rpcs3.savedata, source, data, f"{ROSTER_NAME} {datetime.date.today():%Y-%m-%d}", title_id=title)

    @staticmethod
    def _address():
        """The IP address of the game server now (RPCS3's IP swap list takes an address, not a name)."""
        return socket.gethostbyname(urllib.parse.urlsplit(lobby.api_url()).hostname)

    # --- the lobby -------------------------------------------------------------------------------------------------
    def _me(self):
        """(name, roster CRC, patch, game version, RPCS3 build) as the lobby wants them from a guest."""
        return (self.account, (self.roster or {}).get('crc') or '', self.patch_word(), self.game_word(),
                self._build_text())

    def game_word(self):
        """The game as the lobby compares it: the region and the version ("EU 01.00", "NA 01.01"). Two games of another region or
        version did not stay in step in the lab (a 1.01 against a 1.00 never finished loading, a NA against an EU one lost step
        in the first period), so the server lets only the same word play together."""
        region = 'NA' if str(self.title or '').startswith('BLUS') else 'EU'
        return f"{region} {self.state.get('game') or '01.00'}"

    def _build_text(self):
        return '' if self.build is None else str(self.build)

    def bring(self):
        """(the roster the host would bring, why he cannot bring it): the one picked in Setup."""
        slot = getattr(self.update, 'selected_slot', lambda: None)()
        if slot is None:
            return None, PICK_ROSTER
        if getattr(slot, 'disc', False):
            return slot.name, OWN_ROSTER
        why = (getattr(self.update, 'usable', {}) or {}).get(slot.folder) or self.update.misfit(slot)
        return slot.name, (str(why) if why else None)

    def set_public(self, on):
        with self.lock:
            self.public = bool(on)
        self.changed()

    def create(self, public=None):
        """Make a lobby with the roster picked in Setup: it is copied to the app's own online save, the lobby is opened with its
        CRC and the roster goes up to the server for the friend. A public lobby is also in everybody's list."""
        with self.lock:
            if public is not None:
                self.public = bool(public)
            rpcs3 = self.rpcs3()
            if self.busy or rpcs3 is None or not self.account or self.code:
                return
            if not self.marks()['ready']:
                self.note = {'text': PATCH_NEEDED if self.marks()['online'] else "Set up online first.", 'tone': 'bad'}
                self.changed()
                return
            old = self.build_problem()
            if old:
                self.note = {'text': old, 'tone': 'bad'}
                self.changed()
                return
            name, why = self.bring()
            slot = self.update.selected_slot()
            if why:
                self.note = {'text': why, 'tone': 'bad'}
                self.changed()
                return
            if savedata.running_rpcs3():
                self.note = {'text': CLOSE_TO_BRING, 'tone': 'bad'}
                self.changed()
                return
            title, account, patch = self.title, self.account, self.patch_word()
            game, listed, build = self.game_word(), self.public, self._build_text()
            same = bool(self.roster and slot.folder == self.roster['folder'])
            self.busy = "Sending your roster..."
            self.note = None
        self.changed()

        def work():
            with open(slot.sys_data, 'rb') as f:
                data = f.read()
            crc = onlinecfg.roster_crc(data)
            if not same:
                self._put_roster(rpcs3, title, data)
            installed = self._installed(rpcs3, title)
            answer = lobby.create(account, crc, patch, game, public=listed, roster_name=name, rpcs3=build)
            try:
                return lobby.put_roster(answer['code'], account, data), installed
            except lobby.LobbyError:
                try:
                    lobby.leave(answer['code'], account)
                except lobby.LobbyError:
                    pass
                raise

        def done(result):
            answer, installed = result
            with self.lock:
                self.busy = None
                self.roster, self.brought, self.copy_crc = installed, name, None
            self._take(answer)

        def failed(message):
            with self.lock:
                self.busy = None
                self.note = {'text': message, 'tone': 'bad'}
            self.changed()

        jobs.run(work, done, failed, expected=(lobby.LobbyError, savedata.RosterFull, savedata.InPlaceError, OSError, ValueError))

    def join(self, text):
        code = lobby.clean_code(text)
        if code is None:
            with self.lock:
                self.note = {'text': "A lobby code is six letters, like KDMQRS.", 'tone': 'bad'}
            self.changed()
            return
        self._lobby_call(lambda who: lobby.join(code, *who))

    def ready(self, on=True):
        with self.lock:
            code, name = self.code, self.account
            problem = self.guest_problem() if on else None
            if problem:
                self.note = {'text': problem, 'tone': 'bad'}
        if problem:
            self.changed()
            return
        if code:
            self._lobby_call(lambda who: lobby.ready(code, name, on))

    def leave(self):
        with self.lock:
            code, name = self.code, self.account
            self.lobby = self.code = self.launched = self.log = self.countdown = None
            self.brought = self.copy_crc = self._sent_me = None
        self._stop_timer()
        self._clear_start()
        self.changed()
        self._arm_list(0.3)
        if code and name:
            jobs.run(lambda: lobby.leave(code, name), None, None, expected=(lobby.LobbyError,))

    def _lobby_call(self, call):
        with self.lock:
            if self.busy or not self.account:
                return
            if not self.marks()['ready']:
                self.note = {'text': PATCH_NEEDED if self.marks()['online'] else "Set up online first.", 'tone': 'bad'}
                self.changed()
                return
            old = self.build_problem()
            if old:
                self.note = {'text': old, 'tone': 'bad'}
                self.changed()
                return
            who = self._me()
            self.busy = "Asking the server..."
        self.changed()

        def done(answer):
            with self.lock:
                self.busy = None
                self.note = None
            self._take(answer)

        def failed(message):
            with self.lock:
                self.busy = None
                self.note = {'text': message, 'tone': 'bad'}
            self.changed()

        jobs.run(lambda: call(who), done, failed, expected=(lobby.LobbyError,))

    def _take(self, answer):
        """The server's lobby `answer`: keep it, start the game when it says "starting", get the host's roster when this
        PC lacks it, tell the server about a changed patch, ask again soon."""
        with self.lock:
            if answer.get('state') == 'expired':
                self.lobby = self.code = self.launched = self.brought = None
                self.note = {'text': LOBBY_CLOSED, 'tone': 'bad'}
                self._arm_list(0.3)
            else:
                self.lobby, self.code = answer, answer.get('code')
            self.server = True
        self.changed()
        self._hud_chat()
        if answer.get('state') == 'starting':
            self._start_game()
        if self.watching and time.time() - self.ranks_at >= WATCH_POLL:
            self.refresh_ranks(board=False)
            self._arm_ranks()
        if self.hidden() is False and self._hide_sent is None and self.card is not None and self.card.get('hidden'):
            self._send_hidden()                 # showing again needs the lobby's token: now there is one
        self._sync_roster()
        self._sync_me()
        self._arm()

    def _member(self):
        """This player's member entry of the lobby as last seen (None outside a lobby)."""
        return next((m for m in (self.lobby or {}).get('members', []) if m['name'] == self.account), None)

    def _sync_roster(self):
        """A guest whose online roster is not the host's: download it, check it, install it, tell the server."""
        with self.lock:
            me, roster = self._member(), (self.lobby or {}).get('roster')
            if me is None or me['role'] != 'guest' or not roster or self.lobby.get('state') not in ('open', 'starting'):
                return
            want = str(roster['crc']).lower()
            if str((self.roster or {}).get('crc') or '').lower() == want or self.copying or self.copy_crc == want:
                return
            rpcs3, title, code, name = self.rpcs3(), self.title, self.code, self.account
            if rpcs3 is None or title is None:
                return
            if savedata.running_rpcs3():
                self.note = {'text': CLOSE_TO_COPY, 'tone': 'bad'}
                self.changed()
                return
            self.copying, self.copy_crc, self.note = "Getting your friend's roster...", want, None
            patch, game, build = self.patch_word(), self.game_word(), self._build_text()
        self.changed()

        def work():
            data = lobby.get_roster(code, name)
            try:
                crc = onlinecfg.roster_check(data)
            except ValueError as err:
                raise ValueError(f"The roster your friend sent is not a roster the game can read ({err}). It was not used.") from err
            if crc.lower() != want:
                raise ValueError("The roster did not arrive correctly. Leave the lobby and join again.")
            self._put_roster(rpcs3, title, data)
            return lobby.update_me(code, name, crc, patch, game, build), self._installed(rpcs3, title)

        def done(result):
            answer, installed = result
            with self.lock:
                self.copying, self.roster = None, installed
            self._take(answer)

        def failed(message):
            with self.lock:
                self.copying = None
                self.note = {'text': message, 'tone': 'bad'}
            self.changed()

        jobs.run(work, done, failed, expected=(lobby.LobbyError, savedata.RosterFull, savedata.InPlaceError, OSError, ValueError))

    def _sync_me(self):
        """The patch changed since the server last heard (the player patched or unpatched): tell it, so the lobby compares anew."""
        with self.lock:
            me = self._member()
            if me is None or self.busy or self.copying or self.lobby.get('state') not in ('open', 'starting'):
                return
            mine = (self.patch_word(), self.game_word(), self._build_text())
            if (me.get('patch'), me.get('version'), me.get('rpcs3') or '') == mine or self._sent_me == mine:
                return
            self._sent_me = mine
            code, name, crc = self.code, self.account, (self.roster or {}).get('crc') or ''

        def failed(message):
            with self.lock:
                self._sent_me = None
                self.note = {'text': message, 'tone': 'bad'}
            self.changed()

        jobs.run(lambda: lobby.update_me(code, name, crc, *mine), self._take, failed, expected=(lobby.LobbyError,))

    def poll_once(self):
        """Ask the server about the open lobby (and read the game's log): called every POLL seconds while a lobby is open."""
        with self.lock:
            code, name = self.code, self.account
            launched = self.launched
        if not code:
            return
        try:
            self._take(lobby.status(code, name))
        except lobby.Unreachable:
            with self.lock:
                self.server = False
            self.changed()
            self._arm()
        except lobby.LobbyError as err:
            with self.lock:
                self.lobby = self.code = None
                self.note = {'text': str(err), 'tone': 'bad'}
            self.changed()
            self._arm_list(0.3)
        if launched:
            self._read_log()

    def _arm(self):
        if not self.autopoll:
            return
        with self.lock:
            if not self.code or self._timer is not None:
                return
            self._timer = threading.Timer(self.poll_every, self._tick)
            self._timer.daemon = True
            self._timer.start()

    def _tick(self):
        with self.lock:
            self._timer = None
        self.poll_once()

    # --- the public lobbies ---------------------------------------------------------------------------------------
    def list_once(self):
        """Ask the server for the public lobbies (only where a lobby could be joined now: the tab shows, nothing is open)."""
        with self.lock:
            if not self.shown or self.code or self.busy or self.view() != 'ready':
                return
        try:
            found = lobby.lobbies()
            error = None
        except lobby.Unreachable:
            found, error = None, "Puck Peak's online server is not reachable right now."
        except lobby.LobbyError as err:
            found, error = None, str(err)
        with self.lock:
            if found is not None:
                self.open_lobbies = found
            self.open_error = error
        self.changed()

    def refresh_list(self):
        """The Refresh button: ask now, in the background."""
        jobs.run(self.list_once, None, None, expected=())

    def _arm_list(self, delay=None):
        if not self.autopoll:
            return
        with self.lock:
            if not self.shown or self._list_timer is not None:
                return
            self._list_timer = threading.Timer(self.list_every if delay is None else delay, self._list_tick)
            self._list_timer.daemon = True
            self._list_timer.start()

    def _list_tick(self):
        with self.lock:
            self._list_timer = None
        self.list_once()
        self._arm_list()

    def _stop_list_timer(self):
        with self.lock:
            timer, self._list_timer = self._list_timer, None
        if timer is not None:
            timer.cancel()

    def rows(self):
        """The public lobbies as the tab lists them: each with `joinable` and, when it cannot be joined, `why` (another game patch
        version: update the program; another region or game version)."""
        mine = self.patch_word()
        out = []
        for row in self.open_lobbies:
            item = dict(row)
            item['joinable'], item['why'] = True, None
            if row.get('patch') and row['patch'] != mine:
                item['joinable'] = False
                item['why'] = PATCH_DIFFERS.format(theirs=row['patch'], mine=mine)
            elif row.get('version') and row['version'] != self.game_word():      # a warning only: the lobby can be joined
                item['warn'] = GAME_DIFFERS.format(theirs=row['version'], mine=self.game_word())
            out.append(item)
        return out

    def _stop_timer(self):
        with self.lock:
            timer, self._timer = self._timer, None
        if timer is not None:
            timer.cancel()


    # --- chat, ranks, my matches, the result of a match (0.90; a server from before 0.90 has none: the cards hide) -------------
    def say(self, text):
        """One chat line to the lobby (a phrase button or the box). A second line within a moment only waits: the Send button rests."""
        text = ' '.join(str(text or '').split())[:CHAT_LENGTH]
        with self.lock:
            code, name = self.code, self.account
            if not code or not name or not text or time.time() < self.chat_wait or self.chat() is None:
                return
            self.chat_wait = time.time() + CHAT_GAP
        self.changed()

        def failed(message, err=None):
            with self.lock:
                if not (err is not None and (err.code == 'slow_down' or lobby.missing(err))):
                    self.note = {'text': message, 'tone': 'bad'}
            self.changed()

        def work():
            try:
                return lobby.say(code, name, text)
            except lobby.LobbyError as err:
                failed(str(err), err)
                return None

        jobs.run(work, lambda answer: answer and self._take(answer), failed, expected=(lobby.LobbyError,))

    def chat(self):
        """The lobby's chat as the tab shows it: None when the server keeps none (before 0.90), else the lines with `mine`."""
        if not self.lobby or 'chat' not in self.lobby:
            return None
        return [dict(line, mine=line.get('name') == self.account) for line in self.lobby.get('chat') or []]

    def hidden(self):
        settings = getattr(self.update, 'settings', None)
        return bool(settings.get(HIDDEN_KEY)) if isinstance(settings, dict) else False

    def set_hidden(self, on):
        """The "Show me on the leaderboard" switch (off = hidden): kept in settings, told to the server. Showing again needs this
        player's lobby token (the server's rule: a stranger cannot put anyone back), so it waits for the next lobby."""
        on, settings = bool(on), getattr(self.update, 'settings', None)
        if isinstance(settings, dict):
            settings[HIDDEN_KEY] = on
            S.save(settings)
        with self.lock:
            self._hide_sent = None
        self.changed()
        self._send_hidden()

    def _send_hidden(self):
        with self.lock:
            name, want = self.account, self.hidden()
            if not name or self.ranks_on is False or self._hide_sent == (name, want):
                return
            if not want and self.card is not None and not self.card.get('hidden'):
                return                                      # shown already: nothing to tell
            self._hide_sent = (name, want)

        def work():
            try:
                lobby.hide(name, want)
            except lobby.LobbyError as err:
                with self.lock:
                    if lobby.missing(err) and not isinstance(err, lobby.Unreachable):
                        self.ranks_on = False
                    elif err.code == 'not_member':
                        self.note = {'text': SHOW_LATER, 'tone': 'warn'}
                    self._hide_sent = None                  # not done: tried again at the next look (in a lobby for showing)
                self.changed()
                return False
            return True

        jobs.run(work, lambda ok: ok and self.refresh_ranks(), None, expected=(lobby.LobbyError,))

    def refresh_ranks(self, board=None):
        """Ask the server for my card and matches (and the board while the tab shows), in the background, quietly: a server without
        the routes turns the cards off, any other failure keeps what was shown."""
        with self.lock:
            name = self.account
            if not name or self._ranks_busy:
                return
            board = self.shown and not self.watching if board is None else board
            self._ranks_busy, self.ranks_at = True, time.time()

        def work():
            found = {}
            try:
                try:
                    found['history'] = lobby.history(name, HISTORY_ROWS)
                except lobby.LobbyError as err:
                    if err.code != 'unknown':
                        raise
                    found['history'] = []
                newest = (found['history'] or [{}])[0]
                if not self.watching or self._card_for != (newest.get('id'), newest.get('status')) or self.card is None:
                    try:
                        found['card'] = lobby.card(name)
                    except lobby.LobbyError as err:
                        if err.code != 'unknown':
                            raise
                        found['card'] = None
                    found['card_for'] = (newest.get('id'), newest.get('status'))
                if board:
                    found['board'] = lobby.board()
            except lobby.LobbyError as err:
                found['error'] = err
            return found

        def done(found):
            with self.lock:
                self._ranks_busy = False
                err = found.get('error')
                if err is not None:
                    if lobby.missing(err) and not isinstance(err, lobby.Unreachable):
                        self.ranks_on = False
                else:
                    self.ranks_on = True
                    self.history = found['history']
                    if 'card' in found:
                        self.card, self._card_for = found['card'], found['card_for']
                    if 'board' in found:
                        self.board = found['board']
                    self._see_result()
            self.changed()
            if err is None and self.ranks_tab == 'box':
                self._read_box()                        # a match that was waiting may have its other report now
            if err is None and self.hidden() and self.card is not None and not self.card.get('hidden'):
                self._send_hidden()

        def failed(message):
            with self.lock:
                self._ranks_busy = False

        jobs.run(work, done, failed, expected=(lobby.LobbyError,))

    def _see_result(self):
        """(lock held) A new match of mine after the launch: show its result until it is put away (also while it waits for the
        other report: it changes as the server hears more). The first history read after the launch is the line it is after."""
        if not self.watching:
            return
        newest = (self.history or [None])[0]
        if self.baseline is PENDING:
            self.baseline = newest['id'] if newest else None
            return
        if newest and newest['id'] != self.baseline and newest['id'] not in self.results_seen:
            self.result = newest
            self._hud_card()

    def result_view(self):
        """The result window's words and numbers (None when there is nothing to show)."""
        row = self.result
        if not row:
            return None
        card, delta, opp = self.card or {}, row.get('delta'), row.get('opponent') or 'Your friend'
        status = row.get('status')
        out = {'id': row['id'], 'status': status, 'opponent': opp, 'team': row.get('team') or '', 'opp_team': row.get('opp_team') or '',
               'for': row.get('for'), 'against': row.get('against'), 'result': row.get('result'), 'delta': delta,
               'rating': None, 'before': None, 'tier': card.get('tier'), 'next_tier': card.get('next_tier'),
               'next_at': card.get('next_at'), 'placing': card.get('placing')}
        if delta is not None and card.get('rating') is not None:
            out['rating'], out['before'] = card['rating'], card['rating'] - delta
        if status == 'waiting':
            out['line'] = RESULT_LEFT.format(opp=opp) if row.get('why') == 'left' else RESULT_WAITING.format(opp=opp)
        elif status == 'disputed':
            out['line'] = RESULT_DISPUTED
        elif status == 'voided':
            out['line'] = RESULT_DESYNC if row.get('why') == 'desync' else RESULT_VOIDED
        elif status == 'forfeit':
            out['line'] = RESULT_FORFEIT_WON.format(opp=opp) if row.get('result') == 'W' else RESULT_FORFEIT_LOST
        else:
            out['line'] = RESULT_WON if row.get('result') == 'W' else RESULT_LOST
        return out

    def result_seen(self):
        with self.lock:
            if self.result:
                self.results_seen.add(self.result['id'])
            self.result = None
        self.changed()

    def set_ranks_tab(self, tab):
        with self.lock:
            self.ranks_tab = tab if tab in RANKS_TABS else 'mine'
            board = self.ranks_tab == 'board' and self.board is None
        self.changed()
        if board:
            self.refresh_ranks(board=True)
        if self.ranks_tab == 'box':
            self._read_box()

    def open_box(self, mid):
        """The box score of match `mid` (a row of My matches pressed, or the arrows of the Box score view)."""
        with self.lock:
            self.ranks_tab, self.box_id = 'box', mid
        self.changed()
        self._read_box()

    def _read_box(self):
        """Read the box score that shows, once per status of its match (a waiting match is read again when the other report came)."""
        with self.lock:
            mid = self.box_id = self._box_match()
            row = next((r for r in self.history if r['id'] == mid), None)
            status = row.get('status') if row else None
            if not mid or not self.box_on or self.box_busy == mid or (mid in self.boxes and self.boxes[mid][0] == status):
                return
            self.box_busy = mid

        def work():
            try:
                return {'box': lobby.match(mid)}
            except lobby.LobbyError as err:
                return {'error': err}

        def done(found):
            with self.lock:
                self.box_busy = None
                err = found.get('error')
                if err is None:
                    self.boxes[mid] = (status, found['box'])
                elif getattr(err, 'code', None) == 'unknown':
                    self.boxes[mid] = (status, None)
                elif lobby.missing(err) and not isinstance(err, lobby.Unreachable):
                    self.box_on = False
            self.changed()

        def failed(message):
            with self.lock:
                self.box_busy = None
            self.changed()

        jobs.run(work, done, failed, expected=(lobby.LobbyError,))

    def open_board(self):
        """The leaderboard page in the browser (the server's /board)."""
        url = lobby.api_url()
        url = url[:-4] if url.endswith('/api') else url
        self.host.open_url(url + '/board')

    def _ranks_tick(self):
        with self.lock:
            self._ranks_timer = None
            watching = self.watching
        if watching:
            self._watch_game()
        self.refresh_ranks()
        self._arm_ranks()

    def _watch_game(self):
        """While a game of a lobby runs: RPCS3 closed (after START_GRACE) ends it; the watch ends once the result is final or
        WATCH_AFTER seconds after the end."""
        with self.lock:
            if self.ended is None and time.time() - self.started_at > START_GRACE_RANKS and not savedata.running_rpcs3():
                self.ended = time.time()
            final = self.result and self.result.get('status') not in ('waiting',)
            if self.ended and (final or time.time() - self.ended > WATCH_AFTER):
                self.watching = False
            stop = not self.watching
        if stop:
            self._hud_stop()

    def _arm_ranks(self, delay=None):
        """The ranks are read every RANKS_POLL seconds while the tab shows, every WATCH_POLL while a game of a lobby runs."""
        if not self.autopoll:
            return
        with self.lock:
            if self._ranks_timer is not None or not (self.shown or self.watching) or self.ranks_on is False:
                return
            wait = delay if delay is not None else (WATCH_POLL if self.watching else RANKS_POLL)
            self._ranks_timer = threading.Timer(wait, self._ranks_tick)
            self._ranks_timer.daemon = True
            self._ranks_timer.start()

    def _stop_ranks_timer(self):
        with self.lock:
            timer, self._ranks_timer = self._ranks_timer, None
        if timer is not None:
            timer.cancel()

    def ranks_view(self):
        """My card, my matches and the board as the tab shows them (None: the server has no ranks, or nothing read yet)."""
        if not self.ranks_on:
            return None
        board = self.board or {}
        rows = board.get('players') or []
        me = next((r for r in rows if r.get('name') == self.account), None)
        return {'card': self.card, 'history': self.history or [], 'top': rows[:BOARD_ROWS],
                'me': me if me and me not in rows[:BOARD_ROWS] else None, 'highlights': board.get('highlights') or [],
                'placement': board.get('placement') or 5, 'hidden': self.hidden(), 'tab': self.ranks_tab,
                'stats': stats_view(self.card), 'box': self.box_view()}

    def _box_match(self):
        """The match the Box score shows: the one picked while it is among my matches, else the newest."""
        ids = [r['id'] for r in self.history or []]
        return self.box_id if self.box_id in ids else (ids[0] if ids else None)

    def box_view(self):
        """The Box score view: the match picked among my matches, its two sides (mine first) and its lines."""
        if not self.box_on:
            return {'on': False, 'note': BOX_LATER}
        ids = [r['id'] for r in self.history]
        if not ids:
            return {'on': True, 'id': None, 'note': "No matches yet."}
        mid = self._box_match()
        k = ids.index(mid)
        row = self.history[k]
        at = datetime.datetime.fromtimestamp(row['at']).strftime('%d %b, %H:%M') if row.get('at') else ''
        out = {'on': True, 'id': mid, 'title': f"vs {row.get('opponent') or 'your friend'}" + (f" · {at}" if at else ''),
               'newer': ids[k - 1] if k > 0 else None, 'older': ids[k + 1] if k + 1 < len(ids) else None,
               'loading': mid not in self.boxes, 'sides': None, 'rows': [], 'note': None}
        box = self.boxes.get(mid, (None, None))[1]
        if mid in self.boxes and not box:
            out['note'] = BOX_NONE
        if not box or len(box.get('sides') or []) != 2:
            return out
        sides = box['sides']
        mine = next((n for n, s in enumerate(sides) if (s.get('name') or '').lower() == (self.account or '').lower()), None)
        if mine is None:                                # I am hidden: the side that is not the opponent
            mine = next((n for n, s in enumerate(sides) if s.get('name') != row.get('opponent')), 0)
        me, them = sides[mine], sides[1 - mine]
        out['sides'] = [{'name': s.get('name') or '', 'team': s.get('team') or '', 'score': s.get('score')} for s in (me, them)]
        out['rows'] = box_lines(me.get('stats') or {}, them.get('stats') or {})
        if not out['rows']:
            out['note'] = BOX_EMPTY
        return out

    # --- the overlay over the game (Windows; legacy_roster/hud) -------------------------------------------------------------
    def overlay(self):
        """Partner chat and the result card over the game: the player's switch (default on), on Windows only."""
        settings = getattr(self.update, 'settings', None)
        on = settings.get(OVERLAY_KEY, True) if isinstance(settings, dict) else True
        return bool(on) and hud.available()

    def set_overlay(self, on):
        """The "Show chat and results over the game" switch: kept in settings; a game running now gets or loses it at once."""
        settings = getattr(self.update, 'settings', None)
        if isinstance(settings, dict):
            settings[OVERLAY_KEY] = bool(on)
            S.save(settings)
        if not on:
            self._hud_stop()
        elif self.watching and not self.ended:
            self._hud_start()
        self.changed()

    def _hud_start(self):
        """The overlay for the game just started (its chat begins after the lines already read)."""
        with self.lock:
            if self.hud is not None or not self.overlay():
                return
            factory = self.make_hud or (self._real_hud if self.autopoll else None)
            if factory is None:
                return
            self.hud = factory(self._hotkey)
            self._hud_shown = None
            started = self.hud
        started.start()

    @staticmethod
    def _real_hud(on_hotkey):
        return hud.Hud(hud.emulator_rect, on_hotkey=on_hotkey, hotkeys=hud.PHRASE_KEYS)

    def _hud_stop(self):
        with self.lock:
            gone, self.hud = self.hud, None
        if gone is not None:
            gone.stop()

    def _hotkey(self, index):
        """Ctrl+Shift+F1..F6 in the game: the six phrases, in the order of the tab's buttons."""
        if 0 <= index < len(PHRASES):
            self.say(PHRASES[index])

    def _hud_chat(self):
        """The friend's new chat lines go over the game (mine stay in the tab)."""
        with self.lock:
            lines = (self.lobby or {}).get('chat') or []
            new = [line for line in lines if line.get('seq', 0) > self._chat_seen]
            if lines:
                self._chat_seen = max([self._chat_seen] + [line.get('seq', 0) for line in lines])
            shown = self.hud
            me = self.account
        if shown is None:
            return
        for line in new:
            if line.get('name') != me and line.get('text'):
                shown.chat(line.get('name') or 'Friend', line['text'])

    def _hud_card(self):
        """(lock held) The result card over the game, once, when the new match is rated (a match that waits for the other
        report, or counts for nothing, stays in the tab's result window)."""
        row = self.result
        if self.hud is None or not row or row['id'] == self._hud_shown or row.get('delta') is None:
            return
        view = self.result_view()
        if view is None or view.get('rating') is None:
            return
        self._hud_shown = row['id']
        self.hud.result(hud_card(view, (self.board or {}).get('tiers'), (self.board or {}).get('placement') or 5))

    # --- the game ----------------------------------------------------------------------------------------------------
    def _start_game(self):
        """Both are Ready: start RPCS3 into the game (not again for the same lobby, and not when a game is open)."""
        with self.lock:
            code, rpcs3, title = self.code, self.rpcs3(), self.title
            if self.launched == code or rpcs3 is None or title is None:
                return
            problem = self.guest_problem()
            if problem:
                self.note = {'text': problem, 'tone': 'bad'}
            else:
                self.launched = code
        if problem:
            self.changed()
            if code:
                self._lobby_call(lambda who: lobby.ready(code, who[0], False))
            return
        if savedata.running_rpcs3():          # started by the player: follow it all the same (result window, overlay)
            self.started_at, self.signed_at, self._tail = time.time(), None, None
            with self.lock:
                self.watching, self.ended, self.baseline, self.result = True, None, PENDING, None
                self.note = {'text': "Your game is open. Press nothing here; we follow it.", 'tone': 'good'}
            self.changed()
            self._hud_start()
            return
        try:
            if self.roster:
                savedata.boot_first(rpcs3.savedata, self.roster['folder'])      # the game loads it by itself at boot
            config = onlinecfg.write_config(rpcs3, title, self._address(), borderless=self.overlay())
            self.by_itself = patchinstall.auto_start(rpcs3, title)
            if self.by_itself:      # for this start only; _read_log unticks it as soon as the game has booted
                patchinstall.set_online_start(rpcs3, [title], True)
            self.started_at, self.signed_at, self._tail = time.time(), None, None
            with self.lock:
                self.watching, self.ended, self.baseline, self.result = True, None, PENDING, None
            args = onlinecfg.launch_args(rpcs3, title, config)
            if args is None and not rpcs3.command():
                raise OSError("The program does not know how to start RPCS3. In Setup, pick the RPCS3 program itself (not only its folder).")
            if args is None:
                raise OSError("RPCS3 does not say where your copy of the game is. Start the game once from RPCS3's list.")
            flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
            savedata.launch(args, cwd=rpcs3.launch_dir(), close_fds=True, creationflags=flags)
            self._hud_start()
        except (OSError, patchinstall.PatchError) as err:
            self._untick_start()
            with self.lock:
                self.launched = None
                self.note = {'text': f"The game could not be started: {err}", 'tone': 'bad'}
            self.changed()

    def _read_log(self):
        rpcs3 = self.rpcs3()
        if rpcs3 is None:
            return
        path = onlinecfg.log_path(rpcs3)
        try:
            if os.path.getmtime(path) < self.started_at:       # the last session's log says nothing about this start
                return
            if self._tail is None or self._tail.path != path:
                self._tail = onlinecfg.LogTail(path)
            log = self._tail.read()
        except OSError:
            return
        with self.lock:
            self.log = log
            if log['name'] and self.signed_at is None:
                self.signed_at = time.time()
        if log['name'] or log['bound']:     # the game has started and read its patches
            self._untick_start()
        self.changed()

    def _clear_start(self):
        """Whatever happened to the last start (the program closed, a crash), the online start entry must not stay ticked: untick it
        in every version when RPCS3 is not running (the next normal boot would dive into a search)."""
        rpcs3 = self.rpcs3()
        if rpcs3 is None or savedata.running_rpcs3():
            return
        if self.by_itself and time.time() - self.started_at < START_GRACE:     # RPCS3 is just starting: the game has yet to read it
            return
        try:
            patchinstall.set_online_start(rpcs3, list(self.update.versions), False)
            self.by_itself = False
        except (OSError, patchinstall.PatchError):
            pass

    def _untick_start(self):
        """The online start entry is for one start only: untick it (RPCS3 must be closed; if it is not, the next try does it)."""
        rpcs3, title = self.rpcs3(), self.title
        if rpcs3 is None or title is None or not getattr(self, 'by_itself', False):
            return
        try:
            patchinstall.set_online_start(rpcs3, [title], False)
            self.by_itself = False
        except (OSError, patchinstall.PatchError):
            pass

    # --- what the page shows -------------------------------------------------------------------------------------------
    def by_itself_possible(self):
        """Will the game take both players to Select Teams with no key (game version 1.00 or the update 1.01, with the start entry and the screens)?"""
        return self.auto

    def stalled(self):
        """The game has been signed in for a while and its player still has no session (no host, no guest, not playing): whatever
        the reason, the steps are then shown to press by hand (a game that went by itself never gets here)."""
        me = self._member()
        return bool(self.launched and self.signed_at is not None and time.time() - self.signed_at > STALL_AFTER
                    and me and me.get('progress') in (None, 'offline', 'in_game', 'signed_in'))

    def steps(self, role):
        """The things to press in the game, by role (the host creates the session, the guest joins it)."""
        load = [LOAD_ROSTER.format(name=self.roster['name'])] if self.roster else []
        by_hand = list(STEPS_ALL) + list(STEPS_HOST if role == 'host' else STEPS_GUEST)
        if self.by_itself_possible():
            return load + [BY_ITSELF] + ([STALLED] + by_hand if self.stalled() else [])
        return load + by_hand

    def view(self):
        """The tab's state word: no-rpcs3 | no-account | not-set-up | ready | in-lobby | starting | in-game | failed."""
        if self.rpcs3() is None:
            return 'no-rpcs3'
        if not self.account:
            return 'no-account'
        if not self.marks()['ready']:
            return 'not-set-up'
        if not self.lobby:
            return 'ready'
        if self.log and (self.log['refused'] or self.log['fatal'] or self.log['old'] or not self.log['signaling']):
            return 'failed'
        if self.launched and not self.ended:
            return 'in-game'
        return 'starting' if self.lobby.get('state') == 'starting' else 'in-lobby'

    def why(self):
        """What went wrong in the game, in the player's words (None when nothing)."""
        log = self.log
        if not log or not self.launched:
            return None
        if log['fatal']:
            return "RPCS3 stopped. Close it and press Ready again."
        if log['old']:
            return "Your RPCS3 is too old for the online server. Update RPCS3 (rpcs3.net, Download), then start again."
        if log['refused']:
            return "Sign-in failed: check your account in RPCS3 (Configuration > RPCN)."
        if not log['signaling']:
            return "RPCN did not answer. Check your internet connection and your firewall, then start again."
        return None

    def hint(self):
        """What to do when the lobby says the patches differ, this PC lost its patch, or the host's roster does not fit this game
        (None otherwise)."""
        me = self._member()
        problem = self.guest_problem()
        if problem:
            return problem
        if me and not self.marks()['patched']:
            return PATCH_NEEDED
        return PATCH_HINT if me and not me.get('patch_ok', True) else None

    def snapshot(self):
        with self.lock:
            role = (self._member() or {}).get('role')
            bring, bring_why = self.bring()
            return {'state': self.view(), 'no_rpcs3': self.no_rpcs3(), 'native': getattr(getattr(self.update, 'rpcs3', None), 'native', False),
                    'account': self.account, 'title': self.title, 'busy': self.busy or self.copying,
                    'note': self.note, 'checked': self.checked, 'server': self.server, 'marks': self.marks(),
                    'roster': self.roster['name'] if self.roster else None, 'brought': self.brought,
                    'bring': bring, 'bring_why': bring_why, 'patch': self.patch_word(), 'hint': self.hint(),
                    'guest_problem': self.guest_problem(),
                    'build': self.build, 'build_note': self.build_note(), 'game_note': self.game_note(), 'build_old': self.build_problem(),
                    'lobby': self.lobby, 'code': self.code, 'role': role, 'steps': self.steps(role) if role else [],
                    'public': self.public, 'open': self.rows(), 'open_error': self.open_error,
                    'progress': PROGRESS, 'why': self.why(), 'no_account': NO_ACCOUNT, 'launched': bool(self.launched),
                    'ended': bool(self.ended), 'chat': self.chat(), 'chat_wait': time.time() < self.chat_wait,
                    'phrases': PHRASES, 'ranks': self.ranks_view(), 'result': self.result_view(),
                    'overlay': {'can': hud.available(), 'on': self.overlay()}}


def box_lines(mine, theirs):
    """The box score's lines [{label, me, them}] from two sides' stats ({tag: number}); a line where both sides have nothing is left out."""
    def text(stats, tags):
        if isinstance(tags, tuple):
            made, tries = (int(stats.get(t) or 0) for t in tags)
            return f"{made}/{tries}" if made or tries else None
        value = int(stats.get(tags) or 0)
        if not value:
            return None
        return f"{value // 60}:{value % 60:02d}" if tags == 'TOA' else str(value)
    rows = []
    for label, tags in BOX_LINES:
        a, b = text(mine, tags), text(theirs, tags)
        if a is not None or b is not None:
            zero = '0:00' if tags == 'TOA' else '0/0' if isinstance(tags, tuple) else '0'
            rows.append({'label': label, 'me': a or zero, 'them': b or zero})
    return rows


def signed(n):
    return f"+{n}" if n > 0 else str(n)


def stats_view(card):
    """The My stats view from my rank card (None before a rated match): tiles, form, the rating line, opponents and teams."""
    if not card:
        return {'note': STATS_NONE}
    w, l = card.get('w') or 0, card.get('l') or 0
    streak = card.get('streak') or 0
    gf, ga = card.get('gf') or 0, card.get('ga') or 0
    tiles = [{'label': 'Record', 'value': f"{w}-{l}", 'sub': f"{round(100 * w / (w + l))} % won" if w + l else ''},
             {'label': 'Streak', 'value': (f"W{streak}" if streak > 0 else f"L{-streak}") if streak else '-', 'sub': 'in a row'},
             {'label': 'Best rating', 'value': str(card.get('peak') or card.get('rating') or '-'), 'sub': f"now {card.get('rating')}"},
             {'label': 'Goals', 'value': f"{gf}-{ga}", 'sub': f"{signed(gf - ga)} difference"},
             {'label': 'Last 7 days', 'value': signed(card.get('delta7') or 0), 'sub': 'rating'}]
    curve = [int(p[1]) for p in card.get('curve') or [] if isinstance(p, (list, tuple)) and len(p) == 2]
    return {'note': None, 'tiles': tiles, 'form': list(card.get('form') or ''), 'curve': curve,
            'opponents': card.get('opponents') or [], 'teams': card.get('teams') or []}


def hud_card(view, tiers=None, placement=5):
    """The overlay's result card (hud.anim.Result's data) from OnlineController.result_view() of a rated match; `tiers` the
    board's [{name, min}] (for the bar's low end and a rank-up), `placement` the games before a rank shows."""
    won = view.get('result') == 'W'
    score = f"{view['for']} - {view['against']} " if view.get('for') is not None and view.get('against') is not None else ''
    data = {'title': 'Final', 'sub': score + ('win' if won else 'loss'), 'rating_from': view['before'],
            'rating_to': view['rating'], 'tier': view.get('tier'), 'next_name': view.get('next_tier'),
            'next_at': view.get('next_at')}
    if view.get('status') == 'forfeit':
        data['sub'] = 'win, your friend left' if won else 'loss, you left'
    if view.get('placing'):
        data.update(tier=None, placing=view['placing'], placing_of=placement)
        return data
    steps = sorted((t['min'], t['name']) for t in tiers or [] if t.get('min') is not None)

    def tier_at(rating):
        return next((name for low, name in reversed(steps) if rating >= low), None)
    low = next((m for m, name in steps if name == view.get('tier')), None)
    if low is not None:
        data['band_low'] = low
    if steps and view['rating'] > view['before'] and tier_at(view['rating']) != tier_at(view['before']):
        data['rank_up'] = tier_at(view['rating'])
    return data
