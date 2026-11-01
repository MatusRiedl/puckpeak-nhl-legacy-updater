"""The look of a custom team (slots 222-251: the prospect pools, Coachella Valley, Henderson, the switched-off ones).

The game draws these teams like teams made in Create a Team (lab rounds 34 and 37, docs/notes/lab-round-37.md), not from
jersey files of their own:
- team table `ttOk`: `jerseybackhome` / `jerseybackaway` the jersey design worn at home / away (0-8 = the Create a Team
  menu's jersey0-8 and `rendering/czjersey/jerseyct_<cut>_<n>`; 9 falls back to 0), `pantsstyle`, `sockstyle`, `font`
  (0-5: `czpant/pantct_<n>`, `czsock/texlib_<n>`, `czfont/czfont_<n>`), `artid` = 20001 + the create-a-team logo (the
  crest, `czlogo/logoct_<n>`), `primarycolor` / `secondarycolor` (menus, goalie gear);
- table `NDEo` (customteamequipmenttable): 30 teams x 11 pieces x home / away, team = slot + 1, variant 1 home / 2 away,
  zones 1-9 RGB (PIECES). Only the colours change here; the rows stay.

The Roster editor keeps a team's look in edits.json (`teams[slot]['kit']`, edits.py) and `write` puts it into the
roster. Standard library only.
"""
from .layout import CLUB_ART, OWN_KIT

SLOTS = range(222, 252)
POOL_ART = 21000                    # + slot: a prospect pool's own menu logo (art/portraits.py; drawn there, not here)
TABLE = 'NDEo'
FIRST_ART = 20001                   # art id of create-a-team logo 0
LOGOS = tuple(n for n in range(87) if n != 54)      # the disc's create-a-team logos (54 has no files)
ARTS = frozenset(FIRST_ART + n for n in LOGOS)
JERSEYS = range(9)                  # designs the game draws (9 shows design 0: the community roster has one)
STYLES = range(6)                   # pants, socks and numbers
# the design fields and the values verify allows on a custom slot. jerseystyle (one bit) is not the design: with 0 (every
# custom slot of the game's own roster) the game draws the jersey plain, without the design and its colours (lab round
# 46: white, black in another RPCS3); with 1 (the community's teams) as designed. Only 1 is ever written.
DRAWN = 1
DESIGN_FIELDS = {'jerseybackhome': range(10), 'jerseybackaway': range(10), 'pantsstyle': STYLES,
                 'sockstyle': STYLES, 'font': STYLES, 'jerseystyle': (DRAWN,)}
DESIGN_WORDS = {'jerseybackhome': "home jersey", 'jerseybackaway': "away jersey", 'pantsstyle': "pants",
                'sockstyle': "socks", 'font': "numbers", 'jerseystyle': "jersey style"}
HOME, AWAY = 1, 2
# piece -> (name for the player, its zones' names): the zones the game paints (the others hold one value everywhere)
PIECES = {
    9: ("Jersey", ("Body", "Stripe", "Second stripe", "Collar", "Shoulders", "Trim")),
    10: ("Name and numbers", ("Fill", "Outline", "Second outline")),
    8: ("Helmet", ("Colour 1", "Colour 2", "Colour 3")),
    5: ("Gloves", tuple(f"Colour {z}" for z in range(1, 10))),
    7: ("Pants", ("Colour 1", "Colour 2", "Colour 3")),
    6: ("Socks", ("Colour 1", "Colour 2", "Colour 3")),
    11: ("Crest", tuple(f"Colour {z}" for z in range(1, 7))),
    1: ("Goalie: catching glove", tuple(f"Colour {z}" for z in range(1, 10))),
    2: ("Goalie: blocker", tuple(f"Colour {z}" for z in range(1, 10))),
    3: ("Goalie: pads", tuple(f"Colour {z}" for z in range(1, 10))),
    4: ("Goalie: stick", ("Colour 1", "Colour 2", "Colour 3")),
}
CREST = 11
KEYS = ('index', 'team', 'equipment', 'variant', 'brand')     # what a row of NDEo is: never changed
WHITE, GREY = (245, 245, 245), (232, 232, 232)


def is_custom(slot):
    return isinstance(slot, int) and slot in SLOTS


def logo_of(art):
    """The create-a-team logo number of art id `art`, or None."""
    return art - FIRST_ART if art in ARTS else None


def rgb(text):
    """'#rrggbb' as (r, g, b), or None."""
    t = str(text or '').strip().lstrip('#')
    try:
        return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)) if len(t) == 6 else None
    except ValueError:
        return None


def hex_of(colour):
    return '#%02x%02x%02x' % tuple(colour)


def _rows(R, slot):
    """{(piece, variant): row} of `slot` in NDEo."""
    E = R.f[TABLE]
    return {(E.get(i, 'equipment'), E.get(i, 'variant')): i for i in range(E.cur_rec) if E.get(i, 'team') == slot + 1}


def colours(R, slot):
    """{(piece, variant): [(r, g, b) per zone the game paints]} of a custom team."""
    E = R.f[TABLE]
    return {key: [tuple(E.get(i, f'zone{z}_{c}') for c in 'rgb') for z in range(1, len(PIECES[key[0]][1]) + 1)]
            for key, i in _rows(R, slot).items() if key[0] in PIECES}


def design(R, slot):
    """{'jersey': [home, away], 'pants', 'socks', 'font', 'logo' (or None), 'colours': [3 (r, g, b)]} as the roster has
    them."""
    T = R.T
    return {'jersey': [T.get(slot, 'jerseybackhome'), T.get(slot, 'jerseybackaway')],
            'pants': T.get(slot, 'pantsstyle'), 'socks': T.get(slot, 'sockstyle'), 'font': T.get(slot, 'font'),
            'logo': logo_of(T.get(slot, 'artid')),
            'colours': [tuple(T.get(slot, f'{k}color_{c}') for c in 'rgb') for k in ('primary', 'secondary')]}


def fill(main, second, third):
    """{(piece, variant): zones} for every piece but the crest, home and away, from a team's three colours: home in the
    main colour, away on white (the way layout.OWN_KIT was made by hand). Deterministic."""
    a, b, c, w = tuple(main), tuple(second), tuple(third), WHITE
    out = {}
    for v, body, hood, sock in ((HOME, a, a, (a, b, c)), (AWAY, w, w, (w, a, b))):
        accent = b if v == HOME else a
        out[(9, v)] = (body, accent, c, accent, hood, c)
        out[(10, v)] = (b, c, a) if v == HOME else (a, b, w)
        out[(8, v)] = (a, b, c) if v == HOME else (w, w, a)
        out[(5, v)] = (a,) * 6 + (b, a, a)
        out[(7, v)] = (a, a, b)
        out[(6, v)] = sock
        out[(1, v)] = (body,) * 4 + (accent,) + (body,) * 3 + (c,)
        out[(2, v)] = out[(1, v)]
        out[(3, v)] = (body, accent, body, body, c, accent, body, accent, c) if v == AWAY else \
            (body,) * 4 + (b, c, body, c, c)
        out[(4, v)] = (GREY, a, b)
    return out


def _paint(R, row, zones):
    E = R.f[TABLE]
    for z, colour in enumerate(zones, start=1):
        if colour is None:
            continue
        for c, x in zip('rgb', colour):
            E.set(row, f'zone{z}_{c}', max(0, min(255, int(x))))


def free_logo(R, slot, reserved=()):
    """A create-a-team logo for slot `slot`'s own crest picture that no other team wears: its own when no other team has
    it (so a second run changes nothing), else the lowest free one; never one in `reserved` (Coachella Valley's and
    Henderson's). None when every logo is taken."""
    T = R.T
    worn = {T.get(s, 'artid') for s in range(T.cur_rec) if s != slot}
    mine = logo_of(T.get(slot, 'artid'))
    if mine is not None and FIRST_ART + mine not in worn and mine not in reserved:
        return mine
    return next((n for n in LOGOS if FIRST_ART + n not in worn and n not in reserved), None)


def write(R, slot, kit, reserved=(), own_art=None):
    """Put the look `kit` (edits.json `teams[slot]['kit']`, see edits.py) into custom slot `slot` of roster `R`: the
    crest, the designs, the three team colours (team colours + every piece, `fill`; the crest too when it is one of the
    game's logos: a crest picture keeps the colours made from it), each piece the player set (on top). `reserved` {logo
    number}: logos kept for other teams' crests; `own_art`: the art id the slot keeps for its own crest (Coachella Valley,
    Henderson: layout.OWN_ART). Returns (what changed as words, the crest picture link or None). Values the game has no
    use for are left out. The jersey is drawn as designed (`DRAWN`), also on a slot of the game's own roster."""
    T, words = R.T, []
    T.set(slot, 'jerseystyle', DRAWN)
    crest, picture = str(kit.get('crest') or ''), None
    if crest.startswith('logo:'):
        try:
            n = int(crest[5:])
        except ValueError:
            n = None
        if n in LOGOS and n not in reserved:
            T.set(slot, 'artid', FIRST_ART + n)
            words.append("crest")
    elif crest.startswith('file:'):
        n = logo_of(own_art) if own_art else free_logo(R, slot, reserved)
        if n is not None:
            T.set(slot, 'artid', FIRST_ART + n)
            picture = crest
            words.append("crest picture")
    drawn = picture is not None or (own_art is not None and T.get(slot, 'artid') == own_art)
    jersey = kit.get('jersey')
    if isinstance(jersey, (list, tuple)) and len(jersey) == 2:
        for field, n in zip(('jerseybackhome', 'jerseybackaway'), jersey):
            if n in JERSEYS:
                T.set(slot, field, n)
                words.append(DESIGN_WORDS[field])
    for part, field in (('pants', 'pantsstyle'), ('socks', 'sockstyle'), ('font', 'font')):
        if kit.get(part) in STYLES:
            T.set(slot, field, kit[part])
            words.append(DESIGN_WORDS[field])
    team = team_colours(kit)
    if team:
        for kind, colour in zip(('primary', 'secondary'), team):
            for c, x in zip('rgb', colour):
                T.set(slot, f'{kind}color_{c}', x)
        words.append("team colours")
    if kit.get('pieces'):
        words.append("colours in detail")
    rows, before = _rows(R, slot), colours(R, slot)
    for key, zones in sorted(shown_colours(before, kit, drawn, slot).items()):
        if zones != before[key]:
            _paint(R, rows[key], zones)
    return words, picture


def team_colours(kit):
    """The kit's three team colours as (r, g, b), or None."""
    team = [rgb(c) for c in (kit.get('colours') or [])[:3]]
    return team if len(team) == 3 and all(team) else None


def piece_key(key):
    """'<piece>/<variant>' as (piece, variant), or None."""
    try:
        piece, variant = (int(x) for x in str(key).split('/'))
    except ValueError:
        return None
    return (piece, variant) if piece in PIECES and variant in (HOME, AWAY) else None


def hand_made(current, slot):
    """The pieces of `slot` that still wear the colours made by hand for it (layout.OWN_KIT: Coachella Valley, Henderson):
    typed team colours leave them alone, only "Paint everything" (kit 'all') repaints them."""
    return {key for key, zones in (OWN_KIT.get(slot) or {}).items()
            if key in current and tuple(map(tuple, current[key])) == tuple(map(tuple, zones[:len(current[key])]))}


def shown_colours(current, kit, drawn, slot=None):
    """{(piece, variant): zones} a custom team wears with `kit` on top of `current` (colours()): the three team colours
    paint every piece (the crest too when it is one of the game's logos, not a crest picture: `drawn`), then the pieces
    the player set one by one. A piece made by hand for `slot` keeps its colours unless the kit says 'all'. The window
    shows this, `write` puts it in."""
    out = {key: list(zones) for key, zones in current.items()}
    team = team_colours(kit)
    if team:
        painted = fill(*team)
        if not drawn:                       # the game's logo takes the team's colours (zones 4-6: unused, white)
            painted.update({(CREST, v): tuple(team) + (WHITE,) * 3 for v in (HOME, AWAY)})
        keep = set() if kit.get('all') or slot is None else hand_made(current, slot)
        for key, zones in painted.items():
            if key in out and key not in keep:
                out[key] = list(zones[:len(out[key])])
    pieces = kit.get('pieces') or {}
    for name in sorted(pieces):
        key = piece_key(name)
        if key in out:
            given = [rgb(c) for c in (pieces[name] or [])[:len(out[key])]]
            out[key] = [g or old for g, old in zip(given + [None] * len(out[key]), out[key])]
    return out


def problems(R, source, crests=None):
    """verify's check of the custom teams' looks: the design fields change only on custom slots and only to values the
    game draws; a custom slot's new art id is a create-a-team logo the disc has (or a prospect pool's own menu logo,
    POOL_ART + slot); NDEo keeps its rows (only colours
    change); every art id in `crests` ({slot: art id} of the teams whose own crest picture the photos install) is that
    slot's and no other team's (they would wear it too)."""
    out = []
    T, S = R.T, source.T
    for slot in range(min(T.cur_rec, S.cur_rec)):
        for field, allowed in DESIGN_FIELDS.items():
            v = T.get(slot, field)
            if v != S.get(slot, field) and (slot not in SLOTS or v not in allowed):
                out.append(f"{R.team_name(slot)}: {DESIGN_WORDS[field]} {v} is not one the game can draw there")
        art = T.get(slot, 'artid')
        if slot in SLOTS and art != S.get(slot, 'artid') and art not in ARTS and art != POOL_ART + slot \
                and art != CLUB_ART.get(slot):
            out.append(f"{R.team_name(slot)}: art id {art} is not one of the game's create-a-team logos")
    if TABLE in R.f.tables and TABLE in source.f.tables:
        E, F = R.f[TABLE], source.f[TABLE]
        if E.cur_rec != F.cur_rec or any(E.get(i, k) != F.get(i, k) for i in range(E.cur_rec) for k in KEYS):
            out.append("the custom teams' colour table lost or moved a row")
    for slot, art in sorted((crests or {}).items()):
        if T.get(slot, 'artid') != art:
            out.append(f"{R.team_name(slot)}: its crest picture is for art id {art}, the team has {T.get(slot, 'artid')}")
        others = [R.team_name(s) for s in range(T.cur_rec) if s != slot and T.get(s, 'artid') == art]
        if others:
            out.append(f"{R.team_name(slot)}'s crest picture would show on {', '.join(others)} too")
    return out
