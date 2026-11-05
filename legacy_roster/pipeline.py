"""One entry point for building an updated roster: used by the GUI, the CLI and the tests."""
import collections
import copy
import csv
import datetime
import os
import sys
import traceback
from collections import Counter

from . import contracts, datasource, draft, faces, gamepatch, restore, savedata, schedule, sticks, stock
from . import layout as L
from .builder import FREE_AGENTS, REPAIRS, Builder, Data, drop_removed_player
from .leagues import clubs, pools
from .roster import Roster
from .verify import verify

# what the user can tick; steps run in this order whatever order they are given in
NHL, RATINGS, NATIONAL = 'nhl', 'ratings', 'national'
CORE_STEPS = (NHL, RATINGS, NATIONAL)
# the game's calendar (schedule.py): the real schedule of the season, 30 teams; played by the owner on 2026-10-06 and on
# by default since (the year label stays 2015, Seattle and Vegas play Play Now only)
SCHEDULE = 'schedule'
# club leagues, available when the data pack has rosters for them
LEAGUE_ORDER = ('liiga', 'extraliga', 'shl', 'del', 'nl', 'norway', 'ahl', 'chl')
STEP_LABELS = {NHL: "NHL rosters, numbers, lines and captains",
               RATINGS: "Player ratings",
               NATIONAL: "National teams",
               'liiga': "Liiga: real clubs", 'extraliga': "Extraliga: real clubs", 'shl': "SHL: real clubs",
               'del': "DEL: real clubs", 'nl': "National League: real clubs", 'norway': "Norway: real clubs",
               'ahl': "AHL rosters", 'chl': "CHL (OHL / QMJHL / WHL)",
               SCHEDULE: "Calendar 2026-27"}
LEAGUE_NAMES = {'liiga': "Liiga", 'extraliga': "Extraliga", 'shl': "SHL", 'del': "DEL", 'nl': "National League",
                'norway': "Norway", 'ahl': "AHL", 'chl': "CHL (OHL / QMJHL / WHL)"}
# a club league's calendar (schedule.LEAGUES) is written with the calendar step and the step that fills its clubs
CALENDAR_STEP = {'ahl': 'ahl', 'shl': 'shl', 'liiga': 'liiga', 'del': 'del', 'extraliga': 'extraliga', 'nl': 'nl',
                 'ohl': 'chl', 'qmjhl': 'chl', 'whl': 'chl'}
# the parts of the update, as the change log tags its rows (builder.ChangeLog) and the list of changes groups them
SECTION_NHL, SECTION_RATINGS, SECTION_NATIONAL = "NHL", "Player ratings", "National teams"
SECTION_POOLS, SECTION_EDITS, SECTION_CONTRACTS = "Prospect pools", "My edits", "Contracts"
SECTION_STOCK = "The game's own roster"
SECTION_FREE_AGENTS, SECTION_PLAYER_DATA = FREE_AGENTS, "Player data"
SECTION_PICTURES = "Pictures not installed"
SECTION_REPAIRS = REPAIRS


def usable_clubs(R, league):
    """A league's clubs without those whose slot is a custom team that is switched off (the game's
    own roster has Coachella Valley's and Henderson's slots, 234 and 235, off): those clubs are left
    out, like clubs the game has no slot for."""
    off = [t for t in league['teams'] if R.T.get(t['slot'], 'league') == L.CUSTOM_LEAGUE and not R.T.get(t['slot'], 'NYKk')]
    if not off:
        return league
    out = dict(league)
    out['teams'] = [t for t in league['teams'] if t not in off]
    out['left_out'] = list(league.get('left_out') or []) + [t['full'] for t in off]
    out['extra'] = list(league.get('extra') or []) + off       # for a player's own team of that name
    return out


def with_own_teams(R, league, taken, mirrors):
    """The league with the player's own custom teams named after its left-out clubs added
    (clubs.own_teams). `taken`: slots already used, grown by the ones given out here."""
    own = clubs.own_teams(R, league, taken, mirrors)
    taken.update(t['slot'] for t in league['teams'])
    if not own:
        return league
    taken.update(t['slot'] for t in own)
    return dict(league, teams=list(league['teams']) + own)


def vees_club(league):
    """The Penticton Vees among a league's clubs without a slot of their own in the data pack, or None."""
    return next((c for c in league.get('extra') or [] if c.get('art') == 'PEN' and c.get('players')), None)


def with_vees(R, league, taken, mirrors, listed=True):
    """The CHL with the Penticton Vees in their own slot (layout.VEES): the club the data pack lists under `extra` goes
    into `teams`, its slot switched on. A player's own team named after them keeps them (clubs.own_teams), and a slot that
    already holds something else stays as it is, so the Vees stay a club without a slot. A prospect pool is no such thing:
    a full update fills all 16 spare slots, so a roster updated before the Vees has one there; the league step moves it
    out as it does for a pool in a European club's slot. `listed` False: the game could never list them (layout.listed),
    a new Vees stays out, as Coachella Valley and Henderson do on such a roster (usable_clubs)."""
    club = vees_club(league)
    if club is None:
        return league
    T = R.T
    if not L.is_vees(T) and not listed:
        return league
    if not L.is_vees(T):
        busy = T.get(L.VEES, 'NYKk') or any(R.U.get(e, 'BSXd') == L.VEES for e in range(R.U.cur_rec))
        if ((busy and not pools.is_pool(R, L.VEES)) or L.VEES in taken
                or any(c['art'] == 'PEN' for c in clubs.own_teams(R, league, taken, mirrors))):
            return league
        T.set(L.VEES, 'NYKk', 1)
    taken.add(L.VEES)
    return dict(league, teams=list(league['teams']) + [dict(club, slot=L.VEES, short='Penticton')],
                left_out=[name for name in league.get('left_out') or [] if name != club['full']],
                extra=[c for c in league['extra'] if c is not club])


def section_of(row):
    """The part of the update a change-log row belongs to ('' for rows made outside build())."""
    return row[5] if len(row) > 5 else ''
# steps that pass every check here but still wait for the owner's check in the game (docs/ROADMAP.md);
# the window no longer marks them and they are on by default like the rest (owner, 2026-10-04).
# Liiga and Extraliga were confirmed in the game on 2026-10-03.
# 'stock' is starting from the game's own roster (stock.py), 'positions' NHL.com's positions and wing
# sides on the lines, 'favourite logos' the reflection logos (art/install.REFLECTION), all new in 0.6.0.
# New in 0.8.0: 'free agents' (retired ones go, unsigned NHL players come), 'goalie gear' (painted in
# the new club's colours), 'draft' (real draft data), 'own teams' (a player's own team named after a
# club the game has no slot for gets its players). The calendar left this list on 2026-10-06: the owner played it.
# New on 2026-10-16: 'type and face edits' (the Roster editor), 'contracts' (the real 2026-27 deals, contracts.py).
# New on 2026-10-18: 'current ratings' (the current ratings, player types and tendencies for every player they have,
# Builder.rate_full, docs/notes/full-ratings.md).
# New on 2026-10-18 (0.21.0): 'team sticks' (sticks.team_sticks), 'nhl gear' (Builder.nhl_gear on the right rows),
# 'puck peak texts' (loc.PROMO) and 'hidden menus' (art/menus.py), both installed with the photos.
# New in 0.30.0: 'gear colours' (Builder.club_gear, goalie_gear for goalies in colours their club does not wear,
# equipment.fix_models for gear the game draws plain blue), 'jerseys every league' (art/looks.py: the Roster editor's
# jerseys for every league, this season's home and away only) and 'own art ids' (Coachella Valley / Henderson: 20073 / 20081 on
# every roster, their colours layout.OWN_KIT and the crests art/crests.py installs with the photos).
# 'farm clubs in the AHL' (2026-10-19, lab round 35): Coachella Valley / Henderson in the AHL's league on patch rosters
# (gamepatch.league_fit, stage Y, the Be a Pro word 0x458ec8) and the text keys hashed the game's way (loc.key_hash).
# New in 0.31.0: 'custom team kits' (the Roster editor's look of a custom team: designs, colours, crest pictures on a
# free create-a-team logo; custom_kit.py, lab round 37) and 'shared ice' (a picture on the centre ice the national teams,
# the DEL or EASHL share: looks.ice_group).
# New on 2026-10-20: 'picture numbers' (portraits.Claims / forget_conflicts: no picture number another roster on this PC
# uses for someone else; a photo that cannot be made keeps the old picture) and 'own pictures on save' (the player's own
# pictures go into the game on the Roster editor's Save and on every update, also with Photos off: pipeline.Pictures).
# Left the list on 2026-10-21 (lab round 41): 'contracts' and 'contract edits' (0.50.0: a contract set by hand in the Front
# office, edits.apply_contracts after the real deals): Team Rosters, a new Be a GM's Contract Status and Be a Pro Central
# show the real and the edited deals, with the contract status (contracts.status_fit) and UFA year (ufa_fit) fitted.
# New on 2026-10-22: 'draft classes' (the player's made-up prospects on European / CHL clubs with a potential the game
# keeps: draftclass.py, lab round 44) and 'new player records' (records held for the player's new players before the
# leagues' depth players: edits.records_needed).
# 'league calendars' (2026-10-22): the real season of the AHL (unpatched game), SHL, Liiga, DEL, Extraliga, National League,
# OHL, QMJHL and WHL in their own tables (schedule.apply_league). Left the list on 2026-10-23 (lab round 46): Season mode
# played the roster's own DEL, SHL and OHL tables on the patched game and the AHL's on the unpatched one, game for game.
EXPERIMENTAL = {'shl', 'del', 'nl', 'norway', 'ahl', 'chl', 'stock', 'positions', 'favourite logos',
                'free agents', 'goalie gear', 'draft', 'own teams', 'type and face edits',
                'current ratings', 'team sticks', 'nhl gear', 'puck peak texts', 'hidden menus',
                'own art ids', 'jerseys every league', 'gear colours', 'farm clubs in the AHL',
                'custom team kits', 'shared ice', 'picture numbers', 'own pictures on save',
                'draft classes', 'new player records', 'no press start', 'real lines', 'club art 900',
                'real captains', 'real equipment', 'new centre ice', 'alternate jerseys'}
ALL_STEPS = CORE_STEPS      # what build() and update() run when no steps are given


def steps_for(pack):
    """The steps this data pack can serve, in running order."""
    return list(CORE_STEPS) + [k for k in LEAGUE_ORDER if k in pack.get('leagues', {})] + (
        [SCHEDULE] if pack.get('schedule') else [])


def default_steps(pack):
    """What is switched on unless the user chooses: everything the pack serves."""
    return steps_for(pack)


def planned(pack):
    """Names of the leagues the game has that cannot be updated with this data pack."""
    return [LEAGUE_NAMES[k] for k in LEAGUE_ORDER if k not in pack.get('leagues', {})]


def left_out_note(pack, step):
    """A short line naming a league's clubs the game has no team slot for (None when all fit)."""
    league = pack.get('leagues', {}).get(step) or {}
    vees = vees_club(league)
    clubs = [name for name in league.get('left_out') or [] if not vees or name != vees['full']]
    if not clubs:
        return None
    if len(clubs) <= 3:
        return "No slot in the game for " + ", ".join(clubs)
    return f"The game has slots for only some clubs: {len(clubs)} are left out"


class BuildResult:
    def __init__(self, data, log, problems, info, builder):
        self.data = data            # bytes of the new SYS-DATA
        self.log = log              # [[team, change, player, detail, number]]
        self.problems = problems    # integrity problems; the save must not be installed if any
        self.info = info
        self.builder = builder
        self.turned_back = False    # made from a roster for the patched game, for the unpatched game (build)

    @property
    def ok(self):
        return not self.problems

    def _counts(self):
        return Counter(r[1] for r in self.log if section_of(r) in (SECTION_NHL, SECTION_NATIONAL))

    def lines(self):
        """What each part of the update did, one (title, text) per part, for the window and the
        list of changes: ('NHL', '124 changed teams, 201 joined, 127 left')."""
        c = self._counts()
        out = []
        if c['moved'] or c['added'] or c['left NHL roster'] or c['created'] or c['farm under contract']:
            joined = f"{c['added'] + c['created']} joined" + (f" ({c['created']} new)" if c['created'] else "")
            kept = f", {c['stays under contract']} kept under contract" if c['stays under contract'] else ""
            kept += f", {c['farm under contract']} to their farm club (under contract)" if c['farm under contract'] else ""
            out.append((SECTION_NHL, f"{c['moved']} traded, {joined}, {c['left NHL roster']} left{kept}"))
        if getattr(self.builder, 'positions_changed', 0):
            out.append(("Positions", f"{self.builder.positions_changed} NHL players moved to NHL.com's position"))
        retired, signable, new = self.free_agent_counts()
        if retired or signable:
            out.append((SECTION_FREE_AGENTS, f"{retired} retired, {signable} unsigned NHL "
                        f"player{'s' if signable != 1 else ''} added" + (f" ({new} new)" if new else "")))
        if any(self.rating_sources()):
            out.append((SECTION_RATINGS, self.ratings_text()))
        if c['national team: added'] or c['national team: removed']:
            text = f"{c['national team: added']} players added"
            if c['national team: removed']:
                text += f", {c['national team: removed']} removed"
            out.append((SECTION_NATIONAL, text))
        empty = [r[2] for r in self.log if r[1] == 'national team: left empty']
        if empty:
            out.append(("Left empty", f"{', '.join(empty)} (not enough players of that country)"))
        for key, s in self.builder.league_stats.items():
            placed = s.get('moved', 0) + s.get('added', 0) + s.get('created', 0)
            if not placed and not s.get('left'):
                out.append((LEAGUE_NAMES[key], "already up to date"))
                continue
            text = f"{placed} placed" + (f" ({s['created']} new)" if s.get('created') else "")
            if s.get('left'):
                text += f", {s['left']} left"
            if s.get('skipped: no free record'):
                text += f", {s['skipped: no free record']} skipped (no room)"
            out.append((LEAGUE_NAMES[key], text))
        if getattr(self.builder, 'repairs', 0):
            out.append((SECTION_REPAIRS, f"{self.builder.repairs} put right that the update had left wrong"))
        if getattr(self.builder, 'pool_released', 0):
            out.append((SECTION_POOLS, f"{self.builder.pool_released} without room, now free agents"))
        for club, team in getattr(self.builder, 'own_teams', ()):
            out.append(("Your own team", f"{team} got {club}'s players"))
        edited = sum(1 for r in self.log if r[1] in ('edited', 'team edited', 'created') and section_of(r) == SECTION_EDITS)
        if edited:
            out.append((SECTION_EDITS, f"{edited} of your changes applied"))
        data = [f"{n} {what}" for n, what in ((getattr(self.builder, 'drafted', 0), "real drafts"),
                                               (getattr(self.builder, 'gear_painted', 0), "goalies' gear repainted"))
                if n]
        if data:
            out.append((SECTION_PLAYER_DATA, ", ".join(data)))
        held, real = self.real_deals()
        if held:
            out.append(("Contracts", f"{held} players hold their real 2026-27 deal"
                        + (" (real dollars)" if real else " (scaled to the game's cap)")))
        lined = getattr(self.builder, 'real_lined', None)
        if lined:
            out.append(("Lines", f"{len(lined)} teams play the lines of their last games"))
        clubs_lined = getattr(self.builder, 'club_lined', None)
        if clubs_lined:
            out.append(("Club lines", f"{len(clubs_lined)} clubs play their real lines"))
        lettered = getattr(self.builder, 'lettered', None) or set()
        national = getattr(self.builder, 'national_lettered', None) or set()
        if lettered or national:
            nhl = len(lettered & set(L.NHL_PRIMARY))
            parts = [f"{nhl} NHL teams" if nhl else '', f"{len(lettered) - nhl} clubs" if len(lettered) > nhl else '']
            text = " and ".join(p for p in parts if p)
            text = f"{text} wear this season's letters" if text else ''
            if national:
                text += (", " if text else '') + f"{len(national)} national teams are led by their players' own captains"
            out.append(("Captains", text))
        starters = sum((getattr(self.builder, 'starter_deals', None) or {}).values())
        if starters:
            out.append(("Starter deals", f"{starters} player{'s' if starters != 1 else ''} without a contract got one "
                                         "with their club"))
        cal = getattr(self.builder, 'calendar', None)
        if cal:
            out.append(("Calendar", f"{cal['games']} games, {cal['first']} to {cal['last']} ({cal['variant']})"))
        leagues = getattr(self.builder, 'league_calendars', None) or {}
        if leagues:
            out.append(("League calendars", ", ".join(f"{schedule.LEAGUE_LABELS[p]} {c['games']}"
                                                      for p, c in sorted(leagues.items())) + " games"))
        kept = getattr(self.builder, 'calendars_kept', None)
        if kept:
            out.append(("League calendars", "kept as they were: " + ", ".join(kept)))
        for line in (self.info or {}).get('heads_up') or []:       # free editing: saved, but the game hangs with it
            out.append(("Heads up", line))
        return out

    def rating_sources(self):
        """(players rated from the full ratings, from the ratings list, estimated) in this update (Builder.rating_counts)."""
        return getattr(self.builder, 'rating_sources', None) or (0, 0, 0)

    def ratings_text(self):
        full, listed, estimated = self.rating_sources()
        return f"{full + listed} current, {estimated} estimated"

    def free_agent_counts(self):
        """(players who retired, unsigned NHL players made free agents, of them new to the game)."""
        retired = sum(1 for r in self.log if r[1] == 'free agent retired'
                      or (r[1] in ('left NHL roster', 'left the club') and r[3] == 'retired'))
        added = [r for r in self.log if r[1] == 'free agent added']
        return retired, len(added), sum(1 for r in added if 'new to the game' in str(r[3]))

    def real_deals(self):
        """(players who hold the real 2026-27 contract after the update, True when in real dollars)."""
        s = getattr(self.builder, 'real_deals', None) or {}
        held = s.get('given their real contract', 0) + s.get('real contract already', 0)
        return held, getattr(self.builder, 'money', contracts.GAME) == contracts.REAL

    def headline(self):
        """The size of each step's work on one line (the sentences are in summary())."""
        return "   |   ".join(f"{title}: {text}" for title, text in self.lines()) or "Nothing needed changing."

    def summary(self):
        """A few plain sentences about what changed."""
        c = self._counts()
        lines = []
        if c['moved'] or c['added'] or c['left NHL roster'] or c['created']:
            lines.append(f"NHL: {c['moved']} players changed teams, {c['added']} joined an NHL roster, "
                         f"{c['left NHL roster']} left, {c['created']} new players created.")
        if getattr(self.builder, 'positions_changed', 0):
            lines.append(f"Positions: {self.builder.positions_changed} NHL players now play the position NHL.com lists.")
        if any(self.rating_sources()):
            lines.append(f"Ratings: {self.ratings_text()}.")
        for key, s in self.builder.league_stats.items():
            moved = s.get('moved', 0) + s.get('added', 0)
            if not moved and not s.get('created') and not s.get('left'):
                lines.append(f"{LEAGUE_NAMES[key]}: the clubs were already up to date.")
                continue
            placed = moved + s.get('created', 0)
            text = (f"{LEAGUE_NAMES[key]}: {placed} player{'s' if placed != 1 else ''} placed on their clubs "
                    f"({s.get('created', 0)} of them new to the game)")
            if s.get('left'):
                text += f", {s['left']} left"
            if s.get('pool players moved'):
                text += f"; {s['pool players moved']} prospect-pool players moved to custom teams"
            if s.get('skipped: no free record'):
                text += f"; {s['skipped: no free record']} skipped, no free player record left"
            lines.append(text + ".")
        if getattr(self.builder, 'repairs', 0):
            n = self.builder.repairs
            lines.append(f"Repairs: {n} thing{'s' if n != 1 else ''} the update had left wrong put right "
                         "(the List of changes says which).")
        if getattr(self.builder, 'pool_released', 0):
            lines.append(f"Prospect pools: no room left for {self.builder.pool_released} players; "
                         "they are free agents now and can be signed.")
        if c['national team: added'] or c['national team: removed']:
            lines.append(f"National teams: {c['national team: added']} players added, {c['national team: removed']} removed.")
        empty = [r[2] for r in self.log if r[1] == 'national team: left empty']
        if empty:
            lines.append(f"National teams left empty, not enough players of that country found: {', '.join(empty)}.")
        retired, signable, new = self.free_agent_counts()
        if retired or signable:
            lines.append(f"Free agents: {retired} player{'s' if retired != 1 else ''} retired; {signable} NHL "
                         f"player{'s' if signable != 1 else ''} without a contract can be signed ({new} of them new to "
                         "the game).")
        held, real = self.real_deals()
        if held:
            lines.append(f"Contracts: {held} players hold their real 2026-27 contract, "
                         + ("in real dollars (the game patch raises the salary cap to $104M)." if real else
                            "scaled to the game's own salary cap of $71.4M."))
        starters = sum((getattr(self.builder, 'starter_deals', None) or {}).values())
        if starters:
            lines.append(f"Starter deals: {starters} player{'s' if starters != 1 else ''} on a club got a made-up "
                         "contract with it (they had none); change any of them in Front office.")
        if not lines:
            lines.append("Nothing needed changing.")
        return lines


def build(source, data, steps=ALL_STEPS, progress=None, check=True, art_registry=None, my_edits=None,
          team_edits=None, calendar_from=None, game_patch=False, normal_from=None, art=None):
    """Build an updated roster from `source` (path or bytes of a SYS-DATA).

    `data` is a builder.Data; `steps` the steps to run (see steps_for()). `my_edits` and
    `team_edits` are the player's own edits of players and teams (edits.py), applied last. With `art_registry` (an art.portraits.Registry:
    photos and logos are on) the placed players get portrait ids and the result's `art` lists the
    pictures to install; `art` (a Pictures, for this PC's RPCS3) does the same with what the PC knows: numbers other
    rosters use, photos that make no picture, only the player's own pictures. `calendar_from` (a Roster: the game's own) puts that roster's calendar back. `game_patch`: the
    roster is for the game patch (patch_roster follows): the players' rights get six bits (gamepatch.rights_wide), so
    Henderson's players hold Vegas's, and Coachella Valley and Henderson are filled on the game's own roster too. Without it a roster made for the patch is
    turned back into one for the unpatched game (gamepatch.unpatch_roster) with `normal_from` (a Roster: the game's own
    roster, restore.default_slot)."""
    say = progress or (lambda msg: None)
    steps = set(steps)
    if isinstance(source, (bytes, bytearray)):
        src_bytes = bytes(source)
    else:
        with open(source, 'rb') as f:
            src_bytes = f.read()
    R = Roster(src_bytes)
    kind = L.check_base(R)
    patched = gamepatch.is_patch_roster(R)
    turned_back = False
    if patched:                         # made for the game patch: its years back to ours first (patch_roster again)
        gamepatch.unshift(R)
        gamepatch.unleague(R)           # Coachella Valley / Henderson in the Custom league, as the builder knows them
        gamepatch.unart(R)              # and with their create-a-team art ids
        if not game_patch:              # for the unpatched game: the game's own calendars, room and section back
            if normal_from is None:
                raise L.LayoutError("This roster was made for the patched game. To make it a roster for the unpatched "
                                    "game the program needs the game's own roster: start the game once from RPCS3.")
            say("Turning the roster for the patched game back into one for the unpatched game")
            gamepatch.unpatch_roster(R, normal_from)
            src_bytes = R.f.build()     # the checks compare the new roster with this
            turned_back = True
    if game_patch:                      # Vegas's rights fit: its farm players are Henderson's, as every farm club's
        gamepatch.rights_wide(R)
    if game_patch and kind == L.STOCK:  # the patched Season's farm clubs of Seattle and Vegas (gamepatch.FARM_SLOTS)
        for slot in gamepatch.FARM_SLOTS[30:]:
            R.T.set(slot, 'NYKk', 1)
    prepared = []
    # the game's own roster with edits only (the Roster editor's Save, no update step): it stays the game's 2014 roster,
    # All-Star teams and birth years as the disc has them; stock.prepare is for an update, which fills Seattle and Vegas
    as_disc = kind == L.STOCK and not steps and not game_patch and not stock.prepared(R)
    if kind == L.STOCK and not as_disc:     # the game's own roster: made updatable first (stock.py)
        prepared = stock.prepare(R, data.season_year)
        if prepared:
            say("The game's own roster: making room for today's players")
    if my_edits:
        from . import edits
        edits.restore(R, my_edits)      # renamed players carry their real names through the update
        R.reindex()
    gone = drop_removed_player(R)       # a player the game's own save left behind (Season mode crashed on him)
    if gone:
        say(f"Taking off {gone}, whom the game had already removed")
    # a patch roster's years were mended (year_shift); one turned back is read as every normal roster is, so that
    # updating it again sees what this run saw
    stale = kind == L.COMMUNITY and (not patched or turned_back)
    if game_patch and stale:            # its first update starts from mended years too: a second run then sees the same
        gamepatch.mend_years(R)
        stale = False
    money = contracts.scale_of(game_patch)          # real dollars for the game patch, else the game's cap's scale
    rescaled = contracts.rescale(R.P, money / contracts.scale_of(patched)) if money != contracts.scale_of(patched) else 0
    drafts = draft.Drafts(data.drafts, data.season_year, stale=stale)
    drafted = draft.apply(R, drafts, data.season_year)     # before the builder looks at anyone's age
    b = Builder(R, data, progress=say, layout=kind, stale=stale)
    b.money = money
    if getattr(R, 'stale_markers', False):      # a roster made by 0.8.0 from the community roster (see builder)
        say(f"Giving the {b.relink_free_agents()} free agents new links")
    if prepared:
        b.maintain = False              # its national teams are 2014's: brought up to date like a first run
    log = b.log                         # each change is tagged with the part of the update it belongs to
    log.section = SECTION_STOCK
    for what, detail in prepared:
        log.append(['ALL', 'summary', what, detail, ''])
    if rescaled:
        log.append(['ALL', 'summary', "contracts moved to " + ("real dollars" if money == contracts.REAL else
                                                                "the game's cap"), f"{rescaled} players", ''])
    identity = b.nhl_identity() if (kind == L.STOCK and not as_disc) or NHL in steps else 0
    if identity:
        log.append(['ALL', 'summary', "arena names and colours of the NHL teams", f"{identity} teams", ''])
    farm_arenas = b.ahl_identity() if 'ahl' in steps else 0
    if farm_arenas:
        log.append(['ALL', 'summary', "arenas of the AHL clubs", f"{farm_arenas} clubs", ''])
    if NHL in steps and b.nhl_gear(own=normal_from or calendar_from):
        log.append(['ALL', 'summary', "helmets and gear of Utah, Seattle and Vegas", "in their colours", ''])
    # the club leagues as they will be built (with the player's own teams named after left-out clubs):
    # their players' records are reserved from the start
    leagues = [key for key in LEAGUE_ORDER if key in steps and key in data.leagues]
    taken = set(L.MIRROR_OF) if b.mirrors else set()
    copies = set(L.MIRROR_OF) if b.mirrors else ()
    league_data = {}
    for key in leagues:
        league = usable_clubs(R, data.leagues[key])
        if key == 'chl':                # the game's own roster keeps 222-233 off: the unpatched lists never reach 251
            league = with_vees(R, league, taken, copies, listed=game_patch or kind != L.STOCK)
        league_data[key] = with_own_teams(R, league, taken, copies)
    if any(t['slot'] == L.VEES and not t.get('own') for t in league_data.get('chl', {}).get('teams', ())):
        b.vees_arena()
    if 'ahl' in league_data and league_data['ahl'].get('orgs'):
        # this season's farm pairs before anything counts on them (the NHL step's call-ups, the retiring of old players,
        # the AHL step): with the game's own 2014 pairs the retiring kept a player the AHL step then let go
        clubs.pair_farms(R, league_data['ahl']['teams'])
    own = [(t['full'], R.team_name(t['slot'])) for key in leagues for t in league_data[key]['teams'] if t.get('own')]
    for club, team in own:
        log.append(['ALL', 'summary', f"your own team {team}", f"gets {club}'s players", ''])
    b.reserve_listed(league_data)
    if my_edits:                        # the player's own new players: their records are taken before the leagues'
        from . import edits
        b.hold_records(edits.records_needed(b, my_edits))
    b.league_keys = set(leagues)        # where undrafted prospects can go (clubs._place_prospects)
    # the game's own roster, first update: its 2014 national teams are filled again from scratch (the NHL
    # step empties them once it knows NHL.com's players)
    b.rebuild_national = bool(prepared) and NATIONAL in steps
    if b.rebuild_national and NHL not in steps:
        b.clear_national()
    rebuilt = set()
    if NHL in steps:
        log.section = SECTION_NHL
        say("NHL: moving players to their teams")
        b.nhl_rosters()
    if RATINGS in steps:
        log.section = SECTION_RATINGS
        say("Ratings: writing the current ratings")
        b.apply_list_ratings()
        b.donors.refresh()              # ratings move players across the legend line of spare records
    if NHL in steps:
        log.section = SECTION_NHL
        say("NHL: lines and mirror teams")
        b.nhl_lines()
        b.sync_mirrors()
    if NATIONAL in steps:
        # before the club leagues: new national players need spare records, and the junior
        # leagues, last in line, are the ones cut short if records run out
        log.section = SECTION_NATIONAL
        say("Filling the empty national teams")
        b.fill_empty_national()
    if leagues:                         # old players the leagues no longer list retire first
        log.section = SECTION_FREE_AGENTS
        say("Retiring the old players the leagues no longer list")
        stock.retire_leftovers(b, league_data)
    # player records are scarce: every league's clubs get a dressable 20 before any league's depth
    needs = {key: clubs.core_needs(b, league_data[key]) for key in leagues}
    for k, key in enumerate(leagues):
        b.core_reserve = sum((needs[x] for x in leagues[k + 1:]), Counter())
        log.section = LEAGUE_NAMES[key]
        say(f"{LEAGUE_NAMES[key]}: building the clubs")
        rebuilt |= clubs.update_league(b, key, league_data[key], say)
    if leagues:
        log.section = SECTION_POOLS
        b.pool_released = pools.settle(b, say)
        b.former_photos()               # last season's photos for players no list gave one
        if not game_patch and L.is_vees(R.T) and not L.listed(R.T, L.VEES):
            log.append(['ALL', 'summary', "Penticton Vees", "not in the game's team list yet: it shows them once every "
                        "league is updated", ''])
    if NATIONAL in steps:
        log.section = SECTION_NATIONAL
        say("National teams")
        b.national_teams()
        clubs.late_positions(b, say)    # league positions held back for players the national step took off
        b.national_lines()
    if NHL in steps and b.data.contracts:
        log.section = SECTION_NHL
        b.contract_strays()             # players under contract (2026-27) left on no club: to their organisation
    if NHL in steps:                    # a stick in a colour the team does not wear: the brand's in its colours
        log.section = SECTION_NHL
        swapped = sticks.team_sticks(R, skip=b.deleted)     # not by a place the player is leaving
        if swapped:
            log.append(['ALL', 'summary', "sticks in team colours", len(swapped), ''])
    if (set(steps) - {RATINGS, SCHEDULE}) and (b.data.skins or faces.COUNTRY_SKIN):
        # created players in a skin their photo or country does not fit (only when a step that places players runs)
        log.section = SECTION_PLAYER_DATA
        fitted = b.donors.fit_skins()
        if fitted:
            log.append(['ALL', 'summary', "players given a head that fits their photo or country", fitted, ''])
    if NHL in steps and b.data.equipment:       # how the players really dress: before the player's own choices, which win
        log.section = SECTION_PLAYER_DATA
        real = b.real_equipment()
        if real:
            log.append(['ALL', 'summary', "players given their real sock tucks, pants and neck guards", real, ''])
    log.section = SECTION_EDITS
    if my_edits:
        from . import edits
        say("My edits: applying your own changes")
        edits.apply(b, my_edits, say)
    if team_edits:
        from . import edits
        edits.apply_teams(b, team_edits, say)
    log.section = SECTION_PLAYER_DATA
    if steps:                           # an update, not only the Roster editor's edits
        b.club_gear()                   # helmets and gloves in colours the club does not wear
    b.goalie_gear(mend=bool(steps))     # mend: also gear the game cannot draw and colours the club does not wear
    # free editing (verify's `free`, Builder.players_team): an edit-only save is all the player's; an update with edits
    # frees what they changed (the rows set grows with the contract edits below)
    b.free = True if not steps else ((getattr(b, 'edited', (set(), set()))[1],
                                      {int(k) for k in (team_edits or {}) if str(k).isdigit()})
                                     if my_edits or team_edits else None)
    log.section = SECTION_CONTRACTS
    b.contracts()
    if NHL in steps and b.data.contracts:
        say("Contracts: the real 2026-27 deals")
        b.real_contracts()
    # a starter deal for every club player who has none: the whole roster after a step that moves players, else only
    # the players whose clubs changed (the Roster editor's moves)
    b.starter_contracts(everyone=bool(steps - {RATINGS, SCHEDULE}))
    contract_edits = {}
    if my_edits:                        # the contracts the player set: after the real deals, or those would replace them
        from . import edits
        log.section = SECTION_EDITS
        contract_edits = edits.apply_contracts(b, my_edits, say)
    log.section = SECTION_PLAYER_DATA
    # the real draft for everyone (again: players made or renamed in this run)
    drafted += draft.apply(R, drafts, data.season_year)
    if drafted:
        log.append(['ALL', 'summary', 'players given their real draft (year, round, pick, team)', drafted, ''])
    b.drafted = drafted
    b.prospects = None
    if my_edits:                        # the player's draft classes: after the real drafts, which would undo them
        from . import draftclass
        log.section = SECTION_EDITS
        b.prospects = draftclass.apply(b, my_edits, say)
        log.section = SECTION_PLAYER_DATA
    # players the edits moved or made (no step): their contract status is fitted below, before finish() renumbers
    touched = set()
    if not (steps - {RATINGS, SCHEDULE}):
        now = b.club_teams(contracts.contract_clubs(R))
        touched = {pid for pid in set(now) | set(b.orig_clubs) if now.get(pid) != b.orig_clubs.get(pid)}
    b.own_teams = own
    b.rating_sources = b.rating_counts()    # where the ratings of the players on a team now came from
    b.calendar = None
    if SCHEDULE in steps and data.schedule:
        say("Calendar: writing the season's games")
        b.calendar = schedule.apply(R, data.schedule, data.calendar or schedule.THIRTY)
    b.league_calendars, b.calendars_kept = {}, []
    if SCHEDULE in steps:
        for part, games in sorted(data.league_schedules.items()):
            # a league not updated keeps its calendar (its slots may hold other clubs); the patch writes the AHL's
            if CALENDAR_STEP[part] not in steps or (part == 'ahl' and data.calendar == schedule.ALL_PATCH):
                continue
            try:
                b.league_calendars[part] = schedule.apply_league(R, part, games)
            except schedule.ScheduleError as err:
                say(f"Calendar: {err}; the {schedule.LEAGUE_LABELS[part]} keeps its calendar")
                b.calendars_kept.append(schedule.LEAGUE_LABELS[part])
    if calendar_from is not None and SCHEDULE not in steps:
        say("Calendar: putting the game's own calendar back")
        restore.copy_calendar(R, calendar_from)
    b.mend(Roster(src_bytes))           # leftovers verify would refuse and that have one safe answer (Builder.mend)
    b.finish()
    # after finish: the tables say who is on a team and who is a free agent. Every record is fitted after a step that
    # moves players or writes deals or birth years; the Roster editor's Save (no step) and a ratings / calendar update
    # touch only the contracts edited and the players it moved or made
    moved = bool(steps - {RATINGS, SCHEDULE})
    touched = {R.p_by_id[pid] for pid in touched if pid in R.p_by_id}
    # Seattle's rights on a roster for the unpatched game (0.50.0 / 0.50.1 wrote them): its Season crashed on them
    dropped = contracts.drop_rights(R)
    if dropped:
        log.section = SECTION_CONTRACTS
        log.append(['ALL', 'summary', "NHL rights the unpatched game's Season does not know taken off (Seattle's)",
                    len(dropped), ''])
    statused = contracts.status_fit(R, None if moved else set(contract_edits) | touched | set(dropped))
    if statused:
        log.section = SECTION_CONTRACTS
        log.append(['ALL', 'summary', "contract status set to fit the contract (Team Rosters shows it)", statused, ''])
    # the UFA year once every birth year is final
    ufa = contracts.ufa_fit(R) if moved else 0
    if ufa:
        log.section = SECTION_CONTRACTS
        log.append(['ALL', 'summary', "free-agent year set to age 27 (Be a GM shows UFA / RFA by it)", ufa, ''])
    pictures = art
    art = None
    if pictures is not None and getattr(pictures, 'season_looks', False):
        # a team without an Alternate version gets a jersey row for this season's third (lab round 57: only together with
        # its files, a row alone draws a plain blue jersey); rows first, art_fit's (patch_roster) come after
        from .art.looks import alternate_rows
        from .art.lookpack import LookPack
        look_pack = LookPack.open()
        added = alternate_rows(R, look_pack) if look_pack is not None else []
        if added:
            log.section = SECTION_PLAYER_DATA
            log.append(['ALL', 'summary', "teams given an Alternate jersey of this season's", len(added), ''])
    if pictures is not None:
        from .art import portraits
        say("Photos and logos: choosing the pictures")
        art = portraits.plan(b, pictures.registry, own_only=pictures.own_only, claims=pictures.claims,
                             check=pictures.check, moved=pictures.moved, names_on=getattr(pictures, 'names_on', None))
    elif art_registry is not None:
        from .art import portraits
        say("Photos and logos: choosing the pictures")
        art = portraits.plan(b, art_registry)
    say("Packing the save")
    out = R.f.build()
    problems, info = [], {}
    if check:
        say("Checking the new roster")
        problems, info = verify(out, Roster(src_bytes), getattr(b, 'nhl_listed', data.nhl_players) if NHL in steps else None, rebuilt,
                                edited=getattr(b, 'edited', None), calendar=b.calendar,
                                calendar_source=calendar_from, depth=b.joined_depth, money=money,
                                deals=b.data.contracts if NHL in steps else None,
                                crests={s: R.T.get(s, 'artid') for s in b.crest_pictures}, contract_edits=contract_edits,
                                prospects=b.prospects, league_calendars=b.league_calendars, free=b.free)
    result = BuildResult(out, sorted(b.log, key=lambda r: (str(r[0]), str(r[1]), str(r[2]))), problems, info, b)
    result.art = art            # ({portrait id: photo link}, {team art id: (logo link, colours)}, team names) or None
    result.turned_back = turned_back
    result.patched = patched            # the source was made for the game patch
    return result


def patch_roster(result, source, pack, season):
    """The roster built in `result` (a BuildResult with the calendar step's schedule.ALL_PATCH calendar and the AHL step)
    made for the game patch (gamepatch.py): birth years and picks the patched way, the AHL of 32 with its own calendar,
    Utah in the Central and Seattle / Vegas in the Pacific, EASHL 1 / 2 as the All-Stars, Coachella Valley / Henderson in
    the AHL's league (league_fit) and art ids of their own (art_fit), the next seasons' calendar,
    the patched game's section length, the farm clubs' rights. `source` is the roster it was built from (bytes).
    Returns (save bytes, problems, farm games); nothing may be saved while there are problems."""
    R = Roster(result.data)
    gamepatch.year_shift(R, result.builder.stale_years)
    farm_games = pack.get('ahl_schedule')
    if not farm_games:
        raise RuntimeError("this program has no AHL schedule in its data (tools/build_datapack.py --refresh ahl_schedule)")
    farm_count = gamepatch.farm_fit(R, farm_games)
    gamepatch.divisions_fit(R)
    gamepatch.all_star_fit(R)
    gamepatch.league_fit(R)
    gamepatch.art_fit(R)                # art ids 900 / 901 and their jersey rows (art/clubart.py)
    gamepatch.future_fit(R)
    gamepatch.section_fit(R)
    gamepatch.rights_wide(R)            # Vegas's rights fit (a lab roster is built without game_patch)
    gamepatch.rights_fit(R, pack['leagues']['ahl']['teams'], season)
    contracts.status_fit(R)             # rights_fit's two-way deals
    contracts.ufa_fit(R)                # birth years on the league's clock (year_shift)
    data = R.f.build()
    problems = gamepatch.check_years(Roster(data), season)
    problems += verify(data, Roster(source), calendar=result.builder.calendar, farm_patch=True,
                       money=contracts.REAL, prospects=getattr(result.builder, 'prospects', None),
                       league_calendars=getattr(result.builder, 'league_calendars', None),
                       free=getattr(result.builder, 'free', None))[0]
    return data, problems, farm_count


class UpdateResult:
    def __init__(self, build_result, slot, report_path, name, art=None, slots=None, in_place=False, backup=None,
                 unchanged=False, exported=None):
        self.exported = exported        # the SYS-DATA file written by export_sysdata (no save, no RPCS3)
        self.in_place = in_place        # the roster save was updated, not a new one made
        self.backup = backup            # the folder with the old roster's files (in place)
        self.unchanged = unchanged      # in place, and the roster already was this
        self.build = build_result
        self.slot = slot                # the new savedata.Slot, None on a dry run or a failed check
        self.slots = slots if slots is not None else ([slot] if slot else [])   # one per version saved for
        self.report_path = report_path
        self.name = name
        self.art = art                  # (pictures installed, already there, failed), a message, or None
        self.restored = []              # lines about what was put back as the game had it (restore.py)
        self.patch = None               # made for the patched game: its title ids; None: for the unpatched game
        self.db_note = None             # the patched game's db files could not get this roster's next seasons: why
        self.patch_art = False          # the pictures and names went in with it (Season names Seattle and Vegas)
        self.look_teams = 0            # teams in this season's jerseys or centre ice (the look pack)
        self.own_pictures = False       # `art` is about the player's own pictures alone (photos and logos off)
        self.own_looks = False          # look_teams counts the teams the player gave jerseys (this season's were off)
        self.after = []                 # [(what, message, details)]: parts after the save that failed (the roster is saved)

    def saved_where(self):
        """'BLES021530210 (EU) and BLUS315400200 (NA)': the new folders, for the player."""
        if self.exported:
            return self.exported
        if self.in_place:
            return f"{self.slot.folder} ({self.slot.region}), updated in place"
        return " and ".join(f"{s.folder} ({s.region})" for s in self.slots)

    def art_line(self):
        """One sentence about photos and logos (None when they were off)."""
        if self.art is None:
            return None
        what = "Your own pictures" if self.own_pictures else "Photos and logos"
        if isinstance(self.art, str):
            return f"{what} were not installed: " + self.art
        written, already, failed = self.art
        text = f"{what}: {written} pictures installed"
        if already:
            text += f", {already} were installed already"
        if failed:
            text += f", {failed} could not be made (those players keep the picture they had)"
        if self.look_teams and self.own_looks:
            text += f". Jerseys and ice of {self.look_teams} of your teams installed"
        elif self.look_teams:
            text += f". {self.look_teams} teams wear this season's jerseys"
        return text + "."

    def patch_lines(self):
        """What the player reads about the game patch (empty for an ordinary roster of the unpatched game)."""
        if self.patch is None:
            if self.build.turned_back:
                return ["This roster was made for the patched game. The new one is for your unpatched game: 30 teams "
                        "in Season and Be a GM."]
            return []
        lines = [f"Made for the patched game (32 teams and the year 2026). In the game, load the roster "
                 f"\"{self.name}\", then start a new Season or Be a GM."]
        if self.db_note:
            lines.append("The game patch could not be brought up to date: " + self.db_note)
        if not self.patch_art:
            lines.append("Switch on \"Team names\" too: without it Season shows Seattle and Vegas "
                         "as the All-Star teams.")
        return lines


def write_report(result, title, heading=None, leagues=None):
    """The list of changes: a page to read (HTML, grouped by part and team; its path is returned)
    and the same rows as a table next to it (CSV, for a spreadsheet)."""
    from . import report
    path = datasource.app_dir('reports', f"{title}.csv")
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['team', 'change', 'player', 'detail', 'number', 'part'])
        w.writerows(result.log)
    page = path[:-4] + '.html'
    with open(page, 'w', encoding='utf-8') as f:
        f.write(report.html(result, heading or title, leagues or {}, csv_name=title + '.csv'))
    return page


def update(save_folder, source_folder=None, steps=ALL_STEPS, name=None, progress=None,
           offline=False, dry_run=False, data=None, art_rpcs3=None, art_registry=None, my_edits=None,
           team_edits=None, targets=None, disc=None, in_place=False, backup_root=None, restore_parts=None,
           default=None, rpcs3=None, game_patch=None, art_parts=None, also_looks=(), ice_order=None):
    """The whole job: read the chosen roster save, gather data, build, check, write a new save.

    `save_folder`: anything savedata.find_savedata() accepts. `source_folder`: the roster save to
    start from (folder name); default is the one pointed at, else the newest.
    `targets`: the versions of the game to save the new roster for (title ids, see
    savedata.GAMES); default the source's own. One new save folder each.
    `art_rpcs3` (a savedata.Rpcs3) switches photos and logos on: they are installed into that
    RPCS3's game folders (one per target) after the new roster is saved (RPCS3 must be closed). `art_parts` (art/parts.py)
    says which: default team names, photos and logos, and this season's jerseys and centre ice (the one switch of before
    0.76.0); the arenas, community centre ice and team masks are asked for by name. `ice_order`: the two centre-ice parts
    (art/parts.py PACK_ICE, BRIGHT_ICE) in the order they were switched on, the second lies over the first.
    `disc` (a savedata.DiscSlot) starts from the game's own roster on the player's disc instead of a
    roster save; `save_folder` is then the save folder itself (it may not exist yet).
    `in_place` updates the chosen roster save itself instead of making a new one (savedata.update_in_place:
    after a backup copy in `backup_root`, default the program's backups folder; only the source's own
    version, never the game's own roster; RPCS3 must be closed); `name` then renames it, no name keeps it.
    `restore_parts` (restore.ROSTERS / CALENDAR / PICTURES) puts the game's own things back in this save, taken from
    `default` (restore.default_slot: only read): the rosters start from the game's own roster (written as it is when no step is
    left), the calendar is copied from it, and the pictures, names and jerseys are put back after the save; restore.PATCH
    takes the game patch out of `rpcs3` (patchinstall.remove). Steps still switched on are applied on top.
    The new roster is for the game as `rpcs3` (a savedata.Rpcs3) is: patched for every target version
    (patchinstall.patched_titles: Patch in the window's step 2), a roster for the game patch (patch_roster: the calendar
    and AHL steps run too, and the db files get its next seasons, patchinstall.refresh_db); patched for none, a roster
    for the unpatched game (one made for the patch is turned back, with `default` or the version's own default roster);
    patched for some, refused. `game_patch` True / False makes it one or the other whatever RPCS3 is.
    Nothing is written when the integrity check finds a problem or `dry_run` is set."""
    from . import patchinstall
    say = progress or (lambda msg: None)
    parts = set(restore_parts or ())
    steps = list(steps)
    pack = None
    if restore.PATCH in parts:
        game_patch = False                  # Restore default unpatches the game: the roster is for the unpatched one
    if parts:
        if default is None:
            raise FileNotFoundError("The game's own roster was not found: there is no clean roster save and no game disc.")
        if restore.CALENDAR in parts:
            steps = [s for s in steps if s != SCHEDULE]
        if (restore.PICTURES in parts or restore.pictures_of(parts)) and not dry_run and savedata.running_rpcs3():
            raise savedata.InPlaceError(f"{savedata.close_first()}: the game's own pictures can only be put back while the game is closed.")
        if restore.PATCH in parts and not dry_run and savedata.running_rpcs3():
            raise savedata.InPlaceError("Close RPCS3 first: the game patch can only be taken out while RPCS3 is closed.")
    if in_place and disc is not None:
        raise savedata.InPlaceError("The game's own roster cannot be updated in place: save it as a new roster.")
    if disc is not None:
        folder, source = os.path.abspath(save_folder), disc
    else:
        folder, preselected = savedata.find_savedata(save_folder)
        slots = savedata.list_rosters(folder)
        wanted = source_folder or preselected
        source = next((s for s in slots if s.folder == wanted), None) if wanted else slots[0]
        if source is None:
            raise FileNotFoundError(f"roster save {wanted} was not found in {folder}")
    target = source                     # the roster save that "update in place" replaces
    if restore.ROSTERS in parts:
        source = default                # the update starts from the game's own roster
    targets = sorted(set(targets or [source.title_id]), key=lambda t: (t != source.title_id, t))
    host = art_rpcs3 or rpcs3
    if getattr(host, 'native', False):
        targets = [savedata.NATIVE_TITLE]   # the one version the port runs
    if game_patch is None:              # as RPCS3 is
        stale = [t for t in targets if t in patchinstall.stale_titles(rpcs3)]
        if stale and rpcs3.native:
            raise L.LayoutError(patchinstall.PORT_OTHER + " Press Unpatch in Game patch, then update.")
        if stale:
            raise L.LayoutError(f"Your {' and '.join(savedata.region(t) for t in stale)} game has update 1.01, and the "
                                "game patch in RPCS3 was made before this program knew it. Press Patch again in Game "
                                "patch, then update.")
        on = [t for t in targets if t in patchinstall.patched_titles(rpcs3)]
        if on and len(on) != len(targets):
            off = [t for t in targets if t not in on]
            raise L.LayoutError(f"Your {' and '.join(savedata.region(t) for t in on)} game is patched for 32 teams, your "
                                f"{' and '.join(savedata.region(t) for t in off)} game is not. Patch both in step 2, "
                                "or save for one of them.")
        game_patch = bool(on)
    if game_patch:
        parts.discard(restore.CALENDAR)     # the patch has its own calendar of 32 teams
        steps += [s for s in (SCHEDULE, 'ahl') if s not in steps]
    if in_place and targets != [source.title_id]:
        raise savedata.InPlaceError("A roster is updated in place in its own version of the game only: "
                                    "save a new roster for the other version.")
    if in_place and not dry_run and savedata.running_rpcs3():
        raise savedata.InPlaceError(f"{savedata.close_first()}: a roster can only be updated while the game is closed.")
    if not in_place and not dry_run:
        for title_id in targets:        # every version has room before anything is built or saved
            savedata.next_free(folder, title_id)
    if dry_run:
        art_rpcs3 = None
    from .art import install, portraits
    pictures, own_note = None, None
    # the player's own pictures (Roster editor) go in with photos and logos off too
    looks_for = looks_teams(team_edits) | frozenset(also_looks or ())      # also_looks: set back to the game's own
    own = (art_rpcs3 is None and not dry_run and rpcs3 is not None and not rpcs3.plain
           and restore.PICTURES not in parts and (portraits.mine(my_edits, team_edits) or bool(looks_for)))
    if art_rpcs3 is not None or own:    # say what stands in the way before anything is built
        pic_rpcs3 = art_rpcs3 or rpcs3
        # the pictures are made from the disc of a version RPCS3 knows; the other version gets copies
        art_title = next((t for t in targets if pic_rpcs3.game_disc(t)), targets[0])
        try:
            from .art import parts as art_kinds
            shown = frozenset(art_parts) if art_parts is not None else art_kinds.LEGACY
            pictures = Pictures(pic_rpcs3, art_title, targets, own_only=own, registry=art_registry, say=say,
                                parts=frozenset() if own else shown, looks_for=looks_for,
                                season_looks=art_kinds.LOOKS in shown, ice_order=ice_order)
        except install.ArtError as err:
            if not own:
                raise
            own_note = str(err)         # the roster is still saved; the next update puts them in
    say(f"Starting from \"{source.name}\" ({source.folder})")
    src_bytes = savedata.read_roster(source)
    target_bytes = src_bytes if target is source else savedata.read_roster(target)
    normal_from = None
    if not game_patch and gamepatch.is_patch_roster(Roster(src_bytes)):    # turned back with the game's own roster
        own = default or (restore.default_slot(rpcs3, source.title_id) if rpcs3 is not None and not rpcs3.plain else None)
        if own is None:
            raise L.LayoutError(f"\"{source.name}\" was made for the patched game (32 teams). To make it a roster for "
                                "the unpatched game the program needs the game's own roster: pick rpcs3.exe and start "
                                "the game once from RPCS3, or patch the game in step 2.")
        normal_from = Roster(savedata.read_roster(own))
    raw = restore.ROSTERS in parts and not steps         # nothing to update: the game's own roster, as it is
    if raw:
        say("Putting the game's own roster back as it is")
        result = BuildResult(src_bytes, [], [], {}, restore._Raw())
        result.art = None
    else:
        calendar_from = Roster(savedata.read_roster(default)) if restore.CALENDAR in parts else None
        if data is None:
            pack = datasource.load_pack(say, offline)
            R = Roster(src_bytes)
            if L.check_base(R) == L.STOCK and NHL not in steps:
                steps.append(NHL)       # Seattle and Vegas start empty on the game's own roster; only this step fills them
            data = datasource.gather(R, set(steps), pack, say, offline)
        if game_patch:
            data = copy.copy(data)
            data.calendar = schedule.ALL_PATCH      # all 84 games of the 32 teams and the All-Star game
        result = build(src_bytes, data, steps, say, art=pictures,
                       my_edits=my_edits, team_edits=team_edits, calendar_from=calendar_from,
                       game_patch=game_patch, normal_from=normal_from)
        if game_patch and result.ok:
            say("Game patch: making the roster for 32 teams and the year 2026")
            pack = pack or datasource.load_pack(say, offline)
            result.data, result.problems, _ = patch_roster(result, src_bytes, pack, data.season_year)
    asked_name = name
    name = savedata.clean_name(name or (target.name if in_place else savedata.default_name()))
    stamp = f"{datetime.datetime.now():%Y%m%d-%H%M%S}"
    heading = f"\"{name}\", made from \"{source.name}\""
    def report_as(title):
        return write_report(result, title, heading, getattr(data, 'leagues', None))
    if not result.ok:
        report = report_as(f"failed_{stamp}")
        say(f"The new roster did not pass {len(result.problems)} integrity checks, so nothing was saved.")
        return UpdateResult(result, None, report, name)
    if dry_run:
        return UpdateResult(result, None, report_as(f"dryrun_{stamp}"), name)
    saved, backup, unchanged = [], None, False
    if in_place:
        slot, backup, changed = savedata.update_in_place(
            folder, target, result.data, asked_name, expected=target_bytes,
            backup_root=backup_root or datasource.app_dir('backups'))
        saved, unchanged = [slot], not changed
        say("Already up to date: the roster is the same as the new one" if unchanged else
            f"Updated \"{slot.name}\" in place ({slot.folder}, {slot.region})")
    else:
        for title_id in targets:
            slot = savedata.install(folder, source, result.data, name, title_id=title_id)
            saved.append(slot)
            say(f"Saved as \"{slot.name}\" in {slot.folder} ({slot.region})")
    # the roster is saved: what follows must not make the player think it was not (a tester's "[WinError 3]" after
    # "Saved as" read "Nothing was saved"). Each part that fails is told in UpdateResult.after, with its details.
    after = []

    def then(what, work, failed=None):
        try:
            return work()
        except Exception as err:
            text = str(err) + (f": {err.filename}" if isinstance(err, OSError) and err.filename
                               and str(err.filename) not in str(err) else '')
            say(f"{what}: {text}")
            after.append((what, text, traceback.format_exc()))
            return failed
    title = f"{saved[0].folder}_{stamp}"
    report = then("The list of changes could not be written", lambda: report_as(title))
    db_note = None
    if game_patch and rpcs3 is not None and rpcs3.patchable:   # the patched game's db files carry its next seasons
        db_note = then("The game patch could not be brought up to date",
                       lambda: patchinstall.refresh_db(rpcs3, targets, result.data, say))
    art, look_teams = own_note, 0
    if result.art is not None and pictures is not None:
        art, look_teams, noted = then("The pictures did not go in", lambda: pictures.put_in(result, say),
                                      (None, 0, False))
        if noted:                       # in the list of changes, by name: a player can tell us who
            report = then("The list of changes could not be written", lambda: report_as(title), report)
    done = UpdateResult(result, saved[0], report, name, art, slots=saved, in_place=in_place, backup=backup,
                        unchanged=unchanged)
    done.after = after
    done.own_pictures = own
    done.patch = list(targets) if game_patch else None
    done.db_note = db_note if isinstance(db_note, str) else None
    done.patch_art = art_rpcs3 is not None
    done.look_teams = look_teams
    done.own_looks = pictures is not None and art_kinds.LOOKS not in pictures.parts
    if restore.PATCH in parts and rpcs3 is not None:
        def unpatch():
            if patchinstall.installed(rpcs3):
                patchinstall.remove(rpcs3, say)
                done.restored.append("The game patch is out: the game is as it was.")
        then("The game patch could not be taken out", unpatch)
    if restore.PICTURES in parts:
        from .art import install

        def unpicture():
            n = install.remove(say)
            done.restored.append("The game's own pictures, team names and jerseys are back." if n else
                                 "No photos or logos were installed: the pictures are the game's own.")
        then("The game's own pictures could not be put back", unpicture)
    elif restore.pictures_of(parts):
        from .art import install

        def unparts():
            n = install.remove_parts(restore.pictures_of(parts), say)
            done.restored.append("The game's own pictures are back for what you restored." if n else
                                 "Nothing of that was installed: the pictures are the game's own.")
        then("The game's own pictures could not be put back", unparts)
    host = art_rpcs3 or rpcs3
    if getattr(host, 'native', False) and (restore.PICTURES in parts or restore.pictures_of(parts) or pictures is not None):
        from . import native
        then("The game could not be told about the new files", lambda: native.settle(host, say))
    if restore.ROSTERS in parts:
        done.restored.insert(0, "The rosters start from " + restore.describe(default)[0].lower() + restore.describe(default)[1:])
    if restore.CALENDAR in parts:
        done.restored.insert(0, "The calendar is the game's own.")
    return done


def looks_teams(team_edits):
    """The slots of the teams the player gave jerseys or a centre ice (edits.json teams[slot] 'uniforms' / 'ice') or a
    custom kit with a crest picture of his own ('kit' 'crest' 'file:...'): their pictures go into the game like the player's
    own photos and logos, with this season's jerseys switched off too (owner, 2026-10-28: the Roster editor's Save)."""
    out = set()
    for key, e in (team_edits or {}).items():
        e = e or {}
        if e.get('uniforms') or e.get('ice') or str((e.get('kit') or {}).get('crest') or '').startswith('file:'):
            try:
                out.add(int(key))
            except (TypeError, ValueError):
                continue
    return frozenset(out)


def names_of(source, team_edits=None):
    """What art.portraits.names gives the roster `source` (bytes of a SYS-DATA) with the player's own team names
    `team_edits`, as an update of it would give. The roster is only read: nothing here is saved."""
    from . import edits
    from .art import portraits
    R = Roster(source)
    kind = L.check_base(R)
    if gamepatch.is_patch_roster(R):    # names go by the teams as the builder knows them, as in build()
        gamepatch.unleague(R)
        gamepatch.unart(R)
    b = Builder(R, Data(season_year=2026), layout=kind)
    for key, entry in (team_edits or {}).items():
        if 0 <= int(key) < R.T.cur_rec:
            edits.team_name(b, int(key), entry)
    return portraits.names(b)


def apply_names(rpcs3, source, title_id, targets=None, team_edits=None, say=print):
    """The team names of the roster `source` (bytes of a SYS-DATA) and the main menu into the game now: no roster is
    saved, no pack is read, no picture is looked at. The Team names row's "Apply names" and `cli names apply`. Raises
    install.ArtError when they cannot go in (the game runs, no disc)."""
    from . import native
    from .art import install
    if savedata.running_rpcs3():
        raise install.ArtError(f"{savedata.close_first()}: team names can only go in while the game is closed.")
    if rpcs3.native:                    # the port has one version, whatever a copied roster says
        title_id, targets = savedata.NATIVE_TITLE, None
    targets = list(targets or [title_id])
    names = names_of(source, team_edits)
    plainly = lambda line: say(line.removeprefix('Photos and logos: '))
    install.install(rpcs3, title_id, {}, {}, plainly, names=names, also=[t for t in targets if t != title_id], pack=False,
                    cache=False, pictures=False)
    if rpcs3.native:
        native.settle(rpcs3, say)
    return len(names['teams'])


class Pictures:
    """Photos and logos for one update or one Roster editor save on this PC: what portraits.plan needs before the
    build (the numbers other rosters and packs use, the photos that make no picture) and the install after the save
    (put_in). `parts` (art/parts.py): what is switched on; default photos, logos, names and this season's looks (the
    one switch of before 0.76.0), none when `own_only`: the player's own pictures alone. `looks_for` (looks_teams): teams
    whose own jerseys, ice and crest go in also while this season's jerseys are off, only theirs (`season_looks`: with
    this season's kits for the versions the player left alone). Raises install.ArtError when they cannot go in now
    (RPCS3 runs, no disc)."""

    def __init__(self, rpcs3, title_id, targets=None, own_only=False, registry=None, say=None, parts=None, looks_for=(),
                 season_looks=True, ice_order=None):
        from .art import install, portraits
        from .art import parts as P
        say = say or (lambda msg: None)
        self.parts = frozenset(parts if parts is not None else (() if own_only else P.LEGACY))
        self.photos = P.PHOTOS in self.parts
        self.own_only = not self.photos         # photos and logos are off: the player's own pictures only
        self.names_on = P.NAMES in self.parts
        self.looks_for, self.season_looks = frozenset(looks_for or ()), season_looks
        self.ice_order = P.ice_order(ice_order, self.parts)     # the centre-ice parts that are on, the first switched on first
        install.check(rpcs3, title_id, own=not self.parts)
        self.rpcs3, self.title_id = rpcs3, title_id
        self.targets = list(targets or [title_id])
        self.registry = registry or portraits.Registry()
        self.claims = install.scan_claims(rpcs3)
        # numbers of ours someone else uses: those players get fresh ones, the files go back after the save
        self.moved = {} if self.own_only else portraits.forget_conflicts(self.registry, self.claims)
        self.check = lambda links: install.prefetch(links, rpcs3, title_id, say=say)

    def put_in(self, result, say):
        """After the roster is saved: its pictures into the game. Returns (what UpdateResult.art holds, teams in this
        season's jerseys, whether the list of changes got rows about pictures that could not be made)."""
        from .art import install
        from .art import parts as P
        self.registry.save()             # the new roster uses these ids now
        portraits_, logos, names = result.art
        if self.photos:                 # a roster for the patched game: Coachella Valley's / Henderson's logos under 900 / 901
            from .art import clubart
            logos = clubart.rekey_logos(Roster(result.data), logos)
        bad = result.builder.bad_pictures
        skipped = [('photo', url, why) for url, why in sorted(bad.items())]
        look_teams = 0
        own = bool(portraits_ or logos or bad)
        try:
            install.remove_retired(say)     # files of a part taken out again (the test versions' scoreboard)
        except OSError as err:
            say(f"The test scoreboard's files could not be put back now ({err}); the next update tries again.")
        if not (self.parts - {P.PHOTOS}) and self.own_only and not own and not self.looks_for:
            return None, 0, False       # none of the player's own pictures is in this roster
        try:
            if self.photos:
                install.give_back((set(self.moved) | self.claims.contested()) - set(portraits_), say)
            new_ice, own_ice = self.new_centres(result)
            # two sets of centre ice can be on: the one switched on second is laid over the first
            pack_wins = len(self.ice_order) == 2 and self.ice_order[1] == P.PACK_ICE
            by_pack = set()             # the art ids this season's centre ice has (filled by install_looks)
            if P.LOOKS in self.parts or P.PACK_ICE in self.parts:
                look_teams = install_looks(result, self.rpcs3, self.title_id, self.targets, say,
                                           new_ice=set() if pack_wins else new_ice - own_ice,
                                           jerseys=P.LOOKS in self.parts, centres=P.PACK_ICE in self.parts,
                                           covered=by_pack)
            elif self.looks_for:
                look_teams = install_looks(result, self.rpcs3, self.title_id, self.targets, say, only=self.looks_for,
                                           season=self.season_looks)
            if self.photos:
                install_crests(result, self.rpcs3, self.title_id, self.targets, say)
            elif self.looks_for:
                install_crests(result, self.rpcs3, self.title_id, self.targets, say, only=self.looks_for)
                install_masks(result, self.rpcs3, self.title_id, self.targets, say)
            if P.ARENAS in self.parts:
                install_arenas(result, self.rpcs3, self.title_id, self.targets, say)
            if P.BRIGHT_ICE in self.parts:
                install_bright_ice(result, self.rpcs3, self.title_id, self.targets, say,
                                   keep=own_ice | (by_pack if pack_wins else set()))
            if P.TEAM_MASKS in self.parts:
                install_team_masks(result, self.rpcs3, self.title_id, self.targets, say)
            art = (0, 0, 0)
            if self.photos or own or self.names_on:
                art = install.install(self.rpcs3, self.title_id, portraits_, logos, say, names=names,
                                      also=[t for t in self.targets if t != self.title_id], skipped=skipped,
                                      menus=self.names_on, pictures=self.photos or own)
            art = (art[0], art[1], art[2] + len(bad))
        except install.ArtError as err:  # the roster is saved; only the pictures are missing
            say(str(err))
            art = str(err)
        if skipped:
            note_skipped(result, skipped)
        return art, look_teams, bool(skipped)

    def new_centres(self, result):
        """(the art ids the community centre ice has, the art ids among them whose centre the player chose in Jerseys &
        ice), both empty while its switch is off or its pack is not here. Which centre a team gets: the player's own choice,
        else the one of the two sets switched on second, else the one switched on first, else the game's."""
        from .art import brightice
        from .art import parts as P
        from .art.extrapack import ExtraPack
        if P.BRIGHT_ICE not in self.parts:
            return set(), set()
        pack = ExtraPack.open('ice')
        if pack is None:
            return set(), set()
        try:
            covered = brightice.covered(pack)
        finally:
            pack.close()
        own = set()
        if P.LOOKS in self.parts:           # the player's centre ice goes in with this season's jerseys
            own = {int(s) for s, e in (getattr(result.builder, 'looks_edits', None) or {}).items()
                   if ((e or {}).get('ice') or {}).get('use')}
        return covered, own & covered


def install_looks(result, rpcs3, title, targets, say, new_ice=(), only=None, season=True, jerseys=True, centres=True,
                  covered=None):
    """The new jerseys, pants, socks, menu pictures and centre-ice logos (art/looks.py): Utah, Seattle and Vegas, the
    teams the player gave a look, and this season's jerseys and centre ice for every team the program's look pack has
    (art/lookpack.py), made from the player's own disc, with the photos and logos. A logo that cannot be had leaves the
    jerseys out, the rest goes on; a team the pack cannot dress gets a row in the list of changes. `new_ice`: art ids
    whose centre ice the new centre ice (install_bright_ice) gives; their looks leave the centre to it. `only`: these slots
    alone (the Roster editor's Save; `season`: with this season's kits, else the game's own where the player chose
    nothing), the files of other teams stay as they are. `jerseys` / `centres`: this season's jerseys and this season's
    centre ice are two switches (0.96.0); one alone leaves the other's files as they are. `covered` (a set) gets the art
    ids whose centre ice this season's pack writes.
    Returns how many teams get this season's jerseys or centre ice (with `only`: how many of those teams' looks went in)."""
    from .art import looks
    from .art.lookpack import LookPack
    from .art.photopack import PhotoPack, PictureCache
    b = result.builder
    nhl_logos = getattr(b.data, 'nhl_logos', None)
    look_pack = LookPack.open() if season else None
    skipped, no_ice = [], []
    try:
        data = datasource.load_pack(offline=True)
        nhl_logos = nhl_logos or data.get('nhl_logos') or {}
        R = Roster(result.data)
        links = looks.club_logos(R, data.get('leagues'))    # the clubs' logos also where their league did not run now
        links.update(b.logos)
        made = looks.looks_from(R, dict(getattr(b, 'looks_edits', {})), links, nhl_logos,
                                PhotoPack.open(), PictureCache(), look_pack=look_pack, skipped=skipped, no_ice=no_ice,
                                only=only)
    except Exception as err:
        say(f"Jerseys and ice: left out ({err})")
        return 0
    scope = None
    if only is not None:            # the arts these teams' files may have: their own, a shared centre ice's, the made looks'
        scope = {m.art for m in made} | {looks.team_art(R, s)[0] for s in only if 0 <= s < R.T.cur_rec}
        scope |= {group[0] for group in (looks.ice_group(R, s) for s in only) if group}
    for slot, why in skipped:
        result.log.append(['', "This season's jerseys not installed", R.team_name(slot), why, '', SECTION_PICTURES])
    for slot, why in no_ice:
        result.log.append(['', "Centre ice not installed", R.team_name(slot), why, '', SECTION_PICTURES])
    made = [m._replace(centre=looks.OTHER) if m.art in new_ice else m for m in made]
    made = looks.split_looks(made, jerseys, centres)
    if covered is not None:
        covered.update(m.art for m in made if str(m.centre).startswith('pack:'))
    if made or scope:
        looks.install_looks(rpcs3, title, made, say, also=[t for t in targets if t != title], look_pack=look_pack,
                            only=scope, kind=None if jerseys and centres else 'jerseys' if jerseys else 'centres')
    if only is not None:
        return len(made)
    return sum(1 for m in made if m.pack or str(m.centre).startswith('pack:'))


def install_crests(result, rpcs3, title, targets, say, only=None):
    """Coachella Valley's and Henderson's crests and the custom teams' own crest pictures (the Roster editor's kit) on
    their jerseys and centre ice (art/crests.py), with the photos. `only`: these slots alone (the Roster editor's Save;
    a crest picture replaced by another leaves the old logo's files until the next update with the photos)."""
    from .art import crests, looks
    from .art.photopack import PhotoPack, PictureCache
    skipped = []
    try:
        R = Roster(result.data)
        data = datasource.load_pack(offline=True)
        links = looks.club_logos(R, data.get('leagues'))
        links.update(result.builder.logos)
        made = crests.crests_from(R, links, PhotoPack.open(), PictureCache(), skipped=skipped,
                                  pictures=getattr(result.builder, 'crest_pictures', {}), only=only)
        arts = None if only is None else {R.T.get(s, 'artid') for s in only if 0 <= s < R.T.cur_rec} | {a for a, _l, _c in made}
        crests.install_crests(rpcs3, title, made, say, also=[t for t in targets if t != title], only=arts)
    except Exception as err:
        say(f"Crests: left out ({err})")
        return
    for slot, why in skipped:
        result.log.append(['', "Crest not installed", R.team_name(slot), why, '', SECTION_PICTURES])


def install_masks(result, rpcs3, title, targets, say):
    """The goalies' own mask pictures (art/masks.py), with the photos and logos."""
    from .art import masks
    try:
        masks.install_masks(rpcs3, title, dict(getattr(result.builder, 'mask_looks', {})), say,
                            also=[t for t in targets if t != title])
    except Exception as err:
        say(f"Goalie masks: left out ({err})")


def _extra(name, what, say, result):
    """The small pack `name` (art/extrapack.py) or None, with a line for the player when it is not on this PC yet (also
    in the list of changes: an update that changed nothing of it says so)."""
    from .art.extrapack import ExtraPack
    pack = ExtraPack.open(name)
    if pack is None:
        say(f"{what}: the download is not here yet, so nothing was changed. Try again in a moment.")
        result.log.append(['', f"{what} not installed", '', "its download is not on this PC (offline, or not available "
                           "yet); the next update tries again", '', SECTION_PICTURES])
    return pack


def install_arenas(result, rpcs3, title, targets, say):
    """The NHL arenas' newer pictures (art/arenas.py, the "Arenas" switch)."""
    from .art import arenas
    pack = _extra('arenas', "Arenas", say, result)
    if pack is None:
        return
    skipped = []
    try:
        arenas.install_arenas(rpcs3, title, pack, say, also=[t for t in targets if t != title], skipped=skipped)
    except Exception as err:
        say(f"Arenas: left out ({err})")
    finally:
        pack.close()
    for art, why in skipped:
        result.log.append(['', "Arena not installed", f"arena {art}", why, '', SECTION_PICTURES])


def install_bright_ice(result, rpcs3, title, targets, say, keep=()):
    """The new centre ice (art/brightice.py, the "New centre ice" switch, key `bright_ice`); `keep`: art ids whose
    centre the player chose in Jerseys & ice (left to install_looks)."""
    from .art import brightice
    pack = _extra('ice', "New centre ice", say, result)
    if pack is None:
        return
    skipped = []
    try:
        brightice.install_bright(rpcs3, title, pack, say, also=[t for t in targets if t != title], keep=keep,
                                 skipped=skipped)
    except Exception as err:
        say(f"New centre ice: left out ({err})")
    finally:
        pack.close()
    for art, why in skipped:
        result.log.append(['', "Centre ice not installed", f"arena {art}", why, '', SECTION_PICTURES])


def install_team_masks(result, rpcs3, title, targets, say):
    """The goalie masks of the teams (art/masks.py, the "Team goalie masks" switch); a mask picture of the player's own
    is left to it."""
    from .art import masks
    pack = _extra('masks', "Team masks", say, result)
    if pack is None:
        return
    own = {int(n) for n in getattr(result.builder, 'mask_looks', {})}
    try:
        masks.install_team_masks(rpcs3, title, pack, say, also=[t for t in targets if t != title], own=own)
    except Exception as err:
        say(f"Team masks: left out ({err})")
    finally:
        pack.close()


ExportSlot = collections.namedtuple('ExportSlot', 'name folder region')


def export_root():
    """The folder an exported SYS-DATA goes to: next to the program (the exe; run from source, the current folder).
    When that folder cannot be written to (a program folder), the player's Documents folder."""
    base = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else os.getcwd()
    try:
        probe = os.path.join(base, '.write-test')
        with open(probe, 'w'):
            pass
        os.remove(probe)
        return base
    except OSError:
        docs = os.path.join(os.path.expanduser('~'), 'Documents')
        return docs if os.path.isdir(docs) else os.path.expanduser('~')


def export_sysdata(source_file, steps=ALL_STEPS, name=None, progress=None, offline=False, my_edits=None, team_edits=None,
                   data=None, out_root=None, game_patch=False, normal_from=None):
    """Update a roster file (a community roster's SYS-DATA) and write the new SYS-DATA into a new folder next to the program,
    without RPCS3 and without any save folder: for a PC that cannot run RPCS3 (a Mac, a Linux box). The new file is checked
    like every roster; nothing is written when a check fails. No photos, logos or jerseys (they are RPCS3's files), no
    start from the game's own roster (that needs the disc). `game_patch`: a roster for the patched game (patch_roster);
    else a roster made for the patch is turned back with `normal_from` (build). Returns an UpdateResult whose `exported`
    is the new file."""
    say = progress or (lambda msg: None)
    steps = list(steps) + ([s for s in (SCHEDULE, 'ahl') if s not in steps] if game_patch else [])
    if not os.path.isfile(source_file):
        raise FileNotFoundError("The roster file was not found.")
    with open(source_file, 'rb') as f:
        src_bytes = f.read()
    R = Roster(src_bytes)
    L.check_base(R)
    from . import stock
    if stock.untouched(R):
        raise L.LayoutError("This is the game's own roster as it comes on the disc, which is started from your game disc. "
                            "Pick an updated roster or the community roster's SYS-DATA instead.")
    say(f"Starting from \"{os.path.basename(os.path.dirname(os.path.abspath(source_file))) or 'SYS-DATA'}\" (SYS-DATA file)")
    pack = None
    if data is None:
        pack = datasource.load_pack(say, offline)
        data = datasource.gather(R, set(steps), pack, say, offline)
    if game_patch:
        data = copy.copy(data)
        data.calendar = schedule.ALL_PATCH
    result = build(src_bytes, data, steps, say, my_edits=my_edits, team_edits=team_edits, game_patch=game_patch,
                   normal_from=normal_from)
    if game_patch and result.ok:
        say("Game patch: making the roster for 32 teams and the year 2026")
        result.data, result.problems, _ = patch_roster(result, src_bytes, pack or datasource.load_pack(say, offline),
                                                       data.season_year)
    name = savedata.clean_name(name or savedata.default_name())
    stamp = f"{datetime.datetime.now():%Y%m%d-%H%M%S}"
    heading = f"\"{name}\", made from the roster file {os.path.basename(source_file)}"
    if not result.ok:
        say(f"The new roster did not pass {len(result.problems)} integrity checks, so nothing was saved.")
        return UpdateResult(result, None, write_report(result, f"failed_{stamp}", heading, data.leagues), name)
    root = out_root or export_root()
    folder = os.path.join(root, f"NHL Legacy roster {datetime.datetime.now():%Y-%m-%d %H%M}")
    n = 1
    while os.path.exists(folder):
        n += 1
        folder = os.path.join(root, f"NHL Legacy roster {datetime.datetime.now():%Y-%m-%d %H%M} ({n})")
    os.makedirs(folder)
    target = os.path.join(folder, 'SYS-DATA')
    with open(target + '.tmp', 'wb') as f:
        f.write(result.data)
    os.replace(target + '.tmp', target)
    say(f"Exported SYS-DATA to {target}")
    report = write_report(result, f"export_{stamp}", heading, data.leagues)
    return UpdateResult(result, ExportSlot(name, folder, ''), report, name, exported=target)


def note_skipped(result, skipped):
    """Rows in the list of changes for the pictures that could not be made, with the players' or
    clubs' names."""
    b = result.builder
    R = Roster(result.data)
    who = {}
    for prow, url in b.photos.items():
        who.setdefault(url, []).append(R.name(prow))
    for slot, url in b.logos.items():
        who.setdefault(url, []).append(R.team_name(slot))
    for what, url, why in sorted(skipped):
        for name in sorted(who.get(url, [url])):
            result.log.append(['', f"{what} not installed", name, why, '', SECTION_PICTURES])
