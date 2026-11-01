"""The "Jerseys and ice" window of a custom team (slots 222-251: the prospect pools, Coachella Valley, Henderson).

The game draws these teams like teams made in Create a Team (custom_kit.py, lab round 37): a crest out of the game's
create-a-team logos (or a picture of the player's own on one of them), a jersey design for home and away, pants, socks
and numbers out of the game's few, and the colours of every piece. The window shows the game's own Create a Team pictures
and keeps what the player sets in edits.json (`teams[slot]['kit']`, edits.py), merged with what was kept before: only
"Undo all for this team" drops it. Three team colours paint every piece the player has not set by itself as they are
typed ("Paint everything" also starts those pieces again); each piece can be set by itself, home and away. The centre ice of a custom team shows its crest.
"""
import io
import re
import threading

from .. import custom_kit as K
from .. import layout as L
from . import dataurl

PICS = (('jersey', K.JERSEYS), ('pants', K.STYLES), ('socks', K.STYLES), ('font', K.STYLES))
MENU = 'fe/ion/artassets/createteam/{kind}/{kind}{n}.big'     # the game's Create a Team pictures (cache.big)
THUMB = (192, 96)
LOGO_THUMB = (96, 96)
DESIGNS = (('home', "Home jersey", 'jersey'), ('away', "Away jersey", 'jersey'), ('pants', "Pants", 'pants'),
           ('socks', "Socks", 'socks'), ('font', "Numbers", 'font'))
TEAM = ("Main colour", "Second colour", "Third colour")
OWN, MINE = 'own', 'mine'


def _hex(colour):
    return K.hex_of(colour)


class TeamKit:
    """What the window shows and keeps for custom team `slot` of roster `R`; `saved` the team's kit kept so far."""

    def __init__(self, R, slot, name, saved):
        self.slot, self.name = slot, name
        self.kit = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                    for k, v in (saved or {}).items()}
        self.current = K.colours(R, slot)                   # the roster as it is
        self.design = K.design(R, slot)
        self.own_art = L.OWN_ART.get(slot)
        self.reserved = {K.logo_of(art) for s, art in L.OWN_ART.items() if s != slot}
        team = K.team_colours(self.kit)
        if team is None:
            body = self.current.get((9, K.HOME)) or [(255, 255, 255)] * 3
            team = list(self.design['colours']) + [body[2]]
        self.typed = [_hex(c) for c in team]
        self.valid = [tuple(c) for c in team]               # the last colour that could be read of each
        self.side = K.HOME

    # --- what is chosen ---------------------------------------------------------------------------------
    def crest(self):
        """'own' (Coachella Valley's / Henderson's own crest), 'mine' (a picture of the player's own) or a logo number."""
        c = str(self.kit.get('crest') or '')
        if c.startswith('file:'):
            return MINE
        if c.startswith('logo:') and c[5:].isdigit():
            return int(c[5:])
        logo = self.design['logo']
        if self.own_art is not None and (logo is None or K.FIRST_ART + logo == self.own_art):
            return OWN
        return logo

    def _drawn(self):
        return self.crest() in (OWN, MINE)

    def shown(self):
        return K.shown_colours(self.current, self.kit, self._drawn(), self.slot)

    def value(self, part):
        if part in ('home', 'away'):
            jersey = self.kit.get('jersey') or self.design['jersey']
            n = jersey[0 if part == 'home' else 1]
            return n if n in K.JERSEYS else 0              # 9 shows design 0 in the game
        return self.kit.get(part, self.design[part])

    # --- the player's choices -------------------------------------------------------------------------------
    def set_design(self, part, n):
        try:
            n = int(n)
        except (TypeError, ValueError):
            return False
        if part in ('home', 'away'):
            if n not in K.JERSEYS:
                return False
            jersey = [self.value('home'), self.value('away')]
            jersey[0 if part == 'home' else 1] = n
            self.kit['jersey'] = jersey
            return True
        if part in ('pants', 'socks', 'font') and n in K.STYLES:
            self.kit[part] = n
            return True
        return False

    def type_colour(self, i, text):
        try:
            i = int(i)
        except (TypeError, ValueError):
            return False
        if not 0 <= i < 3:
            return False
        self.typed[i] = str(text or '')
        if K.rgb(text):
            self.valid[i] = K.rgb(text)
            # kept as the team colours at once (before, only "Paint everything" kept them and a Save lost what was
            # typed); the pieces set one by one stay on top
            self.kit['colours'] = [_hex(c) for c in self.team()]
        return True

    def team(self):
        """The three typed team colours as (r, g, b) (a colour that cannot be read: the one shown before)."""
        return list(self.valid)

    def paint(self):
        """Every piece in the three team colours: the pieces set one by one start again (a crest picture keeps its
        colours)."""
        self.kit['colours'] = [_hex(c) for c in self.team()]
        self.kit['all'] = True              # also what was made by hand for Coachella Valley / Henderson
        keep = {k: v for k, v in (self.kit.get('pieces') or {}).items()
                if self.crest() == MINE and K.piece_key(k) and K.piece_key(k)[0] == K.CREST}
        if keep:
            self.kit['pieces'] = keep
        else:
            self.kit.pop('pieces', None)

    def set_side(self, side):
        try:
            side = int(side)
        except (TypeError, ValueError):
            return False
        if side not in (K.HOME, K.AWAY):
            return False
        self.side = side
        return True

    def set_zone(self, piece, zone, text):
        """Zone `zone` (1...) of piece `piece` on the side shown to colour `text`."""
        try:
            piece, zone = int(piece), int(zone)
        except (TypeError, ValueError):
            return False
        colour = K.rgb(text)
        zones = self.shown().get((piece, self.side))
        if colour is None or zones is None or not 1 <= zone <= len(zones) or (piece == K.CREST and self._drawn()):
            return False
        zones = list(zones)
        zones[zone - 1] = colour
        self.kit.setdefault('pieces', {})[f"{piece}/{self.side}"] = [_hex(c) for c in zones]
        return True

    def reset_piece(self, piece):
        """Piece `piece` on the side shown back to what the team colours (or the roster) give it."""
        pieces = self.kit.get('pieces') or {}
        pieces.pop(f"{piece}/{self.side}", None)
        if not pieces:
            self.kit.pop('pieces', None)

    def set_logo(self, value):
        """The crest: 'own' or a game logo number."""
        if value == OWN and self.own_art is not None:
            self.kit.pop('crest', None)
        else:
            try:
                n = int(value)
            except (TypeError, ValueError):
                return False
            if n not in K.LOGOS or n in self.reserved:
                return False
            self.kit['crest'] = f"logo:{n}"
        self._drop_crest_colours()
        return True

    def set_picture(self, link, colours):
        """A crest picture of the player's own (`link`, 'file:...') drawn in its own three main colours `colours`."""
        self.kit['crest'] = link
        self._drop_crest_colours()
        zones = [_hex(c) for c in colours[:3]] + [_hex(K.WHITE)] * 3
        pieces = self.kit.setdefault('pieces', {})
        for side in (K.HOME, K.AWAY):
            pieces[f"{K.CREST}/{side}"] = list(zones)

    def _drop_crest_colours(self):
        pieces = self.kit.get('pieces') or {}
        for side in (K.HOME, K.AWAY):
            pieces.pop(f"{K.CREST}/{side}", None)
        if not pieces:
            self.kit.pop('pieces', None)

    def collect(self):
        """The kit to keep (edits.json): what was kept before with this visit's changes."""
        return {k: v for k, v in self.kit.items() if v not in (None, {}, [])}

    # --- what the page shows -------------------------------------------------------------------------------
    def snapshot(self, note, loaded, pictures):
        crest = self.crest()
        shown = self.shown()
        touched = {K.piece_key(k) for k in (self.kit.get('pieces') or {})}
        team = self.team()
        pieces = []
        for piece, (label, zone_names) in K.PIECES.items():
            zones = shown.get((piece, self.side))
            if zones is None:
                continue
            pieces.append({'piece': piece, 'label': label, 'touched': (piece, self.side) in touched,
                           'locked': piece == K.CREST and crest in (OWN, MINE),
                           'zones': [{'zone': z, 'label': zone_names[z - 1], 'hex': _hex(c)}
                                     for z, c in enumerate(zones, start=1)]})
        if crest == MINE:
            crest_text = "Crest: your picture, drawn on one of the game's create-a-team logos no other team wears."
        elif crest == OWN:
            crest_text = "Crest: the team's own."
        else:
            crest_text = (f"Crest: the game's logo {crest}." if crest is not None else
                          "Crest: none of the game's create-a-team logos yet. Pick one, or your own picture.")
        return {'kind': 'custom', 'slot': self.slot, 'title': f"{self.name}: jerseys and ice", 'note': note,
                'loaded': loaded, 'pictures': pictures,
                'crest': {'value': crest if crest in (OWN, MINE) else str(crest), 'text': crest_text,
                          'own': self.own_art is not None,
                          'logos': [str(n) for n in K.LOGOS if n not in self.reserved]},
                'designs': [{'part': part, 'label': label, 'kind': kind, 'value': self.value(part),
                             'items': list(K.JERSEYS if kind == 'jersey' else K.STYLES)}
                            for part, label, kind in DESIGNS],
                'team': [{'i': i, 'label': TEAM[i], 'text': self.typed[i], 'hex': _hex(team[i])} for i in range(3)],
                'side': self.side, 'pieces': pieces}


def menu_pictures(disc):
    """{'<kind>:<n>': data: link} of the game's Create a Team pictures: jersey designs, pants, socks, numbers and the
    logos (by logo number; the game's files are named by art id)."""
    from PIL import Image
    from ..art.bigf import ArtFile
    arc = disc.archives['cache.big']
    out = {}

    def read(name):
        try:
            img = Image.open(io.BytesIO(ArtFile(arc.read(name)).image()))
            img.load()
            return img
        except Exception:
            return None
    names = set(arc.entries)
    for kind, numbers in PICS:
        for n in numbers:
            name = MENU.format(kind=kind, n=n)
            img = read(name) if name in names else None
            if img is not None:
                out[f"{kind}:{n}"] = dataurl.picture(img, THUMB)
    logo = re.compile(r"^fe/ion/artassets/createteam/logo/logo(\d+)\.big$")
    for name in sorted(names):
        m = logo.match(name)
        n = K.logo_of(int(m.group(1))) if m else None
        if n is None:
            continue
        img = read(name)
        if img is not None:
            img = img.convert('RGBA')
            box = img.getchannel('A').getbbox()
            out[f"logo:{n}"] = dataurl.picture(img.crop(box) if box else img, LOGO_THUMB)
    return out


def read_menu_pictures(pictures, done):
    """The Create a Team pictures from the player's disc in a worker thread; `done(found)` ({} when the disc cannot be
    read)."""
    def job():
        try:
            found = pictures.disc_work(menu_pictures)
        except Exception:
            found = {}
        done(found)
    threading.Thread(target=job, daemon=True).start()
