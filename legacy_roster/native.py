"""What the program does for NHL Legacy Native, the PC port, besides what it does for RPCS3 (savedata.Native).

The port reads no loose files of its own folders: its launcher joins the update and the mods into data/hdd0 with hard
links when PLAY is pressed, or `NHLLauncher.exe --compose` runs (no window; seen 2026-11-02: exit 0, logs/compose.log). Every
file we write is in one mod, mods/Puck Peak. Two mods with the same file: the one higher in the Mods tab wins, and the list
is [launcher] mod_order, then the rest by name (seen 2026-11-02; the port's README says the other way). So "Imported from
update folder", which holds whatever the player's RPCS3 had there, would beat ours by its name, and we go first.

Nothing here writes into data/, and nhl_settings.ini changes only in the one line `mod_order`.
"""
import os
import subprocess

from . import savedata

TIMEOUT = 120               # seconds; joining links takes about a second


def _text(host):
    """The ini as text and its line ending, (None, None) when it is not there or not plain text: then it is left alone."""
    try:
        with open(host.ini, 'rb') as f:
            data = f.read()
        text = data.decode('utf-8')
    except (OSError, UnicodeDecodeError):
        return None, None
    return text, '\r\n' if '\r\n' in text else '\n'


def other_mods(host):
    """The other mods in the Mods tab, by name. The launcher leaves out folders that start with a dot."""
    try:
        return sorted(n for n in os.listdir(host.mods) if n != savedata.NATIVE_MOD and not n.startswith('.')
                      and os.path.isdir(os.path.join(host.mods, n)))
    except OSError:
        return []


def order_of(host):
    """The names in [launcher] mod_order."""
    text = savedata.read_ini(host.ini).get('launcher', {}).get('mod_order', '')
    return [n.strip() for n in text.split('|') if n.strip()]


def first_in_order(host):
    """Our mod to the top of the Mods tab when another mod could cover its files, keeping the other names as they are.
    Returns True when the ini changed."""
    order = order_of(host)
    if not other_mods(host) or (order and order[0] == savedata.NATIVE_MOD):
        return False
    text, end = _text(host)
    if text is None:
        return False
    line = 'mod_order = ' + '|'.join([savedata.NATIVE_MOD] + [n for n in order if n != savedata.NATIVE_MOD])
    lines = text.split(end)
    section, place, launcher = '', None, None
    for number, raw in enumerate(lines):
        bare = raw.strip()
        if bare.startswith('[') and bare.endswith(']'):
            section = bare[1:-1]
            launcher = number if section == 'launcher' else launcher
        elif section == 'launcher' and bare.split('=', 1)[0].strip() == 'mod_order' and '=' in bare:
            place = number
    if place is not None:
        lines[place] = line
    elif launcher is not None:
        lines.insert(launcher + 1, line)
    else:
        lines[len(lines) - (lines[-1] == ''):0] = ['[launcher]', line]
    tmp = host.ini + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(end.join(lines).encode('utf-8'))
    os.replace(tmp, host.ini)
    return True


def mod_off(host):
    """Did the player switch our mod off in the Mods tab?"""
    if not os.path.isdir(host.mod):
        return False
    return savedata.read_ini(host.ini).get('mods', {}).get(savedata.NATIVE_MOD, '1').strip() == '0'


def mod_roster(host):
    """The mod whose roster the launcher uses (its "Use roster"), or None. It takes our rosters aside at PLAY."""
    return savedata.read_ini(host.ini).get('launcher', {}).get('roster', '').strip() or None


def game_patch_files(host):
    """The other mods holding the patched game's database (db/nhlng.db, db/nhlng-meta.xml): "Imported from update folder"
    brings them along from an RPCS3 that had the game patch, and the unpatched port cannot read a roster with them."""
    return [name for name in other_mods(host)
            if any(os.path.isfile(os.path.join(host.mods, name, 'USRDIR', 'db', f)) for f in ('nhlng.db', 'nhlng-meta.xml'))]


def clear_mod(host):
    """Takes our mod away when nothing of ours is left in it, so the Mods tab shows no empty line."""
    for folder in (os.path.join(host.mod, 'USRDIR'), host.mod):
        try:
            os.rmdir(folder)
        except OSError:
            pass


def compose(host, say=print):
    """Join the update and the mods now, so the game runs the new files also when started without the launcher. The launcher
    does this at PLAY as well, so a failure costs nothing: it is said once. Windows only. Returns True when it ran."""
    if not savedata.WINDOWS or not os.path.isfile(host.launcher):
        return False
    try:
        run = subprocess.run([host.launcher, '--compose', '--install', host.folder], cwd=host.folder, timeout=TIMEOUT,
                             env=savedata.clean_environment(), capture_output=True,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.SubprocessError):
        run = None
    if run is None or run.returncode != 0:
        say("Press PLAY in NHL Legacy Native's launcher: it puts the new files in when the game starts.")
        return False
    return True


def settle(host, say=print):
    """After files went into or out of our mod: the mod first in the list, the empty mod gone, and the game's folder joined
    again."""
    clear_mod(host)
    first_in_order(host)
    return compose(host, say)


def notes(host):
    """What the player should know about this install, in plain words, for Setup."""
    out = []
    if mod_off(host):
        out.append("The mod \"Puck Peak\" is switched off in the launcher's Mods tab: the game shows none of your pictures "
                   "or team names until it is on.")
    roster = mod_roster(host)
    if roster:
        out.append(f"The launcher's Mods tab has \"Use roster\" ticked for \"{roster}\": the game plays that roster. Untick "
                   "it to play the rosters you make here.")
    stale = game_patch_files(host)
    if stale:
        out.append(f"The mod \"{stale[0]}\" holds files of the 32-team game patch, which this game cannot use: rosters "
                   "may not load. Switch it off in the launcher's Mods tab.")
    return out
