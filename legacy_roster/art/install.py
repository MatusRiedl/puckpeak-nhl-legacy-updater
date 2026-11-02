"""Photos and logos: download, draw and install the pictures, and take them away again.

    install(rpcs3, title_id, portraits, logos)   after an update with "Photos and logos" on, or with the
                                                 player's own pictures only (menus=False: Roster editor's Save)
    prefetch(links, rpcs3, title_id)             before the roster is planned: which photos cannot be made
                                                 (no face, no download, NHL.com's grey stand-in)
    scan_claims(rpcs3)                           the picture numbers every roster and picture file on this PC uses
    give_back(numbers)                           take our pictures off numbers someone else uses
    remove()                                     the "Restore the game's own pictures" button

The pictures go, as loose files, into the game's own folder on RPCS3's hard disk
(dev_hdd0/game/<TITLEID>/USRDIR/fe/ion/artassets/...); the game reads a loose file there before
the one on the disc (tested in the game on 2026-10-03). Each art file is made from one of the
player's own disc (a template) with only the picture swapped, so nothing of the game's is shipped, and
the photos and logos are downloaded on the player's PC from the leagues' public sites.

The European (BLES02153) and North American (BLUS31540) versions each have their own folder; their
discs hold the same art and text files, so one set of pictures made from either disc serves both
(`also`: further versions that receive every file too).

Safety: nothing is written while RPCS3 runs; any file replaced is first copied to
%LOCALAPPDATA%\\NHLLegacyRosterUpdater\\art\\backup, and a list of everything written, per game
folder (art\\installed.json), lets remove() put every file back as it was. A picture already
installed from the same link is not made again, so a later update downloads only new or changed
photos.

Needs Pillow (images.py); the window exe has it.
"""
import concurrent.futures
import contextlib
import hashlib
import io
import json
import os
import shutil

from .. import datasource, savedata
from . import bigf, dds, lab
from .lab import ART, Disc, portrait_folder
from .photopack import PhotoPack, PictureCache, key_for

WORKERS = 6
PORTRAIT_KINDS = ('playerheads', 'playerheadssmall')
LOGO_KINDS = lab.LOGO_KINDS          # (folder, file prefix): plain, small banner, wide, calendar, dynasty
# the logo standing on its reflection: the favourite-team screens. The disc has one for each NHL team
# (art ids 0-29); Seattle and Vegas in the All-Star slots 30/31 get one made from Anaheim's file
REFLECTION = ('teamlogosreflection', 'r')
PORTRAIT_TEMPLATE = 100              # the disc portrait whose file new portraits are made from
# how logos are drawn (images.logo); a change redraws every installed logo once. '#2': the game's own
# sizes (images.LOGO_BOX), 0.8.0. '#3': the pictures with a white edge are drawn from ESPN's plain logos,
# not the white-silhouette ones for dark backgrounds (Tampa Bay and Toronto came out all white), 0.8.1.
# '#5': logos centred on their own middle, not on the shadow (testers, 0.9.0)
# '#4': the other kinds take the plain logo too where the game's own picture of that kind is coloured
# and the dark one a white silhouette (Toronto's calendar and wide logos)
LOGO_DRAWING = '#5'
SILHOUETTE = 0.8                     # share of white in a dark-background logo that makes it a silhouette
COLOURED = 0.3                       # average saturation of the game's own logo picture that makes it coloured
LOGO_ONLY_KINDS = ('c', 'w')         # pictures that are the logo alone (the banner 's' is mostly its colour band)
# the kinds drawn on a white edge (images.logo); they take the plain logo, the others (banner, watermark,
# calendar: on a dark or coloured ground) the one for dark backgrounds
EDGED_KINDS = ('t', 'd', 'r')
# the same for portraits: '#2', 0.8.0: studio photos on a shaded backdrop are cut out too (images.
# _shaded_background_mask), no longer shown in an oval
PORTRAIT_DRAWING = '#2'
UPDATE_ARCHIVE = 'patch.big'         # the game's update 1.01 puts its newer files there (USRDIR), text files among them


def logo_kinds(artid):
    """The logo pictures a team gets: every kind, and for the 32 NHL teams the reflection too."""
    return LOGO_KINDS + (REFLECTION,) if artid < 32 else LOGO_KINDS


class ArtError(RuntimeError):
    """Something the player has to fix (RPCS3 running, game not found); the message says what."""


# Each kind of file we install keeps its own list and kept copies (a store: a folder of the program's own files), so
# one kind is taken away without the other: the pictures ('art', "Restore the game's own pictures"), the game patch's
# files ('patch', patchinstall.py: its db files and RPCS3's patch file).
ART_STORE, PATCH_STORE = 'art', 'patch'


_REDIRECT = None            # export.py: a folder that holds the lists and kept copies instead of the program's own
_READ_ONLY_DIRS = ()        # game folders (USRDIR) that are only read while exporting (the update's text files)
_HOST = None                # use_host: the program's own lists and copies of NHL Legacy Native, away from RPCS3's
_HOST_READS = ()            # the game folders of that host that are only read (the update)


def use_host(rpcs3):
    """The game the program works on now. RPCS3's pictures and the PC port's are kept apart, each port install with its own
    lists and kept copies, so a player can have both and Restore takes away only the game picked. Set when a game is
    found: every list in this file then is that game's."""
    global _HOST, _HOST_READS
    native = rpcs3 is not None and getattr(rpcs3, 'native', False)
    _HOST = 'native-' + hashlib.sha1(os.path.normcase(rpcs3.folder).encode()).hexdigest()[:12] if native else None
    _HOST_READS = (rpcs3.update_folder(),) if native else ()


@contextlib.contextmanager
def redirected(folder, read_dirs=()):
    """While exporting files to a folder (export.py): the lists of written files and the kept copies go to `folder`, so the
    player's own lists (what is installed in his RPCS3, what Restore puts back) are neither read nor changed. `read_dirs`:
    game folders of the player's RPCS3 that are only read (update 1.01's text files)."""
    global _REDIRECT, _READ_ONLY_DIRS
    before = _REDIRECT, _READ_ONLY_DIRS
    _REDIRECT, _READ_ONLY_DIRS = folder, tuple(read_dirs)
    try:
        yield
    finally:
        _REDIRECT, _READ_ONLY_DIRS = before


def _paths(store=ART_STORE):
    if _REDIRECT:
        base = os.path.join(_REDIRECT, store)
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, 'installed.json'), os.path.join(base, 'backup')
    if _HOST:
        store = os.path.join(_HOST, store)
    return datasource.app_dir(store, 'installed.json'), datasource.app_dir(store, 'backup')


def load_manifest(store=ART_STORE):
    """{'games': {game folder: {file key: {'source': link, 'backup': path or None,
    'stamp': [size, time] of the file as written}}}}. 'stamp' tells a file of ours from one put
    there later (another picture pack); manifests before 0.6 have none."""
    path, _ = _paths(store)
    try:
        with open(path, encoding='utf-8') as f:
            m = json.load(f)
    except (OSError, ValueError):
        m = {}
    if 'games' not in m:                # version 0.4 and earlier: one game folder
        m = {'games': {m['game_dir']: m.get('files') or {}} if m.get('game_dir') else {}}
    return m


def _save_manifest(m, store=ART_STORE):
    path, _ = _paths(store)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(m, f, indent=0, sort_keys=True)
    os.replace(tmp, path)


def installed():
    """How many picture and text files are installed now (every game version together; a game folder that is not there
    any more does not count)."""
    return sum(len(files) for d, files in load_manifest()['games'].items() if os.path.isdir(d))


# --- making the pictures --------------------------------------------------------------------------
def _dds_bytes(template, img):
    """A DDS like `template` (bytes) holding the Pillow image `img` (the template's size)."""
    h = dds.Header(template)
    if img.size != (h.width, h.height):
        raise ValueError(f"the picture must be {h.width} x {h.height}")
    if h.fourcc == 'DXT5':
        buf = io.BytesIO()
        img.save(buf, 'DDS', pixel_format='DXT5')
        body = buf.getvalue()[128:]
    else:
        # plain 32-bit pixels: byte k of each pixel is the channel whose mask starts at bit 8k
        shift = {(m & -m).bit_length() - 1: 'RGBA'[c] for c, m in enumerate(h.masks) if m}
        body = img.convert('RGBA').tobytes('raw', ''.join(shift.get(8 * k, 'X') for k in range(4)))
    if len(body) != h.data_size:
        raise ValueError("the picture came out the wrong size")
    return h.raw + body


def art_file(template_art, img):
    """A new art file: the template (bytes of a disc art file) with `img` as its picture."""
    a = bigf.ArtFile(template_art)
    return a.with_image(_dds_bytes(a.image(), img))


def _template_size(template_art):
    h = dds.Header(bigf.ArtFile(template_art).image())
    return h.width, h.height


def _download(url):
    """A picture from a link; 'file:<path>' is a picture of the player's own (Roster editor)."""
    from PIL import Image
    if url.startswith('file:'):
        img = Image.open(url[5:])
    else:
        img = Image.open(io.BytesIO(datasource.http_get(url, timeout=30, retries=2)))
    img.load()
    return img


def _cacheable(url):
    return not url.startswith(('file:', 'badge:'))        # the player's own pictures are on his PC already


class NoPicture(ValueError):
    """A photo link that gives no picture of the player (a league's grey stand-in)."""


STAND_IN = "only a grey stand-in, no photo of him yet"


def _pictures(url, sizes, pack=None, cache=None):
    """{size: portrait} for one photo link (None when the photo shows no head; NoPicture for a stand-in). A
    picture this PC drew before (`cache`) or the program's photo pack has is used as it is; anything else is
    downloaded, drawn, and kept in the cache."""
    from . import images
    cache = cache if cache and _cacheable(url) else None
    if cache and cache.headless(url):
        return None
    stores = [s for s in (cache, pack) if s]
    photo = None
    drawn, out = {}, {}
    for size in sizes:
        pic = next((p for p in (s.portrait(url, size) for s in stores) if p is not None and not images.stand_in(p)),
                   None)
        if pic is None:
            photo = photo or _download(url)
            pic = drawn[size] = images.portrait(photo, size)
            if pic is None:
                if cache:
                    cache.put_portrait(url, None, None)
                return None
            if _cacheable(url) and images.stand_in(pic):      # not remembered: the league may put his photo
                raise NoPicture(STAND_IN)                          # under the same link (own pictures may be grey)
        out[size] = pic
    if cache and (512, 512) in drawn and (256, 128) in drawn:
        cache.put_portrait(url, drawn[(512, 512)], drawn[(256, 128)])
    return out


def make_portrait(url, templates, pack=None, cache=None):
    """{kind: art file bytes} for one photo link (None when the photo shows no head, see _pictures)."""
    sizes = {kind: _template_size(templates[kind]) for kind in PORTRAIT_KINDS}
    pics = _pictures(url, list(dict.fromkeys(sizes.values())), pack, cache)
    return None if pics is None else {kind: art_file(templates[kind], pics[size]) for kind, size in sizes.items()}


def prefetch(links, rpcs3, title_id, say=print, pack=None, cache=None, workers=WORKERS):
    """Before a build gives players their pictures (portraits.plan): {photo link: why} for the links that make no
    picture, so those players keep the one they have. The others are drawn into the picture cache now (nothing
    goes into the game folder), so the install after the save finds them there."""
    from . import images
    if not links:
        return {}
    disc = Disc(rpcs3.game_disc(title_id))
    sizes = list(dict.fromkeys(_template_size(disc.portrait(k, PORTRAIT_TEMPLATE)) for k in PORTRAIT_KINDS))
    pack = PhotoPack.open() if pack is None else pack or None
    cache = PictureCache() if cache is None else cache or None
    done = {e.get('source') for files in load_manifest()['games'].values() for key, e in files.items()
            if key.startswith('/'.join(ART + (PORTRAIT_KINDS[0],)))}

    def why(url):
        if url + PORTRAIT_DRAWING in done:
            return None
        stores = [s for s in ((cache if _cacheable(url) else None), pack) if s]
        small = next((p for p in (s.portrait(url, sizes[-1]) for s in stores) if p is not None), None)
        if small is not None and not images.stand_in(small):
            return None
        try:
            return None if _pictures(url, sizes, pack, cache) is not None else "no head found in it"
        except Exception as err:       # a photo that will not download or decode
            return str(err) or type(err).__name__

    say(f"Photos and logos: checking {len(links)} photos")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        found = dict(zip(links, pool.map(why, links)))
    return {url: text for url, text in found.items() if text}


def plain_logo_url(url):
    """ESPN's plain logo for the link of its dark-background one (the same link for any other logo)."""
    return url.replace('/500-dark/', '/500/')


def _saturation(template):
    """Average saturation (0-1) of the opaque pixels of a game art file's picture (a sample of them)."""
    _, _, pixels = dds.read(bigf.ArtFile(template).image())
    found = [(max(p[:3]) - min(p[:3])) / max(p[:3]) for row in pixels[::4] for p in row[::4] if p[3] > 128 and max(p[:3])]
    return sum(found) / len(found) if found else 0.0


def make_logo(url, colours, templates, pack=None, cache=None):
    """{(folder, prefix): art file bytes} for one logo link (from the cache, the pack, or downloaded
    and then kept in the cache). The pictures with a white edge (EDGED_KINDS) are drawn from the plain
    version of an ESPN logo; so are the others when the dark version is a white silhouette and the
    game's own calendar or wide picture is coloured (Toronto's calendar logo)."""
    from . import images
    cache = cache if cache and _cacheable(url) else None
    images_by_link = {}

    def image(link):
        if link not in images_by_link:
            if link.startswith('badge:'):              # a draft-class pool: a badge with its year
                img = images.badge(link[len('badge:'):], colours)
            else:
                img = (cache.logo(link) if cache else None) or (pack.logo(link) if pack else None)
                if img is None:
                    img = _download(link).convert('RGBA')
                    if cache:
                        cache.put_logo(link, images._trim(img))
            images_by_link[link] = img
        return images_by_link[link]
    out = {}
    silhouette = None
    for (folder, prefix), template in templates.items():
        link = plain_logo_url(url) if prefix in EDGED_KINDS else url
        if link == url and prefix in LOGO_ONLY_KINDS and plain_logo_url(url) != url:
            if silhouette is None:
                silhouette = images.white_share(image(url)) > SILHOUETTE
            if silhouette and _saturation(template) > COLOURED:
                link = plain_logo_url(url)
        img = image(link)
        out[(folder, prefix)] = art_file(template, images.logo(img, prefix, _template_size(template), colours))
    return out


# --- writing ------------------------------------------------------------------------------------
class _Writer:
    """Writes files into one or more game folders (the versions of the game being updated) and
    keeps the manifest of everything written."""

    def __init__(self, game_dirs, store=ART_STORE):
        self.store = store
        self.manifest = load_manifest(store)
        self.game_dirs = list(game_dirs)
        for d in self.game_dirs:
            self.manifest['games'].setdefault(d, {})
        _, self.backups = _paths(store)
        os.makedirs(self.backups, exist_ok=True)

    def current(self, rel, url):
        """Is this file installed already from this link, in every game folder (and still ours)?"""
        key = '/'.join(rel)
        for d in self.game_dirs:
            entry = self.manifest['games'][d].get(key)
            path = os.path.join(d, *rel)
            if not (entry and entry.get('source') == url and os.path.exists(path) and ours(entry, path)):
                return False
        return True

    def _keep(self, game_dir, key, path, newer=False):
        """Copy the file at `path` (not ours) aside so "Restore" can put it back. A copy already kept
        is never overwritten by one of our own files (after a lost manifest the file there is ours);
        only `newer`, a file someone put there after ours, replaces it."""
        name = hashlib.sha1(f"{game_dir}|{key}".encode()).hexdigest()[:16] + '_' + os.path.basename(path)
        target = os.path.join(self.backups, name)
        if newer or not os.path.exists(target):
            shutil.copy2(path, target)
        return target

    def write(self, rel, data, url):
        key = '/'.join(rel)
        for d in self.game_dirs:
            files = self.manifest['games'][d]
            path = os.path.join(d, *rel)
            entry = files.get(key)
            exists = os.path.exists(path)
            if entry and entry.get('source') == url and exists and ours(entry, path):
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if entry is None:
                entry = files[key] = {'backup': None}
                if exists:                            # a file we did not write: keep the original
                    entry['backup'] = self._keep(d, key, path)
            elif exists and not ours(entry, path):    # put there after ours (another pack): keep that one
                entry['backup'] = self._keep(d, key, path, newer=True)
            entry['source'] = url
            tmp = path + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(data)
            os.replace(tmp, path)
            entry['stamp'] = stamp(path)

    def stale(self, prefix, wanted):
        """File keys written by a source that starts with `prefix` (in any game folder) that are not in `wanted`."""
        return sorted({key for d in self.game_dirs for key, entry in self.manifest['games'][d].items()
                       if str(entry.get('source', '')).startswith(prefix) and key not in wanted})

    def drop(self, rel):
        """Put one file we wrote back as it was (the kept copy returns, or our file goes) and forget it."""
        key = '/'.join(rel)
        for d in self.game_dirs:
            entry = self.manifest['games'][d].pop(key, None)
            if entry is None:
                continue
            path = os.path.join(d, *rel)
            if entry.get('backup') and os.path.exists(entry['backup']):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                shutil.copy2(entry['backup'], path)
                os.remove(entry['backup'])
            elif os.path.exists(path) and ours(entry, path):
                os.remove(path)

    def save(self):
        _save_manifest(self.manifest, self.store)


def stamp(path):
    st = os.stat(path)
    return [st.st_size, st.st_mtime_ns]


def ours(entry, path):
    """Is the file at `path` still the one this program wrote (manifests before 0.6: assumed)?"""
    if not entry.get('stamp'):
        return True
    try:
        return stamp(path) == list(entry['stamp'])
    except OSError:
        return False


def check(rpcs3, title_id, own=False):
    """Raise ArtError, with what to do, when the pictures cannot be installed now. `own`: only the player's own
    pictures (the Roster editor's), which go in with photos and logos off too."""
    if savedata.running_rpcs3():
        first = savedata.close_first()
        raise ArtError(f"{first}: your own pictures go into the game while it is closed." if own else
                       f"{first}: pictures and team names can only be installed while the game is closed. "
                       "Or switch them off.")
    if not rpcs3.game_disc(title_id):
        raise ArtError("NHL Legacy Native's game folder is missing, so names and pictures cannot be made. Press Install in its "
                       "launcher, then try again." if rpcs3.native else
                       "RPCS3 does not say where your copy of the game is, so names and pictures cannot be made. "
                       "Start the game once from RPCS3's game list, then try again.")
    if any(not rpcs3.holds(d) and os.path.isdir(d) for d in load_manifest()['games']):
        raise ArtError("Photos and logos are installed for another copy of RPCS3. Press \"Restore the game's "
                       "own pictures\" first.")


def _game_dirs(rpcs3, manifest):
    """Every game folder pictures may be in: the ones the manifest names and this RPCS3's (both versions)."""
    dirs = {}
    for d in list(manifest['games']) + [rpcs3.game_folder(t) for t in savedata.GAMES]:
        dirs.setdefault(os.path.normcase(os.path.abspath(d)), d)
    return list(dirs.values())


def scan_claims(rpcs3):
    """Who uses which portrait number on this PC (portraits.Claims): the people every roster save of every RPCS3 user
    shows (the game folder is shared by them all), and the portrait files in the game folders, ours or another
    pack's. Only reads."""
    from ..roster import Roster
    from .portraits import NEW_IDS, Claims, birth_of, loose_key, person_key
    rosters = {}
    home = os.path.join(rpcs3.dev_hdd0, 'home')
    folders = {os.path.normcase(os.path.abspath(rpcs3.savedata)): rpcs3.savedata}
    for user in sorted(os.listdir(home)) if os.path.isdir(home) else []:
        folder = os.path.join(home, user, 'savedata')
        folders.setdefault(os.path.normcase(os.path.abspath(folder)), folder)
    for folder in getattr(rpcs3, 'extra_savedata', ()):         # an export reads the player's own saves too (export.py)
        folders.setdefault(os.path.normcase(os.path.abspath(folder)), folder)
    for folder in folders.values():
        for slot in savedata.list_rosters(folder):
            try:
                P = Roster(savedata.read_roster(slot)).P
            except Exception:          # a damaged or foreign save: nobody's pictures to protect
                continue
            for r in range(P.cur_rec):
                if P.get(r, 'hasportrait'):
                    who = loose_key(person_key(P.get(r, 'PedH'), P.get(r, 'RMbQ'), birth_of(P, r)))
                    rosters.setdefault(P.get(r, 'artid'), set()).add(who)
    m = load_manifest()
    theirs, mine, urls = set(), set(), {}
    for d in _game_dirs(rpcs3, m):
        files = m['games'].get(d, {})
        for kind in PORTRAIT_KINDS:
            base = os.path.join(d, *ART, kind)
            for sub in sorted(os.listdir(base)) if os.path.isdir(base) else []:
                folder = os.path.join(base, sub)
                for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                    if not (name.startswith('p') and name.endswith('.big') and name[1:-4].isdigit()):
                        continue
                    aid, entry = int(name[1:-4]), files.get('/'.join(ART + (kind, sub, name)))
                    if entry and ours(entry, os.path.join(folder, name)):
                        mine.add(aid)
                        if entry.get('backup') and aid in NEW_IDS:     # we covered another pack's file
                            theirs.add(aid)
                        source = str(entry.get('source', ''))
                        if source.endswith(PORTRAIT_DRAWING) and kind == PORTRAIT_KINDS[0]:
                            urls[aid] = source[:-len(PORTRAIT_DRAWING)]
                    elif aid in NEW_IDS:
                        theirs.add(aid)
    return Claims(rosters, theirs, mine, urls)


def give_back(numbers, say=print):
    """Take our portraits off these numbers (portraits.forget_conflicts: someone else's) in every game folder: the
    file another pack had there comes back from its kept copy, else ours is deleted. Returns how many numbers."""
    if not numbers:
        return 0
    m = load_manifest()
    writer = _Writer(list(m['games']))
    for aid in sorted(numbers):
        for kind in PORTRAIT_KINDS:
            writer.drop(ART + (kind, portrait_folder(aid), f"p{aid}.big"))
    writer.save()
    say(f"Photos and logos: {len(numbers)} picture numbers given back to the rosters that had them first")
    return len(numbers)


def update_texts(game_dirs):
    """{language: text file} of the game's update 1.01 when one of `game_dirs` (USRDIR folders) has it: its patch.big
    holds the text files the game then reads instead of the disc's, with 13 more texts (the 3-on-3 overtime, gear and
    jersey names) and newer ones. {} without the update."""
    from . import loc
    from .disc import EbArchive
    for d in list(game_dirs) + list(_READ_ONLY_DIRS) + list(_HOST_READS):
        path = os.path.join(d, UPDATE_ARCHIVE)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, 'rb') as f:
                arc = EbArchive(f)
                names = {lang: f"fe/loc/nhl_{lang}.db" for lang in loc.LANGUAGES}
                return {lang: arc.read(name) for lang, name in names.items() if name in arc.entries}
        except (OSError, ValueError, NotImplementedError):
            continue
    return {}


def install_names(disc, writer, names, say):
    """The game's text files with the roster's team names and the Puck Peak texts (loc.py), one per
    language, made from the game's own each time (so nothing piles up): the update's when a game folder has update
    1.01 (a superset of the disc's), else the disc's. Returns how many files were written."""
    import hashlib as _h
    from . import loc
    newer = update_texts(writer.game_dirs)
    source = 'names:' + _h.sha1((loc.NAMES_VERSION + json.dumps(names, sort_keys=True, default=sorted)
                                 + loc.PROMO_VERSION + json.dumps(loc.PROMO, sort_keys=True)).encode()).hexdigest()
    if newer:
        source += ':' + _h.sha1(b''.join(newer[lang] for lang in sorted(newer))).hexdigest()[:12]
    rels = {lang: ('fe', 'loc', f"nhl_{lang}.db") for lang in loc.LANGUAGES}
    todo = [lang for lang in loc.LANGUAGES if not writer.current(rels[lang], source)]
    if not todo:
        return 0
    files = {}
    for lang in loc.LANGUAGES:        # all of them: a promo text's room is the longest any language keeps
        original = newer.get(lang) or disc.text_file(lang)
        if original is not None:
            files[lang] = loc.LocFile(original)
    room = loc.promo_limits(files.values())
    written = 0
    for lang in todo:
        text = files.get(lang)
        if text is None:
            continue
        limits = text.limits()
        if loc.apply_names(text, names) + loc.apply_promo(text):
            over = text.over_limit(limits) + loc.promo_over(text, room)
            if over:               # never install a text the game's buffers cannot hold
                say(f"Photos and logos: team names and Puck Peak texts NOT written in {lang}: {over[0][0]} is "
                    f"{over[0][1]} bytes (the game allows {over[0][2]})")
                continue
            writer.write(rels[lang], text.build(), source)
            written += 1
    if written:
        say(f"Photos and logos: team names and Puck Peak texts written in {written} languages")
    return written


def install_menus(disc, writer, say, mode=None):
    """The main menu without the entries that died with the game's servers (menus.py: HUT, View Player Hub, Leaderboards,
    Lobby), made from the disc's own menu file. Returns how many files were written."""
    from . import menus
    mode = mode or menus.HIDE
    source = 'menus:' + menus.MENUS_VERSION + str(mode)
    if writer.current(menus.REL, source):
        return 0
    if _Writer(writer.game_dirs, store=PATCH_STORE).current(menus.REL, source):     # the online setup put the same file in
        return 0
    try:
        files = menus.menu_files(disc, mode)
    except (ValueError, KeyError, OSError) as err:     # a menu file that does not look like the game's own: left alone
        say(f"Photos and logos: the main menu was left as it is ({err})")
        return 0
    for rel, data in sorted(files.items()):
        writer.write(rel, data, source)
    say("Photos and logos: the main menu leaves out the online entries that no longer work")
    return len(files)


def install(rpcs3, title_id, portraits, logos, say=print, workers=WORKERS, pack=None, names=None, also=(),
            cache=None, skipped=None, menus=True, pictures=True):
    """Make and install the pictures. `portraits` {artid: photo link}, `logos` {team artid:
    (logo link, colours)} (from portraits.plan()). Pictures come from the program's photo pack
    (`pack`; default: the bundled one, if this edition has it; False: none) or are downloaded.
    `names` (portraits.names()) go into the game's text files. Templates come from the disc of
    `title_id`; `also` are further versions of the game (title ids) that get every file as well.
    `skipped` (a list) gets (what, link, why) of every picture that could not be made. `menus`: the main menu
    without its dead entries goes in too (not with the player's own pictures alone). `pictures` False: only the
    names and the menu (the "Team names" switch alone); the photos and logos are left as they are.
    Returns (written, already there, failed)."""
    check(rpcs3, title_id, own=not (menus or names))
    if not _REDIRECT and not _HOST and os.path.exists(lab.manifest_path()):     # an export never touches the player's RPCS3
        lab.remove(say=lambda msg: None)  # the one-off art test, if it is still installed
    say("Photos and logos: reading picture templates from your game")
    disc = Disc(rpcs3.game_disc(title_id))
    p_templates = {k: disc.portrait(k, PORTRAIT_TEMPLATE) for k in PORTRAIT_KINDS} if pictures else {}
    targets = [title_id] + [t for t in also if t != title_id]
    writer = _Writer([rpcs3.game_folder(t) for t in targets])
    pack = PhotoPack.open() if pack is None else pack or None
    cache = PictureCache() if cache is None else cache or None
    try:
        if names:
            install_names(disc, writer, names, say)
        if menus:
            install_menus(disc, writer, say)
    finally:
        writer.save()
    if not pictures:
        return 0, 0, 0

    jobs = []           # (description, function, [(relative path, key in the result)], link, source in the manifest)
    bundled = kept = 0
    for aid, url in sorted(portraits.items()):
        rels = [(ART + (k, portrait_folder(aid), f"p{aid}.big"), k) for k in PORTRAIT_KINDS]
        source = url + PORTRAIT_DRAWING
        if not all(writer.current(rel, source) for rel, _k in rels):
            jobs.append(('photo', lambda u=url: make_portrait(u, p_templates, pack, cache), rels, url, source))
            if cache and _cacheable(url) and (cache.portrait(url, (256, 128)) is not None or cache.headless(url)):
                kept += 1
            else:
                bundled += bool(pack and key_for(url) in pack.portraits)
    for aid, (url, colours) in sorted(logos.items()):
        templates = {(f, p): disc.logo(f, p, aid) or disc.logo(f, p, 0) for f, p in logo_kinds(aid)}
        templates = {k: v for k, v in templates.items() if v}
        rels = [(ART + (f, f"{p}{aid}.big"), (f, p)) for f, p in templates]
        source = url + LOGO_DRAWING     # a logo drawn another way is drawn again
        if not all(writer.current(rel, source) for rel, _k in rels):
            jobs.append(('logo', lambda u=url, c=colours, t=templates: make_logo(u, c, t, pack, cache), rels, url,
                         source))
            if cache and _cacheable(url) and cache._name(url, 'l'):
                kept += 1
            else:
                bundled += bool(pack and key_for(url) in pack.logos) or url.startswith(('badge:', 'file:'))
    already = len(portraits) + len(logos) - len(jobs)
    if not jobs:
        say(f"Photos and logos: all {already} pictures are installed already")
        return 0, already, 0

    written = failed = 0
    fetch = len(jobs) - bundled - kept
    source = ", ".join(part for part in (f"{bundled} from this program" if pack else "",
                                         f"{kept} kept on this PC" if kept else "",
                                         f"{fetch} to download" if fetch else "") if part) or "none to download"
    say(f"Photos and logos: making {len(jobs)} pictures ({already} are installed already; {source})")
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fn): (what, rels, url, source) for what, fn, rels, url, source in jobs}
            for k, fut in enumerate(concurrent.futures.as_completed(futures), 1):
                what, rels, url, source = futures[fut]
                try:
                    made = fut.result()
                    why = "no head found in it" if made is None else ""
                except Exception as err:       # a photo that will not download or decode: skip it
                    made, why = None, str(err) or type(err).__name__
                if made is None:
                    failed += 1
                    say(f"Skipped the {what} {url}: {why}")
                    if skipped is not None:
                        skipped.append((what, url, why))
                else:
                    for rel, key in rels:
                        writer.write(rel, made[key], source)
                    written += 1
                if k % 25 == 0 or k == len(jobs):
                    say(f"Photos and logos: {k} of {len(jobs)} pictures made")
                    writer.save()
    finally:
        writer.save()
    say(f"Photos and logos: {written} pictures installed" + (f", {failed} could not be downloaded" if failed else ""))
    return written, already, failed


def remove(say=print):
    """Put every file the photos and logos replaced back and delete the ones they added.
    Returns how many files were handled. The game patch's files are not pictures: they stay (patchinstall.remove)."""
    move_entries('db/', ART_STORE, PATCH_STORE)
    m = load_manifest()
    lab_count = lab.remove(say=lambda msg: None) if not _HOST and os.path.exists(lab.manifest_path()) else 0
    if not any(m['games'].values()):
        say("No photos or logos are installed." if not lab_count else "The art test was removed.")
        path, _ = _paths()
        if os.path.exists(path):
            os.remove(path)
        return lab_count
    if savedata.running_rpcs3():
        raise ArtError(f"{savedata.close_first()}: pictures can only be removed while the game is closed.")
    n, left = _put_back(m)
    _forget_handled(m, ART_STORE)
    say(f"The game's own pictures are back: {n} files put back as they were." + _left_line(left))
    return n


def remove_parts(parts, say=print):
    """Put back only the files of `parts` (art/parts.py): their kept copies return, the files they added go, every other
    part stays installed. Returns how many files were handled. RPCS3 must be closed."""
    from . import parts as P
    m = load_manifest()
    chosen = {d: {k: e for k, e in files.items() if any(P.belongs(e.get('source'), p) for p in parts)}
              for d, files in m['games'].items()}
    chosen = {d: files for d, files in chosen.items() if files}
    if not chosen:
        say("None of these pictures is installed.")
        return 0
    if savedata.running_rpcs3():
        raise ArtError(f"{savedata.close_first()}: pictures can only be removed while the game is closed.")
    sub = dict(m)
    sub['games'] = {d: dict(files) for d, files in chosen.items()}
    n, left = _put_back(sub)
    for d, files in chosen.items():
        if d not in left:
            for key in files:
                m['games'][d].pop(key, None)
    m['games'] = {d: files for d, files in m['games'].items() if files}
    _forget_handled(m, ART_STORE)
    say(f"The game's own pictures are back for these parts: {n} files put back as they were." + _left_line(left))
    return n


def remove_retired(say=print):
    """Put back the files of parts the program no longer has (art/parts.py RETIRED_TAGS: the new scoreboard of the test
    versions 0.78.0 / 0.80.0), in every game folder the list knows. Says nothing when there are none; leaves them while
    RPCS3 runs (the callers have checked). Returns how many files were handled."""
    from . import parts as P
    m = load_manifest()
    chosen = {d: {k: e for k, e in files.items() if str(e.get('source') or '').startswith(P.RETIRED_TAGS)}
              for d, files in m['games'].items()}
    chosen = {d: files for d, files in chosen.items() if files}
    if not chosen or savedata.running_rpcs3():
        return 0
    sub = dict(m)
    sub['games'] = {d: dict(files) for d, files in chosen.items()}
    n, left = _put_back(sub)
    for d, files in chosen.items():
        if d not in left:
            for key in files:
                m['games'][d].pop(key, None)
    m['games'] = {d: files for d, files in m['games'].items() if files}
    _forget_handled(m, ART_STORE)
    say(f"The test scoreboard was taken out: {n} of the game's own files put back." + _left_line(left))
    return n


def remove_store(store):
    """Put every file of `store` back as it was (kept copies return, our files go) and forget the store's list. RPCS3
    must be closed (the caller checks). Returns how many files were handled."""
    m = load_manifest(store)
    n, _ = _put_back(m)
    _forget_handled(m, store)
    return n


def move_entries(prefix, source, target):
    """Hand the files whose key starts with `prefix` from one store's list to another's, kept copies included (the game
    patch's db files, which `cli team32-test` wrote with the pictures before 0.18). Returns how many moved."""
    src, dst = load_manifest(source), load_manifest(target)
    _, backups = _paths(target)
    moved = 0
    for game_dir, files in src['games'].items():
        for key in [k for k in files if k.startswith(prefix)]:
            entry = files.pop(key)
            if entry.get('backup') and os.path.exists(entry['backup']):
                os.makedirs(backups, exist_ok=True)
                kept = os.path.join(backups, os.path.basename(entry['backup']))
                shutil.move(entry['backup'], kept)
                entry['backup'] = kept
            dst['games'].setdefault(game_dir, {})[key] = entry
            moved += 1
    if moved:
        _save_manifest(dst, target)
        _save_manifest(src, source)
    return moved


def _put_back(m):
    """Put every file of the list `m` back (see remove) and take away the folders we made and left empty. A game
    folder that is not there any more (RPCS3 moved, a drive unplugged) is left in `m` with its kept copies, so they come
    back once it is there again. Returns (files handled, {game folder left: files})."""
    n, left = 0, {}
    for game_dir, files in sorted(m['games'].items()):
        if not os.path.isdir(game_dir):
            if files:
                left[game_dir] = len(files)
            continue
        for key, entry in sorted(files.items()):
            path = os.path.join(game_dir, *key.split('/'))
            if entry.get('backup') and os.path.exists(entry['backup']):
                os.makedirs(os.path.dirname(path), exist_ok=True)     # a folder taken away since (game reinstalled)
                shutil.copy2(entry['backup'], path)
                os.remove(entry['backup'])
            elif os.path.exists(path) and ours(entry, path):
                os.remove(path)             # a file someone put there after ours (no copy kept) stays
            n += 1
        for key in files:                    # folders we created and left empty
            folder = os.path.dirname(os.path.join(game_dir, *key.split('/')))
            while folder.startswith(game_dir) and len(folder) > len(game_dir):
                try:
                    os.rmdir(folder)
                except OSError:
                    break
                folder = os.path.dirname(folder)
    m['games'] = {d: files for d, files in m['games'].items() if d in left}
    return n, left


def _forget_handled(m, store):
    """Keep the list of what _put_back left (game folders not there now), or delete it when nothing is left."""
    path, _ = _paths(store)
    if m['games']:
        _save_manifest(m, store)
    elif os.path.exists(path):
        os.remove(path)


def _left_line(left):
    return "".join(f" {count} pictures are for a game folder that is not there any more ({d}): they stay listed and "
                   f"come back with Restore once that folder is there again." for d, count in sorted(left.items()))
