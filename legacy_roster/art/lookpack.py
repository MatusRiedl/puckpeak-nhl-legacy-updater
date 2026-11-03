"""The look pack (looks.zip): this season's jerseys and centre-ice logos, already in the PS3's layout (made by the
maintainer's private tools, DEVELOPING.md). It is downloaded from the program's file server while "Photos, logos and
team names" is on (packs.py, 0.32.0). Without it (not downloaded yet, offline), `LookPack.open()` returns None and
every team keeps the look it had (the game's own, or Utah / Seattle / Vegas made from their colours). `art/looks.py`
puts these pictures onto the player's own disc files (`looks.pack_team`, `looks.Maker.pack_files`).

    looks.zip
        index.json         {"format": 1, "built", "teams": {slot: {"league", "name", "style",
                            "kits": {"dark" | "light" | "third": {"numbers": [fill, outline] or null}},
                            "ice"}}}
        j/<slot>_<role>.webp   a jersey's colour map, 1024 x 1024, in the team's PS3 cut (`style`)
        m/<slot>_<role>.webp   the pack's own menu picture of that kit (the shirt alone on a clear ground, cut to the shirt,
                               200 px tall; since 2026-10-18, a pack without it gets the recoloured chassis picture)
        f/<slot>_<role>.webp   the kit's own number sheet (names, digits, C / A, sleeve digits), 512 x 512 with
                               transparency, in the game's glyph layout (since 2026-10-27; a pack without it gets the
                               chassis' sheet recoloured)
        i/<slot>.webp          the centre-ice logo, 1024 x 1024 with transparency
        s/<slot>_<role>.webp   the kit's own sock in the game's layout, 1024 x 512 (since 0.95.0; the kit's index entry also
                               has "pants": [main, stripe]; a pack without them gets the chassis' recoloured to the kit)

"name" is the club the slot holds after an update (the data pack's full name; for the NHL the code, for the national
teams the abbreviation): a slot that holds another club keeps its own look.
"""
import io
import json
import os
import re
import unicodedata
import zipfile

FORMAT = 1
ROLES = ('dark', 'light', 'third')


def norm(name):
    """A club's name for comparing: no accents, no case, letters and digits only ('Färjestad BK' -> 'farjestadbk')."""
    text = unicodedata.normalize('NFKD', name or '').casefold()
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in text if not unicodedata.combining(c)))


class LookPack:
    def __init__(self, path):
        self.path = path
        self.zip = zipfile.ZipFile(path)
        index = json.loads(self.zip.read('index.json'))
        if index.get('format') != FORMAT:
            raise ValueError(f"look pack format {index.get('format')}")
        self.built = index.get('built', '')
        self.teams = {int(slot): team for slot, team in (index.get('teams') or {}).items()}
        self._crc = {i.filename: i.CRC for i in self.zip.infolist()}

    @classmethod
    def open(cls, path=None):
        """The pack at `path` (default: the downloaded one, packs.path), or None (none yet, or it cannot be read)."""
        from .. import packs
        path = path or packs.path('looks')
        if not path or not os.path.exists(path):
            return None
        try:
            return cls(path)
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            return None

    def __len__(self):
        return len(self.teams)

    def jersey_member(self, slot, role):
        return f"j/{slot}_{role}.webp"

    def menu_member(self, slot, role):
        return f"m/{slot}_{role}.webp"

    def font_member(self, slot, role):
        return f"f/{slot}_{role}.webp"

    def sock_member(self, slot, role):
        return f"s/{slot}_{role}.webp"

    def ice_member(self, slot):
        return f"i/{slot}.webp"

    def has(self, member):
        return member in self._crc

    def crc(self, member):
        """A short mark of a stored picture (the zip's own check sum): a rebuilt pack with another picture gives another."""
        return f"{self._crc.get(member, 0):08x}"

    def picture(self, member):
        """A stored picture as a Pillow picture (RGB for jerseys, RGBA for the menu pictures and the ice)."""
        from PIL import Image
        img = Image.open(io.BytesIO(self.zip.read(member)))
        img.load()
        return img

    def holds(self, slot, R):
        """Does slot `slot` of roster `R` hold the team the pack made its look for? The NHL slots always do; a national
        team by its abbreviation; a club by its full name (a league step left out keeps the slot's old club)."""
        team = self.teams.get(slot)
        if team is None:
            return False
        if team.get('league') == 'nhl':
            return True
        if team.get('league') == 'national':
            return R.T.get(slot, 'abbrname') == team.get('name')
        return norm(R.team_name(slot)) == norm(team.get('name'))
