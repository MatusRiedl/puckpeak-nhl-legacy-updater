"""Which picture each player and club shows: the roster side of "Photos and logos".

A player's menu portrait is the art file p<artid>.big (`artid` and `hasportrait` in his record).
When photos are switched on, every player the update placed and who has a photo link gets one:

- an id the game already uses for him keeps it: the game's own ids (1-12,401, the disc's portraits) and
  the community roster's ids (12,402-13,826, its portrait pack). His file is replaced by the
  current photo;
- anyone else gets an id of his own from NEW_IDS. Ids are remembered per person on this PC
  (`Registry`), so the same player keeps his picture in every roster made here, and the next
  update writes the same ids again (a build on its own output stays byte-identical).

A picture file is shared by every roster of the game version, so a number is only good for one person on
the whole PC (testers, 0.10.4: a community roster's own numbers showed our photos of other people).
`Claims` says who else uses which number (every roster save, picture files another pack put there); a
number someone else uses is never given out, and one of ours that turns out to be someone else's is
forgotten (`forget_conflicts`): our player gets a fresh one and the file goes back to its owner
(install.give_back).

Clubs need no change in the roster: a club's logo is the file t<artid>.big of its team record.

`plan()` returns the pictures to make; `install.py` downloads, draws and writes them. Nothing
here needs Pillow.
"""
import json
import os
import unicodedata

from .. import custom_kit
from .. import datasource

from .. import layout as L

DISC_IDS = range(1, 12402)           # the disc's portraits
COMMUNITY_IDS = range(12402, 13827)  # the community roster's portrait pack
NEW_IDS = range(20000, 65536)       # ours (artid is 16 bits)
# where new ones are given out: above the numbers the community's picture packs use (its 2026-27 roster: up to
# 30,007); numbers given out before stay unless someone else uses them
FRESH_IDS = range(40000, 65536)
SHARED_POOL_ART = 20054             # the custom logo every prospect pool of the base roster uses
POOL_ART = custom_kit.POOL_ART      # + slot: a pool's own logo (team artid is 15 bits)
CUSTOM_LEAGUE = 13
# NHL slots the community roster gave to newer teams; the game's text still names the old ones
NHL_NAMES = {22: ("Utah Mammoth", "Utah", "UTA"), 30: ("Seattle Kraken", "Seattle", "SEA"),
             31: ("Vegas Golden Knights", "Vegas", "VGK")}


def person_key(first, last, birth):
    """A player's identity across rosters: plain-letter name and birthdate."""
    plain = lambda s: unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower().strip()
    return f"{plain(first)}|{plain(last)}|{birth[0]:04d}-{birth[1]:02d}-{birth[2]:02d}"


def loose_key(key):
    """A person key without the birth year, to compare people across rosters: a roster for the game patch keeps
    years shifted (gamepatch.year_shift), others have stale ones."""
    first, last, birth = key.split('|')
    return f"{first}|{last}|{birth[5:]}"


def same_person(a, b):
    """Are two loose keys one person? The last name must match, then the first name or the birthday: rosters
    disagree on either (NHL.com's Alexander for a roster's Alex, a birthday the update corrected). Twins (the
    Sedins) differ in the first letter."""
    if a == b:
        return True
    fa, la, da = a.split('|')
    fb, lb, db = b.split('|')
    return la == lb and (fa.startswith(fb) or fb.startswith(fa) or (da == db and fa[:1] == fb[:1]))


def strangers(keys, lk):
    """Does anyone in `keys` (loose keys) differ from the person `lk`?"""
    return any(not same_person(k, lk) for k in keys)


class Claims:
    """Who uses which portrait number on this PC besides the roster being built (install.scan_claims).
    `rosters` {number: {loose keys}}: the people every roster save shows with that number; `theirs`: our numbers
    (NEW_IDS) whose file another pack put there (also one we covered, its copy kept); `ours`: numbers whose
    files this program installed, with `urls` {number: photo link}."""

    def __init__(self, rosters=None, theirs=(), ours=(), urls=None):
        self.rosters = {a: set(k) for a, k in (rosters or {}).items()}
        self.theirs = set(theirs)
        self.ours = set(ours)
        self.urls = dict(urls or {})

    def others(self, aid, key):
        """Does anyone but the person `key` use this number?"""
        return aid in self.theirs or strangers(self.rosters.get(aid, ()), loose_key(key))

    def contested(self):
        """Numbers of ours that rosters on this PC give to more than one person."""
        return {a for a in self.ours if any(strangers(self.rosters[a], k) for k in self.rosters.get(a, ()))}

    def used(self):
        return set(self.rosters) | self.theirs | self.ours


class Registry:
    """Portrait ids given out on this PC: {person key: id}, kept in a small JSON file."""

    def __init__(self, path=None):
        self.path = path or datasource.app_dir('art', 'portrait_ids.json')
        self.ids = {}
        try:
            with open(self.path, encoding='utf-8') as f:
                self.ids = {k: int(v) for k, v in json.load(f).items()}
        except (OSError, ValueError):
            pass
        self.dirty = False

    def id_for(self, key, current, taken, claims=None, here=None):
        """The id for a person: his remembered one, else the id he has in the roster if it is
        one of ours, else the next free one; never one another person uses (`here`: {id: loose keys}
        in this roster, `claims`: the rest of this PC). `taken`: every id in this roster."""
        lk = loose_key(key)
        owners = {v: k for k, v in self.ids.items()}

        def free(aid):
            return (not (here and strangers(here.get(aid, ()), lk))
                    and not (claims and claims.others(aid, key)))
        remembered = self.ids.get(key)
        if remembered is not None and free(remembered):
            return remembered
        if current in NEW_IDS and owners.get(current, key) == key and free(current):
            aid = current
        else:
            used = set(owners) | set(taken) | set(here or ()) | (claims.used() if claims else set())
            aid = next(i for i in FRESH_IDS if i not in used)
        self.ids[key] = aid
        self.dirty = True
        return aid

    def forget(self, key):
        if self.ids.pop(key, None) is not None:
            self.dirty = True

    def save(self):
        if self.dirty:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.ids, f, indent=0, sort_keys=True)
            os.replace(tmp, self.path)
            self.dirty = False


def birth_of(P, prow):
    return (P.get(prow, 'dnFq') + 1910, P.get(prow, 'pLKJ') + 1, P.get(prow, 'iwsK') + 1)


def mine(my_edits, team_edits):
    """Do the player's edits hold pictures of his own (a player's photo, a team's logo)?"""
    return (any(e.get('photo') for e in (my_edits or {}).values())
            or any(e.get('logo') for e in (team_edits or {}).values()))


def forget_conflicts(registry, claims):
    """Forget the ids of ours someone else uses on this PC (another roster, another pack's file): those players
    get a fresh one in plan(). Returns {id: (person key, photo link installed under it or None)}."""
    gone = {}
    for key, aid in sorted(registry.ids.items()):
        if claims.others(aid, key):
            gone[aid] = (key, claims.urls.get(aid))
            registry.forget(key)
    return gone


def plan(b, registry, own_only=False, claims=None, check=None, moved=None, names_on=None):
    """Give every placed player with a photo his portrait id (written into the roster) and list
    the pictures to make: ({artid: photo link}, {team artid: (logo link, colours)}, names).

    `own_only`: only the player's own pictures (the Roster editor's; photos and logos are off): no other
    player, team or name changes. `claims` (Claims): numbers the rest of this PC uses. `check(links)` ->
    {link: why} the photos that cannot be made: those players keep the picture they had. `moved`
    (forget_conflicts): players whose id was given back get a fresh one with the photo they had. `names_on`: the team
    names are chosen too (the "Team names" switch; default: with photos and logos, as before 0.76.0)."""
    P, T = b.P, b.R.T
    if names_on is None:
        names_on = not own_only
    taken = {P.get(r, 'artid') for r in range(P.cur_rec)}
    key_of = lambda r: person_key(P.get(r, 'PedH'), P.get(r, 'RMbQ'), birth_of(P, r))
    here = {}           # id -> the people this roster shows with it
    for r in range(P.cur_rec):
        if P.get(r, 'hasportrait'):
            here.setdefault(P.get(r, 'artid'), set()).add(loose_key(key_of(r)))
    photos = {r: u for r, u in b.photos.items() if not own_only or r in b.own_photos}
    if moved and not own_only:
        for r in range(P.cur_rec):
            aid = P.get(r, 'artid')
            if r not in photos and P.get(r, 'hasportrait') and aid in moved and moved[aid][1] \
                    and same_person(loose_key(moved[aid][0]), loose_key(key_of(r))):
                photos[r] = moved[aid][1]
    bad = check(sorted(set(photos.values()))) if check and photos else {}
    b.bad_pictures = dict(bad)
    portraits, given = {}, {}
    for prow in sorted(photos):
        url = photos[prow]
        if url in bad:
            continue                    # he keeps the picture he had (none is better than a blank)
        aid, key = P.get(prow, 'artid'), key_of(prow)
        lk = loose_key(key)
        shared = (strangers(here.get(aid, ()), lk) or not same_person(given.get(aid, lk), lk)
                  or (claims is not None and claims.others(aid, key)))
        if aid not in DISC_IDS and aid not in COMMUNITY_IDS or shared:
            aid = registry.id_for(key, aid, taken - {aid}, claims, here)
            taken.add(aid)
            P.set(prow, 'artid', aid)
        given[aid] = lk
        P.set(prow, 'hasportrait', 1)
        portraits[aid] = url
    if not own_only:
        _pool_logos(b)
    logos = {}
    for slot, url in sorted(b.logos.items()):
        if own_only and slot not in b.own_logos:
            continue
        if own_only and T.get(slot, 'artid') == SHARED_POOL_ART:
            T.set(slot, 'artid', POOL_ART + slot)      # as _pool_logos does: not every pool's logo
        colours = tuple(tuple(T.get(slot, f"{c}color_{x}") for x in 'rgb') for c in ('primary', 'secondary'))
        logos[T.get(slot, 'artid')] = (url, colours)
    return portraits, logos, names(b) if names_on else None


def _pool_logos(b):
    """The prospect pools in the spare custom slots all share one custom logo (art id 20054). Each
    gets an art id of its own and a logo: an NHL "System" pool its NHL team's, a draft class a
    badge with its year (drawn by images.badge)."""
    T, R = b.R.T, b.R
    names_ = {t: n.replace('®', '').strip().lower() for t, n in b.nhl_names.items()}    # before any team edit
    # "Red Wings System" -> the NHL team whose name ends in "red wings" (two-word cities too: "los angeles kings")
    parent_of = lambda nick: next((t for t, n in names_.items() if n.endswith(' ' + nick)), None)
    nhl_logo = {L.API_TO_SLOT[a]: url for a, url in b.data.nhl_logos.items() if a in L.API_TO_SLOT}
    for slot in sorted(L.SPARE):
        if slot >= T.cur_rec or not b.entries_on(slot):
            continue
        name = R.team_name(slot).strip()
        art = T.get(slot, 'artid')
        if art == SHARED_POOL_ART:
            T.set(slot, 'artid', POOL_ART + slot)
        elif art in custom_kit.ARTS:
            continue        # a create-a-team logo picked in the Roster editor (custom_kit): the game draws that one
        if name.endswith('System'):
            parent = parent_of(name[:-len('System')].strip().lower())
            if parent is not None and parent in nhl_logo:
                b.logos.setdefault(slot, nhl_logo[parent])
        elif name[:4].isdigit():
            b.logos.setdefault(slot, f"badge:{name[:4]}")


def _nick(full, city):
    """'Rytíři Kladno' with city 'Kladno' -> 'Rytíři'; the full name when nothing sensible is left."""
    rest = full.replace(city, '').strip(' -') if city and city in full else ''
    return rest if len(rest) >= 3 else full


def names(b):
    """The names the menus should show (the game takes them from its text file, loc.py):
    {'teams': [(art code, full, city, nickname, abbreviation)], 'cities': {custom team key: name},
     'force': {art codes written even when the game's own text looks the same}}.

    A custom team shows only the text under its `shortname` (a key like COACHELLA_VALLEY, see
    Builder.custom_city_keys); it gets the team's full name there, unless the game already has a
    text under that key (ANAHEIM for the Ducks copy). Coachella Valley and Henderson also get the
    club texts of their art code (CVF, HSK), which the patched game reads; so do the Vees (PEN)."""
    T, R = b.R.T, b.R
    teams, cities = [], {}
    for slot, (full, city, abbr) in NHL_NAMES.items():           # the community's Utah, Seattle, Vegas
        T.set(slot, 'fullname', full)
        T.set(slot, 'shortname', city)
        T.set(slot, 'abbrname', abbr)
    clubs = L.SHL | L.LIIGA | L.DEL | L.EXTRALIGA | L.NL | L.NORWAY | L.AHL | L.CHL
    for slot in range(T.cur_rec):
        if slot in L.EVENTS or not b.entries_on(slot):
            continue
        if T.get(slot, 'league') == CUSTOM_LEAGUE and not L.is_city_key(T.get(slot, 'shortname')):
            # a city the game cannot find a text for ("NhlCityName_13" on the Kings copy, a roster made
            # by version 0.4): a key in the game's style; a copy takes its NHL team's city (LOS_ANGELES)
            city = T.get(b.mirror_of[slot], 'shortname') if slot in b.mirror_of else T.get(slot, 'shortname')
            L.set_city(T, slot, city or T.get(slot, 'fullname'))
        art = T.get(slot, 'artabbr')
        full, city, abbr = T.get(slot, 'fullname'), T.get(slot, 'shortname'), T.get(slot, 'abbrname')
        if T.get(slot, 'league') == CUSTOM_LEAGUE:
            if L.is_city_key(city):
                name = full
                if slot in b.mirror_of:         # the game has texts for the copies' cities; a fallback only
                    primary = T.get(b.mirror_of[slot], 'shortname')
                    name = primary if L.city_key(primary) == city else city.replace('_', ' ').title()
                cities[city] = (name or city.replace('_', ' ').title()).replace('®', '').strip()
            if slot in L.AHL or (slot == L.VEES and L.is_vees(T)):
                # Coachella Valley / Henderson / the Vees: the patched game lists them in their league and names them the
                # club way, by their art code (gamepatch stage Y); the unpatched one by the key above
                town = city.replace('_', ' ').title() if L.is_city_key(city) else city
                teams.append((art, full, town, _nick(full, town), abbr))
            elif slot in b.team_names and slot not in b.mirror_of:
                teams.append((art, full, city, _nick(full, city), abbr))
        elif slot in NHL_NAMES or slot in clubs or slot in b.team_names:
            teams.append((art, full, city, _nick(full, city), abbr))
    # the community's NHL slots also have texts under their number, and show the NHL's ® sign
    numbered = {s: (full, city, full[len(city):].strip() if full.startswith(city + ' ') else full, abbr)
                for s, (full, city, abbr) in NHL_NAMES.items()}
    return {'teams': teams, 'cities': cities, 'numbered': numbered,
            'marked': {T.get(s, 'artabbr') for s in NHL_NAMES},
            'force': {T.get(s, 'artabbr') for s in set(NHL_NAMES) | set(b.team_names)}}
