"""The Update tab without a window toolkit: say where RPCS3 is, pick a roster, switch on what to
update, press one button. `snapshot()` is everything the tab shows, as plain data; the methods are
its buttons. The same rules as the old window (gui.App), which this replaces."""
import datetime
import os
import sys
import tempfile
import threading
import time

from .. import __version__, datasource, export, gamepatch, layout, native, packs, patchinstall, pipeline, restore, savedata
from .. import edits as my_edits
from ..art import install as art_install
from ..art import parts as P
from ..art.install import ArtError, installed as art_installed, remove as remove_art
from ..gui_state import is_current_scan
from ..progress import fraction
from ..roster import Roster
from ..stock import StockError
from . import jobs, selfupdate, settings as S, texts as X

SLICE = 'update'


def _load_pack():
    try:
        return datasource.load_pack(offline=True)
    except datasource.Offline:
        return {}


def temporary(path):
    """Is `path` in the system's temp folder, in the program as players run it (the exe)? Such an RPCS3 is never
    used at start and never remembered: a test's pretend RPCS3 once landed in the owner's settings (2026-10-22), and
    Patch then failed on its pretend disc. Run from source (tests, tools/window_shot.py) a temp RPCS3 is fine."""
    if not path or not getattr(sys, 'frozen', False):
        return False
    temp = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
    return os.path.normcase(os.path.abspath(path)).startswith(temp + os.sep)


def update_context(rpcs3, slot, targets, steps, parts, in_place, photos=False, edits=False):
    """The lines of an update's block in the error log: the roster, where it goes, what runs, and the folders it
    uses (each one marked "missing" when it is not there: a tester's "[WinError 3]" named no folder)."""
    def where(path):
        return f"{path}{'' if path and os.path.exists(path) else '  (missing)'}" if path else "(none)"
    lines = [f"roster: {getattr(slot, 'name', '?')} in {where(getattr(slot, 'folder', None))}",
             f"version {getattr(slot, 'title_id', '?')}, saved for {', '.join(targets or [])}, "
             f"{'in place' if in_place else 'as a new roster'}",
             f"steps: {', '.join(steps) or '(none)'}; restore: {', '.join(sorted(parts)) or '(none)'}; "
             f"photos: {'on' if photos else 'off'}; my edits: {'yes' if edits else 'no'}"]
    if rpcs3 is None:
        return lines
    lines += [f"rpcs3: {where(getattr(rpcs3, 'where', None))}", f"save folder: {where(getattr(rpcs3, 'savedata', None))}",
              f"patched: {', '.join(patchinstall.patched_titles(rpcs3)) or 'no'}"]
    for title in dict.fromkeys([getattr(slot, 'title_id', None)] + list(targets or [])):
        if title:
            lines += [f"{title} game folder: {where(rpcs3.game_folder(title))}",
                      f"{title} game: {where(rpcs3.game_disc(title))}"]
    return lines


class UpdateController:
    def __init__(self, host, settings=None, pack=None, photos=False):
        self.host = host
        self.lock = threading.RLock()
        self.settings = S.load() if settings is None else settings
        self.pack = _load_pack() if pack is None else pack
        self.editor = None          # the Roster editor's controller, once there is one (it shares the save mode)
        self.rpcs3 = None           # savedata.Rpcs3 once the program has been found
        self.versions = []          # the versions of the game that RPCS3 has (title ids)
        self.slots = []
        self.usable = {}            # roster folder -> None when usable, else the reason it is not
        self.selected = None        # roster folder to start from
        self.problem = None         # why the path picked is not RPCS3 (shown in red)
        self.running = False        # RPCS3 runs (seen at the last scan)
        self.busy = False
        self.quitting = False       # the new version runs: this window must close, whatever it was doing
        self.scanning = False
        self.checked = {}           # (SYS-DATA path, size, time) -> (None or why it cannot be used, made for the patch,
                                    # its rights' bits)
        self.patch_rosters = set()  # roster folders made for the game patch
        self.roster_rights = {}     # roster folder -> the bits of its player rights (5; 6 on a roster for patch 0.23)
        self.patch_state = {}       # patchinstall.state of this RPCS3
        self._fit_check = False     # Patch / Unpatch done: after the next scan, ask to update a roster that no longer fits
        self._fit = None            # the roster folder that question's "Update it now" updates in place
        self._scan_id = 0
        self.at = 0.0               # progress of the running update, 0..1
        self.photos_running = False
        self.save_pick = S.BOTH if self.settings.get(S.SAVE_BOTH) else None
        self.save_mode = S.AS_NEW if self.settings.get(S.SAVE_MODE) == S.AS_NEW else S.IN_PLACE
        self.name = savedata.default_name()
        self.name_edited = False
        self.export_mode = bool(self.settings.get(S.EXPORT_ONLY))
        picked = self.settings.get(S.EXPORT_FILE)
        self.export_file = picked if picked and os.path.isfile(picked) and not self._untouched(picked) else None
        self.export_from_file = self.export_file is not None and bool(self.settings.get(S.EXPORT_FROM_FILE, True))
        self.export_patch = bool(self.settings.get(S.EXPORT_PATCH))     # the export holds the game patch
        self.export_problem = None
        self._export_result = None  # the last ExportResult (its pop-up can be opened again)
        self.result = None          # the result box (dict), or None
        self.status = None          # (text, tone) while busy or while a result shows; else worked out
        self.dialog = None
        self._answers = {}
        self.last_report = self._backup = self._export_folder = self._update_page = None
        self.art_installed = art_installed()

        remembered = self.settings.get('steps', {})
        self.step_keys = pipeline.steps_for(self.pack)
        defaults = pipeline.default_steps(self.pack)
        self.steps = {k: bool(remembered.get(k, k in defaults)) for k in self.step_keys}
        self.photos = bool(remembered.get(S.PHOTOS, photos))
        self.use_edits = bool(remembered.get(S.EDITS, True))
        self.skip_intro = bool(remembered.get(S.SKIP_INTRO, True))
        self.no_login = bool(remembered.get(S.NO_LOGIN, False))
        # 0.76.0: team names, this season's jerseys, arenas, bright ice and team masks have switches of their own. A
        # settings file from before keeps what it had: photos on meant names and jerseys on too.
        self.art_on = {S.NAMES: bool(remembered.get(S.NAMES, True)),
                       S.LOOKS: bool(remembered.get(S.LOOKS, self.photos)),
                       S.ARENAS: bool(remembered.get(S.ARENAS, False)),
                       S.TEAM_MASKS: bool(remembered.get(S.TEAM_MASKS, False))}
        self.art_on[S.BRIGHT_ICE] = self.art_on[S.LOOKS]    # 0.80.0: the new centre ice comes with this season's (S.TOGETHER)
        if S.PHOTOS_DEFAULT not in self.settings:       # 0.65: the switch starts off for everyone, once; ticking it again is kept
            self.photos = False
            self.settings[S.PHOTOS_DEFAULT] = True
            self.save_settings()
        self.marks = {}             # row key -> its part of restore.py ("Restore" pressed)
        # the picture packs (packs.py), downloaded in the background while a switch that needs one is on
        self.fetch = 'ready' if all(packs.have(n) for n in self.packs_wanted()) else 'idle'     # running / failed
        self.fetch_at = 0.0         # 0..1 while running
        self.fetch_size = None      # bytes still to download, once the server said
        self.pack_sizes = {}        # pack name -> its size on the server, once the list was read
        self._fetch_stop = threading.Event()
        self._fetching = False
        self.waiting = None         # Update pressed during the download: start(everything) once it is done
        self.pictures_short = []    # the packs the running update lacks (offline, not on the server): the result names them

    # --- start --------------------------------------------------------------------------------------
    def start_up(self):
        """Find RPCS3 where it was last time (or where it runs / usually is)."""
        last = self.settings.get('rpcs3') or self.settings.get('folder')
        running = savedata.running_rpcs3()
        running = running if running and os.path.exists(running) else None      # a Flatpak's /app/bin/rpcs3 is not on this PC
        self.set_rpcs3((None if temporary(last) else last) or running or savedata.default_rpcs3(), quiet=True)

    def changed(self):
        self.host.changed(SLICE)

    # --- a newer version of the program -----------------------------------------------------------------
    def check_for_update(self, force=False):
        """Look at GitHub in the background (at every start, unless the player switched it off; `force`: the button);
        a newer version is offered in a question. Never in the way: offline means silence."""
        with self.lock:
            if not force and not selfupdate.due(self.settings):
                return
        threading.Thread(target=self._look_for_update, args=(force,), daemon=True).start()

    def _look_for_update(self, force, wait=2.0):
        release = selfupdate.latest()
        with self.lock:
            if release is None and force:
                self.ask("You have the newest version", [f"Version {__version__} is the latest one."
                         " If you are offline, or GitHub did not answer, try again in a moment."],
                         [("OK", 'ok', 'primary')], {})
                return
            if release is None or (not force and self.settings.get('update_skipped') == release.text):
                return
        while True:                 # an update or another question first, then the offer (before, it was dropped)
            with self.lock:
                if self.quitting:
                    return
                if not (self.busy or self.dialog):
                    self._offer_update(release)
                    return
            time.sleep(wait)

    def _offer_update(self, release):
        notes = [line.strip(' #*-') for line in release.notes.splitlines() if line.strip(' #*-')][:4]
        lines = [f"You have version {__version__}."] + notes
        if release.can_install() and selfupdate.can_replace():
            buttons = [("Update now", 'now', 'primary'), ("Later", 'later', 'plain'), ("Skip this version", 'skip', 'ghost')]
            lines.append("The program downloads the new version, restarts and keeps all your settings and rosters.")
            answers = {'now': lambda: self.install_update(release)}
        else:
            buttons = [("Open the download page", 'page', 'primary'), ("Later", 'later', 'plain'),
                       ("Skip this version", 'skip', 'ghost')]
            answers = {'page': lambda: self.host.open_url(release.page)}
        answers['skip'] = lambda: self._skip_update(release)
        self.ask(f"Version {release.text} is out", lines, buttons, answers)

    def _skip_update(self, release):
        with self.lock:
            self.settings['update_skipped'] = release.text
            S.save(self.settings)

    # --- the pictures: photos, jerseys, arenas, bright ice, team masks (packs.py) ---------------------------
    def parts_on(self):
        """The picture parts switched on (art/parts.py names)."""
        on = {p for p, v in self.art_on.items() if v}
        if self.photos:
            on.add(P.PHOTOS)
        return frozenset(on)

    def packs_wanted(self):
        """The packs the switched-on parts need (packs.NAMES): the names switch needs none."""
        return P.packs_for(self.parts_on())

    def not_served(self, names):
        """Did the server's list (read at the last download) lack one of the packs `names`? Not yet published: the
        row says so instead of "Downloaded automatically"."""
        return bool(self.pack_sizes) and any(n not in self.pack_sizes for n in names)

    def download_pictures(self):
        """While a switch that needs a pack is on: download what is missing or changed, in the background (at start,
        when a switch goes on, and before an update when the last try failed). The next update uses it."""
        with self.lock:
            if not self.packs_wanted() or self._fetching:
                return
            self._fetching = True
            self._fetch_stop.clear()
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        why = None
        wanted = self.packs_wanted()
        try:
            try:
                packs.prune()           # what an earlier run still had open
            except OSError:
                pass
            listed = packs.manifest()
            if listed is None:
                why = 'offline'
            else:
                names = packs.missing(listed, wanted)
                with self.lock:
                    self.pack_sizes = {n: e['size'] for n, e in listed.items()}
                    self.fetch_size = packs.size_of(listed, names) or None
                    if names:
                        self.fetch, self.fetch_at = 'running', 0.0
                    self.changed()
                why = packs.sync(self._fetch_progress, self._fetch_stop.is_set, listed, wanted)[1]
        except packs.Cancelled:
            why = 'stopped'
        except Exception as err:        # a folder that cannot be written: logged, tried again later
            jobs.log_unexpected(err)
            why = str(err)
        if why not in (None, 'stopped'):
            self.host.log(f"The pictures were not downloaded ({why}). The program tries again.")
        with self.lock:
            self._fetching = False
            have = all(packs.have(n) for n in wanted)
            self.fetch = ('ready' if why is None or have else 'idle' if why == 'stopped' else 'failed')
            waiting, self.waiting = self.waiting, None
            if waiting is not None:
                self.busy, self.status = False, None
            self.changed()
        if waiting is not None:
            self.start(waiting, waited=True)

    def _fetch_progress(self, at):
        with self.lock:
            moved = int(at * 100) != int(self.fetch_at * 100)
            self.fetch_at = at
            if moved:
                if self.waiting is not None:
                    self.at, self.status = at, (X.PHOTOS_WAITING.format(pct=int(at * 100)), 'body')
                self.changed()

    def install_update(self, release):
        with self.lock:
            if self.busy:
                return
            self.busy, self.at = True, 0.0
            self.status = ("Downloading the new version...", 'body')
            self.changed()

        def progress(value):
            with self.lock:
                self.at = value
                self.status = (f"Downloading version {release.text}...", 'body')
                self.changed()

        def work():
            try:
                selfupdate.install(release, progress)
            except Exception as err:
                with self.lock:
                    self.busy, self.at, self.status = False, 0.0, None
                    self.show_result(False, "The update did not work", [
                        str(err) if isinstance(err, ValueError) else "The new version could not be downloaded or put in place.",
                        "Nothing was changed: this version still works. You can download the new one from the release page."],
                        [("Open the download page", 'update_page')])
                    self._update_page = release.page
                return
            with self.lock:
                self.quitting, self.busy = True, False
            self.host.quit()

        threading.Thread(target=work, daemon=True).start()

    def set_check_updates(self, on):
        with self.lock:
            self.settings['check_updates'] = bool(on)
            S.save(self.settings)
            self.changed()

    def save_settings(self):
        self.settings['steps'] = dict(self.steps)
        self.settings['steps'][S.PHOTOS] = self.photos
        self.settings['steps'].update(self.art_on)
        self.settings['steps'][S.EDITS] = self.use_edits
        self.settings['steps'].update({S.SKIP_INTRO: self.skip_intro, S.NO_LOGIN: self.no_login})
        S.save(self.settings)

    def tick(self):
        """Every 15 seconds: the suggested name keeps the current time until the player types their own."""
        with self.lock:
            if not self.name_edited and not self.busy and not self.in_place():
                name = savedata.default_name()
                if name != self.name:
                    self.name = name
                    self.changed()

    # --- helpers ------------------------------------------------------------------------------------
    def say(self, *texts):
        """Lines from the engine: into the details, onto the status line, into the progress bar."""
        if not texts:
            return
        self.host.log(*texts)
        with self.lock:
            last = next((t for t in reversed(texts) if t), None)
            if self.busy and last:
                for text in texts:
                    value = fraction(text, self.at, photos=self.photos_running) if text else None
                    if value is not None:
                        self.at = value
                self.status = (last, 'body')
                self.changed()

    def selected_slot(self):
        return self.slot_of(self.selected)

    def roster_file(self):
        """The roster file an export starts from (the team tabs show it), or None."""
        return self.export_file if self.export_mode and self.export_from_file and self.export_file else None

    def slot_of(self, folder):
        found = next((s for s in self.slots if s.folder == folder), None)
        if found is None and self.export_mode and folder:       # the game's own roster of a game the player pointed at
            found = next((s for s in self._export_discs() if s.folder == folder), None)
        return found

    def in_place(self, slot=None):
        """Is the roster picked updated in place? (The game's own roster is no save: always a new roster.)"""
        slot = slot or self.selected_slot()
        return (self.save_mode == S.IN_PLACE and slot is not None and not getattr(slot, 'disc', False)
                and not self.export_mode)            # an export never changes a roster

    def save_targets(self, slot=None):
        """The versions of the game (title ids) the new roster is saved for."""
        slot = slot or self.selected_slot()
        if slot is None:
            return []
        if self.in_place(slot):
            return [slot.title_id]
        if len(self.versions) < 2 or self.save_pick in (None, slot.region):
            return [slot.title_id]
        if self.save_pick == S.BOTH:
            return sorted(set(self.versions) | {slot.title_id}, key=lambda t: (t != slot.title_id, t))
        return [savedata.title_of(self.save_pick)]

    def editor_busy(self):
        return bool(self.editor is not None and getattr(self.editor, 'busy', False))

    def show_result(self, good, title, lines, buttons=(), items=(), bad=()):
        """`bad`: lines shown first, in red (what went wrong after the roster was saved)."""
        self.result = {'good': good, 'title': title, 'lines': list(lines), 'items': [list(i) for i in items],
                       'buttons': [{'label': label, 'action': action} for label, action in buttons], 'dim': None,
                       'bad': list(bad)}
        self.changed()

    def hide_result(self):
        with self.lock:
            self.result = None
            self.status = None if not self.busy else self.status
            self.changed()

    def ask(self, title, lines, buttons, answers, **more):
        """A question in the page (Delete, Restore default...). `buttons`: (label, answer, style[, keep]); a button with
        `keep` does its work and leaves the window open; `answers`: answer -> what to do. `more`: a bigger window with `rows`
        ([{'head', 'text'}]), `notes` (lines after them) and `copy` (the text its 'copy' button puts on the clipboard)."""
        ident = (self.dialog or {}).get('id', 0) + 1
        self.dialog = {'id': ident, 'title': title, 'lines': list(lines),
                       'buttons': [{'label': b[0], 'answer': b[1], 'style': b[2], 'keep': len(b) > 3 and bool(b[3]),
                                    'copy': b[1] == 'copy' and 'copy' in more} for b in buttons]}
        self.dialog.update(more)
        self._answers = answers
        self.changed()

    def answer(self, ident, answer):
        with self.lock:
            if not self.dialog or self.dialog['id'] != ident:
                return
            todo = self._answers.get(answer)
            if any(b['answer'] == answer and b['keep'] for b in self.dialog['buttons']):
                pass
            else:
                self.dialog, self._answers = None, {}
            self.changed()
        if todo:
            todo()

    # --- RPCS3 and its rosters ------------------------------------------------------------------------
    def pick_rpcs3(self):
        with self.lock:
            if self.busy:
                return
            start = self.rpcs3.folder if self.rpcs3 else os.path.expanduser('~')
        if savedata.WINDOWS:
            path = self.host.ask_open("Where is rpcs3.exe, or NHLLauncher.exe in NHL Legacy Native?",
                                      ['Programs (*.exe)', 'All files (*.*)'], start)
        elif savedata.MAC:      # RPCS3.app is a folder to the file dialog; RPCS3's data folder will do as well
            path = self.host.ask_folder("Where is RPCS3.app, or RPCS3's folder? (" + ", ".join(savedata.data_folders()) + ")", start)
        else:                   # Linux: the program (an AppImage or the rpcs3 binary) or RPCS3's folder; the Flatpak has only a folder
            self.ask("Where is RPCS3?", X.linux_pick(savedata.data_folders()),
                     [("The program or AppImage", 'file', 'primary'), ("RPCS3's folder", 'folder', 'plain'),
                      ("Cancel", 'no', 'plain')],
                     {'file': lambda: self._pick_from(self.host.ask_open("Where is RPCS3? (the rpcs3 program or its AppImage)",
                                                                         ['RPCS3 (rpcs3*, *.AppImage)', 'All files (*)'], start)),
                      'folder': lambda: self._pick_from(self.host.ask_folder(
                          "Where is RPCS3's folder? (" + ", ".join(savedata.data_folders()) + ")", start))})
            return
        self._pick_from(path)

    def _pick_from(self, path):
        if path:
            self.set_rpcs3(os.path.normpath(path))

    def set_rpcs3(self, path, quiet=False, then=None):
        """Find the saves behind `path` (RPCS3 or its folder) and list the rosters, in the background;
        saves already read (same file, size and time) are not read again. `then()` runs once the list is there."""
        with self.lock:
            self._scan_id += 1
            scan_id = self._scan_id
            self.scanning = True
            checked = dict(self.checked)
            games = self.settings.get('games')
            self.changed()

        def scan():
            found, slots, usable, versions, problem, picked, patchy, state = None, [], {}, [], None, None, set(), {}
            rights = {}
            if path:
                try:
                    found = savedata.find_rpcs3(path, games=games)
                except savedata.NoGameError as err:         # RPCS3 itself is fine: it only needs the game
                    found = err.rpcs3
                except (savedata.Rpcs3Error, OSError) as err:
                    try:                    # not RPCS3: a folder with roster saves will do (savedata.SaveFolder)
                        found, picked = savedata.open_saves(path)
                    except (FileNotFoundError, OSError):
                        problem = str(err)
            if found:
                slots = savedata.list_rosters(found.savedata)
                versions = found.games()
                for s in found.disc_slots():        # the game's own roster: always usable, read when used
                    usable[s.folder] = None
                for s in slots:
                    try:
                        st = os.stat(s.sys_data)
                        key = (s.sys_data, st.st_size, st.st_mtime_ns)
                    except OSError:
                        key = None
                    if key not in checked:
                        try:
                            R = Roster(s.sys_data)
                            layout.check_base(R)
                            checked[key] = (None, gamepatch.is_patch_roster(R), R.P.field(gamepatch.RIGHTS).bits)
                        except (layout.LayoutError, ValueError, KeyError, OSError) as err:
                            checked[key] = (str(err), False, None)
                    usable[s.folder] = checked[key][0]
                    if checked[key][1]:
                        patchy.add(s.folder)
                    rights[s.folder] = checked[key][2]
                slots = slots + found.disc_slots()
                if found.patchable or found.native:
                    state = patchinstall.state(found)
            running = savedata.running_rpcs3() is not None if found else False
            self._scanned(found, slots, usable, versions, problem, quiet, running, checked, picked, scan_id, patchy, state,
                          rights)
            if then is not None:
                then()

        jobs.run(scan, failed=lambda message: self._scan_failed(message, scan_id))

    def _scan_failed(self, message, scan_id):
        with self.lock:
            if not is_current_scan(scan_id, self._scan_id):
                return
            self.scanning = False
            self.problem = message
            self.changed()

    def _scanned(self, found, slots, usable, versions, problem, quiet, running, checked, picked, scan_id, patchy=(),
                 state=None, rights=None):
        with self.lock:
            if not is_current_scan(scan_id, self._scan_id):
                return
            self.scanning = False
            if picked:
                self.selected = picked
            self.checked = checked
            self.rpcs3, self.slots, self.usable, self.versions = found, slots, usable, versions
            self.patch_rosters, self.patch_state = set(patchy), dict(state or {})
            self.roster_rights = dict(rights or {})
            self.problem = problem if problem and not quiet else None
            self.running = running
            if found and not temporary(found.where):
                self.settings['rpcs3'] = found.where
                self.settings.pop('folder', None)
                if not found.plain:         # the last RPCS3 and the last port, one press apart (Setup's "Switch to")
                    self.settings.setdefault('hosts', {})['native' if found.native else 'rpcs3'] = found.where
                S.save(self.settings)
            art_install.use_host(found)
            self.art_installed = art_installed()
            keep = self.selected if self.slot_of(self.selected) and self.usable.get(self.selected) is None else None
            first = next((s.folder for s in slots if usable[s.folder] is None and not getattr(s, 'disc', False)),
                         next((s.folder for s in slots if usable[s.folder] is None), None))
            self._select(keep or first)
            if self._fit_check:
                self._fit_check = False
                self._ask_fit()
            self.changed()

    def _other_host(self):
        """(what it is called, where it is) of the other game the player picked before, None without one."""
        if self.rpcs3 is None or self.rpcs3.plain:
            return None
        kind, name = ('rpcs3', 'RPCS3') if self.rpcs3.native else ('native', 'NHL Legacy Native')
        path = (self.settings.get('hosts') or {}).get(kind)
        return (name, path) if path and os.path.exists(path) else None

    def switch_host(self):
        """Setup's "Switch to": the other game picked before."""
        with self.lock:
            other = None if self.busy or self.scanning else self._other_host()
        if other:
            self.set_rpcs3(other[1])

    def _named(self, text):
        """A text about RPCS3 in the words of the game in use."""
        return text.replace('RPCS3', self.rpcs3.name) if self.rpcs3 is not None and self.rpcs3.native else text

    def misfit(self, s):
        """Why the game as RPCS3 has it now cannot load roster `s`, or None: a normal roster in a patched game, a
        roster made for the patch in a game without it (the game says the roster is damaged), a roster made for another
        version of the patch (its player rights have other bits than the game's db description: patch 0.23 gave them
        six)."""
        if s is None or getattr(s, 'disc', False) or self.rpcs3 is None or self.rpcs3.plain \
                or self.usable.get(s.folder) is not None:
            return None
        if self.patch_state.get(s.title_id, {}).get('stale'):
            return X.MISFIT_PORT if self.rpcs3.native else X.MISFIT_STALE
        patched, made = s.title_id in self._patched(), s.folder in self.patch_rosters
        if patched and made:
            game, own = self.patch_state.get(s.title_id, {}).get('rights'), self.roster_rights.get(s.folder)
            return X.MISFIT_VERSION if game and own and game != own else None
        return X.MISFIT_PATCHED if patched else X.MISFIT_UNPATCHED if made else None

    def _ask_fit(self):
        """After Patch / Unpatch: the roster picked no longer fits the game, so offer to update it now."""
        slot = self.selected_slot()
        why = self.misfit(slot)
        if why is None:
            return
        self.ask(f"Update \"{slot.name}\" now?", X.fit_ask(slot.name, why),
                 [("Update it now", 'yes', 'primary'), ("Later", 'no', 'plain')],
                 {'yes': lambda: self._update_fit(slot.folder)})

    def _update_fit(self, folder):
        with self.lock:
            if self.busy or self.selected != folder:
                return
            if not any(self.steps.values()):
                self.show_result(False, "Nothing to update", [X.FIT_NO_STEP])
                self.host.send('focus_tab', {'tab': 'update'})
                return
            self._fit = folder
        self.host.send('focus_tab', {'tab': 'update'})
        self.start()

    def pick_game(self, folder=False):
        """The player points at the game (RPCS3 does not list it): the program keeps the place and looks again."""
        with self.lock:
            if self.busy or (not self.rpcs3 and not self.export_mode):     # an export needs no RPCS3
                return
        start = os.path.expanduser('~')
        if folder:
            path = self.host.ask_folder("Pick the folder of your NHL Legacy game (it holds PS3_GAME)", start)
        else:
            path = self.host.ask_open("Pick your NHL Legacy game", ['Game disc image (*.iso)', 'All files (*.*)'], start)
        if not path:
            return
        title = savedata.game_title_id(os.path.normpath(path))
        with self.lock:
            if title not in savedata.GAMES:
                self.show_result(False, "Not NHL Legacy", ["That is not a copy of NHL Legacy Edition. Pick the game's "
                                                           ".iso file, or the folder that holds its PS3_GAME folder."])
                return
            self.settings.setdefault('games', {})[title] = os.path.normpath(path)
            S.save(self.settings)
            where = self.rpcs3.where if self.rpcs3 else None
            if where is None:
                self.changed()
        if where is not None:
            self.set_rpcs3(where)

    def select(self, folder):
        with self.lock:
            if self.busy or self.slot_of(folder) is None or self.usable.get(folder) is not None:
                return
            self._select(folder)
            if self.export_mode and self.export_from_file:      # a roster picked: the export starts from it, not the file
                self.export_from_file = False
                self.settings[S.EXPORT_FROM_FILE] = False
                S.save(self.settings)
            self.changed()

    def _select(self, folder):
        previous = self.selected
        if folder != previous and self.save_pick != S.BOTH:
            self.save_pick = None           # a single version follows the roster picked
        if folder != previous and self.save_mode == S.IN_PLACE:
            self.name_edited = False        # the name box shows the roster picked
        self.selected = folder
        slot = self.selected_slot()
        if folder != previous and getattr(slot, 'disc', False) and not self.name_edited:
            self.name = savedata.default_name()
        if self.in_place(slot) and not self.name_edited:
            self.name = slot.name

    def open_roster_folder(self, folder):
        slot = self.slot_of(folder)
        if slot is not None and not getattr(slot, 'disc', False) and os.path.isdir(slot.path):
            self.host.open_path(slot.path)

    def ask_delete(self, folder):
        """Ask before a roster save goes to the Recycle Bin."""
        with self.lock:
            slot = self.slot_of(folder)
            if slot is None or getattr(slot, 'disc', False) or self.busy or self.scanning:
                return
            if savedata.running_rpcs3():
                self.show_result(False, savedata.close_first(), ["A roster can only be removed while the game is closed."])
                return
            self.ask(f"Move \"{slot.name}\" to the {X.BIN_NAME}?",
                     [f"{slot.region} game, folder {slot.folder}, saved {X.friendly_date(slot.modified)}.",
                      f"You can take it out of the {X.BIN_NAME} again. Your other rosters are not changed."],
                     [(f"Move to the {X.BIN_NAME}", 'yes', 'danger'), ("Keep it", 'no', 'plain')],
                     {'yes': lambda: self.delete_save(folder)})

    def delete_save(self, folder):
        with self.lock:
            slot = self.slot_of(folder)
            if slot is None or getattr(slot, 'disc', False) or self.busy or self.scanning or self.rpcs3 is None:
                return
            if self.editor_busy():
                self.show_result(False, "The roster was not removed", ["The Roster editor is working. Try again in a moment."])
                return
            try:
                savedata.trash_save(self.rpcs3.savedata, folder)
            except savedata.DeleteError as err:
                self.show_result(False, "The roster was not removed", [str(err)])
                return
            if self.editor is not None and getattr(self.editor, 'source', None) and self.editor.source[1] == folder:
                self.editor.source = None       # an update may give the same folder name to a new roster
            self.slots = [s for s in self.slots if s.folder != folder]
            if self.selected == folder:
                self.selected = None
            where = self.rpcs3.where
            self.show_result(True, f"\"{slot.name}\" is in the {X.BIN_NAME}",
                             [f"The {slot.region} roster in folder {folder} was removed from the game's saves. "
                              f"Take it out of the {X.BIN_NAME} to get it back."])
        self.say(f"Moved the roster \"{slot.name}\" ({folder}) to the {X.BIN_NAME}.")
        self.set_rpcs3(where, quiet=True)

    # --- what to update, how to save ------------------------------------------------------------------
    def set_step(self, key, on):
        with self.lock:
            if self.busy:
                return
            on = bool(on)
            if key in self.steps:
                self.steps[key] = on
            elif key in S.PICTURE_KEYS or key == S.PICTURES:
                if on and (self.rpcs3 is not None and self.rpcs3.plain and not self.export_mode
                           or self.export_mode and not self.export_games()):
                    return
                for k in S.row_parts(S.GROUP if key == S.PICTURES else (key,)):    # the group row switches all its parts together
                    if k == S.PHOTOS:
                        self.photos = on
                    else:
                        self.art_on[k] = on
                    if on:
                        self.marks.pop(k, None)
                if on:
                    self.download_pictures()
                elif not self.packs_wanted():
                    self._fetch_stop.set()      # what is already on this PC stays, for the next time it is on
            elif key == S.EDITS:
                self.use_edits = on
            else:
                return
            if on:
                self.marks.pop(key, None)       # a switch turned on again cancels its "Restore"
            self.save_settings()
            self.changed()

    # --- step 2: the game patch -----------------------------------------------------------------------
    def patchable(self):
        """None when Patch / Unpatch can run now, else why not (shown on the card)."""
        if self.export_mode or self.rpcs3 is None or self.rpcs3.plain:
            return X.PATCH_NEEDS_RPCS3
        if not self.rpcs3.patchable:
            return X.PATCH_NATIVE
        if not self.versions:
            return X.PATCH_NEEDS_GAME
        return None                     # RPCS3 running: Patch / Unpatch say so when pressed

    def patch(self):
        """Step 2's Patch button: the game patch into every version RPCS3 has (the first time after a question)."""
        with self.lock:
            if self.busy or self.scanning or self.rpcs3 is None or not self.rpcs3.patchable:
                return
            if savedata.running_rpcs3():
                self.running = True
                self.show_result(False, self._named("Close RPCS3 first"), [self._named("The game can only be patched while RPCS3 is closed.")])
                return
            if not self.settings.get(S.PATCH_ASKED) or self.rpcs3.native:
                self.ask("32 teams and the year 2026", X.PATCH_ASK_NATIVE if self.rpcs3.native else X.PATCH_ASK,
                         [("Patch the game", 'yes', 'primary'), ("Cancel", 'no', 'plain')], {'yes': self._patch_asked})
                return
        self._patch()

    def _patch_asked(self):
        with self.lock:
            self.settings[S.PATCH_ASKED] = True
            S.save(self.settings)
        self._patch()

    def _patch(self):
        with self.lock:
            if self.busy or self.rpcs3 is None or not self.rpcs3.patchable:
                return
            rpcs3, titles, intro, login = self.rpcs3, list(self.versions), self.skip_intro, self.no_login
            self._begin("Patching...")

        def work():
            messages = []
            done = patchinstall.install_patch(rpcs3, titles, intro=intro, login=login, say=messages.append)
            return done, messages

        def done(result):
            titles, messages = result
            with self.lock:
                self._fit_check = True
            self._finish()
            self.say(*messages)
            with self.lock:
                self.at = 1.0
                where = " and ".join(savedata.region(t) for t in titles)
                self.result = None          # step 2 says it: the rosters keep their room
                self.status = (X.patched_status(where), 'good')
                self.changed()

        jobs.run(work, done=done, failed=self._failed_patch_in,
                 expected=(patchinstall.PatchError, datasource.Offline, StockError, OSError))

    def _failed_patch_in(self, message):
        self._finish()
        self.say(message)
        with self.lock:
            self.at = 0.0
            self.status = ("The game is not patched.", 'bad')
            self.show_result(False, "The game was not patched", [message, self._named("Nothing in RPCS3 was changed.")])

    def set_patch_switch(self, key, on):
        """"Skip the intro" / "No pop ups at start": kept for the next Patch, and put into a patched game at once."""
        with self.lock:
            if self.busy or key not in (S.SKIP_INTRO, S.NO_LOGIN, S.EXPORT_PATCH):
                return
            on = bool(on)
            if key == S.EXPORT_PATCH:       # the export holds the game patch: nothing in RPCS3 changes
                self.export_patch = on
                self.settings[S.EXPORT_PATCH] = on
                S.save(self.settings)
                self.changed()
                return
            patched = [] if self.export_mode else self._patched()      # an export never touches RPCS3's patch
            if patched and savedata.running_rpcs3():
                self.running = True
                self.show_result(False, "Close RPCS3 first", ["The game patch can only be changed while RPCS3 is closed."])
                self.changed()
                return
            if key == S.SKIP_INTRO:
                self.skip_intro = on
            else:
                self.no_login = on
            self.save_settings()
            if patched:
                try:
                    patchinstall.set_switches(self.rpcs3, patched, self.skip_intro, self.no_login)
                    self.patch_state = patchinstall.state(self.rpcs3)
                except (patchinstall.PatchError, OSError) as err:
                    self.show_result(False, "The game patch was not changed", [str(err)])
            self.changed()

    def _patched(self):
        """The versions patched now (title ids)."""
        return [t for t, st in self.patch_state.items() if st.get('patched')]

    def unpatch(self):
        """Step 2's Unpatch button: the game patch out of RPCS3, after a question."""
        with self.lock:
            if self.busy or self.rpcs3 is None or not (self.rpcs3.patchable or self.rpcs3.native):
                return
            if savedata.running_rpcs3():
                self.running = True
                self.show_result(False, self._named("Close RPCS3 first"), [self._named("The game can only be unpatched while RPCS3 is closed.")])
                return
            self.ask("Unpatch the game", [self._named(line) for line in X.UNPATCH_ASK], [("Unpatch", 'yes', 'primary'), ("Cancel", 'no', 'plain')],
                     {'yes': self._unpatch})

    def _unpatch(self):
        with self.lock:
            if self.busy or self.rpcs3 is None:
                return
            rpcs3 = self.rpcs3
            self._begin("Unpatching...")

        def work():
            messages = []
            patchinstall.remove(rpcs3, say=messages.append)
            return messages

        def done(messages):
            with self.lock:
                self._fit_check = True
            self._finish()
            self.say(*messages)
            with self.lock:
                self.at = 1.0
                self.result = None
                self.status = (X.UNPATCHED, 'good')
                self.changed()

        jobs.run(work, done=done, failed=self._failed_patch, expected=(patchinstall.PatchError,))

    def _failed_patch(self, message):
        self._finish()
        self.say(message)
        with self.lock:
            self.at = 0.0
            self.status = ("The game is still patched.", 'bad')
            self.show_result(False, "The game patch is still in", [message])

    def toggle_restore(self, key):
        """A row's Restore button: that part is put back as the game had it in the next save (again: undo)."""
        with self.lock:
            if self.busy or self.scanning or self.export_mode:
                return
            if key == S.PICTURES:           # the group row: Restore for every part in it (again: undo)
                if any(k in self.marks for k in S.GROUP):
                    for k in S.row_parts(S.GROUP):
                        self.marks.pop(k, None)
                else:
                    for k in S.row_parts(S.GROUP):
                        self.marks[k] = restore.picture_part(k)
                    self.photos = False
                    for k in S.row_parts(S.GROUP[1:]):
                        self.art_on[k] = False
                    self.save_settings()
            elif key in self.marks:
                for k in S.row_parts((key,)):
                    self.marks.pop(k, None)
            elif key in S.PICTURE_KEYS:
                for k in S.row_parts((key,)):
                    self.marks[k] = restore.picture_part(k)
                    if k == S.PHOTOS:
                        self.photos = False
                    else:
                        self.art_on[k] = False
                self.save_settings()
            elif key in self.steps:
                self.marks[key] = restore.CALENDAR if key == pipeline.SCHEDULE else restore.ROSTERS
                self.steps[key] = False
                self.save_settings()
            self.changed()

    def set_save_mode(self, mode):
        with self.lock:
            if self.busy or mode not in (S.IN_PLACE, S.AS_NEW):
                return
            self.save_mode = mode
            self.settings[S.SAVE_MODE] = mode
            S.save(self.settings)
            self.name_edited = False
            slot = self.selected_slot()
            self.name = slot.name if self.in_place(slot) else savedata.default_name()
            self.changed()
        if self.editor is not None:
            self.editor.changed()

    def set_save_for(self, value):
        with self.lock:
            if self.busy or value not in ('EU', 'NA', S.BOTH):
                return
            self.save_pick = value
            self.settings[S.SAVE_BOTH] = value == S.BOTH
            S.save(self.settings)
            self.changed()

    def set_name(self, text):
        with self.lock:
            if self.busy:
                return
            self.name = str(text)
            self.name_edited = True
            self.changed()

    # --- the update ---------------------------------------------------------------------------------
    def restore_default(self):
        """The big button: everything back as the game had it, after a question."""
        with self.lock:
            slot = self.selected_slot()
            if slot is None or self.busy or self.scanning or self.export_mode:
                return
            where = (f"\"{slot.name}\" is replaced (its old version is copied to the backups folder first)"
                     if self.in_place(slot) else "A new roster is saved next to your others; nothing you have is replaced")
            self.ask("Restore default",
                     ["This puts back the game's own rosters, calendar, pictures, team names and jerseys, and takes "
                      "the game patch out.",
                      f"{where}. RPCS3 must be closed."],
                     [("Restore default", 'yes', 'primary'), ("Cancel", 'no', 'plain')],
                     {'yes': lambda: self.start(everything=True)})

    def start(self, everything=False, waited=False):
        with self.lock:
            if self.export_mode:
                self._start_export(waited)
                return
            slot = self.selected_slot()
            fit, self._fit = slot is not None and self._fit == slot.folder, None    # "Update it now": in place
            steps = [] if everything else [s for s in self.step_keys if self.steps[s]]
            parts = set(restore.ALL_PARTS) if everything else set(self.marks.values())
            if slot is None or self.busy or self.scanning or not (steps or parts) or self.rpcs3 is None:
                return
            self.save_settings()
            in_place = fit or self.in_place(slot)
            if in_place and savedata.running_rpcs3():
                self.show_result(False, savedata.close_first(), ["A roster can only be updated while the game is closed."])
                return
            # the editor saving pictures writes the same lists of pictures as an update: one at a time
            if self.editor_busy() and (in_place or getattr(self.editor, 'saving_pictures', False)):
                self.show_result(False, "The roster was not updated", ["The Roster editor is working. Try again in a moment."])
                return
            if fit:
                name = None
            elif in_place:      # a rename only when the player changed the name
                name = self.name.strip() if self.name_edited and self.name.strip() != slot.name else None
            else:
                name = self.name.strip() if self.name_edited and self.name.strip() else savedata.default_name()
            shown = self.parts_on()
            art = self.rpcs3 if shown and not self.rpcs3.plain and not everything else None
            if art is not None and not waited and self.packs_wanted() and (self._fetching or self.fetch == 'failed'):
                self.waiting = everything           # the pictures first; a failed download is tried once more
                self._fit = slot.folder if fit else None
                self.busy, self.at = True, self.fetch_at
                self.status = (X.PHOTOS_WAITING.format(pct=int(self.fetch_at * 100)), 'body')
                self.changed()
                self.download_pictures()
                return
            self._begin("Updating... (the last result is shown until the new one is ready)")
            self.photos_running = art is not None
            self.pictures_short = [n for n in self.packs_wanted() if not packs.have(n)] if art is not None else []
            mine = (my_edits.load(), my_edits.load_teams()) if self.use_edits and not everything else (None, None)
            rpcs3, targets = self.rpcs3, [slot.title_id] if fit else self.save_targets(slot)

        def work():
            default = restore.default_slot(rpcs3, slot.title_id) if parts else None
            result = pipeline.update(rpcs3.savedata, slot.folder, steps, name, self.say,
                                     art_rpcs3=art, art_parts=shown, my_edits=mine[0] or None, team_edits=mine[1] or None,
                                     targets=targets, disc=slot if getattr(slot, 'disc', False) else None,
                                     in_place=in_place, restore_parts=parts, default=default,
                                     rpcs3=None if rpcs3.plain else rpcs3)
            return result, savedata.running_rpcs3() is not None

        def context():
            return update_context(rpcs3, slot, targets, steps, parts, in_place, photos=art is not None,
                                  edits=bool(mine[0] or mine[1]))

        self._context = context
        jobs.run(work, done=lambda r: self._done(*r), failed=self._failed, context=context,
                 expected=(layout.LayoutError, datasource.Offline, FileNotFoundError, ArtError, StockError,
                           savedata.InPlaceError, patchinstall.PatchError))

    def _begin(self, dim_title):
        self.busy, self.at, self.last_report = True, 0.0, None
        if self.result:                 # the last result stays, greyed, until the new one is ready
            self.result['dim'] = dim_title
        self.status = ("Starting...", 'body')
        self.host.log_clear()
        self.changed()

    def _finish(self):
        with self.lock:
            self.busy = False
            where = self.rpcs3.where if self.rpcs3 else None
        if not self.export_mode:
            self.set_rpcs3(where, quiet=True)

    def apply_names(self):
        """The Team names row's button: the picked roster's team names into the game now, nothing else."""
        with self.lock:
            slot = self.selected_slot()
            if self._names_blocked(slot):
                return
            rpcs3, targets = self.rpcs3, self.save_targets(slot)
            teams = my_edits.load_teams() if self.use_edits else None
            self._begin("Writing the team names...")

        def work():
            messages = []
            with open(slot.sys_data, 'rb') as f:
                pipeline.apply_names(rpcs3, f.read(), slot.title_id, targets, teams, say=messages.append)
            return messages

        def done(messages):
            self._finish()
            self.say(*messages)
            with self.lock:
                self.art_installed = art_installed()
                self.at = 1.0
                self.status = (X.NAMES_DONE, 'good')
                self.show_result(True, "Team names", [X.NAMES_DONE])

        jobs.run(work, done=done, failed=self._failed, expected=(ArtError, OSError, ValueError))

    def _names_blocked(self, slot):
        return (self.busy or self.scanning or self.export_mode or slot is None or getattr(slot, 'disc', False)
                or self.rpcs3 is None or self.rpcs3.plain)

    def _failed(self, message):
        self._finish()
        self.say(message)
        with self.lock:
            self._fail("Nothing was saved", [message, "Your existing rosters are untouched."])

    def _fail(self, title, lines):
        self.at = 0.0
        self.status = ("Nothing was saved.", 'bad')
        self.show_result(False, title, lines, [("Show details", 'details')])

    def _done(self, result, rpcs3_running):
        self._finish()
        items = result.build.lines() + [("Restored", text) for text in result.restored]
        if self.pictures_short:
            items.append(("Pictures", X.pictures_short(self.pictures_short)))
        self.say("", "What changed:", *(f"   {title}: {text}" for title, text in items))
        with self.lock:
            self.last_report = result.report_path
            if result.exported and result.slot is not None:
                self._export_folder = os.path.dirname(result.exported)
                self.at = 1.0
                self.status = ("Done: SYS-DATA exported.", 'good')
                self.show_result(True, "SYS-DATA exported",
                                 [f"New file: {result.exported}", X.HOW_TO_USE_EXPORT, "No pictures are in it: they need RPCS3."],
                                 [("Open the folder", 'export_folder'), ("List of changes", 'report')],
                                 items=items or [("Result", "Nothing needed changing.")])
                said = [f"Done. {X.HOW_TO_USE_EXPORT}"]
            elif result.slot is None:
                problems = result.build.problems
                if problems:
                    jobs.log_block(self._context_lines() + ["the safety checks failed:"]
                                   + [f"  - {p}" for p in problems[:40]])
                self._fail("The new roster failed the safety checks, so nothing was saved",
                           problems[:3] + ["Your existing rosters are untouched."])
                said = ["   - " + p for p in problems[:15]]
            else:
                for what, text, details in getattr(result, 'after', []):
                    jobs.log_block(self._context_lines() + [f"after the save: {what}: {text}", details.rstrip()])
                said = self._saved(result, rpcs3_running, items)
        self.say(*said)

    def _context_lines(self):
        context = getattr(self, '_context', None)
        try:
            return list(context()) if context else []
        except Exception as err:
            return [f"(the details could not be gathered: {err})"]

    def _saved(self, result, rpcs3_running, items):
        """The result box of a saved roster; returns the lines for the details."""
        said = []
        thin = result.build.info.get('thinner_ahl_teams') or []
        if thin:
            said.append(f"Note: {len(thin)} AHL teams lost players to NHL rosters and are short-handed. "
                        "Switch on \"AHL rosters\" to fill them with their real players.")
        art = result.art_line()
        if art:
            said.append(art)
        patched = result.patch_lines()
        said += patched
        how = X.HOW_TO_LOAD_IN_PLACE if result.in_place else X.HOW_TO_LOAD
        said.append(f"Done. {how}")
        self.name_edited = False
        self.at = 1.0
        buttons = [("List of changes", 'report'), ("Open save folder", 'save_folder')]
        self._backup = result.backup if result.in_place else None
        if self._backup:
            buttons.insert(1, ("Open backup folder", 'backup'))
        if not rpcs3_running and self.rpcs3 is not None and not self.rpcs3.plain:
            buttons.append((f"Start {self.rpcs3.name}", 'start_rpcs3'))
        name = result.slot.name
        if result.in_place:
            if self.editor is not None:
                self.editor.source = None       # the editor shows what the file is now
            where = ("The roster is already the same as the new one: nothing was changed." if result.unchanged
                     else f"Updated: {result.saved_where()}.")
            lines = [where] + ([f"The old roster is kept in {result.backup}"] if result.backup else []) \
                + list(result.restored) + ([art] if art else []) + patched + [how]
            title = f"Already up to date: \"{name}\"" if result.unchanged else f"Updated \"{name}\""
            self.status = (f"Done: {'already up to date' if result.unchanged else 'updated'} \"{name}\".", 'good')
        else:
            where = f"New save: {result.saved_where()}."
            lines = [where] + list(result.restored) + ([art] if art else []) + patched + [how]
            title = f"Saved as \"{name}\""
            self.status = (f"Done: saved as \"{name}\".", 'good')
        said.append(where)
        bad = [f"{what}: {text}" for what, text, _details in getattr(result, 'after', [])]
        if bad:                     # the roster is saved all the same: say so, and where the details are
            bad.append(X.SAVED_DESPITE.format(log=datasource.app_dir('logs', 'error.log')))
            buttons.append(("Error log", 'error_log'))
            self.status = (self.status[0] + " " + X.SAVED_SOME_FAILED, 'bad')
        self.show_result(True, title, lines, buttons, items=items or [("Result", "Nothing needed changing.")], bad=bad)
        said[:0] = bad
        return said

    def result_action(self, action):
        if action == 'report':
            if self.last_report and os.path.exists(self.last_report):
                self.host.open_path(self.last_report)
        elif action == 'save_folder':
            if self.rpcs3:
                self.host.open_path(self.rpcs3.savedata)
        elif action == 'backup':
            if self._backup:
                self.host.open_path(self._backup)
        elif action == 'export_folder':
            if self._export_folder:
                self.host.open_path(self._export_folder)
        elif action == 'export_how':
            with self.lock:
                if self._export_result is not None and self.dialog is None:
                    self._ask_export(self._export_result)
        elif action == 'start_rpcs3':
            self.start_rpcs3()
        elif action == 'update_page':
            if self._update_page:
                self.host.open_url(self._update_page)
        elif action == 'details':
            self.host.send('details', {'open': True})
        elif action == 'error_log':
            path = datasource.app_dir('logs', 'error.log')
            if os.path.exists(path):
                self.host.open_path(path)
        elif action == 'close':
            self.hide_result()

    def start_rpcs3(self):
        if self.rpcs3 and not self.rpcs3.plain and not savedata.running_rpcs3():
            self.rpcs3.start()

    def remove_photos(self):
        """Put back every game file the photos and logos replaced."""
        with self.lock:
            if self.busy:
                return
            messages = []
            try:
                remove_art(say=messages.append)
            except ArtError as err:
                self.show_result(False, "The photos and logos are still there", [str(err)])
                return
            self.art_installed = art_installed()
            self.show_result(True, "The game's own pictures are back", messages + ["Your rosters are not changed."])
        self.say(*messages)

    def closing(self):
        """May the window close now? Not while a roster is being written."""
        with self.lock:
            if not self.busy or self.quitting or self.waiting is not None:
                return True             # a download cut short leaves a piece that the next start removes
            self.ask("Please wait", ["A roster is being made right now. Close the window when it is done, so no "
                                     "half-written roster is left behind."], [("OK", 'ok', 'primary')], {})
            return False

    # --- "Export files to a folder" (export.py): the update's files in a new folder, RPCS3 untouched ------------
    def set_export_only(self, on):
        with self.lock:
            if self.busy:
                return
            self.export_mode = bool(on)
            self.settings[S.EXPORT_ONLY] = self.export_mode
            S.save(self.settings)
            self.result = None
            self.status = None
            self.name_edited = False
            self.name = savedata.default_name()
            where = self.rpcs3.where if self.rpcs3 else self.settings.get('rpcs3')
            if self.export_mode and self.selected_slot() is None and self.export_file is not None:
                self.export_from_file = True
            self.changed()
        if where:
            self.set_rpcs3(where, quiet=True)       # the lists follow the mode (the game's own roster of a game pointed at)

    def export_games(self):
        """{title id: the game} an export can make pictures, the game patch and the game's own roster from: the ones
        RPCS3 lists, else the ones the player pointed at (settings 'games')."""
        found, picked = {}, self.settings.get('games') or {}
        for title in savedata.GAMES:
            path = self.rpcs3.game_disc(title) if self.rpcs3 is not None and not self.rpcs3.plain else None
            path = path or (picked.get(title) if picked.get(title) and os.path.exists(picked[title]) else None)
            if path:
                found[title] = path
        return found

    def _export_discs(self):
        """The game's own roster of each game the player pointed at, when there is no RPCS3 to list it (an export)."""
        if self.rpcs3 is not None and not self.rpcs3.plain:
            return []
        return [savedata.DiscSlot(t, p) for t, p in self.export_games().items()]

    def _export_source(self):
        """What the export starts from: a roster file (SYS-DATA) or a roster of RPCS3 (a savedata.Slot), else None."""
        if self.export_from_file and self.export_file:
            return self.export_file
        slot = self.selected_slot()
        if slot is not None and self.usable.get(slot.folder) is None:
            return slot
        return self.export_file

    def _export_targets(self, source):
        """The versions of the game the export is made for (title ids): the source's own, or as "Save for" says."""
        own = savedata.title_of('EU') if isinstance(source, str) else source.title_id
        if self.save_pick == S.BOTH:
            return [own] + [t for t in savedata.GAMES if t != own]
        if self.save_pick in ('EU', 'NA'):
            return [savedata.title_of(self.save_pick)]
        return [own]

    def pick_export_file(self):
        with self.lock:
            if self.busy:
                return
            start = os.path.dirname(self.export_file) if self.export_file else os.path.expanduser('~')
        path = self.host.ask_open("Pick the roster file (SYS-DATA)", ['Roster file (SYS-DATA)', 'All files (*.*)'], start)
        if not path:
            return
        self.use_export_file(os.path.normpath(path))

    @staticmethod
    def _untouched(path):
        """Is `path` the game's own roster as the disc has it (it cannot start an export: the disc roster is picked instead)?"""
        from .. import stock
        try:
            return stock.untouched(Roster(path))
        except (layout.LayoutError, ValueError, KeyError, OSError):
            return False

    def use_export_file(self, path):
        try:
            layout.check_base(Roster(path))
            from .. import stock
            if stock.untouched(Roster(path)):
                raise layout.LayoutError(X.GAME_ROSTER_FILE)
            problem = None
        except (layout.LayoutError, ValueError, KeyError, OSError) as err:
            problem = "That file cannot be used: " + X.short_reason(str(err))[len("Cannot be used: "):]
        with self.lock:
            if problem:
                self.export_file, self.export_problem = None, problem
            else:
                self.export_file, self.export_problem = path, None
                self.export_from_file = True
                self.settings[S.EXPORT_FILE] = path
                self.settings[S.EXPORT_FROM_FILE] = True
                S.save(self.settings)
            self.changed()

    def _start_export(self, waited=False):
        steps = [s for s in self.step_keys if self.steps[s]]
        source = self._export_source()
        if source is None or self.busy or self.scanning or not steps:
            return
        self.save_settings()
        games = self.export_games()
        shown = self.parts_on()
        photos = bool(shown) and bool(games)
        if photos and not waited and self.packs_wanted() and (self._fetching or self.fetch == 'failed'):
            self.waiting = False                    # the pictures first; a failed download is tried once more
            self.busy, self.at = True, self.fetch_at
            self.status = (X.PHOTOS_WAITING.format(pct=int(self.fetch_at * 100)), 'body')
            self.changed()
            self.download_pictures()
            return
        self._begin("Working... (the last result is shown until the new one is ready)")
        self.photos_running = photos
        self.pictures_short = [n for n in self.packs_wanted() if not packs.have(n)] if photos else []
        mine = (my_edits.load(), my_edits.load_teams()) if self.use_edits else (None, None)
        name = self.name.strip() if self.name_edited and self.name.strip() else savedata.default_name()
        rpcs3, targets, patch = self.rpcs3, self._export_targets(source), self.export_patch
        intro, login = self.skip_intro, self.no_login
        label = source if isinstance(source, str) else f"{source.name} ({source.folder})"

        def work():
            return export.run(None, source, rpcs3=rpcs3, steps=steps, targets=targets, name=name, photos=photos,
                              game_patch=patch, intro=intro, login=login, my_edits=mine[0] or None,
                              team_edits=mine[1] or None, progress=self.say, games=games, art_parts=shown)

        def context():
            return [f"export from {label}{'' if not isinstance(source, str) or os.path.exists(source) else '  (missing)'}",
                    f"steps: {', '.join(steps)}", f"for: {', '.join(targets)}; photos: {photos}; game patch: {patch}"]

        self._context = context
        jobs.run(work, done=self._export_done, failed=self._failed, context=context,
                 expected=(layout.LayoutError, datasource.Offline, FileNotFoundError, OSError, ArtError, StockError,
                           export.ExportError, patchinstall.PatchError))

    def _export_done(self, res):
        self._finish()
        update = res.update
        items = update.build.lines()
        if self.pictures_short:
            items.append(("Pictures", X.pictures_short(self.pictures_short)))
        self.say("", "What changed:", *(f"   {title}: {text}" for title, text in items))
        with self.lock:
            self.last_report = update.report_path
            if res.folder is None:
                problems = update.build.problems
                if problems:
                    jobs.log_block(self._context_lines() + ["the safety checks failed:"] + [f"  - {p}" for p in problems[:40]])
                self._fail("The new roster failed the safety checks, so nothing was exported",
                           problems[:3] + ["Nothing was written."])
                said = ["   - " + p for p in problems[:15]]
            else:
                bad = list(res.after)
                self._export_result, self._export_folder = res, res.folder
                self.at = 1.0
                self.status = ("Done: the files are ready.", 'bad' if bad else 'good')
                self.show_result(True, "Your files are ready", [f"They are in: {res.folder}", "Nothing in RPCS3 was changed."],
                                 [("Open the folder", 'export_folder'), ("How to install", 'export_how'),
                                  ("List of changes", 'report')],
                                 items=items or [("Result", "Nothing needed changing.")], bad=bad)
                self._ask_export(res)
                said = [f"Done. The files are in {res.folder}"] + bad
        self.say(*said)

    def _ask_export(self, res):
        """The pop-up "Your files are ready": one row per folder, what to tick, how to load, how to undo."""
        self.ask(export.TITLE, [f"The files are in: {res.folder}"] + list(res.intro),
                 [("Open folder", 'open', 'primary', True), ("Copy text", 'copy', 'plain', True), ("Close", 'close', 'plain')],
                 {'open': lambda: self.host.open_path(res.folder), 'copy': lambda: None},
                 rows=res.rows, notes=res.notes, copy=res.text, wide=True)

    # --- what the tab shows -------------------------------------------------------------------------
    def snapshot(self):
        with self.lock:
            slot = self.selected_slot()
            export = self.export_mode
            source = self._export_source() if export else None
            ready = (source is not None and not self.busy and not self.scanning) if export else \
                (slot is not None and not self.busy and not self.scanning)
            plain = self.rpcs3 is not None and self.rpcs3.plain
            any_step = any(self.steps.values()) or (bool(self.marks) and not export)
            in_place = self.in_place(slot) and not export
            room = {} if export else self._room()
            hidden = set().union(*(h for _, h in room.values())) if room else set()
            full = [t for t in self.save_targets(slot) if t in room and room[t][0] >= savedata.GAME_LISTS] \
                if slot is not None and not in_place and not export else []
            return {
                'busy': self.busy, 'scanning': self.scanning,
                'rpcs3': self._rpcs3_view(export),
                'patch': self._patch_view(),
                'export': self._export_view(export, source),
                'fresh': [{'folder': s.folder, 'label': f"New from {s.region} disc", 'region': s.region}
                          for s in self._fresh(export)],
                'empty': None if self.slots else ("Looking for your rosters..." if self.scanning else
                                                  "No RPCS3 rosters are listed. Pick RPCS3 in step 1, or use a roster file." if export else
                                                  "Pick your game first. Your rosters will be listed here."),
                'rosters': [self._roster_view(s, hidden) for s in self.slots],
                'room': self._room_view(room, export),
                'selected': self.selected,
                'steps': self._steps_view(export, plain),
                'later': ("Coming later:  " + "  ·  ".join(n.split(' (')[0] for n in pipeline.planned(self.pack))
                          if pipeline.planned(self.pack) else None),
                'restore_all': {'shown': not export, 'enabled': ready and not export},
                'save': self._save_view(slot, export, in_place, ready, any_step, full),
                'result': self.result,
                'status': self._status_view(slot, export, ready, any_step, full),
                'progress': {'value': round(self.at, 4), 'active': self.busy,
                             'indeterminate': self.scanning and not self.busy},
                'dialog': self.dialog,
                'check_updates': self.settings.get('check_updates', True) is not False,
                'downloads': self._downloads_view(),
            }

    def _fresh(self, export):
        """The game's own roster of each game known (a disc slot): RPCS3's list, and in an export the games pointed at."""
        found = [s for s in self.slots if getattr(s, 'disc', False)]
        if export:
            found += [s for s in self._export_discs() if all(s.folder != f.folder for f in found)]
        return found

    def _export_view(self, export, source):
        """Setup's roster card and the Update tab's top bar in an export: where the new roster starts from."""
        if not export:
            return {'on': False, 'file': self.export_file, 'text': '', 'tone': 'muted', 'from_file': False, 'game': None}
        if self.export_problem:
            text, tone = self.export_problem, 'bad'
        elif source is None:
            text, tone = X.EXPORT_PICK, 'muted'
        elif isinstance(source, str):
            text, tone = f"Roster file: {source}", 'good'
        else:
            text, tone = f"{source.name} ({source.region})", 'good'
        games = self.export_games()
        return {'on': True, 'file': self.export_file, 'text': text, 'tone': tone,
                'from_file': isinstance(source, str), 'patch': self.export_patch,
                'game': None if games else X.EXPORT_GAME, 'why': X.EXPORT_WHY}

    def _downloads_view(self):
        """The Setup tab's Downloads card: the pictures (downloaded by themselves) and the player data."""
        running = self.fetch == 'running'
        pictures = (X.PHOTOS_RUNNING.format(pct=int(self.fetch_at * 100)) if running else
                    X.PHOTOS_READY if self.fetch == 'ready' else
                    X.PHOTOS_RETRY if self.fetch == 'failed' else X.photos_will(self.fetch_size))
        try:
            made = datetime.date.fromisoformat(str((self.pack or {}).get('generated') or '')[:10])
            made = f"{made.day} {made:%b %Y}"
        except ValueError:
            made = ''
        return [{'title': "Pictures", 'text': pictures, 'tone': 'good' if self.fetch == 'ready' else
                 'amber' if self.fetch == 'failed' else 'muted', 'bar': round(self.fetch_at, 3) if running else None},
                {'title': "Rosters, ratings, contracts and the calendar",
                 'text': f"Data from {made}" if made else "No data available",
                 'tone': 'good' if made else 'muted', 'bar': None}]

    def _rpcs3_view(self, export):
        if self.rpcs3 is None:
            if self.scanning:
                note, tone = "Looking for your rosters...", 'muted'
            elif export:
                note, tone = X.EXPORT_RPCS3, 'muted'
            elif self.problem:
                note, tone = self.problem, 'bad'
            else:
                note, tone = savedata.PICK_RPCS3 + " The program finds your saves from there.", 'muted'
        elif self.scanning and not self.slots:
            note, tone = "Looking for your rosters...", 'muted'
        else:
            note, tone = X.rpcs3_note(self.rpcs3, self.slots), 'info'
        if export:
            needs_game = not self.export_games()
        else:
            needs_game = bool(self.rpcs3 and not self.rpcs3.plain and not self.rpcs3.disc_slots())
        native_host = self.rpcs3 is not None and self.rpcs3.native
        return {'path': self.rpcs3.where if self.rpcs3 else None, 'note': {'text': note, 'tone': tone} if note else None,
                'needs_game': needs_game, 'find_label': "Find your game",
                'enabled': not self.busy, 'kind': self.rpcs3.name if self.rpcs3 and not self.rpcs3.plain else None,
                'native': X.NATIVE_NOTE if native_host else None, 'warnings': native.notes(self.rpcs3) if native_host else [],
                'other': (self._other_host() or (None,))[0]}

    def _patch_view(self):
        """Step 2: is the game patched, the two small switches, Patch / Unpatch."""
        if self.export_mode:
            return self._patch_export_view()
        why = self.patchable()
        port = why == X.PATCH_NATIVE
        native_host = self.rpcs3 is not None and self.rpcs3.native
        left = port and any(st.get('stale') for st in self.patch_state.values())    # only Unpatch: the port changed under the patch
        off = (port and not left) or why == X.PATCH_NEEDS_RPCS3
        patched = [t for t, st in self.patch_state.items() if st.get('patched') or st.get('stale')] \
            if not off else []                              # stale: patched before update 1.01 was known
        old = [t for t in patched if self.patch_state[t].get('version') != gamepatch.TEAMS_VERSION
               or self.patch_state[t].get('stale')]
        missing = [t for t in self.versions if t not in patched]
        free = not self.busy and not self.scanning and (why is None or left)
        if off or left:
            state = {'text': why, 'tone': 'amber' if left else 'muted'}
        elif patched:
            state = {'text': X.patch_state(self.patch_state, old, missing), 'tone': 'amber' if old or missing else 'good'}
        else:
            state = {'text': X.NOT_PATCHED, 'tone': 'muted'}
        buttons = []
        if not off and self.versions:
            if left:
                label = None
            elif old:
                label = "Patch again"
            elif not patched:
                label = "Patch the game"
            elif missing:
                label = "Patch " + " and ".join(savedata.region(t) for t in missing) + " too"
            else:
                label = None
            if label:
                buttons.append({'label': label, 'call': 'patch', 'enabled': free, 'kind': 'gold'})
            if patched:
                buttons.append({'label': "Unpatch", 'call': 'unpatch', 'enabled': free, 'kind': 'gold-line'})
        switch = not self.busy and not off
        note = None if off else why
        return {'title': X.PATCH_TITLE, 'sub': X.PATCH_SUB, 'state': state,
                'note': note,
                'info': {'title': X.PATCH_INFO_TITLE,
                         'sections': [{'head': self._named(head), 'items': [self._named(item) for item in items]}
                                      for head, items in (X.PATCH_INFO_NATIVE if native_host else X.PATCH_INFO)]},
                'checks': [] if native_host else     # the port's launcher has its own Skip the intro
                [{'key': S.SKIP_INTRO, 'label': "Skip the intro", 'on': self.skip_intro, 'enabled': switch},
                 {'key': S.NO_LOGIN, 'label': "No pop ups at start", 'tip': X.NO_LOGIN_TIP,
                  'on': self.no_login, 'enabled': switch}],
                'buttons': buttons, 'patched': bool(patched), 'regions': [] if off else self._patch_regions(patched, old)}

    def _patch_export_view(self):
        """The Game patch tab in an export: no Patch / Unpatch (they change RPCS3); a box puts the patch into the export."""
        on = self.export_patch
        switch = not self.busy
        return {'title': X.PATCH_TITLE, 'sub': X.PATCH_SUB,
                'state': {'text': X.EXPORT_PATCH_ON if on else X.EXPORT_PATCH_OFF, 'tone': 'good' if on else 'muted'},
                'note': X.EXPORT_PATCH_NOTE,
                'info': {'title': X.PATCH_INFO_TITLE,
                         'sections': [{'head': head, 'items': items} for head, items in X.PATCH_INFO]},
                'checks': [{'key': S.EXPORT_PATCH, 'label': "Put the game patch in the export", 'on': on, 'enabled': switch},
                           {'key': S.SKIP_INTRO, 'label': "Skip the intro", 'on': self.skip_intro, 'enabled': switch},
                           {'key': S.NO_LOGIN, 'label': "No pop ups at start", 'tip': X.NO_LOGIN_TIP,
                            'on': self.no_login, 'enabled': switch}],
                'buttons': [], 'patched': on, 'regions': []}

    def _patch_regions(self, patched, old):
        """The Game patch tab: one card per version of the game, patched or not, with its rosters."""
        out = []
        for t in self.versions:
            if self.patch_state.get(t, {}).get('stale'):
                state, tone = ("NHL Legacy Native has changed: the patch does not fit it now" if self.rpcs3.native
                               else "The game has update 1.01, the patch is older: patch again"), 'amber'
            elif t in old:
                state, tone = "Patched with an older patch: patch again", 'amber'
            elif t in patched:
                state, tone = "Patched: 32 teams, the year 2026", 'good'
            else:
                state, tone = "Not patched", 'muted'
            rosters = [{'name': s.name, 'tag': "32 teams" if s.folder in self.patch_rosters else None,
                        'misfit': self.misfit(s) is not None}
                       for s in self.slots if s.title_id == t and not getattr(s, 'disc', False)]
            out.append({'region': savedata.region(t), 'title': t, 'state': state, 'tone': tone, 'rosters': rosters})
        return out

    def _room(self):
        """{title id: (roster folders, folders the game does not list)} for the versions in view."""
        where = getattr(self.rpcs3, 'savedata', None)
        if not where:
            return {}
        titles = {s.title_id for s in self.slots} | set(self.versions)
        return {t: (savedata.roster_count(where, t), savedata.hidden_in_game(where, t)) for t in sorted(titles)}

    def _room_view(self, room, export):
        if export or not room:
            return None
        full = any(n >= savedata.GAME_LISTS for n, _ in room.values())
        most = savedata.GAME_LISTS
        counts = [{'region': savedata.region(t),
                   'text': f"{n} of {most}" + (" (full)" if n == most else f", {n - most} not in the game" if n > most else ""),
                   'tone': 'bad' if n >= most else 'amber' if n == most - 1 else 'good'}
                  for t, (n, _) in room.items()]
        near = any(c['tone'] != 'good' for c in counts)       # the note only when it matters (step 2 took the room)
        return {'counts': counts, 'text': X.ROOM_FULL_SHORT if full else X.ROOM_NOTE if near else None,
                'tip': X.ROOM_NOTE, 'tone': 'bad' if full else 'info'}

    def _roster_view(self, s, hidden=frozenset()):
        problem = self.usable.get(s.folder)
        disc = getattr(s, 'disc', False)
        return {'folder': s.folder, 'name': s.name, 'region': s.region,
                'meta': X.DISC_NOTE if disc else f"{s.folder}  |  {X.friendly_date(s.modified)}",
                'tag': "32 teams" if s.folder in self.patch_rosters else None,
                'chip': {'text': "start fresh", 'kind': 'muted'} if disc else
                        {'text': "not in the game", 'kind': 'hidden'} if s.folder in hidden else
                        {'text': "made here", 'kind': 'made'} if s.tool_made and problem is None else None,
                'problem': X.short_reason(problem) if problem else X.HIDDEN_IN_GAME if s.folder in hidden else None,
                'misfit': self.misfit(s),
                'actions': not disc and not self.export_mode, 'usable': problem is None,
                'selected': s.folder == self.selected and not (self.export_mode and self.export_from_file),
                'delete_enabled': not self.busy and not self.scanning}

    def _steps_view(self, export, plain):
        sources = self.pack.get('sources', {})
        notes = {pipeline.NHL: X.NHL_NOTE,
                 pipeline.RATINGS: X.dated(sources.get('ratings_list')),
                 pipeline.NATIONAL: X.dated(sources.get('iihf')),
                 pipeline.SCHEDULE: X.SCHEDULE_NOTE}
        restorable = not export and not self.busy and not self.scanning
        rows = [{'key': k, 'title': pipeline.STEP_LABELS[k], 'sub': notes.get(k) or X.dated(sources.get(k)),
                 'warn': pipeline.left_out_note(self.pack, k), 'hint': None, 'on': self.steps[k],
                 'enabled': not self.busy, 'restore': not export, 'restore_enabled': restorable,
                 'restoring': k in self.marks}
                for k in self.step_keys]
        rows[:0] = [self._photos_row(export, plain, restorable), self._picture_row(S.NAMES, export, plain, restorable)]
        rows.append({'key': S.EDITS, 'title': "My edits", 'sub': "Your changes from the Roster editor, applied after the update",
                     'warn': None, 'hint': X.EDITS_HINT, 'on': self.use_edits, 'enabled': not self.busy,
                     'restore': False, 'restore_enabled': False, 'restoring': False})
        return rows

    def _photos_row(self, export, plain, restorable):
        """First in the list and highlighted: the group "Photos and logos". Its switch turns every part inside on or off
        (the page opens the list of parts with an arrow); the status line says only whether the downloads are here."""
        offered = bool(self.export_games()) if export else not plain      # an export needs the game, not RPCS3
        kids = [self._picture_row(k, export, plain, restorable) for k in S.GROUP]
        for kid in kids:
            kid['child'] = True
        wanted = P.packs_for({k for k in S.row_parts(S.GROUP) if (self.photos if k == S.PHOTOS else self.art_on[k])})
        on = any(kid['on'] for kid in kids)
        here = all(packs.have(n) for n in wanted)
        running = on and self.fetch == 'running' and not here
        if not offered:
            sub = kids[0]['sub']
        elif not on:
            sub = X.PHOTOS_OFF
        elif running:
            sub = X.PHOTOS_RUNNING.format(pct=int(self.fetch_at * 100))
        elif here:
            sub = X.PHOTOS_READY
        elif self.not_served(wanted):
            sub = X.PICTURE_NOT_SERVED
        elif self.fetch == 'failed':
            sub = X.PHOTOS_RETRY
        else:
            sub = X.photos_will(sum(self.pack_sizes.get(n) or X.PICTURE_SIZES.get(n, 0) for n in wanted))
        count = sum(1 for kid in kids if kid['on'])
        every = len(kids)
        if offered and on and count < every:
            sub = f"{count} of {every} parts on. " + sub
        return {'key': S.PICTURES, 'title': X.PHOTOS_TITLE, 'sub': sub, 'warn': None, 'hint': self._named(X.PHOTOS_HINT), 'featured': True,
                'on': on, 'enabled': not self.busy and offered, 'restore': offered and not export,
                'restore_enabled': restorable, 'restoring': any(k in self.marks for k in S.GROUP),
                'bar': round(self.fetch_at, 3) if running else None, 'children': kids}

    def _picture_row(self, key, export, plain, restorable):
        """One of the picture switches (art/parts.py): its status says only whether its download is here."""
        offered = bool(self.export_games()) if export else not plain      # an export needs the game, not RPCS3
        flag = self.photos if key == S.PHOTOS else self.art_on[key]
        title, hint = X.PICTURE_ROWS[key][:2]
        names = P.packs_for(S.row_parts((key,)))        # its downloads (this season's: also the new centre ice's)
        on = flag and offered
        here = all(packs.have(n) for n in names)
        running = on and bool(names) and self.fetch == 'running' and not here
        size = sum(self.pack_sizes.get(n) or X.PICTURE_SIZES.get(n, 0) for n in names)
        if export and not offered:
            sub = X.PHOTOS_EXPORT
        elif plain and not export:
            sub = X.PHOTOS_NEEDS_RPCS3
        elif not flag:
            sub = X.PICTURE_NAMES_OFF if key == S.NAMES else X.PHOTOS_OFF
        elif not names:
            sub = X.PICTURE_NO_DOWNLOAD
        elif running:
            sub = X.PHOTOS_RUNNING.format(pct=int(self.fetch_at * 100))
        elif here:
            sub = X.PHOTOS_READY
        elif self.not_served(names):
            sub = X.PICTURE_NOT_SERVED
        elif self.fetch == 'failed':
            sub = X.PHOTOS_RETRY
        else:
            sub = X.photos_will(size)
        return {'key': key, 'title': title, 'sub': sub, 'warn': None, 'hint': self._named(hint),
                'on': on, 'enabled': not self.busy and offered, 'restore': offered and not export,
                'restore_enabled': restorable, 'restoring': key in self.marks,
                'bar': round(self.fetch_at, 3) if running else None,
                'action': {'label': "Apply names", 'call': 'apply_names', 'tip': X.NAMES_TIP,
                           'enabled': not self._names_blocked(self.selected_slot())}
                if key == S.NAMES and not export and not plain else None}

    def _save_view(self, slot, export, in_place, ready, any_step, full=()):
        if export:
            button = "Working..." if self.busy else "Export files"
        elif self.busy:
            button = "Updating..."
        elif self.marks:
            button = "Update and restore" if any(self.steps.values()) else "Restore"
        else:
            button = "Update roster" if in_place else "Make new roster"
        two = slot is not None and len(self.versions) >= 2 and not in_place and not export
        if export:          # the version is picked here: there may be no RPCS3 to tell which games exist
            source = self._export_source()
            own = savedata.region(savedata.title_of('EU') if isinstance(source, str) or source is None else source.title_id)
            save_for = {'value': self.save_pick or own, 'enabled': not self.busy, 'options': ['EU', 'NA', S.BOTH]}
        else:
            save_for = {'value': self.save_pick or slot.region, 'enabled': not self.busy,
                        'options': ['EU', 'NA', S.BOTH]} if two else None
        return {'mode': (S.IN_PLACE if in_place else S.AS_NEW if slot is not None else self.save_mode),
                'mode_shown': not export, 'mode_enabled': not self.busy,
                'name': self.name, 'name_enabled': not self.busy,
                'save_for': save_for,
                'button': {'text': button, 'enabled': ready and any_step and not full},
                'note': X.EXPORT_SAVE_NOTE if export else self._named(X.SAVE_NOTE)}

    def _status_view(self, slot, export, ready, any_step, full=()):
        if self.busy or (self.result is not None and self.status):
            text, tone = self.status or ("Working...", 'body')
        elif full:
            text, tone = f"{X.ROOM_FULL} ({' and '.join(savedata.region(t) for t in full)})", 'bad'
        elif export:
            text, tone = ("Looking for your rosters..." if self.scanning else
                          "Ready." if ready and any_step else
                          "Pick a roster (Setup) or a roster file first." if not ready and not self.busy else
                          "Switch on at least one thing to update."), 'muted'
        else:
            text, tone = ("Looking for your rosters..." if self.scanning else
                          "Ready." if ready and any_step else
                          "Start with step 1: find your game." if self.rpcs3 is None else
                          "Switch on at least one thing to update." if slot is not None else
                          "None of the rosters found can be updated."), 'muted'
        return {'text': text, 'tone': tone}
