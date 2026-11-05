"""A player's face: his 3D head (`cPbu.DaPp`, headid), skin colour (`QDTK`) and eye colour (`jfuZ`).

The heads the game can draw are the rows of table `vuqu` (stockplayerheads: a head id and its two hair cards, so the
hair comes with the head); ids from 60000 on are the generic heads that created players wear. Every head worn on the
disc's roster is in it. Skin colours run 1-10 on both the disc's and the community roster, eye colours 0-6 (the game's
Create Player offers 7; docs/notes/faces.md). The Roster editor gives a player another player's face or a generic head
(edits.py `set` keys `head`, `skin`, `eyes`); `problems` is verify()'s check of what an update changed.

**The created look** (the game's Create Player "Custom Head", lab D, docs/notes/draft-class.md "Faces of created
players"): only the 180 records the game keeps for Create Player (game ids 16000-16029 goalies, 16030-16179 skaters)
can have one. It is a head shape (`SHAPES`, the custom heads 20050-21200), a skin tone 1-16 (`skincolor` from
`TONE_SKIN`, `customfacetable.skintexture` tone - 1) and the record's row of `customfacetable` (`Vzjq`, `playerid` =
game id - 16000): hair, facial hair, eyebrows and their colours, black eye, scars, freckles. A look is kept in the
player's edit as the game's own numbers (`LOOK`, `DEFAULT_LOOK`); `look_problems` is verify()'s check.
"""

GENERIC = 60000                 # head ids from here on are the game's generic heads
HEADS = 'vuqu'                  # the table of heads the game has
FIELDS = {'head': 'DaPp', 'skin': 'QDTK', 'eyes': 'jfuZ'}
SKINS = tuple(range(1, 11))
EYES = tuple(range(0, 7))
EYE_WORDS = {0: "Blue", 1: "Light Blue", 2: "Brown", 3: "Light Brown", 4: "Hazel", 5: "Green", 6: "Yellow"}

# the records the game's Create Player fills (the first free one of the kind); a created look lives only there
RESERVED = range(16000, 16180)
RESERVED_GOALIES = range(16000, 16030)
KEEP_FREE = {'G': 5, 'S': 10}   # left for the game's own Create Player: this program takes them from the top down
LOOK_TABLE = 'Vzjq'             # customfacetable, a row per reserved record
CUSTOM_HEADS = range(20000, 22000)
# the menu's Head Shape 1-15 (the skin tone does not change it); all 24 heads 20050-21200 are in `vuqu`
SHAPES = (21200, 21050, 20900, 20700, 20500, 21100, 20050, 21150, 20650, 20950, 20850, 20400, 20350, 20200, 20150)
CREATED_HEADS = range(20050, 21201, 50)     # every created head the game can draw, the menu's 15 and 9 more (20300 ...)
TONE_SKIN = (1, 1, 1, 1, 2, 2, 3, 3, 4, 4, 4, 4, 6, 9, 9, 10)     # Skin Tone 1-16 -> cPbu skincolor
# the generic heads come in four skin groups (lab and contact sheets, docs/notes/skin-tones.md): the group is the head's
# own `QDTK` values, and a head only ever shows its own skin
BUCKETS = {'light': (1, 2), 'medium': (3, 4), 'brown': (6, 7, 8), 'dark': (9, 10)}
BUCKET_OF = {skin: name for name, skins in BUCKETS.items() for skin in skins}
DARKER = ('brown', 'dark')
# countries whose players the game's one generic skin (light) misses, where it is clear (owner, 2026-11-05): ISO code ->
# group. Only the codes the roster has a country number for (layout.NAT_CODE) can be used.
COUNTRY_SKIN = {'JPN': 'medium', 'KOR': 'medium', 'CHN': 'medium', 'TPE': 'medium', 'HKG': 'medium', 'MGL': 'medium'}
COLOURS = ((5, "Black"), (0, "Blonde"), (2, "Brown"), (1, "Dirty Blonde"), (3, "Light Brown"), (4, "Red"))
# key -> (customfacetable field or None: on the player record, the menu's choices in its order as (number, the game's
# word)); the numbers are the game's own, the tone's 1-16 as the menu counts (the field holds tone - 1)
LOOK = {
    'shape': (None, tuple((n, f"Head {n}") for n in range(1, 16))),
    'tone': ('xohz', tuple((n, f"Skin Tone {n}") for n in range(1, 17))),
    'hair': ('TpVs', ((3, "Short Shaggy"), (4, "Long Slicked"), (5, "Long Wavy"), (6, "Short Curly"),
                      (8, "Dreadlocks"), (0, "Bald"), (2, "Short"), (7, "Short Wavy"))),
    'hair_colour': ('wFGt', COLOURS),
    'facial_hair': ('Gdzy', ((4, "Full"), (5, "Goatee"), (6, "Soul Patch"), (7, "Thin Beard"), (8, "Side Burns"),
                             (9, "None"), (0, "Stubble"), (1, "Moustache"), (2, "Handlebars"), (3, "Beard"))),
    'facial_hair_colour': ('lhIz', COLOURS),
    'eyebrow': ('bRvt', ((1, "Regular 2"), (2, "Bushy"), (3, "Thin 1"), (5, "Thin 2"), (4, "Unibrow"),
                         (0, "Regular 1"))),
    'eyebrow_colour': ('eiVK', COLOURS),
    'eyes': (None, tuple(EYE_WORDS.items())),
    'black_eye': ('isZW', ((0, "None"), (1, "Left"), (2, "Right"), (3, "Both"))),
    'scars': ('gFSM', ((4, "None"), (0, "Cheek"), (1, "Brow"), (2, "Lip"), (3, "Chin"))),
    'freckles': ('KYFD', ((0, "Off"), (1, "On"))),
}
LOOK_WORDS = {'shape': "Head Shape", 'tone': "Skin Tone", 'hair': "Hairstyle", 'hair_colour': "Hair Color",
              'facial_hair': "Facial Hair", 'facial_hair_colour': "Facial Hair Color", 'eyebrow': "Eyebrow",
              'eyebrow_colour': "Eyebrow Color", 'eyes': "Eye Color", 'black_eye': "Black Eye", 'scars': "Scars",
              'freckles': "Freckles"}
# a new skater in the game's Create Player
DEFAULT_LOOK = {'shape': 5, 'tone': 8, 'hair': 3, 'hair_colour': 2, 'facial_hair': 4, 'facial_hair_colour': 2,
                'eyebrow': 1, 'eyebrow_colour': 2, 'eyes': 0, 'black_eye': 0, 'scars': 4, 'freckles': 0}


def read(P, prow):
    """{'head', 'skin', 'eyes'} of the player record."""
    return {key: P.get(prow, tag) for key, tag in FIELDS.items()}


def write(P, prow, face):
    """Set the parts of `face` ({'head', 'skin', 'eyes'}, any of them) on the player record."""
    for key, value in face.items():
        P.set(prow, FIELDS[key], value)


def heads(R):
    """The head ids the game can draw (table `vuqu`); empty when the roster has no such table."""
    if HEADS not in R.f.tables:
        return set()
    V = R.f[HEADS]
    return {V.get(i, 'DaPp') for i in range(V.cur_rec)}


def generic(R):
    """The generic heads, lowest first."""
    return sorted(h for h in heads(R) if h >= GENERIC)


def wrong(face, valid):
    """What in `face` the game cannot show (`valid`: heads()), as words, or None. A created head (CUSTOM_HEADS) is
    never a `set` head: it needs a created look's row (write_look)."""
    if 'head' in face and face['head'] in CUSTOM_HEADS:
        return f"head {face['head']} is a created head (it comes with a created look)"
    if 'head' in face and valid and face['head'] not in valid:
        return f"head {face['head']} is not one of the game's heads"
    if 'skin' in face and face['skin'] not in SKINS:
        return f"skin colour {face['skin']} is not 1-10"
    if 'eyes' in face and face['eyes'] not in EYES:
        return f"eye colour {face['eyes']} is not 0-6"
    return None


def problems(R, source):
    """Faces the update changed (or gave a new player) that the game cannot show. A part the source already had for
    that player is not blamed (one community player wears a head the table lacks). A created look's head is
    look_problems' to check."""
    valid = heads(R)
    before = {source.P.get(i, 'zIBw'): read(source.P, i) for i in range(source.P.cur_rec)}
    out = []
    for prow in range(R.P.cur_rec):
        face, old = read(R.P, prow), before.get(R.P.get(prow, 'zIBw')) or {}
        changed = {key: value for key, value in face.items() if old.get(key) != value}
        if changed.get('head') in CUSTOM_HEADS and is_reserved(R.P, prow):
            changed.pop('head')
        why = changed and wrong(changed, valid)
        if why:
            out.append(f"{R.name(prow)}: {why}")
    return out


def is_reserved(P, prow, goalie=None):
    """Is the record one the game keeps for Create Player (a goalie's / a skater's, when `goalie` says which)?"""
    pid = P.get(prow, 'zIBw')
    if pid not in RESERVED:
        return False
    return goalie is None or (pid in RESERVED_GOALIES) == bool(goalie)


def is_free(R, prow):
    """A reserved record nobody has: no name, not active, on no team (a free agent is on the list with a roster
    entry-less link, but has a name)."""
    P = R.P
    return (is_reserved(P, prow) and not P.get(prow, 'NYKk') and not P.get(prow, 'RMbQ') and not P.get(prow, 'PedH')
            and not R.entries_by_pid.get(P.get(prow, 'zIBw')))


def free_reserved(R, goalie, taken=()):
    """The free reserved records of the kind this program may take, the highest game id first (the game's Create Player
    takes the lowest), KEEP_FREE of them left over. `taken`: records already given out in this run."""
    P = R.P
    rows = sorted((i for i in range(P.cur_rec) if is_reserved(P, i, goalie) and is_free(R, i) and i not in taken),
                  key=lambda i: -P.get(i, 'zIBw'))
    return rows[:max(0, len(rows) - KEEP_FREE['G' if goalie else 'S'])]


def look_row(R, prow):
    """The record's row of customfacetable, or None (not a reserved record, or no such table)."""
    if LOOK_TABLE not in R.f.tables or not is_reserved(R.P, prow):
        return None
    V, n = R.f[LOOK_TABLE], R.P.get(prow, 'zIBw') - RESERVED.start
    if n < V.cur_rec and V.get(n, 'qFky') == n:
        return n
    return next((i for i in range(V.cur_rec) if V.get(i, 'qFky') == n), None)


def look_wrong(look):
    """What in a look (any of its parts) the game's Create Player does not offer, as words, or None."""
    for key, value in look.items():
        if key not in LOOK:
            return f"{key} is not part of a look"
        if value not in dict(LOOK[key][1]):
            return f"{LOOK_WORDS[key]} {value} is not one of the game's choices"
    return None


def clean_look(look):
    """(the whole look: `look`'s parts over DEFAULT_LOOK, problems as words). A part that is not one of the game's
    choices keeps the default."""
    out, problems = dict(DEFAULT_LOOK), []
    for key, value in (look or {}).items():
        try:
            value = int(value)
        except (TypeError, ValueError):
            problems.append(f"{LOOK_WORDS.get(key, key)} {value!r} is not a number")
            continue
        why = look_wrong({key: value})
        if why:
            problems.append(why)
        else:
            out[key] = value
    return out, problems


def write_look(R, prow, look):
    """Give the reserved record the created look (clean_look's whole look): the head shape, skin and eye colour on the
    record, the rest in its customfacetable row. False when the record cannot have one."""
    row = look_row(R, prow)
    if row is None:
        return False
    P, V = R.P, R.f[LOOK_TABLE]
    P.set(prow, 'DaPp', SHAPES[look['shape'] - 1])
    P.set(prow, 'QDTK', TONE_SKIN[look['tone'] - 1])
    P.set(prow, 'jfuZ', look['eyes'])
    for key, (tag, _choices) in LOOK.items():
        if tag:
            V.set(row, tag, look[key] - 1 if key == 'tone' else look[key])
    V.set(row, 'NtOg', 0)                   # wrinkles: not in the menu
    return True


def read_look(R, prow):
    """The record's created look, or None (not a reserved record, or not wearing a created head)."""
    row = look_row(R, prow)
    head = R.P.get(prow, 'DaPp')
    if row is None or head not in SHAPES:
        return None
    V = R.f[LOOK_TABLE]
    look = {key: V.get(row, tag) for key, (tag, _choices) in LOOK.items() if tag}
    look['tone'] += 1
    look['shape'] = SHAPES.index(head) + 1
    look['eyes'] = R.P.get(prow, 'jfuZ')
    return look


def random_look(rng):
    """A plain random look (random.Random `rng`): any head shape and skin tone, hair, eyebrows and beard of one colour
    (black on the darkest tones), mostly no beard or stubble; no black eye, scar or freckles."""
    tone = rng.randint(1, 16)
    colour = 5 if tone >= 13 else rng.choices((5, 2, 3, 1, 0, 4), (3, 4, 2, 2, 1, 1))[0]
    return {'shape': rng.randint(1, len(SHAPES)), 'tone': tone,
            'hair': rng.choices((3, 4, 5, 6, 8, 0, 2, 7), (3, 1, 1, 2, 1 if tone >= 13 else 0, 1, 4, 3))[0],
            'hair_colour': colour, 'facial_hair': rng.choices((9, 0, 4, 5, 6, 7, 3), (6, 5, 1, 1, 1, 1, 1))[0],
            'facial_hair_colour': colour, 'eyebrow': rng.choice((1, 2, 3, 5, 0)), 'eyebrow_colour': colour,
            'eyes': rng.choices(tuple(EYE_WORDS), (3, 2, 4, 2, 2, 2, 0))[0], 'black_eye': 0, 'scars': 4, 'freckles': 0}


def look_words(look):
    """'Head 5, Skin Tone 8, Short Shaggy, Brown' for the card."""
    words = {key: dict(LOOK[key][1]).get(value, str(value)) for key, value in look.items() if key in LOOK}
    out = [words.get('shape'), words.get('tone'), words.get('hair')]
    if look.get('hair') != 0:
        out.append(f"{words.get('hair_colour', '').lower()} hair")
    if look.get('facial_hair') != 9:
        out.append(f"facial hair {words.get('facial_hair', '').lower()} ({words.get('facial_hair_colour', '').lower()})")
    out.append(f"{words.get('eyes', '').lower()} eyes")
    return ", ".join(w for w in out if w)


def link_problems(R, source):
    """verify()'s check of the Create Player records' links (`exhibitionplayers`): each keeps the game's own (table 1,
    number = game id), and no other link names one of them, as with the game's own Create Player. A new career copies
    the created look only of a player listed through his own link (lab round 45: an ordinary link gave a blue head).
    A link the source already had is not blamed."""
    def links(roster):
        C = roster.C
        return [(C.get(i, 'qEfv'), C.get(i, 'BERR'), C.get(i, 'qFky')) for i in range(C.cur_rec)]
    had = set(links(source))
    own = {pid for link, kind, pid in links(R) if pid in RESERVED and link == pid and kind == 1}
    out = [f"the game's own link of Create Player record {pid} is gone"
           for pid in sorted({pid for link, kind, pid in had if pid in RESERVED and link == pid and kind == 1} - own)]
    for link, kind, pid in links(R):
        if pid in RESERVED and (link, kind) != (pid, 1) and (link, kind, pid) not in had:
            prow = R.p_by_id.get(pid)
            who = R.name(prow) if prow is not None else f"Create Player record {pid}"
            out.append(f"{who}: listed through link {link}, not the game's own link of his record")
    return out


def look_problems(R, source):
    """verify()'s check of created looks: a created head only on a reserved record, one of the created heads the game
    can draw (all of CREATED_HEADS, not only the menu's 15 SHAPES: a roster the game or another tool saved may wear the
    others), with a skin colour that fits its tone; customfacetable keeps its rows (one per reserved record) and every
    changed row holds the game's choices. What the source already had is not blamed."""
    out = []
    P = R.P
    old = {source.P.get(i, 'zIBw'): (source.P.get(i, 'DaPp'), source.P.get(i, 'QDTK')) for i in range(source.P.cur_rec)}
    old_tones = {}
    if LOOK_TABLE in source.f.tables:
        W = source.f[LOOK_TABLE]
        old_tones = {W.get(i, 'qFky'): W.get(i, 'xohz') for i in range(W.cur_rec)}
    drawable = (heads(R) & set(CUSTOM_HEADS)) or set(CREATED_HEADS)
    for prow in range(P.cur_rec):
        pid, head = P.get(prow, 'zIBw'), P.get(prow, 'DaPp')
        if head not in CUSTOM_HEADS:
            continue
        was_head, was_skin = old.get(pid, (None, None))
        if not is_reserved(P, prow):
            if was_head != head:
                out.append(f"{R.name(prow)}: a created head ({head}) on a record the game's Create Player does not use")
        elif head not in drawable:
            if was_head != head:
                out.append(f"{R.name(prow)}: head {head} is not one of the game's created heads")
        elif (row := look_row(R, prow)) is not None:
            tone = R.f[LOOK_TABLE].get(row, 'xohz')
            same = (was_head, was_skin, old_tones.get(pid - RESERVED.start)) == (head, P.get(prow, 'QDTK'), tone)
            if not same and (tone >= len(TONE_SKIN) or P.get(prow, 'QDTK') != TONE_SKIN[tone]):
                out.append(f"{R.name(prow)}: skin colour {P.get(prow, 'QDTK')} does not fit skin tone {tone + 1}")
    if LOOK_TABLE not in R.f.tables or LOOK_TABLE not in source.f.tables:
        return out
    V, W = R.f[LOOK_TABLE], source.f[LOOK_TABLE]
    if [V.get(i, 'qFky') for i in range(V.cur_rec)] != [W.get(i, 'qFky') for i in range(W.cur_rec)]:
        return out + ["customfacetable: its rows changed (one per Create Player record)"]
    tags = [(key, tag) for key, (tag, _choices) in LOOK.items() if tag]
    for i in range(V.cur_rec):
        now = {key: V.get(i, tag) for key, tag in tags}
        if now == {key: W.get(i, tag) for key, tag in tags} and V.get(i, 'NtOg') == W.get(i, 'NtOg'):
            continue
        now['tone'] += 1
        why = look_wrong(now) or (V.get(i, 'NtOg') and "wrinkles are not one of the game's choices")
        if why:
            out.append(f"customfacetable row {V.get(i, 'qFky')}: {why}")
    return out
