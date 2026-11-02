"""The game patch in RPCS3 (gamepatch.py): put it in, tell whether it is in, and take it out again.

    install_patch(rpcs3, titles, intro=, login=)   the window's Patch button (step 2), cli game-patch install
    set_switches(rpcs3, titles, intro, login)      the two small switches of a patched game, changed
    set_online(rpcs3, titles, on)                  the online entry (our server's words) ticked or not, with or without the 32 teams
    refresh_db(rpcs3, titles, roster)              after a patched update: the db files hold that roster's calendars
    state(rpcs3) / patched_titles(rpcs3)           {title id: {'patched', 'version', 'game', 'stale', ...}} / the patched ones
    remove(rpcs3)                                  the Unpatch button (and Restore default)

A patched game needs three things together (docs/GAME_PATCH.md):
  * RPCS3's patch file patches/<TITLEID>_patch.yml (gamepatch.player_patch_text: one entry with the year and the 32 teams,
    the intro, login and news entries, for the game's 1.00 and for update 1.01, whichever RPCS3 runs: game_version) and
    the switches in config/patch_config.yml (RPCS3's list of ticked entries, at the top of its folder on Linux / Mac:
    config_file, carry_over; the news entry is ticked with the 32 teams,
    the intro and login entries are the window's two switches);
  * the game's database description and database for 32 teams, db/nhlng-meta.xml and db/nhlng.db, as loose files in the
    game's folder (dev_hdd0/game/<TITLEID>/USRDIR), made from the player's own disc (no file of the game's is shipped); the
    database carries the next seasons' calendars, made from the data pack as a patch roster has them (calendar_roster);
  * a roster made for the patch (pipeline.patch_roster): every update while the game is patched makes one.

Safety, as for the pictures (art/install.py): nothing is written while RPCS3 runs; a patch file or db file that was there
before is copied aside and comes back on remove(); the list of what was written is the program's own 'patch' store
(%LOCALAPPDATA%\\NHLLegacyRosterUpdater\\patch), apart from the pictures', so "Restore the game's own pictures" leaves the
patch alone and Unpatch leaves the pictures. patch_config.yml is RPCS3's file with every game's switches: only our
entries' lines under our PPU hashes (EU 1.00, NA 1.00, update 1.01 for both) are added or taken out, every other line
stays as it is, entries that already had our names come back as they were (config_before.json), and a copy of the file
is kept (patch/backup) before the first change. Rosters and Season / Be a GM saves are never touched.
"""
import hashlib
import json
import os
import shutil
import struct

from . import datasource, gamepatch, savedata
from .art import install, menus, onlinestart, pressstart
from .roster import Roster
from .sfo import Sfo

STORE = install.PATCH_STORE
GAME = "NHL Legacy"                 # the game's name in RPCS3's patch lists
ENTRIES = (gamepatch.PLAYER_ENTRY, gamepatch.INTRO_ENTRY, gamepatch.LOGIN_ENTRY, gamepatch.NEWS_ENTRY,
           gamepatch.ONLINE_ENTRY, gamepatch.ONLINE_START_ENTRY)   # the last one is ticked for one start only (set_online_start)
NO_PRESS = True                     # the intro skip also skips Press Start (art/pressstart.py; lab 47d passed, EU; the
                                    # NA disc's file is the same bytes)
PRESS_SOURCE = 'press:' + pressstart.PRESS_VERSION
SCREENS_SOURCE = 'online:' + onlinestart.FILES_VERSION      # the Welcome back panel and the matchmaking screen (set_online)
MENU_SOURCE = 'menus:' + menus.MENUS_VERSION + menus.HIDE   # the main menu with the start's cave: the same tag the Photos install writes


class PatchError(RuntimeError):
    """Something the player has to fix (RPCS3 running, game not found); the message says what."""


def config_file(rpcs3):
    """RPCS3's list of ticked patches. On Windows config/patch_config.yml (RPCS3 since 2023), else next to its data (older
    ones). On Linux and Mac always next to its data (~/.config/rpcs3/patch_config.yml): RPCS3 adds the config/ folder only
    on Windows (fs::get_config_dir(true)), so a config/patch_config.yml there is never read (a Linux tester's damaged roster:
    the program believed the game patched)."""
    old = os.path.join(rpcs3.folder, 'patch_config.yml')
    if not savedata.WINDOWS:
        return old
    folder = os.path.join(rpcs3.folder, 'config')
    return old if os.path.isfile(old) and not os.path.isdir(folder) else os.path.join(folder, 'patch_config.yml')


def carry_over(rpcs3):
    """Linux / Mac: our switches in the config/patch_config.yml that programs before 0.85.0 wrote (RPCS3 never reads it
    there, config_file) moved into RPCS3's own file and out of the old one, so a game patched then is patched now: its
    patch file and db files are in already. Done also while RPCS3 runs (it reads the file when a game starts); the old
    file's other lines stay, the file goes when nothing is left. Returns True when something moved."""
    if savedata.WINDOWS or rpcs3 is None or not rpcs3.patchable:
        return False
    stray = os.path.join(rpcs3.folder, 'config', 'patch_config.yml')
    old = _read(stray)
    found = {(t, v): ticked(old, t, v) for t in gamepatch.HASHES for v in gamepatch.VERSIONS}
    if not any(found.values()):
        return False
    path = config_file(rpcs3)
    before = text = _read(path)
    saved = _load_saved()
    saved.pop(os.path.abspath(stray), None)     # what the old file had before us: nothing RPCS3 ever read
    mine = _kept(saved, path)
    for (title, version), names in found.items():
        old = config_with(old, title, set(), version)
        if names:
            hash_ = gamepatch.hash_of(title, version)
            if hash_ not in mine:
                mine[hash_] = entries_before(before, hash_)
            text = config_with(text, title, ticked(text, title, version) | names, version)
    _store_saved(saved)
    if text != before:
        _write_config(rpcs3, text)
    if old.strip():
        with open(stray + '.tmp', 'w', encoding='utf-8', newline='') as f:
            f.write(old)
        os.replace(stray + '.tmp', stray)
    else:
        os.remove(stray)
        if not os.listdir(os.path.dirname(stray)):
            os.rmdir(os.path.dirname(stray))
    return True


def _read_config(rpcs3):
    """RPCS3's patch_config.yml as text (after carry_over)."""
    carry_over(rpcs3)
    return _read(config_file(rpcs3))


def patches_dir(rpcs3):
    return os.path.join(rpcs3.folder, 'patches')


def patch_file(rpcs3, title):
    """RPCS3 reads <TITLEID>_patch.yml from its patches folder when that game starts."""
    return os.path.join(patches_dir(rpcs3), f"{title}_patch.yml")


# --- patch_config.yml, as text --------------------------------------------------------------------
def _read(path):
    try:
        with open(path, encoding='utf-8-sig', newline='') as f:
            return f.read()
    except FileNotFoundError:
        return ''


def _block(lines, hash_):
    """(start, end) of the lines of `PPU-<hash_>:` (a line at the left edge up to the next one), or None."""
    head = f"PPU-{hash_}:"
    for start, line in enumerate(lines):
        if line.rstrip() in (head, f'"{head[:-1]}":'):
            end = start + 1
            while end < len(lines) and (not lines[end].strip() or lines[end][:1] in (' ', '\t')):
                end += 1
            return start, end
    return None


def _entries(lines, start, end):
    """{entry name: (first line, end)} of the block lines[start:end] (entries are the lines indented by two)."""
    found, name, at = {}, None, None
    for i in range(start + 1, end + 1):
        line = lines[i] if i < end else ''
        is_entry = i == end or (line.startswith('  ') and line[2:3] not in (' ', '') and line.rstrip().endswith(':'))
        if is_entry:
            if name is not None:
                found[name] = (at, i)
            if i < end:
                name, at = line.strip()[:-1].strip('"\''), i
    return found


def _serials(lines, at, stop):
    """{title id: (first line, end)} of the entry lines[at:stop]: the lines indented by six (under the game's name), each
    with its game version and switch below it."""
    found, name, first = {}, None, None
    for i in range(at + 1, stop + 1):
        line = lines[i] if i < stop else ''
        if i == stop or (line.strip() and len(line) - len(line.lstrip(' ')) <= 6):
            if name is not None:
                found[name] = (first, _end(lines, first, i))
                name = None
            if i < stop and line.startswith(' ' * 6) and line[6:7] != ' ' and line.rstrip().endswith(':'):
                name, first = line.strip()[:-1].strip('"\''), i
    return found


def _end(lines, start, stop):
    """`stop` moved back over the blank lines at the end of lines[start:stop] (they stay after it)."""
    while stop > start + 1 and not lines[stop - 1].strip():
        stop -= 1
    return stop


def _serial_lines(title, version):
    return [f"      {title}:", f"        {version}:", "          Enabled: true"]


def _entry_lines(name, title, version='01.00'):
    return [f"  {name}:", f"    {GAME}:"] + _serial_lines(title, version)


def config_with(text, title, wanted, version='01.00'):
    """`text` (patch_config.yml) with our entries of the version `title` of the game in its game version `version`:
    those named in `wanted` ticked, our other ENTRIES gone; every line that is not ours stays as it is (an emptied entry
    or PPU block goes). Update 1.01 is one program for EU and NA: an entry under its hash lists both, each with its own
    lines, in title order."""
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines()
    hash_ = gamepatch.hash_of(title, version)
    if _block(lines, hash_) is None:
        if not wanted:
            return text
        lines.append(f"PPU-{hash_}:")
    start, end = _block(lines, hash_)
    found = _entries(lines, start, end)
    for name in sorted((n for n in ENTRIES if n in found), key=lambda n: found[n][0], reverse=True):
        at, stop = found[name]
        serials = _serials(lines, at, stop)
        if not [t for t in serials if t != title]:
            del lines[at:stop]                  # ours alone: the whole entry
        elif title in serials:
            del lines[slice(*serials[title])]   # the other version's lines stay
    start, end = _block(lines, hash_)
    add = []
    for name in ENTRIES:
        if name not in wanted:
            continue
        found = _entries(lines, start, end)
        if name not in found:
            add += _entry_lines(name, title, version)
            continue
        at, stop = found[name]
        serials = _serials(lines, at, stop)
        later = [serials[t][0] for t in sorted(serials) if t > title]
        where = later[0] if later else _end(lines, at, stop)
        lines[where:where] = _serial_lines(title, version)
        end += 3
    end = _end(lines, start, end)
    lines[end:end] = add
    if end + len(add) == start + 1:             # nothing left under our hash
        del lines[start]
    out = newline.join(lines)          # RPCS3 itself ends the file without a newline: keep what the file has
    return out + newline if out and (text.endswith('\n') or not text) else out


def entries_before(text, hash_):
    """Entries with our names that `text` (patch_config.yml) already has under the PPU hash `hash_`, before we change it
    (the player may have ticked a patch of the same name by hand): [(name, its lines, the name of the entry above it or
    None)]. remove() puts them back where they were."""
    lines = text.splitlines()
    where = _block(lines, hash_)
    if not where:
        return []
    found = _entries(lines, *where)
    order = sorted(found, key=lambda n: found[n][0])
    out = []
    for i, name in enumerate(order):
        if name in ENTRIES:
            above = order[i - 1] if i else None     # put back in this order, so one of ours above is back first
            at, stop = found[name]
            out.append((name, lines[at:_end(lines, at, stop)], above))
    return out


def config_restored(text, hash_, saved):
    """`text` with the entries `saved` (entries_before) back under the PPU hash `hash_`, each below the entry that was
    above it (or at the top, or at the end when that one is gone)."""
    if not saved:
        return text
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines()
    if not _block(lines, hash_):
        lines.append(f"PPU-{hash_}:")
    for name, body, above in saved:
        start, end = _block(lines, hash_)
        found = _entries(lines, start, end)
        if name in found:
            continue
        if above is None:
            at = start + 1
        elif above in found:
            at = _end(lines, found[above][0], found[above][1])
        else:
            at = _end(lines, start, end)
        lines[at:at] = list(body)
    out = newline.join(lines)
    return out + newline if text.endswith('\n') else out


def all_hashes():
    """Every PPU hash of the game: EU and NA 1.00, then update 1.01 (one program for both)."""
    return list(dict.fromkeys(gamepatch.hash_of(t, v) for v in gamepatch.VERSIONS for t in gamepatch.HASHES))


def _saved_path():
    return os.path.join(datasource.app_dir(STORE), 'config_before.json')


def _load_saved():
    try:
        with open(_saved_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _store_saved(saved):
    with open(_saved_path(), 'w', encoding='utf-8') as f:
        json.dump(saved, f, indent=1, sort_keys=True)


def _kept(saved, path):
    """The entries kept for the patch_config.yml at `path` (entries_before), by PPU hash (older programs kept them by
    title id: one hash each then)."""
    mine = saved.setdefault(os.path.abspath(path), {})
    for title, hash_ in gamepatch.HASHES.items():
        if title in mine:
            mine.setdefault(hash_, mine.pop(title))
    return mine


def ticked(text, title, version='01.00'):
    """Our entries ticked for the version `title` of the game in its game version `version` in `text`
    (patch_config.yml): a set of names."""
    lines = text.splitlines()
    where = _block(lines, gamepatch.hash_of(title, version))
    if not where:
        return set()
    found = _entries(lines, *where)
    out = set()
    for name in ENTRIES:
        mine = _serials(lines, *found[name]).get(title) if name in found else None
        if mine and any(line.strip() == 'Enabled: true' for line in lines[slice(*mine)]):
            out.add(name)
    return out


def _write_config(rpcs3, text):
    path = config_file(rpcs3)
    if os.path.isfile(path):            # a copy of RPCS3's own file before our first change, kept for good
        kept = os.path.join(datasource.app_dir(STORE, 'backup'),
                            hashlib.sha1(os.path.abspath(path).encode()).hexdigest()[:16] + '_patch_config.yml')
        if not os.path.exists(kept):
            shutil.copy2(path, kept)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    os.replace(tmp, path)


# --- the db files ---------------------------------------------------------------------------------
def calendar_roster(disc, pack):
    """The game's own roster from `disc` with the patch's calendars, as patch_roster gives every patch roster: the 84
    games of the 32 teams and the All-Star row (schedule.ALL_PATCH), the AHL of 32 (farm_fit) and the next seasons'
    calendar (future_fit), all from the data pack `pack`, and six-bit rights (rights_wide, which check_db asks of the
    roster the db is made for). Save bytes: what the db files' next seasons are made from when no patch roster is at
    hand (the Patch button)."""
    from . import schedule, stock
    if not pack.get('schedule') or not pack.get('ahl_schedule'):
        raise PatchError("This program's data has no 2026-27 calendar, so the game patch cannot be made. "
                         "Download the newest version of the program.")
    R = Roster(stock.from_disc(disc))
    schedule.apply(R, pack['schedule'], schedule.ALL_PATCH)
    gamepatch.farm_fit(R, pack['ahl_schedule'])
    gamepatch.future_fit(R)
    gamepatch.rights_wide(R)
    return R.f.build()


def db_files(disc, roster):
    """The game's database description and database for 32 teams (gamepatch.fit_meta, fit_db) from the game's disc
    (`disc`: an image or the game's folder; EU and NA hold the same two files), the database with the next seasons'
    calendars of `roster` (save bytes: a patch roster, or calendar_roster's). Returns (meta, db); PatchError when one
    does not pass its checks."""
    meta = gamepatch.fit_meta(gamepatch.disc_meta(disc))
    problems = gamepatch.check_meta(meta)
    if problems:
        raise PatchError("The game's database description does not pass the checks: " + "; ".join(problems[:3]))
    db = gamepatch.fit_db(gamepatch.disc_db(disc), meta, Roster(roster))
    problems = gamepatch.check_db(db, meta, Roster(roster))
    if problems:
        raise PatchError("The game's database does not pass the checks: " + "; ".join(problems[:3]))
    return meta, db


def write_db(rpcs3, titles, meta, db):
    """The two db files into the game folders of `titles` (kept copies of what was there). Returns their paths."""
    install.move_entries('db/', install.ART_STORE, STORE)       # written with the pictures by team32-test before
    writer = install._Writer([rpcs3.game_folder(t) for t in titles], store=STORE)
    try:
        writer.write(gamepatch.META_FILE, meta, 'meta:' + hashlib.sha1(meta).hexdigest())
        writer.write(gamepatch.DB_FILE, db, 'db:' + hashlib.sha1(db).hexdigest())
    finally:
        writer.save()
    return [os.path.join(rpcs3.game_folder(t), *rel) for t in titles for rel in (gamepatch.META_FILE, gamepatch.DB_FILE)]


def find_disc(rpcs3, titles):
    """A disc of the game RPCS3 knows, the versions in `titles` first (either one makes the db files)."""
    return next((rpcs3.game_disc(t) for t in list(titles) + list(gamepatch.HASHES) if rpcs3.game_disc(t)), None)


# --- in, state, out -------------------------------------------------------------------------------
def check(rpcs3, titles):
    """Raise PatchError, with what to do, when the patch cannot be put in now."""
    if rpcs3 is None or not rpcs3.patchable:
        raise PatchError("The game patch needs RPCS3: pick the RPCS3 program (rpcs3.exe on Windows). A folder of saves or "
                         "NHL Legacy Native cannot take it.")
    if savedata.running_rpcs3():
        raise PatchError("Close RPCS3 first: the game patch can only be put in or taken out while RPCS3 is closed.")
    if not find_disc(rpcs3, titles):
        raise PatchError("RPCS3 does not say where your copy of the game is, so the game patch cannot be made. "
                         "Start the game once from RPCS3's game list, then try again.")


def install_patch(rpcs3, titles, roster=None, intro=True, login=False, say=print, pack=None):
    """Patch the versions `titles` of the game in `rpcs3`: the patch file, the switches (the 32-team entry, and the
    intro / login entries when `intro` / `login`), the db files with the next seasons' calendars of `roster` (save bytes
    of a patch roster), else of calendar_roster (from the data pack `pack`, default the program's own). Returns the
    titles patched."""
    titles = [t for t in gamepatch.HASHES if t in titles]
    check(rpcs3, titles)
    disc = find_disc(rpcs3, titles)
    if roster is None:
        say("Game patch: making the game's database for 32 teams from your disc")
        roster = calendar_roster(disc, pack if pack is not None else datasource.load_pack(say, offline=True))
    meta, db = db_files(disc, roster)
    write_db(rpcs3, titles, meta, db)
    writer = install._Writer([patches_dir(rpcs3)], store=STORE)
    text = gamepatch.player_patch_text().encode()     # one file for both (update 1.01's entries name both)
    try:
        for title in titles:
            writer.write((os.path.basename(patch_file(rpcs3, title)),), text,
                         f"patch:{gamepatch.TEAMS_VERSION}:" + hashlib.sha1(text).hexdigest())
    finally:
        writer.save()
    wanted = _wanted(intro, login)
    before = text = _read_config(rpcs3)
    saved = _load_saved()
    mine = _kept(saved, config_file(rpcs3))
    for title in titles:
        for version in gamepatch.VERSIONS:      # 1.00 and update 1.01: whichever the player's game runs
            hash_ = gamepatch.hash_of(title, version)
            if hash_ not in mine:       # how our names looked before our first change; kept until remove()
                mine[hash_] = entries_before(before, hash_)
            text = config_with(text, title, wanted | _online_on(text, title, version), version)
    _store_saved(saved)
    if text != before:
        _write_config(rpcs3, text)
    set_press(rpcs3, titles, intro, disc, say)
    say(f"Game patch {gamepatch.TEAMS_VERSION} is in RPCS3 for " + " and ".join(savedata.region(t) for t in titles))
    return titles


def _wanted(intro, login):
    """The entries ticked: the 32 teams and the news always, the intro / login entries when `intro` / `login`."""
    return ({gamepatch.PLAYER_ENTRY, gamepatch.NEWS_ENTRY} | ({gamepatch.INTRO_ENTRY} if intro else set())
            | ({gamepatch.LOGIN_ENTRY} if login else set()))


def set_switches(rpcs3, titles, intro, login):
    """The intro / login entries of the patched versions among `titles` ticked as `intro` / `login` (the 32-team and
    news entries stay): only patch_config.yml changes, no disc needed. Returns the titles changed."""
    if savedata.running_rpcs3():
        raise PatchError("Close RPCS3 first: the game patch can only be changed while RPCS3 is closed.")
    patched = [t for t in patched_titles(rpcs3) if t in titles]
    wanted = _wanted(intro, login)
    before = text = _read_config(rpcs3)
    for title in patched:
        for version in covered(_read(patch_file(rpcs3, title)), title):
            text = config_with(text, title, wanted | _online_on(text, title, version), version)
    if text != before:
        _write_config(rpcs3, text)
    if patched:
        set_press(rpcs3, patched, intro)
    return patched


def _online_on(text, title, version):
    """{ONLINE_ENTRY} when `text` (patch_config.yml) has it ticked for `title` in `version`, else nothing: the 32-team
    switches keep an online setup as it is."""
    return {gamepatch.ONLINE_ENTRY} & ticked(text, title, version)


def set_online(rpcs3, titles, on, say=print):
    """Tick (`on`) or untick the online entry (gamepatch.ONLINE_ENTRY) for the versions `titles` of the game, 1.00 and
    update 1.01 alike; the patch file is written first when it is not there. It works without the 32-team patch and
    leaves that and the intro switches as they are. RPCS3 closed; no disc needed. Returns the titles changed."""
    titles = [t for t in gamepatch.HASHES if t in titles]
    if rpcs3 is None or not rpcs3.patchable:
        raise PatchError("Online play needs RPCS3: pick the RPCS3 program (rpcs3.exe on Windows). A folder of saves or "
                         "NHL Legacy Native cannot play online.")
    if savedata.running_rpcs3():
        raise PatchError("Close RPCS3 first: the game patch can only be put in or taken out while RPCS3 is closed.")
    if on:
        writer = install._Writer([patches_dir(rpcs3)], store=STORE)
        text = gamepatch.player_patch_text().encode()
        try:
            for title in titles:
                writer.write((os.path.basename(patch_file(rpcs3, title)),), text,
                             f"patch:{gamepatch.TEAMS_VERSION}:" + hashlib.sha1(text).hexdigest())
        finally:
            writer.save()
    set_screens(rpcs3, titles, on, say=say)
    before = text = _read_config(rpcs3)
    saved = _load_saved()
    mine = _kept(saved, config_file(rpcs3))
    for title in titles:
        for version in gamepatch.VERSIONS:
            hash_ = gamepatch.hash_of(title, version)
            if hash_ not in mine:
                mine[hash_] = entries_before(before, hash_)
            keep = ticked(text, title, version) - {gamepatch.ONLINE_ENTRY, gamepatch.ONLINE_START_ENTRY}
            text = config_with(text, title, keep | ({gamepatch.ONLINE_ENTRY} if on else set()), version)
    _store_saved(saved)
    if text != before:
        _write_config(rpcs3, text)
    say(("Online play is set up in RPCS3 for " if on else "Online play is switched off in RPCS3 for ")
        + " and ".join(savedata.region(t) for t in titles))
    return titles


def set_screens(rpcs3, titles, on, disc=None, say=print):
    """The Welcome back panel and the matchmaking screen that go on by themselves (art/onlinestart.py) in the game folders of
    `titles` when `on`, else the game's own files back. Made from the player's disc; a disc whose files are not the ones the
    change was made for keeps the screens as they are (the lobby's steps are then pressed by hand). Returns whether they are in."""
    writer = install._Writer([rpcs3.game_folder(t) for t in titles], store=STORE)
    try:
        if not on:
            for rel in (onlinestart.WELCOME_REL, onlinestart.MATCH_REL, menus.REL):     # the menu only if this store wrote it
                writer.drop(rel)
            return False
        screens = all(writer.current(rel, SCREENS_SOURCE) for rel in (onlinestart.WELCOME_REL, onlinestart.MATCH_REL))
        menu = _menu_in(rpcs3, titles)
        if screens and menu:
            return True
        try:
            source = disc or find_disc(rpcs3, titles)
            files = {} if screens else onlinestart.screen_files(source)
            if not menu:        # the start's cave sits in the main menu file, which the Photos install makes too (and then owns)
                files[menus.REL] = menus.menu_files(source)[menus.REL]
        except (ValueError, KeyError, OSError) as err:
            say(f"Online play: the game's screens stay as they are, you press X on them yourself ({err})")
            return False
        for rel, data in sorted(files.items()):
            writer.write(rel, data, MENU_SOURCE if rel == menus.REL else SCREENS_SOURCE)
        return True
    finally:
        writer.save()


def _menu_in(rpcs3, titles):
    """Is the main menu with the start's cave in the game folders of `titles`, written by this program (here or by the Photos install)?"""
    dirs = [rpcs3.game_folder(t) for t in titles]
    return any(install._Writer(dirs, store=store).current(menus.REL, MENU_SOURCE) for store in (STORE, install.ART_STORE))


def screens_in(rpcs3, title):
    """Are the two screens and the main menu of set_screens in the game folder of `title` (written by this program, still ours)?"""
    writer = install._Writer([rpcs3.game_folder(title)], store=STORE)
    return (all(writer.current(rel, SCREENS_SOURCE) for rel in (onlinestart.WELCOME_REL, onlinestart.MATCH_REL))
            and _menu_in(rpcs3, [title]))


def auto_start(rpcs3, title):
    """Can the game be started into the lobby's search by the patch (no key at all)? The patch file must hold the entry
    (it does for 1.00 and update 1.01) and the two screens must be in."""
    if rpcs3 is None or getattr(rpcs3, 'plain', False):
        return False
    version = game_version(rpcs3, title)
    return (f"  {gamepatch.ONLINE_START_ENTRY}:" in _read(patch_file(rpcs3, title)) and screens_in(rpcs3, title)
            and {gamepatch.ONLINE_ENTRY, gamepatch.INTRO_ENTRY} <= ticked(_read_config(rpcs3), title, version))


def set_online_start(rpcs3, titles, on):
    """Tick (`on`) or untick the online start entry (gamepatch.ONLINE_START_ENTRY: the game goes to the lobby's search by
    itself) for the game version each of `titles` has (1.00 or update 1.01); everything else stays ticked as it is. RPCS3 closed. It is ticked for one
    start only: the program unticks it as soon as the game has read it (unticking is allowed while RPCS3 runs: it reads the
    patch file at the game's start). Returns the titles changed."""
    if on and savedata.running_rpcs3():
        raise PatchError("Close RPCS3 first: the game patch can only be changed while RPCS3 is closed.")
    before = text = _read_config(rpcs3)
    done = []
    for title in (t for t in gamepatch.HASHES if t in titles):
        version = game_version(rpcs3, title)
        keep = ticked(text, title, version) - {gamepatch.ONLINE_START_ENTRY}
        if on and not auto_start(rpcs3, title):
            continue
        text = config_with(text, title, keep | ({gamepatch.ONLINE_START_ENTRY} if on else set()), version)
        done.append(title)
    if text != before:
        _write_config(rpcs3, text)
    return done


def set_press(rpcs3, titles, on, disc=None, say=print):
    """The title screen that presses Start by itself (art/pressstart.py) in the game folders of `titles` when `on` (with
    the intro entry: without the game's quick boot the copy does nothing), else the game's own file back. Made from the
    player's disc; a disc whose file is not the one the change was made for keeps Press Start. Returns whether it is in."""
    on = on and NO_PRESS
    writer = install._Writer([rpcs3.game_folder(t) for t in titles], store=STORE)
    try:
        if not on:
            writer.drop(pressstart.REL)
            return False
        if writer.current(pressstart.REL, PRESS_SOURCE):
            return True
        try:
            files = pressstart.skip_files(disc or find_disc(rpcs3, titles))
        except (ValueError, KeyError, OSError) as err:
            say(f"Game patch: the game still waits for Start on its title screen ({err})")
            return False
        for rel, data in sorted(files.items()):
            writer.write(rel, data, PRESS_SOURCE)
        return True
    finally:
        writer.save()


def refresh_db(rpcs3, titles, roster, say=print):
    """After an update of a patched game: the db files of `titles` carry the next seasons' calendars of the patch
    roster `roster` (save bytes). They already do unless the program's data changed since the game was patched; then
    they are made again (RPCS3 closed). Returns True when they were written, a message when they could not be."""
    titles = [t for t in gamepatch.HASHES if t in titles]
    disc = find_disc(rpcs3, titles)
    if disc is None:
        return False
    try:
        meta, db = db_files(disc, roster)
    except (PatchError, ValueError, OSError) as err:
        return f"{err}"
    paths = [os.path.join(rpcs3.game_folder(t), *gamepatch.DB_FILE) for t in titles]
    def same(path):
        try:
            with open(path, 'rb') as f:
                return f.read() == db
        except OSError:
            return False
    if all(same(p) for p in paths):
        return False
    if savedata.running_rpcs3():
        return ("the game's database for the patch is older than this roster's calendar. Close RPCS3 and press "
                "\"Patch again\" in step 2.")
    say("Game patch: the game's database gets this roster's next seasons")
    write_db(rpcs3, titles, meta, db)
    return True


def patched_titles(rpcs3):
    """The versions of the game patched in `rpcs3` (title ids), [] for none, no RPCS3 or NHL Legacy Native."""
    if rpcs3 is None or not getattr(rpcs3, 'patchable', True):
        return []
    return [t for t, s in state(rpcs3).items() if s['patched']]


def stale_titles(rpcs3):
    """The versions of the game whose patch in `rpcs3` is not for the game version RPCS3 runs (a patch put in before
    this program knew update 1.01): Patch again."""
    if rpcs3 is None or not getattr(rpcs3, 'patchable', True):
        return []
    return [t for t, s in state(rpcs3).items() if s['stale']]


def game_version(rpcs3, title):
    """The game version RPCS3 runs for `title`: an update's ('01.01') when its program is in the game's folder
    (dev_hdd0/game/<TITLEID>/USRDIR/EBOOT.BIN: RPCS3 starts it instead of the disc's; PARAM.SFO beside USRDIR says
    which), else the disc's '01.00'."""
    usr = rpcs3.game_folder(title)
    if not os.path.isfile(os.path.join(usr, 'EBOOT.BIN')):
        return gamepatch.VERSIONS[0]
    try:
        found = Sfo.load(os.path.join(os.path.dirname(usr), 'PARAM.SFO')).get('APP_VER')
    except (OSError, ValueError, struct.error):
        found = None
    return found if found in gamepatch.VERSIONS else gamepatch.VERSIONS[-1]


def covered(body, title):
    """The game versions of `title` the patch file `body` has the 32-team entry for."""
    return [v for v in gamepatch.VERSIONS if f"PPU-{gamepatch.hash_of(title, v)}:" in body
            and f"        {title}: [ {v} ]" in body]


def state(rpcs3):
    """{title id: {'patched': the 32-team entry is ticked for the game version RPCS3 runs and our patch file has it,
    'version': its patch version or None, 'game': the game version RPCS3 runs ('01.00', update '01.01'), 'stale': the
    patch is in, but not for that game version (Patch again), 'intro', 'login', 'news', 'online': those entries ticked, 'rights':
    the bits the game's db description gives the player rights (gamepatch.meta_rights; None without one)}} for both
    versions of the game."""
    out = {}
    real = rpcs3 is not None and rpcs3.patchable
    text = _read_config(rpcs3) if real else ''
    for title in gamepatch.HASHES:
        game = game_version(rpcs3, title) if real else gamepatch.VERSIONS[0]
        body = _read(patch_file(rpcs3, title)) if real else ''
        version = rights = None
        if f"  {gamepatch.PLAYER_ENTRY}:" in body:
            tail = body.split(f"  {gamepatch.PLAYER_ENTRY}:", 1)[1]
            version = next((line.split(':', 1)[1].strip() for line in tail.splitlines()
                            if line.strip().startswith('Patch Version:')), None)
            rights = installed_rights(rpcs3, title)
        has = covered(body, title) if version else []
        on = ticked(text, title, game)
        patched = gamepatch.PLAYER_ENTRY in on and game in has
        stale = not patched and any(gamepatch.PLAYER_ENTRY in ticked(text, title, v) for v in has)
        out[title] = {'patched': patched, 'version': version, 'game': game, 'stale': stale,
                      'intro': gamepatch.INTRO_ENTRY in on, 'login': gamepatch.LOGIN_ENTRY in on,
                      'news': gamepatch.NEWS_ENTRY in on, 'online': gamepatch.ONLINE_ENTRY in on, 'rights': rights}
    return out


def installed_rights(rpcs3, title):
    """The bits the db description in `title`'s game folder gives the player rights, or None (no file there)."""
    try:
        with open(os.path.join(rpcs3.game_folder(title), *gamepatch.META_FILE), 'rb') as f:
            return gamepatch.meta_rights(f.read())
    except (OSError, ValueError):
        return None


def installed(rpcs3):
    """Is anything of the patch in (a switch, our patch file, a db file): what Unpatch would take out."""
    if rpcs3 is not None and not rpcs3.patchable:
        return False
    text = _read_config(rpcs3) if rpcs3 is not None else ''
    if any(ticked(text, t, v) for t in gamepatch.HASHES for v in gamepatch.VERSIONS):
        return True
    if any(install.load_manifest(STORE)['games'].values()):
        return True
    return any(key.startswith('db/') for files in install.load_manifest(install.ART_STORE)['games'].values()
               for key in files)


def remove(rpcs3, say=print):
    """Take the game patch out of `rpcs3`: our switches out of patch_config.yml, our patch files and db files gone (or the
    files that were there before back). Returns how many files were handled."""
    if savedata.running_rpcs3():
        raise PatchError("Close RPCS3 first: the game patch can only be put in or taken out while RPCS3 is closed.")
    before = text = _read_config(rpcs3)
    saved = _load_saved()
    mine = _kept(saved, config_file(rpcs3))
    saved.pop(os.path.abspath(config_file(rpcs3)))
    for title in gamepatch.HASHES:
        for version in gamepatch.VERSIONS:
            text = config_with(text, title, set(), version)
    for hash_ in all_hashes():
        text = config_restored(text, hash_, mine.get(hash_))
    if text != before:
        _write_config(rpcs3, text)
    _store_saved(saved)
    install.move_entries('db/', install.ART_STORE, STORE)
    n = install.remove_store(STORE)
    say("The game patch is out of RPCS3: the game is as it was. Rosters made for the patch open only with it.")
    return n
