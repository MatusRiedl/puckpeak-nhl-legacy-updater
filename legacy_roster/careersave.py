"""Running Be a Pro careers: read the save, change the pro, give the save's bytes back.

The game keeps a Be a Pro career in a folder `<TITLE>05NN` as files DATA0000, DATA0001, ... (1 MiB each, the last one
shorter) that together are one file (docs/notes/be-a-pro-save.md):

    0x00  "PS3BeAProFile"
    0x10  zlib.crc32 of [0x1C : L], L = the end of the last chunk (Be a GM autosaves carry old bytes after it)
    0x24  the section size, 0x28 its CRC-32/BZIP2, 0x2C the zlib length (little-endian), 0x30 the league's database
    then  ten chunks, each a 16-byte head (type, 1, length, CRC-32/BZIP2 of the body) and the body

The pro is kept twice: chunk 8 holds his values as the career began (names, birth year, bio index, ratings - 36, type,
...), his rows in the database the ones the game shows and plays (`leagueplayerbiotable`, `leagueskaterai`: Player
Growth, Pro Central and the Overall, worked out again on load, come from `leagueskaterai`'s `c_` ratings; lab round 47).
Spending XP in Player Growth changes only those `c_` ratings and chunk 24's spent words, never chunk 8. Chunk 24 keeps the
XP earned and spent per pool; the XP to spend is earned minus spent.

This module reads a career into memory and builds the bytes again; a career nobody changed comes back byte for byte
(tests/test_careersave.py, every copy of LEGACY_ROSTER_CAREERS). Writing the files is `savedata.update_career`'s job
(backup first, never while RPCS3 runs); `verify.career_problems` checks a change first (AGENTS.md rules 1 and 3).
Standard library only.
"""
import datetime
import os
import re
import struct
import time
import zlib

from .sfo import Sfo
from .tdb import RosterFile, crc32_bzip2

MAGIC = b'PS3BeAProFile'
FOLDER = re.compile(r'^([A-Z]{4}\d{5})05(\d{2})$')
DATA = re.compile(r'^DATA\d{4}$')
PIECE = 1 << 20
VERSIONS = (1, 2)               # a chunk's second word; update 1.01 writes chunk 2 as 2 and the header's word at 0x20 too
SETTLE = 5                     # seconds a save must be left alone before it is read (as seasonsave.SETTLE)
RATING_BASE = 36                # chunk 8 and the tables keep a rating as value - 36

PRO_CHUNK, XP_CHUNK = 8, 24
BIO, SKATER, GOALIE = 'MMxP', 'wiLv', 'kPCA'        # leagueplayerbiotable, leagueskaterai, leaguegoalieai
INDEX = 'qEfv'                                      # a row's bio index (the pro's is chunk 8's word at 0x5C)
FIRST, LAST = 'PedH', 'RMbQ'                        # leagueplayerbiotable firstname / lastname (200 bits)

# chunk 8: offset of each field
NAME_SIZE = 0x19
AT = {'first': 0x00, 'last': 0x19, 'birthplace': 0x32, 'year': 0x5A, 'bio': 0x5C, 'game_id': 0x5E,
      'overall': 0x82, 'ratings': 0x83, 'type': 0xA2, 'overall7': 0x12C, 'overall10': 0x134, 'jersey': 0x1A2}

# the 25 skater ratings, in chunk 8's order (alphabetical by the game's field names), with their tags in leagueskaterai:
# c_ the rating, e_ / s_ (the same at a career's start), m_ (a modifier, -16..15)
RATINGS = ('acceleration', 'aggression', 'agility', 'balance', 'bodychecking', 'defawareness', 'deking', 'discipline',
           'durability', 'endurance', 'faceoffs', 'fightingskill', 'handeye', 'offawareness', 'passing', 'poise',
           'puckcontrol', 'shotblocking', 'slapaccuracy', 'slapshotpower', 'speed', 'stickchecking', 'strength',
           'wristaccuracy', 'wristshotpower')
_TAGS = {
    'c': 'ckxF oskO pyYq YqOX oisw OTvp iCvN ShqX seUB kIjD KrwV gUBy ujcW VlLd oRUd fRaZ YqXz zRrS KQBB DCvJ bEdA TUty '
         'POYr ObeE Hvje',
    'e': 'mnjx gpBx TPOp CXow KpCE kAlN RvMf mkTo cjNe XaGf VjiI KErg ciSp vmdZ SAae ZcuO FZev tidW ovPB hCFn lRFf pEHg '
         'Iqae kfUW PGuJ',
    's': 'gcbr IVca YMIa pgeT UaKy mLdD JTIJ agij EfcN DQVR WOCi XHHO Xxsa ldlD hDkx hNAS Gscb nths WULb EZFZ FAzb UHLO '
         'rrSI ZAoo JpUs',
    'm': 'AROy Onpr bNGW ehgr MbnT qmQu AoNg IeHi ShRc mvxh lvpX hcWL EcqO xcMS uGiB SKlV guhB XQId mliu KuUY KXGw Kcaf '
         'wehx PTFd IJNK',
}
TAGS = {kind: dict(zip(RATINGS, tags.split())) for kind, tags in _TAGS.items()}
# the Player Growth screen's three pools: chunk 24's words 0-2 the XP earned, 3-5 the XP spent (6-8 the last game's)
POOLS = ('offense', 'defense', 'athletic')
MAX_XP = 99999                  # a sane top for the XP to spend (the copies hold 600-750 at a career's start)
LOWEST, HIGHEST = 40, 99        # a rating typed in the window (as editor/card.py; 6 bits hold 36-99)

# what each kind of edit may change (verify.career_problems): byte ranges of chunk 8 ('pro') and chunk 24 ('xp'), and
# {table: fields} of the pro's own rows
EDITABLE = {
    'name': {'pro': [(AT['first'], AT['birthplace'])], 'xp': [], 'rows': {BIO: (FIRST, LAST)}},
    'xp': {'pro': [], 'xp': [(0, 4 * len(POOLS))], 'rows': {}},
    'ratings': {'pro': [], 'xp': [], 'rows': {SKATER: tuple(TAGS['c'].values())}},
}


class CareerError(ValueError):
    """The save cannot be read or written (the message says why, in words for players)."""


class Chunk:
    def __init__(self, kind, flag, body):
        self.kind, self.flag, self.body = kind, flag, bytearray(body)


class Career:
    """One Be a Pro career in memory: the database (a RosterFile), the chunks, and what lies after them."""

    def __init__(self, raw):
        raw = bytes(raw)
        if len(raw) < 0x30 or raw[:16].rstrip(b'\0') != MAGIC:
            raise CareerError("This is not a Be a Pro save.")
        self.raw = raw
        size = struct.unpack_from('>I', raw, 0x24)[0]
        try:
            self.db = RosterFile(data=raw)
        except (ValueError, zlib.error, struct.error) as e:
            raise CareerError("This save is damaged or not complete.") from e
        self.chunks, pos = [], 0x2C + size
        while pos + 16 <= len(raw):
            kind, flag, n, crc = struct.unpack_from('>IIII', raw, pos)
            if flag not in VERSIONS or pos + 16 + n > len(raw):
                break
            body = raw[pos + 16:pos + 16 + n]
            if crc32_bzip2(body) != crc:
                raise CareerError("This save is damaged or not complete.")
            self.chunks.append(Chunk(kind, flag, body))
            pos += 16 + n
        self.end, self.tail = pos, raw[pos:]
        if struct.unpack_from('>I', raw, 0x10)[0] != zlib.crc32(raw[0x1C:pos]):
            raise CareerError("This save is damaged or not complete.")
        kinds = [c.kind for c in self.chunks]
        if PRO_CHUNK not in kinds or XP_CHUNK not in kinds:
            raise CareerError("This Be a Pro save could not be read.")
        self.pieces = None              # the sizes of the DATA files it was read from (read() sets them)

    def chunk(self, kind):
        return next(c for c in self.chunks if c.kind == kind).body

    # --- the pro ------------------------------------------------------------------------------------------------
    @property
    def pro(self):
        return Pro(self)

    def bio_row(self):
        return self._row(BIO)

    def skater_row(self):
        return self._row(SKATER)

    def _row(self, tag):
        t = self.db.tables.get(tag)
        if t is None:
            return None
        bio = struct.unpack_from('>H', self.chunk(PRO_CHUNK), AT['bio'])[0]
        return next((i for i in range(t.cur_rec) if t.get(i, INDEX) == bio), None)

    # --- changes ------------------------------------------------------------------------------------------------
    def set_xp(self, pools):
        """XP to spend, {'offense': n, 'defense': n, 'athletic': n} (pools not named keep theirs): the XP earned
        becomes the XP spent + n, as the game counts it (lab round 47: +500 earned showed +500 to spend)."""
        body = self.chunk(XP_CHUNK)
        for i, pool in enumerate(POOLS):
            if pool in pools:
                value = int(pools[pool])
                if not 0 <= value <= MAX_XP:
                    raise CareerError(f"XP must be 0 to {MAX_XP}.")
                spent = struct.unpack_from('>I', body, 4 * (i + len(POOLS)))[0]
                struct.pack_into('>I', body, 4 * i, spent + value)

    def set_ratings(self, values):
        """The skater's ratings {name: value} in his `leagueskaterai` row (`c_`), where the game reads them; chunk 8
        keeps the career's first values, as it does when XP is spent."""
        row = self.skater_row()
        if row is None:
            raise CareerError("Ratings of a goalie career cannot be changed yet.")
        t = self.db.tables[SKATER]
        for name, value in values.items():
            value = int(value)
            if name not in TAGS['c'] or not LOWEST <= value <= HIGHEST:
                raise CareerError(f"Ratings go from {LOWEST} to {HIGHEST}.")
            t.set(row, TAGS['c'][name], value - RATING_BASE)

    def set_name(self, first=None, last=None):
        """The pro's first / last name, in chunk 8 and in his bio row."""
        body, row = self.chunk(PRO_CHUNK), self.bio_row()
        for key, tag, value in (('first', FIRST, first), ('last', LAST, last)):
            if value is None:
                continue
            try:
                data = value.encode('latin1')
            except UnicodeEncodeError:
                raise CareerError("A name can use only letters the game has (no č, ť, ž ...).") from None
            if not data or len(data) >= NAME_SIZE:
                raise CareerError(f"A name must be 1 to {NAME_SIZE - 1} letters.")
            body[AT[key]:AT[key] + NAME_SIZE] = data.ljust(NAME_SIZE, b'\0')
            if row is not None:
                self.db.tables[BIO].set(row, tag, value)

    # --- bytes --------------------------------------------------------------------------------------------------
    def build(self):
        """The career's bytes: the database built again (its section CRC), every chunk's CRC, then 0x10 up to the end
        of the last chunk. Nothing changed: the bytes it was read from."""
        out = bytearray(self.db.build())
        pos = 0x2C + struct.unpack_from('>I', out, 0x24)[0]
        for c in self.chunks:
            struct.pack_into('>IIII', out, pos, c.kind, c.flag, len(c.body), crc32_bzip2(c.body))
            out[pos + 16:pos + 16 + len(c.body)] = c.body
            pos += 16 + len(c.body)
        if pos != self.end or len(out) != len(self.raw):
            raise CareerError("The changed career no longer fits its save.")
        struct.pack_into('>I', out, 0x10, zlib.crc32(out[0x1C:pos]))
        return bytes(out)


class Pro:
    """The pro: names, bio and type from chunk 8, ratings from his `leagueskaterai` row (empty for a goalie), XP from
    chunk 24. `overall` is chunk 8's, as the career began (the game works it out again on load)."""

    def __init__(self, career):
        c8 = career.chunk(PRO_CHUNK)
        text = lambda at, n: bytes(c8[at:at + n]).split(b'\0')[0].decode('latin1')
        self.first, self.last = text(AT['first'], NAME_SIZE), text(AT['last'], NAME_SIZE)
        self.birthplace = text(AT['birthplace'], AT['year'] - AT['birthplace'])
        self.year, self.bio, game_id = struct.unpack_from('>HHH', c8, AT['year'])
        self.game_id = None if game_id == 0xFFFF else game_id
        self.overall = c8[AT['overall']] + RATING_BASE
        self.type = c8[AT['type']]
        self.jersey = c8[AT['jersey']]
        words = struct.unpack_from(f'>{2 * len(POOLS)}I', career.chunk(XP_CHUNK), 0)
        self.earned, self.spent = dict(zip(POOLS, words)), dict(zip(POOLS, words[len(POOLS):]))
        self.xp = {p: max(0, self.earned[p] - self.spent[p]) for p in POOLS}          # to spend
        row = career.skater_row()
        self.goalie = row is None
        t = career.db.tables.get(SKATER)
        self.ratings = {} if row is None else {name: t.get(row, tag) + RATING_BASE for name, tag in TAGS['c'].items()}

    @property
    def name(self):
        return f"{self.first} {self.last}".strip()


# --- the files -------------------------------------------------------------------------------------------------
class Save:
    """A Be a Pro career folder (only its name, times and PARAM.SFO are read)."""

    def __init__(self, path):
        self.path = path
        self.folder = os.path.basename(path)
        m = FOLDER.match(self.folder)
        self.title_id = m.group(1)
        self.files = data_files(path)
        self.modified = max(os.path.getmtime(p) for p in self.files)
        try:
            self.name = Sfo.load(os.path.join(path, 'PARAM.SFO')).get('SUB_TITLE', '') or self.folder
        except (OSError, ValueError):
            self.name = self.folder

    def settled(self, now=None):
        return (now if now is not None else time.time()) - self.modified >= SETTLE

    def label(self):
        return f"Be a Pro: {self.name}   (saved {datetime.datetime.fromtimestamp(self.modified):%Y-%m-%d %H:%M})"


def sub_title(folder, last):
    """The load list's label the game gives a career saved in `folder`: the last name in capitals and the folder's number
    + 1 ("DI NICOLA1" in 0500, "O'BRIEN3" in 0502)."""
    return f"{last.upper()}{int(FOLDER.match(folder).group(2)) + 1}"


def renamed_label(save, old_last, new_last):
    """The label `save` (a Save) should get when the pro's last name changes, or None: only a label the game made
    from the old name follows it (a career's label is kept by the game when it saves over the folder; lab round 47)."""
    if new_last == old_last or save.name != sub_title(save.folder, old_last):
        return None
    return sub_title(save.folder, new_last)


def data_files(path):
    return [os.path.join(path, n) for n in sorted(os.listdir(path)) if DATA.match(n)]


def is_career(path):
    """True for a folder `<TITLE>05NN` whose DATA0000 starts with the Be a Pro name (reads 16 bytes)."""
    if not FOLDER.match(os.path.basename(path)) or not os.path.isdir(path):
        return False
    try:
        with open(os.path.join(path, 'DATA0000'), 'rb') as f:
            return f.read(16).rstrip(b'\0') == MAGIC
    except OSError:
        return False


def find(savedata, title_ids=None):
    """The Be a Pro careers in a savedata folder (of the games `title_ids`, default every one), newest first."""
    if not savedata or not os.path.isdir(savedata):
        return []
    saves = []
    for name in os.listdir(savedata):
        m = FOLDER.match(name)
        if not m or (title_ids and m.group(1) not in title_ids):
            continue
        path = os.path.join(savedata, name)
        if is_career(path):
            try:
                saves.append(Save(path))
            except (OSError, ValueError):
                pass
    return sorted(saves, key=lambda s: s.modified, reverse=True)


def read(save, now=None):
    """The Career of a `Save` (or a folder path). A save written in the last SETTLE seconds, or one that changes while
    it is read, is refused: the game may still be writing it."""
    if not isinstance(save, Save):
        if not is_career(save):
            raise CareerError("This is not a Be a Pro save.")
        save = Save(save)
    if not save.settled(now):
        raise CareerError("The game is still saving. Try again in a moment.")
    before = [os.path.getmtime(p) for p in save.files]
    parts = []
    for p in save.files:
        with open(p, 'rb') as f:
            parts.append(f.read())
    if [os.path.getmtime(p) for p in save.files] != before:
        raise CareerError("The game is still saving. Try again in a moment.")
    career = Career(b''.join(parts))
    career.pieces = [len(p) for p in parts]
    return career


def pieces(data, sizes=None):
    """The DATA files of a career's bytes: with `sizes` (the files it was read from) split the same way, refused when
    the bytes no longer fit them; without, 1 MiB pieces and a shorter last one, as the game writes them."""
    if sizes is None:
        return [data[i:i + PIECE] for i in range(0, len(data), PIECE)]
    if sum(sizes) != len(data) or not all(sizes):
        raise CareerError("The changed career no longer fits its save.")
    out, at = [], 0
    for n in sizes:
        out.append(data[at:at + n])
        at += n
    return out
