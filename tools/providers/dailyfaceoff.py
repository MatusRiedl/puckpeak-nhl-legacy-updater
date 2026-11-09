"""The lines teams announce, for the data pack (part `lines`, 0.50.5; owner, 2026-10-24: "we need the real lines").

NHL.com cannot say who plays centre when two centres share a line (McDavid and Draisaitl are both listed C): shifts and
face-offs do not settle it. Daily Faceoff's team pages (https://www.dailyfaceoff.com/teams/<team>/line-combinations, allowed by
its robots.txt) carry the answer as page data: four lines (LW / C / RW), three pairs, two goalies, power-play units 1 / 2
(five skaters, any mix of forwards and defencemen) and penalty-kill units 1 / 2 (four skaters). Only who plays where is
taken, matched to NHL.com's current roster (the data pack's players are NHL.com ids), one page and one roster request per
team. Output: {team code: {'date', 'source', 'slots'}} with `slots` {slot name (schema.SLOT_TAG): NHL.com player id}; a
group with a player NHL.com's roster lacks is left out (the games' lines fill it, tools/providers/nhl_lines.py).
"""
import json
import re
import time
import unicodedata

from legacy_roster import datasource, matching
from legacy_roster.layout import API_TO_SLOT, NHL_TEAM_NAMES

PAGE = "https://www.dailyfaceoff.com/teams/{slug}/line-combinations"
DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
CODE_NAMES = {code: name for name, code in NHL_TEAM_NAMES.items()}


def slug(team_name):
    """'St. Louis Blues' -> 'st-louis-blues'."""
    plain = unicodedata.normalize('NFKD', team_name).encode('ascii', 'ignore').decode().lower().replace('.', '')
    return re.sub(r'[^a-z0-9]+', '-', plain).strip('-')


def page(code):
    """The page's data for a team code: {'updated', 'players': [dicts with group, position, name, number]}."""
    html = datasource.http_get(PAGE.format(slug=slug(CODE_NAMES[code]))).decode('utf-8', 'replace')
    found = DATA.search(html)
    if not found:
        raise ValueError(f"{code}: the line combinations page has no data")
    combos = json.loads(found.group(1))['props']['pageProps']['combinations']
    players = [{'group': p['groupIdentifier'], 'spot': p['positionIdentifier'], 'name': p['name'],
                'number': p.get('jerseyNumber')} for p in combos['players']]
    return {'updated': combos.get('updatedAt'), 'players': players}


def roster_ids(code, season_year):
    """{(normalised name): [(id, number)]} and {number: (id, normalised last name)} of the team's NHL.com roster."""
    d = datasource.http_json(f"{datasource.NHL_API}/roster/{code}/current")
    by_name, by_number = {}, {}
    for kind in ('forwards', 'defensemen', 'goalies'):
        for p in d.get(kind, []):
            first, last = p['firstName']['default'], p['lastName']['default']
            by_name.setdefault(matching.norm(first + last), []).append((p['id'], p.get('sweaterNumber')))
            if p.get('sweaterNumber') is not None:
                by_number[p['sweaterNumber']] = (p['id'], matching.norm(last))
    return by_name, by_number


def who(p, by_name, by_number):
    """The NHL.com id of a listed player: by full name (two of one name: by number), else by his number when the
    roster's player of that number has his last name (a middle name the roster leaves out). A player the roster lacks
    gets None, never the id of a team-mate who wears his number (2026-11-09: Lettieri #95 read as Ekman-Larsson #95)."""
    same = by_name.get(matching.norm(p['name']), [])
    found = same[0][0] if len(same) == 1 else next((i for i, n in same if n == p['number']), None)
    if found is None and p['number'] in by_number:
        ident, last = by_number[p['number']]
        if last and matching.norm(p['name']).endswith(last):
            found = ident
    return found


def team_slots(players, by_name, by_number):
    """The slots of one team from its page's players; groups with an unknown player are left out."""
    ids = {}
    for p in players:
        ids[(p['group'], p['spot'], p['name'])] = who(p, by_name, by_number)
    slots, role, rank = {}, {}, {}

    def put(names, picks):
        if all(x is not None for x in picks):
            slots.update(dict(zip(names, picks)))
            return True
        return False

    def line(group, spots):
        got = [next((ids[k] for k in ids if k[0] == group and k[1] == s), None) for s in spots]
        return got

    for n in (1, 2, 3, 4):
        names = [f"l{n}lw", f"l{n}c", f"l{n}rw"] + ([f"l{n}ld", f"l{n}rd"] if n < 4 else [])
        picks = line(f"f{n}", ('lw', 'c', 'rw')) + (line(f"d{n}", ('ld', 'rd')) if n < 4 else [])
        if put(names, picks):
            for name, who_ in zip(names, picks):
                role[who_], rank[who_] = name[2:], n        # the even-strength role (lw, c, rw, ld, rd) and line
    put(['g1', 'g2'], line('g', ('g1', 'g2')))
    defence = {i for i, r in role.items() if r in ('ld', 'rd')}
    for k in (1, 2):                                        # power play: 5 skaters in the order listed
        five = [ids[key] for key in ids if key[0] == f"pp{k}"]
        if len(five) != 5 or None in five or len(set(five)) != 5:
            continue
        forwards = sorted((i for i in five if i not in defence), key=lambda i: rank.get(i, 9))    # best line first
        back = [i for i in five if i in defence]
        if len(forwards) < 3:
            continue
        pick = {}
        for spot in ('c', 'lw', 'rw'):                      # each spot: a forward who plays it at even strength
            pick[spot] = next((i for i in forwards if role.get(i) == spot and i not in pick.values()), None)
        for spot in ('c', 'lw', 'rw'):
            if pick[spot] is None:
                pick[spot] = next(i for i in forwards if i not in pick.values())
        spare = [i for i in forwards if i not in pick.values()]
        back.sort(key=lambda i: role.get(i) != 'ld')         # left defence first
        back = back + spare                                 # a fourth forward plays the defence spot left open
        if len(back) < 2:
            continue
        slots.update({f"pp{k}lw": pick['lw'], f"pp{k}c": pick['c'], f"pp{k}rw": pick['rw'],
                      f"pp{k}ld": back[0], f"pp{k}rd": back[1],
                      f"pp4_{k}lw": pick['lw'], f"pp4_{k}c": pick['c'], f"pp4_{k}ld": back[0], f"pp4_{k}rd": back[1]})
    for k in (1, 2):                                        # penalty kill: 2 forwards and 2 defencemen
        four = [ids[key] for key in ids if key[0] == f"pk{k}"]
        if len(four) != 4 or None in four or len(set(four)) != 4:
            continue
        back = [i for i in four if i in defence]
        front = [i for i in four if i not in defence]
        if len(back) != 2 or len(front) != 2:
            continue
        front.sort(key=lambda i: role.get(i) != 'c')        # the centre first
        back.sort(key=lambda i: role.get(i) != 'ld')
        slots.update({f"pk4_{k}lw": front[1], f"pk4_{k}c": front[0], f"pk4_{k}ld": back[0], f"pk4_{k}rd": back[1],
                      f"pk3_{k}c": front[0], f"pk3_{k}ld": back[0], f"pk3_{k}rd": back[1]})
    return slots


CATEGORIES = {'l': 18, 'g': 2, 'pp': 18, 'pk': 14}        # slot-name prefix: how many slots a whole category has


def merge(announced, games):
    """{team code: {'date', 'source', 'games', 'slots', 'letters'}}: a team's announced lines, with every category they
    lack entirely (even strength, goalies, power play, penalty kill) taken from the games' lines
    (tools/providers/nhl_lines); the captains are the games' own."""
    out = {}
    for code in sorted(set(announced) | set(games)):
        a, g = announced.get(code, {}), games.get(code, {})
        slots, source = {}, []
        for prefix, size in CATEGORIES.items():
            mine = {k: v for k, v in a.get('slots', {}).items() if k.startswith(prefix)}
            theirs = {k: v for k, v in g.get('slots', {}).items() if k.startswith(prefix)}
            use, label = (mine, 'announced') if len(mine) == size else (theirs, 'games')
            slots.update(use)
            if use:
                source.append(f"{prefix}:{label}")
        out[code] = {'date': a.get('date') or g.get('date'), 'source': ' '.join(source),
                     'games': g.get('games', []), 'slots': slots, 'letters': g.get('letters', {})}
    return out


def lines(season_year, teams=None, log=print):
    """{team code: {'date', 'source', 'slots'}} for the NHL teams (all, or the codes in `teams`)."""
    out = {}
    for code in sorted(teams or API_TO_SLOT):
        try:
            data = page(code)
            by_name, by_number = roster_ids(code, season_year)
        except Exception as err:          # one team's page failing leaves that team to the games' lines
            log(f"lines (announced): {code}: {err}")
            continue
        slots = team_slots(data['players'], by_name, by_number)
        out[code] = {'date': (data['updated'] or '')[:10], 'source': 'announced', 'slots': slots}
        log(f"lines (announced): {code}: {len(slots)} of 71 slots")
        time.sleep(0.5)
    return out
