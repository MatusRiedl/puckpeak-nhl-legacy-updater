"""Turn a source roster into an updated one.

`Builder` owns the working copy of the save and the bookkeeping every step shares: roster
entries and links, the free-agent list, line slots, contracts and the change log. It also holds
the NHL and national-team steps; club leagues are in leagues/. pipeline.build() runs the steps.
"""
import heapq
import struct
import zlib
from collections import Counter

from . import contracts as pay
from . import layout as L
from . import lines
from . import schema
from . import ratings
from .donors import Donors, real_birth_year
from .faces import RESERVED
from .matching import match, norm, same_first_name


class ChangeLog(list):
    """The change log: rows [team, change, player, detail, number], each tagged on its way in with
    the part of the update it belongs to (`section`: 'NHL', a league's name, ...) as a sixth
    column, so the list of changes can group them (Chicago and Chicoutimi are both 'CHI')."""
    section = ''

    def append(self, row):
        super().append(list(row) + [self.section])


class Data:
    """Everything the builder needs from outside the save."""

    def __init__(self, nhl_players=None, ratings_list=None, iihf=None, season_year=2026, leagues=None, nhl_logos=None,
                 nhl_last=None, drafts=None, schedule=None, calendar=None, contracts=None, ratings_full=None,
                 league_schedules=None, real_lines=None, club_lines=None, equipment=None, retired=None, skins=None):
        self.nhl_players = nhl_players or []   # flat list, see datasource.flatten_nhl()
        self.ratings_list = ratings_list           # [{'name','team','position','birth','ovr','attrs'}] or None
        self.ratings_full = ratings_full                # the full ratings (data pack part `ratings_full`), with the ratings step
        self.iihf = iihf                       # {'AUT': [player, ...]} or None
        self.season_year = season_year         # the year the season starts in
        self.leagues = leagues or {}           # club leagues: {'liiga': {'teams': [{'slot', 'players', ...}]}}
        self.nhl_logos = nhl_logos or {}       # NHL.com team code -> logo link (photos and logos)
        self.nhl_last = nhl_last or []         # who played in the NHL last season; 'team' None: unsigned now
        self.retired = retired or []           # who announced his retirement [{'first', 'last', 'birth'}] (data pack part `retired`)
        self.drafts = drafts or []             # NHL draft picks (draft.py)
        self.schedule = schedule or []         # the season's games [date, home code, away code] (schedule.py)
        self.calendar = calendar               # which way to write them (schedule.VARIANTS), None: the default
        # the club leagues' seasons {part: [date, home slot, away slot]} (data pack `schedules`, the AHL's `ahl_schedule`;
        # schedule.apply_league)
        self.league_schedules = league_schedules or {}
        self.contracts = contracts or []       # real 2026-27 NHL contracts (contracts.py), only with the NHL step
        self.club_lines = club_lines or {}      # club slot (str) -> {'slots': {slot name: [first, last, birth year]}} (data pack part `club_lines`)
        self.real_lines = real_lines or {}     # NHL team code -> {'slots': {slot name: NHL.com id}} (data pack part `lines`)
        self.skins = skins                     # skin groups of players by photo (data pack part `skins`, datasource.skins_part)
        self.equipment = equipment             # real sock tucks, pant lengths, neck guards (data pack part `equipment`, datasource.equipment_part)


LINK_LIMIT = 16000      # player link ids from here up are the game's own
# a free agent or a player leaving his team retires at this age when he did not play in the NHL last
# season and no league lists him (the game's own roster: stock.RETIRE_AGE)
FA_RETIRE_AGE = 35
# an unsigned player of last season retires at this age (born season_year - 38 or earlier; owner, 2026-10-28: Kopitar, Toews)
UNSIGNED_RETIRE_AGE = 38
FREE_AGENTS = "Free agents"     # the part of the list of changes for retired and unsigned free agents
REPAIRS = "Repairs"             # what Builder.mend put right before the roster was written


def stock_retire_age():
    from .stock import RETIRE_AGE
    return RETIRE_AGE


def source_rank(team):
    """Which non-NHL entry to promote: AHL first, then prospect pools, draft classes, juniors."""
    if team in L.AHL:
        return 0
    if team in L.SYSTEM_POOL_SLOTS:
        return 1
    if 62 <= team <= 100:
        return 2
    return 3


def marker(table):
    """The row a table header names as the last one removed (the word at 0x18 is 1 and the row), or None."""
    word = struct.unpack_from('>I', table.header, 0x18)[0]
    return word & 0xFFFF if word >> 16 == 1 else None


def drop_removed_player(R):
    """The community's 2026-27 roster was saved by the game right after a player was removed: the
    entry and link tables name his rows in their headers (Jonathan Drouin: entry 225, link row
    2945), and he is on no free-agent list and has no contract team. The game treats those rows as
    removed; our update did not know, put him on the free-agent list when he was not on an NHL
    roster, and Season mode then crashed on his link (every roster this program made, from the
    community roster or the game's own, 2026-10-06). The two rows are removed here, before anything
    else looks at the roster; the markers in every table header are cleared. Returns his name, or
    None when the roster has no such player (the game's own roster and ROSTER2526 have no markers)."""
    U, C, P = R.U, R.C, R.P
    row, link_row = marker(U), marker(C)
    name = None
    if row is not None and link_row is not None and row < U.cur_rec and link_row < C.cur_rec:
        link = U.get(row, 'TWSX')
        prow = R.p_by_id.get(R.link_to_pid.get(link))
        listed = any(R.link_to_pid.get(Q_link) == R.link_to_pid.get(link) for Q_link in (R.Q.get(i, 'TWSX') for i in range(R.Q.cur_rec)))
        if C.get(link_row, 'qEfv') == link and prow is not None and P.get(prow, 'BSXd') == 0 and not listed:
            name = R.name(prow)
            U.delete_record(row)
            C.delete_record(link_row)
            R.kept_links = {link}
    if name is None and (row is not None or link_row is not None):
        # a roster this program made before the fix (0.8.0) from that roster: the markers are still in its
        # headers, but the rows moved; he is a free agent on his old link, which is dropped by
        # relink_free_agents() (pipeline.build) so that a second update does not carry the crash on
        R.stale_markers = True
    for table in R.f.tables:
        R.f[table].header[0x18:0x1C] = b'\x00\x00\xff\xff'
    R.reindex()
    return name


# Utah, Seattle and Vegas also get a city: both rosters still hold Arizona Arena (Glendale) in 22 and one row "Bridgestone
# Arena, Nashville" for 30 and 31 (lab round 32: Utah's game intro said "Arizona Arena, GLENDALE, AZ"); the game's own
# roster has Arizona's colours in slot 22 and the All-Star slots' in 30 and 31.
#
# Every NHL team's arena name (with its (R) / (TM) mark) and two team colours as the testers listed them (2026-10-26, docs/notes/
# arenas-colours.md), by slot; both rosters held 2014 or half-right names and colours. `nhl_identity` writes them.
NHL_ARENAS = ("Honda Center®", "Canada Life Centre™", "TD Garden®", "KeyBank Center®", "Scotiabank Saddledome™",
              "Lenovo Center™", "United Center®", "Ball Arena™", "Nationwide Arena®", "American Airlines Center®",
              "Little Caesars Arena®", "Rogers Place™", "Amerant Bank Arena®", "CRYPTO.COM Arena™", "Grand Casino Arena™",
              "Centre Bell™", "Bridgestone Arena™", "Prudential Center®", "UBS Arena®", "Madison Square Garden®",
              "Canadian Tire Centre™", "Xfinity Mobile Arena™", "Delta Center®", "PPG Paints Arena®", "Enterprise Center™",
              "SAP Center at San Jose®", "Benchmark International Arena™", "Scotiabank Arena®", "Rogers Arena™",
              "Capital One Arena®", "Climate Pledge Arena®", "T-Mobile Arena™")
NHL_COLOUR_HEX = ("cf4520 89734c", "041e41 004a98", "ffb81c 010101", "003087 ffb81c", "c8102e f1be48", "cc0000 000000",
                  "ce1126 000000", "6f263d 236192", "003366 cc0033", "00843d a7a9ac", "ce1126 ffffff", "00205b d14520",
                  "cf102d 091f3f", "a2aaad 010101", "024930 af1e24", "af1e2d 192168", "ffb81c 041e42", "cc0000 000000",
                  "00468b f26924", "0033a0 c8102e", "da1a32 b79257", "d24303 000000", "6cace4 010101", "ffb81c 000000",
                  "0173b7 f9b619", "006d75 000000", "002868 ffffff", "00205b ffffff", "00205b 046a38", "cf0a2c 041e41",
                  "96d8d8 001425", "b9975b 333f48")
NHL_COLOURS = tuple(tuple(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in pair.split()) for pair in NHL_COLOUR_HEX)
NHL_CITIES = {22: "Salt Lake, UT", 30: "Seattle, WA", 31: "Las Vegas, NV"}      # the cities the rosters still get wrong
NHL_LOOK = {slot: (NHL_ARENAS[slot], city) + NHL_COLOURS[slot] for slot, city in NHL_CITIES.items()}
# The AHL clubs' arenas by slot (name, city, capacity), as the clubs play now (docs/notes/equipment-accuracy.md section 5).
# The rosters name the buildings of the 2014 clubs of those slots (Utica's Comets in Albany, Laval's Rocket in St. John's).
# Left out because the roster is right: Charlotte, Grand Rapids, Hershey, Lehigh Valley, Wilkes-Barre/Scranton, and Manitoba,
# who share Winnipeg's row. Coachella Valley (234) and Henderson (235) borrow rows of other clubs and get their own;
# the Barracuda (54) leave the Sharks' row. Two of the names differ from the database's on purpose: Rosemont, not Chicago;
# Pechanga Arena for San Diego; Hamilton's TD Coliseum (the database holds a placeholder).
AHL_ARENAS = {
    32: ("Utica Memorial Auditorium", "Utica, NY", 4000),
    33: ("Dignity Health Arena", "Bakersfield, CA", 13399),
    34: ("CAA Arena", "Belleville, ON", 3257),
    35: ("TD Coliseum", "Hamilton, ON", 17383),
    37: ("Blue Arena", "Loveland, CO", 5289),
    39: ("PeoplesBank Arena", "Hartford, CT", 9801),
    41: ("Casey's Center", "Des Moines, IA", 8851),
    42: ("Rocket Mortgage FieldHouse", "Cleveland, OH", 17000),
    45: ("UW-Milwaukee Panther Arena", "Milwaukee, WI", 9652),
    46: ("Toyota Arena", "Ontario, CA", 9736),
    47: ("MassMutual Center", "Springfield, MA", 6679),
    48: ("Amica Mutual Pavilion", "Providence, RI", 14500),
    49: ("Blue Cross Arena at the War Memorial", "Rochester, NY", 11200),
    50: ("BMO Center", "Rockford, IL", 8500),
    51: ("Place Bell", "Laval, QC", 6250),
    52: ("Allstate Arena", "Rosemont, IL", 16692),
    53: ("Pechanga Arena San Diego", "San Diego, CA", 12920),
    54: ("Tech CU Arena", "San Jose, CA", 4200),
    55: ("Tucson Arena", "Tucson, AZ", 7440),
    56: ("Scotiabank Saddledome™", "Calgary, AB", 19289),
    57: ("Upstate Medical University Arena", "Syracuse, NY", 6230),
    58: ("H-E-B Center", "Cedar Park, TX", 6800),
    59: ("Coca-Cola Coliseum", "Toronto, ON", 8295),
    60: ("Rogers Forum", "Abbotsford, BC", 7000),
    234: ("Acrisure Arena", "Palm Desert, CA", 9918),
    235: ("Lee's Family Forum", "Henderson, NV", 9500),
}
AHL_ALONE = {234, 235}      # rows shared with a club or a copy that stays where it was (Colorado's AllState Arena, Seattle's copy)
VEES_ARENA = ("South Okanagan Events Centre", "Penticton, BC", 4494)
# their helmets, gloves and goalie gear (Builder.nhl_gear): a coloured part becomes the first colour here, a dark one the
# second; white and black stay (Utah: black, Seattle: deep sea blue, Vegas: gold and steel grey)
NHL_GEAR = {22: ((32, 32, 32), (32, 32, 32)), 30: ((0, 35, 63), (0, 35, 63)), 31: ((238, 192, 84), (60, 59, 65))}
# 0.10.0 to 0.20.0 took the equipment tables' team number for the slot (it is the slot + 1) and painted the teams before:
# Philadelphia (21) in Utah's colours, Washington (29) in Seattle's, Seattle (30) in Vegas's. Those colours go back.
GEAR_SLIPS = {21: 22, 29: 30, 30: 31}


class Builder:
    def __init__(self, R, data, progress=None, layout=L.COMMUNITY, stale=None):
        self.R = R
        self.data = data
        self.layout = layout
        self.mirrors = L.mirrors(layout)    # custom copies kept in step with their NHL team
        # copy -> its NHL team, by the roster's own layout: the game's own roster has no copies, and a player may fill
        # those slots with clubs of his own (a tester's KHL clubs in 222-227: real clubs, not Blues / Bruins ...)
        self.mirror_of = {m: p for p, ms in self.mirrors.items() for m in ms}
        # NHL teams and their copies in this roster (L.NHL_ALL is the community layout's: on the game's own roster
        # slots 222-233 are prospect pools, real places a player keeps when he leaves his NHL team)
        self.nhl_all = L.NHL_PRIMARY | set(self.mirror_of)
        # players who leave a team, or are free agents, at this age retire (their records become
        # spare) unless they played in the NHL last season: in the game's own roster from 30
        # (stock.RETIRE_AGE: its 2014 players), in a community roster from FA_RETIRE_AGE
        self.retire_age = FA_RETIRE_AGE if layout == L.COMMUNITY else stock_retire_age()
        # records still in the game's year - 1900 (donors.real_birth_year): only community rosters have them (`stale` False:
        # none left, a roster made for the game patch)
        self.stale_years = layout == L.COMMUNITY if stale is None else stale
        self.progress = progress or (lambda msg: None)
        self.money = pay.GAME   # the scale of the roster's dollars (contracts.scale_of; pipeline.build sets it)
        self.U, self.P, self.C, self.Q = R.U, R.P, R.C, R.Q
        U = self.U
        self.flags = [n for n, f in U.fields.items() if f.bits == 1 and n != 'jZSh']
        self.log = ChangeLog()
        self.deleted = set()
        self.left_keys = set()  # people who left the NHL and are no longer active
        self.created = set()    # repurposed records (their old contract data is junk)
        self.arrivals = {}      # team -> [entry]
        self.departures = {}    # team -> [(pos_class, frozenset(flags), quality)]
        # player links (exhibitionplayers): new ones take the lowest free number; ids from 16000 up
        # are the game's own special links and are never handed out
        # (the link of a leftover entry taken off by drop_removed_player() is not handed out again)
        self.link_ids = {self.C.get(i, 'qEfv') for i in range(self.C.cur_rec)} | getattr(R, 'kept_links', set())
        self.free_links = (k for k in range(LINK_LIMIT) if k not in self.link_ids)
        self.link_row = {self.C.get(i, 'qEfv'): i for i in range(self.C.cur_rec)}
        # a Create Player record's own link (table 1, number = his game id): the game lists such a player only
        # through it, and a new career copies his created look only then (lab round 45: an ordinary link, a blue head)
        self.own_links = {self.C.get(i, 'qFky'): self.C.get(i, 'qEfv') for i in range(self.C.cur_rec)
                          if self.C.get(i, 'BERR') == 1 and self.C.get(i, 'qEfv') == self.C.get(i, 'qFky') >= LINK_LIMIT}
        self.dead_links = []    # (row, link) of retired players' links, handed out again before new ones
        self.fa_links = [self.Q.get(i, 'TWSX') for i in range(self.Q.cur_rec)]
        self.unlist_club_players()
        self.ovr = {}           # pid -> the list's overall (filled by apply_list_ratings)
        self.api = []
        self.api_rows = set()
        self.api_country = {}
        self.attached = set()   # pids given a new roster entry in this run
        self.league_stats = {}  # club league -> what its step did
        self.filled_now = set() # national teams filled from scratch in this run
        self.joined_depth = {}  # player row -> the NHL slot he joined as depth NHL.com does not list (call_ups)
        self.placed = set()     # pids a club league has placed in this run (the first league to list him keeps him)
        # row -> (position, club slot, team code, log section): a league's position for a player still on a national team,
        # put in after the national step if he is off it then (clubs.late_positions: else a second run would do it)
        self.later_positions = {}
        self.core_reserve = Counter()   # records kept back for the line-ups of leagues still to come ('G', 'S')
        self.held_records = {}          # position -> records taken for the player's own new players (hold_records)
        self.list_rated = set()   # pids whose attributes the ratings list set in this run (never estimated over)
        # the full ratings (rate_full): first, before the ratings list and the estimate
        self.full_ratings = ratings.full_index(data.ratings_full) if data.ratings_full else None
        self.full_rated = set()    # pids the full ratings were written for in this run
        self.real_gear = None      # (first, last) -> [(birth, entry)] of the real equipment (real_equipment), made when first needed
        self.full_quality = {}     # pid -> the full ratings' overall on the level scale (ratings.overall_level)
        self.rated_by = {}          # pid -> where this run took his ratings from: 'full', 'list', 'estimate'
        self.full_dates = 0        # records given the full ratings' birthdate (the DEL gives only an age)
        # the club leagues that give only an age (DEL): (first, last) -> the birth year the feed's record has
        approx = {}
        for league in data.leagues.values():
            for t in league.get('teams') or []:
                for p in t['players']:
                    if p.get('birth_approx'):
                        approx.setdefault((norm(p['first']), norm(p['last'])), set()).add(p['birth'][0])
        self.approx_birth = {k: next(iter(v)) for k, v in approx.items() if len(v) == 1}
        self.pool_released = 0  # prospect-pool players who found no room and became free agents
        self.positions_changed = 0  # NHL players given NHL.com's position
        self.position_teams = set() # the teams of those players: their kept lines are checked and dealt again
        self.called_up = []         # (team, player row) brought in so a team can dress 20 (repair_lineups)
        self.rebuilt_clubs = {}     # club slot -> its league's key, for the clubs a league step rebuilt (update_league)
        self.feed_letters = {}      # club slot -> {entry: 'C' / 'A'} the league's own list gives (update_league)
        self.lettered = set()       # teams given this season's captains (real_letters)
        self.national_lettered = set()  # national teams given their captains by the players' own (national_letters)
        self.photos = {}        # player row -> photo link, for the players placed in this run
        self.logos = {}         # team slot -> logo link
        self.own_photos = set()     # player rows whose photo is the player's own picture (edits.py)
        self.own_logos = set()      # team slots whose logo is the player's own picture (edits.py)
        self.bad_pictures = {}      # photo link -> why it cannot be made (portraits.plan): those players keep theirs
        self.looks_edits = {}   # team slot -> the player's own jerseys / centre-ice logo (edits.py)
        self.crest_pictures = {}    # custom team slot -> its own crest picture ('file:...', edits.py kit; art/crests.py)
        self.team_names = {}    # team slot -> True: the player renamed it in the Roster editor
        self.nhl_names = {t: R.team_name(t) for t in range(32)}     # as the source has them
        # rating rows never move: player id -> row in the skater / goalie attribute table
        self.ai_row = {tn: {R.f[tn].get(i, 'zIBw'): i for i in range(R.f[tn].cur_rec)} for tn in ('yvSd', 'yuHm')}
        # The list's overalls run slightly above (skaters) or below (goalies) the plain attribute mean
        self.ovr_offset = ratings.overall_offset(data.ratings_list) if data.ratings_list else {False: 0.0, True: 0.0}
        self._ratings()
        # the most common playing style of defencemen and of forwards (for a skater who changes between them)
        styles = {'D': Counter(), 'F': Counter()}
        S = R.f['yvSd']
        for i in range(S.cur_rec):
            prow = R.p_by_id.get(S.get(i, 'zIBw'))
            if prow is not None and self.P.get(prow, 'aljv') < 4:
                styles['D' if self.P.get(prow, 'aljv') == 3 else 'F'][S.get(i, 'sFgQ')] += 1
        self.usual_style = {k: (c.most_common(1)[0][0] if c else (4 if k == 'D' else 9)) for k, c in styles.items()}
        # the source already has the national teams the base left empty: it was made by this tool,
        # so a second run only maintains what is there instead of rebuilding it
        self.maintain = all(any(U.get(i, 'BSXd') == t for i in range(U.cur_rec)) for t in L.EMPTY_NATIONAL.values())
        self.depth = {goalie: self._depth_level(goalie) for goalie in (False, True)}
        self.records_of = {}    # identity -> records (one person can have two: national-team goalies)
        for r in range(self.P.cur_rec):
            self.records_of.setdefault(self.identity(r), []).append(r)
        # who played in the NHL last season (never retired; the unsigned ones are free agents)
        self.last_season_people = match(R, [dict(p, birth=tuple(p['birth'])) for p in data.nhl_last])
        self.gone_people = self.retired_people(data)
        self.last_season_people = [p for p in self.last_season_people if id(p) not in self.gone_people]
        self.last_season = {self.P.get(p['row'], 'zIBw') for p in self.last_season_people if p['row'] is not None}
        # who retired although he played last season (retired_people): retires like an old free agent, whatever his age
        self.gone = {self.P.get(p['row'], 'zIBw') for p in self.gone_people.values() if p['row'] is not None}
        self.gone |= {self.P.get(p['row'], 'zIBw') for p in match(R, [dict(p, birth=tuple(p['birth'])) for p in data.retired])
                      if p['row'] is not None and self.P.get(p['row'], 'zIBw') not in self.last_season}
        self.listed_rows = set()    # records the club leagues list (reserve_listed): never retired
        self.league_rows = set()    # of them, the ones a club league lists (not an IIHF squad)
        self.league_names = set()   # (first, last) of everyone a club league lists, matched to a record or not
        self.api_pids = set()       # pids on the NHL.com rosters (nhl_rosters)
        self.under_contract = set() # pids with an NHL contract for 2026-27 (contract_keeps): never retired
        self.contract_org = {}      # pid -> the NHL slot holding his deal, for the ones no list names (farm_contract)
        self.contract_kept = {}     # pid -> the NHL slot that keeps him under contract (contract_keeps)
        self.contract_full = set()  # pids under contract whom a full NHL roster turned away (contract_keeps)
        self.national_gaps = {}     # national team -> position groups of members who retired
        self.rebuild_national = False   # the NHL step first empties the national teams (clear_national)
        self.donors = Donors(self)
        self.donors.reserve(data.nhl_last)      # not for reuse, even when on no team in the save
        self.orig_club = self.club_teams()
        self.orig_clubs = self.club_teams(pay.contract_clubs(R))       # every league's (starter_contracts)
        self.orig_home = self.home_teams()
        # each player's deal as the source holds it (the list of changes counts the deals that differ at the end)
        self.orig_deals = {self.P.get(r, 'zIBw'): tuple(self.P.get(r, f) for f in pay.FIELDS) for r in range(self.P.cur_rec)}
        # each team's original line structure: (class, slot set) of its dressed players, best first.
        # The class is the one the slots are for (a centre on a wing's line slot leaves a wing's set)
        self.orig_slot_sets = {}
        for i in range(U.cur_rec):
            if self.held(i):
                role = lines.slot_role(self.held(i)) or self.cls(i)
                self.orig_slot_sets.setdefault(U.get(i, 'BSXd'), []).append((role, self.held(i), self.q(i)))
        for sets in self.orig_slot_sets.values():
            sets.sort(key=lambda s: (-len(s[1]), -s[2]))
        # contracts that already point at a team the player is not on (left alone, as in the original)
        on = {}
        for i in range(U.cur_rec):
            on.setdefault(self.pid_of_entry(i), set()).add(U.get(i, 'BSXd'))
        self.orig_contract_bad = {
            pid for pid, prow in R.p_by_id.items()
            if self.P.get(prow, 'BSXd') and not self.same_team(self.P.get(prow, 'BSXd') - 1) & on.get(pid, set())}

    # --- helpers ----------------------------------------------------------
    def home_teams(self):
        """pid -> the club a player plays for (his lowest team that is no national team, NHL copy or
        event team), for players who have one."""
        U, out = self.U, {}
        for i in range(U.cur_rec):
            t = U.get(i, 'BSXd')
            if i in self.deleted or t in L.NATIONAL or t in self.mirror_of or t in L.EVENTS:
                continue
            pid = self.pid_of_entry(i)
            out[pid] = min(out.get(pid, t), t)
        return out

    def club_teams(self, clubs=L.CLUB):
        """pid -> set of club teams (NHL, AHL; `clubs`: other teams) the player has a roster entry on."""
        U, out = self.U, {}
        for i in range(U.cur_rec):
            t = U.get(i, 'BSXd')
            if i not in self.deleted and t in clubs:
                out.setdefault(self.pid_of_entry(i), set()).add(t)
        return out

    def active_fields(self, tname):
        """The attribute fields that make up a player's level."""
        return ratings.attribute_fields(self.R.f[tname])

    def _ratings(self):
        """Quality on the overall-rating scale: the list's overall when known, otherwise the mean of the
        player's attributes shifted onto that scale."""
        self.quality = {}
        for tname in ('yvSd', 'yuHm'):
            t = self.R.f[tname]
            act = self.active_fields(tname)
            k = self.ovr_offset[tname == 'yuHm']
            for i in range(t.cur_rec):
                self.quality[t.get(i, 'zIBw')] = sum(t.get(i, n) for n in act) / len(act) + 36 + k
        self.quality.update(self.ovr)
        self.quality.update(getattr(self, 'full_quality', {}))

    def player_style(self, pid):
        """A roster entry carries the same playerstyle as the player's attribute record."""
        for tname in ('yvSd', 'yuHm'):
            row = self.ai_row[tname].get(pid)
            if row is not None:
                return self.R.f[tname].get(row, 'sFgQ')
        return 1

    def pid_of_entry(self, e):
        return self.R.link_to_pid.get(self.U.get(e, 'TWSX'))

    def equipment_row(self, prow, kind='skater'):
        """The row of a player's equipment (`kind` skater or goalie), or None."""
        from . import equipment
        table = self.R.f[equipment.KINDS[kind][0]]
        cache = self.__dict__.setdefault('_equipment_rows', {})
        if cache.get(kind, (None,))[0] != table.cur_rec:     # new players add rows
            cache[kind] = (table.cur_rec, equipment.row_of(table, kind))
        return cache[kind][1].get(self.P.get(prow, 'zIBw'))

    def prow_of_entry(self, e):
        return self.R.p_by_id.get(self.pid_of_entry(e))

    def q(self, e):
        return self.quality.get(self.pid_of_entry(e), 0)

    def cls(self, e):
        return L.POS_CLASS[self.P.get(self.prow_of_entry(e), 'aljv')]

    def held(self, e):
        return frozenset(f for f in self.flags if self.U.get(e, f))

    def entries_on(self, team):
        U = self.U
        return [i for i in range(U.cur_rec) if i not in self.deleted and U.get(i, 'BSXd') == team]

    def person(self, prow):
        """Identity across duplicate records (national-team goalies have their own records)."""
        return (norm(self.P.get(prow, 'PedH')), norm(self.P.get(prow, 'RMbQ')))

    def identity(self, prow):
        """Name and birthdate: two records with the same identity are one real person."""
        P = self.P
        return self.person(prow) + (P.get(prow, 'dnFq'), P.get(prow, 'pLKJ'), P.get(prow, 'iwsK'))

    def depart(self, e):
        """Record the line slots entry `e` leaves behind on its current team."""
        team = self.U.get(e, 'BSXd')
        self.departures.setdefault(team, []).append((self.cls(e), self.held(e), self.q(e), self.U.get(e, 'lcCm')))

    def clear_lines(self, e):
        for f in self.flags + ['jZSh']:
            self.U.set(e, f, 0)
        self.U.set(e, 'lcCm', 0)

    def move_entry(self, e, team):
        self.depart(e)
        self.clear_lines(e)
        self.U.set(e, 'BSXd', team)
        self.arrivals.setdefault(team, []).append(e)

    def new_entry(self, team, link, prow):
        U = self.U
        e = U.add_record()
        for f in U.fields:
            U.set(e, f, 0)
        U.set(e, 'BSXd', team)
        U.set(e, 'TWSX', link)
        U.set(e, 'XWot', L.XWOT_UNSET)  # real id assigned by renumber_entries()
        U.set(e, 'tRVs', self.P.get(prow, 'tRVs'))
        pid = self.P.get(prow, 'zIBw')
        U.set(e, 'sFgQ', self.player_style(pid))
        self.attached.add(pid)
        return e

    def new_link(self, pid):
        if pid in self.own_links:   # a Create Player record keeps the game's own link
            return self.own_links[pid]
        if self.dead_links:     # a retired player's link: the row is taken over in place
            row, link = heapq.heappop(self.dead_links)
            self.C.set(row, 'BERR', 0)
            self.C.set(row, 'qFky', pid)
            self.R.link_to_pid[link] = pid
            return link
        link = next(self.free_links)
        self.link_ids.add(link)
        self.link_row[link] = self.C.add_record({'BERR': 0, 'qEfv': link, 'qFky': pid})
        self.R.link_to_pid[link] = pid
        return link

    def unlist_club_players(self):
        """Take players who are on a club team (not a national team, a copy of an NHL team or an event team) off the
        free-agent list. The game itself can save one on both (a tester's roster: Joe Sakic on Colorado and on the list);
        contracts() would clear the deal of everyone listed, so his club keeps him and his deal as the game saved it.
        Run again at the start of contracts(): a step that left someone on both (0.95.0 on the game's own roster: Nick
        Jensen left Anaheim for the list and kept his prospect pool place) mends here instead of failing verify."""
        R, U = self.R, self.U
        club = {}
        for i in range(U.cur_rec):
            if i in self.deleted:
                continue
            t = U.get(i, 'BSXd')
            if t not in L.NATIONAL and t not in self.mirror_of and t not in L.EVENTS:
                club.setdefault(R.link_to_pid.get(U.get(i, 'TWSX')), set()).add(t)
        for link in [l for l in self.fa_links if R.link_to_pid.get(l) in club]:
            pid = R.link_to_pid[link]
            self.drop_fa(pid)
            prow = R.p_by_id.get(pid)
            if prow is not None:
                team = min(club[pid])
                section, self.log.section = self.log.section, FREE_AGENTS
                self.log.append(['FA', 'taken off the free-agent list', R.name(prow), f"plays for {R.team_name(team)}", ''])
                self.log.section = section

    def drop_fa(self, pid):
        self.fa_links = [l for l in self.fa_links if self.R.link_to_pid.get(l) != pid]

    def live_entries(self):
        """pid -> the roster entries he has right now (deleted ones left out)."""
        U, live = self.U, {}
        for e in range(U.cur_rec):
            if e not in self.deleted:
                live.setdefault(self.pid_of_entry(e), []).append(e)
        return live

    def release(self, e, live):
        """Take entry `e` off its team. A player left on no club team (a national team does not
        count) goes onto the free-agent list: he stays in the game and can be signed, and his
        record is never reused for someone else. `live` (see live_entries) is kept up to date.
        Returns True when he became a free agent."""
        pid = self.pid_of_entry(e)
        self.depart(e)
        self.deleted.add(e)
        rest = [x for x in live.get(pid, []) if x != e]
        live[pid] = rest
        if any(self.U.get(x, 'BSXd') not in L.NATIONAL for x in rest):
            return False
        if len(self.records_of.get(self.identity(self.R.p_by_id[pid]), ())) > 1:
            return False        # a second record of someone the game has elsewhere (national-team goalies)
        if not any(self.R.link_to_pid.get(l) == pid for l in self.fa_links):
            self.fa_links.append(self.U.get(e, 'TWSX'))
        return True

    def retired_people(self, data):
        """{id(entry): entry} of last season's players (last_season_people) who retired: unsigned now and on the
        data pack's list (`retired`) or UNSIGNED_RETIRE_AGE or older (Kopitar, Toews, Quick; Nyquist at 37 stays a
        free agent)."""
        listed = {(norm(p['first']), norm(p['last']), tuple(p['birth'])) for p in data.retired}
        return {id(p): p for p in self.last_season_people if not p.get('team')
                and ((norm(p['first']), norm(p['last']), tuple(p['birth'])) in listed
                     or p['birth'][0] <= data.season_year - UNSIGNED_RETIRE_AGE)}

    def would_retire(self, pid):
        """Is this player old enough to retire (retire_age) and nobody's player any more? Not when
        he played in the NHL last season (an unsigned veteran is a free agent: Reimer), is on an
        NHL.com roster, is listed by a club league, or was placed in this run. Someone who retired
        (gone: the data pack's list, or unsigned at UNSIGNED_RETIRE_AGE) retires whatever his age."""
        prow = self.R.p_by_id.get(pid)
        if prow is None or pid in self.last_season or pid in self.api_pids or prow in self.listed_rows                 or pid in self.under_contract:
            return False
        if pid in self.gone:
            return pid not in self.attached
        return real_birth_year(self.P, prow, self.stale_years) <= self.data.season_year - self.retire_age and pid not in self.attached

    def retires(self, pid, force=False):
        """A player who has left his team (or is a free agent), is on no club team any more and
        would_retire() retires instead of staying a free agent (`force`: whatever his age, make_room). His record is cleared of its
        contract and NHL rights and becomes a spare record for a new player; his places on national
        teams are freed (national_teams() fills them). False for everyone else. Only
        settle_free_agents(), the NHL step and stock.retire_leftovers() retire players: all run
        before any new player is made, so a second run finds no spare record the first did not."""
        ents = [x for x in self.R.entries_by_pid.get(pid, []) if x not in self.deleted]
        copies = [x for x in ents if self.U.get(x, 'BSXd') in self.mirror_of]
        ents = [x for x in ents if x not in copies]
        if any(self.U.get(x, 'BSXd') not in L.NATIONAL for x in ents) or not (force or self.would_retire(pid)):
            return False
        prow = self.R.p_by_id[pid]
        for e in copies:        # places on the custom copies of his NHL team go with it (sync_mirrors)
            self.deleted.add(e)
        for e in ents:          # national teams: a 2014 squad of the game's own roster (Datsyuk, Price)
            team = self.U.get(e, 'BSXd')
            self.depart(e)
            self.deleted.add(e)
            self.national_gaps.setdefault(team, []).append({3: 'D', 4: 'G'}.get(self.P.get(prow, 'aljv'), 'F'))
            self.log.append([self.R.T.get(team, 'RPbr'), 'national team: removed', self.R.name(prow), 'retired',
                             self.U.get(e, 'tRVs')])
        for f in ('BSXd', 'GDhI', 'dhKk', 'IrlK', 'IzRv', 'WBbd'):
            self.P.set(prow, f, 0)
        self.fa_links = [l for l in self.fa_links if self.R.link_to_pid.get(l) != pid]
        self.donors.add_spare(prow)
        if getattr(self, '_pick_links', None) is None:
            picks = self.R.f['vaHq']
            self._pick_links = {picks.get(i, 'TWSX') for i in range(picks.cur_rec)}
        dropped = getattr(self, 'old_fa_links', set())      # links relink_free_agents() dropped are never handed out again
        for link in self.R.pid_to_links.get(pid, []):      # his links are free for new players now
            if link < LINK_LIMIT and link not in self._pick_links and link in self.link_row and link not in dropped:
                heapq.heappush(self.dead_links, (self.link_row[link], link))
        return True

    # --- creating players that are not in the file -------------------------
    def _depth_level(self, goalie):
        """Quality of a typical depth NHL player (30th percentile of the source's NHL rosters)."""
        R, U = self.R, self.U
        vals = sorted(self.quality[pid] for pid in
                      {R.link_to_pid[U.get(i, 'TWSX')] for i in range(U.cur_rec) if U.get(i, 'BSXd') in L.NHL_PRIMARY}
                      if pid in self.quality and (self.P.get(R.p_by_id[pid], 'aljv') == 4) == goalie)
        return vals[int(len(vals) * 0.3)] if vals else 70

    def set_text(self, prow, field, text):
        """Write a name, shortened to what the field can hold (the limit is in UTF-8 bytes)."""
        limit = self.P.field(field).bits // 8 - 1
        while len(text.encode('utf-8')) > limit:
            text = text[:-1]
        self.P.set(prow, field, text)

    def take_record(self, pos, who, target=None, required=True):
        """A player record for someone who is not in the save yet (see donors.py). When none is
        left: an error, or None if the caller can do without (`required=False`)."""
        prow = self.donors.take(pos, target)
        if prow is None and required:
            prow = self.make_room(pos, who, target)
        if prow is None:
            if not required:
                return None
            raise RuntimeError(f"no spare player record left for {who}")
        self.created.add(prow)
        pid = self.P.get(prow, 'zIBw')      # the previous owner's overall and ratings source are not the new player's
        self.ovr.pop(pid, None)
        self.full_quality.pop(pid, None)
        self.rated_by.pop(pid, None)
        self.full_rated.discard(pid)
        if pos != 4:        # the record's last wearer's tucks, tape and visor go: a new player starts with Edit Pro's plain choices
            from . import equipment
            row = self.equipment_row(prow)
            if row is not None:
                table = self.R.f[equipment.TABLE]
                equipment.write(table, row, equipment.clean(equipment.NEW_PLAYER, table)[0])
        return prow

    def make_room(self, pos, who, target=None):
        """No record is left for a player who must be in the game (on an NHL.com roster or an IIHF squad): a full update
        gives every spare record to the club leagues, so the next update's newcomers find none (a tester's Owen Michaels,
        Edmonton, 2026-10-23). The free agent the game needs least retires and his record is taken: the oldest, then the
        lowest rated (donors' order), never one who played in the NHL last season, is under contract, holds NHL rights, is
        listed by this run's data, plays for a national team, is a legend or younger than donors.MIN_AGE. When none fits
        (goalies: most free agents in goal are drafted prospects), a junior club's lowest-rated player whom it can do
        without (it keeps 2 goalies and 18 skaters, no NHL rights, on no other team) leaves the game, as the CHL step
        itself leaves depth players out when records run short. A second run needs no room: it finds the newcomer, and
        the CHL step misses the junior as before. None when nobody fits."""
        R, P = self.R, self.P
        live = self.live_entries()
        fits = []
        for link in self.fa_links:
            pid = R.link_to_pid.get(link)
            prow = R.p_by_id.get(pid)
            if (prow is None or (P.get(prow, 'aljv') == 4) != (pos == 4) or prow in self.created
                    or pid in self.last_season or pid in self.api_pids or prow in self.listed_rows
                    or pid in self.under_contract or pid in self.attached or pid in RESERVED
                    or any(e not in self.deleted for e in live.get(pid, []))     # also on no national team
                    or not self.donors._spare_ok(prow) or self.person(prow) in self.donors.reserved):
                continue
            fits.append(prow)
        for prow in sorted(fits, key=self.donors._order):
            name, age = R.name(prow), self.data.season_year - real_birth_year(P, prow, self.stale_years)
            if not self.retires(P.get(prow, 'zIBw'), force=True):
                continue
            section, self.log.section = self.log.section, FREE_AGENTS
            self.log.append(['FA', 'free agent retired', name, f"{age}, to make room for {who}", ''])
            self.log.section = section
            return self.donors.take(pos, target)
        goalie = lambda prow: P.get(prow, 'aljv') == 4
        kept = Counter()                # (junior club, goalie?) -> players on it
        for pid, ents in live.items():
            for e in ents:
                if self.U.get(e, 'BSXd') in L.CHL:
                    kept[(self.U.get(e, 'BSXd'), goalie(R.p_by_id[pid]))] += 1
        fits = []
        for pid, ents in live.items():
            prow = R.p_by_id.get(pid)
            if (prow is None or len(ents) != 1 or goalie(prow) != (pos == 4) or prow in self.created
                    or pid in self.api_pids or pid in self.under_contract or pid in self.attached or pid in RESERVED
                    or P.get(prow, 'WBbd') or len(self.records_of[self.identity(prow)]) != 1):
                continue
            team = self.U.get(ents[0], 'BSXd')
            if team in L.CHL and kept[(team, pos == 4)] > (2 if pos == 4 else 18):
                fits.append((self.quality.get(pid, 0), prow, ents[0]))
        if not fits:
            return None
        _quality, prow, e = min(fits)
        team, name, number = self.U.get(e, 'BSXd'), R.name(prow), self.U.get(e, 'tRVs')
        self.depart(e)
        self.deleted.add(e)
        self.retires(P.get(prow, 'zIBw'), force=True)
        spare = self.donors.spare[P.get(prow, 'aljv')]
        if prow in spare:
            spare.remove(prow)
        if pos != 4 and P.get(prow, 'aljv') != pos:
            self.set_position(prow, pos)
        from .pipeline import LEAGUE_NAMES
        section, self.log.section = self.log.section, LEAGUE_NAMES['chl']
        self.log.append([R.T.get(team, 'RPbr'), 'left to make room', name, f"for {who} (no free player record)", number])
        self.log.section = section
        return prow

    def hold_records(self, counts):
        """Take records for the player's own new players before anyone else ({position code: count},
        edits.records_needed): the leagues' players, matched or new, then use the rest, and edits._create gives these
        out. Held while records last; returns how many."""
        held = 0
        for pos in sorted(counts):
            for _ in range(counts[pos]):
                prow = self.take_record(pos, 'a new player of your own', required=False)
                if prow is None:
                    break
                self.held_records.setdefault(pos, []).append(prow)
                held += 1
        return held

    def create_player(self, p, required=True):
        P = self.P
        pos = L.POS_CODE[p['pos']]
        name = f"{p['first']} {p['last']}"
        prow = self.take_record(pos, name, target=self.depth[pos == 4], required=required)
        if prow is None:
            return None
        old = self.R.name(prow)
        y, m, d = p['birth']
        self.donors.reset_identity(prow, name, L.NAT_CODE.get(p.get('country')), y)
        self.set_text(prow, 'PedH', p['first'])
        self.set_text(prow, 'RMbQ', p['last'])
        if p.get('city'):
            self.set_text(prow, 'JzFM', p['city'])
        P.set(prow, 'iwsK', d - 1)
        P.set(prow, 'pLKJ', m - 1)
        P.set(prow, 'dnFq', y - 1910)
        self.nhl_bio(prow, p)
        if p.get('num'):
            P.set(prow, 'tRVs', p['num'])
        self.log.append([p['team'], 'created', name, f"reused record of {old}", p.get('num') or ''])
        return prow

    def nhl_bio(self, prow, p):
        """NHL.com's height, weight, hand and birthplace, for every NHL player (not only new ones:
        the game's own roster has 2014's)."""
        P = self.P
        if p.get('height_in'):
            P.set(prow, 'QBpy', max(0, min(31, p['height_in'] - 54)))
        if p.get('weight_lb'):
            P.set(prow, 'WZNs', max(0, min(255, p['weight_lb'] - 120)))
        if p.get('shoots') in ('L', 'R'):
            P.set(prow, 'pkRG', 0 if p['shoots'] == 'L' else 1)
        if p.get('city'):
            self.set_text(prow, 'JzFM', p['city'])

    def former_photos(self):
        """Players on a team or the free-agent list whom no list gave a photo get last season's, from
        the leagues' `former` lists (name and birthdate): a junior the list leaves out stays with his
        club and keeps a picture (Landon DuPont, testers 0.8.0)."""
        index = {}
        for league in self.data.leagues.values():
            for p in league.get('former') or []:
                index.setdefault((norm(p['first']), norm(p['last']), tuple(p['birth'])), p['photo'])
        if not index:
            return 0
        P, R = self.P, self.R
        fa = {R.link_to_pid.get(l) for l in self.fa_links}
        live = self.live_entries()
        added = 0
        for prow in range(P.cur_rec):
            pid = P.get(prow, 'zIBw')
            if prow in self.photos or not (live.get(pid) or pid in fa):
                continue
            key = (norm(P.get(prow, 'PedH')), norm(P.get(prow, 'RMbQ')),
                   (P.get(prow, 'dnFq') + 1910, P.get(prow, 'pLKJ') + 1, P.get(prow, 'iwsK') + 1))
            if key in index:
                self.photos[prow] = index[key]
                added += 1
        return added

    # --- free agents --------------------------------------------------------------
    def reserve_listed(self, leagues):
        """The players the club leagues list (`leagues`: {step: league} as they will be built) and the
        IIHF's national squads: their records are never reused or retired, even before their league
        or national team places them."""
        from .leagues import clubs
        from .matching import match_club
        people = [p for league in leagues.values() for p in clubs.listed(league['teams'])]
        self.donors.reserve(people)
        match_club(self.R, people)
        squads = [dict(p, birth=tuple(p['birth'])) for players in (self.data.iihf or {}).values() for p in players]
        self.donors.reserve(squads)
        match(self.R, squads)
        self.listed_rows = {p['row'] for p in people + squads if p['row'] is not None}
        self.league_rows = {p['row'] for p in people if p['row'] is not None}      # a league places these
        self.league_names = {(norm(p['first']), norm(p['last'])) for p in people}

    def settle_free_agents(self):
        """Free agents who would_retire() retire: off the list, their records spare (Rask, Getzlaf,
        Price, who last played in 2022). Runs before any player is made (see retires())."""
        R = self.R
        section, self.log.section = self.log.section, FREE_AGENTS
        for link in list(self.fa_links):
            pid = R.link_to_pid.get(link)
            prow = R.p_by_id.get(pid)
            if prow is None or link not in self.fa_links:
                continue
            age = self.data.season_year - real_birth_year(self.P, prow, self.stale_years)
            if self.retires(pid):
                why = 'retired after last season' if pid in self.gone else 'not in the NHL last season'
                self.log.append(['FA', 'free agent retired', R.name(prow), f"{age}, {why}", ''])
        self.log.section = section

    def add_unsigned(self):
        """Everyone who played in the NHL last season and is unsigned now is a free agent: the ones
        the save has get onto the list, the others are created (owner, 2026-10-04: all of them)."""
        R, P = self.R, self.P
        section, self.log.section = self.log.section, FREE_AGENTS
        on_rosters = {p.get('nhl_id') for p in self.api if p.get('nhl_id')}
        live = self.live_entries()
        fa = {R.link_to_pid.get(l) for l in self.fa_links}
        added = created = 0
        for p in sorted(self.last_season_people, key=lambda p: p['nhl_id'] or 0):
            if p.get('team') or p.get('nhl_id') in on_rosters:
                continue
            name = f"{p['first']} {p['last']}"
            row = p['row']
            if row is not None:
                pid = P.get(row, 'zIBw')
                if pid in fa or pid in self.api_pids or any(e not in self.deleted for e in live.get(pid, [])):
                    continue                    # a free agent already, or with a club in the save
                detail = 'unsigned, in the NHL last season'
                added += 1
            else:
                row = self.create_player(dict(p, team='FA', num=None, birth=tuple(p['birth'])), required=False)
                if row is None:
                    self.log.append(['FA', 'skipped', name, 'no free player record left', ''])
                    continue
                pid = P.get(row, 'zIBw')
                detail = 'unsigned, in the NHL last season: new to the game'
                created += 1
            self.fa_links.append(self.new_link(pid))
            fa.add(pid)
            if p.get('photo'):
                self.photos[row] = p['photo']
            self.log.append(['FA', 'free agent added', name, detail, ''])
        if added or created:
            self.log.append(['ALL', 'summary', 'unsigned NHL players made free agents', f"{added + created} "
                             f"({created} new to the game)", ''])
        self.log.section = section

    # --- NHL ------------------------------------------------------------------
    NHL_KEEP_ROOM = 30      # contract_keeps: an NHL team keeps players under contract while it holds fewer (NHL.com: 23-27)
    FARM_KEEP_ROOM = 34     # contract_strays: a farm club takes players under contract while it holds fewer (the game: 40)

    def contract_keeps(self, api):
        """Who stays with (or goes to) his NHL organisation because he holds an NHL contract for 2026-27 (data pack
        `contracts`; owner, 2026-10-16: "your choice"): {pid: NHL slot}. Only players whom NHL.com's rosters and the
        club leagues leave out (NHL.com's roster copy misses injured players: Larkin, Jarvis, Zucker, who became free
        agents) and who are on one NHL roster now and on no other club (the ones on no club at all: contract_strays, at
        the end of the update). NHL.com and the leagues win whenever they list him (a league by name: its own match may
        make a record of him). The ones on their organisation's roster stay (within the game's 40),
        the ones on another NHL roster move while it holds fewer than NHL_KEEP_ROOM; a second run finds the ones who
        moved there, and a team that turned one away full still. Also sets under_contract (never retired) and
        contract_full (turned away)."""
        if not self.data.contracts:
            return {}
        R, U, P = self.R, self.U, self.P
        held, listed = {}, set()
        for d in match(R, [dict(d, birth=tuple(d['birth'])) for d in self.data.contracts]):
            if d['row'] is not None and d['org'] in L.API_TO_SLOT:
                held.setdefault(P.get(d['row'], 'zIBw'), (d['row'], L.API_TO_SLOT[d['org']]))
                if (norm(d['first']), norm(d['last'])) in self.league_names:
                    listed.add(P.get(d['row'], 'zIBw'))
        self.under_contract = set(held)
        self.contract_org = {pid: org for pid, (prow, org) in held.items()
                             if pid not in self.api_pids and prow not in self.league_rows and pid not in listed}
        size = Counter(L.API_TO_SLOT[p['team']] for p in api)
        live = self.live_entries()
        stay, join = [], []
        for pid, (prow, org) in sorted(held.items()):
            if pid in self.api_pids or prow in self.league_rows or pid in listed:
                continue                        # a league lists him (by name: its own match may make a record of him)
            teams = {U.get(x, 'BSXd') for x in live.get(pid, [])} - L.NATIONAL - set(self.mirror_of)
            if len(teams) != 1 or teams - L.NHL_PRIMARY:
                continue
            (stay if teams == {org} else join).append((pid, org))
        keep, self.contract_full = {}, set()
        for group, room in ((stay, L.MAX_PER_TEAM), (join, self.NHL_KEEP_ROOM)):
            for pid, org in group:
                if size[org] < room:
                    keep[pid] = org
                    size[org] += 1
                else:
                    self.contract_full.add(pid)
        return keep

    def farm_contract(self, e, slot, parents):
        """Is entry `e` on AHL club `slot` a player under contract with its parent organisation (`parents`:
        clubs.affiliates) whom no list names? contract_strays puts such a player there; the AHL step lets him stay."""
        return parents.get(slot) is not None and self.contract_org.get(self.pid_of_entry(e)) == parents[slot]

    def contract_strays(self):
        """After the club leagues and the national teams: a player holds an NHL contract who is on no club now
        (a free agent: an earlier update made Larkin one; a prospect a league or pool let go; a player made for a
        national team) and whom neither NHL.com nor a club league lists goes to his organisation, in pid order: a
        two-way deal (a prospect: Stillman, Cavallin) to its farm club while that holds fewer than FARM_KEEP_ROOM, else
        to the NHL roster while that holds fewer than NHL_KEEP_ROOM; a one-way deal the other way round. The lines of
        each team that got players are dealt again (as the NHL step and the leagues do for a team that changed).
        Matched on the roster as it is now, so a second run finds them on their team and changes nothing. Returns how
        many joined."""
        if not self.data.contracts:
            return 0
        from .leagues.clubs import affiliates, _letters
        R, U, P = self.R, self.U, self.P
        farms = {nhl: ahl for ahl, nhl in affiliates(R).items() if R.T.get(ahl, 'NYKk')}
        live = self.live_entries()
        joined = {}
        seen = set()
        for d in sorted(match(R, [dict(d, birth=tuple(d['birth'])) for d in self.data.contracts]),
                        key=lambda d: (P.get(d['row'], 'zIBw') if d['row'] is not None else -1)):
            prow = d['row']
            if prow is None or d['org'] not in L.API_TO_SLOT:
                continue
            pid = P.get(prow, 'zIBw')
            if pid in seen:
                continue
            seen.add(pid)
            org = L.API_TO_SLOT[d['org']]
            if pid in self.api_pids or prow in self.league_rows or (norm(d['first']), norm(d['last'])) in self.league_names:
                continue
            if any(U.get(x, 'BSXd') not in L.NATIONAL and U.get(x, 'BSXd') not in self.mirror_of for x in live.get(pid, [])):
                continue
            places = [(farms.get(org), self.FARM_KEEP_ROOM), (org, self.NHL_KEEP_ROOM)]
            team = next((t for t, room in (places if d.get('two_way') else places[::-1])
                         if t is not None and len(self.entries_on(t)) < room), None)
            if team is None:
                self.contract_full.add(pid)
                continue
            fa = [l for l in self.fa_links if R.link_to_pid.get(l) == pid]
            taken = {U.get(x, 'tRVs') for x in self.entries_on(team)}
            e = self.new_entry(team, fa[0] if fa else self.new_link(pid), prow)
            U.set(e, 'tRVs', next(n for n in (P.get(prow, 'tRVs'), *range(2, 99)) if n and n not in taken))
            live.setdefault(pid, []).append(e)
            self.set_pro_team(prow, org)
            self.drop_fa(pid)
            joined[pid] = team
            where = f"from {'free agent' if fa else 'no club'}: under contract (2026-27)"
            if team == org:
                self.log.append([L.SLOT_TO_API[org], 'added', R.name(prow), where, U.get(e, 'tRVs')])
            else:
                self.log.append([R.T.get(team, 'nnsx'), 'farm under contract', R.name(prow),
                                 f"{where}, {L.SLOT_TO_API[org]}'s farm club", U.get(e, 'tRVs')])
        self.rate_by_name(set(joined))
        for team in sorted(set(joined.values())):
            if team not in L.NHL_PRIMARY:
                # a club its league rebuilt keeps the league's own letters only, the rest go by quality with the players
                # who came (as its league step deals them on the next run); another keeps the letters it has
                letters = self.feed_letters.get(team) if team in self.feed_letters else {
                    e: lines.LETTERS[U.get(e, 'lcCm')] for e in self.entries_on(team) if U.get(e, 'lcCm') in lines.LETTERS}
                try:
                    lines.build_lines(self, team)
                except lines.NotEnoughPlayers:
                    continue                    # it could not dress 20 before either: no lines, as the leagues leave it
                _letters(self, team, letters)
            elif team in self.orig_slot_sets:
                self.lines_by_template(team, self.orig_slot_sets[team])
            else:
                self.lines_from_scratch(team)
        if any(t in L.NHL_PRIMARY for t in joined.values()):
            self.lines_from_games({t for t in joined.values() if t in L.NHL_PRIMARY})
            self.sync_mirrors()
        self.contract_kept.update(joined)
        return len(joined)

    def searched_room(self, players):
        """NHL.com's roster lists plus the players its player search found for the save's NHL teams (datasource.
        find_missing: injured, or playing in the minors: the search names a farm player's NHL organisation, Coachella
        Valley's players 'SEA'). A searched player whom a club league lists plays there; the others join their team
        while it holds fewer than NHL_KEEP_ROOM (a tester's roster had Seattle's farm on Seattle: "Kraken has 49
        players"). The rest count as not on NHL.com's roster. Returns the players the NHL step places, in their order."""
        search = lambda p: p.get('source') == 'player search'
        size = Counter(p['team'] for p in players if not search(p))
        out, left = [], 0
        for p in players:
            if search(p):
                if (norm(p['first']), norm(p['last'])) in self.league_names or size[p['team']] >= self.NHL_KEEP_ROOM:
                    left += 1
                    continue
                size[p['team']] += 1
            out.append(p)
        if left:
            self.log.append(['ALL', 'summary', "players NHL.com's search puts with an NHL team who stay in the minors",
                             left, ''])
        return out

    def nhl_rosters(self):
        """Put every player of the official rosters on his team (steps 1-3 of the original)."""
        R, U = self.R, self.U
        self.nhl_listed = self.searched_room(self.data.nhl_players)
        api = match(R, [dict(p) for p in self.nhl_listed])
        self.api = api
        self.api_rows = {p['row'] for p in api if p['row'] is not None}
        self.api_country = {p['row']: p.get('country') for p in api if p['row'] is not None}
        api_pids = {self.P.get(p['row'], 'zIBw') for p in api if p['row'] is not None}
        self.api_pids = api_pids
        self.contract_kept = self.contract_keeps(api)
        keep = dict(self.contract_kept)
        target_entry = {}
        if self.rebuild_national:      # the game's own roster, first update (clear_national)
            self.clear_national()
        # 0. free agents who retired since: before anything else, so their records are spare now
        self.settle_free_agents()

        # 1. players leaving the NHL: remove their NHL entries, free agent unless still on another pro team
        for e in range(U.cur_rec):
            t = U.get(e, 'BSXd')
            if t in L.NHL_PRIMARY and self.pid_of_entry(e) not in api_pids:
                pid = self.pid_of_entry(e)
                org = keep.pop(pid, None)
                if org is not None:             # under contract for 2026-27, on no NHL.com roster: stays (contract_keeps)
                    name = R.name(R.p_by_id[pid])
                    self.set_pro_team(R.p_by_id[pid], org)
                    if org == t:
                        self.log.append([L.SLOT_TO_API[t], 'stays under contract', name,
                                         "under contract (2026-27), not on NHL.com's roster", U.get(e, 'tRVs')])
                    else:
                        self.move_entry(e, org)
                        self.log.append([L.SLOT_TO_API[org], 'moved', name,
                                         f"from {L.SLOT_TO_API[t]}: under contract (2026-27)", U.get(e, 'tRVs')])
                    continue
                self.depart(e)
                self.deleted.add(e)
                other = [x for x in R.entries_by_pid.get(pid, []) if x != e
                         and U.get(x, 'BSXd') not in self.nhl_all and U.get(x, 'BSXd') not in L.NATIONAL]
                status = 'free agent'
                if other:
                    status = 'stays with ' + R.team_name(U.get(other[0], 'BSXd'))
                elif self.retires(pid):
                    status = 'retired'
                elif U.get(e, 'TWSX') not in self.fa_links:
                    self.fa_links.append(U.get(e, 'TWSX'))
                if status == 'free agent' and pid in self.contract_full:
                    status += ' (under contract for 2026-27, no room)'
                self.log.append([L.SLOT_TO_API[t], 'left NHL roster', R.name(R.p_by_id[pid]), status, U.get(e, 'tRVs')])
                self.left_keys.add(self.person(R.p_by_id[pid]))

        # 1b. a player on a copy of an NHL team alone (a community roster whose copies are out of step: Kopitar on Los
        # Angeles' copy only) who is on no NHL.com roster and would retire, retires now, as step 1 retires the others;
        # sync_mirrors would list him as a free agent, and the next update's settle_free_agents retire him (0.95.1)
        on_primary = {self.pid_of_entry(e) for e in range(U.cur_rec) if e not in self.deleted
                      and U.get(e, 'BSXd') in L.NHL_PRIMARY}
        for e in range(U.cur_rec):
            t = U.get(e, 'BSXd')
            pid = self.pid_of_entry(e)
            if (e in self.deleted or t not in self.mirror_of or pid in api_pids or pid in on_primary
                    or pid not in R.p_by_id or pid in keep):
                continue
            if self.retires(pid):
                self.log.append([L.SLOT_TO_API[self.mirror_of[t]], 'left NHL roster', R.name(R.p_by_id[pid]), 'retired',
                                 U.get(e, 'tRVs')])
                self.left_keys.add(self.person(R.p_by_id[pid]))

        # 2. every player onto his team
        self.logos.update({L.API_TO_SLOT[a]: url for a, url in self.data.nhl_logos.items() if a in L.API_TO_SLOT})
        for p in api:
            target = L.API_TO_SLOT[p['team']]
            if p['row'] is None:
                prow = self.create_player(p)
                p['row'] = prow
                self.api_rows.add(prow)
                self.api_country[prow] = p.get('country')
                pid = self.P.get(prow, 'zIBw')
                e = self.new_entry(target, self.new_link(pid), prow)
                self.arrivals.setdefault(target, []).append(e)
                target_entry[e] = p
                self.set_pro_team(prow, target)
                continue
            self.set_pro_team(p['row'], target)
            self.nhl_position(p)
            self.nhl_birthdate(p)
            self.nhl_bio(p['row'], p)
            pid = self.P.get(p['row'], 'zIBw')
            ents = [x for x in R.entries_by_pid.get(pid, []) if x not in self.deleted]
            here = [x for x in ents if U.get(x, 'BSXd') == target]
            nhl = [x for x in ents if U.get(x, 'BSXd') in L.NHL_PRIMARY]
            if here:
                e = here[0]
            elif nhl:
                e = nhl[0]
                frm = L.SLOT_TO_API[U.get(e, 'BSXd')]
                self.move_entry(e, target)
                self.log.append([p['team'], 'moved', f"{p['first']} {p['last']}", f"from {frm}", p['num']])
            else:
                src = sorted((x for x in ents if U.get(x, 'BSXd') not in self.nhl_all | L.NATIONAL),
                             key=lambda x: source_rank(U.get(x, 'BSXd')))
                if src:
                    e = src[0]
                    frm = R.team_name(U.get(e, 'BSXd'))
                    self.move_entry(e, target)
                else:
                    fa = [l for l in self.fa_links if R.link_to_pid.get(l) == pid]
                    link = fa[0] if fa else self.new_link(pid)
                    e = self.new_entry(target, link, p['row'])
                    self.arrivals.setdefault(target, []).append(e)
                    frm = 'free agent' if fa else 'no team'
                self.log.append([p['team'], 'added', f"{p['first']} {p['last']}", f"from {frm}", p['num']])
            # his places on other NHL teams go (0.95.1: a community roster whose slot 31 was still an All-Star team
            # listed Toews on Colorado and on it; he stayed on both)
            for x in ents:
                t = U.get(x, 'BSXd')
                if x != e and x not in self.deleted and t in L.NHL_PRIMARY and t != target:
                    self.depart(x)
                    self.deleted.add(x)
                    self.log.append([L.SLOT_TO_API[t], 'left NHL roster', f"{p['first']} {p['last']}",
                                     f"plays for {p['team']}", U.get(x, 'tRVs')])
            self.drop_fa(pid)
            target_entry[e] = p
        for p in api:
            if p.get('photo') and p['row'] is not None:
                self.photos[p['row']] = p['photo']
        # 2b. last season's NHL players who are unsigned now: free agents
        self.add_unsigned()

        # 3. jersey numbers from the official rosters, resolving clashes
        for team in L.NHL_PRIMARY:
            ents = self.entries_on(team)
            taken = Counter()
            before = {e: U.get(e, 'tRVs') for e in ents}
            for e in ents:
                p = target_entry.get(e)
                if p and p['num']:
                    U.set(e, 'tRVs', p['num'])
                taken[U.get(e, 'tRVs')] += 1
            for n in [n for n, c in taken.items() if c > 1]:
                # the official number wins; between two official claims the one who already wears it
                # keeps it (so a second run, with ratings since written, changes nothing), else the
                # better player
                clash = sorted((e for e in ents if U.get(e, 'tRVs') == n),
                               key=lambda e: (bool(target_entry.get(e) and target_entry[e]['num'] == n),
                                              before[e] == n, self.q(e)),
                               reverse=True)
                for e in clash[1:]:
                    # the number he wore before, if nobody has it: a second run then changes nothing
                    free = before[e] if before[e] and taken[before[e]] == 0 else next(
                        x for x in range(2, 99) if taken[x] == 0)
                    taken[n] -= 1
                    taken[free] += 1
                    U.set(e, 'tRVs', free)
                    if free != before[e]:
                        self.log.append([L.SLOT_TO_API[team], 'number changed', R.name(self.prow_of_entry(e)),
                                         f"#{n} also used by {R.name(self.prow_of_entry(clash[0]))}", free])

    def nhl_position(self, p):
        """A player already in the save gets the position NHL.com lists him at (C, LW, RW, D): the
        community roster has some at another one (Cole Smith a left wing, Chicago one right wing
        short). Goalies and skaters never swap."""
        want = L.POS_CODE.get(p.get('pos'))
        cur = self.P.get(p['row'], 'aljv')
        if want is None or want == cur or 4 in (want, cur):
            return
        self.set_position(p['row'], want)
        self.positions_changed += 1
        # his new team and every team he is on now (national teams): their lines are dealt again (nhl_lines,
        # national_lines), or kept lines would count a defenceman who is now a winger among the 6 D
        pid = self.P.get(p['row'], 'zIBw')
        self.position_teams.add(L.API_TO_SLOT[p['team']])
        self.position_teams.update(self.U.get(x, 'BSXd') for x in self.R.entries_by_pid.get(pid, []) if x not in self.deleted)
        self.log.append([p['team'], 'position changed', f"{p['first']} {p['last']}",
                         f"{L.POS_NAME[cur]} to {L.POS_NAME[want]}", p['num']])

    def nhl_birthdate(self, p):
        """A player found by his name (not his birthdate) gets the birthdate NHL.com lists: the game's
        own roster has Kyle Burroughs a month off, and a league step would then not know him and
        make him a second record. National-team goalies' second records are left alone (their
        records must keep one birthdate)."""
        if p.get('how') == 'birth' or not p.get('birth'):
            return
        prow = p['row']
        if len(self.records_of.get(self.identity(prow), ())) > 1:
            return
        y, m, d = p['birth']
        if y - 1910 < 0:
            return
        before = self.identity(prow)
        self.P.set(prow, 'dnFq', y - 1910)
        self.P.set(prow, 'pLKJ', m - 1)
        self.P.set(prow, 'iwsK', d - 1)
        self.records_of.pop(before, None)
        self.records_of.setdefault(self.identity(prow), []).append(prow)

    def set_position(self, prow, pos):
        """Give a skater another skater position. Moving between forward and defence also moves his
        playing style into the new range (defence styles 1-4, forward styles 5-10), on his
        attribute record and on his roster entries."""
        P = self.P
        old = P.get(prow, 'aljv')
        if old == pos or 4 in (old, pos):
            return
        P.set(prow, 'aljv', pos)
        if (old == 3) != (pos == 3):        # the full ratings' type when it fits the new position (as the next run writes it)
            cls = 'D' if pos == 3 else 'F'
            self.set_style(prow, self.full_style(prow, cls) or self.usual_style[cls])

    def set_style(self, prow, style):
        """Give a player another playing style (player type), on his skater or goalie record and on every roster
        entry of his. False when he has no such record."""
        pid = self.P.get(prow, 'zIBw')
        for tname in ('yvSd', 'yuHm'):
            row = self.ai_row[tname].get(pid)
            if row is not None:
                break
        else:
            return False
        self.R.f[tname].set(row, 'sFgQ', style)
        U = self.U
        for e in range(U.cur_rec):
            if e not in self.deleted and self.pid_of_entry(e) == pid:
                U.set(e, 'sFgQ', style)
        return True

    def set_pro_team(self, prow, team):
        """cPbu.proteam (the NHL organisation that holds a player's rights) is team + 1. On a roster for the unpatched
        game Seattle and Vegas (slots 30 / 31) hold no rights: its Season knows 30 NHL teams (contracts.rights_teams),
        so their players hold nobody's; a roster for the game patch holds them all (gamepatch.rights_wide)."""
        self.P.set(prow, 'WBbd', team + 1 if pay.holds_rights(self.P, team) else 0)

    def nhl_lines(self):
        """Departed players' slots/letters go to newcomers, then NHL lines are re-dealt by rating
        on each team's own template. A roster this tool already built keeps the lines of teams
        whose players did not change (they may have been set by hand in the game), unless one of its
        players changed position (NHL.com: a defenceman now a winger) or its lines would not pass
        verify's line-up rule. A team that cannot dress a legal 20 first gets the players it misses
        (call_ups)."""
        self.call_ups()
        changed = set(self.departures) | set(self.arrivals)
        for team in changed:
            self.fill_lines(team)
        for team in L.NHL_PRIMARY:
            if team not in self.orig_slot_sets:
                self.lines_from_scratch(team)
            elif team in changed or team in self.position_teams or not self.maintain or self.mendable(team):
                self.deal_again(team)
        self.lines_from_games()

    def lines_from_games(self, teams=None):
        """Lay the real lines of the team's last games (data pack part `lines`) over the lines just dealt, group by group:
        the four lines and three pairs, the goalies, the power play (and its 4-skater units) and the penalty kill, each
        only when every slot of the group has a player who is on the team now. Overtime, the shootout and the extra
        attackers stay as dealt (a player the real lines took out of the 20 is swapped for a dressed one). Kept only
        when check_lineup finds nothing; else the team keeps what it had. `self.real_lined` / `real_refused`: team codes.
        `teams`: only these, dealt again by a later step (contract_strays); the next run would lay the lines on again."""
        if teams is None:
            self.real_lined, self.real_refused = [], {}
        rows = {p['nhl_id']: p['row'] for p in self.api if p.get('nhl_id') and p['row'] is not None}
        for team in sorted(L.NHL_PRIMARY if teams is None else teams):
            code = L.SLOT_TO_API[team]
            real = self.data.real_lines.get(code) or {}
            wanted = real.get('slots')
            if real.get('letters'):          # the captains of the team's last games (NHL.com's game rosters)
                self.real_letters(team, {rows[int(i)]: v for i, v in real['letters'].items() if int(i) in rows})
            if not wanted:
                continue
            problems = self.real_line_up(team, wanted, rows)
            if problems:
                self.real_refused[code] = problems
                if code in self.real_lined:
                    self.real_lined.remove(code)
            elif code not in self.real_lined:
                self.real_lined.append(code)
        if self.lettered & set(L.NHL_PRIMARY):
            self.sync_mirrors()

    def real_club_lines(self, slots):
        """The real lines of the clubs outside the NHL (data pack part `club_lines`: an Extraliga club's latest match
        line-up, else the lines of a larger database) over the lines the league step dealt, for the clubs in `slots`: the
        same rule as the NHL's (`real_line_up`), players found on the club by name (the full name, else the last name and
        the first initial when only one player of the club has them). `self.club_lined` / `club_refused`: club slots."""
        self.club_lined, self.club_refused = [], {}
        for slot in sorted(slots):
            wanted = (self.data.club_lines.get(str(slot)) or {}).get('slots')
            if not wanted:
                continue
            full, short = {}, {}
            for e in self.entries_on(slot):
                prow = self.prow_of_entry(e)
                first, last = norm(self.P.get(prow, 'PedH')), norm(self.P.get(prow, 'RMbQ'))
                full.setdefault(first + last, []).append(prow)
                short.setdefault((last, first[:1]), []).append(prow)

            def found(who):
                first, last = norm(who[0]), norm(who[1])
                rows = full.get(first + last) or short.get((last, first[:1])) or []
                return rows[0] if len(rows) == 1 else None
            key = {}
            for name, who in wanted.items():
                prow = found(who)
                if prow is not None:
                    key[name] = prow
            self.fill_real_gaps(slot, key)
            problems = self.real_line_up(slot, key, {prow: prow for prow in key.values()})
            if problems:
                self.club_refused[slot] = problems
            else:
                self.club_lined.append(slot)

    GAP_SHARE = 0.4     # a group of real lines is kept when at most this share of its players has left the club

    def fill_real_gaps(self, team, key):
        """`key` ({slot name: player row}) holds the real lines' players found on the club. A group that lacks some of them
        (a database older than the club's list, a player now in the NHL) is completed when at most GAP_SHARE of its slots
        are open: each open slot goes to the player who holds it now, else to the club's best player of that kind (goalie,
        defenceman, forward) not yet in the group; a group with more gone is dropped from `key` (the deal stays)."""
        slots, _letters = lines.lineup(self, team)
        ents = self.entries_on(team)
        kind = {e: {4: 'G', 3: 'D'}.get(self.P.get(self.prow_of_entry(e), 'aljv'), 'F') for e in ents}
        kind_of = {self.prow_of_entry(e): kind[e] for e in ents}
        for n in list(key):                 # a place for a kind of player he is not (a database's positions differ): open
            want = 'G' if n.startswith('g') else 'D' if n.endswith(('ld', 'rd')) and n in schema.EVEN_STRENGTH else                 'F' if n.endswith(('lw', 'c', 'rw')) else None
            if want and kind_of.get(key[n]) != want:
                del key[n]
        for _title, names in lines.GROUPS:
            got = [n for n in names if n in key]
            open_ = [n for n in names if n not in key]
            if not got or not open_:
                continue
            if len(open_) > self.GAP_SHARE * len(names):
                for n in got:
                    del key[n]
                continue
            used = {key[n] for n in got}
            for n in open_:
                want = 'G' if n.startswith('g') else 'D' if n.endswith(('ld', 'rd')) else 'F'
                now = slots.get(n)
                pick = now if now is not None and self.prow_of_entry(now) not in used and kind.get(now) == want else None
                if pick is None:
                    pick = next((e for e in sorted(ents, key=lambda e: (-self.q(e), self.pid_of_entry(e), e))
                                 if kind[e] == want and self.prow_of_entry(e) not in used), None)
                if pick is None:
                    break
                key[n] = self.prow_of_entry(pick)
                used.add(key[n])

    def real_line_up(self, team, wanted, rows):
        """Write `wanted` ({slot name: NHL.com id}) onto `team`'s lines; returns what is wrong with the result ([] when it
        was written)."""
        slots, letters = lines.lineup(self, team)
        ents = self.entries_on(team)
        if len(slots) != len(self.flags):
            return ['the team has no complete lines to start from']
        entry_of = {self.prow_of_entry(e): e for e in ents}
        new, applied = dict(slots), 0
        for _group, names in lines.GROUPS:
            got = {n: entry_of.get(rows.get(wanted.get(n))) for n in names}
            if all(e is not None for e in got.values()) and len(set(got.values())) == len(got):
                new.update(got)
                applied += 1
        if not applied:
            return ['no group of the real lines has all its players on the team']
        for slot in new:                                   # a defence pair: the right shot on the right
            if slot.endswith('ld') and slot[:-2] + 'rd' in new and new[slot] != slots.get(slot):
                new[slot], new[slot[:-2] + 'rd'] = lines._pair(self.P, self, new[slot], new[slot[:-2] + 'rd'])
        dressed = {new[n] for n in schema.EVEN_STRENGTH + schema.GOALIE_SLOTS}
        skaters = sorted((e for e in dressed if self.P.get(self.prow_of_entry(e), 'aljv') != 4),
                         key=lambda e: (-self.q(e), self.pid_of_entry(e), e))
        for _group, names in lines.GROUPS:                # the groups left as dealt hold dressed players only
            if names is schema.EVEN_STRENGTH or names is schema.GOALIE_SLOTS:
                continue
            for n in names:
                if new[n] in dressed:
                    continue
                held = {new[m] for m in names}
                want_d = n.endswith(('ld', 'rd'))          # shootout and extra attackers: forwards
                pick = [e for e in skaters if e not in held and
                        (self.P.get(self.prow_of_entry(e), 'aljv') == 3) == want_d]
                if pick:
                    new[n] = pick[0]
        kinds = {0: 'C', 1: 'L', 2: 'R', 3: 'D', 4: 'G'}
        pos = {e: kinds[self.P.get(self.prow_of_entry(e), 'aljv')] for e in ents}
        names = {e: self.R.name(self.prow_of_entry(e)) for e in ents}
        problems = lines.check_lineup(new, letters, pos, names, nhl=team in L.NHL_PRIMARY)
        if not problems:
            lines.set_lineup(self, team, new, letters)
        return problems

    # --- a legal 20 (verify's line-up rule) ------------------------------------------
    def kinds_on(self, team):
        """How many goalies, defencemen and forwards `team` holds now, by their real positions: Counter G / D / F."""
        return Counter({4: 'G', 3: 'D'}.get(self.P.get(self.prow_of_entry(e), 'aljv'), 'F') for e in self.entries_on(team))

    def can_dress(self, team):
        """Can `team` dress a legal 20 (2 goalies, at least 6 defencemen, 18 skaters)?"""
        have = self.kinds_on(team)
        return have['G'] >= 2 and have['D'] >= 6 and have['D'] + have['F'] >= 18

    def mendable(self, team):
        """Do `team`'s lines break verify's line-up rule (lines.lineup_flaws) while its players could dress a
        legal 20? Then dealing them again mends them, and a second run finds nothing to do."""
        return bool(lines.lineup_flaws(self, team)) and self.can_dress(team)

    def deal_again(self, team):
        """Deal an NHL or national team's lines again on its own template (lines_by_template); when that still
        breaks the line-up rule (the template is short: the source dressed 19, or a forward stood in on defence)
        and the team can dress a legal 20, from scratch (lines.build_lines; its letters stay)."""
        if team in self.orig_slot_sets:
            self.lines_by_template(team, self.orig_slot_sets[team])
            if not lines.lineup_flaws(self, team):
                return
        if self.can_dress(team):
            lines.build_lines(self, team)
            self.set_letters(team)

    def lineup_needs(self, team):
        """What `team` misses for a legal 20: Counter G / D / F (forwards: the skaters short of 18 once it has
        its 6 defencemen). Empty when nothing."""
        have = self.kinds_on(team)
        need = Counter(G=2 - have['G'], D=6 - have['D'], F=18 - max(have['D'], 6) - have['F'])
        return +need

    def call_ups(self):
        """NHL teams that cannot dress a legal 20 by their players' real positions (NHL.com moved a defenceman up
        front and the team has no seventh; a roster copy left a team short) get the players they miss, one at a
        time, best first by rating, then person id: a former player of the team whom this run took off (not on
        NHL.com's roster, a free agent now; a second run finds the one this run brought in there, and keeps him),
        then a player of its farm club (clubs.affiliates) while the club keeps a dressable 20 of its own, then a
        free agent. Never a player who would retire, one a club league lists (its step would take him away
        again) or one under contract with another organisation. They pass verify's NHL check as depth (joined_depth). Before the lines are dealt
        (nhl_lines) and again at the end (repair_lineups). Returns how many came."""
        from .leagues.clubs import CORE, affiliates
        R, U, P = self.R, self.U, self.P
        short = {}
        for team in sorted(L.NHL_PRIMARY):
            if self.players_team(team):     # free editing: a team the player left short stays as he left it
                continue
            need = self.lineup_needs(team) if self.entries_on(team) else None
            if need:
                short[team] = need
        if not short:
            return 0
        farms = {nhl: ahl for ahl, nhl in affiliates(R).items() if R.T.get(ahl, 'NYKk')}
        kind = lambda prow: {4: 'G', 3: 'D'}.get(P.get(prow, 'aljv'), 'F')
        live = self.live_entries()
        # on no team but national teams and the copies of `team` (a free agent, a former player whose copies stay until
        # sync_mirrors, or a farm player whose only club is the farm: `but`)
        alone = lambda pid, team, but=None: all(x == but or U.get(x, 'BSXd') in L.NATIONAL
                                                or self.mirror_of.get(U.get(x, 'BSXd')) == team for x in live.get(pid, []))

        def usable(prow, team):
            pid = P.get(prow, 'zIBw')
            return (not self.would_retire(pid) and prow not in self.league_rows and self.person(prow) not in self.league_names
                    and self.contract_org.get(pid, team) == team)

        came = 0
        for team, need in short.items():
            farm = farms.get(team)
            for k in ('G', 'D', 'F'):
                for _ in range(need[k]):
                    fa = {R.link_to_pid.get(l): l for l in reversed(self.fa_links)}
                    found = []      # (source, -quality, pid, how, entry or link, record): the smallest comes
                    for e in sorted(self.deleted):
                        prow = self.prow_of_entry(e)
                        if U.get(e, 'BSXd') == team and prow is not None and kind(prow) == k \
                                and self.pid_of_entry(e) in fa and alone(self.pid_of_entry(e), team) and usable(prow, team):
                            found.append((0, -self.q(e), self.pid_of_entry(e), 'former', e, prow))
                    if farm is not None:
                        have = self.kinds_on(farm)
                        if have[k] - 1 >= CORE[k] and (k == 'G' or have['D'] + have['F'] - 1 >= 18):
                            for e in self.entries_on(farm):
                                prow = self.prow_of_entry(e)
                                if prow is not None and kind(prow) == k and alone(self.pid_of_entry(e), team, e) \
                                        and usable(prow, team):
                                    found.append((1, -self.q(e), self.pid_of_entry(e), 'farm', e, prow))
                    for pid, link in fa.items():
                        prow = R.p_by_id.get(pid)
                        if prow is not None and kind(prow) == k and alone(pid, team) and usable(prow, team):
                            found.append((2, -self.quality.get(pid, 0), pid, 'fa', link, prow))
                    if not found:
                        break
                    _, _, pid, how, x, prow = min(found)
                    e = self.bring_in(team, how, x, prow, k, farm)
                    live = self.live_entries() if how == 'former' else live
                    if how != 'former':
                        live[pid] = [y for y in live.get(pid, []) if y != x] + [e]
                    came += 1
        if came:
            self.log.append(['ALL', 'summary', 'players brought in so a team can dress 20', f"{came} players", ''])
        return came

    def bring_in(self, team, how, x, prow, k, farm=None):
        """Put player `prow` on NHL team `team` (call_ups): `how` 'former' (`x`: his entry this run took off the
        team, put back as it was), 'farm' (`x`: his entry on the farm club, moved) or 'fa' (`x`: his free-agent
        link). His number when the team has it free, else his record's, else the lowest free one. Returns his
        entry."""
        R, U, P = self.R, self.U, self.P
        pid = P.get(prow, 'zIBw')
        abbr, name = L.SLOT_TO_API[team], R.name(prow)
        if how == 'former':
            e = x
            self.deleted.discard(e)
            deps = self.departures.get(team, [])
            left = (self.cls(e), self.held(e), U.get(e, 'lcCm'))
            for i, d in enumerate(deps):        # his place in the lines is his again (nobody else gets it)
                if (d[0], d[1], d[3]) == left:
                    del deps[i]
                    break
            if not deps:
                self.departures.pop(team, None)
            self.left_keys.discard(self.person(prow))
            for i, row in enumerate(self.log):
                if row[0] == abbr and row[1] == 'left NHL roster' and row[2] == name:
                    del self.log[i]
                    break
            change, detail = 'stays to fill the line-up', "not on NHL.com's roster"
        elif how == 'farm':
            e = x
            frm = R.team_name(farm)
            self.move_entry(e, team)
            change, detail = 'called up to fill the line-up', f"from {frm}"
        else:
            e = self.new_entry(team, x, prow)
            self.arrivals.setdefault(team, []).append(e)
            change, detail = 'signed to fill the line-up', 'free agent'
        taken = {U.get(y, 'tRVs') for y in self.entries_on(team) if y != e}
        U.set(e, 'tRVs', next(n for n in (U.get(e, 'tRVs'), P.get(prow, 'tRVs'), *range(2, 99)) if n and n not in taken))
        self.drop_fa(pid)
        self.set_pro_team(prow, team)
        self.joined_depth[prow] = team
        self.called_up.append((team, prow))
        self.log.append([abbr, change, name, f"{detail}, needed at {k} so the team can dress 20", U.get(e, 'tRVs')])
        return e

    def sync_mirrors(self):
        """Keep the mirror copies (classic/alternate team slots) identical to the primary team. A
        player who was only on the copy (a community roster whose copies are out of step) becomes
        a free agent rather than a player on no team. A copy that lists a player twice (a tester's roster: "Kraken has 49
        players") keeps one entry of him; an entry whose link names no player goes."""
        U = self.U
        live = None
        for prim, mirrors in self.mirrors.items():
            pe = {self.pid_of_entry(e): e for e in self.entries_on(prim)}
            for m in mirrors:
                me, twice = {}, 0
                for e in self.entries_on(m):
                    pid = self.pid_of_entry(e)
                    if pid is None or pid not in self.R.p_by_id:
                        self.deleted.add(e)
                    elif pid not in pe:
                        live = live if live is not None else self.live_entries()
                        self.release(e, live)
                    elif pid in me:
                        self.deleted.add(e)
                        twice += 1
                    else:
                        me[pid] = e
                if twice:
                    self.log.append(['ALL', 'summary', f"{self.R.team_name(m)}: players listed twice taken off", twice, ''])
                for pid, src in pe.items():
                    e = me.get(pid)
                    if e is None:
                        e = U.add_record()
                        U.records[e * U.rec_len:(e + 1) * U.rec_len] = U.records[src * U.rec_len:(src + 1) * U.rec_len]
                        U.set(e, 'BSXd', m)
                        U.set(e, 'XWot', L.XWOT_UNSET)
                    for f in self.flags + ['jZSh', 'lcCm', 'tRVs', 'sFgQ']:
                        U.set(e, f, U.get(src, f))

    def set_arena(self, slot, name, city=None, alone=False, capacity=None):
        """The arena name (and `city`, and `capacity`) of a team, on the arena row it uses. A row other teams use too (a
        custom copy of an NHL team, a farm club in the same building) is renamed for all of them; a row another NHL team
        uses (Seattle and Vegas started on one), or with `alone` any team outside the slot's own copies, is copied first
        while the table has room (the copy keeps the arena's art, so the ice and the boards stay). False when that needed
        room the table has not; True when something was written; None when the row already said so."""
        T, A = self.R.T, self.R.f['OEtS']
        row = T.get(slot, 'arenaid')
        if (A.get(row, 'arenaname') == name and (city is None or A.get(row, 'cityname') == city)
                and (capacity is None or A.get(row, 'maxattendance') == capacity)):
            return None
        prime = self.mirror_of.get(slot, slot)
        family = {prime} | set(self.mirrors.get(prime, ()))
        sharers = [t for t in range(T.cur_rec) if t != slot and T.get(t, 'arenaid') == row]
        if any(t not in family for t in sharers) if alone else any(t < 32 for t in sharers):
            if A.cur_rec >= A.max_rec:
                return False
            row = A.add_record(template=row)
            A.set(row, 'index', row)
            T.set(slot, 'arenaid', row)
        A.set(row, 'arenaname', name)
        if city is not None:
            A.set(row, 'cityname', city)
        if capacity is not None:
            A.set(row, 'maxattendance', capacity)
        return True

    def ahl_identity(self):
        """The arena of every AHL club in AHL_ARENAS (and Coachella Valley's and Henderson's) with its city and capacity. A
        club in a building of its own gets a row of its own while the table has room; the clubs left out of the table
        already name the right building (or share their NHL team's). Returns how many clubs changed; a second run
        changes none; a club that needed a row the table has not keeps the shared one."""
        done = 0
        for slot, (name, city, capacity) in AHL_ARENAS.items():
            done += bool(self.set_arena(slot, name, city, alone=slot in AHL_ALONE, capacity=capacity))
        return done

    def vees_arena(self):
        """The Penticton Vees' own arena: a copy of a WHL club's row, for its ice and boards (a custom slot starts on a row
        of the custom teams'). When the table has no room left they play in that club's arena."""
        T, A = self.R.T, self.R.f['OEtS']
        name, city, capacity = VEES_ARENA
        if A.get(T.get(L.VEES, 'arenaid'), 'arenaname') != name:
            T.set(L.VEES, 'arenaid', T.get(L.VEES_RINK, 'arenaid'))
        return self.set_arena(L.VEES, name, city, alone=True, capacity=capacity)

    def nhl_identity(self):
        """The arena name of every NHL team (NHL_ARENAS), the city of Utah, Seattle and Vegas (NHL_CITIES) and every NHL
        team's two colours (NHL_COLOURS). Returns how many teams changed; a second run changes none. (A team whose arena
        needed a row of its own when the table was full keeps the shared one; its colours are written all the same.)"""
        T = self.R.T
        done = 0
        for slot in range(32):
            changed = bool(self.set_arena(slot, NHL_ARENAS[slot], NHL_CITIES.get(slot)))
            for kind, rgb in zip(('primary', 'secondary'), NHL_COLOURS[slot]):
                for channel, value in zip('rgb', rgb):
                    if T.get(slot, f"{kind}color_{channel}") != value:
                        T.set(slot, f"{kind}color_{channel}", value)
                        changed = True
            done += changed
        return done

    def nhl_gear(self, own=None):
        """The helmets, gloves and the rest of Utah's, Seattle's and Vegas's equipment in their colours (NHL_GEAR), the
        teams' own (vbHh) and their goalies' (nAUy). Both tables count teams from 1: the slot + 1. The game's tables
        still hold Arizona's red and the All-Star teams' colours: a colour with a hue becomes the gear's first colour, a
        dark one its second, cream becomes white; greys, white and black stay. First the colours the old step put on the
        teams before them go back (GEAR_SLIPS; from `own`, the game's own roster, where it has the row, else from the
        team's own colours). Doing it again changes nothing. Returns how many equipment rows end up changed."""
        E, G = self.R.f['vbHh'], self.R.f['nAUy']
        zones = [[f"zone{z}_{c}" for c in 'rgb'] for z in range(1, 10)]
        gzones = [[f"{part}zone{z}color_{c}" for c in 'rgb'] for part in ('blocker', 'pads', 'trapper') for z in range(1, 10)]
        mine = set(NHL_GEAR) | set(GEAR_SLIPS)
        rows = [(table, names, row) for table, names in ((E, zones), (G, gzones)) for row in range(table.cur_rec)
                if table.get(row, 'team') - 1 in mine]
        look = lambda table, names, row: [table.get(row, n) for trio in names for n in trio]
        was = [look(*r) for r in rows]
        self._gear_back(E, zones, {slot + 1: slot for slot in GEAR_SLIPS}, own)
        for table, names in ((E, zones), (G, gzones)):
            for row in range(table.cur_rec):
                slot = table.get(row, 'team') - 1
                if slot not in NHL_GEAR:
                    continue
                first, second = NHL_GEAR[slot]
                for trio in names:
                    colour = tuple(table.get(row, n) for n in trio)
                    top, low = max(colour), min(colour)
                    if top and (top - low) / top >= 0.25:
                        new = second if top < 75 else first
                    elif top > 200 and colour[0] - colour[2] >= 15:
                        new = (231, 231, 231)
                    else:
                        continue
                    if new != colour:
                        for n, v in zip(trio, new):
                            table.set(row, n, v)
        return sum(look(*r) != old for r, old in zip(rows, was))

    GEAR_NEAR = 35          # degrees of hue: a gear colour this close to a team colour is the team's
    TEAM_GEAR = (5, 8)      # vbHh / NDEo equipment numbers: 5 the gloves, 8 the helmet (lab round 33)

    def off_hue(self, colour, hues):
        """A colour with a hue none of the team's colours has (black, white and grey always fit)."""
        from . import sticks
        h = sticks.hue_of(colour)
        return h is not None and bool(hues) and all(sticks._apart(h, t) > self.GEAR_NEAR for t in hues)

    def club_gear(self):
        """Helmets and gloves (TEAM_GEAR) of the league clubs (slots 32-213 but the national teams; vbHh) in a colour the
        club does not wear: the slot held another club before (Augsburg's blue helmets, Schwenningen's red ones). Such a
        zone becomes the club's first colour with a hue, a dark one its darkest (sticks.team_colours). The NHL's rows are
        the game's own (also its throwback versions in other colours) and stay; so do the national teams'. The custom teams'
        (NDEo) stay too: their team colours are the placeholder blue / red; Coachella Valley and Henderson get theirs
        whole (layout.OWN_KIT). Doing it again changes nothing. Returns how many rows changed."""
        from . import sticks
        R = self.R
        zones = [[f"zone{z}_{c}" for c in 'rgb'] for z in range(1, 10)]
        tables = ((R.f['vbHh'], lambda s: 32 <= s < 214 and s not in L.NATIONAL and s not in L.MIRROR_OF),)
        changed, colours = 0, {}
        for E, mine in tables:
            for row in range(E.cur_rec):
                slot = E.get(row, 'team') - 1
                if E.get(row, 'equipment') not in self.TEAM_GEAR or slot < 0 or not mine(slot):
                    continue
                if slot not in colours:
                    own = [c for c in sticks.team_colours(R, slot) if sticks.hue_of(c) is not None]
                    colours[slot] = (own, [sticks.hue_of(c) for c in own])
                own, hues = colours[slot]
                if not own:
                    continue
                touched = False
                for trio in zones:
                    colour = tuple(E.get(row, n) for n in trio)
                    if not self.off_hue(colour, hues):
                        continue
                    new = min(own, key=sum) if max(colour) < 90 else own[0]
                    for n, v in zip(trio, new):
                        E.set(row, n, v)
                    touched = True
                changed += touched
        if changed:
            self.log.append(['ALL', 'summary', "helmets and gloves painted in their club's colours", changed, ''])
        return changed

    def _gear_back(self, E, zones, before, own):
        """GEAR_SLIPS: a zone in the colours of the team painted by mistake goes back to the game's own row of `own`
        (the same team, equipment, variant, brand and era; the n-th of equal rows), else to the team's own colours."""
        T = self.R.T
        key = lambda tab, row: tuple(tab.get(row, f) for f in ('team', 'equipment', 'variant', 'brand', 'era'))
        theirs = {}
        if own is not None:
            O = own.f['vbHh']
            for row in range(O.cur_rec):
                if O.get(row, 'team') in before:
                    theirs.setdefault(key(O, row), []).append(row)
        seen = {}
        for row in range(E.cur_rec):
            value = E.get(row, 'team')
            if value not in before:
                continue
            slot = before[value]
            k = key(E, row)
            n = seen[k] = seen.get(k, -1) + 1
            match = theirs.get(k, [])
            orow = match[n] if n < len(match) else None
            _a, _c, primary, secondary = NHL_LOOK[GEAR_SLIPS[slot]]
            if orow is not None:                # all the old step wrote: its colours, its black and its white
                mine = {primary, secondary, (231, 231, 231)}
            else:                               # without the game's row only what is surely ours: not black or white
                mine = {primary: tuple(T.get(slot, f"primarycolor_{c}") for c in 'rgb'),
                        secondary: tuple(T.get(slot, f"secondarycolor_{c}") for c in 'rgb')}
                if secondary == (32, 32, 32):   # Utah's: the game's own black on many teams
                    del mine[secondary]
            for trio in zones:
                colour = tuple(E.get(row, n) for n in trio)
                if colour in mine:
                    new = tuple(own.f['vbHh'].get(orow, n) for n in trio) if orow is not None else mine[colour]
                    for n, v in zip(trio, new):
                        E.set(row, n, v)

    def relink_free_agents(self):
        """Every free agent gets a new link number; his old link row goes in finish() when nothing else
        uses it. Returns how many."""
        old = list(self.fa_links)
        self.fa_links = [self.new_link(self.R.link_to_pid[link]) for link in old]
        self.old_fa_links = set(old)
        return len(old)

    def mend(self, source):
        """Put right, just before the roster is written, what a step left behind that verify would refuse and that has
        one safe answer (0.95.1: tester rosters kept failing on such leftovers, the last one Nick Jensen on a custom
        team and on the free-agent list). Each repair is a row under REPAIRS in the list of changes. What `source` (the
        roster the build started from, as verify sees it) already had is left alone, as verify allows it, and so is
        what the player's own edits did (verify's `free`). Returns how many repairs were made.

        - a team that lists a player twice keeps one of his places (the one holding line slots);
        - a player on two NHL / AHL teams (a copy of an NHL team counts as that team) keeps the team his contract
          names, else his NHL team, else the lowest; his other places go;
        - the free-agent list holds nobody twice and nobody who is on a club (unlist_club_players);
        - a free agent carries no contract, a contract names a team the player is on (else it is cleared), and every
          player on an NHL team has a contract (the default terms, as contracts() gives a new player).
        Teams that lost a dressed player get their lines dealt again."""
        from . import verify as V
        R, U, P = self.R, self.U, self.P
        free = getattr(self, 'free', None)
        mine = V.free_editing(R, source, free)[0] if free else (lambda pid: False)
        section, self.log.section = self.log.section, REPAIRS
        made = 0

        def note(t, what, prow, detail):
            nonlocal made
            made += 1
            self.log.append([R.T.get(t, 'nnsx') if t is not None else 'ALL', what, R.name(prow), detail, ''])

        def live():
            out = {}
            for e in range(U.cur_rec):
                if e not in self.deleted:
                    out.setdefault(self.pid_of_entry(e), []).append(e)
            return {pid: es for pid, es in sorted(out.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
                    if pid in R.p_by_id and not mine(pid)}

        def drop(e, relines):
            if self.held(e) or U.get(e, 'jZSh'):
                relines.add(U.get(e, 'BSXd'))
            self.depart(e)
            self.deleted.add(e)

        relines, primaries = set(), False
        twice_before = Counter((source.U.get(i, 'BSXd'), source.link_to_pid.get(source.U.get(i, 'TWSX')))
                               for i in range(source.U.cur_rec))
        for pid, ents in live().items():
            by_team = {}
            for e in ents:
                by_team.setdefault(U.get(e, 'BSXd'), []).append(e)
            for t, es in sorted(by_team.items()):
                if len(es) < 2 or twice_before[(t, pid)] > 1 or t in self.mirror_of:   # copies follow their team
                    continue
                keep = max(es, key=lambda e: (len(self.held(e)), bool(U.get(e, 'jZSh')), -e))
                for e in es:
                    if e != keep:
                        drop(e, relines)
                primaries |= t in self.mirrors
                note(t, 'listed twice: one place removed', R.p_by_id[pid], f"on {R.team_name(t)}")

        multi_before = V.multi_club(source)
        for pid, ents in live().items():
            teams = {self.mirror_of.get(U.get(e, 'BSXd'), U.get(e, 'BSXd')) for e in ents} & L.CLUB
            if len(teams) < 2 or pid in multi_before:
                continue
            prow = R.p_by_id[pid]
            named = P.get(prow, 'BSXd') - 1
            nhl = sorted(teams & L.NHL_PRIMARY)
            keep = named if named in teams else (nhl[0] if nhl else min(teams))
            for e in ents:
                t = U.get(e, 'BSXd')
                if t in L.CLUB and t != keep and t not in self.mirror_of:
                    primaries |= t in self.mirrors
                    drop(e, relines)
            note(keep, 'on two teams: kept on one', prow, f"stays on {R.team_name(keep)}, off "
                 + ", ".join(R.team_name(t) for t in sorted(teams - {keep})))
        if primaries:
            self.sync_mirrors()
        for t in sorted(relines - set(self.mirror_of)):
            try:
                lines.build_lines(self, t)
            except lines.NotEnoughPlayers:
                pass                # verify names the team; nothing safe to do here
        if relines & set(self.mirrors):
            self.sync_mirrors()

        self.unlist_club_players()
        listed_before = Counter(source.link_to_pid.get(source.Q.get(k, 'TWSX')) for k in range(source.Q.cur_rec))
        seen, kept = set(), []
        for link in self.fa_links:
            pid = R.link_to_pid.get(link)
            if pid in seen and pid in R.p_by_id and listed_before[pid] < 2 and not mine(pid):
                note(None, 'free agent listed twice: one entry removed', R.p_by_id[pid], '')
                continue
            seen.add(pid)
            kept.append(link)
        self.fa_links = kept

        on = {pid: {U.get(e, 'BSXd') for e in es} for pid, es in live().items()}
        clubs = pay.contract_clubs(R)
        deal = ('BSXd', 'GDhI', 'dhKk', 'IrlK', 'IzRv')
        no_deal_before = set()
        for i in range(source.U.cur_rec):
            pid = source.link_to_pid.get(source.U.get(i, 'TWSX'))
            if source.U.get(i, 'BSXd') in L.NHL_PRIMARY and pid in source.p_by_id:
                srow = source.p_by_id[pid]
                if not (source.P.get(srow, 'GDhI') and source.P.get(srow, 'dhKk')):
                    no_deal_before.add(pid)
        for pid in sorted({R.link_to_pid.get(link) for link in self.fa_links} - {None}):
            prow = R.p_by_id.get(pid)
            if prow is not None and not mine(pid) and any(P.get(prow, f) for f in deal):
                for f in deal:
                    P.set(prow, f, 0)
                note(None, 'free agent: contract cleared', prow, '')
        for pid, teams in on.items():
            prow = R.p_by_id[pid]
            b = P.get(prow, 'BSXd')
            if b and pid not in self.orig_contract_bad and not self.same_team(b - 1) & teams:
                if teams:
                    t = min(teams & clubs or teams)
                    P.set(prow, 'BSXd', t + 1)
                    note(t, 'contract moved to his team', prow,
                         f"named {R.team_name(b - 1)}, he plays for {R.team_name(t)}")
                else:
                    for f in deal:
                        P.set(prow, f, 0)
                    note(None, 'contract cleared', prow, f"named {R.team_name(b - 1)}, he is on no team")
            nhl = sorted(teams & L.NHL_PRIMARY)
            if nhl and pid not in no_deal_before and not (P.get(prow, 'GDhI') and P.get(prow, 'dhKk')):
                years, cap = pay.default_terms(P.get(prow, 'dnFq') + 1910 >= self.data.season_year - 22, self.money)
                P.set(prow, 'BSXd', nhl[0] + 1)
                P.set(prow, 'GDhI', years)
                P.set(prow, 'dhKk', cap)
                note(nhl[0], 'given a contract', prow, f"on {R.team_name(nhl[0])} with none")
        self.log.section = section
        self.repairs = made
        return made

    def finish(self):
        """Remove deleted entries, give every entry its team slot id, write the free-agent list, and
        give back the links of removed roster places that nothing uses any more (the link table
        has room for 9,955: without this every update would use up more, until it is full)."""
        U, Q, C = self.U, self.Q, self.C
        gone = {U.get(e, 'TWSX') for e in self.deleted} | getattr(self, 'old_fa_links', set())
        for e in sorted(self.deleted, reverse=True):
            U.delete_record(e)
        gone |= self.own_links_fit()
        used = {U.get(i, 'TWSX') for i in range(U.cur_rec)} | set(self.fa_links)
        picks = self.R.f['vaHq']
        used |= {picks.get(i, 'TWSX') for i in range(picks.cur_rec)}      # draft picks point at links too
        unused = {link for link in gone - used if link < LINK_LIMIT}     # the game's own links stay
        for i in reversed(range(C.cur_rec)):
            if C.get(i, 'qEfv') in unused:
                C.delete_record(i)
        self.deleted = set()
        for name in self.R.f.tables:        # no "last removed row" is left to name (see drop_removed_player)
            self.R.f[name].header[0x18:0x1C] = b'\x00\x00\xff\xff'
        self.renumber_entries()
        Q.cur_rec = 0
        for link in self.fa_links:
            Q.add_record({'TWSX': link})

    def own_links_fit(self):
        """A player on a Create Player record listed through an ordinary link (rosters of this program before lab
        round 45) is listed through his own link again, on his teams and on the free-agent list. Returns the ordinary
        links it let go."""
        U, to_pid, left = self.U, self.R.link_to_pid, set()
        for e in range(U.cur_rec):
            link = U.get(e, 'TWSX')
            own = self.own_links.get(to_pid.get(link))
            if own is not None and own != link:
                U.set(e, 'TWSX', own)
                left.add(link)
        fa = []
        for link in self.fa_links:
            own = self.own_links.get(to_pid.get(link))
            if own is not None and own != link:
                left.add(link)
                if own in fa or own in self.fa_links:
                    continue
                link = own
            fa.append(link)
        self.fa_links = fa
        return left

    def renumber_entries(self):
        """Roster entry ids are team * 40 + slot, slots 0..n-1 with no gaps (the game finds a team's
        players through them). Entries that already belong to the team keep their order."""
        U = self.U
        by_team = {}
        for i in range(U.cur_rec):
            by_team.setdefault(U.get(i, 'BSXd'), []).append(i)
        for team, ents in by_team.items():
            if len(ents) > L.MAX_PER_TEAM:
                raise RuntimeError(f"{self.R.team_name(team)} has {len(ents)} players (max {L.MAX_PER_TEAM})")
            ents.sort(key=lambda i: (U.get(i, 'XWot') // L.MAX_PER_TEAM != team, U.get(i, 'XWot') % L.MAX_PER_TEAM, i))
            for k, i in enumerate(ents):
                U.set(i, 'XWot', team * L.MAX_PER_TEAM + k)

    # --- lines by rating -----------------------------------------------------
    STAND_INS = {'G': 'G', 'D': 'DWC', 'C': 'CWD', 'W': 'WCD'}   # who fills a slot set of each class

    def lines_by_template(self, team, template):
        """Re-deal a team's line slots by rating: the i-th best player of a class (G, D, C, W) gets
        the slot set held by the i-th most-used player of that class in `template`. A wing's slot
        set goes to a winger of its side first (a left wing on the left), then to the other side."""
        U = self.U
        ents = self.entries_on(team)
        for e in ents:
            for f in self.flags + ['jZSh']:
                U.set(e, f, 0)
        pools = {c: sorted((e for e in ents if self.cls(e) == c), key=self.q, reverse=True) for c in 'GDCW'}
        for c in 'GDCW':
            for cc, slots, _ in template:
                if cc != c:
                    continue
                # short of forwards: the other forward position, then a spare defenceman (and the
                # other way round for defence)
                pool = next((pools[k] for k in self.STAND_INS[c] if pools[k]), [])
                if pool:
                    e = pool[0]
                    side = lines.wing_side(slots) if pool is pools['W'] else None
                    natural = next((x for x in pool if self.P.get(self.prow_of_entry(x), 'aljv') == side), None)
                    if natural is not None and self.q(natural) >= self.q(e) - lines.SIDE_MARGIN:
                        e = natural         # his own side, unless that means dressing a much weaker player
                    pool.remove(e)
                    for f in slots:
                        U.set(e, f, 1)
        for e in ents:
            U.set(e, 'jZSh', 1 if self.held(e) else 0)

    def set_letters(self, team):
        """Captain and two alternates for a team that has none: its three best skaters."""
        U = self.U
        ents = self.entries_on(team)
        if any(U.get(e, 'lcCm') for e in ents):
            return
        best = sorted((e for e in ents if self.cls(e) != 'G'), key=self.q, reverse=True)[:3]
        for k, e in enumerate(best):
            U.set(e, 'lcCm', 1 if k == 0 else 2)

    def real_letters(self, team, letters):
        """This season's captain and alternates (`letters` {player row: 'C' | 'A'}, from the team's games or its league's
        list) onto `team`: the skaters of them who are on it, one captain at most, topped up to three with alternates for
        its best dressed skaters (no captain left: three alternates, as the game allows). Written only when check_lineup
        passes (else the team keeps its letters); True when written. `self.lettered`: the teams that got them."""
        U = self.U
        ents = [e for e in self.entries_on(team) if e not in self.deleted]
        on = {self.prow_of_entry(e): e for e in ents}
        skater = {e for e in ents if self.P.get(self.prow_of_entry(e), 'aljv') != 4}
        new = {}
        for prow, letter in sorted(letters.items(), key=lambda kv: (kv[1] != 'C', self.pid_of_entry(on[kv[0]])
                                                                     if kv[0] in on else 0, kv[0])):
            e = on.get(prow)
            if e not in skater or len(new) == 3 or (letter == 'C' and 'C' in new.values()):
                continue
            new[e] = letter
        if not new:
            return False
        for e in sorted((e for e in skater if U.get(e, 'jZSh') and e not in new),
                        key=lambda e: (-self.q(e), self.pid_of_entry(e), e))[:3 - len(new)]:
            new[e] = 'A'
        if team in L.NHL_PRIMARY and len(new) != 3:
            return False
        slots, old = lines.lineup(self, team)
        kinds = {0: 'C', 1: 'L', 2: 'R', 3: 'D', 4: 'G'}
        pos = {e: kinds[self.P.get(self.prow_of_entry(e), 'aljv')] for e in ents}
        names = {e: self.R.name(self.prow_of_entry(e)) for e in ents}
        if len(slots) == len(self.flags):       # only what the letters add counts (the lines may be mended later)
            had = set(lines.check_lineup(slots, old, pos, names, nhl=team in L.NHL_PRIMARY))
            if set(lines.check_lineup(slots, new, pos, names, nhl=team in L.NHL_PRIMARY)) - had:
                return False
        code = {v: k for k, v in lines.LETTERS.items()}
        for e in ents:
            U.set(e, 'lcCm', code.get(new.get(e), 0))
        self.lettered.add(team)
        return True

    def national_letters(self, teams):
        """Letters for national teams this run filled (no list names their captains): the captain is the skater who
        captains his own NHL team or club, else one who wears an A there, else the best; the two alternates follow the
        same order. Dressed skaters first. `self.national_lettered`: the teams."""
        U = self.U
        worn = {}                                   # player id -> 1 (C) / 2 (A) on his NHL team or club
        for e in range(U.cur_rec):
            t = U.get(e, 'BSXd')
            if e not in self.deleted and t not in L.NATIONAL and U.get(e, 'lcCm') in lines.LETTERS:
                p = self.pid_of_entry(e)
                worn[p] = min(worn.get(p, 9), U.get(e, 'lcCm'))
        for team in sorted(teams):
            ents = self.entries_on(team)
            skaters = [e for e in ents if self.P.get(self.prow_of_entry(e), 'aljv') != 4]
            if not skaters:
                continue
            order = sorted(skaters, key=lambda e: (not U.get(e, 'jZSh'), worn.get(self.pid_of_entry(e), 9), -self.q(e),
                                                   self.pid_of_entry(e), e))
            for e in ents:
                U.set(e, 'lcCm', 0)
            for k, e in enumerate(order[:3]):
                U.set(e, 'lcCm', 1 if k == 0 else 2)
            self.national_lettered.add(team)

    def fill_lines(self, team):
        U = self.U
        ents = self.entries_on(team)
        holders = {}
        for e in ents:
            for f in self.held(e):
                holders.setdefault(f, []).append(e)
        newcomers = sorted((e for e in self.arrivals.get(team, []) if e not in self.deleted), key=self.q, reverse=True)
        reserves = sorted((e for e in ents if not self.held(e) and e not in newcomers), key=self.q, reverse=True)
        pools = [newcomers, reserves]
        for cls, slots, _, captaincy in sorted(self.departures.get(team, []), key=lambda d: -len(d[1])):
            slots = {f for f in slots if f not in holders}
            if not slots:
                continue
            pick = None
            for want in (lambda c: c == cls, lambda c: c in 'CW' and cls in 'CW'):
                for pool in pools:
                    for e in pool:
                        if want(self.cls(e)):
                            pick = e
                            pool.remove(e)
                            break
                    if pick is not None:
                        break
                if pick is not None:
                    break
            if pick is None:
                continue
            for f in slots:
                U.set(pick, f, 1)
                holders.setdefault(f, []).append(pick)
        for e in ents:
            U.set(e, 'jZSh', 1 if self.held(e) else 0)
        # letters (C/A) of departed players go to the best remaining dressed skater without one
        for _, _, _, captaincy in self.departures.get(team, []):
            if not captaincy:
                continue
            cands = [e for e in ents if e not in self.deleted and U.get(e, 'jZSh') and not U.get(e, 'lcCm')
                     and self.cls(e) != 'G']
            if cands:
                U.set(max(cands, key=self.q), 'lcCm', captaincy)

    # --- the full ratings (data pack part `ratings_full`, docs/notes/full-ratings.md) ------------------------
    def full_match(self, prow):
        """the full ratings' player for a record, as (player, how) or None (ratings.match_full). Found from the record's own name,
        birthdate and kind (goalie or skater) alone, never from other records, so the next run finds the same player
        for him. On a community roster a record still in the game's year - 1900 (donors.real_birth_year) is also tried ten
        years earlier for the exact birthdate."""
        if not self.full_ratings:
            return None
        P = self.P
        first, last = P.get(prow, 'PedH'), P.get(prow, 'RMbQ')
        if not first or not last:
            return None
        shown = P.get(prow, 'dnFq') + 1910
        birth = (shown, P.get(prow, 'pLKJ') + 1, P.get(prow, 'iwsK') + 1)
        years = (shown, shown - 10) if self.stale_years else (shown,)
        return ratings.match_full(self.full_ratings, first, last, birth, P.get(prow, 'aljv') == 4, years, (shown,))

    def full_style(self, prow, cls):
        """the full ratings' player type for a record when it is one of class `cls` ('F', 'D', 'G': ratings.STYLE_CHOICES),
        else None."""
        found = self.full_match(prow)
        if not found:
            return None
        p, _ = found
        style = ratings.full_values(self.full_ratings, ratings.full_kind(cls == 'G'), p).get('playerstyle')
        return style if style in ratings.STYLE_CHOICES[cls] else None

    def rate_full(self, prow, live=None):
        """Give a player the full ratings when the full ratings have him (full_match): the ratings and tendencies
        (ratings.write_full), his player type when it fits his position, his height, weight and hand when NHL.com
        does not cover him (full_bio), and his quality from the full ratings' overall (ratings.overall_level). `live`
        (live_entries) saves looking for his roster entries. False when the full ratings do not have him or he has no rating
        row."""
        found = self.full_match(prow)
        if not found:
            return False
        p, how = found
        P = self.P
        goalie = P.get(prow, 'aljv') == 4
        kind = ratings.full_kind(goalie)
        tname = ratings.GOALIE_TABLE if goalie else ratings.SKATER_TABLE
        pid = P.get(prow, 'zIBw')
        row = self.ai_row[tname].get(pid)
        if row is None:
            return False
        values = ratings.full_values(self.full_ratings, kind, p)
        ratings.write_full(self.R.f[tname], row, values, kind)
        style = values.get('playerstyle')
        if style in ratings.STYLE_CHOICES[ratings.style_class(P.get(prow, 'aljv'))]:
            if live is None:
                self.set_style(prow, style)
            else:
                self.R.f[tname].set(row, 'sFgQ', style)
                for e in live.get(pid, ()):
                    self.U.set(e, 'sFgQ', style)
        self.full_bio(prow, p, how)
        self.ovr.pop(pid, None)
        self.list_rated.discard(pid)
        getattr(self, 'list_name_only', set()).discard(pid)
        level = (ratings.overall_level(self.full_ratings, kind, values['c_overall']) if 'c_overall' in values
                 else ratings.level(self.R.f[tname], row))
        self.full_quality[pid] = self.quality[pid] = level + self.ovr_offset[goalie]
        self.full_rated.add(pid)
        self.rated_by[pid] = 'full'
        return True

    def unrate_full(self, pid):
        """A player whom the full ratings no longer find (his birth year was just put right): from now on he counts by his
        attributes, as the next run will see him."""
        if pid not in self.full_rated:
            return
        self.full_rated.discard(pid)
        self.full_quality.pop(pid, None)
        self.rated_by.pop(pid, None)
        for tname in ('yvSd', 'yuHm'):
            row = self.ai_row[tname].get(pid)
            if row is not None:
                self.quality[pid] = ratings.level(self.R.f[tname], row) + self.ovr_offset[tname == 'yuHm']

    def full_bio(self, prow, p, how):
        """the full ratings' height, weight and hand for a player NHL.com does not cover (a league's feed, written after, still
        wins). A record matched by his name alone ('name': the DEL gives only an age) also takes the full ratings' birthdate,
        when the league's step still finds him by it (born in the feed's year or the one before: match_club) and he
        has one record."""
        if prow in self.api_rows:
            return
        P = self.P
        if p.get('height'):
            P.set(prow, 'QBpy', max(0, min(31, p['height'] - 54)))
        if p.get('weight'):
            P.set(prow, 'WZNs', max(0, min(255, p['weight'] - 120)))
        if p.get('hand') in ('L', 'R'):
            P.set(prow, 'pkRG', 0 if p['hand'] == 'L' else 1)
        if how != 'name':
            return
        fed = self.approx_birth.get(self.person(prow))
        y, m, d = p['birth']
        shown = P.get(prow, 'dnFq') + 1910
        before = self.identity(prow)
        if (fed is None or shown not in (fed, fed - 1) or y not in (fed, fed - 1) or y - 1910 < 0
                or len(self.records_of.get(before, ())) > 1):
            return
        P.set(prow, 'dnFq', y - 1910)
        P.set(prow, 'pLKJ', m - 1)
        P.set(prow, 'iwsK', d - 1)
        self.records_of.pop(before, None)
        self.records_of.setdefault(self.identity(prow), []).append(prow)
        self.full_dates += 1

    def apply_full(self):
        """the full ratings for every record the full ratings have (rate_full): the first source of ratings. Returns how many."""
        if not self.full_ratings:
            return 0
        live = self.live_entries()
        return sum(1 for prow in range(self.P.cur_rec) if self.rate_full(prow, live))

    def rating_counts(self):
        """(from the full ratings, from the ratings list, estimated) in this run, over the players on a team or the free-agent list."""
        fa = {self.R.link_to_pid.get(l) for l in self.fa_links}
        live = self.live_entries()
        c = Counter(how for pid, how in self.rated_by.items() if live.get(pid) or pid in fa)
        return c['full'], c['list'], c['estimate']

    # --- the ratings list -------------------------------------------------------------
    def apply_list_ratings(self):
        """The ratings step: the full ratings for every player the full ratings have (apply_full), then the list's published attributes
        for the players the full ratings lack."""
        stats = Counter()
        if self.full_ratings:
            stats['players rated'] = self.apply_full()
            self.log.append(['ALL', 'Current ratings', 'players rated', stats['players rated'], ''])
            if self.full_dates:
                self.log.append(['ALL', 'Current ratings', "real birthdates (the league gives the age only)",
                                 self.full_dates, ''])
        players = self.data.ratings_list
        if not players:
            self._ratings()
            self.list_rated, self.list_name_only = set(), set()
            self.rating_stats = dict(stats)
            return
        P = self.P
        # fully rated players first, so a duplicate listing never downgrades someone to overall-only
        players = sorted(players, key=lambda p: -sum(v is not None for v in p.get('attrs', {}).values()))
        matched = ratings.match_players(self.R, [p for p in players if p.get('birth')])
        # players published without a birthdate: by full name among the players on NHL teams,
        # then on AHL teams (the list has a club's farm players too); only an unambiguous match counts.
        # Other leagues are left out: a name alone is not enough among thousands of club players.
        by_name, elsewhere = {}, {}
        name_only = set()           # records rated by name alone: only while on an NHL or AHL team
        U = self.U
        for e in range(U.cur_rec):
            if e in self.deleted:
                continue
            t, prow = U.get(e, 'BSXd'), self.prow_of_entry(e)
            if t in L.NHL_PRIMARY:
                by_name.setdefault(self.person(prow), []).append((prow, L.SLOT_TO_API[t]))
            elif t in L.AHL:
                elsewhere.setdefault(self.person(prow), set()).add(prow)
        for p in players:
            if p.get('birth'):
                continue
            first, _, last = p['name'].partition(' ')
            key = (norm(first), norm(last))
            cands = by_name.get(key, [])
            if len(cands) > 1:
                cands = [c for c in cands if c[1] == L.team_code(p.get('team'))]
            if len(cands) == 1:
                matched.append((p, cands[0][0]))
                name_only.add(cands[0][0])
            elif not cands and len(elsewhere.get(key, ())) == 1:
                matched.append((p, next(iter(elsewhere[key]))))
                name_only.add(next(iter(elsewhere[key])))
        # the same person can have several records (national-team goalies): rate all of them
        same_person = {}
        for r in range(P.cur_rec):
            key = (self.person(r), P.get(r, 'dnFq'), P.get(r, 'pLKJ'), P.get(r, 'iwsK'))
            same_person.setdefault(key, []).append(r)
        listed = Counter()
        rated = set()
        for p, prow in matched:
            goalie = ratings.is_goalie(p)
            tname = 'yuHm' if goalie else 'yvSd'
            t = self.R.f[tname]
            key = (self.person(prow), P.get(prow, 'dnFq'), P.get(prow, 'pLKJ'), P.get(prow, 'iwsK'))
            done = False
            for r in same_person.get(key, [prow]):
                pid = P.get(r, 'zIBw')
                row = self.ai_row[tname].get(pid)
                if row is None or pid in rated or pid in self.full_rated:     # the full ratings come first
                    continue
                rated.add(pid)
                listed['attributes written'] += ratings.write_attributes(t, row, p, self.ovr_offset[goalie])
                if p.get('ovr'):
                    self.ovr[pid] = p['ovr']
                self.rated_by[pid] = 'list'
                done = True
            if done:
                listed['players rated'] += 1
        self._ratings()
        self.list_rated = rated
        self.list_name_only = {P.get(r, 'zIBw') for r in name_only} & rated
        for k, v in sorted(listed.items()):
            self.log.append(['ALL', 'Current ratings (second list)', k, v, ''])
        stats['players rated'] += listed['players rated']
        stats['attributes written'] += listed['attributes written']
        self.rating_stats = dict(stats)

    def list_rating_for(self, first, last, birth, by_name=False):
        """the list's rating of a player the ratings step could not reach (a club league is about to create
        him, or to put him on an AHL team), found the way apply_list_ratings would find him on a
        second run: last name + birthdate with a fitting first name, else -- for AHL players only,
        `by_name` -- a unique listing without a birthdate under his full name."""
        if not self.data.ratings_list:
            return None
        if getattr(self, '_list_index', None) is None:
            by_birth, no_birth = {}, {}
            for p in sorted(self.data.ratings_list, key=lambda p: -sum(v is not None for v in p.get('attrs', {}).values())):
                fn, _, ln = p['name'].partition(' ')
                if p.get('birth'):
                    by_birth.setdefault((norm(ln), tuple(p['birth'])), []).append((norm(fn), p))
                else:
                    no_birth.setdefault((norm(fn), norm(ln)), []).append(p)
            self._list_index = by_birth, no_birth
        by_birth, no_birth = self._list_index
        fn = norm(first)
        same_day = by_birth.get((norm(last), tuple(birth)), [])
        found = [p for f, p in same_day if same_first_name(f, fn)]
        if found:
            return found[0]
        if len(same_day) == 1:          # last name + birthdate alone, as matching.match finds him (Mikey / Michael Eyssimont)
            return same_day[0][1]
        listed = no_birth.get((fn, norm(last)), []) if by_name else []
        return listed[0] if len(listed) == 1 else None

    def rate_by_name(self, pids):
        """Ratings the list publishes without a birthdate reach a player by his full name while he is on an NHL team, or
        on an AHL team when no NHL player has the name (apply_list_ratings). For the players `pids` who joined one after
        that step (contract_strays), the same way, as the next run will find them."""
        if not self.data.ratings_list or not pids or getattr(self, 'rating_stats', None) is None:
            return                                  # (the ratings step did not run in this update)
        U, P = self.U, self.P
        by_name, elsewhere = {}, {}
        for e in range(U.cur_rec):
            if e in self.deleted:
                continue
            t, prow = U.get(e, 'BSXd'), self.prow_of_entry(e)
            if t in L.NHL_PRIMARY:
                by_name.setdefault(self.person(prow), []).append((prow, L.SLOT_TO_API[t]))
            elif t in L.AHL:
                elsewhere.setdefault(self.person(prow), set()).add(prow)
        for p in sorted(self.data.ratings_list, key=lambda p: -sum(v is not None for v in p.get('attrs', {}).values())):
            if p.get('birth'):
                continue
            first, _, last = p['name'].partition(' ')
            key = (norm(first), norm(last))
            cands = by_name.get(key, [])
            if len(cands) > 1:
                cands = [c for c in cands if c[1] == L.team_code(p.get('team'))]
            if len(cands) == 1:
                prow = cands[0][0]
            elif not cands and len(elsewhere.get(key, ())) == 1:
                prow = next(iter(elsewhere[key]))
            else:
                continue
            pid = P.get(prow, 'zIBw')
            if pid in pids and pid not in self.list_rated and pid not in self.full_rated and self.write_list_rating(prow, p):
                self.list_name_only.add(pid)

    def unrate_name_only(self, pid):
        """A player the list's rating reached by name alone (no birthdate: only on NHL and AHL teams) who now
        joins a club elsewhere: from now on he counts as the next run will see him, by his attributes
        (they stay as the list's rating wrote them). Otherwise lines dealt on the list's overall in this run
        differ from the next run's (Joona Koppanen, 75 by the list, 74.5 by his attributes, at Luleå)."""
        if pid not in getattr(self, 'list_name_only', ()):
            return
        self.list_name_only.discard(pid)
        self.list_rated.discard(pid)
        self.ovr.pop(pid, None)
        for tname in ('yvSd', 'yuHm'):
            row = self.ai_row[tname].get(pid)
            if row is not None:
                self.quality[pid] = ratings.level(self.R.f[tname], row) + self.ovr_offset[tname == 'yuHm']

    def write_list_rating(self, prow, p):
        """Give a player the list's published attributes (see apply_list_ratings). False if he has no rating row."""
        goalie = ratings.is_goalie(p)
        tname = 'yuHm' if goalie else 'yvSd'
        pid = self.P.get(prow, 'zIBw')
        row = self.ai_row[tname].get(pid)
        if row is None:
            return False
        t = self.R.f[tname]
        ratings.write_attributes(t, row, p, self.ovr_offset[goalie])
        if p.get('ovr'):
            self.ovr[pid] = p['ovr']
        self.quality[pid] = self.ovr.get(pid) or ratings.level(t, row) + self.ovr_offset[goalie]
        self.list_rated.add(pid)
        self.rated_by[pid] = 'list'
        return True

    # --- national teams the mod left empty ----------------------------------------
    def estimated_profile(self):
        """Median attribute values of the mod's European-league national players (no club team),
        per rating table and position class -- the base for players the ratings list does not rate."""
        U, R = self.U, self.R
        national_only = {self.pid_of_entry(i) for i in range(U.cur_rec) if U.get(i, 'BSXd') in L.NATIONAL}
        national_only -= {self.pid_of_entry(i) for i in range(U.cur_rec) if U.get(i, 'BSXd') in L.CLUB}
        prof = {}
        for tname in ('yvSd', 'yuHm'):
            t = R.f[tname]
            act = self.active_fields(tname)
            groups = {}
            for i in range(t.cur_rec):
                pid = t.get(i, 'zIBw')
                if pid in national_only and pid in R.p_by_id:
                    c = {'W': 'F', 'C': 'F'}.get(L.POS_CLASS[self.P.get(R.p_by_id[pid], 'aljv')],
                                                 L.POS_CLASS[self.P.get(R.p_by_id[pid], 'aljv')])
                    groups.setdefault(c, []).append([t.get(i, n) for n in act])
            for c, rows in groups.items():
                prof[(tname, c)] = {n: sorted(r[k] for r in rows)[len(rows) // 2] for k, n in enumerate(act)}
        return prof

    # the smallest squad a filled national team gets (2 goalies and 18 skaters dress, plus spares)
    NATIONAL_MINIMUM = {'G': 3, 'D': 7, 'F': 13}

    def fill_empty_national(self):
        """Fill every national team the source leaves empty: the eight the base roster never had,
        and any squad a community roster emptied. Members: the latest IIHF roster (players not in
        the save get a spare record), NHL players of that nationality, then -- where positions are
        still short -- other players of that nationality in the save (AHL, European clubs, juniors,
        prospect pools, free agents), best first; at most 26. A country without enough players to
        dress 2 goalies and 18 skaters keeps its empty squad."""
        R, U, P = self.R, self.U, self.P
        rosters = self.data.iihf or {}
        prof = self.estimated_profile()
        group = lambda prow: {3: 'D', 4: 'G'}.get(P.get(prow, 'aljv'), 'F')
        quality = lambda prow: self.quality.get(P.get(prow, 'zIBw'), 0)
        nhl_now, elsewhere = {}, {}
        for t in L.NHL_PRIMARY:
            for e in self.entries_on(t):
                nhl_now[self.person(self.prow_of_entry(e))] = self.prow_of_entry(e)
        for e in range(U.cur_rec):
            t = U.get(e, 'BSXd')
            if e not in self.deleted and t not in self.nhl_all and t not in L.NATIONAL and t not in L.EVENTS:
                elsewhere.setdefault(self.person(self.prow_of_entry(e)), self.prow_of_entry(e))
        for link in self.fa_links:
            prow = R.p_by_id.get(R.link_to_pid.get(link))
            if prow is not None:
                elsewhere.setdefault(self.person(prow), prow)
        for team in sorted(L.NATIONAL):
            code = L.NATIONAL_ISO.get(R.T.get(team, 'RPbr'))
            if self.entries_on(team) or code not in L.NAT_CODE:
                continue
            iihf = [dict(p) for p in rosters.get(code) or []]
            if code == 'BLR':  # 2021 roster: drop players who would be 38+ this season
                iihf = [p for p in iihf if p['birth'][0] >= self.data.season_year - 37]
            for p in iihf:
                p.update(team=code, birth=tuple(p['birth']))
            match(R, iihf)
            members = []  # (prow or IIHF player still to be created, number, source)
            for p in iihf:
                members.append((p['row'] if p['row'] is not None else p, p['num'], 'IIHF'))
            grp = lambda m: group(m[0]) if isinstance(m[0], int) else {'G': 'G', 'D': 'D'}.get(m[0]['pos'], 'F')
            qual = lambda m: (quality(m[0]) if isinstance(m[0], int) else
                              (self._national_estimate(m[0], code, prof) or (0, 0, 0, 0))[3])
            have = {self.person(m[0]) for m in members if isinstance(m[0], int)}

            def room_for(g):
                """A free place for one more player of group g that still leaves enough places for
                every other group's minimum (Russia has no IIHF roster: its best NHL players alone
                would be 26 forwards and goalies, and the game needs 6 defencemen)."""
                count = Counter(grp(m) for m in members)
                short = sum(max(0, need - count[h]) for h, need in self.NATIONAL_MINIMUM.items() if h != g)
                return len(members) < 26 and (count[g] < self.NATIONAL_MINIMUM[g] or 26 - len(members) > short)
            # NHL players of that nationality (save nationality and NHL birth country agree)
            nhl_cands = sorted((prow for k, prow in nhl_now.items()
                                if k not in have and P.get(prow, 'hleL') == L.NAT_CODE[code]
                                and self.api_country.get(prow) == code),
                               key=quality, reverse=True)
            for prow in nhl_cands:
                same = [m for m in members if grp(m) == group(prow)]
                if room_for(group(prow)):
                    members.append((prow, None, 'NHL'))
                elif len(members) >= 26 and same:
                    weakest = min(same, key=qual)
                    if quality(prow) > qual(weakest):
                        members.remove(weakest)
                        members.append((prow, None, 'NHL'))
            # positions still short: the country's players elsewhere in the save
            have = {self.person(m[0]) for m in members if isinstance(m[0], int)}
            others = sorted((prow for k, prow in elsewhere.items()
                             if k not in have and k not in nhl_now and P.get(prow, 'hleL') == L.NAT_CODE[code]
                             and P.get(prow, 'dnFq') + 1910 >= self.data.season_year - 38
                             and not self.would_retire(P.get(prow, 'zIBw'))),
                            key=lambda r: (-quality(r), r))
            for prow in others:
                g = group(prow)
                if len(members) >= 26:
                    break
                if sum(grp(m) == g for m in members) < self.NATIONAL_MINIMUM[g]:
                    members.append((prow, None, 'club'))
            # places kept for a position nobody else could fill: the best NHL players left
            have = {self.person(m[0]) for m in members if isinstance(m[0], int)}
            for prow in nhl_cands:
                if len(members) >= 26:
                    break
                if self.person(prow) not in have:
                    members.append((prow, None, 'NHL'))
            count = Counter(grp(m) for m in members)
            # the game dresses 2 goalies, 6 defencemen and 12 forwards (verify.structure)
            if count['G'] < 2 or count['D'] < 6 or count['D'] + count['F'] < 18:
                self.log.append([code, 'national team: left empty', R.team_name(team),
                                 f"{count['G']} goalies, {count['D']} defencemen and "
                                 f"{count['D'] + count['F']} skaters found", ''])
                continue
            self.filled_now.add(team)
            numbers = Counter()
            for who, num, src in members:
                prow = who if isinstance(who, int) else self.create_national(who, code, prof, team)
                e = self.new_entry(team, self.new_link(P.get(prow, 'zIBw')), prow)
                n = num if num and not numbers[num] else next(x for x in range(2, 99) if not numbers[x])
                U.set(e, 'tRVs', n)
                numbers[n] += 1
                self.log.append([code, 'national team: added', R.name(prow), src, n])
            lines.build_lines(self, team)
            self.set_letters(team)

    def clear_national(self):
        """The game's own roster, first update: its national teams are 2014's, so they are emptied and
        filled again like the ones the community left empty (fill_empty_national). Their members who
        are on no other team retire (would_retire) or become free agents: never a teamless record,
        which the next update would reuse and so differ from this one."""
        self.rebuild_national = False
        R, U = self.R, self.U
        gone = set()
        for e in range(U.cur_rec):
            if e not in self.deleted and U.get(e, 'BSXd') in L.NATIONAL:
                self.deleted.add(e)
                gone.add(self.pid_of_entry(e))
        live = self.live_entries()
        fa = {R.link_to_pid.get(l) for l in self.fa_links}
        retired = freed = 0
        for pid in sorted(p for p in gone if p in R.p_by_id):
            if any(e not in self.deleted for e in live.get(pid, [])) or pid in fa:
                continue
            if self.retires(pid):
                retired += 1
            else:
                link = next((l for l in R.pid_to_links.get(pid, []) if l in self.link_row), None)
                self.fa_links.append(link if link is not None else self.new_link(pid))
                fa.add(pid)
                freed += 1
        self.log.append(['ALL', 'summary', "2014's national teams emptied, to be filled again",
                         f"{len(gone)} players: {retired} retired, {freed} free agents", ''])

    def _national_estimate(self, p, code, prof):
        """(rating table, attribute profile, adjustment, quality) for an IIHF player the ratings list does not rate: the mod's European national median, adjusted for tournament level and age. None
        when the save has no such profile."""
        goalie = p['pos'] == 'G'
        tname, grp = ('yuHm', 'G') if goalie else ('yvSd', 'D' if p['pos'] == 'D' else 'F')
        base = prof.get((tname, grp))
        if not base:
            return None
        name = f"{p['first']} {p['last']}"
        age = self.data.season_year - p['birth'][0]
        adj = L.NATIONAL_TIER.get(code, 0) + (-2 if age < 21 else -1 if age < 24 else -1 if age > 32 else 0)
        adj += (zlib.crc32(name.encode()) % 3) - 1
        return tname, base, adj, sum(base.values()) / len(base) + adj + 36 + self.ovr_offset[goalie]

    def create_national(self, p, code, prof, team):
        """A European/Asian league player the ratings list does not rate: repurpose a spare record, fill in the
        IIHF data and an estimated rating profile."""
        R, P = self.R, self.P
        if p['pos'] == 'G':
            pos = 4
        elif p['pos'] == 'D':
            pos = 3
        else:  # IIHF lists forwards only as F: alternate C / LW / RW
            pos = len([1 for x in self.created if P.get(x, 'aljv') in (0, 1, 2)]) % 3
        name = f"{p['first']} {p['last']}"
        prow = self.take_record(pos, name)
        old = R.name(prow)
        y, m, d = p['birth']
        self.donors.reset_identity(prow, name, L.NAT_CODE[code], y)
        self.set_text(prow, 'PedH', p['first'])
        self.set_text(prow, 'RMbQ', p['last'])
        P.set(prow, 'JzFM', '')
        P.set(prow, 'iwsK', d - 1)
        P.set(prow, 'pLKJ', m - 1)
        P.set(prow, 'dnFq', y - 1910)
        if p.get('height_cm'):
            P.set(prow, 'QBpy', max(0, min(31, round(p['height_cm'] / 2.54) - 54)))
        if p.get('weight_kg'):
            P.set(prow, 'WZNs', max(0, min(255, round(p['weight_kg'] * 2.20462) - 120)))
        if p.get('shoots') in ('L', 'R'):
            P.set(prow, 'pkRG', 0 if p['shoots'] == 'L' else 1)
        if p.get('num'):
            P.set(prow, 'tRVs', p['num'])
        for f in ('GDhI', 'dhKk', 'IrlK', 'IzRv'):
            P.set(prow, f, 0)
        P.set(prow, 'BSXd', team + 1)  # national-only player: contract team = national team
        pid = P.get(prow, 'zIBw')
        # the full ratings (and bio) when they have him, else the ratings list (an NHL player under contract whom
        # contract_strays brings to his team: Jokiharju), as the next run's ratings step gives them; else the estimate
        rated = self.rate_full(prow, {})
        on_list = None if rated else self.list_rating_for(p['first'], p['last'], p['birth'])
        if on_list and ratings.is_goalie(on_list) == (pos == 4):
            rated = self.write_list_rating(prow, on_list)
        estimate = None if rated else self._national_estimate(p, code, prof)
        if estimate and self.ai_row[estimate[0]].get(pid) is not None:
            tname, base, adj, quality = estimate
            t, row = R.f[tname], self.ai_row[tname][pid]
            for n, v in base.items():
                t.set(row, n, max(0, min(63, v + adj)))
            self.quality[pid] = quality
            self.rated_by[pid] = 'estimate'
        self.log.append([code, 'created', name, f"IIHF {code}, reused record of {old}", p.get('num')])
        return prow

    def national_teams(self, max_swaps=4):
        """Keep the filled national teams current: players who left the NHL make room for the best
        available, and (first build only) up to `max_swaps` rising stars are brought in."""
        R, U, P = self.R, self.U, self.P
        if self.maintain:
            max_swaps = 0
        rising_star_born = self.data.season_year - 24  # upgrade swaps only bring in players this young
        group = lambda prow: {3: 'D', 4: 'G'}.get(P.get(prow, 'aljv'), 'F')
        # unknown quality never counts as "weakest", so no one is swapped out on missing data
        nq = lambda e: self.quality.get(self.pid_of_entry(e), float('inf'))
        pq = lambda prow: self.quality.get(P.get(prow, 'zIBw'), 0)
        nhl_now = {}
        for t in L.NHL_PRIMARY:
            for e in self.entries_on(t):
                prow = self.prow_of_entry(e)
                nhl_now[self.person(prow)] = (prow, e)
        live = self.live_entries()
        for t in sorted(L.NATIONAL):
            members = self.entries_on(t)
            if not members or t in self.filled_now:      # a squad filled from scratch in this run is current
                continue
            abbr = R.T.get(t, 'RPbr')
            code = Counter(P.get(self.prow_of_entry(e), 'hleL') for e in members).most_common(1)[0][0]
            have = {self.person(self.prow_of_entry(e)) for e in members}
            # eligible: the save's nationality and the NHL birth country agree
            pool = sorted((v for k, v in nhl_now.items()
                           if k not in have and k not in L.NOT_ELIGIBLE and P.get(v[0], 'hleL') == code
                           and self.api_country.get(v[0]) == L.NATIONAL_ISO.get(abbr)),
                          key=lambda v: pq(v[0]), reverse=True)
            numbers = Counter(U.get(e, 'tRVs') for e in members)
            added = []

            def add(prow, club_entry, reason):
                pool.remove((prow, club_entry))
                e = self.new_entry(t, self.new_link(P.get(prow, 'zIBw')), prow)
                for n in (U.get(club_entry, 'tRVs'), P.get(prow, 'tRVs')):
                    if n and numbers[n] == 0:
                        break
                else:
                    n = next(x for x in range(2, 99) if numbers[x] == 0)
                U.set(e, 'tRVs', n)
                numbers[n] += 1
                self.arrivals.setdefault(t, []).append(e)
                added.append(e)
                self.log.append([abbr, 'national team: added', R.name(prow), reason, n])

            def remove(e, reason):
                numbers[U.get(e, 'tRVs')] -= 1
                self.release(e, live)            # off his last team: a free agent, never lost
                members.remove(e)
                self.log.append([abbr, 'national team: removed', R.name(self.prow_of_entry(e)), reason,
                                 U.get(e, 'tRVs')])

            # players who left the NHL and are no longer active make room for the best available
            for e in [e for e in members if self.person(self.prow_of_entry(e)) in self.left_keys]:
                g = group(self.prow_of_entry(e))
                remove(e, 'no longer active in the NHL')
                repl = next((v for v in pool if group(v[0]) == g), None)
                if repl:
                    add(*repl, reason=f"replaces {R.name(self.prow_of_entry(e))}")
            # places of members who retired in this run (retires())
            for g in self.national_gaps.pop(t, []):
                repl = next((v for v in pool if group(v[0]) == g), None)
                if repl:
                    add(*repl, reason="replaces a retired player")
            # up to `max_swaps` rising stars who rate above the weakest member at their position (never
            # one who would retire as a free agent: the next update would retire him, and differ)
            swaps = 0
            for prow, ce in list(pool):
                if swaps >= max_swaps:
                    break
                if P.get(prow, 'dnFq') + 1910 < rising_star_born:
                    continue
                same = [e for e in members if e not in added and group(self.prow_of_entry(e)) == group(prow)
                        and not self.would_retire(self.pid_of_entry(e))]
                if not same:
                    continue
                weakest = min(same, key=nq)
                if pq(prow) > nq(weakest) + 0.5:
                    name = R.name(self.prow_of_entry(weakest))
                    remove(weakest, f"replaced by {R.name(prow)}")
                    add(prow, ce, reason=f"rising star, replaces {name}")
                    swaps += 1
            self.fill_lines(t)

    def national_lines(self):
        changed = set(self.departures) | set(self.arrivals)
        for team in L.NATIONAL:
            ents = self.entries_on(team)
            if not ents:
                continue
            if team not in self.orig_slot_sets and team not in self.filled_now:
                # players but no line structure (a squad a community roster left unfinished): deal
                # lines from scratch, or the game would see a team that dresses nobody
                self.lines_from_scratch(team)
            elif team in self.orig_slot_sets and (team in changed or team in self.position_teams or not self.maintain
                                                  or self.mendable(team)):
                self.deal_again(team)

    def lines_from_scratch(self, team):
        """Deal every line slot of a team that has no structure of its own to copy (lines.py) and
        give it letters; a team too short to dress 20 keeps no lines."""
        try:
            lines.build_lines(self, team)
        except lines.NotEnoughPlayers:
            for e in self.entries_on(team):
                for f in self.flags + ['jZSh']:
                    self.U.set(e, f, 0)
            return
        self.set_letters(team)

    # --- goalie equipment ------------------------------------------------------------
    GEAR_PARTS = ('pads', 'blocker', 'trapper')

    @staticmethod
    def coloured(colour):
        """A gear colour that is not white, grey or black: red, green and blue 40 apart (a beige (166, 166, 122)) or a hue
        (sticks.hue_of: a dark green (24, 55, 47)). Every colour a goalie who stays would have changed (off_hue) is one,
        so a second run changes nothing."""
        from . import sticks
        return max(colour) - min(colour) >= 40 or sticks.hue_of(colour) is not None

    def real_equipment(self):
        """Real sock tucks, pant lengths, neck guards and tape for players the data pack's `equipment` part has (equipment.real_values):
        found from the record's own full name and birthdate alone (a name only is never enough: namesakes), so the next run
        finds the same players. Models, shoulder pads, jersey tuck and visor are never touched. Runs before the player's
        own choices (edits.apply), which win. Returns the number of players changed."""
        from . import equipment
        part = self.data.equipment
        if not part:
            return 0
        if self.real_gear is None:
            self.real_gear = {}
            for entry in part['players']:
                self.real_gear.setdefault((norm(entry['first']), norm(entry['last'])), []).append((tuple(entry['birth']), entry))
        P = self.P
        changed = 0
        for prow in range(P.cur_rec):
            first, last = P.get(prow, 'PedH'), P.get(prow, 'RMbQ')
            if not first or not last:
                continue
            shown = P.get(prow, 'dnFq') + 1910
            goalie = P.get(prow, 'aljv') == 4
            found = None
            for year in ((shown, shown - 10) if self.stale_years else (shown,)):
                birth = (year, P.get(prow, 'pLKJ') + 1, P.get(prow, 'iwsK') + 1)
                hits = [e for b, e in self.real_gear.get((norm(first), norm(last)), ()) if b == birth and bool(e.get('goalie')) == goalie]
                if len(hits) == 1:
                    found = hits[0]
                    break
            if found is None:
                continue
            kind = 'goalie' if goalie else 'skater'
            row = self.equipment_row(prow, kind)
            if row is None:
                continue
            table = self.R.f[equipment.KINDS[kind][0]]
            ok, _bad = equipment.clean(equipment.real_values(found, goalie), table, kind)
            changed += bool(equipment.write(table, row, ok, kind))
        return changed

    def goalie_gear(self, mend=True):
        """A goalie who changed club (or is new: a record taken over) wears his old club's colours:
        The game painted each goalie's pads, blocker and glove (exhibitiongoalieequipment) in his 2014
        team's colours on white. The coloured parts are painted in the new club's colours: the first
        colour becomes its primary, the second its secondary; white, grey and black stay (`coloured`). A goalie
        whose club did not change but who wears a colour his club does not (off_hue: the community roster moved Cooper
        Black to Charlotte in navy and gold) gets only those zones changed, each to the club's closest colour (a gold
        his club wears stays). Gear models the game cannot draw (plain blue) are swapped first (equipment.fix_models).
        Without `mend` (the Roster editor's edits alone) only goalies who changed team are painted. A second run changes
        nothing."""
        from . import equipment, sticks
        R, P, T = self.R, self.P, self.R.T
        swapped = equipment.fix_models(R) if mend else []
        if swapped:
            self.log.append(['ALL', 'summary', "equipment the game cannot draw (plain blue) swapped for a model it can",
                             len(swapped), ''])
        G = R.f['lVMf']
        rows = {G.get(i, 'zIBw'): i for i in range(G.cur_rec)}
        now = self.home_teams()
        worn = self.team_masks(G, rows, now)
        painted = masked = 0
        for pid, team in sorted(now.items()):
            prow = R.p_by_id.get(pid)
            if prow is None or P.get(prow, 'aljv') != 4 or pid not in rows:
                continue
            g = rows[pid]
            if self.orig_home.get(pid) == team and prow not in self.created:
                if not mend:
                    continue
                own = [c for c in sticks.team_colours(R, team) if sticks.hue_of(c) is not None]
                hues = [sticks.hue_of(c) for c in own]
                touched = False
                for part in self.GEAR_PARTS:
                    for z in range(1, 10):
                        names = [f"{part}zone{z}color_{c}" for c in 'rgb']
                        colour = tuple(G.get(g, n) for n in names)
                        if own and self.off_hue(colour, hues):
                            new = min(own, key=lambda o: sum((a - b) ** 2 for a, b in zip(colour, o)))
                            for n, v in zip(names, new):
                                G.set(g, n, v)
                            touched = True
                painted += touched
                continue
            masked += self.fit_mask(G, g, prow, team, worn)
            club = [tuple(T.get(team, f"{k}color_{c}") for c in 'rgb') for k in ('primary', 'secondary')]
            order = []          # the gear's own colours, in the order they first appear
            for part in self.GEAR_PARTS:
                for z in range(1, 10):
                    colour = tuple(G.get(g, f"{part}zone{z}color_{c}") for c in 'rgb')
                    if self.coloured(colour) and colour not in order:
                        order.append(colour)
            if not order:
                continue
            for part in self.GEAR_PARTS:
                for z in range(1, 10):
                    colour = tuple(G.get(g, f"{part}zone{z}color_{c}") for c in 'rgb')
                    if colour in order:
                        for c, v in zip('rgb', club[order.index(colour) % 2]):
                            G.set(g, f"{part}zone{z}color_{c}", v)
            painted += 1
        self.gear_painted = painted
        if painted:
            self.log.append(['ALL', 'summary', "goalie equipment painted in the new club's colours",
                             f"{painted} goalies", ''])
        if masked:
            self.log.append(['ALL', 'summary', "goalies who changed club wear their new club's mask (or a plain one)",
                             f"{masked} goalies", ''])

    PLAIN_MASKS = (120, 125)        # masks with no club's look: plain white, plain black

    def team_masks(self, G, rows, now):
        """{team: its own mask number} (masktype 0): an NHL team's art id 0-29 (mask n is NHL art n's; not Utah's 22, which
        is Arizona's coyote), else the mask most of the team's goalies who did not move wear, when no other team's goalies
        wear it (Seattle, Vegas, the clubs). A team with none is missing."""
        from . import equipment
        T, code = self.R.T, equipment.GOALIE_CODE
        counts, teams_of = {}, {}
        for pid, team in now.items():
            prow = self.R.p_by_id.get(pid)
            if prow is None or pid not in rows or self.orig_home.get(pid) != team or prow in self.created:
                continue
            g = rows[pid]
            if G.get(g, code[equipment.MASK_TYPE]) != 0:
                continue
            mask = G.get(g, code['maskid'])
            counts.setdefault(team, Counter())[mask] += 1
            teams_of.setdefault(mask, set()).add(team)
        out = {}
        for team in set(now.values()):
            art = T.get(team, 'artid')
            if team in L.NHL_ALL and 0 <= art < 30 and art != 22:
                out[team] = art
                continue
            mine = [(n, -mask) for mask, n in (counts.get(team) or {}).items()
                    if teams_of[mask] == {team} and mask not in self.PLAIN_MASKS]
            if mine:
                out[team] = -max(mine)[1]
        return out

    def fit_mask(self, G, g, prow, team, worn):
        """A goalie who changed club or took over a record kept the mask of the record's old holder (a red European club's
        on Swayman in Boston): he gets his new club's (`team_masks`), else plain white. A mask that fits already (the
        club's own, a plain one), another mask type and a mask the player chose (edits) stay. True when it changed."""
        from . import equipment
        code = equipment.GOALIE_CODE
        if G.get(g, code[equipment.MASK_TYPE]) != 0 or 'mask' in getattr(self, 'equipment_set', {}).get(prow, ()):
            return False
        mask = G.get(g, code['maskid'])
        if mask in getattr(self, 'mask_looks', {}) or mask in self.PLAIN_MASKS or mask == worn.get(team):
            return False
        G.set(g, code['maskid'], worn.get(team, self.PLAIN_MASKS[0]))
        return True

    # --- contracts -----------------------------------------------------------------
    def players_team(self, team):
        """Free editing (pipeline.build sets `free` before contracts()): is `team` the player's to leave as his edits made
        it? True for an edit-only save; else a team the edits named, or one an edited player is on or was on."""
        free = getattr(self, 'free', None)
        if free is True or not free:
            return bool(free)
        rows, slots = free
        if team in slots:
            return True
        pids = {self.P.get(r, 'zIBw') for r in rows}
        return (any(self.pid_of_entry(e) in pids for e in self.entries_on(team))
                or any(team in self.orig_clubs.get(p, ()) for p in pids))

    def repair_lineups(self):
        """The last look at the line-ups, after every step that moves players (contracts() starts with it, so the
        players brought in get their contracts): each team that must dress a legal 20 (verify's line-up rule) and
        does not, by its players' real positions, gets the players it misses and its lines dealt again. NHL teams:
        call_ups, then deal_again; the clubs a league step rebuilt (rebuilt_clubs) and, on a game-patch roster,
        Coachella Valley and Henderson: clubs._fill_lineup (a prospect-pool player or a free agent), then
        lines.build_lines; the national teams this run changed: deal_again. Nothing to do on most updates.
        Returns the teams whose lines were dealt again."""
        from .leagues import clubs
        from .pipeline import LEAGUE_NAMES, SECTION_NATIONAL, SECTION_NHL
        U, section = self.U, self.log.section
        self.log.section = SECTION_NHL
        came = self.call_ups()
        mended = [t for t in sorted(L.NHL_PRIMARY) if self.mendable(t)]
        for team in mended:
            self.deal_again(team)
        if came or mended:
            self.sync_mirrors()
        slots = dict(self.rebuilt_clubs)
        if self.money == pay.REAL:          # a game-patch roster: its Coachella Valley and Henderson play the farm league
            for slot in L.AHL_PARENT_EXTRA:
                slots.setdefault(slot, 'ahl')
        live, by_team = None, {}
        for e in range(U.cur_rec):
            if e not in self.deleted and U.get(e, 'BSXd') in slots:
                by_team.setdefault(U.get(e, 'BSXd'), []).append(e)
        for slot, key in sorted(slots.items()):
            ents = by_team.get(slot, []) if live is None else self.entries_on(slot)    # (a club mended moves players)
            if not ents or not lines.lineup_flaws(self, slot, ents) or self.players_team(slot):
                continue
            live = self.live_entries() if live is None else live
            self.log.section = LEAGUE_NAMES.get(key, section)
            before = set(self.entries_on(slot))
            letters = {e: lines.LETTERS[U.get(e, 'lcCm')] for e in before if U.get(e, 'lcCm') in lines.LETTERS}
            clubs._fill_lineup(self, slot, {}, live, self.R.T.get(slot, 'nnsx'), Counter(), clubs.JUNIOR_AGE.get(key))
            taken = Counter(U.get(e, 'tRVs') for e in before)
            for e in self.entries_on(slot):         # the ones who came: their number when free, else the lowest free one
                if e not in before:
                    n = U.get(e, 'tRVs')
                    if not n or taken[n]:
                        n = next(x for x in range(2, 99) if not taken[x])
                        U.set(e, 'tRVs', n)
                    taken[n] += 1
            have = self.kinds_on(slot)
            if any(have[g] < n for g, n in clubs.CORE.items()):
                continue                            # nobody left to fill in: as the league step leaves such a club
            lines.build_lines(self, slot)
            clubs._letters(self, slot, letters)
            mended.append(slot)
        if self.data.club_lines:            # last, when no step moves a player any more: the real lines of the clubs
            self.real_club_lines(slots)
        for slot, letters in sorted(self.feed_letters.items()):    # every club of a league that ran: its own captains
            if letters:
                self.real_letters(slot, {self.prow_of_entry(e): v for e, v in sorted(letters.items())})
        self.log.section = SECTION_NATIONAL
        for team in sorted(L.NATIONAL & (set(self.departures) | set(self.arrivals) | self.position_teams)):
            if self.mendable(team):
                self.deal_again(team)
                mended.append(team)
        self.national_letters(self.filled_now & L.NATIONAL)   # after the clubs' and the NHL's captains are this season's
        self.log.section = section
        return mended

    def contracts(self):
        """Keep each player's contract team (cPbu.team = team + 1) on a team he is actually on.

        The game walks a team's contracts on screens like Team Management; a contract that
        points at a player who is not on that roster makes it crash. First the line-ups get what
        they miss (repair_lineups)."""
        self.unlist_club_players()      # nobody on a club and on the free-agent list (verify 'fa on team')
        self.repair_lineups()
        P, R = self.P, self.R
        final = self.club_teams()
        fa = {R.link_to_pid.get(l) for l in self.fa_links}
        stats = Counter()
        for pid in set(self.orig_club) | set(final):
            if self.orig_club.get(pid, set()) == final.get(pid, set()):
                continue
            prow = R.p_by_id.get(pid)
            if prow is None:
                continue
            teams = final.get(pid, set())
            nhl = sorted(t for t in teams if t in L.NHL_PRIMARY)
            if nhl:
                P.set(prow, 'BSXd', nhl[0] + 1)
                if prow in self.created or not P.get(prow, 'GDhI') or not P.get(prow, 'dhKk'):
                    years, cap = pay.default_terms(P.get(prow, 'dnFq') + 1910 >= self.data.season_year - 22, self.money)
                    P.set(prow, 'GDhI', years)
                    P.set(prow, 'dhKk', cap)
                    P.set(prow, 'IrlK', 0)
                    P.set(prow, 'IzRv', 0)
                    stats['new contract'] += 1
                stats['contract team -> NHL'] += 1
            elif teams:
                P.set(prow, 'BSXd', min(teams) + 1)
                stats['contract team -> AHL'] += 1
            elif pid in fa:
                for f in ('BSXd', 'GDhI', 'dhKk', 'IrlK', 'IzRv'):
                    P.set(prow, f, 0)
                stats['free agent, contract cleared'] += 1
        # sweep: any contract that now points at a team the player left (e.g. national-team-only
        # European players dropped from their national team) moves to a team he is on, or is cleared
        U = self.U
        on = {}
        for i in range(U.cur_rec):
            if i not in self.deleted:
                on.setdefault(self.pid_of_entry(i), set()).add(U.get(i, 'BSXd'))
        clubs = pay.contract_clubs(R)
        for pid, prow in R.p_by_id.items():
            b = P.get(prow, 'BSXd')
            if not b or pid in self.orig_contract_bad:
                continue
            teams = on.get(pid, set())
            if self.same_team(b - 1) & teams:
                continue
            if teams:                                   # his club before a national team (the deal is the club's)
                P.set(prow, 'BSXd', min(teams & clubs or teams) + 1)
                stats['contract team -> current team'] += 1
            else:
                for f in ('BSXd', 'GDhI', 'dhKk', 'IrlK', 'IzRv'):
                    P.set(prow, f, 0)
                stats['no team left, contract cleared'] += 1
        # free agents carry no contract (club players released by a league step may still have one;
        # the NHL rights in proteam stay)
        for link in self.fa_links:
            prow = R.p_by_id.get(R.link_to_pid.get(link))
            if prow is not None and any(P.get(prow, f) for f in ('BSXd', 'GDhI', 'dhKk', 'IrlK', 'IzRv')):
                for f in ('BSXd', 'GDhI', 'dhKk', 'IrlK', 'IzRv'):
                    P.set(prow, f, 0)
                stats['free agent, contract cleared'] += 1
        for k, v in sorted(stats.items()):
            self.log.append(['ALL', 'contracts', k, f"{v} players", ''])

    def real_contracts(self):
        """Every player on a club (any league: an NHL prospect in Europe or the CHL too) who holds an NHL contract (data
        pack `contracts`) gets that deal: cap hit, seasons left, two-way, an extension, on the roster's money scale
        (contracts.py), and the rights of the NHL team he signed with when he is on none and nobody holds them (a
        prospect a league's list leaves out keeps his club). After contracts(): free agents hold none and are left alone, and so is everyone the contracts do
        not name. The values are written whole, so a second run writes the same; "given" counts the deals that differ
        from the source's (an AHL step's two-way flag written over is no change). Returns {what: number of players} for
        the list of changes."""
        if not self.data.contracts:
            return {}
        P, R = self.P, self.R
        on = self.club_teams(pay.contract_clubs(R))
        stats, done = Counter(), set()
        people = match(R, [dict(d, birth=tuple(d['birth'])) for d in self.data.contracts])
        for d in people:
            prow = d['row']
            if prow is None:
                stats['not in this roster'] += 1
                continue
            if prow in done:
                continue
            done.add(prow)
            pid = P.get(prow, 'zIBw')
            if not on.get(pid):
                stats['not on a club here'] += 1
                continue
            pay.write(P, prow, d, self.money)
            org = L.API_TO_SLOT.get(d.get('org'))
            if (org is not None and not P.get(prow, 'WBbd') and not on[pid] & L.NHL_PRIMARY
                    and pay.holds_rights(P, org)):      # his NHL team's deal: its rights (Seattle's / Vegas's: patch rosters)
                P.set(prow, 'WBbd', org + 1)
                stats['rights given to the team he signed with'] += 1
            if tuple(P.get(prow, f) for f in pay.FIELDS) != self.orig_deals.get(pid):
                stats['given their real contract'] += 1
            else:
                stats['real contract already'] += 1
        scale = ("real dollars (the game patch raises the cap)" if self.money == pay.REAL else
                 f"the game's cap: dollars x {self.money:.4f}")
        self.log.append(['ALL', 'summary', "2026-27 contracts", scale, ''])
        for k, v in sorted(stats.items()):
            self.log.append(['ALL', 'contracts', f"2026-27: {k}", f"{v} players", ''])
        cap = pay.CAP * self.money                          # the cap the game shows, in the save's own dollars
        for t in sorted(L.NHL_PRIMARY):
            total = pay.payroll(R, t, pay.REAL)                 # REAL: the save's dollars as they stand
            self.log.append([L.SLOT_TO_API[t], 'payroll', f"${total / 1e6:.2f}M", f"cap ${cap / 1e6:.2f}M", ''])
        self.real_deals = dict(stats)
        return dict(stats)

    def starter_contracts(self, everyone=True):
        """A made-up starter deal (owner, 2026-10-22; contracts.starter_terms: by the club's league and his overall,
        one-way, one season from 27 on, else two) for every player on a club who has no deal (cap hit and seasons) and
        whose rights no NHL team holds: an unsigned draft pick stays unsigned (a deal would be an NHL deal on his NHL
        team's cap in Be a GM; the game's own roster leaves them so). A player on an NHL team without a deal gets
        contracts.default_terms. The deal's team (cPbu.team) becomes the club when it points at no club he is on.
        After contracts() and real_contracts(), before the player's own contract edits (they win). `everyone` False:
        only players whose clubs changed in this run (the Roster editor's Save). A second run finds every deal in place.
        Returns {starter league or 'NHL': number of players}; `self.started`: their player ids."""
        P, R = self.P, self.R
        on = self.club_teams(pay.contract_clubs(R))
        fa = {R.link_to_pid.get(l) for l in self.fa_links}
        given = Counter()
        self.started = set()
        for pid in sorted(on):
            prow, teams = R.p_by_id.get(pid), on[pid]
            if prow is None or pid in fa or (P.get(prow, 'dhKk') and P.get(prow, 'GDhI')):
                continue
            if not everyone and self.orig_clubs.get(pid) == teams:
                continue
            nhl = sorted(teams & L.NHL_PRIMARY)
            born = P.get(prow, 'dnFq') + 1910
            if nhl:
                years, cap = pay.default_terms(born >= self.data.season_year - 22, self.money)
                values = {'dhKk': cap, 'GDhI': years, 'DVoL': 0, 'gHmt': int(years >= 2), 'IrlK': 0, 'IzRv': 0,
                          'xdoJ': 0}
                club, kind = nhl[0], 'NHL'
            elif P.get(prow, 'WBbd'):
                continue
            else:
                club = min(teams)
                values = pay.starter_terms(club, self.quality.get(pid, 0), self.data.season_year - born, self.money)
                kind = pay.starter_league(club)
            pay.put(P, prow, values)
            if P.get(prow, 'BSXd') - 1 not in teams:
                P.set(prow, 'BSXd', club + 1)
            given[kind] += 1
            self.started.add(pid)
        names = {'NHL': "NHL teams (the league minimum or an entry-level deal)", 'AHL': "AHL clubs (an AHL-only deal)",
                 'NL': "the National League", 'SHL': "the SHL and the DEL", 'LIIGA': "Liiga and the Extraliga",
                 'CHL': "the junior leagues", 'OTHER': "Norway and custom teams"}
        for kind in sorted(given):
            self.log.append(['ALL', 'contracts', f"starter deal: {names[kind]}", f"{given[kind]} players", ''])
        self.starter_deals = dict(given)
        return dict(given)

    def same_team(self, t):
        """A team and its mirror copies count as one team."""
        prim = self.mirror_of.get(t, t)
        return {prim} | set(self.mirrors.get(prim, []))
