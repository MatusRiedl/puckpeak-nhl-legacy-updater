"""Real lines from real games, for the data pack (part `lines`, 0.50.4; owner, 2026-10-24: "lines real from real games").

For each NHL team, its last GAMES finished regular-season games (NHL.com schedule), and per game the box score (who
dressed, positions, goalies' time) and the shift chart (who was on the ice second by second). From that, only for the
team's players of its latest game:
  * even strength (5 v 5): the forward trios and defence pairs that skated together most, best line = most ice time;
  * power play / penalty kill: the forwards and defencemen ranked by their time in that state (then by even-strength
    time), split into units 1 / 2;
  * goalies: the one with most ice time over the games is the starter.
Overtime, the shootout and the extra attackers are left out (the builder deals them by rating). No scraping and no
guessing: NHL.com's own numbers, one request per game for each. Output: {team code: {'date', 'games', 'slots',
'letters'}} with `slots` {slot name (schema.SLOT_TAG): NHL.com player id}; a slot the games cannot name is missing.
`letters` {NHL.com player id (str): 'C' | 'A'}: the captain and alternates as NHL.com's official game roster report of
each game marks them ("ADAM LOWRY  (C)"), counted over the games (providers/letters.py).
"""
import re
import time
from collections import Counter

from legacy_roster import datasource
from legacy_roster.layout import API_TO_SLOT

from .letters import count_letters

GAMES = 5                           # games per team
SCHEDULE = datasource.NHL_API + "/club-schedule-season/{abbr}/{season}"
BOXSCORE = datasource.NHL_API + "/gamecenter/{id}/boxscore"
SHIFTS = "https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={id}"
ROSTER_REPORT = "https://www.nhl.com/scores/htmlreports/{season}/RO{number}.HTM"
ROW = re.compile(r'<tr>\s*<td[^>]*>\s*(\d+)\s*</td>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>([^<]*)</td>', re.I)
PERIOD = 1200                       # seconds in a period
END = 3 * PERIOD + 300              # three periods and the overtime (regular season: 5 minutes, 3 v 3)
FINAL = ('OFF', 'FINAL')


def clock(text):
    minutes, seconds = text.split(':')
    return int(minutes) * 60 + int(seconds)


def seconds_of(shift):
    """(first second, end second) of a shift in the game's own clock, or None for the shootout / playoff periods."""
    if not 1 <= shift['period'] <= 4 or not shift.get('startTime') or not shift.get('endTime'):
        return None
    base = (shift['period'] - 1) * PERIOD
    a, b = base + clock(shift['startTime']), base + clock(shift['endTime'])
    return (a, min(b, END)) if b > a else None


def read_letters(html):
    """(visitor, home): {sweater number: 'C' | 'A'} of an NHL.com game roster report: its dressed players stand in two
    columns, the visitors' first (`<td valign="top" width="50%" class="border">`), the scratches follow in a section of
    their own (left out); a captain's row reads "ADAM LOWRY  (C)". Empty dicts for a page without them."""
    dressed = re.split(r'id="Scratches"', html, maxsplit=1, flags=re.I)[0]
    columns = re.split(r'<td[^>]*width="50%"[^>]*class="border"[^>]*>', dressed, flags=re.I)[1:3]
    out = []
    for part in columns:
        marks = {}
        for number, name in ROW.findall(part):
            m = re.search(r'\(([CA])\)\s*$', name.strip())
            if m:
                marks.setdefault(int(number), m.group(1))
        out.append(marks)
    return tuple((out + [{}, {}])[:2])


def game_letters(game_id):
    """(visitor, home) {sweater number: letter} of one game; ({}, {}) when the report cannot be read (the lines are
    made without it)."""
    url = ROSTER_REPORT.format(season=f"{str(game_id)[:4]}{int(str(game_id)[:4]) + 1}", number=str(game_id)[4:])
    try:
        return read_letters(datasource.http_get(url, retries=1).decode('latin-1'))
    except (OSError, ValueError):
        return {}, {}


def read_game(game_id):
    """{team code: {'players': {id: position C/L/R/D/G}, 'toi': {id: seconds}, 'ev': Counter, 'pp': ..., 'pk': ...,
    'trios': Counter, 'pairs': Counter, 'letters': {id: 'C' | 'A'}}} of one finished game."""
    box = datasource.http_json(BOXSCORE.format(id=game_id))
    teams, positions, toi, goalies, numbers = {}, {}, {}, {}, {}
    visitor, home = game_letters(game_id)
    marks = {'homeTeam': home, 'awayTeam': visitor}
    for side in ('homeTeam', 'awayTeam'):
        code, team_id = box[side]['abbrev'], box[side]['id']
        teams[team_id] = code
        stats = box['playerByGameStats'][side]
        goalies[code] = set()
        positions[code], toi[code], numbers[code] = {}, {}, {}
        for kind in ('forwards', 'defense', 'goalies'):
            for p in stats.get(kind, []):
                pos = p['position'] if p['position'] in ('C', 'L', 'R', 'D', 'G') else ('G' if kind == 'goalies' else 'C')
                positions[code][p['playerId']] = pos
                toi[code][p['playerId']] = clock(p['toi']) if p.get('toi') else 0
                if pos == 'G':
                    goalies[code].add(p['playerId'])
                elif p.get('sweaterNumber') in marks[side]:
                    numbers[code][p['playerId']] = marks[side][p['sweaterNumber']]
    ice = {code: [set() for _ in range(END)] for code in teams.values()}
    shifts = datasource.http_json(SHIFTS.format(id=game_id)).get('data', [])
    for s in shifts:
        if s.get('typeCode') != 517 or s.get('teamId') not in teams:
            continue
        span = seconds_of(s)
        if span:
            code = teams[s['teamId']]
            for t in range(*span):
                ice[code][t].add(s['playerId'])
    out = {}
    for code, other in zip(ice, reversed(list(ice))):
        pos = positions[code]
        mine = {'players': pos, 'toi': toi[code], 'ev': Counter(), 'pp': Counter(), 'pk': Counter(),
                'trios': Counter(), 'pairs': Counter(), 'letters': numbers[code]}
        for t in range(END):
            skaters = ice[code][t] - goalies[code]
            theirs = ice[other][t] - goalies[other]
            # a pulled goalie (either side) is no manpower state
            if not (ice[code][t] & goalies[code]) or not (ice[other][t] & goalies[other]):
                continue
            n, m = len(skaters), len(theirs)
            if n == 5 and m == 5:
                state = 'ev'
            elif n > m and n in (4, 5) and m in (3, 4):
                state = 'pp'
            elif n < m and m in (4, 5) and n in (3, 4):
                state = 'pk'
            else:
                continue
            for pid in skaters:
                mine[state][pid] += 1
            if state == 'ev':
                fwd = frozenset(p for p in skaters if pos.get(p) in ('C', 'L', 'R'))
                dfn = frozenset(p for p in skaters if pos.get(p) == 'D')
                if len(fwd) == 3 and len(dfn) == 2:
                    mine['trios'][fwd] += 1
                    mine['pairs'][dfn] += 1
        out[code] = mine
    return out


def last_games(abbr, season_year):
    """[(game id, date)] of the team's last GAMES finished regular-season games, oldest first."""
    season = f"{season_year}{season_year + 1}"
    games = [g for g in datasource.http_json(SCHEDULE.format(abbr=abbr, season=season)).get('games', [])
             if g.get('gameType') == 2 and g.get('gameState') in FINAL]
    games.sort(key=lambda g: (g['gameDate'], g['id']))
    return [(g['id'], g['gameDate']) for g in games[-GAMES:]]


def pick_groups(counts, universe, size, n, seconds):
    """`n` disjoint groups of `size` from `universe`: the group seen together longest first; when no seen group is left,
    the most-used players still free."""
    left, out = set(universe), []
    seen = sorted(counts.items(), key=lambda kv: (-kv[1], sorted(kv[0])))
    for _ in range(n):
        group = next((set(g) for g, _c in seen if set(g) <= left), None)
        if group is None:
            group = set(sorted(left, key=lambda p: (-seconds[p], p))[:size])
        if len(group) < size:
            break
        out.append(sorted(group))
        left -= group
    out.sort(key=lambda g: (-sum(seconds[p] for p in g), g))
    return out


def trio_slots(trio, pos, seconds):
    """(left wing, centre, right wing) of three forwards: the centre is the centre with most time (else the forward with
    most time), wings on their own side where possible."""
    centres = sorted((p for p in trio if pos[p] == 'C'), key=lambda p: (-seconds[p], p))
    centre = centres[0] if centres else sorted(trio, key=lambda p: (-seconds[p], p))[0]
    rest = [p for p in trio if p != centre]
    left = next((p for p in rest if pos[p] == 'L'), None)
    rest = [p for p in rest if p != left]
    right = next((p for p in rest if pos[p] == 'R'), None)
    rest = [p for p in rest if p != right]
    if left is None:
        left = rest.pop(0)
    if right is None:
        right = rest.pop(0)
    return left, centre, right


def ranked(players, counter, then=None):
    """The players who spent time in the state, most time first (ties by id). With `then` (a second count), every
    player is listed: those with no time in the state follow, most `then` time first."""
    if then is not None:
        return sorted(players, key=lambda p: (-counter[p], -then[p], p))
    return [p for p in sorted(players, key=lambda p: (-counter[p], p)) if counter[p] > 0]


def team_lines(games):
    """The `slots` of one team from its games' read_game results (oldest first)."""
    latest = games[-1]
    pos = latest['players']
    total = {key: Counter() for key in ('ev', 'pp', 'pk', 'trios', 'pairs', 'toi')}
    for g in games:
        for key in total:
            total[key].update(g[key] if key != 'toi' else g['toi'])
    forwards = [p for p, k in pos.items() if k in ('C', 'L', 'R')]
    defence = [p for p, k in pos.items() if k == 'D']
    goalies = sorted((p for p, k in pos.items() if k == 'G'), key=lambda p: (-total['toi'][p], p))
    slots = {}
    if len(goalies) >= 2:
        slots['g1'], slots['g2'] = goalies[0], goalies[1]
    ev = total['ev']
    f12 = ranked(forwards, ev) + sorted(p for p in forwards if ev[p] == 0)
    d6 = ranked(defence, ev) + sorted(p for p in defence if ev[p] == 0)
    if len(forwards) >= 12 and len(defence) >= 6:
        f12, d6 = f12[:12], d6[:6]
        for k, trio in enumerate(pick_groups(total['trios'], f12, 3, 4, ev), 1):
            slots[f"l{k}lw"], slots[f"l{k}c"], slots[f"l{k}rw"] = trio_slots(trio, pos, ev)
        for k, pair in enumerate(pick_groups(total['pairs'], d6, 2, 3, ev), 1):
            slots[f"l{k}ld"], slots[f"l{k}rd"] = pair
    # power play: units of 3 forwards and 2 defencemen by their time on the power play
    pp_f, pp_d = ranked(forwards, total['pp'], ev), ranked(defence, total['pp'], ev)
    for k in (1, 2):
        f, d = pp_f[3 * (k - 1):3 * k], pp_d[2 * (k - 1):2 * k]
        if len(f) == 3 and len(d) == 2:
            lw, c, rw = trio_slots(f, pos, total['pp'])
            slots.update({f"pp{k}lw": lw, f"pp{k}c": c, f"pp{k}rw": rw, f"pp{k}ld": d[0], f"pp{k}rd": d[1],
                          f"pp4_{k}lw": lw, f"pp4_{k}c": c, f"pp4_{k}ld": d[0], f"pp4_{k}rd": d[1]})
    # penalty kill: units of 2 forwards and 2 defencemen by their time shorthanded; 3 skaters = the centre and the pair
    pk_f, pk_d = ranked(forwards, total['pk'], ev), ranked(defence, total['pk'], ev)
    for k in (1, 2):
        f, d = pk_f[2 * (k - 1):2 * k], pk_d[2 * (k - 1):2 * k]
        if len(f) == 2 and len(d) == 2:
            centre = sorted(f, key=lambda p: (pos[p] != 'C', -total['pk'][p], p))[0]
            wing = next(p for p in f if p != centre)
            slots.update({f"pk4_{k}lw": wing, f"pk4_{k}c": centre, f"pk4_{k}ld": d[0], f"pk4_{k}rd": d[1],
                          f"pk3_{k}c": centre, f"pk3_{k}ld": d[0], f"pk3_{k}rd": d[1]})
    return slots


def lines(season_year, teams=None, log=print):
    """{team code: {'date', 'games': [ids], 'slots'}} for the NHL teams (all, or the codes in `teams`)."""
    cache, out = {}, {}
    for abbr in sorted(teams or API_TO_SLOT):
        try:
            picked = last_games(abbr, season_year)
            reads = []
            for game_id, _date in picked:
                if game_id not in cache:
                    cache[game_id] = read_game(game_id)
                    time.sleep(0.1)
                if abbr in cache[game_id]:
                    reads.append(cache[game_id][abbr])
        except (OSError, ValueError, KeyError) as err:     # one team failing leaves it out (the pack keeps its old lines)
            log(f"lines: {abbr}: {err}")
            continue
        if not reads:
            log(f"lines: {abbr} has no finished game yet")
            continue
        letters = count_letters([g.get('letters', {}) for g in reads])
        out[abbr] = {'date': picked[-1][1], 'games': [g for g, _d in picked], 'slots': team_lines(reads),
                     'letters': {str(k): v for k, v in sorted(letters.items())}}
        log(f"lines: {abbr}: {len(picked)} games, {len(out[abbr]['slots'])} of 71 slots, "
            f"{len(letters)} letters")
        time.sleep(0.1)
    return out
