"""Export files to a folder: everything an update would put into RPCS3, made into a folder instead.

    run(...)                  the same update as the window's Update button, but the new roster, the pictures, the team
                              names and the game patch's files are written into a new folder next to the program, laid out
                              like RPCS3's own (dev_hdd0/..., patches/...), with HOW-TO-INSTALL.txt
    instructions(...)         what the player reads: which folder goes where on Windows, Linux (also Flatpak) and Mac

For a player whose RPCS3 the program cannot write into (Linux, a Mac, another PC) and for anyone who wants to look first.
It is the normal update pipeline run against an `ExportTarget`, a pretend RPCS3 that lives in the new folder:

  * `savedata.exporting()`: no RPCS3 counts as running (nothing is written into one);
  * `art.install.redirected()`: the lists of written files and the kept copies go to a work folder inside the new one, so the
    player's own lists (what is installed, what Restore puts back) are neither read nor changed;
  * the roster the update starts from (a save of RPCS3 or of a save folder, the game's own roster, or a SYS-DATA file) is
    copied into the work folder first and never touched; the work folder is deleted at the end.

Nothing is written outside the new folder, except what an update always keeps in the program's own folder (the list of
changes, downloaded pictures). Patch switches in RPCS3 (config/patch_config.yml) are not written: the player ticks them.
"""
import datetime
import os
import shutil

from . import datasource, gamepatch, patchinstall, pipeline, savedata
from .art import install
from .sfo import Sfo

WORK = '.export-work'                   # inside the new folder: the roster the update starts from, the lists; deleted at the end
HOW_TO = 'HOW-TO-INSTALL.txt'
FILE_NUMBER = 99                        # the number the work folder's copy of a roster file gets (never in the output)
SYSTEMS = ('Windows', 'Linux', 'Mac')

TITLE = "Your files are ready"
ROW_WHAT = {'dev_hdd0': "The game's files"}


class ExportError(RuntimeError):
    """Something the player has to fix; the message says what, in plain words."""


class ExportTarget(savedata.Rpcs3):
    """A pretend RPCS3 that lives in the export folder: its virtual hard disk is <out>/dev_hdd0, its patches folder
    <out>/patches. The roster saves it holds (`savedata`) are the work copy of the starting roster and the new rosters until
    they are moved to their place in dev_hdd0. `games`: {title id: the game's .iso or folder}, where the pictures' and the
    patch's templates come from. `extra_savedata`: save folders of the player's own RPCS3, only read (picture numbers
    other rosters already use)."""

    def __init__(self, out, work_savedata, games=None, user='00000001', extra_savedata=()):
        super().__init__(None, work_savedata, user, root=out, games=games)
        self.extra_savedata = list(extra_savedata)
        self.out = out

    def final_savedata(self):
        return os.path.join(self.dev_hdd0, 'home', self.user, 'savedata')


class ExportResult:
    """What `run` made. `folder` is None when the roster failed its safety checks (nothing was kept)."""

    def __init__(self, update, folder=None, files=(), rosters=(), top=(), text='', rows=(), intro=(), after=(), entries=(),
                 notes=()):
        self.update = update            # the pipeline.UpdateResult
        self.folder = folder            # the new folder
        self.files = list(files)        # every file in it, relative with '/', sorted
        self.rosters = list(rosters)    # [(folder name, region, roster name)] the new roster folders in dev_hdd0
        self.top = list(top)            # the folders in it: dev_hdd0 and / or patches
        self.text = text                # the same words as HOW-TO-INSTALL.txt
        self.rows = list(rows)          # [{'head': folder, 'text': what and where}] for the pop-up
        self.intro = list(intro)
        self.after = list(after)        # lines about parts that went wrong after the roster was made
        self.entries = list(entries)    # the patch's entries to tick in RPCS3
        self.notes = list(notes)


# --- the words ---------------------------------------------------------------------------------------------
def _system():
    return 'Windows' if savedata.WINDOWS else 'Mac' if savedata.MAC else 'Linux'


def _order(system):
    return [system] + [s for s in SYSTEMS if s != system]


def _where(what, system):
    """The place RPCS3 keeps `what` ('' = its data folder, 'patches' = its patches folder) on each system, as lines."""
    tail = f"/{what}" if what else ""
    inside = f", into its {what} folder" if what else ""
    text = {
        'Windows': f"Windows: the folder that holds rpcs3.exe{inside}",
        'Linux': f"Linux: ~/.config/rpcs3{tail}",
        'Flatpak': f"Linux, Flatpak: ~/.var/app/net.rpcs3.RPCS3/config/rpcs3{tail}",
        'Mac': f"Mac: ~/Library/Application Support/rpcs3{tail}",
    }
    names = [s for s in _order(system)]
    names.insert(names.index('Linux') + 1, 'Flatpak')
    return [text[s] for s in names]


def entry_names(intro=True, login=False):
    """The patch entries to tick in RPCS3, in the order its list shows ours."""
    names = [gamepatch.PLAYER_ENTRY, gamepatch.NEWS_ENTRY]
    if intro:
        names.append(gamepatch.INTRO_ENTRY)
    if login:
        names.append(gamepatch.LOGIN_ENTRY)
    return names


def instructions(parts, rosters=(), entries=(), full=(), user='00000001', system=None):
    """What to do with the folders. `parts`: the paths in the export folder ('dev_hdd0/home', 'dev_hdd0/game', 'patches'),
    `rosters`: [(folder name, region, roster name)], `entries`: the patch entries to tick, `full`: regions whose save folder
    already holds the 10 rosters the game lists. Returns (intro lines, rows [{'head', 'text'}], after lines): the pop-up and
    HOW-TO-INSTALL.txt say the same."""
    from .app import texts as X
    system = system or _system()
    top = sorted({p.split('/')[0] for p in parts})
    intro = ["Nothing in RPCS3 was changed.",
             "Close RPCS3, then copy " + ("each folder" if len(top) > 1 else "the folder") + " below into RPCS3's own folder "
             "(a plain copy; if you are asked, merge the folders and replace the files)."]
    rows = []
    if 'dev_hdd0' in top:
        has = {p.split('/', 1)[1] for p in parts if p.startswith('dev_hdd0/')}
        what = []
        if 'home' in has:
            what.append("your new roster" + (f" ({', '.join(f'{name}: {folder}' for folder, _r, name in rosters)})"
                                             if rosters else ""))
        if 'game' in has:
            what.append("the pictures, team names and other files the game reads before its own")
        lines = ["Contains " + " and ".join(what) + "." if what else "Contains game files."]
        lines += ["Goes into RPCS3's data folder, next to the dev_hdd0 that is there:"] + ["  " + w for w in _where('', system)]
        lines.append("  On a Mac, hold the Option key while you drop it and choose Merge: a plain drop would replace your "
                     "whole dev_hdd0 folder.")
        lines.append("  In a terminal on Linux or a Mac, from inside this folder: cp -R dev_hdd0 <RPCS3's data folder>")
        if 'home' in has:
            lines.append(f"The roster is in dev_hdd0/home/{user}/savedata. {user} is RPCS3's first user; if you use another "
                         "one, put the roster folder into that user's savedata folder.")
            lines.append("If a folder with the same name is already in your savedata folder, rename the new one to a free "
                         "name: the same letters and numbers, ending 01 to 09 (the game lists 10 rosters per version).")
        if 'game' in has:
            lines.append("Files of the same name that were there (another picture pack's) are replaced and not kept: "
                         "copy your dev_hdd0/game folder somewhere first if you want them back.")
        for region in full:
            lines.append(f"Your {region} game already lists 10 rosters: delete one you no longer play, or the new one will not show.")
        rows.append({'head': 'dev_hdd0', 'text': "\n".join(lines)})
    if 'patches' in top:
        lines = ["Contains the game patch (32 teams and the year 2026) for RPCS3.",
                 "Goes into RPCS3's patches folder:"] + ["  " + w for w in _where('patches', system)]
        lines.append("A file of the same name that is there is replaced.")
        rows.append({'head': 'patches', 'text': "\n".join(lines)})
    after = []
    if entries:
        after.append("Then, in RPCS3: Manage > Game Patches, open NHL Legacy and tick: " + "; ".join(entries) + ". Do it for "
                     "the version of the game you play (the 1.00 and the 1.01 entries are both there).")
    after.append(X.HOW_TO_LOAD)
    made = [w for w, here in (("the roster folder", 'dev_hdd0/home' in parts), ("the pictures and other game files",
                                                                              'dev_hdd0/game' in parts),
                              ("the file in patches", 'patches' in top)) if here]
    after.append("To undo it: delete the files you copied (" + ", ".join(made) + ")" + (" and untick the patch" if 'patches' in top else "")
                 + ". The Restore buttons of this program only work when it writes into RPCS3 itself.")
    return intro, rows, after


def how_to_text(intro, rows, after):
    """HOW-TO-INSTALL.txt (and the pop-up's Copy text)."""
    out = [TITLE, "=" * len(TITLE), ""] + list(intro) + [""]
    for row in rows:
        out += [row['head'], "-" * len(row['head']), row['text'], ""]
    out += list(after)
    return "\n".join(out) + "\n"


# --- the work ----------------------------------------------------------------------------------------------
def _new_folder(root, now):
    base = os.path.join(root, f"NHL Legacy export {now:%Y-%m-%d %H%M}")
    folder, n = base, 1
    while os.path.exists(folder):
        n += 1
        folder = f"{base} ({n})"
    os.makedirs(folder)
    return folder


def _stage_file(path, work_savedata, title, disc):
    """A roster file (SYS-DATA) as a roster save in the work folder: the save folder the update starts from."""
    from . import stock
    if not os.path.isfile(path):
        raise FileNotFoundError("The roster file was not found.")
    with open(path, 'rb') as f:
        data = f.read()
    if not data.startswith(savedata.ROSTER_MAGIC):
        raise ExportError("That file is not a roster: pick the SYS-DATA file of a roster save.")
    folder = f"{title}02{FILE_NUMBER}"
    target = os.path.join(work_savedata, folder)
    os.makedirs(target)
    with open(os.path.join(target, 'SYS-DATA'), 'wb') as f:
        f.write(data)
    savedata.roster_sfo(title, folder, "roster file").save(os.path.join(target, 'PARAM.SFO'))
    with open(os.path.join(target, 'ICON0.PNG'), 'wb') as f:
        f.write(stock.disc_icon(disc) if disc else stock.own_icon())
    return folder


def _free_numbers(title, *folders):
    used = set()
    for folder in folders:
        used |= savedata._numbers_in_use(folder, title)
    return [k for k in range(1, savedata.GAME_LISTS) if k not in used]


def _games_of(rpcs3, games, source):
    """{title id: game} for the target: what the player pointed at, what RPCS3 lists, the disc the roster starts from."""
    found = {}
    for title in savedata.GAMES:
        path = rpcs3.game_disc(title) if rpcs3 is not None and not getattr(rpcs3, 'plain', False) else None
        if path:
            found[title] = path
    found.update({t: p for t, p in (games or {}).items() if p and os.path.exists(p)})
    if getattr(source, 'disc', False):
        found[source.title_id] = source.path
    return found


def run(out_root=None, source=None, rpcs3=None, steps=pipeline.ALL_STEPS, targets=None, name=None, photos=False,
        game_patch=False, intro=True, login=False, my_edits=None, team_edits=None, progress=None, offline=False, data=None,
        games=None, now=None, system=None, art_parts=None, ice_order=None):
    """Make the update and write its files into a new folder in `out_root` (default: next to the program).

    `source`: the roster to start from: a savedata.Slot (a roster save of `rpcs3`, or of a save folder), a DiscSlot (the
    game's own roster), or the path of a SYS-DATA file (the community roster, no RPCS3 needed). `rpcs3`: the player's RPCS3
    or save folder (savedata.Rpcs3 / SaveFolder), only read: it says where the game is and which roster numbers are taken.
    `games`: {title id: the game's .iso or folder} the player pointed at. `targets`: the versions to make the roster for
    (title ids; default: the source's own, EU for a file). `photos`: pictures, names and jerseys (they need the game);
    `art_parts` (art/parts.py) says which of them (default: names, photos and logos, this season's jerseys).
    `game_patch`: a roster for the patched game, with the patch's files (they need the game; `intro` / `login`: which of its
    small entries to offer). Returns an ExportResult; `folder` is None (and nothing is kept) when the new roster failed its
    safety checks."""
    say = progress or (lambda msg: None)
    real = rpcs3 if rpcs3 is not None else None
    is_file = isinstance(source, str)
    if source is None:
        raise ExportError("Pick the roster to start from: a roster of your RPCS3, or a roster file (SYS-DATA).")
    title = (targets or [None])[0] or (savedata.title_of('EU') if is_file else source.title_id)
    targets = list(targets or [title])
    found_games = _games_of(real, games, None if is_file else source)
    needs_game = photos or game_patch or getattr(source, 'disc', False)
    if needs_game and not any(found_games.get(t) for t in targets):
        raise ExportError("Pick your copy of the game (the .iso file or its folder): the pictures, the game patch and the "
                          "game's own roster are made from it.")
    steps = list(steps)
    root = out_root or pipeline.export_root()
    now = now or datetime.datetime.now()
    out = _new_folder(root, now)
    keep = False
    try:
        work = os.path.join(out, WORK)
        work_savedata = os.path.join(work, 'savedata')
        os.makedirs(work_savedata)
        user = (getattr(real, 'user', None) or '00000001') if real is not None else '00000001'
        real_saves = getattr(real, 'savedata', None) if real is not None else None
        target = ExportTarget(out, work_savedata, found_games, user=user,
                              extra_savedata=[real_saves] if real_saves and os.path.isdir(real_saves) else [])
        disc_slot = source if getattr(source, 'disc', False) else None
        if is_file:
            say(f"Starting from the roster file {os.path.basename(source)}")
            folder = _stage_file(source, work_savedata, title, found_games.get(title))
        elif disc_slot is not None:
            folder = None
        else:
            folder = source.folder
            shutil.copytree(source.path, os.path.join(work_savedata, folder))
        read_dirs = [real.game_folder(t) for t in savedata.GAMES] if real is not None and real.game_folder(title) else []
        registry = _registry(work)
        with savedata.exporting(), install.redirected(os.path.join(work, 'state'), read_dirs):
            result = pipeline.update(work_savedata, folder, steps, name, progress, offline=offline, data=data,
                                     art_rpcs3=target if photos else None, art_registry=registry, my_edits=my_edits,
                                     team_edits=team_edits, targets=targets, disc=disc_slot, rpcs3=target,
                                     game_patch=bool(game_patch), art_parts=art_parts, ice_order=ice_order)
            if result.slot is None:                # the safety checks failed: nothing is kept
                return ExportResult(result)
            entries = []
            if game_patch:
                entries = _patch_files(target, targets, intro, say)
        after = [f"{what}: {text}" for what, text, _details in getattr(result, 'after', [])]
        if isinstance(result.db_note, str):
            after.append("The game patch's database: " + result.db_note)
        rosters = _place_rosters(result, out, target, real_saves, user)
        shutil.rmtree(work)
        parts = sorted({os.path.relpath(os.path.join(dp, dn), out).replace(os.sep, '/')
                        for dp, dns, _fn in os.walk(out) for dn in dns} & {'dev_hdd0/home', 'dev_hdd0/game', 'patches'})
        full = [savedata.region(t) for t in targets if real_saves and savedata.roster_count(real_saves, t) >= savedata.GAME_LISTS]
        intro_lines, rows, after_lines = instructions(parts, rosters, entries, full, user, system)
        text = how_to_text(intro_lines, rows, after_lines)
        with open(os.path.join(out, HOW_TO), 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        files = sorted(os.path.relpath(os.path.join(dp, fn), out).replace(os.sep, '/')
                       for dp, _dns, fns in os.walk(out) for fn in fns)
        keep = True
        say(f"Exported the files to {out}")
        return ExportResult(result, out, files, rosters, sorted({p.split('/')[0] for p in parts}), text, rows,
                            intro_lines, after, entries, after_lines)
    finally:
        if not keep:
            shutil.rmtree(out, ignore_errors=True)


def _registry(work):
    """The picture numbers handed out so far, as a copy in the work folder: the export gives the numbers the player's own
    updates use, and the player's list is not changed."""
    from .art import portraits
    path = os.path.join(work, 'state', 'portrait_ids.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mine = datasource.app_dir('art', 'portrait_ids.json')
    if os.path.isfile(mine):
        shutil.copyfile(mine, path)
    return portraits.Registry(path)


def _patch_files(target, titles, intro, say):
    """The game patch's own files besides the database (the update wrote that): RPCS3's patch file for each version, and the
    title screen that presses Start by itself when the intro is skipped. patch_config.yml is the player's: not written."""
    import hashlib
    text = gamepatch.player_patch_text().encode()
    writer = install._Writer([patchinstall.patches_dir(target)], store=patchinstall.STORE)
    try:
        for title in titles:
            writer.write((os.path.basename(patchinstall.patch_file(target, title)),), text,
                         f"patch:{gamepatch.TEAMS_VERSION}:" + hashlib.sha1(text).hexdigest())
    finally:
        writer.save()
    disc = patchinstall.find_disc(target, titles)
    patchinstall.set_press(target, titles, intro, disc, say)
    say("Game patch: its files are in the export folder")
    return entry_names(intro, False)


def _place_rosters(result, out, target, real_saves, user):
    """Move the new roster folders from the work folder to dev_hdd0/home/<user>/savedata under a free name: numbers the
    player's own save folder uses are skipped (the player copies the folder in, never over another roster)."""
    final = target.final_savedata()
    os.makedirs(final, exist_ok=True)
    placed = []
    for slot in result.slots:
        free = _free_numbers(slot.title_id, final, *([real_saves] if real_saves and os.path.isdir(real_saves) else []))
        if not free:
            free = _free_numbers(slot.title_id, final) or [1]
        folder = f"{slot.title_id}02{free[0]:02d}"
        dest = os.path.join(final, folder)
        shutil.move(slot.path, dest)
        sfo_path = os.path.join(dest, 'PARAM.SFO')
        sfo = Sfo.load(sfo_path)
        sfo.set_str('SAVEDATA_DIRECTORY', folder)
        sfo.save(sfo_path)
        placed.append((folder, savedata.region(slot.title_id), slot.name))
    return placed
