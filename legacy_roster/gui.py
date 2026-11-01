"""The window: say where RPCS3 is, pick a roster, switch on what to update, press one button."""
import datetime
import json
import os
from collections import Counter
import queue
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:      # only when run from source without the window's one extra package
    sys.exit("The window needs the 'customtkinter' package:  pip install customtkinter\n"
             "(the command line works without it:  python -m legacy_roster list --rpcs3 <rpcs3.exe>)")

from . import __version__, datasource, layout, packs, pipeline, restore, savedata
from . import theme as T
from .art.install import ArtError, installed as art_installed, remove as remove_art
from .editor.view import EditorTab
from . import edits as my_edits
from .progress import fraction
from .roster import Roster
from .stock import StockError
from .app.jobs import where as jobs_where
from .app.texts import photos_will
from .gui_state import is_current_scan, sync_packed_order
from .widgets import Banner, Card, Choice, GhostButton, PrimaryButton, RosterRow, SwitchRow, configure_if_changed, flag_image

SETTINGS = 'settings.json'
PHOTOS = 'photos'           # the "Photos and logos" switch in the remembered settings
EDITS = 'edits'             # the "My edits" switch
SAVE_BOTH = 'save_both'     # "Save for: EU + NA" (remembered; a single version follows the roster picked)
BOTH = "EU + NA"
EXPORT_ONLY, EXPORT_FILE = 'export_only', 'export_file'     # "Export only SYS-DATA roster" and the roster file picked for it
SAVE_MODE = 'save_mode'     # how an update is saved (remembered): IN_PLACE or AS_NEW
IN_PLACE, AS_NEW = 'update', 'new'
UPDATE_TAB, EDITOR_TAB = "Update", "Roster editor"
MIN_HEIGHT = 640
SHORT_SCREEN = 900          # screens shorter than this (window units) show the result lines scrolling
BANNER_LINES_SHORT = 64     # ... in this much height (about three lines)
BANNER_LINES_MIN = 40       # the least height the result's lines get when the window has no more room
DETAILS_HEIGHT = 150
ROSTER_MIN = 150            # the roster list (step 2) never gets less than this (window units), result shown or not
SITE = "https://www.puckpeak.com"
SITE_LABEL = "www.puckpeak.com"
TAGLINE = "NHL & hockey analytics like never before"
HOW_TO_LOAD ="In the game: Customize > Save/Load/Delete > Load > Rosters, pick it, then save the roster once so it stays active."
NO_NAME = "(a roster file has no name)"
HOW_TO_USE_EXPORT = ("Copy SYS-DATA into one of your roster save folders in place of the file with that name (keep a copy of "
                     "the old one), then in the game: Customize > Save/Load/Delete > Load > Rosters, pick it, and save the roster once.")
HOW_TO_LOAD_IN_PLACE = ("In the game: start it. If this is not the roster in use, Customize > Save/Load/Delete > Load > Rosters, pick it, "
                        "then save the roster once.")


def load_settings():
    try:
        with open(datasource.app_dir(SETTINGS), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(values):
    try:
        with open(datasource.app_dir(SETTINGS), 'w', encoding='utf-8') as f:
            json.dump(values, f)
    except OSError:
        pass


def open_site():
    """Puck Peak's website in the player's browser (the header logo and line link there)."""
    import webbrowser
    webbrowser.open(SITE)


def friendly_date(when, now=None):
    now = now or datetime.datetime.now()
    days = (now.date() - when.date()).days
    if days == 0:
        return f"today {when:%H:%M}"
    if days == 1:
        return f"yesterday {when:%H:%M}"
    return f"{when.day} {when:%b %Y}"


def shorten(path, fits):
    """`path` with as much of its middle cut out as needed for fits(text) to be true, so both the
    drive and the file name stay visible."""
    text, keep = path, len(path)
    while keep > 12 and not fits(text):
        keep -= 1
        text = path[:keep // 2] + "..." + path[len(path) - (keep - keep // 2):]
    return text


def short_reason(problem):
    if 'custom copies' in problem:
        return "Cannot be used: its teams are laid out differently from the community roster."
    return "Cannot be used: " + problem.split('. ')[0].rstrip('.') + "."


# the game's own roster (savedata.DiscSlot), as its row in the list says it
BIN_NAME = "Recycle Bin" if savedata.WINDOWS else "Trash"
DISC_NOTE = "From your game disc: the 2014-15 players, brought up to today"


class App:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.queue = queue.Queue()
        self.rpcs3 = None           # savedata.Rpcs3 once the program has been found
        self.versions = []          # the versions of the game that RPCS3 has (title ids)
        self.save_pick = BOTH if self.settings.get(SAVE_BOTH) else None   # "Save for", when chosen
        self.save_mode = AS_NEW if self.settings.get(SAVE_MODE) == AS_NEW else IN_PLACE   # the owner's default: update
        self.slots = []
        self.usable = {}            # roster folder -> None when usable, else the reason it is not
        self.rows = {}              # roster folder -> RosterRow
        self.selected = None        # roster folder to start from
        self.busy = False
        self.photos_running = False # the running update also makes photos and logos
        self.at = 0.0               # progress of the running update, 0..1
        self.last_report = None
        self.name_edited = False
        self.details_open = False
        self.details_grown = self.banner_grown = 0      # how much those panels made the window grow
        self.scanning = False       # the rosters are being read (in the background)
        self.checked = {}           # (SYS-DATA path, size, time) -> None or why it cannot be used
        self._scan_id = 0            # only the newest background roster scan may update the window
        self._status = None         # what the status line shows: (text, colour)
        self.export_mode = bool(self.settings.get(EXPORT_ONLY))     # no RPCS3: update a roster file, write a new SYS-DATA
        picked = self.settings.get(EXPORT_FILE)
        self.export_file = picked if picked and os.path.isfile(picked) else None
        self.export_problem = None
        self._bar_colour = None
        try:
            self.pack = datasource.load_pack(offline=True)
        except datasource.Offline:
            self.pack = {}

        root.title(f"Puck Peak Legacy Updater {__version__}")
        # as tall as the content likes, but never taller than the screen (768-line laptops)
        room = T.screen_height(root) - 90
        root.geometry(f"1000x{max(MIN_HEIGHT, min(780, room))}")
        root.minsize(940, MIN_HEIGHT)
        self._header()
        self._footer()              # packed before the body, so it is the body that gives way
        self.tabs = ctk.CTkTabview(root, fg_color=T.BG, corner_radius=0, border_width=0, height=10,
                                   segmented_button_fg_color=T.CELL, segmented_button_selected_color=T.ACCENT,
                                   segmented_button_selected_hover_color=T.ACCENT_DEEP,
                                   segmented_button_unselected_color=T.CELL,
                                   segmented_button_unselected_hover_color=T.CELL_HOVER, text_color=T.TEXT,
                                   command=self.tab_changed)
        self.tabs.pack(fill='both', expand=True, padx=12, pady=(2, 0))
        self.tabs._segmented_button.configure(font=T.font(14, 'semibold'))
        body = ctk.CTkFrame(self.tabs.add(UPDATE_TAB), fg_color='transparent')
        body.pack(fill='both', expand=True, padx=6, pady=(4, 0))
        body.columnconfigure(0, weight=11, uniform='col')
        body.columnconfigure(1, weight=9, uniform='col')
        body.rowconfigure(1, weight=1, minsize=round(ROSTER_MIN * T.scaling(root)))
        self.body = body
        self._card_rpcs3(body).grid(row=0, column=0, sticky='nsew', padx=(0, 6), pady=(0, 10))
        self._card_roster(body).grid(row=1, column=0, sticky='nsew', padx=(0, 6), pady=(0, 10))
        self._card_updates(body).grid(row=0, column=1, rowspan=2, sticky='nsew', padx=(6, 0), pady=(0, 10))
        self._card_name(body).grid(row=2, column=0, columnspan=2, sticky='nsew')
        self.banner = Banner(body)
        self.banner.grid(row=3, column=0, columnspan=2, sticky='nsew', pady=(10, 0))
        self.banner.grid_remove()
        self.editor = EditorTab(self.tabs.add(EDITOR_TAB), self)
        self.editor.pack(fill='both', expand=True, padx=6, pady=(4, 0))

        if self.export_mode:
            self.roster_list.pack_forget()
            self.export_box.pack(fill='both', expand=True)
            self._export_look()
        root.bind('<Return>', lambda _e: self.start())
        from .app.update import temporary
        last = self.settings.get('rpcs3') or self.settings.get('folder')
        self.set_rpcs3((None if temporary(last) else last) or savedata.running_rpcs3() or savedata.default_rpcs3(),
                       quiet=True)
        self.tick()
        self.poll()

    # --- building the window ----------------------------------------------------------------
    def _header(self):
        head = ctk.CTkFrame(self.root, fg_color='transparent')
        head.pack(fill='x', pady=(12, 0))
        logo = self.logo = tk.Label(head, image=T.logo(self.root), bg=T.BG, bd=0, cursor='hand2')
        logo.pack()
        logo.bind('<Button-1>', lambda _e: open_site())
        link = ctk.CTkLabel(head, text=f"{TAGLINE}   ·   {SITE_LABEL}", font=T.font(14, 'semibold'),
                            text_color=T.ACCENT, cursor='hand2')
        link.pack(pady=(0, 2))
        self.site_link, self.compact = link, False
        link.bind('<Button-1>', lambda _e: open_site())
        link.bind('<Enter>', lambda _e: link.configure(font=T.font(14, 'semibold', underline=True)))
        link.bind('<Leave>', lambda _e: link.configure(font=T.font(14, 'semibold')))
        line = self.title_line = ctk.CTkFrame(head, fg_color='transparent')
        line.pack(pady=(0, 6))
        ctk.CTkLabel(line, text="LEGACY UPDATER", font=T.font(13, 'bold'), text_color=T.TEXT).pack(side='left')
        ctk.CTkLabel(line, text=f"   |   NHL Legacy Edition on RPCS3   |   version {__version__}",
                     font=T.font(13), text_color=T.MUTED).pack(side='left')
        tk.Label(self.root, image=T.glow_line(self.root, 760), bg=T.BG, bd=0).pack()

    def _card_rpcs3(self, master):
        card = Card(master, 1, "Where is RPCS3?")
        row = ctk.CTkFrame(card.body, fg_color='transparent')
        row.pack(fill='x')
        row.columnconfigure(0, weight=1)
        box = ctk.CTkFrame(row, fg_color=T.CELL, corner_radius=10, height=40)
        box.grid(row=0, column=0, sticky='ew')
        box.pack_propagate(False)
        self.path = ctk.CTkLabel(box, text="", font=T.font(14), text_color=T.TEXT, anchor='w')
        self.path.pack(fill='both', expand=True, padx=12)
        self.path_full = ""
        # the label's own size event (customtkinter's bind() would listen to its inner parts)
        tk.Frame.bind(self.path, '<Configure>', lambda _e: self.fit_path(), '+')
        self.change = GhostButton(row, "Change", self.browse, width=96, height=40)
        self.find = PrimaryButton(row, "Find rpcs3.exe" if savedata.WINDOWS else "Find RPCS3", self.browse, width=150,
                                  height=40)
        self.rpcs3_note = ctk.CTkLabel(card.body, text="", font=T.font(13), text_color=T.MUTED, anchor='w',
                                       justify='left', wraplength=470)
        self.rpcs3_note.pack(fill='x', pady=(8, 0))
        # no RPCS3 on this PC (a Mac, a Linux box): only the roster file is updated, and a new SYS-DATA is written
        self.export_var = tk.BooleanVar(value=self.export_mode)
        self.export_check = ctk.CTkCheckBox(card.body, text="Export only SYS-DATA roster", variable=self.export_var,
                                            command=self.toggle_export, font=T.font(13, 'semibold'), text_color=T.ACCENT,
                                            fg_color=T.ACCENT, hover_color=T.ACCENT_DEEP, border_color=T.BORDER_STRONG,
                                            checkbox_width=20, checkbox_height=20)
        self.export_check.pack(anchor='w', pady=(8, 0))
        # RPCS3 has no roster yet and does not list the game: the player points at it (.iso or folder)
        self.game_row = ctk.CTkFrame(card.body, fg_color='transparent')
        PrimaryButton(self.game_row, "Pick the game (.iso)...", self.browse_game, width=200, height=38).pack(side='left')
        GhostButton(self.game_row, "or its folder...", lambda: self.browse_game(folder=True), width=140,
                    height=38).pack(side='left', padx=(8, 0))
        return card

    def _card_roster(self, master):
        card = Card(master, 2, "Which roster should be updated?")
        self.roster_card = card
        self.roster_list = ctk.CTkScrollableFrame(card.body, fg_color='transparent', height=96,
                                                  scrollbar_button_color=T.BORDER_STRONG,
                                                  scrollbar_button_hover_color=T.FAINT)
        self.fresh_row = ctk.CTkFrame(card.body, fg_color='transparent')
        self.fresh_buttons = {}
        self.roster_list.pack(fill='both', expand=True)
        self.roster_empty = ctk.CTkLabel(card.body, text="Pick RPCS3 first. Your rosters will be listed here.",
                                         font=T.font(14), text_color=T.FAINT)
        # "Export only SYS-DATA roster": the roster file to update instead of the list
        self.export_box = ctk.CTkFrame(card.body, fg_color='transparent')
        self.export_label = ctk.CTkLabel(self.export_box, text="", font=T.font(13), text_color=T.MUTED, anchor='w',
                                         justify='left', wraplength=440)
        self.export_label.pack(fill='x', pady=(4, 8))
        PrimaryButton(self.export_box, "Pick the roster file (SYS-DATA)...", self.pick_export_file, width=300,
                      height=38).pack(anchor='w')
        return card

    def _card_updates(self, master):
        card = Card(master, 3, "What should be updated?")
        sources = self.pack.get('sources', {})
        notes = {pipeline.NHL: "Today's rosters from NHL.com",
                 pipeline.RATINGS: self._dated(sources.get('ratings_list')),
                 pipeline.NATIONAL: self._dated(sources.get('iihf')),
                 pipeline.SCHEDULE: "The real games and dates for Season mode (30 teams; the game still calls "
                                    "the year 2015)"}
        remembered = self.settings.get('steps', {})
        available = pipeline.steps_for(self.pack)
        later = [name.split(' (')[0] for name in pipeline.planned(self.pack)]
        if later:
            ctk.CTkLabel(card.body, text="Coming later:  " + "  ·  ".join(later), font=T.font(12),
                         text_color=T.FAINT, anchor='w', justify='left', wraplength=380
                         ).pack(side='bottom', fill='x', pady=(4, 0))
        # shown only while photos and logos are installed
        self.remove_art = GhostButton(card.body, "Restore the game's own pictures", self.remove_photos, height=28)
        # one button puts everything back as the game had it (rosters, calendar, pictures, names, jerseys)
        self.restore_all = PrimaryButton(card.body, "Restore default: rosters, calendar and pictures",
                                         self.restore_default, width=300, height=46)
        self.restore_all.pack(side='bottom', fill='x', pady=(8, 0))
        self.marks = {}         # a row marked "Restore" -> (its part of restore.py, its switch variable)
        # the list scrolls: on a small screen, or once more leagues are available than fit
        rows = ctk.CTkScrollableFrame(card.body, fg_color='transparent', height=96,
                                      scrollbar_button_color=T.BORDER_STRONG, scrollbar_button_hover_color=T.FAINT)
        rows.pack(fill='both', expand=True)
        self.steps, self.switches, self.step_rows = {}, [], {}
        for step in available:
            var = tk.BooleanVar(value=remembered.get(step, step in pipeline.default_steps(self.pack)))
            self.steps[step] = var
            part = restore.CALENDAR if step == pipeline.SCHEDULE else restore.ROSTERS
            row = SwitchRow(rows, pipeline.STEP_LABELS[step], notes.get(step) or self._dated(sources.get(step)),
                            var, self.refresh_state, extra=pipeline.left_out_note(self.pack, step),
                            restore=lambda k=step, part=part: self.toggle_restore(self.step_rows[k], part, self.steps[k]))
            row.pack(fill='x', pady=(0, 5), padx=(1, 10))
            self.switches.append(row)
            self.step_rows[step] = row
        self.photos = tk.BooleanVar(value=remembered.get(PHOTOS, True))
        row = SwitchRow(rows, "Photos, logos and team names", photos_will(), self.photos, self.refresh_state,
                        extra="RPCS3 must be closed. The game's own pictures are kept and can be put back.",
                        restore=lambda: self.toggle_restore(self.photos_row, restore.PICTURES, self.photos))
        row.pack(fill='x', pady=(0, 5), padx=(1, 10))
        self.switches.append(row)
        self.photos_row = row               # needs RPCS3: off for a plain save folder (savedata.SaveFolder)
        self.use_edits = tk.BooleanVar(value=remembered.get(EDITS, True))
        row = SwitchRow(rows, "My edits", "Your changes from the Roster editor, applied after the update",
                        self.use_edits, self.refresh_state,
                        extra="Kept on this PC, so the next download does not undo them.")
        row.pack(fill='x', pady=(0, 5), padx=(1, 10))
        self.switches.append(row)
        return card

    def _card_name(self, master):
        card = Card(master, 4, "Save")
        self.mode_choice = Choice(card.body, [(IN_PLACE, "Update this roster", None), (AS_NEW, "Save as a new roster", None)],
                                  self.pick_save_mode)
        self.mode_choice.pack(anchor='w', pady=(0, 8))
        row = self.name_row = ctk.CTkFrame(card.body, fg_color='transparent')
        row.pack(fill='x')
        row.columnconfigure(0, weight=1)
        self.name = tk.StringVar(value=savedata.default_name())
        self.name_entry = ctk.CTkEntry(row, textvariable=self.name, height=42, corner_radius=10, fg_color=T.CELL,
                                       border_color=T.BORDER, border_width=1, text_color=T.STRONG, font=T.font(15))
        self.name_entry.grid(row=0, column=0, sticky='ew')
        self.name_entry.bind('<Key>', lambda _e: setattr(self, 'name_edited', True))
        # shown only when RPCS3 has both versions of the game (refresh_state)
        self.save_for_label = ctk.CTkLabel(row, text="Save for", font=T.font(13), text_color=T.MUTED)
        self.save_for = Choice(row, [('EU', 'EU', flag_image('EU')), ('NA', 'NA', flag_image('NA')),
                                     (BOTH, BOTH, flag_image(('EU', 'NA')))], self.pick_save_for)
        self.go = PrimaryButton(row, "Update roster", self.start, width=190)
        configure_if_changed(self.go, text="Update roster")
        self.go.grid(row=0, column=3, padx=(12, 0))
        self.name_note = ctk.CTkLabel(
            card.body,
            text="Updating this roster makes a backup first. Saving as a new roster leaves existing saves untouched. "
                 "RPCS3 must be closed for in-place updates.",
            font=T.font(13), text_color=T.MUTED, anchor='w', justify='left', wraplength=900)
        self.name_note.pack(fill='x', pady=(8, 0))
        return card

    def _footer(self):
        foot = self.foot = ctk.CTkFrame(self.root, fg_color='transparent')
        foot.pack(side='bottom', fill='x', padx=18, pady=(10, 12))
        foot.columnconfigure(1, weight=1)
        self.bar = ctk.CTkProgressBar(foot, width=260, height=8, corner_radius=4, fg_color=T.CELL,
                                      progress_color=T.CELL)
        self.bar.set(0)
        self.bar.grid(row=0, column=0, padx=(2, 12))
        self.status = ctk.CTkLabel(foot, text="Ready.", font=T.font(13), text_color=T.MUTED, anchor='w')
        self.status.grid(row=0, column=1, sticky='ew')
        self.details_button = GhostButton(foot, "Details", self.toggle_details, width=84, height=28)
        self.details_button.grid(row=0, column=2)
        self.details = ctk.CTkTextbox(self.root, height=DETAILS_HEIGHT, fg_color=T.CARD, border_color=T.BORDER,
                                      border_width=1, corner_radius=10, text_color=T.BODY, font=T.font(12),
                                      state='disabled', wrap='word')

    @staticmethod
    def _dated(source):
        return f"{source['label']}, data from {source['date']}" if source else "No data available"

    # --- small helpers -----------------------------------------------------------------------
    def say(self, *texts):
        """Lines from the engine: into the details, onto the status line, into the progress bar. Many
        at once (everything that came in since the last look) cost one redraw, not one each."""
        if not texts:
            return
        self.details.configure(state='normal')
        self.details.insert('end', ''.join(t + '\n' for t in texts))
        self.details.see('end')
        self.details.configure(state='disabled')
        last = next((t for t in reversed(texts) if t), None)
        if self.busy and last:
            for text in texts:
                value = fraction(text, self.at, photos=self.photos_running) if text else None
                if value is not None:
                    self.at = value
            self.set_bar(self.at)
            self.set_status(f"{round(self.at * 100)}%   {last}", T.BODY)

    def set_status(self, text, colour=T.MUTED):
        """The line at the bottom (set only here, and only when it changes)."""
        if self._status != (text, colour):
            self._status = (text, colour)
            self.status.configure(text=text, text_color=colour)

    def clear_details(self):
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.configure(state='disabled')

    def selected_slot(self):
        return next((s for s in self.slots if s.folder == self.selected), None)

    def in_place(self, slot=None):
        """Is the roster picked updated in place? (The game's own roster is no save: it is always a new roster.)"""
        slot = slot or self.selected_slot()
        return self.save_mode == IN_PLACE and slot is not None and not getattr(slot, 'disc', False)

    def pick_save_mode(self, value):
        self.save_mode = value
        self.settings[SAVE_MODE] = value
        save_settings(self.settings)
        self.name_edited = False
        self.refresh_state()

    def tick(self):
        """Keep the suggested name at the current time until the user types their own."""
        if not self.name_edited and not self.busy and not self.in_place() and not self.export_mode:
            self.name.set(savedata.default_name())
        self.root.after(15000, self.tick)

    def show_path(self, text, colour):
        self.path_full = text
        self.path.configure(text_color=colour)
        self.fit_path()

    def fit_path(self):
        """The RPCS3 path, shortened in the middle when the box is too narrow for all of it."""
        room = self.path.winfo_width() / T.scaling(self.root) - 4
        if room < 40:                   # not laid out yet: the label's resize event calls this again
            self.path.configure(text=self.path_full)
            return
        self.path.configure(text=shorten(self.path_full, lambda text: T.text_width(self.root, text, 14) <= room))

    def set_bar(self, value):
        colour = T.ACCENT if value > 0 else T.CELL      # no stub at zero
        if colour != self._bar_colour:
            self._bar_colour = colour
            self.bar.configure(progress_color=colour)
        self.bar.set(value)

    def resize(self, delta):
        """Make the window `delta` taller (negative: shorter again) so a panel that appears does
        not squeeze the cards. Returns what was actually applied: the screen may not have the room."""
        if self.root.state() != 'normal':
            return 0
        scale = T.scaling(self.root)
        width, height = round(self.root.winfo_width() / scale), round(self.root.winfo_height() / scale)
        new = max(MIN_HEIGHT, min(height + delta, T.screen_height(self.root) - 70))
        self.root.geometry(f"{width}x{new}")
        return new - height

    def toggle_details(self):
        self.details_open = not self.details_open
        if self.details_open:        # below the progress row
            self.details.pack(side='bottom', fill='x', padx=18, pady=(0, 12), before=self.foot)
            self.details_grown = self.resize(DETAILS_HEIGHT + 12)
        else:
            self.details.pack_forget()
            self.resize(-self.details_grown)
        self.details_button.configure(text="Hide details" if self.details_open else "Details")

    def show_banner(self, good, title, lines, buttons, items=()):
        """Show the result box. One already showing (the last result, dimmed during the update) gets
        the new content, and the window changes its height once, by the difference."""
        scale = T.scaling(self.root)
        shown = self.banner.winfo_ismapped()
        before = round(self.banner.winfo_reqheight() / scale) + 10 if shown else 0
        self.banner.show(good, title, lines, buttons, items)
        # a short screen (a 768-line laptop) has no room for every line: they scroll there
        self.banner.fit(BANNER_LINES_SHORT if T.screen_height(self.root) < SHORT_SCREEN else None)
        if not shown:
            self.banner.grid()
        self.root.update_idletasks()
        delta = round(self.banner.winfo_reqheight() / scale) + 10 - before
        if delta:
            got = self.resize(delta)
            self.banner_grown += got
            if got < delta:             # a maximised window or a short screen: the big logo folds away
                self.compact_header(True)
        self.fit_banner()

    def fit_banner(self):
        """The result's lines get only the height the steps leave free (they scroll in it), so the
        rosters and every step stay in view (owner, 0.8.0: in a maximised window the result squeezed
        the roster list away)."""
        if not self.banner.winfo_ismapped():
            return
        for _ in range(3):              # the box's own size changes the layout around it: settle in a few steps
            self.root.update_idletasks()
            over = (self.body.winfo_reqheight() - self.body.winfo_height()) / T.scaling(self.root)
            if over <= 1 or self.banner.lines_height <= BANNER_LINES_MIN:
                break
            self.banner.fit(max(BANNER_LINES_MIN, self.banner.lines_height - over))

    def compact_header(self, on):
        """Fold the big Puck Peak logo and its link line away (on) or show them again."""
        if on == self.compact:
            return
        self.compact = on
        if on:
            self.logo.pack_forget()
            self.site_link.pack_forget()
        else:
            self.logo.pack(before=self.title_line)
            self.site_link.pack(pady=(0, 2), before=self.title_line)

    def hide_banner(self):
        if self.banner.winfo_ismapped():
            self.banner.grid_remove()
            self.resize(-self.banner_grown)
        self.banner_grown = 0
        self.compact_header(False)

    # --- RPCS3 and its rosters ------------------------------------------------------------------
    def browse(self):
        start = self.rpcs3.folder if self.rpcs3 else os.path.expanduser('~')
        if savedata.WINDOWS:
            path = filedialog.askopenfilename(parent=self.root, title="Where is rpcs3.exe?", initialdir=start,
                                              filetypes=[("RPCS3", "rpcs3.exe"), ("Programs", "*.exe")])
        else:       # Linux, Mac: RPCS3 keeps its data in a folder of its own, which is what the program needs
            path = filedialog.askdirectory(parent=self.root, initialdir=start, mustexist=True,
                                           title="Where is RPCS3's folder? (" + ", ".join(savedata.data_folders()) + ")")
        if path:
            self.set_rpcs3(os.path.normpath(path))

    def browse_saves(self):
        """Pick a folder with roster saves (or one roster save) instead of RPCS3."""
        start = self.rpcs3.savedata if self.rpcs3 else os.path.expanduser('~')
        path = filedialog.askdirectory(parent=self.root, initialdir=start, mustexist=True,
                                       title="Pick the folder with your NHL Legacy roster saves (or one roster save)")
        if path:
            self.set_rpcs3(os.path.normpath(path))

    def set_rpcs3(self, path, quiet=False):
        """Find the saves behind `path` (RPCS3 or its folder) and list the rosters. Reading the
        saves takes a moment each, so it happens in the background; the window stays as it is
        meanwhile, and saves already read (same file, size and time) are not read again."""
        self._scan_id += 1
        scan_id = self._scan_id
        self.scanning = True
        if path and not self.slots:
            configure_if_changed(self.rpcs3_note, text="Looking for your rosters...", text_color=T.MUTED)
        self.refresh_state()
        checked = dict(self.checked)

        def scan():
            found, slots, usable, versions, problem, picked = None, [], {}, [], None, None
            if path:
                try:
                    found = savedata.find_rpcs3(path, games=self.settings.get('games'))
                except savedata.NoGameError as err:         # RPCS3 itself is fine: it only needs the game
                    found = err.rpcs3
                except (savedata.Rpcs3Error, OSError) as err:
                    try:                    # not RPCS3: a folder with roster saves will do (savedata.SaveFolder)
                        found, picked = savedata.open_saves(path)
                    except (FileNotFoundError, OSError):
                        problem = str(err) + " Or pick a folder with roster saves (the link below)."
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
                            layout.check_base(Roster(s.sys_data))
                            checked[key] = None
                        except (layout.LayoutError, ValueError, KeyError, OSError) as err:
                            checked[key] = str(err)
                    usable[s.folder] = checked[key]
                slots = slots + found.disc_slots()
            running = savedata.running_rpcs3() is not None if found else False
            self.queue.put(('ui', lambda: self._scanned(found, slots, usable, versions, problem, quiet, running,
                                                        checked, picked, scan_id)))
        threading.Thread(target=scan, daemon=True).start()

    def _scanned(self, found, slots, usable, versions, problem, quiet, running, checked, picked=None, scan_id=None):
        """The rosters read by set_rpcs3, shown (on the window's thread). `picked`: the roster save
        the player pointed at directly, selected."""
        if scan_id is not None and not is_current_scan(scan_id, self._scan_id):
            return
        self.scanning = False
        if picked:
            self.selected = picked
        self.checked = checked
        self.rpcs3, self.slots, self.usable, self.versions = found, slots, usable, versions
        if self.rpcs3:
            from .app.update import temporary
            if not temporary(self.rpcs3.where):
                self.settings['rpcs3'] = self.rpcs3.where
                self.settings.pop('folder', None)
                save_settings(self.settings)
            if self.path_full != self.rpcs3.where:
                self.show_path(self.rpcs3.where, T.TEXT)
            configure_if_changed(self.rpcs3_note, text=self.found_text() + (" RPCS3 is running." if running else ""),
                                 text_color=T.GREEN)
            if self.find.winfo_manager():
                self.find.grid_remove()
            if not self.change.winfo_manager():
                self.change.grid(row=0, column=1, padx=(10, 0))
        else:
            self.show_path("Not set yet", T.FAINT)
            configure_if_changed(
                self.rpcs3_note,
                text=problem if problem and not quiet else
                savedata.PICK_RPCS3 + " The program finds your saves from there.",
                text_color=T.RED if problem and not quiet else T.MUTED)
            if self.change.winfo_manager():
                self.change.grid_remove()
            if not self.find.winfo_manager():
                self.find.grid(row=0, column=1, padx=(10, 0))
        needs_game = bool(self.rpcs3 and not self.rpcs3.plain and not self.rpcs3.disc_slots())
        if needs_game and not self.game_row.winfo_manager():
            self.game_row.pack(anchor='w', pady=(8, 0), before=self.export_check)
        elif not needs_game and self.game_row.winfo_manager():
            self.game_row.pack_forget()
        self.list_rosters()
        self.update_disc_actions()
        self.refresh_state()
        if self.export_mode:
            self._export_look()

    def browse_game(self, folder=False):
        """The player points at the game (RPCS3 does not list it): the program keeps the place and starts
        again from there, with "The game's own roster" among the rosters."""
        if not self.rpcs3:
            return
        start = os.path.expanduser('~')
        if folder:
            path = filedialog.askdirectory(parent=self.root, initialdir=start, mustexist=True,
                                           title="Pick the folder of your NHL Legacy game (it holds PS3_GAME)")
        else:
            path = filedialog.askopenfilename(parent=self.root, initialdir=start, title="Pick your NHL Legacy game",
                                              filetypes=[("Game disc image", "*.iso"), ("All files", "*.*")])
        if not path:
            return
        title = savedata.game_title_id(os.path.normpath(path))
        if title not in savedata.GAMES:
            messagebox.showwarning("Not NHL Legacy", "That is not a copy of NHL Legacy Edition. Pick the game's .iso "
                                   "file, or the folder that holds its PS3_GAME folder.")
            return
        self.settings.setdefault('games', {})[title] = os.path.normpath(path)
        save_settings(self.settings)
        self.set_rpcs3(self.rpcs3.where)

    def found_text(self):
        """'Found 9 rosters of NHL Legacy: 8 EU, 1 NA.' and a word on a version without rosters."""
        saves = [s for s in self.slots if not getattr(s, 'disc', False)]
        if self.rpcs3 is not None and self.rpcs3.plain:
            n = len(saves)
            return (f"Found {n} roster{'s' if n != 1 else ''} of NHL Legacy in this folder. Without RPCS3 the new roster "
                    "is saved next to them; photos and the game's own roster need RPCS3.")
        if not saves and not self.slots:
            return ("No roster is saved in RPCS3 yet, and RPCS3 does not say where your game is. Pick the game "
                    "(its .iso file or its folder): the program then starts from the game's own roster, made from "
                    "your game disc and brought up to today.")
        if not saves:
            return ("No roster is saved in RPCS3 yet. Start from the game's own roster (listed below): it is "
                    "made from your game disc and brought up to today.")
        n = len(saves)
        count = Counter(s.region for s in saves)
        parts = ", ".join(f"{k} {r}" for r, k in sorted(count.items(), key=lambda kv: (kv[0] != 'EU', kv[0])))
        text = f"Found {n} roster{'s' if n != 1 else ''} of NHL Legacy" + (f": {parts}." if parts else ".")
        empty = [savedata.region(t) for t in self.versions if not count[savedata.region(t)]]
        if empty:
            text += (f" Your {empty[0]} game has no roster yet: \"Save for\" below can make one from an "
                     f"{'NA' if empty[0] == 'EU' else 'EU'} roster.")
        return text

    def save_targets(self, slot=None):
        """The versions of the game (title ids) the new roster is saved for."""
        slot = slot or self.selected_slot()
        if slot is None:
            return []
        if self.in_place(slot):
            return [slot.title_id]
        if len(self.versions) < 2 or self.save_pick in (None, slot.region):
            return [slot.title_id]
        if self.save_pick == BOTH:
            return sorted(set(self.versions) | {slot.title_id}, key=lambda t: (t != slot.title_id, t))
        return [savedata.title_of(self.save_pick)]

    def pick_save_for(self, value):
        self.save_pick = value
        self.settings[SAVE_BOTH] = value == BOTH
        save_settings(self.settings)
        self.refresh_state()

    def list_rosters(self):
        """One row per roster. Rows that are still the same stay as they are (rebuilding the list
        made it flash after every update); only new or changed rosters get a new row."""
        if self.export_mode:
            return
        if not self.slots:
            for row in self.rows.values():
                row.destroy()
            self.rows = {}
            if self.roster_list.winfo_manager():
                self.roster_list.pack_forget()
            if not self.roster_empty.winfo_manager():
                self.roster_empty.pack(fill='both', expand=True, pady=24)
            self.selected = None
            self.refresh_state()
            return
        if self.roster_empty.winfo_manager():
            self.roster_empty.pack_forget()
        if not self.roster_list.winfo_manager():
            self.roster_list.pack(fill='both', expand=True)
        wanted = {}
        for s in self.slots:
            problem = self.usable[s.folder]
            if getattr(s, 'disc', False):
                wanted[s.folder] = (s.name, DISC_NOTE, ("start fresh", 'muted'), None, s.region, False)
                continue
            wanted[s.folder] = (s.name, f"{s.folder}  |  {friendly_date(s.modified)}",
                                ("made here", 'made') if s.tool_made and problem is None else None,
                                short_reason(problem) if problem else None, s.region, True)
        for folder in [f for f, row in self.rows.items() if wanted.get(f) != row.shows]:
            self.rows.pop(folder).destroy()
        order = [s.folder for s in self.slots]
        for k, folder in enumerate(order):
            if folder in self.rows:
                continue
            title, note, chip, problem, region, actions = wanted[folder]
            row = RosterRow(self.roster_list, title, note, chip=chip, problem=problem,
                            command=lambda f=folder: self.select(f), region=region,
                            on_open=(lambda f=folder: self.open_save(f)) if actions else None,
                            on_delete=(lambda f=folder: self.ask_delete(f)) if actions else None)
            row.shows = wanted[folder]
            after = next((self.rows[f] for f in order[k + 1:] if f in self.rows), None)
            row.pack(fill='x', pady=(0, 5), padx=(1, 10), **({'before': after} if after else {}))
            self.rows[folder] = row
        sync_packed_order(self.roster_list, [self.rows[folder] for folder in order])
        keep = self.selected if self.selected in self.rows and self.usable.get(self.selected) is None else None
        first = next((s.folder for s in self.slots if self.usable[s.folder] is None and not getattr(s, 'disc', False)),
                     next((s.folder for s in self.slots if self.usable[s.folder] is None), None))
        self.select(keep or first)
        self.root.after(50, self.reveal_selected)

    def update_disc_actions(self):
        """Offer direct source buttons for a new save based on each detected game disc."""
        discs = [s for s in self.slots if getattr(s, 'disc', False)]
        wanted = {s.title_id: s.region for s in discs}
        shown = {key: region for key, (region, _button) in self.fresh_buttons.items()}
        if wanted == shown:
            if self.export_mode or not discs:
                self.fresh_row.pack_forget()
            elif not self.fresh_row.winfo_manager():
                self.fresh_row.pack(fill='x', pady=(0, 6), before=self.roster_list._parent_frame)
            return
        for child in self.fresh_row.winfo_children():
            child.destroy()
        self.fresh_buttons.clear()
        if not discs or self.export_mode:
            self.fresh_row.pack_forget()
            return
        if not self.fresh_row.winfo_manager():
            self.fresh_row.pack(fill='x', pady=(0, 6), before=self.roster_list._parent_frame)
        ctk.CTkLabel(self.fresh_row, text="Start fresh:", font=T.font(12, 'semibold'),
                     text_color=T.MUTED).pack(side='left', padx=(0, 6))
        for slot in discs:
            button = GhostButton(self.fresh_row, f"New from {slot.region} disc",
                                 lambda folder=slot.folder: self.select(folder), height=28)
            button.pack(side='left', padx=(0, 6))
            self.fresh_buttons[slot.title_id] = (slot.region, button)

    def slot_of(self, folder):
        return next((s for s in self.slots if s.folder == folder), None)

    def open_save(self, folder):
        """Show one roster save's own folder in the file manager."""
        slot = self.slot_of(folder)
        if slot is not None and os.path.isdir(slot.path):
            savedata.open_path(slot.path)

    def ask_delete(self, folder):
        """Ask in the result box before a roster save goes to the Recycle Bin."""
        slot = self.slot_of(folder)
        if slot is None or getattr(slot, 'disc', False) or self.busy or self.scanning:
            return
        if savedata.running_rpcs3():
            self.show_banner(False, "Close RPCS3 first", ["A roster can only be removed while the game is closed."], [])
            return
        self.show_banner(
            False, f"Move \"{slot.name}\" to the {BIN_NAME}?",
            [f"{slot.region} game, folder {slot.folder}, saved {friendly_date(slot.modified)}.",
             f"You can take it out of the {BIN_NAME} again. Your other rosters are not changed."],
            [(f"Move to the {BIN_NAME}", lambda: self.delete_save(folder)), ("Keep it", self.hide_banner)])

    def delete_save(self, folder):
        slot = self.slot_of(folder)
        if slot is None or getattr(slot, 'disc', False) or self.busy or self.scanning or self.rpcs3 is None:
            return
        if getattr(self.editor, 'busy', False):
            self.show_banner(False, "The roster was not removed",
                             ["The Roster editor is working. Try again in a moment."], [])
            return
        try:
            savedata.trash_save(self.rpcs3.savedata, folder)
        except savedata.DeleteError as err:
            self.show_banner(False, "The roster was not removed", [str(err)], [])
            return
        if self.editor.source and self.editor.source[1] == folder:
            self.editor.source = None               # an update may give the same folder name to a new roster
        self.slots = [s for s in self.slots if s.folder != folder]
        if self.selected == folder:
            self.selected = None
        self.say(f"Moved the roster \"{slot.name}\" ({folder}) to the {BIN_NAME}.")
        self.show_banner(True, f"\"{slot.name}\" is in the {BIN_NAME}",
                         [f"The {slot.region} roster in folder {folder} was removed from the game's saves. "
                          f"Take it out of the {BIN_NAME} to get it back."], [])
        self.list_rosters()
        self.set_rpcs3(self.rpcs3.where, quiet=True)

    def reveal_selected(self):
        """Scroll the roster list so the selected roster can be seen (the list is rebuilt after an update)."""
        row = self.rows.get(self.selected)
        canvas = getattr(self.roster_list, '_parent_canvas', None)
        if row is None or canvas is None or not row.winfo_exists():
            return
        self.root.update_idletasks()
        total = max(1, self.roster_list.winfo_height())
        top, bottom = canvas.yview()
        start, end = row.winfo_y() / total, (row.winfo_y() + row.winfo_height()) / total
        if start < top or end > bottom:
            canvas.yview_moveto(max(0.0, start - 0.02))

    def select(self, folder):
        if self.busy:
            return
        previous = self.selected
        if folder != self.selected and self.save_pick != BOTH:
            self.save_pick = None           # a single version follows the roster picked
        if folder != self.selected and self.save_mode == IN_PLACE:
            self.name_edited = False        # the name box shows the roster picked
        self.selected = folder
        slot = self.selected_slot()
        if folder != previous and getattr(slot, 'disc', False) and not self.name_edited:
            self.name.set(savedata.default_name())
        if previous != folder:
            if previous in self.rows:
                self.rows[previous].select(False)
            if folder in self.rows:
                self.rows[folder].select(True)
        elif folder in self.rows:
            self.rows[folder].select(True)   # the selected row may have been rebuilt after its details changed
        self.refresh_state(selection_only=True)

    def refresh_state(self, selection_only=False):
        """Bring every control in line with the state. Runs on every click, so it only touches what
        actually changes (each change redraws a widget)."""
        if self.export_mode:
            self._refresh_export()
            return
        slot = self.selected_slot()
        ready = slot is not None and not self.busy and not self.scanning
        delete_enabled = not self.busy and not self.scanning
        if getattr(self, '_delete_enabled', None) != delete_enabled:
            self._delete_enabled = delete_enabled
            for row in self.rows.values():
                row.enable_delete(delete_enabled)
        in_place = self.in_place(slot)
        self.mode_choice.set(IN_PLACE if in_place else AS_NEW if slot is not None else self.save_mode)
        self.mode_choice.enable(not self.busy)
        if slot is not None and len(self.versions) >= 2 and not in_place:
            if not self.save_for.winfo_manager():
                self.save_for_label.grid(row=0, column=1, padx=(12, 6))
                self.save_for.grid(row=0, column=2)
            self.save_for.set(self.save_pick or slot.region)
            self.save_for.enable(not self.busy)
        elif self.save_for.winfo_manager():
            self.save_for_label.grid_remove()
            self.save_for.grid_remove()
        if in_place:
            if not self.name_edited and self.name.get() != slot.name:
                self.name.set(slot.name)
        for row, (_part, var) in list(self.marks.items()):    # a switch turned on again cancels its "Restore"
            if var.get():
                del self.marks[row]
                row.mark_restore(False)
        any_step = any(v.get() for v in self.steps.values()) or bool(self.marks)
        self.go.enable(ready and any_step)
        configure_if_changed(self.restore_all, state='normal' if ready else 'disabled',
                             fg_color=T.ACCENT if ready else T.BORDER_STRONG)
        if not self.busy:
            ticked = any(v.get() for v in self.steps.values())
            configure_if_changed(self.go, text=("Update roster" if in_place else "Make new roster") if not self.marks else
                                 ("Update and restore" if ticked else "Restore"))
        if not self.busy and not self.banner.winfo_ismapped():
            self.set_status("Looking for your rosters..." if self.scanning else
                            "Ready." if ready and any_step else
                            "Start with step 1: find RPCS3." if self.rpcs3 is None else
                            "Switch on at least one thing to update." if slot is not None else
                            "None of the rosters found can be updated.")
        if selection_only:
            return
        plain = self.rpcs3 is not None and self.rpcs3.plain
        for row in self.switches:
            row.enable(not self.busy and not (plain and row is self.photos_row))
        configure_if_changed(self.name_entry, state='normal' if not self.busy else 'disabled')
        configure_if_changed(self.change, state='normal' if not self.busy else 'disabled')
        self.settings['steps'] = {k: v.get() for k, v in self.steps.items()}
        self.settings['steps'][PHOTOS] = self.photos.get()
        self.settings['steps'][EDITS] = self.use_edits.get()
        if art_installed():
            if not self.remove_art.winfo_manager():
                self.remove_art.pack(side='bottom', anchor='w', pady=(6, 0))
            configure_if_changed(self.remove_art, state='normal' if not self.busy else 'disabled')
        elif self.remove_art.winfo_manager():
            self.remove_art.pack_forget()

    # --- the update ------------------------------------------------------------------------------
    def toggle_restore(self, row, part, var):
        """The Restore button of a row: that part is put back as the game had it in the next save (press again to undo)."""
        if self.busy or self.scanning:
            return
        if row in self.marks:
            del self.marks[row]
            row.mark_restore(False)
        else:
            self.marks[row] = (part, var)
            row.mark_restore(True)
            var.set(False)
        self.refresh_state()

    def restore_default(self):
        """The big button: everything back as the game had it, after a question."""
        slot = self.selected_slot()
        if slot is None or self.busy or self.scanning:
            return
        where = (f"\"{slot.name}\" is replaced (its old version is copied to the backups folder first)"
                 if self.in_place(slot) else "A new roster is saved next to your others; nothing you have is replaced")
        if not messagebox.askyesno("Restore default",
                                   "This puts back the game's own rosters, calendar, pictures, team names and jerseys.\n\n"
                                   f"{where}. RPCS3 must be closed.\n\nGo on?"):
            return
        self.start(everything=True)

    def start(self, everything=False):
        if self.export_mode:
            self.start_export()
            return
        slot = self.selected_slot()
        steps = [s for s in self.steps if self.steps[s].get()]
        parts = set(restore.ALL_PARTS) if everything else {part for part, _var in self.marks.values()}
        if everything:
            steps = []
        if slot is None or self.busy or self.scanning or not (steps or parts):
            return
        save_settings(self.settings)
        in_place = self.in_place(slot)
        if in_place and savedata.running_rpcs3():
            self.show_banner(False, "Close RPCS3 first", ["A roster can only be updated while the game is closed."], [])
            return
        if in_place and getattr(self.editor, 'busy', False):
            self.show_banner(False, "The roster was not updated", ["The Roster editor is working. Try again in a moment."], [])
            return
        if in_place:        # a rename only when the player changed the name
            name = self.name.get().strip() if self.name_edited and self.name.get().strip() != slot.name else None
        else:
            name = self.name.get().strip() if self.name_edited else savedata.default_name()
        self.busy, self.at, self.last_report = True, 0.0, None
        if self.banner.winfo_ismapped():     # the last result stays, greyed, so the window keeps its size
            self.banner.dim("Updating... (the last result is shown below until the new one is ready)")
        self.set_bar(0)
        self.refresh_state()
        configure_if_changed(self.go, text="Updating...")
        self.set_status("0%   Starting...", T.BODY)
        self.clear_details()
        art = self.rpcs3 if self.photos.get() and not self.rpcs3.plain and not everything else None
        self.photos_running = art is not None
        mine = (my_edits.load(), my_edits.load_teams()) if self.use_edits.get() and not everything else (None, None)
        threading.Thread(target=self.work, args=(self.rpcs3.savedata, slot, steps, name, art, mine,
                                                 self.save_targets(slot), in_place, parts), daemon=True).start()

    def work(self, folder, slot, steps, name, art=None, mine=(None, None), targets=None, in_place=False, parts=()):
        try:
            if art is not None:         # the pictures first (packs.py); without them photos come one by one
                packs.sync()
            default = restore.default_slot(self.rpcs3, slot.title_id) if parts else None
            result = pipeline.update(folder, slot.folder, steps, name, lambda msg: self.queue.put(('say', msg)),
                                     art_rpcs3=art, my_edits=mine[0] or None, team_edits=mine[1] or None,
                                     targets=targets, disc=slot if getattr(slot, 'disc', False) else None,
                                     in_place=in_place, restore_parts=parts, default=default,
                                     rpcs3=None if self.rpcs3.plain else self.rpcs3)    # follows the game patch as the window does
            self.queue.put(('done', (result, savedata.running_rpcs3() is not None)))
        except (layout.LayoutError, datasource.Offline, FileNotFoundError, ArtError, StockError,
                savedata.InPlaceError) as err:
            self.queue.put(('error', str(err)))
        except Exception as err:      # anything unexpected: keep the details for a bug report
            path = datasource.app_dir('logs', 'error.log')
            with open(path, 'a', encoding='utf-8') as f:
                f.write(traceback.format_exc() + '\n')
            self.queue.put(('error', f"Something went wrong: {err}\nThe details were saved to {path}"))

    def poll(self):
        said = []           # the engine's lines since the last look: shown together
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == 'say':
                    said.append(payload)
                    continue
                self.say(*said)
                said = []
                if kind == 'error':
                    self.finish()
                    self.say(payload)
                    self.failed("Nothing was saved", [payload, "Your existing rosters are untouched."])
                elif kind == 'done':
                    self.finish()
                    self.report(*payload)
                elif kind == 'ui':           # the roster editor's worker hands back its result
                    payload()
        except queue.Empty:
            pass
        self.say(*said)
        self.root.after(100, self.poll)

    def finish(self):
        self.busy = False
        self.set_rpcs3(self.rpcs3.where if self.rpcs3 else None, quiet=True)

    def failed(self, title, lines):
        self.set_bar(0)
        self.set_status("Nothing was saved.", T.RED)
        self.show_banner(False, title, lines,
                         [("Show details", self.toggle_details)] if not self.details_open else [])

    def report(self, result, rpcs3_running):
        self.last_report = result.report_path
        items = result.build.lines() + [("Restored", text) for text in result.restored]
        if result.exported and result.slot is not None:
            self.say("", "What changed:", *(f"   {title}: {text}" for title, text in items))
            self.say(f"Done. {HOW_TO_USE_EXPORT}")
            self.set_bar(1)
            self.set_status("Done: SYS-DATA exported.", T.GREEN)
            folder = os.path.dirname(result.exported)
            self.show_banner(True, "SYS-DATA exported",
                             [f"New file: {result.exported}", HOW_TO_USE_EXPORT, "No pictures are in it: they need RPCS3."],
                             [("Open the folder", lambda: savedata.open_path(folder)), ("List of changes", self.show_report)],
                             items=items or [("Result", "Nothing needed changing.")])
            self.refresh_state()
            return
        self.say("", "What changed:", *(f"   {title}: {text}" for title, text in items))
        if result.slot is None:
            problems = result.build.problems
            for p in problems[:15]:
                self.say("   - " + p)
            self.failed("The new roster failed the safety checks, so nothing was saved",
                        problems[:3] + ["Your existing rosters are untouched."])
            return
        thin = result.build.info.get('thinner_ahl_teams') or []
        if thin:
            self.say(f"Note: {len(thin)} AHL teams lost players to NHL rosters and are short-handed. "
                     "Switch on \"AHL rosters\" to fill them with their real players.")
        art = result.art_line()
        if art:
            self.say(art)
        how = HOW_TO_LOAD_IN_PLACE if result.in_place else HOW_TO_LOAD
        self.say(f"Done. {how}")
        self.name_edited = False
        self.set_bar(1)
        buttons = [("List of changes", self.show_report), ("Open save folder", self.show_folder)]
        if result.in_place and result.backup:
            buttons.insert(1, ("Open backup folder", lambda: savedata.open_path(result.backup)))
        if not rpcs3_running and not self.rpcs3.plain:
            buttons.append(("Start RPCS3", self.start_rpcs3))
        name = result.slot.name
        if result.in_place:
            self.editor.source = None       # the editor shows what the file is now
            where = ("The roster is already the same as the new one: nothing was changed." if result.unchanged
                     else f"Updated: {result.saved_where()}.")
            lines = [where] + ([f"The old roster is kept in {result.backup}"] if result.backup else []) \
                + result.restored + ([art] if art else []) + [how]
            title = f"Already up to date: \"{name}\"" if result.unchanged else f"Updated \"{name}\""
            self.set_status(f"Done: {'already up to date' if result.unchanged else 'updated'} \"{name}\".", T.GREEN)
        else:
            where = f"New save: {result.saved_where()}."
            lines = [where] + result.restored + ([art] if art else []) + [how]
            title = f"Saved as \"{name}\""
            self.set_status(f"Done: saved as \"{name}\".", T.GREEN)
        self.say(where)
        self.show_banner(True, title, lines, buttons, items=items or [("Result", "Nothing needed changing.")])
        self.refresh_state()

    # --- "Export only SYS-DATA roster" (no RPCS3 on this PC) -------------------------------------
    def toggle_export(self):
        """The checkbox: update a roster file and write a new SYS-DATA, instead of working with RPCS3's saves."""
        if self.busy:
            self.export_var.set(self.export_mode)
            return
        self.export_mode = self.export_var.get()
        self.settings[EXPORT_ONLY] = self.export_mode
        save_settings(self.settings)
        self.hide_banner()
        if self.export_mode:
            self.fresh_row.pack_forget()
            self.roster_list.pack_forget()
            self.roster_empty.pack_forget()
            self.export_box.pack(fill='both', expand=True)
            self._export_look()
        else:
            self.export_box.pack_forget()
            self.name_edited = False
            self.name.set(savedata.default_name())
            if not self.mode_choice.winfo_manager():
                self.mode_choice.pack(anchor='w', pady=(0, 8), before=self.name_row)
            configure_if_changed(self.find, state='normal')
            self.set_rpcs3(self.rpcs3.where if self.rpcs3 else self.settings.get('rpcs3'), quiet=True)
            self.list_rosters()
        self.refresh_state()

    def _export_look(self):
        """Step 1 and 2 in the export mode: RPCS3 is not needed, the roster file is what counts."""
        configure_if_changed(self.rpcs3_note, text="Not needed in this mode: the program only makes a roster file.",
                             text_color=T.MUTED)
        configure_if_changed(self.find, state='disabled')
        configure_if_changed(self.change, state='disabled')
        if self.export_problem:
            text, colour = self.export_problem, T.RED
        elif self.export_file:
            text, colour = f"Roster file: {self.export_file}", T.GREEN
        else:
            text, colour = ("Pick the roster's SYS-DATA file (the community roster you downloaded). The new SYS-DATA is "
                            "written next to this program."), T.MUTED
        configure_if_changed(self.export_label, text=text, text_color=colour)

    def pick_export_file(self):
        start = os.path.dirname(self.export_file) if self.export_file else os.path.expanduser('~')
        path = filedialog.askopenfilename(parent=self.root, initialdir=start, title="Pick the roster file (SYS-DATA)",
                                          filetypes=[("Roster file", "SYS-DATA"), ("All files", "*")])
        if not path:
            return
        path = os.path.normpath(path)
        try:
            layout.check_base(Roster(path))
            from . import stock
            if stock.untouched(Roster(path)):
                raise layout.LayoutError("that is the game's own roster as it comes on the disc: pick \"New from EU disc\" (or NA) "
                                         "in the list instead, or a roster that was updated")
            self.export_file, self.export_problem = path, None
            self.settings[EXPORT_FILE] = path
            save_settings(self.settings)
        except (layout.LayoutError, ValueError, KeyError, OSError) as err:
            self.export_file, self.export_problem = None, "That file cannot be used: " + short_reason(str(err))[len("Cannot be used: "):]
        self._export_look()
        self.refresh_state()

    def _refresh_export(self):
        """refresh_state in the export mode."""
        ready = self.export_file is not None and not self.busy
        if self.mode_choice.winfo_manager():
            self.mode_choice.pack_forget()
        if self.save_for.winfo_manager():
            self.save_for_label.grid_remove()
            self.save_for.grid_remove()
        if self.name.get() != NO_NAME:
            self.name.set(NO_NAME)
        configure_if_changed(self.name_entry, state='disabled')
        configure_if_changed(self.name_note, text="The new SYS-DATA is written into a new folder next to this program, named "
                                                  "by the date and time. It has no name of its own and no pictures.")
        any_step = any(v.get() for v in self.steps.values())
        self.go.enable(ready and any_step)
        if not self.busy:
            configure_if_changed(self.go, text="Make new roster")
        if not self.busy and not self.banner.winfo_ismapped():
            self.set_status("Ready." if ready and any_step else
                            "Pick the roster file (step 2)." if self.export_file is None else
                            "Switch on at least one thing to update.")
        for row in self.switches:
            row.enable(not self.busy and row is not self.photos_row)
        self.settings['steps'] = {k: v.get() for k, v in self.steps.items()}
        self.settings['steps'][PHOTOS] = self.photos.get()
        self.settings['steps'][EDITS] = self.use_edits.get()
        if self.remove_art.winfo_manager():
            self.remove_art.pack_forget()

    def start_export(self):
        steps = [s for s in self.steps if self.steps[s].get()]
        if self.export_file is None or self.busy or not steps:
            return
        save_settings(self.settings)
        self.busy, self.at, self.last_report = True, 0.0, None
        self.photos_running = False
        if self.banner.winfo_ismapped():
            self.banner.dim("Working... (the last result is shown below until the new one is ready)")
        self.set_bar(0)
        self.refresh_state()
        configure_if_changed(self.go, text="Working...")
        self.set_status("0%   Starting...", T.BODY)
        self.clear_details()
        mine = (my_edits.load(), my_edits.load_teams()) if self.use_edits.get() else (None, None)
        threading.Thread(target=self.work_export, args=(self.export_file, steps, mine), daemon=True).start()

    def work_export(self, file, steps, mine):
        try:
            result = pipeline.export_sysdata(file, steps, None, lambda msg: self.queue.put(('say', msg)),
                                             my_edits=mine[0] or None, team_edits=mine[1] or None)
            self.queue.put(('done', (result, False)))
        except (layout.LayoutError, datasource.Offline, FileNotFoundError, OSError) as err:
            self.queue.put(('error', str(err)))
        except Exception as err:
            path = datasource.app_dir('logs', 'error.log')
            with open(path, 'a', encoding='utf-8') as f:
                f.write(traceback.format_exc() + '\n')
            self.queue.put(('error', f"Something went wrong: {err}\nThe details were saved to {path}"))

    def tab_changed(self):
        if self.tabs.get() == EDITOR_TAB:
            self.editor.opened()

    def remove_photos(self):
        """Put back every game file the photos and logos replaced."""
        if self.busy:
            return
        messages = []
        try:
            remove_art(say=messages.append)
        except ArtError as err:
            self.show_banner(False, "The photos and logos are still there", [str(err)], [])
            return
        self.say(*messages)
        self.show_banner(True, "The game's own pictures are back",
                         messages + ["Your rosters are not changed."], [])
        self.refresh_state()

    def show_folder(self):
        if self.rpcs3:
            savedata.open_path(self.rpcs3.savedata)

    def show_report(self):
        if self.last_report and os.path.exists(self.last_report):
            savedata.open_path(self.last_report)

    def start_rpcs3(self):
        if self.rpcs3 and not savedata.running_rpcs3():
            self.rpcs3.start()


def main(note=None):
    """`note`: why this window opened instead of the full one (a start that failed): shown at the top of the Update tab."""
    ctk.set_appearance_mode('dark')
    root = ctk.CTk(fg_color=T.BG)
    if T.missing_files():
        root.withdraw()
        messagebox.showerror(
            "Puck Peak Legacy Updater",
            "Some of this program's files are missing from the system's temporary folder. An antivirus "
            "or a cleaning program may have removed them.\n\n"
            "Close this message and start the program again. If it keeps happening, "
            "allow NHLLegacyRosterUpdater in your antivirus.", parent=root)
        root.destroy()
        return
    T.load_fonts(root)
    icon = os.path.join(T.DATA, 'app.ico')
    if os.name == 'nt' and os.path.exists(icon):
        root.after(250, lambda: root.iconbitmap(icon))      # after the toolkit has set its own
    app = App(root)
    if note:
        root.after(800, lambda: app.show_banner(True, "This is the simple window", note.split('\n'), []))
    root.mainloop()


if __name__ == '__main__':
    main()
