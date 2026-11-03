"""What a roster holds, in the shape the roster editor shows it (no window code here).

`Snapshot` reads a roster save into teams and players; `compare()` tells what the player's edits
changed between two of them (the roster as it is and with this session's edits). Players are matched
across rosters by person (edits.who_of: plain name + birthdate), because an edit may give a player
another record. `apply_edits()` makes the roster with the edits (no window needed).
"""
import datetime

from .. import edits, equipment, faces, ratings
from .. import layout as L
from ..roster import Roster
from ..schema import LIST_GOALIE, LIST_SKATER, RATING_BASE

POSITION = {0: 'C', 1: 'LW', 2: 'RW', 3: 'D', 4: 'G'}
POS_KEY = {'C': 'C', 'LW': 'L', 'RW': 'R', 'D': 'D', 'G': 'G'}
COUNTRY = {code: iso for iso, code in L.NAT_CODE.items()}
FREE_AGENTS = 'FA'
SHOWN_AS = {22: ('Arizona Coyotes', 'Utah Mammoth', 'UTA'), 30: (' / ', 'Seattle Kraken', 'SEA'),
            31: (' / ', 'Vegas Golden Knights', 'VGK')}


def _labels(amap):
    """Attribute names in the game's order, one per field."""
    seen, out = set(), []
    for label, field in amap.items():
        if field not in seen:
            seen.add(field)
            out.append(label)
    return out


SKATER_ATTRIBUTES = _labels(LIST_SKATER)
GOALIE_ATTRIBUTES = _labels(LIST_GOALIE)


class Player:
    __slots__ = ('who', 'prow', 'pid', 'first', 'last', 'pos', 'num', 'birth', 'country', 'shoots', 'height_in',
                 'weight_lb', 'teams', 'clubs', 'ovr', 'ratings', 'artid', 'hasportrait', 'equipment', 'style', 'face', 'created',
                 'look')

    @property
    def name(self):
        return f"{self.first} {self.last}"

    def age(self, season_year):
        y, m, d = self.birth
        return season_year - y - (1 if (m, d) > (9, 15) else 0)     # age at the start of the season

    def values(self):
        """What can be edited, for comparing two rosters."""
        return {'first': self.first, 'last': self.last, 'num': self.num, 'pos': self.pos, 'shoots': self.shoots,
                'birth': self.birth, 'country': self.country, 'height_in': self.height_in,
                'weight_lb': self.weight_lb, 'ovr': self.ovr, 'equipment': self.equipment, 'style': self.style,
                'face': self.face, 'look': self.look}

    @property
    def style_label(self):
        """His player type as the editor names it (GRN, PLY ... or its number), '' without a rating record."""
        return '' if self.style is None else ratings.style_label(self.style, self.pos == 'G')


class Snapshot:
    """Teams and players of one roster save (bytes or Roster)."""

    def __init__(self, source, ovr_offset=None, season_year=None, farm_ahl=False):
        self.R = R = source if isinstance(source, Roster) else Roster(source)
        self.season_year = season_year or datetime.date.today().year - (datetime.date.today().month < 9)
        self.offset = ovr_offset or {False: 0.0, True: 0.0}
        P, U, T = R.P, R.U, R.T
        # the game's own roster as the disc has it: birth years in the game's year - 1900 (stock.prepare
        # moves them), or every player would look ten years off and "new to the game" next to the update
        from .. import stock
        base = stock.birth_base(R)
        own = stock.untouched(R)          # the 2014 roster as it is: slots 30 / 31 are still its All-Star teams
        self.team_names = {t: R.team_name(t) for t in range(T.cur_rec)}
        # slots 30 / 31 keep the game's All-Star names in the table of a roster for the unpatched game, 22 Arizona's; the
        # game names them Utah / Seattle / Vegas from its text file (art/portraits.NHL_NAMES), and so does the window
        self.team_codes = {}
        for t, (old, full, code) in SHOWN_AS.items():
            if old in self.team_names.get(t, '') and not (own and t in (30, 31)):
                self.team_names[t], self.team_codes[t] = full, code
        self.heads = faces.heads(R)       # the heads the game can draw (the Roster editor's Face)
        self.copies = L.copies(R)         # {copy slot: its NHL team}, by the roster's own layout (none on the game's own)
        # by the game's league field, as the game lists them: Coachella Valley and Henderson (custom slots 234 / 235)
        # under the AHL in a roster for the game patch (gamepatch.league_fit), also when it is read the update's way
        # (`farm_ahl`: unleagued), else under Custom (owner, 2026-10-19)
        self.team_league = {t: 'AHL' if farm_ahl and t in L.AHL else L.LEAGUE_NAMES.get(T.get(t, 'jjMx'), 'Other')
                            for t in range(T.cur_rec)}
        if L.is_vees(T):     # the Vees under the WHL on every roster (owner, 2026-11-03; the unpatched game calls them Custom)
            self.team_league[L.VEES] = 'WHL'
        self.rosters = {}                 # team -> [pid]
        teams_of = {}
        for i in range(U.cur_rec):
            pid = R.link_to_pid.get(U.get(i, 'TWSX'))
            t = U.get(i, 'BSXd')
            self.rosters.setdefault(t, []).append(pid)
            teams_of.setdefault(pid, []).append(t)
        self.free_agents = [R.link_to_pid.get(R.Q.get(i, 'TWSX')) for i in range(R.Q.cur_rec)]
        self.rosters[FREE_AGENTS] = self.free_agents
        ai = {}
        for tname in (ratings.SKATER_TABLE, ratings.GOALIE_TABLE):
            t = R.f[tname]
            for i in range(t.cur_rec):
                ai[t.get(i, 'zIBw')] = (tname, i)
        gear = R.f[equipment.TABLE]
        gear_row = equipment.row_of(gear)
        pads = R.f[equipment.GOALIE_TABLE]
        pads_row = equipment.row_of(pads, 'goalie')
        self.players = {}
        for pid in set(teams_of) | set(self.free_agents):
            prow = R.p_by_id.get(pid)
            if prow is None:
                continue
            p = Player()
            p.prow, p.pid = prow, pid
            p.first, p.last = P.get(prow, 'PedH'), P.get(prow, 'RMbQ')
            p.pos = POSITION.get(P.get(prow, 'aljv'), '?')
            p.num = P.get(prow, 'tRVs')
            p.birth = edits.birth_of(P, prow, base)
            p.who = edits.who_of(P, prow, base)
            p.country = COUNTRY.get(P.get(prow, 'hleL'), str(P.get(prow, 'hleL')))
            p.shoots = 'R' if P.get(prow, 'pkRG') else 'L'
            p.height_in = P.get(prow, 'QBpy') + 54
            p.weight_lb = P.get(prow, 'WZNs') + 120
            p.teams = sorted(teams_of.get(pid, []))
            p.clubs = club(p.teams, self.copies)      # his own teams: no national team, no copy of an NHL team
            p.artid, p.hasportrait = P.get(prow, 'artid'), P.get(prow, 'hasportrait')     # his menu photo
            p.ratings, p.ovr, p.style = {}, None, None
            p.face = faces.read(P, prow)
            p.created = faces.is_reserved(P, prow)        # on a record of the game's Create Player: can have a look
            p.look = faces.read_look(R, prow) if p.created else None
            p.equipment = (equipment.read(pads, pads_row[pid], 'goalie') if p.pos == 'G' and pid in pads_row else
                           equipment.read(gear, gear_row[pid]) if p.pos != 'G' and pid in gear_row else None)
            where = ai.get(pid)
            if where:
                table = R.f[where[0]]
                goalie = where[0] == ratings.GOALIE_TABLE
                amap = LIST_GOALIE if goalie else LIST_SKATER
                labels = GOALIE_ATTRIBUTES if goalie else SKATER_ATTRIBUTES
                p.ratings = {a: table.get(where[1], amap[a]) + RATING_BASE for a in labels}
                p.ovr = round(ratings.level(table, where[1]) + self.offset[goalie])
                p.style = table.get(where[1], 'sFgQ')
            self.players[pid] = p
        self.by_who = {}
        for p in sorted(self.players.values(), key=lambda p: (not [t for t in p.teams if t not in L.NATIONAL], p.prow)):
            self.by_who.setdefault(p.who, p)

    def leagues(self):
        """League names that have players, in the game's order, then free agents."""
        seen = []
        for t in sorted(t for t in self.rosters if t != FREE_AGENTS):
            name = self.team_league[t]
            if self.rosters[t] and name not in seen:
                seen.append(name)
        return seen + ['Free agents']

    def teams_in(self, league):
        if league == 'Free agents':
            return [FREE_AGENTS]
        return [t for t in sorted(t for t in self.rosters if t != FREE_AGENTS)
                if self.team_league[t] == league and self.rosters[t]]

    def team_name(self, team):
        return 'Free agents' if team == FREE_AGENTS else self.team_names.get(team, f"#{team}")

    def roster(self, team):
        return [self.players[pid] for pid in self.rosters.get(team, []) if pid in self.players]

    def search(self, text, limit=200):
        t = text.lower().strip()
        return [p for p in self.by_who.values() if t in p.name.lower()][:limit] if t else []

    def wearers(self, head):
        """The players (one per person) who wear the head `head`, by name."""
        return sorted((p for p in self.by_who.values() if p.face['head'] == head), key=lambda p: p.name)


def apply_edits(raw, my_edits, team_edits, season_year, art=None):
    """The roster `raw` (SYS-DATA bytes) with the player's edits and no update step: a pipeline.BuildResult
    (its `data` is the new SYS-DATA, `problems` what the safety checks found). `art` (pipeline.Pictures, own pictures
    only): the players with a picture of the player's own get their picture numbers; `art` of the result lists them."""
    from .. import gamepatch, pipeline
    from ..builder import Data
    from ..roster import Roster
    return pipeline.build(raw, Data(season_year=season_year or 2026), steps=[], my_edits=my_edits or None,
                          team_edits=team_edits or None, game_patch=gamepatch.is_patch_roster(Roster(raw)), art=art)


def club(teams, copies=None):
    """`teams` without national teams and copies of NHL teams (`copies`: Snapshot.copies; None: the community's)."""
    copies = L.MIRROR_OF if copies is None else copies
    return [t for t in teams if t not in L.NATIONAL and t not in copies]


def compare(before, after, team, renamed=None):
    """How `team` changed from `before` to `after` (two Snapshots):
    {'joined': {who: where from}, 'left': [Player of before], 'changed': {who: [field, ...]}}.
    `renamed` maps a renamed player's new key to his old one (edits keep the old one)."""
    renamed = dict(renamed or {})
    # the same record under the same name whose birthdate the update corrected (NHL.com's) is the
    # same person, not one leaving and another joining
    by_pid = {q.pid: q for q in before.roster(team)}
    for p in after.roster(team):
        q = by_pid.get(p.pid)
        if q is not None and q.who != p.who and (q.first, q.last) == (p.first, p.last):
            renamed.setdefault(p.who, q.who)
    old_key = lambda who: renamed.get(who, who)
    now = {old_key(p.who) for p in after.roster(team)}
    was = {p.who for p in before.roster(team)}
    out = {'joined': {}, 'left': [], 'changed': {}}
    for p in after.roster(team):
        old = before.by_who.get(old_key(p.who))
        if old_key(p.who) not in was:
            out['joined'][p.who] = ('new to the game' if old is None else
                                    ', '.join(before.team_name(t) for t in old.clubs) or 'free agent')
        elif old is not None:
            a, b = old.values(), p.values()
            diff = [k for k in b if a[k] != b[k]]
            if old.ratings != p.ratings and 'ovr' not in diff:
                diff.append('ratings')
            if diff:
                out['changed'][p.who] = diff
    for p in before.roster(team):
        if p.who not in now:
            out['left'].append(p)
    return out
