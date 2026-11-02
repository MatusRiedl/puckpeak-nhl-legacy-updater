"""Players' contracts in a roster (table cPbu) and the money scale of a save.

A contract is the cap hit per season `dhKk` in units of UNIT dollars (13 bits), the seasons left `GDhI` (this one
included), two-way `DVoL`, multi-year `gHmt` (= two seasons or more, as the community roster keeps it), and an
extension that starts next season: years `IrlK`, cap hit `IzRv`, two-way `xdoJ` (docs/notes/contracts.md).

The game's own salary cap is $71.4M (docs/notes/salary-cap.md). A roster for the 32-team game patch holds real 2026-27
dollars (REAL) and the patch raises the cap to 2026-27's; every other roster holds them times GAME = 71.4 / 104.0, so
that a team's payroll fits the game's cap as the real one fits the real cap (owner, 2026-10-16). `rescale` moves a
roster's money from one scale to the other once, when a normal roster becomes a patch roster or back.

The real deals come from the data pack part `contracts` (made by the maintainer's private tools, DEVELOPING.md):
    {'first', 'last', 'birth': [y, m, d], 'pos': 'C', 'org': 'EDM', 'cap': 12500000, 'years': 2, 'two_way': 0,
     'ext': [years, cap, two_way]}       (ext only when he has signed an extension)
Those are NHL contracts only: nobody outside an NHL organisation has one there, nor in the game's own roster. Since
2026-10-22 (owner: "a tool to actually make it happen for players to have contracts") every club player without a deal
and without NHL rights gets a made-up starter deal with his club (`starter_terms`), and a contract set by hand may be with
any club (`contract_home`, free amounts outside NHL organisations: `edit_problems(nhl=False)`).
"""
from . import layout as L

UNIT = 5000
SEASON = 2026                   # the season the figures are for (2026-27)
CAP, FLOOR = 104_000_000, 76_900_000
MINIMUM, MAXIMUM = 850_000, 20_800_000          # league minimum, the most one player may earn (20 % of the cap)
ENTRY_LEVEL = 975_000           # the most an entry-level deal pays
GAME_CAP = 71_400_000
REAL, GAME = 1.0, GAME_CAP / CAP
FIELDS = ('dhKk', 'GDhI', 'DVoL', 'gHmt', 'IrlK', 'IzRv', 'xdoJ')
LOWEST = 400_000                # verify: an NHL cap hit below this (real) is a wrong unit, not a deal


def scale_of(patch_roster):
    """The money scale of a roster: REAL for one made for the game patch, else GAME."""
    return REAL if patch_roster else GAME


def units(dollars, scale, bits=13):
    """Dollars on `scale` in the save's units, at least 1 and at most what the field holds."""
    return max(1, min((1 << bits) - 1, round(dollars * scale / UNIT)))


def dollars(value, scale):
    """The real dollars a field value on `scale` stands for."""
    return value * UNIT / scale


def default_terms(entry_level, scale):
    """(seasons, cap hit in units) of the deal a player gets who has none: three seasons at the entry-level maximum
    for a young player, else one season at the league minimum."""
    return (3, units(ENTRY_LEVEL, scale)) if entry_level else (1, units(MINIMUM, scale))


def rescale(P, factor):
    """Every cap hit and extension of the player table times `factor` (a roster moving to another scale). Returns the
    number of players changed."""
    changed = 0
    for prow in range(P.cur_rec):
        moved = False
        for f in ('dhKk', 'IzRv'):
            v = P.get(prow, f)
            if v:
                P.set(prow, f, max(1, min(P.field(f).mask, round(v * factor))))
                moved = True
        changed += moved
    return changed


def terms(deal, scale):
    """The field values of a deal from the data pack on `scale`."""
    years, cap, two = deal.get('ext') or (0, 0, 0)
    return {'dhKk': units(deal['cap'], scale), 'GDhI': max(1, min(15, deal['years'])), 'DVoL': int(bool(deal['two_way'])),
            'gHmt': int(deal['years'] >= 2), 'IrlK': min(15, years), 'IzRv': units(cap, scale) if years else 0,
            'xdoJ': int(bool(two)) if years else 0}


def write(P, prow, deal, scale):
    """Give player row `prow` the deal; True when anything changed."""
    return put(P, prow, terms(deal, scale))


def put(P, prow, values):
    """Write contract field values; True when anything changed."""
    changed = any(P.get(prow, f) != v for f, v in values.items())
    for f, v in values.items():
        P.set(prow, f, v)
    return changed


# A made-up starter deal for a club player who has none (owner, 2026-10-22): real dollars a season by the club's league
# and the player's overall (below 70, 70-74, 75-79, 80 and up), one-way, one season from 27 on, else two.
STARTER = {
    'AHL': (75_000, 125_000, 200_000, 300_000),                 # an AHL-only deal
    'NL': (250_000, 400_000, 600_000, 900_000),                 # National League
    'SHL': (150_000, 225_000, 325_000, 450_000),                # also the DEL
    'LIIGA': (100_000, 150_000, 250_000, 350_000),              # also the Extraliga
    'CHL': (10_000, 10_000, 15_000, 20_000),                    # the junior leagues
    'OTHER': (50_000, 75_000, 100_000, 150_000),                # Norway, custom teams
}
STARTER_AGE = 27


def starter_league(slot):
    """The STARTER row of a club."""
    if slot in L.AHL:
        return 'AHL'
    if slot in L.NL:
        return 'NL'
    if slot in L.SHL or slot in L.DEL:
        return 'SHL'
    if slot in L.LIIGA or slot in L.EXTRALIGA:
        return 'LIIGA'
    return 'CHL' if slot in L.CHL or slot == L.VEES else 'OTHER'


def starter_pay(slot, overall):
    """Real dollars a season of the starter deal at club `slot` for a player of `overall`."""
    band = 0 if overall < 70 else 1 if overall < 75 else 2 if overall < 80 else 3
    return STARTER[starter_league(slot)][band]


def starter_terms(slot, overall, age, scale):
    """The field values of the starter deal (STARTER) at club `slot` for a player of `overall` and `age`, on `scale`."""
    years = 1 if age >= STARTER_AGE else 2
    return {'dhKk': units(starter_pay(slot, overall), scale), 'GDhI': years, 'DVoL': 0, 'gHmt': int(years >= 2),
            'IrlK': 0, 'IzRv': 0, 'xdoJ': 0}


STATUS = 'QwoG'                 # contractstatus: 1 = under contract or an NHL team's rights, 0 = none (lab round 41)


def rights_teams(P):
    """How many NHL slots (0 .. n - 1) may hold a player's rights (proteam `WBbd`, slot + 1) on a roster with the player
    table `P`: all 32 on a roster for the game patch (six bits, gamepatch.rights_wide), 30 on one for the unpatched game.
    Its Season knows 30 NHL teams: five bits can store Seattle's (31), and a club player holding them crashed the start
    of a Season (its setup reads a 30-team table at 0x285628; a tester's NA game, 0.50.1). The community's roster gives
    Seattle and Vegas nobody's rights either."""
    return 32 if P.field('WBbd').bits > 5 else 30


def holds_rights(P, slot):
    """Can NHL slot `slot` hold a player's rights on this roster (rights_teams)?"""
    return 0 <= slot < rights_teams(P)


def drop_rights(R):
    """Players holding rights that no NHL slot of roster `R` may hold (rights_teams: Seattle's on a roster for the
    unpatched game, as 0.50.0 and 0.50.1 wrote them) hold nobody's, in place. Returns their player rows."""
    P, n = R.P, rights_teams(R.P)
    rows = [prow for prow in range(P.cur_rec) if P.get(prow, 'WBbd') > n]
    for prow in rows:
        P.set(prow, 'WBbd', 0)
    return rows


def rights_problems(R):
    """Texts naming players who hold rights no NHL slot of roster `R` may hold (rights_teams), empty when right."""
    P, n = R.P, rights_teams(R.P)
    rows = [prow for prow in range(P.cur_rec) if P.get(prow, 'WBbd') > n]
    if not rows:
        return []
    return [f"{len(rows)} players hold the NHL rights of slot {n} or later, which the unpatched game's Season does not "
            f"know (it crashes when a Season starts): " + ", ".join(R.name(prow) for prow in rows[:5])]


def status_of(P, prow):
    """The contract status a player on a club calls for. The game's own roster and the source hold 1 for every player
    whose rights an NHL team holds (proteam `WBbd`), deal or not, and 0 for everyone else; Team Rosters shows CONT / SAL
    only for 1 (lab round 41). So 1 with a deal (cap hit and seasons: an NHL deal, or a club's own since 2026-10-22) or
    with rights, 0 with neither, None (left as it is) for a cap hit without seasons, which the game's own roster has."""
    cap, years = P.get(prow, 'dhKk'), P.get(prow, 'GDhI')
    if cap:
        return 1 if years else None
    return 1 if P.get(prow, 'WBbd') else 0


def contract_clubs(R):
    """The teams of roster `R` whose players hold contracts with them: layout.CONTRACT_CLUB without the prospect pools
    (pools.is_pool: a pool is no club, its players are an NHL team's prospects)."""
    from .leagues.pools import is_pool
    return {t for t in L.CONTRACT_CLUB if t < R.T.cur_rec and not is_pool(R, t)}


def _status_rows(R):
    """(player rows with a place on a club, player rows on the free-agent list), from the tables."""
    P, U, C, Q = R.P, R.U, R.C, R.Q
    clubs = contract_clubs(R)
    link = {C.get(i, 'qEfv'): C.get(i, 'qFky') for i in range(C.cur_rec)}
    row = {P.get(i, 'zIBw'): i for i in range(P.cur_rec)}
    on = {row.get(link.get(U.get(i, 'TWSX'))) for i in range(U.cur_rec) if U.get(i, 'BSXd') in clubs}
    free = {row.get(link.get(Q.get(k, 'TWSX'))) for k in range(Q.cur_rec)}
    return on - {None}, free - {None} - on


def status_fit(R, rows=None):
    """Give every player on a club the contract status his deal calls for (status_of) and every free agent 0, in place;
    with `rows` only those player rows (the Roster editor's contract edits). The game's Team Rosters shows CONT / SAL
    only for status 1: players whom the update gave a deal on a record that had none (Eichel, Hanifin in Vegas, Seattle's
    prospects) showed "N/A" (lab round 41, docs/notes/contracts.md). Returns the number of players changed."""
    P = R.P
    on, free = _status_rows(R)
    changed = 0
    for prow in sorted((on | free) if rows is None else (on | free) & set(rows)):
        want = status_of(P, prow) if prow in on else 0
        if want is not None and P.get(prow, STATUS) != want:
            P.set(prow, STATUS, want)
            changed += 1
    return changed


def status_problems(R, source=None):
    """Texts naming the players whose contract status does not fit their deal (status_fit); with `source` (the roster
    `R` was made from) only players whose status, deal or place differs from the source's."""
    P = R.P
    on, free = _status_rows(R)
    before = {}
    if source is not None:
        s_on, s_free = _status_rows(source)
        before = {source.P.get(r, 'zIBw'): (source.P.get(r, STATUS), source.P.get(r, 'dhKk'), source.P.get(r, 'GDhI'),
                                            r in s_on, r in s_free) for r in range(source.P.cur_rec)}
    bad = []
    for prow in sorted(on | free):
        want, have = status_of(P, prow) if prow in on else 0, P.get(prow, STATUS)
        now = (have, P.get(prow, 'dhKk'), P.get(prow, 'GDhI'), prow in on, prow in free)
        if want is not None and have != want and before.get(P.get(prow, 'zIBw')) != now:
            bad.append(f"{P.get(prow, 'PedH')} {P.get(prow, 'RMbQ')}")
    if not bad:
        return []
    return [f"{len(bad)} players' contract status does not fit their contract (the game would show it wrong): "
            + ", ".join(bad[:5]) + (" ..." if len(bad) > 5 else "")]


# yearufa: the year a player becomes an unrestricted free agent, on the clock of his birth year. The game's own roster holds
# birth year + 27 for everyone; Be a GM's Contract Status shows UFA / RFA after a deal's last season by it (lab round 41:
# the community's values made Eichel an RFA at 32 and Bowman a UFA at 23)
UFA_YEAR, UFA_AGE = 'zKKG', 27


def ufa_of(P, prow):
    """The UFA year that fits the record's birth year (dnFq, on whatever clock the roster keeps it), None without one."""
    born = P.get(prow, 'dnFq')
    return min(born + UFA_AGE, P.field(UFA_YEAR).mask) if born else None


def ufa_fit(R, rows=None):
    """Give every player record (with `rows` only those) the UFA year of its birth year (ufa_of), in place. Runs after
    every birth-year change (pipeline.build after finish, patch_roster after year_shift). Returns the number changed."""
    P = R.P
    changed = 0
    for prow in range(P.cur_rec) if rows is None else sorted(rows):
        want = ufa_of(P, prow)
        if want is not None and P.get(prow, UFA_YEAR) != want:
            P.set(prow, UFA_YEAR, want)
            changed += 1
    return changed


def ufa_problems(R, source=None):
    """Texts naming the players whose UFA year does not fit their birth year (ufa_fit); with `source` (the roster `R` was
    made from) only players whose UFA year differs from the source's (the Roster editor's Save writes none, and a patch
    roster read for the editor has its birth years on our clock but its UFA years on the patch's)."""
    P = R.P
    before = {}
    if source is not None:
        before = {source.P.get(r, 'zIBw'): source.P.get(r, UFA_YEAR) for r in range(source.P.cur_rec)}
    bad = []
    for prow in range(P.cur_rec):
        want, have = ufa_of(P, prow), P.get(prow, UFA_YEAR)
        if want is not None and have != want and before.get(P.get(prow, 'zIBw')) != have:
            bad.append(f"{P.get(prow, 'PedH')} {P.get(prow, 'RMbQ')}")
    if not bad:
        return []
    return [f"{len(bad)} players' free-agent year does not fit their age (the game would show UFA / RFA wrong): "
            + ", ".join(bad[:5]) + (" ..." if len(bad) > 5 else "")]


def payroll(R, team, scale):
    """Real dollars of the cap hits of the players on NHL team `team`'s roster."""
    return sum(dollars(R.P.get(prow, 'dhKk'), scale) for _, prow, *_ in R.team_roster(team) if prow is not None)


def real(value, scale):
    """The real dollars a field value on `scale` stands for, as the window shows them: to the unit on the real scale; on
    the game's (one unit there is $7,283, so $12.5M comes back as $12,497,415) to $25,000 from $1M, below it to $1,000 (a
    junior club's $10,000 starter deal is one unit there: $7,000)."""
    exact = dollars(value, scale)
    step = UNIT if scale == REAL else 25_000 if exact >= 1_000_000 else 1_000
    return round(exact / step) * step


def money(amount):
    """'$12.5M', '$850k', '-$1.2M': real dollars in the player's words."""
    a = abs(amount)
    text = (f"${a / 1e6:.3f}".rstrip('0').rstrip('.') + 'M') if a >= 999_500 else f"${round(a / 1000)}k"
    return ('-' if amount < 0 else '') + text


def deal_of(P, prow, scale):
    """The deal player row `prow` holds, in the data pack's shape and real dollars (`real`): {'cap', 'years', 'two_way',
    'ext': [years, cap, two_way] or None}; cap 0 and years 0 when he has none."""
    cap, years = P.get(prow, 'dhKk'), P.get(prow, 'GDhI')
    if not cap or not years:
        return {'cap': 0, 'years': 0, 'two_way': 0, 'ext': None}
    ext_years, ext_cap = P.get(prow, 'IrlK'), P.get(prow, 'IzRv')
    return {'cap': real(cap, scale), 'years': years, 'two_way': P.get(prow, 'DVoL'),
            'ext': [ext_years, real(ext_cap, scale), P.get(prow, 'xdoJ')] if ext_years and ext_cap else None}


def cap_in(deal, season):
    """What `deal` counts against the cap in season number `season` (0 = 2026-27): its cap hit while it runs, then its
    extension's while that runs, else 0."""
    if not deal or not deal.get('cap'):
        return 0
    if season < deal['years']:
        return deal['cap']
    ext = deal.get('ext')
    return ext[1] if ext and season < deal['years'] + ext[0] else 0


# A contract the player sets by hand (edits.py "contract", the Front office): real dollars on either scale.
EDIT_YEARS = 8                  # the longest deal (and extension) the league allows
FREE_LOW = UNIT                 # the least a contract outside an NHL organisation pays (owner, 2026-10-22: free amounts)


def edit_problems(deal, nhl=True):
    """Why a contract the player set cannot go into a roster, in the player's words (empty when it can): 1 to EDIT_YEARS
    seasons; a cap hit from the lowest salary of 2026-27 (gamepatch.cap_of) to MAXIMUM; an extension of 1 to EDIT_YEARS
    seasons with a cap hit from the lowest salary of the season it starts to MAXIMUM (a fifth of 2026-27's cap; a fifth of
    a later cap is more, so MAXIMUM is the limit there too, and verify's `problems` holds it). A deal with a club outside
    the NHL organisations (`nhl` False: contract_home) may pay from FREE_LOW."""
    from .gamepatch import cap_of
    out = []
    years, cap, ext = deal.get('years'), deal.get('cap'), deal.get('ext')
    if not isinstance(years, int) or not 1 <= years <= EDIT_YEARS:
        out.append(f"a contract of {years} seasons (1 to {EDIT_YEARS})")
        years = 1
    low = cap_of(3, 0) if nhl else FREE_LOW
    if not isinstance(cap, int) or not low <= cap <= MAXIMUM:
        out.append(f"a cap hit of {money(cap or 0)} (from {money(low)} to {money(MAXIMUM)})")
    if ext:
        ext_years, ext_cap = (list(ext) + [None, None])[:2]
        low = cap_of(3, years) if nhl else FREE_LOW
        if not isinstance(ext_years, int) or not 1 <= ext_years <= EDIT_YEARS:
            out.append(f"an extension of {ext_years} seasons (1 to {EDIT_YEARS})")
        if not isinstance(ext_cap, int) or not low <= ext_cap <= MAXIMUM:
            out.append(f"an extension cap hit of {money(ext_cap or 0)} (from {money(low)} to {money(MAXIMUM)})")
    if deal.get('two_way') not in (0, 1, False, True) or (ext and len(ext) > 2 and ext[2] not in (0, 1, False, True)):
        out.append("two-way is neither yes nor no")
    return out


def organisation(P, prow, teams):
    """The NHL slot of the organisation a player's contract is with: the NHL team whose roster he is on (`teams`: the
    slots he is on), else the one holding his rights (proteam `WBbd`, NHL slot + 1), else None."""
    nhl = sorted(t for t in teams if t in L.NHL_PRIMARY)
    if nhl:
        return nhl[0]
    rights = P.get(prow, 'WBbd')
    return rights - 1 if rights else None


def contract_home(P, prow, teams, clubs):
    """Who a contract set by hand is with: (NHL slot, True) in an NHL organisation (`organisation`), else (his club,
    False), the lowest of `teams` (the slots he is on) among `clubs` (contract_clubs); None for a player on no team (a
    free agent) or on no club (a national team only, an NHL copy, a prospect pool) and no NHL team's rights."""
    if not teams:
        return None
    org = organisation(P, prow, teams)
    if org is not None:
        return org, True
    mine = sorted(t for t in teams if t in clubs)
    return (mine[0], False) if mine else None


def misplaced(deals, players):
    """Teams whose deals belong to another team's players: {org: the team most of them play for on NHL.com}.
    `players` is datasource.flatten_nhl's list; a deal matches a player by name and birth year. A team counts when
    five or more of its deals match and most of them play for one other team (a team number mixed up in the source:
    Seattle and Vegas were swapped until 2026-10-20). tools/build_datapack.py refuses such a pack."""
    from collections import Counter
    from .matching import norm
    team_of = {(norm(p['first']), norm(p['last']), p['birth'][0]): p['team'] for p in players}
    seen = {}
    for d in deals:
        team = team_of.get((norm(d['first']), norm(d['last']), d['birth'][0]))
        if team:
            seen.setdefault(d['org'], Counter())[team] += 1
    out = {}
    for org, teams in sorted(seen.items()):
        best, n = teams.most_common(1)[0]
        if best != org and n >= 5 and teams[org] < n:
            out[org] = best
    return out


def problems(R, source, scale, free=lambda pid: False):
    """What is wrong with the deals the update wrote or moved (a player's contract fields differ from the source's):
    on an NHL team a cap hit outside LOWEST..MAXIMUM, on any other club one above MAXIMUM; a deal without seasons on an
    NHL team, or one that lost its seasons (the game's own roster has club players with a cap hit and no seasons; a money
    scale change moves their cap hit); an extension with years but no money or the other way round. Payrolls over the
    cap are allowed (the game asks the GM to fix them). `free(pid)`: the player's own edits, not blamed (rule 3)."""
    def deal(X, prow):
        return tuple(X.P.get(prow, f) for f in FIELDS)
    before = {source.P.get(i, 'zIBw'): deal(source, i) for i in range(source.P.cur_rec)}
    nhl_low, high = units(LOWEST, scale), units(MAXIMUM, scale) + 1
    clubs = contract_clubs(R)
    out, seen = [], set()
    for t in sorted(clubs):
        where = L.SLOT_TO_API.get(t) if t in L.NHL_PRIMARY else R.team_name(t)
        for _, prow, name, *_ in R.team_roster(t):
            was = before.get(R.P.get(prow, 'zIBw')) if prow is not None else None
            if prow is None or prow in seen or deal(R, prow) == was or free(R.P.get(prow, 'zIBw')):
                continue
            seen.add(prow)
            cap, years, ext_years, ext_cap = (R.P.get(prow, f) for f in ('dhKk', 'GDhI', 'IrlK', 'IzRv'))
            if t in L.NHL_PRIMARY and not nhl_low <= cap <= high or cap > high:
                out.append(f"{name} ({where}): a cap hit of ${dollars(cap, scale) / 1e6:.3f}M")
            if not years and (t in L.NHL_PRIMARY or (was and was[1])):
                out.append(f"{name} ({where}): a contract of 0 seasons")
            if bool(ext_years) != bool(ext_cap) or ext_cap > high:
                out.append(f"{name} ({where}): an extension of {ext_years} seasons at "
                           f"${dollars(ext_cap, scale) / 1e6:.3f}M")
    return out[:20]
