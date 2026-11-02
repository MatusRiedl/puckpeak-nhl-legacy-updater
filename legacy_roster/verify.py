"""Integrity checks for a built roster.

Every rule here was found the hard way: breaking it either crashes the game in a menu or makes
it silently keep the previous roster. `verify()` compares the built roster with the roster it
was built from, so a flaw the source already had is not blamed on the update -- only what the
update made worse is reported.
"""
from collections import Counter

from . import contracts, custom_kit, draftclass, equipment, faces, gamepatch, layout as L
from . import ratings, schedule, sticks, strategy
from .art.portraits import person_key
from .matching import closest, match
from .roster import Roster
from .schema import ASIS_RANGE, FULL_ASIS, FULL_RATED, FULL_TABLE, FULL_TAG, RATING_RANGE, SLOT_TAG
from .tdb import check_chain

FULL_LINEUP = list(range(32)) + list(range(133, 154))     # teams that must dress a legal 20
TEAM_FLAWS = ('slot twice', 'goalie', 'dressed', 'lineup', 'slots', 'too many', 'entry ids')   # keyed by team id
# Free editing (owner, 2026-10-29: "allow everything possible that will not really break the roster from loading"): these
# structure() flaws stop an update when the builder made them (our bug), never when the player's own edits did (`free`
# in verify). Keyed by team id / by player id. Everything else structure() finds stops every save: 40 per team (a
# place's id is team * 40 + slot), consecutive place ids, a player listed twice, the copies, the free-agent list.
FREE_TEAM_FLAWS = ('slot twice', 'goalie', 'dressed', 'lineup', 'slots')
FREE_PLAYER_FLAWS = ('no contract', 'draft')
SHORT_GOALIES, SHORT_SKATERS = 2, 18        # a team with fewer hangs its first game when the player plays with it (round 17)


_ALL_STAR_SLOTS = {30: 'Seattle Kraken', 31: 'Vegas Golden Knights'}


def _team(R, t):
    """The team's name as a player knows it: slots 30 and 31 are Seattle and Vegas, whatever the table still calls them
    ('Green / Red', 'Black / Blue' in a roster that was never given the new names)."""
    name = R.team_name(t)
    return _ALL_STAR_SLOTS.get(t, name) if ' / ' in name else name


def contract_violations(R):
    """pid -> (name, team) for players whose contract team is a team they are not on."""
    U, P = R.U, R.P
    on = {}
    for i in range(U.cur_rec):
        on.setdefault(R.link_to_pid[U.get(i, 'TWSX')], set()).add(U.get(i, 'BSXd'))
    bad = {}
    for prow in range(P.cur_rec):
        b = P.get(prow, 'BSXd')
        if not b:
            continue
        t = b - 1
        teams = on.get(P.get(prow, 'zIBw'), set())
        same = {t, L.MIRROR_OF.get(t, t)} | set(L.MIRRORS.get(t, []))
        if not same & teams:
            bad[P.get(prow, 'zIBw')] = (R.name(prow), t)
    return bad


def style_problems(R, source, free=lambda pid: False):
    """The player types (playerstyle, `sFgQ`): every roster entry carries the type of its player's skater or goalie
    record, and a type the update changed or gave a new player (or a player moved between forward and defence) is one
    of his kind's (ratings.STYLE_CHOICES; Builder.set_style). What the source already had is not blamed, and a player
    the player's own edits changed (`free(pid)`) may have any type of a skater / of a goalie (ratings.FREE_STYLES)."""
    def records(X):
        out = {}
        for tname in ('yvSd', 'yuHm'):
            t = X.f[tname]
            for i in range(t.cur_rec):
                out[t.get(i, 'zIBw')] = t.get(i, 'sFgQ')
        return out

    def unlike(X, rec):
        pids = (X.link_to_pid.get(X.U.get(e, 'TWSX')) for e in range(X.U.cur_rec))
        return {pid for e, pid in enumerate(pids) if pid in rec and X.U.get(e, 'sFgQ') != rec[pid]}

    now, before = records(R), records(source)
    out = [f"{R.name(R.p_by_id[pid])}: a roster place shows another player type than his record"
           for pid in sorted(unlike(R, now) - unlike(source, before)) if pid in R.p_by_id]
    kind_before = {source.P.get(i, 'zIBw'): ratings.style_class(source.P.get(i, 'aljv')) for i in range(source.P.cur_rec)}
    words = {'F': 'forward', 'D': 'defenceman', 'G': 'goalie'}
    for prow in range(R.P.cur_rec):
        pid = R.P.get(prow, 'zIBw')
        style, kind = now.get(pid), ratings.style_class(R.P.get(prow, 'aljv'))
        if style is None or (before.get(pid) == style and kind_before.get(pid) == kind):
            continue
        if style not in (ratings.FREE_STYLES if free(pid) else ratings.STYLE_CHOICES)[kind]:
            out.append(f"{R.name(prow)} has player type {style}, which no {words[kind]} has")
    return out


def rating_problems(R, source, free=lambda pid: False):
    """The ratings and tendencies the full ratings are written into (schema.FULL_RATED, FULL_ASIS; Builder.rate_full):
    every value one the game's own players hold (a rating 0-63, that is 36-99; fighting 0-3, consistency 0-2, paddle
    down 0-1, the three biases 0-15). A value the source already had for the same player is not blamed, and neither is a
    player the player's own edits changed (`free(pid)`): the fields' own room still holds him."""
    out = []
    for kind, tname in FULL_TABLE.items():
        t, s = R.f[tname], source.f[tname]
        tags = FULL_TAG[kind]
        ranges = ([(tags[n], n, RATING_RANGE) for n in FULL_RATED[kind]]
                  + [(tags[n], n, ASIS_RANGE[n]) for n in FULL_ASIS[kind] if n in ASIS_RANGE])
        before = {s.get(i, 'zIBw'): i for i in range(s.cur_rec)}
        for i in range(t.cur_rec):
            pid, j = t.get(i, 'zIBw'), before.get(t.get(i, 'zIBw'))
            if free(pid):
                continue
            for tag, name, (lo, hi) in ranges:
                v = t.get(i, tag)
                if not lo <= v <= hi and (j is None or s.get(j, tag) != v):
                    prow = R.p_by_id.get(pid)
                    who = R.name(prow) if prow is not None else f"player {pid}"
                    out.append(f"{who}: {name.removeprefix('c_')} {v} is outside {lo}-{hi}")
    return out


def multi_club(R):
    """pids on two different club teams (mirror copies count as one team)."""
    U = R.U
    club = L.CLUB | set(L.MIRROR_OF)
    teams = {}
    for i in range(U.cur_rec):
        t = U.get(i, 'BSXd')
        if t in club:
            teams.setdefault(R.link_to_pid[U.get(i, 'TWSX')], set()).add(L.MIRROR_OF.get(t, t))
    return {pid for pid, ts in teams.items() if len(ts) > 1}


def layout_mirrors(R):
    """The custom copies of NHL teams `R`'s layout keeps in step (layout.mirrors): none in the game's own roster; a
    roster of no known layout is checked as the community's."""
    try:
        return L.mirrors(L.check_base(R))
    except L.LayoutError:
        return L.MIRRORS


def structure(R, full_lineup=FULL_LINEUP, mirrors=None):
    """Structural flaws of a roster as {key: message}; keys do not depend on record order.

    Teams in `full_lineup` must be playable: 20 dressed with every line slot filled. `mirrors`: the copies that must
    equal their NHL team (default: those of `R`'s own layout, layout_mirrors).
    Also returns per-team line-up facts for the report."""
    U, P, Q = R.U, R.P, R.Q
    flags = [n for n, f in U.fields.items() if f.bits == 1 and n != 'jZSh']
    goal_tags = {SLOT_TAG['g1'], SLOT_TAG['g2']}
    out, teams = {}, {}
    by_team = {}
    for i in range(U.cur_rec):
        by_team.setdefault(U.get(i, 'BSXd'), []).append(i)
    pid = lambda i: R.link_to_pid[U.get(i, 'TWSX')]

    # lines: no slot held twice, dressed == holds a slot; playable teams dress a legal 20
    for t in range(R.T.cur_rec):
        ents = by_team.get(t, [])
        for p, n in Counter(pid(i) for i in ents).items():
            if n > 1:
                out[('twice', t, p)] = f"{_team(R, t)} lists {R.name(R.p_by_id[p])} {n} times"
        held = Counter(f for i in ents for f in flags if U.get(i, f))
        if any(v > 1 for v in held.values()):
            out[('slot twice', t)] = f"{_team(R, t)}: a line slot is held by two players"
        for i in ents:
            if bool(U.get(i, 'jZSh')) != any(U.get(i, f) for f in flags):
                out[('dressed', t, pid(i))] = f"{_team(R, t)}: {R.name(R.p_by_id[pid(i)])} dressed flag and line slots disagree"
        for i in ents:          # goalies play in goal only, and only goalies do (the Roster editor's Lines keep it)
            goalie = P.get(R.p_by_id[pid(i)], 'aljv') == 4
            if any(U.get(i, f) for f in flags if (f in goal_tags) != goalie):
                out[('goalie', t, pid(i))] = (f"{_team(R, t)}: {R.name(R.p_by_id[pid(i)])} "
                                              f"{'is a goalie in a skater slot' if goalie else 'is a skater in goal'}")
        dressed = [i for i in ents if U.get(i, 'jZSh')]
        pos = Counter('CLRDG'[P.get(R.p_by_id[pid(i)], 'aljv')] for i in dressed)
        teams[t] = {'players': len(ents), 'dressed': len(dressed), 'slots': len(held), 'positions': dict(pos)}
        if t in full_lineup and ents:
            if len(dressed) != 20 or pos['G'] != 2 or pos['D'] < 6:
                mix = ", ".join(f"{pos[k]} {name}" for k, name in
                                (('C', 'C'), ('L', 'LW'), ('R', 'RW'), ('D', 'D'), ('G', 'G')) if pos[k])
                out[('lineup', t)] = (f"{_team(R, t)} dresses {len(dressed)} players ({mix or 'none'}); "
                                      "the game needs 20 with 2 G and at least 6 D")
            elif len(held) != len(flags):
                out[('slots', t)] = f"{_team(R, t)} has {len(held)} of {len(flags)} line slots filled"

    # mirrors identical to their primary team
    def sig(t):
        return {pid(i): tuple(U.get(i, f) for f in flags + ['jZSh', 'lcCm', 'tRVs']) for i in by_team.get(t, [])}
    for prim, ms in (layout_mirrors(R) if mirrors is None else mirrors).items():
        for m in ms:        # sig is by player: the count catches a copy that lists someone twice
            if sig(prim) != sig(m) or len(by_team.get(prim, [])) != len(by_team.get(m, [])):
                out[('mirror', m)] = f"{_team(R, m)} (team {m}) is not an exact copy of {_team(R, prim)}"

    # free agents are listed once, are on no club team (national teams, copies and event teams do not count) and carry
    # no contract
    # (the game itself saved a tester's Sakic on Colorado and on the list; Builder.unlist_club_players mends that)
    club_of, copies = {}, {m for ms in (layout_mirrors(R) if mirrors is None else mirrors).values() for m in ms}
    for t in sorted(by_team):
        if t not in L.NATIONAL and t not in copies and t not in L.EVENTS:
            for i in by_team[t]:
                club_of.setdefault(pid(i), t)
    listed = Counter(R.link_to_pid.get(Q.get(k, 'TWSX')) for k in range(Q.cur_rec))
    for k in range(Q.cur_rec):
        p = R.link_to_pid.get(Q.get(k, 'TWSX'))
        prow = R.p_by_id.get(p)
        if prow is None:
            out[('fa link', Q.get(k, 'TWSX'))] = "a free-agent entry points at no player"
            continue
        if listed[p] > 1:
            out[('fa twice', p)] = f"free agent {R.name(prow)} is on the free-agent list twice"
        if p in club_of:
            out[('fa on team', p)] = f"free agent {R.name(prow)} is also on {_team(R, club_of[p])}"
        if any(P.get(prow, f) for f in ('BSXd', 'GDhI', 'dhKk', 'IrlK', 'IzRv')):
            out[('fa contract', p)] = f"free agent {R.name(prow)} still has contract data"

    # draft: a pick has a year, a round and an overall pick; an undrafted player (255) none
    for prow in range(P.cur_rec):
        year, rnd, overall = P.get(prow, 'WzKY'), P.get(prow, 'Ujcc'), P.get(prow, 'WfTt')
        if (rnd > 0) != (overall > 0) or (rnd > 0 and year == 255) or (year == 255 and P.get(prow, 'uWgv')):
            out[('draft', P.get(prow, 'zIBw'))] = (f"{R.name(prow)}: draft year {year}, round {rnd}, pick {overall} "
                                                   "do not fit together")

    # letters: any number of C / A is allowed (the player's own choice; lab round 55 played none, all C, all A and a
    # goalie's in Play Now). The update's own lines keep three letters per NHL team (builder, lines.check_lineup).
    # NHL teams: every player under contract
    for t in range(32):
        for i in by_team.get(t, []):
            prow = R.p_by_id[pid(i)]
            if not P.get(prow, 'GDhI') or not P.get(prow, 'dhKk'):
                out[('no contract', pid(i))] = f"{R.name(prow)} ({_team(R, t)}) has no contract"

    # roster entry ids: team * 40 + slot, slots 0..n-1 per team, at most 40 players per team
    for t, ents in by_team.items():
        ids = sorted(U.get(i, 'XWot') for i in ents)
        if len(ents) > L.MAX_PER_TEAM:
            out[('too many', t)] = f"{_team(R, t)} has {len(ents)} players (the game allows {L.MAX_PER_TEAM})"
        elif ids != [t * L.MAX_PER_TEAM + k for k in range(len(ents))]:
            out[('entry ids', t)] = f"{_team(R, t)}: roster entry ids are not consecutive"
    return out, teams


NO_MARKER = b'\x00\x00\xff\xff'      # a table header's word at 0x18 when no row was removed last


def contract_edit_problems(R, deals, scale, free=False):
    """Problems of the contracts the player set by hand ({player row: deal}, real dollars; `scale` the roster's money
    scale): the fields are not that deal, the deal is one the game cannot hold (NHL bounds in an NHL organisation, free
    amounts with another club: contracts.edit_problems), or the player is on no club (contracts.contract_home). The
    contract's team (cPbu.team) is checked for everyone (contract_violations). `free` (free editing): only the first; a
    deal on a player on no club is the player's own choice."""
    scale = contracts.GAME if scale is None else scale
    clubs = contracts.contract_clubs(R) if deals else set()
    out = []
    for prow, deal in sorted((deals or {}).items()):
        name = R.name(prow)
        if any(R.P.get(prow, f) != v for f, v in contracts.terms(deal, scale).items()):
            out.append(f"{name}: the contract in the roster is not the contract set by hand")
        if free:
            continue
        teams = {t for _, t in R.teams_of(prow)}
        home = contracts.contract_home(R.P, prow, teams, clubs)
        if home is None:
            out.append(f"{name}: a contract set by hand, but he is on no club and with no NHL organisation")
            continue
        out += [f"{name}: {text}" for text in contracts.edit_problems(deal, nhl=home[1])]
    return out[:20]


def verify(built, source, nhl_players=None, rebuilt=(), edited=None, league_moves=(), calendar=None, calendar_source=None,
           farm_patch=False, depth=None, money=None, deals=None, crests=None, contract_edits=None, prospects=None,
           league_calendars=None, free=None):
    """Check `built` (bytes of a SYS-DATA) against `source` (the Roster it was built from).

    `nhl_players`: the official rosters the build used; when given, every listed player must be
    on exactly his NHL team. `rebuilt`: club teams the build filled from scratch; they must be
    fully playable whatever the source had in those slots. `edited`: (player keys, player rows)
    the player's own edits changed on purpose; only the official-roster check lets them differ.
    `league_moves`: team slots allowed to change league (only the in-game league test, lab.py).
    `calendar`: what schedule.apply returned when the calendar step ran: the schedule tables are then checked
    (schedule.check); otherwise they must be the source's (or `calendar_source`'s: the game's own calendar put back).
    `farm_patch`: a roster made for the 32-team game patch (only `cli team32-test`): the farm teams and the farm calendar
    follow the patched Season's farm league (gamepatch.check_farm) instead of the source's, the 32 NHL teams are in
    the four divisions, 8 in each, Utah, Seattle and Vegas named (gamepatch.check_divisions), and the All-Star places and the calendar's one All-Star
    row are right (gamepatch.check_all_star), the next seasons' calendar is the same 32-team calendar
    (gamepatch.check_future), every team plays 84 games in calendar tables grown to hold them (gamepatch.check_games),
    and every farm club (Vegas: its own roster) holds enough of its NHL team's players for call-ups (gamepatch.check_rights),
    and Coachella Valley / Henderson are in the AHL (gamepatch.check_league_fit; without `farm_patch` they may only move to
    the Custom league).
    `depth` ({player row: NHL slot}): players NHL.com does not list who may be on that NHL roster (called up to fill a
    line-up, Builder.call_ups). `money`: the roster's money scale (contracts.scale_of): every deal the update wrote or
    moved is one the game can hold (contracts.problems). `deals` (data pack `contracts`, the real 2026-27 deals): a player
    NHL.com does not list may be on the NHL roster of the organisation he is under contract with
    (Builder.contract_keeps), and only that one.
    `crests` ({slot: art id}): custom teams whose own crest picture the photos install (the Roster editor's kit): that art
    id is theirs alone (custom_kit.problems, which also checks the custom teams' designs and colour table).
    `contract_edits` ({player row: deal}): contracts the player set by hand (edits.apply_contracts): each player holds
    exactly that deal on the roster's scale, one the game can hold (contracts.edit_problems), and is with an NHL
    organisation (contract_edit_problems).
    `prospects` (draftclass.apply): the player's draft-class players: each is eligible for his class, undrafted, on a
    European or CHL club and has a potential inside his growth tier's band (draftclass.problems).
    `league_calendars` ({part: what schedule.apply_league returned}): the club leagues' calendars the update wrote, each
    one the game can play (schedule.check_league); every other league's table stays the source's.
    `free` (free editing, owner 2026-10-29): what the player's own edits did that only our caution refused and the game
    plays: True (an edit-only save: everything is the player's) or (player rows, team slots) the edits changed. Those
    players / teams are not held to a player type of their position, one club, a contract with the team they are on, an
    NHL contract, a draft that fits together, the rating range or a line-up of 20 (FREE_TEAM_FLAWS, FREE_PLAYER_FLAWS).
    What would stop the roster loading stays a problem for everyone. info['heads_up'] names the player's teams with fewer
    than 2 goalies / 18 skaters (the game hangs the first game played with one).
    Returns (problems, info); the save must not be used if there are problems."""
    edited_keys, edited_rows = edited or (set(), set())
    rebuilt = set(rebuilt)
    try:
        problems = list(check_chain(built))
        R = Roster(built)      # re-parses: section, DB and table CRCs checked on load
    except Exception as err:   # not even readable: nothing else can be checked
        return [f"the save cannot be read back: {err}"], {}
    U, P, T = R.U, R.P, R.T

    # hard limits of the game: no new teams, no team changes league. The one exception (owner, 2026-10-19 and 2026-11-02):
    # Coachella Valley and Henderson are in the AHL's Pacific and the Vees in the WHL's B.C. Division (gamepatch.LEAGUE_SLOTS)
    # on a roster for the game patch (stage Y) and in the Custom league on any other (the unpatched game lists a created
    # team under Custom only)
    if T.cur_rec != source.T.cur_rec:
        problems.append(f"team count changed from {source.T.cur_rec} to {T.cur_rec}")
    else:
        for t in range(T.cur_rec):
            if T.get(t, 'jjMx') == source.T.get(t, 'jjMx') or t in league_moves:
                continue
            if t in gamepatch.in_the_roster(R, gamepatch.LEAGUE_SLOTS) and gamepatch.league_of(R, t) == (
                    gamepatch.LEAGUE_SLOTS[t] if farm_patch else gamepatch.CUSTOM_GROUPS):
                continue
            problems.append(f"{_team(R, t)} changed league")
    # the art ids Coachella Valley and Henderson get (layout.OWN_ART) belong to them alone: another team with one would
    # show their logo and jerseys (one the source already had there is not blamed)
    for t in range(T.cur_rec):
        art = T.get(t, 'artid')
        if art in L.OWN_ART.values() and L.OWN_ART.get(t) != art and source.T.get(t, 'artid') != art:
            problems.append(f"{_team(R, t)} has art id {art}, which is kept for another team")
        if art in L.CLUB_ART.values() and (L.CLUB_ART.get(t) != art or not farm_patch):     # 900-902: the patched game only
            problems.append(f"{_team(R, t)} has art id {art}, which only Coachella Valley / Henderson / the Vees have in the "
                            "patched game")
    # an NHL team's farm team (ttOk.ahlaffiliate, slot + 1) is an AHL club of slots 32-61 that serves no other NHL team
    # (the AHL step pairs them by the list's organisations, clubs.pair_farms)
    # (what the source already had is not blamed)
    farms = {n: T.get(n, gamepatch.AFFILIATE) - 1 for n in range(30) if T.get(n, gamepatch.AFFILIATE)}
    farms_before = {n: source.T.get(n, gamepatch.AFFILIATE) - 1 for n in range(30)
                    if source.T.get(n, gamepatch.AFFILIATE)}
    problems += [f"{_team(R, n)} names slot {f} as its farm team" for n, f in farms.items()
                 if not 32 <= f < 62 and farms_before.get(n) != f]
    problems += [f"farm team {_team(R, f)} serves {list(farms.values()).count(f)} NHL teams"
                 for f in sorted(set(farms.values()))
                 if list(farms.values()).count(f) > max(1, list(farms_before.values()).count(f))]
    # the custom teams' looks (the Roster editor's kit, custom_kit.py): designs the game draws, logos it has, its colour
    # table's rows as they were, a crest picture on one team only
    problems += custom_kit.problems(R, source, crests)

    # no table keeps the "last removed row" marker the community roster has in the entry and link tables
    # (Season mode crashed on the player it names, owner 2026-10-06)
    problems += [f"table {name} still names a removed row (the update clears it)" for name in R.f.tables
                 if bytes(R.f[name].header[0x18:0x1C]) != NO_MARKER]

    # every table keeps the room the game gives it (its own database + maxinsert of db/nhlng-meta.xml); only a roster for
    # the game patch has more calendar rows, whose meta file gives the game that room (gamepatch.check_games)
    grown = gamepatch.CALENDAR_TABLES if farm_patch or (calendar or {}).get('variant') == schedule.ALL_PATCH else ()
    problems += [f"table {name} has room for {R.f[name].max_rec} rows, the game gives it {source.f[name].max_rec}"
                 for name in R.f.tables if name in source.f.tables and name not in grown
                 and R.f[name].max_rec != source.f[name].max_rec]

    # team strategies (the Roster editor's Strategies): every value one the game's menus offer (strategy.py)
    if strategy.TABLE in R.f.tables and strategy.TABLE in source.f.tables:
        problems += sorted(strategy.out_of_range(R, source).values())

    # the calendar: the schedule tables are the source's, or what the calendar step wrote and the game's rules allow
    if farm_patch:
        problems += (gamepatch.check_farm(R) + gamepatch.check_divisions(R) + gamepatch.check_all_star(R)
                     + gamepatch.check_future(R) + gamepatch.check_games(R) + gamepatch.check_rights(R)
                     + gamepatch.check_league_fit(R) + gamepatch.check_art_fit(R))
    written = league_calendars or {}
    for part, expected in sorted(written.items()):
        problems += schedule.check_league(R, part, expected)
    written_tags = tuple(schedule.LEAGUES[part][0] for part in written)
    if calendar is not None:
        problems += schedule.check(R, source, calendar, others=written_tags + (
            (gamepatch.FARM_TABLE, gamepatch.FUTURE_TABLE) if farm_patch else ()))
    else:
        base = calendar_source or source
        kept = ('ihmS', 'Iwiq', 'byED') + tuple(tag for tag in schedule.LEAGUE_TAGS if tag not in written_tags
                                                 and not (farm_patch and tag == gamepatch.FARM_TABLE))
        problems += [f"schedule table {tag} changed" for tag in kept if
                     R.f[tag].cur_rec != base.f[tag].cur_rec or any(
                         R.f[tag].record_bytes(i) != base.f[tag].record_bytes(i) for i in range(base.f[tag].cur_rec))]

    # every link resolves to a player, every roster entry id is unique
    for i in range(U.cur_rec):
        if R.link_to_pid.get(U.get(i, 'TWSX')) not in R.p_by_id:
            problems.append(f"roster entry {i} points at no player")
    xw = U.column('XWot')
    if len(set(xw)) != len(xw):
        problems.append("duplicate roster entry ids")
    if problems:   # the checks below assume resolvable links
        return problems, {}

    # official rosters: each player exactly on his team among the 32 primary slots
    if nhl_players:
        api = match(R, [dict(p) for p in nhl_players
                        if person_key(p['first'], p['last'], p['birth']) not in edited_keys])
        for p in api:
            if p['row'] in edited_rows:
                continue
            if p['row'] is None:
                problems.append(f"not found: {p['first']} {p['last']}")
                continue
            slots = [t for _, t in R.teams_of(p['row']) if t < 32]
            if slots != [L.API_TO_SLOT[p['team']]]:
                problems.append(f"{p['first']} {p['last']} on {slots}, expected {L.API_TO_SLOT[p['team']]}")
        api_rows = {p['row'] for p in api}
        held = {}       # player row -> the NHL slot of the organisation holding his deal: the source's record of him
        name = lambda roster, row: (roster.P.get(row, 'PedH'), roster.P.get(row, 'RMbQ'))
        for roster in (source, R):              # (still his: not reused for someone else) or the new roster's
            for d in closest(match(roster, [dict(d, birth=tuple(d['birth'])) for d in deals or ()])):
                row = d['row']
                if row is not None and d['org'] in L.API_TO_SLOT and row < R.P.cur_rec                         and (roster is R or name(R, row) == name(source, row)):
                    held.setdefault(row, L.API_TO_SLOT[d['org']])
        for t in range(32):
            for _, prow, name, _, _ in R.team_roster(t):
                if prow not in api_rows and prow not in edited_rows and (depth or {}).get(prow) != t                         and held.get(prow) != t:
                    problems.append(f"{name} still on {L.SLOT_TO_API[t]}")

    mine_pid, mine_team = free_editing(R, source, free)
    mirrors = layout_mirrors(source)       # the build keeps its source's layout: the same copies are checked in both
    now, teams = structure(R, set(FULL_LINEUP) | rebuilt, mirrors)
    before, teams_before = structure(source, mirrors=mirrors)
    problems += [msg for key, msg in now.items()
                 if (key not in before or (key[0] in TEAM_FLAWS and key[1] in rebuilt))
                 and not (key[0] in FREE_TEAM_FLAWS and mine_team(key[1]))
                 and not (key[0] in FREE_PLAYER_FLAWS and mine_pid(key[1]))]

    # contracts: cPbu.team = team + 1 must point at a team the player is on (mirror slots count)
    baseline = contract_violations(source)
    for p, (name, t) in contract_violations(R).items():
        if p not in baseline and not mine_pid(p):
            problems.append(f"{name} contracted to team {t} but not on it")
    # nobody on two different club teams (unless the player put him there)
    for p in multi_club(R) - multi_club(source):
        if not mine_pid(p):
            problems.append(f"{R.name(R.p_by_id[p])} is on two club teams")
    # player types and faces (the Roster editor's Type and Face): only values the game's own players have; a created
    # look only on the records the game's Create Player uses, with its choices, its player listed through the
    # record's own link
    problems += style_problems(R, source, mine_pid) + faces.problems(R, source) + faces.look_problems(R, source)
    problems += faces.link_problems(R, source)
    # sticks (sticks.team_sticks, the editor): only models the game can draw, or ones the roster already carried
    problems += sticks.problems(R, also=sticks.worn(source))
    # helmets, gloves, skates and goalie gear (equipment.fix_models): the same
    problems += equipment.model_problems(R, also=equipment.worn(source))
    # ratings and tendencies (the full ratings, the estimate, the editor): only values the game's own players hold
    problems += rating_problems(R, source, mine_pid)
    if money is not None:
        problems += contracts.problems(R, source, money, mine_pid)
    problems += contract_edit_problems(R, contract_edits, money, free=bool(free))
    # NHL rights only of teams the game's Season knows: Seattle's on a roster for the unpatched game crashed it
    problems += contracts.rights_problems(R)
    # contract status: the game shows a contract (Team Rosters' CONT / SAL) only for status 1 (contracts.status_fit)
    problems += contracts.status_problems(R, source)
    # the UFA year: birth year + 27 (contracts.ufa_fit), so that Be a GM shows UFA / RFA after a deal's last season
    problems += contracts.ufa_problems(R, source)
    # the player's draft classes (draftclass.apply): eligible, undrafted, on a European / CHL club, a potential the game
    # keeps; a patch roster holds birth years as real - 1911 (gamepatch.year_shift)
    problems += draftclass.problems(R, prospects, base=1911 if farm_patch else 1910)

    # not fatal, but worth telling the user: AHL teams that lost players and cannot ice a full line-up
    # (when the AHL step did not rebuild them)
    thinner = [f"{_team(R, t)} ({teams[t]['players']} players, was {teams_before[t]['players']})"
               for t in sorted(L.AHL) if t not in rebuilt and teams[t]['players'] < min(teams_before[t]['players'], 20)]
    info = {'entries': U.cur_rec, 'players': P.cur_rec, 'free_agents': R.Q.cur_rec,
            'known_flaws_in_source': len(before), 'thinner_ahl_teams': thinner, 'rebuilt_teams': sorted(rebuilt),
            'empty_national_teams': [_team(R, t) for t in range(133, 154) if not teams[t]['players']],
            'teams': teams, 'heads_up': short_teams(R, source, teams, teams_before, mine_team) if free else []}
    return problems, info


def free_editing(R, source, free):
    """(is this player id the player's own?, is this team slot?) for verify's `free`: True = everything; (player rows,
    team slots) = those players, the given teams and every team such a player is on now or was on in `source`."""
    if free is True:
        return (lambda pid: True), (lambda t: True)
    if not free:
        return (lambda pid: False), (lambda t: False)
    rows, slots = free
    pids = {R.P.get(r, 'zIBw') for r in rows if r < R.P.cur_rec}
    teams = set(slots)
    for X in (R, source):
        U = X.U
        for i in range(U.cur_rec):
            if X.link_to_pid.get(U.get(i, 'TWSX')) in pids:
                teams.add(U.get(i, 'BSXd'))
    return pids.__contains__, teams.__contains__


def short_teams(R, source, teams, teams_before, mine_team):
    """The player's teams that hold players but fewer than 2 goalies or 18 skaters, as plain sentences: the game hangs
    the first game the player plays with one (round 17; the engine's line picker waits forever for a player of a kind,
    docs/notes/autoplay.md). Only a team whose players changed from `source`; national teams, copies, event teams and
    prospect pools are left out."""
    from .leagues import pools
    def goalies(X):
        out = {}
        for i in range(X.U.cur_rec):
            pid = X.link_to_pid.get(X.U.get(i, 'TWSX'))
            if pid in X.p_by_id and X.P.get(X.p_by_id[pid], 'aljv') == 4:
                out[X.U.get(i, 'BSXd')] = out.get(X.U.get(i, 'BSXd'), 0) + 1
        return out
    now, before = goalies(R), goalies(source)
    out = []
    for t in sorted(teams):
        if (not teams[t]['players'] or not mine_team(t) or t in L.NATIONAL or t in L.MIRROR_OF
                or t in L.EVENTS or pools.is_pool(R, t)):
            continue
        g = now.get(t, 0)
        skaters = teams[t]['players'] - g
        if g >= SHORT_GOALIES and skaters >= SHORT_SKATERS:
            continue
        if (g, teams[t]['players']) == (before.get(t, 0), (teams_before.get(t) or {}).get('players')):
            continue
        out.append(f"{_team(R, t)} has {g} goalie{'' if g == 1 else 's'} and {skaters} skaters: the game hangs if "
                   "you play a game with them (a team needs 2 goalies and 18 skaters)")
    return out


def career_problems(before, after, allowed=(), sizes=None):
    """What is wrong with a changed Be a Pro career (`after`, bytes) next to the bytes it was read from (`before`).
    `allowed`: the kinds of edit made (careersave.EDITABLE: 'name', 'xp'); `sizes`: the DATA files it was read from.

    Only the allowed bytes of the pro (chunk 8, chunk 24) and the allowed fields of his own database rows may differ;
    every other chunk, table, row, count and room, and the old bytes after the last chunk stay as they were. The
    values are ones the game can hold, the save reads back as written, and its checksums are right."""
    from . import careersave as K
    try:
        old, new = K.Career(before), K.Career(after)
    except K.CareerError as e:
        return [f"the changed career cannot be read: {e}"]
    problems = []
    unknown = set(allowed) - set(K.EDITABLE)
    if unknown:
        return [f"no career edit called {', '.join(sorted(unknown))}"]
    if len(after) != len(before) or new.end != old.end or new.tail != old.tail:
        problems.append("the changed career has another size")
    if sizes is not None:
        try:
            K.pieces(after, sizes)
        except K.CareerError:
            problems.append("the changed career does not fit its DATA files")
    if new.build() != bytes(after):
        problems.append("the changed career does not read back as written")
    known = check_chain(bytes(before[:old.end]))           # (0x10 stops at the chunks: Career checks it)
    problems += [p for p in check_chain(bytes(after[:new.end])) if '0x10' not in p and p not in known]

    # the chunks: the same kinds and lengths; only the allowed bytes of chunks 8 and 24
    ranges = {K.PRO_CHUNK: [r for k in allowed for r in K.EDITABLE[k]['pro']],
              K.XP_CHUNK: [r for k in allowed for r in K.EDITABLE[k]['xp']]}
    if [(c.kind, len(c.body)) for c in old.chunks] != [(c.kind, len(c.body)) for c in new.chunks]:
        problems.append("the changed career's parts differ")
    else:
        for a, b in zip(old.chunks, new.chunks):
            free = ranges.get(a.kind, [])
            moved = [i for i in range(len(a.body)) if a.body[i] != b.body[i]
                     and not any(lo <= i < hi for lo, hi in free)] if a.body != b.body else []
            if moved:
                problems.append(f"part {a.kind} of the career changed where no edit may (from byte {moved[0]:#x})")

    # the database: the same tables, counts and room; only the allowed fields of the pro's own rows
    fields = {}
    for k in allowed:
        for tag, names in K.EDITABLE[k]['rows'].items():
            fields.setdefault(tag, set()).update(names)
    if old.db.order != new.db.order:
        problems.append("the changed career's tables differ")
    else:
        for tag in old.db.order:
            a, b = old.db.tables[tag], new.db.tables[tag]
            if (a.header[4:], a.field_defs, a.tail) != (b.header[4:], b.field_defs, b.tail):   # 0: the chain's CRC
                problems.append(f"table {a.real_name} changed its size or fields")
                continue
            if a.records == b.records:
                continue
            mine = old._row(tag) if tag in fields else None
            for i in range(a.max_rec):
                if a.record_bytes(i) == b.record_bytes(i):
                    continue
                changed = {n for n in a.fields if a.get(i, n) != b.get(i, n)} if i < a.cur_rec else {'(unused)'}
                if i != mine or not changed <= fields[tag]:
                    problems.append(f"table {a.real_name} row {i} changed ({', '.join(sorted(changed))})")
                    break

    # the values: XP the game can hold, ratings typed in the window's range, names of 1-24 letters equal in chunk 8 and
    # the bio row
    pro = new.pro
    if 'xp' in allowed:
        problems += [f"XP for {p} is {v} (0 to {K.MAX_XP})" for p, v in pro.xp.items() if not 0 <= v <= K.MAX_XP]
    if 'ratings' in allowed:
        was = old.pro.ratings
        if pro.goalie:
            problems.append("ratings of a goalie career cannot be changed yet")
        problems += [f"the pro's {k} is {v} ({K.LOWEST} to {K.HIGHEST})" for k, v in pro.ratings.items()
                     if v != was.get(k) and not K.LOWEST <= v <= K.HIGHEST]
    if 'name' in allowed:
        body, row = new.chunk(K.PRO_CHUNK), new.bio_row()
        for key, tag in (('first', K.FIRST), ('last', K.LAST)):
            raw = bytes(body[K.AT[key]:K.AT[key] + K.NAME_SIZE])
            text = raw.split(b'\0')[0]
            if not text or b'\0' not in raw or raw[len(text):].strip(b'\0'):
                problems.append(f"the pro's {key} name is empty or too long")
            elif row is not None and new.db.tables[K.BIO].get(row, tag) != text.decode('latin1'):
                problems.append(f"the pro's {key} name differs in his player row")
    return problems
