"""The picture packs the program downloads from its own file server (0.32.0): `photos` (players' photos and club
logos), `looks` (this season's jerseys and centre-ice logos) and, since 0.76.0, `arenas`, `ice` and `masks`. They are
not inside the program. While a switch that needs a pack is on, the window downloads that pack (only that one) if it is
missing or changed, in the background (app/update.py, `sync(wanted=)`), and the next update uses it; the command line
downloads before `update --photos` (cli.py `packs`). A pack the server does not list yet is simply not offered.

    <files_url>manifest.json
        {"format": 1, "packs": {"photos": {"file": "photos-<sha12>.zip", "size": bytes, "sha256": "...",
                                           "built": "2026-10-20"},
                                "looks": {...}}}

On this PC the packs are in datasource.app_dir('packs'): `<name>-<sha12>.zip` and `state.json` ({name: manifest entry
+ 'local'}). A new pack gets a new file name, because Windows cannot replace a zip an update or the Jerseys window has
open; `prune` removes the old one at the next start, when nothing holds it any more. A download goes into
`<file>.part` and counts only when its size and SHA-256 match the manifest.

LEGACY_ROSTER_PACKS names a folder with photos.zip / looks.zip that is used instead (a developer's own packs,
private/packs); LEGACY_ROSTER_FILES_URL another server (datasource.files_url). The art modules open the packs with
`path(name)` (art/photopack.py, art/lookpack.py).
"""
import hashlib
import json
import os
import re

from . import datasource

NAMES = ('photos', 'looks', 'arenas', 'ice', 'masks',      # 0.76.0: arenas, ice and masks (art/parts.py PACK_OF)
         'portpatch')                                      # the game patch for NHL Legacy Native (patchinstall.PORT_PACK)
ASKED_FOR = ('portpatch',)                                 # downloaded only when named: an RPCS3 player has no use for it
FORMAT = 1
STATE = 'state.json'


class Cancelled(Exception):
    """The download was stopped (the switch went off, the window closed)."""


def folder():
    return datasource.app_dir('packs')


def _state():
    try:
        with open(os.path.join(folder(), STATE), encoding='utf-8') as f:
            state = json.load(f)
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(state):
    path = os.path.join(folder(), STATE)
    with open(path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(path + '.tmp', path)


def _valid(entry):
    return (isinstance(entry, dict) and isinstance(entry.get('size'), int) and entry['size'] > 0
            and isinstance(entry.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', entry['sha256'])
            and isinstance(entry.get('file'), str) and re.fullmatch(r'[A-Za-z0-9._-]+\.zip', entry['file']))


def _local(name, entry):
    return f"{name}-{entry['sha256'][:12]}.zip"


def dev_path(name):
    """A developer's own pack (LEGACY_ROSTER_PACKS/<name>.zip), or None."""
    where = os.environ.get('LEGACY_ROSTER_PACKS')
    path = os.path.join(where, f"{name}.zip") if where else None
    return path if path and os.path.isfile(path) else None


def _complete(entry):
    path = os.path.join(folder(), entry.get('local') or '')
    return path if entry.get('local') and os.path.isfile(path) and os.path.getsize(path) == entry.get('size') else None


def path(name):
    """The pack to use: a developer's own, else the complete download on this PC, else None."""
    entry = _state().get(name)
    return dev_path(name) or (_complete(entry) if isinstance(entry, dict) else None)


def have(name):
    return path(name) is not None


def manifest(timeout=20):
    """The server's list of packs ({name: entry}, only well-formed entries), or None: offline, no server, or a list
    made for a newer program."""
    try:
        listed = json.loads(datasource.http_get(datasource.files_url() + 'manifest.json', timeout=timeout, retries=1))
    except Exception:                  # no connection, no server, not JSON: try again at the next start
        return None
    if not isinstance(listed, dict) or listed.get('format') != FORMAT or not isinstance(listed.get('packs'), dict):
        return None
    return {name: entry for name, entry in listed['packs'].items() if name in NAMES and _valid(entry)}


def missing(listed, names=None):
    """The names whose pack on this PC is not the one `listed` (manifest) names, in NAMES order. `names`: only these
    packs are asked about (the ones the switched-on parts need); a pack the server does not list is not missing."""
    state = _state()
    out = []
    for name in NAMES:
        if (name not in names) if names is not None else (name in ASKED_FOR):
            continue
        entry = listed.get(name)
        if entry is None or dev_path(name):
            continue
        mine = state.get(name)
        if isinstance(mine, dict) and mine.get('sha256') == entry['sha256'] and _complete(mine):
            continue
        out.append(name)
    return out


def size_of(listed, names=None):
    """Bytes the packs `names` (default: every listed one) take."""
    return sum(listed[n]['size'] for n in (names if names is not None else listed) if n in listed)


def fetch(name, entry, progress=None, cancelled=None):
    """Download one pack (`entry` from the manifest) and make it the one in use. `progress(bytes so far)` after every
    piece; `cancelled()` True stops it (Cancelled). A file of another size or check sum is removed and refused
    (ValueError). Returns the pack's path."""
    target = os.path.join(folder(), _local(name, entry))
    part = target + '.part'
    sha = hashlib.sha256()
    got = [0]

    def block(data):
        if cancelled and cancelled():
            raise Cancelled()
        sha.update(data)
        got[0] += len(data)
        if got[0] > entry['size']:
            raise ValueError("The download is bigger than it should be.")
        if progress:
            progress(got[0])

    datasource.download_to(datasource.files_url() + entry['file'], part, on_block=block)
    if got[0] != entry['size'] or sha.hexdigest() != entry['sha256']:
        try:
            os.remove(part)
        except OSError:
            pass
        raise ValueError("The downloaded file is not the one that was published, so it was not used.")
    os.replace(part, target)
    state = _state()
    old = state.get(name)
    state[name] = dict(entry, local=os.path.basename(target))
    _save_state(state)
    if isinstance(old, dict) and old.get('local') and old['local'] != state[name]['local']:
        _remove(os.path.join(folder(), old['local']))         # an open old pack stays until prune
    return target


def sync(progress=None, cancelled=None, listed=None, wanted=None):
    """Download every pack that is missing or changed (`wanted`: only these names). `progress(fraction 0-1)` over all
    of them. Returns (names downloaded, None) or (names downloaded so far, the reason it stopped): 'offline' when the
    list cannot be read, else the error's text. Cancelled is passed on."""
    listed = manifest() if listed is None else listed
    if listed is None:
        return [], 'offline'
    names = missing(listed, wanted)
    total = size_of(listed, names) or 1
    done, base = [], 0
    for name in names:
        entry = listed[name]
        try:
            fetch(name, entry, progress and (lambda n, b=base: progress(min(1.0, (b + n) / total))), cancelled)
        except Cancelled:
            raise
        except Exception as err:       # the line dropped, a wrong file, a full disk: the next start tries again
            return done, str(err) or type(err).__name__
        done.append(name)
        base += entry['size']
    if progress:
        progress(1.0)
    return done, None


def _remove(path):
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def prune():
    """Remove the packs and pieces no longer in use (an old pack an earlier run still had open, a stopped download, a pack
    the program no longer has: the test versions' scoreboard)."""
    state = _state()
    if any(name not in NAMES for name in state):
        _save_state({name: entry for name, entry in state.items() if name in NAMES})
    keep = {e.get('local') for name, e in state.items() if name in NAMES and isinstance(e, dict)} | {STATE}
    for name in os.listdir(folder()):
        if name not in keep:
            _remove(os.path.join(folder(), name))


def status():
    """{name: (built, bytes) or None} of the packs on this PC."""
    state = _state()
    out = {}
    for name in NAMES:
        entry = state.get(name)
        dev = dev_path(name)
        out[name] = ('own copy', os.path.getsize(dev)) if dev else \
            (entry.get('built', ''), entry['size']) if isinstance(entry, dict) and _complete(entry) else None
    return out


def remove_all():
    """Remove every downloaded pack (what an update put into the game stays). Returns the bytes freed; a pack that
    is open now is removed at the next start."""
    _save_state({})                    # from now on none is in use; prune takes what could not go now
    freed = 0
    for name in os.listdir(folder()):
        full = os.path.join(folder(), name)
        size = os.path.getsize(full) if os.path.isfile(full) else 0
        if name != STATE and _remove(full):
            freed += size
    return freed
