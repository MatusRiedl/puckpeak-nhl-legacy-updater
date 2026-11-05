"""Player records for people who are not in the save yet.

The player table cannot simply grow, so a new player takes over an existing record:
  1. a blanked "ZZ" record (the community roster's deleted players) -- the normal case;
  2. when those run out for a position: a teamless, low-rated record of a former player, the
     oldest first. Never taken: legends and well-rated players, anyone whose NHL rights a team
     holds, anyone younger than MIN_AGE, free agents, and anyone whose name appears in the data
     being applied (he may still be placed later in the same run).
The records the game's Create Player fills (faces.RESERVED) are never taken: they are the only ones
that can carry a created look (edits.py gives them to the player's own new players with a look).

Taking a record over also wipes what belonged to its previous owner: portrait, commentary
name, draft and career data.
"""
import bisect
import zlib
from collections import Counter

from . import layout as L
from . import faces
from .faces import RESERVED
from .matching import norm

LEGEND_LEVEL = 84      # teamless records at or above this level are kept (legends, recent stars)
MIN_AGE = 26           # teamless records of younger players are kept (prospects who may sign anywhere)
GAME_ART_MAX = 12401     # portrait ids up to here are the game's own (records from the game's 2015 database)
UNDRAFTED = 255
GENERIC_HEAD = 60000   # head ids from here on are the game's generic head models
CAREER_FIELDS = ('nhlgamesplayedcareer', 'progamesplayedcareer', 'nhlgamesplayedlastseason',
                 'nhlgamesplayedtwoseasonsago', 'nhlgamesplayedthreeseasonsago', 'nhlgamesmissedinjurylastseason')
NORTH_AMERICA = (L.NAT_CODE['CAN'], L.NAT_CODE['USA'])


def real_birth_year(P, i, stale=True):
    """The player's actual birth year, as well as the record tells it.

    This roster family stores birth years as year - 1910, but records nobody updated since the game's
    2015 database still hold year - 1900 and read ten years too young. The draft year (stored as
    year - 1900 in both) gives such records away. An undrafted record with the game's own portrait is
    one of them when its first signing (also year - 1900 in both; the game set it about 20 years after
    the birth) would come at 12 or younger: 830 such records in the 2025-26 roster sign at 10, the
    75 the community updated (Krug, Goodrow) at 18-23, and a few have no signing year (their own).
    A birth year that fits the draft year (drafted at 15-21) is the record's own: a junior's draft
    year is when he becomes eligible (draft.py), and his birth year must not move with it.
    `stale` False: the roster has no such records (the game's own roster, whose birth years
    stock.prepare moved all at once)."""
    shown = P.get(i, 'dnFq') + 1910
    drafted = P.get(i, 'WzKY')
    if drafted != UNDRAFTED:
        guess = drafted + 1900 - 18
        if -3 <= shown - guess <= 3:
            return shown
        if stale and -3 <= shown - 10 - guess <= 3:
            return shown - 10
        return guess if stale else shown
    if stale and 0 < P.get(i, 'rnOl') <= GAME_ART_MAX and shown >= 1990:
        signed = P.get(i, 'TNEo')
        if signed and signed + 1900 - shown <= 12:
            return shown - 10
    return shown


class Donors:
    def __init__(self, b):
        self.b = b
        R, P = b.R, b.P
        fa = {R.link_to_pid.get(l) for l in b.fa_links}
        self.blank = {pos: [] for pos in range(5)}   # ZZ records by position, in row order
        self.spare = {pos: [] for pos in range(5)}   # other teamless records, oldest first
        self.reserved = set()                        # normalised (first, last) of people in the data
        heads, home = Counter(), {}
        pool, eyes = {}, {}      # every generic head the roster's records wear, by skin group (and the eye colour they carry)
        for i in range(P.cur_rec):
            pid = P.get(i, 'zIBw')
            country = P.get(i, 'hleL')
            if P.get(i, 'DaPp') >= GENERIC_HEAD and P.get(i, 'QDTK') in faces.BUCKET_OF:
                group = faces.BUCKET_OF[P.get(i, 'QDTK')]
                pool.setdefault(group, Counter())[(P.get(i, 'DaPp'), P.get(i, 'QDTK'))] += 1
                eyes.setdefault(group, Counter())[P.get(i, 'jfuZ')] += 1
            if R.entries_by_pid.get(pid):
                home.setdefault(country, Counter())[P.get(i, 'IxvQ')] += 1
                if P.get(i, 'DaPp') >= GENERIC_HEAD and not P.get(i, 'LcvS'):
                    heads[(P.get(i, 'DaPp'), P.get(i, 'QDTK'))] += 1
                continue
            if pid in fa or pid not in b.quality or pid in RESERVED:
                continue
            pos = P.get(i, 'aljv')
            if 'ZZ' in P.get(i, 'RMbQ'):
                self.blank[pos].append(i)
            elif self._spare_ok(i):
                self.spare[pos].append(i)
        for pos in self.spare:
            self.spare[pos].sort(key=self._order)
        # (head id, skin colour) pairs the base uses for players without a real head. Nothing says
        # what a new player looks like, so he gets one of the heads of the most common skin colour.
        skin = Counter()
        for (_head, colour), n in heads.items():
            skin[colour] += n
        usual = skin.most_common(1)[0][0] if skin else 1
        self.generic_heads = sorted(k for k in heads if k[1] == usual) or [(GENERIC_HEAD, 1)]
        # the same by skin group: a new player whose photo (or country) says another skin gets a head of that group
        wears = {}      # a head shows one skin whatever the field says: a head goes to the group that most records wear it in
        for g, c in pool.items():
            for (head, _skin), n in c.items():
                wears.setdefault(head, Counter())[g] += n
        self.group_heads = {g: sorted(k for k in c if wears[k[0]].most_common(1)[0][0] == g) for g, c in pool.items()}
        self.group_eyes = {g: c.most_common(1)[0][0] for g, c in eyes.items()}
        self.country_group = {L.NAT_CODE[c]: g for c, g in faces.COUNTRY_SKIN.items() if c in L.NAT_CODE}
        # the usual birth-state code per country (Ontario for Canada, ...)
        self.home_state = {c: cnt.most_common(1)[0][0] for c, cnt in home.items()}

    def _spare_ok(self, i):
        """May this teamless record be taken over? Not a legend or well-rated player, nobody whose
        NHL rights a team holds, nobody younger than MIN_AGE, no second record of someone else in the
        game (national-team goalies)."""
        b, P = self.b, self.b.P
        pid = P.get(i, 'zIBw')
        return (pid in b.quality and b.quality[pid] < LEGEND_LEVEL and not P.get(i, 'WBbd')
                and real_birth_year(P, i, b.stale_years) <= b.data.season_year - MIN_AGE
                and len(b.records_of[b.identity(i)]) == 1)

    def _order(self, i):
        return (real_birth_year(self.b.P, i, self.b.stale_years), self.b.quality[self.b.P.get(i, 'zIBw')], i)

    def add_spare(self, prow):
        """A record that just became free (a player who retired in this run): spare from now on, in
        its place in the oldest-first order."""
        spare = self.spare[self.b.P.get(prow, 'aljv')]
        if self._spare_ok(prow) and prow not in spare and self.b.P.get(prow, 'zIBw') not in RESERVED:
            bisect.insort(spare, prow, key=self._order)

    def refresh(self):
        """The spare records again, as a new Donors would choose them now: after the ratings step
        changed players' quality (a retired player the ratings list still rates drops below LEGEND_LEVEL). A second
        run, which chooses them from this run's output, then finds exactly the same ones."""
        b, R, P = self.b, self.b.R, self.b.P
        live = b.live_entries()
        fa = {R.link_to_pid.get(l) for l in b.fa_links}
        self.spare = {pos: [] for pos in range(5)}
        for i in range(P.cur_rec):
            pid = P.get(i, 'zIBw')
            if (live.get(pid) or pid in fa or i in b.created or pid in b.attached or pid in RESERVED
                    or 'ZZ' in P.get(i, 'RMbQ') or not self._spare_ok(i)):
                continue
            self.spare[P.get(i, 'aljv')].append(i)
        for pos in self.spare:
            self.spare[pos].sort(key=self._order)

    def available(self, pos):
        return len(self.blank[pos]) + len(self.spare[pos])

    def left(self, kind):
        """Records left for goalies ('G') or for skaters of any position ('S': they can switch)."""
        return self.available(4) if kind == 'G' else sum(self.available(p) for p in range(4))

    def take(self, pos, target=None):
        """A record for a new player at position `pos` (None when nothing is left).

        Skaters share one attribute table, so when a skater position has no record left, one of
        another skater position is taken and turned into this position (goalies have a table of
        their own and cannot borrow).

        `target`: prefer the blank record whose rating level is closest to it -- matters for
        players who keep the record's ratings because nobody publishes ratings for them."""
        prow = self._take(pos, target)
        if prow is not None or pos == 4:
            return prow
        same_class = lambda q: (q == 3) == (pos == 3)
        for q in sorted((q for q in range(4) if q != pos), key=lambda q: (not same_class(q), -self.available(q), q)):
            prow = self._take(q, target)
            if prow is not None:
                self.b.set_position(prow, pos)
                return prow
        return None

    def _take(self, pos, target):
        b = self.b
        blank = self.blank[pos]
        if blank:
            if target is None:
                return blank.pop(0)
            k = min(range(len(blank)), key=lambda j: (abs(b.quality[b.P.get(blank[j], 'zIBw')] - target), j))
            return blank.pop(k)
        spare = self.spare[pos]
        while spare:
            i = spare.pop(0)
            pid = b.P.get(i, 'zIBw')
            if pid in b.attached or b.person(i) in self.reserved:
                continue
            return i
        return None

    def reserve(self, people):
        """People named in the data being applied: their existing records are not for reuse."""
        self.reserved.update((norm(p['first']), norm(p['last'])) for p in people)

    def group_for(self, name, birth_year=None, country_code=None):
        """The skin group a player's looks ask for ('medium', 'brown' or 'dark'), None for the game's usual one: the data
        pack's `skins` (his photo; the birth year may be one off), else his country's (faces.COUNTRY_SKIN), else None."""
        for year, group in (self.b.data.skins or {}).get(norm(name), ()):
            if birth_year is None or abs(year - birth_year) <= 1:
                return group
        return self.country_group.get(country_code)

    def head_of(self, name, group):
        """A generic head (head id, skin) of the skin group `group` for the person `name`: the same one every run
        (a hash of the name). None when the roster has no head of that group."""
        heads = self.group_heads.get(group)
        return heads[zlib.crc32(name.encode()) % len(heads)] if heads else None

    def fit_skins(self, log=None):
        """Players on a generic head of the wrong skin: the game gave the light ones to almost everybody. A player
        whose photo or country asks for another group (`group_for`) and who wears a head of a lighter group gets a
        head of his own (brown / dark from the photos: only from light or medium; medium from the country: only from
        light). Never a head the game scanned (below 60000), a created head, or a record of the game's Create Player.
        Doing it again changes nothing. Returns how many players changed."""
        b, P = self.b, self.b.P
        rank = {'light': 0, 'medium': 1, 'brown': 2, 'dark': 3}
        changed = 0
        for i in range(P.cur_rec):
            head = P.get(i, 'DaPp')
            now = faces.BUCKET_OF.get(P.get(i, 'QDTK'))
            if head < GENERIC_HEAD or now is None or faces.is_reserved(P, i):
                continue
            name = f"{P.get(i, 'PedH')} {P.get(i, 'RMbQ')}"
            want = self.group_for(name, real_birth_year(P, i, b.stale_years), P.get(i, 'hleL'))
            if want is None or rank[want] <= rank[now] or (want == 'medium' and now != 'light'):
                continue
            new = self.head_of(name, want)
            if new is None:
                continue
            P.set(i, 'DaPp', new[0])
            P.set(i, 'QDTK', new[1])
            P.set(i, 'jfuZ', self.group_eyes.get(want, P.get(i, 'jfuZ')))
            changed += 1
        return changed

    def reset_identity(self, prow, name, country_code=None, birth_year=None):
        """Wipe what belonged to the record's previous owner."""
        b, P = self.b, self.b.P
        P.set(prow, 'LcvS', 0)        # hasportrait
        P.set(prow, 'rnOl', 0)        # artid (menu portrait)
        P.set(prow, 'Nzao', 0)        # audioid (commentary name)
        group = self.group_for(name, birth_year, country_code)
        own = self.head_of(name, group) if group else None
        head, skin = own or self.generic_heads[zlib.crc32(name.encode()) % len(self.generic_heads)]
        P.set(prow, 'DaPp', head)     # headid: a generic head model, never the previous owner's
        P.set(prow, 'QDTK', skin)
        if own:
            P.set(prow, 'jfuZ', self.group_eyes.get(group, P.get(prow, 'jfuZ')))
        P.set(prow, 'WzKY', UNDRAFTED)
        for f in ('Ujcc', 'WfTt', 'uWgv', 'WBbd', 'yNbZ', 'MHEA'):   # draft round/position/team, proteam, junior team/league
            P.set(prow, f, 0)
        for f in CAREER_FIELDS:
            P.set(prow, f, 0)
        for f in ('ORwy', 'UVQB'):    # rookieahl, rookiechl
            P.set(prow, f, 0)
        if birth_year is not None:
            P.set(prow, 'vnCd', 1 if birth_year >= b.data.season_year - 20 else 0)   # rookie
        if country_code is not None:
            old = P.get(prow, 'hleL')
            P.set(prow, 'hleL', country_code)
            if country_code not in NORTH_AMERICA:
                P.set(prow, 'IxvQ', country_code)            # birth "state" of non-North Americans is the country
            elif old != country_code:
                P.set(prow, 'IxvQ', self.home_state.get(country_code, P.get(prow, 'IxvQ')))
