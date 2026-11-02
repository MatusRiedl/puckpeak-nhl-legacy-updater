"""Give a club league its real clubs: every player of the league's rosters on his club.

The league data (from the data pack) already says which club goes into which team slot. For
each club the players are matched to records in the save; the ones that are not there get a
record of their own with estimated ratings. Whoever was on those slots before and is not on
the new roster leaves: prospect-pool players move to spare custom slots (pools.py), former club
players become free agents.

New players need spare records (donors.py). If those run out, every club first gets the players
it needs to dress a full line-up; the rest of the depth is skipped and listed in the report.
"""
import re
import unicodedata
from collections import Counter

from .. import contracts as pay
from .. import layout as L
from .. import lines, ratings
from ..donors import UNDRAFTED
from ..estimate import Estimator
from ..matching import match_club, norm
from . import pools

CORE = {'G': 2, 'D': 6, 'F': 12}    # a dressed line-up: created before any club's depth players
STAY_AGE = 20                       # a player this young whom his league's list leaves out stays with his club
PROSPECT_ROOM = 36                  # an undrafted prospect joins a club only while it keeps fewer players than this
# where an undrafted prospect of the next drafts plays, by nationality (the game's own roster keeps its draft
# classes on junior and European clubs); everyone else goes to the CHL
HOME_LEAGUE = {'SWE': 'shl', 'FIN': 'liiga', 'CZE': 'extraliga', 'SVK': 'extraliga', 'DEU': 'del', 'AUT': 'del',
               'CHE': 'nl', 'NOR': 'norway'}
NATION_OF = {code: iso for iso, code in L.NAT_CODE.items()}
JUNIOR_AGE = {'chl': 20}            # free agents a junior club may sign to fill its line-up are this young


def group(pos):
    return pos if pos in ('G', 'D') else 'F'


def kind(g):
    """Record pools: goalies have their own attribute table, skaters share one."""
    return 'G' if g == 'G' else 'S'


def listed(teams):
    """The league's players, each once (a feed may list a player twice), with slot and club."""
    people, seen = [], set()
    for t in teams:
        for p in sorted(t['players'], key=lambda p: not p.get('num')):     # a listing with a number first
            key_ = (norm(p['first']), norm(p['last']), tuple(p['birth']))
            if key_ in seen:
                continue
            seen.add(key_)
            q = dict(p)
            q.update(birth=tuple(q['birth']), slot=t['slot'], team=t['abbr'])
            people.append(q)
    return people


# words that do not tell clubs apart ("Silver Knights", "Lakers"), and feed names that are not what
# a player would call the club
COMMON_WORDS = {'hockey', 'ishockey', 'club', 'team', 'lakers', 'silver', 'knights', 'valley', 'panthers', 'the'}
CLUB_ALIASES = {'SCRJ Lakers': 'Rapperswil-Jona Lakers'}


def _words(text):
    plain = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode().lower()
    return set(re.findall(r'[a-z0-9]+', plain))


def own_teams(R, league, taken, mirrors=()):
    """A player's own custom teams named after a club the game has no slot for (Jokerit, Ajoie,
    Penticton, Coachella Valley in the game's own roster ...): [club with 'slot' = his team's slot
    and 'own' True], so the league step gives them that club's players. A custom slot counts when it
    is switched on and is no NHL copy (`mirrors`), prospect pool or slot already used (`taken`);
    its name, city or abbreviation must contain a word of the club's name that tells it apart. The
    team keeps its league (Custom) and the name, city and logo the player gave it."""
    clubs_ = [c for c in league.get('extra') or [] if c.get('players')]
    if not clubs_:
        return []
    T = R.T
    words = {}
    for slot in range(min(L.MIRROR_OF), L.TEAM_COUNT):
        if (slot in taken or slot in mirrors or not T.get(slot, 'NYKk') or pools.is_pool(R, slot)
                or T.get(slot, 'league') != L.CUSTOM_LEAGUE):
            continue
        words[slot] = (_words(R.team_name(slot)) | _words(T.get(slot, 'JkmY'))
                       | _words(T.get(slot, 'shortname').replace('_', ' ')) | _words(T.get(slot, 'nnsx')))
    out = []
    for club in clubs_:
        name = CLUB_ALIASES.get(club['full'], club['full'])
        mark = {w for w in _words(name) | _words(club['short']) if len(w) >= 4 and w not in COMMON_WORDS}
        slot = next((s for s in sorted(words) if mark & words[s]), None)
        if slot is not None:
            out.append(dict(club, slot=slot, own=True))
            del words[slot]
    return out


def core_needs(b, league):
    """How many new records this league needs to give every club a dressable 20 (by record kind,
    as the save stands now): the pipeline keeps that many back from the depth of earlier leagues."""
    people = match_club(b.R, listed(league['teams']))
    have = Counter((p['slot'], group(p['pos'])) for p in people if p['row'] is not None)
    new = Counter((p['slot'], group(p['pos'])) for p in people if p['row'] is None)
    need = Counter()
    for (slot, g), n in new.items():
        need[kind(g)] += min(n, max(0, CORE[g] - have[(slot, g)]))
    return need


def creation_order(b, key, league, people, live, est):
    """Matched players first, then each club's core line-up, then depth -- so that when player
    records run out, the clubs still dress 20. Depth players are marked p['depth']."""
    on_nhl = lambda p: any(b.U.get(e, 'BSXd') in L.NHL_PRIMARY for e in live.get(b.P.get(p['row'], 'zIBw'), []))
    have = Counter((p['slot'], group(p['pos'])) for p in people if p['row'] is not None and not on_nhl(p))
    fresh = [(k, p) for k, p in enumerate(people) if p['row'] is None]
    level = lambda p: est.target(key, L.POS_CODE.get(p['pos'], 0), b.data.season_year - p['birth'][0],
                                 f"{p['first']} {p['last']}", p.get('letter'), p.get('rookie'), _is_import(p, league))
    core = set()
    for k, p in sorted(fresh, key=lambda kp: (-level(kp[1]), kp[0])):
        g = (p['slot'], group(p['pos']))
        if have[g] < CORE[g[1]]:
            have[g] += 1
            core.add(k)
    for k, p in fresh:
        p['depth'] = k not in core
    return ([p for p in people if p['row'] is not None] + [p for k, p in fresh if k in core]
            + [p for k, p in fresh if k not in core])


def own_kit(R, slot):
    """Coachella Valley's / Henderson's designs (layout.OWN_DESIGN), team colours (layout.OWN_COLOURS) and jersey colours
    (layout.OWN_KIT, table NDEo: its rows for slot + 1)."""
    E, kit = R.f['NDEo'], L.OWN_KIT.get(slot)
    if not kit:
        return
    for field, v in L.OWN_DESIGN[slot].items():
        R.T.set(slot, field, v)
    for kind, rgb in zip(('primary', 'secondary'), L.OWN_COLOURS[slot]):
        for c, v in zip('rgb', rgb):
            R.T.set(slot, f'{kind}color_{c}', v)
    for i in range(E.cur_rec):
        if E.get(i, 'team') != slot + 1:
            continue
        zones = kit.get((E.get(i, 'equipment'), E.get(i, 'variant')))
        for z, rgb in enumerate(zones or (), start=1):
            for c, v in zip('rgb', rgb):
                E.set(i, f'zone{z}_{c}', v)


def update_league(b, key, league, say):
    """Rebuild the slots of one league. Returns the set of team ids that were rebuilt."""
    R, U, P, T = b.R, b.U, b.P, b.R.T
    teams = league['teams']
    home = L.country_code(league.get('country'))
    people = listed(teams)
    b.donors.reserve(people)
    match_club(R, people)
    est = Estimator(b)
    slots = [t['slot'] for t in teams]
    departures_before = {t: len(v) for t, v in b.departures.items()}

    # who is on these slots now, and what the slots were called before they get their club names
    leftovers = {e: slot for slot in slots for e in b.entries_on(slot)}
    was_pool = {slot: ((T.get(slot, 'JkmY'), T.get(slot, 'RPbr')) if pools.is_pool(R, slot) else None) for slot in slots}
    for t in teams:
        if t.get('own'):                            # a player's own team: his name, city and logo stay
            continue
        T.set(t['slot'], 'JkmY', t['full'])
        L.set_city(T, t['slot'], t['short'])        # custom slots (Coachella, Henderson): a key, see layout
        T.set(t['slot'], 'nnsx', t['abbr'])
        T.set(t['slot'], 'RPbr', t['art'])
        if t['slot'] in L.OWN_ART:                  # Coachella Valley, Henderson: art ids and jersey colours of their own
            T.set(t['slot'], 'artid', L.OWN_ART[t['slot']])
            own_kit(R, t['slot'])
        if t.get('logo'):
            b.logos[t['slot']] = t['logo']

    live = b.live_entries()     # pid -> entries that exist right now
    people = creation_order(b, key, league, people, live, est)
    parents = affiliates(R) if key == 'ahl' else {}
    claimed, changed, numbers = set(), set(), {}
    letters = {}
    stats = Counter()
    forward_cycle = 0
    for p in people:
        target = p['slot']
        name = f"{p['first']} {p['last']}"
        age = b.data.season_year - p['birth'][0]
        row = p['row']
        if row is not None and row in claimed:       # listed twice in the feed
            continue
        if row is not None:
            pid = P.get(row, 'zIBw')
            ents = live.get(pid, [])
            if any(U.get(e, 'BSXd') in L.NHL_PRIMARY for e in ents):
                stats['on an NHL roster'] += 1       # NHL.com is the authority for NHL players
                continue
            if pid in b.placed:                      # another league listed him too: the first one keeps him
                stats['listed by another league too'] += 1
                continue
            claimed.add(row)
            b.placed.add(pid)
            here = [e for e in ents if U.get(e, 'BSXd') == target]
            # one club at a time: his entries on other clubs, pools and junior teams go
            others = [e for e in ents if U.get(e, 'BSXd') != target
                      and U.get(e, 'BSXd') not in L.NATIONAL and U.get(e, 'BSXd') not in L.NHL_ALL]
            if here:
                e = here[0]
            elif others:
                e = others.pop(0)
                frm = R.team_name(leftovers[e]) if e in leftovers and was_pool[leftovers[e]] is None else None
                frm = frm or (was_pool[leftovers[e]][0] if e in leftovers else R.team_name(U.get(e, 'BSXd')))
                b.move_entry(e, target)
                changed.add(target)
                b.log.append([p['team'], 'joined', name, f"from {frm}", p.get('num') or ''])
                stats['moved'] += 1
            else:
                fa = [l for l in b.fa_links if R.link_to_pid.get(l) == pid]
                e = b.new_entry(target, fa[0] if fa else b.new_link(pid), row)
                b.arrivals.setdefault(target, []).append(e)
                live.setdefault(pid, []).append(e)
                changed.add(target)
                b.log.append([p['team'], 'joined', name, 'was a free agent' if fa else 'was without a team',
                              p.get('num') or ''])
                stats['added'] += 1
            for x in others:
                b.depart(x)
                b.deleted.add(x)
                leftovers.pop(x, None)
            live[pid] = [x for x in live.get(pid, []) if x not in b.deleted]
            leftovers.pop(e, None)
            b.drop_fa(pid)
            if _feed_position(b, row, p, live, name):
                changed.add(target)                  # kept lines would count him at his old position
            if key != 'ahl':
                b.unrate_name_only(pid)     # the list's rating will not reach him here next time
            if key == 'ahl' and pid not in b.list_rated and pid not in b.full_rated and b.data.ratings_list:
                # The ratings list rates NHL and AHL players; one who just came down from the NHL was on neither
                # when the ratings were written
                on_list = b.list_rating_for(P.get(row, 'PedH'), P.get(row, 'RMbQ'), p['birth'], by_name=True)
                if on_list and ratings.is_goalie(on_list) == (P.get(row, 'aljv') == 4):
                    b.write_list_rating(row, on_list)
            if p.get('stale'):                       # a record from the game's own database: fix the birth year, re-rate
                P.set(row, 'dnFq', p['birth'][0] - 1910)
                if not b.rate_full(row, live):      # the full ratings first, as the next run finds him by the year put right
                    b.unrate_full(pid)
                    if pid not in b.list_rated:        # The list's ratings always win over an estimate
                        est.shift(row, est.target(key, P.get(row, 'aljv'), age, name, p.get('letter'),
                                                  p.get('rookie'), _is_import(p, league)))
                        stats['re-rated'] += 1
        else:
            if p['pos'] == 'F':                      # feeds that do not split forwards: C, LW, RW in turn
                pos = forward_cycle % 3
                forward_cycle += 1
            else:
                pos = L.POS_CODE[p['pos']]
            g = kind(group(p['pos']))
            spare = b.donors.left(g) - b.core_reserve[g]
            # depth players only while records remain beyond what later leagues need for their line-ups
            row = b.take_record(pos, name, required=False) if not p['depth'] or spare > 0 else None
            if row is None:                          # no spare record left for this position
                b.log.append([p['team'], 'skipped', name, 'no free player record left', p.get('num') or ''])
                stats['skipped: no free record'] += 1
                continue
            claimed.add(row)
            old = R.name(row)
            pid = P.get(row, 'zIBw')
            b.placed.add(pid)
            b.donors.reset_identity(row, name, L.country_code(p.get('country')) or home, p['birth'][0])
            b.set_text(row, 'PedH', p['first'])
            b.set_text(row, 'RMbQ', p['last'])
            P.set(row, 'JzFM', '')
            y, m, d = p['birth']
            P.set(row, 'iwsK', d - 1)
            P.set(row, 'pLKJ', m - 1)
            P.set(row, 'dnFq', y - 1910)
            # the full ratings first, then the ratings list, then the estimate (as the next run's ratings step finds him)
            dates = b.full_dates
            rated = b.rate_full(row, live)
            on_list = (b.list_rating_for(p['first'], p['last'], p['birth'], by_name=key == 'ahl')
                   if b.data.ratings_list and not rated else None)
            if not (rated or on_list and ratings.is_goalie(on_list) == (pos == 4) and b.write_list_rating(row, on_list)):
                est.write(row, est.target(key, pos, age, name, p.get('letter'), p.get('rookie'),
                                          _is_import(p, league)), name, age)
            e = b.new_entry(target, b.new_link(pid), row)
            b.arrivals.setdefault(target, []).append(e)
            live.setdefault(pid, []).append(e)
            note = "; birthdate approximate (the league gives the age only)" if p.get('birth_approx') else ''
            if b.full_dates > dates:
                note = "; real birthdate (the league gives the age only)"
            b.log.append([p['team'], 'created', name, f"reused record of {old}{note}", p.get('num') or ''])
            stats['created'] += 1
            changed.add(target)
        _bio(b, row, p)
        if p.get('photo'):
            b.photos[row] = p['photo']
        # a club player's contract team is his club. Without NHL rights his deal is the club's own (a starter deal,
        # Builder.starter_contracts, or the player's edit): it stays while he stays; one from another team, or an NHL
        # deal whose rights the list no longer names, goes (the starter deals give him one with this club)
        stays = P.get(row, 'BSXd') == target + 1
        had_rights = P.get(row, 'WBbd')
        P.set(row, 'BSXd', target + 1)
        if league.get('orgs'):                       # the list names his organisation (AHL, owner 2026-10-22)
            _rights(b, row, p.get('org'))
        elif p.get('nhl_contract') and parents.get(target) is not None:
            _nhl_contract(b, row, parents[target])
        if not P.get(row, 'WBbd') and (had_rights or not stays):
            for f in ('GDhI', 'dhKk', 'IrlK', 'IzRv'):
                P.set(row, f, 0)
        numbers[e] = p.get('num')
        letters[e] = p.get('letter')
    for slot in slots:              # the league's own captains: Builder.contract_strays deals the other letters again
        b.feed_letters[slot] = {e: v for e, v in letters.items() if v and U.get(e, 'BSXd') == slot}

    # undrafted prospects of this league's country who are in prospect pools, on the free-agent list or on
    # no team join its clubs, as if they had been there: a second run finds them as former players who stay
    joined = _place_prospects(b, key, slots, leftovers, was_pool, live, stats)

    # players under contract with the parent club (2026-27) whom no list names stay (below); they neither count for
    # the line-up nor fill it, as on a first run, where Builder.contract_strays only puts them here at the end
    under_contract = {e for e, slot in leftovers.items() if was_pool[slot] is None and b.farm_contract(e, slot, parents)}

    # a club the feed leaves short at a position (its listed defencemen are with the NHL club, its
    # goalies could not get a record): a former player of that position stays, else a free agent signs
    for slot in slots:
        _fill_lineup(b, slot, leftovers, live, T.get(slot, 'nnsx'), stats, JUNIOR_AGE.get(key), under_contract)

    # whoever is still on these slots is not on the new rosters
    displaced = {}
    for e, slot in sorted(leftovers.items()):
        if e in under_contract:
            # under contract with the parent club (2026-27) and on no list: he stays, as Builder.contract_strays would
            # put him here at the end; the club is not dealt again for him (a second run must find nothing to do)
            P.set(b.prow_of_entry(e), 'BSXd', slot + 1)
            b.log.append([T.get(slot, 'nnsx'), 'stays under contract', R.name(b.prow_of_entry(e)),
                          f"under contract with {L.SLOT_TO_API[parents[slot]]} (2026-27), not on the league's list",
                          U.get(e, 'tRVs')])
            stats['kept under contract'] += 1
            continue
        changed.add(slot)
        if e in joined:                 # a prospect who just joined (on a slot that may have been a pool): he stays
            continue
        if was_pool[slot] is not None:
            displaced.setdefault(was_pool[slot], []).append(e)
        elif _young(b, b.prow_of_entry(e)):
            # a young player the league's list leaves out stays with his club (testers, 0.8.0: the WHL's 2026-27
            # list has no Landon DuPont, a 2027 first-round prospect; as a free agent the draft would not see him)
            if e not in joined:
                b.log.append([T.get(slot, 'nnsx'), 'stays', R.name(b.prow_of_entry(e)),
                              "a young player the league's list leaves out", U.get(e, 'tRVs')])
                stats['juniors kept'] += 1
            P.set(b.prow_of_entry(e), 'BSXd', slot + 1)      # his contract team is the club he stays with
        else:
            name = R.name(b.prow_of_entry(e))
            became_fa = b.release(e, live)
            b.log.append([T.get(slot, 'nnsx'), 'left the club', name, 'now a free agent' if became_fa else '',
                          U.get(e, 'tRVs')])
            stats['left'] += 1
    if displaced:
        pools.relocate(b, displaced)
        stats['pool players moved'] = sum(len(v) for v in displaced.values())

    rebuilt = set(slots)
    for slot in slots:
        ents = b.entries_on(slot)
        for e in sorted(ents, key=lambda e: (b.q(e), e))[:max(0, len(ents) - L.MAX_PER_TEAM)]:   # 40 a team
            name = R.name(b.prow_of_entry(e))
            b.release(e, live)
            b.log.append([T.get(slot, 'nnsx'), 'left the club', name, 'no room (40 players at most)', U.get(e, 'tRVs')])
            changed.add(slot)
        ents = b.entries_on(slot)
        taken = Counter()
        for e in ents:
            if numbers.get(e):
                U.set(e, 'tRVs', min(numbers[e], 99))
        for e in sorted(ents, key=lambda e: (not numbers.get(e), -b.q(e))):      # listed numbers win a clash
            n = U.get(e, 'tRVs')
            if not n or taken[n]:
                n = next(x for x in range(2, 99) if not taken[x])
                U.set(e, 'tRVs', n)
            taken[n] += 1
        complete = len({f for e in ents for f in b.held(e)}) == len(b.flags)
        short = Counter(group('CLRDG'[P.get(b.prow_of_entry(e), 'aljv')]) for e in ents)
        enough = all(short[g] >= n for g, n in CORE.items())
        # kept lines that break the line-up rule by real positions (lines.lineup_flaws) are dealt again when they can be
        if slot in changed or not complete or (enough and lines.lineup_flaws(b, slot, ents)):
            try:
                if not enough:
                    raise lines.NotEnoughPlayers(f"{R.team_name(slot)}: {short['G']} goalies, {short['D']} "
                                                 f"defencemen, {short['F']} forwards -- cannot dress 20")
                lines.build_lines(b, slot)
            except lines.NotEnoughPlayers as err:
                # nobody left to fill in: the club keeps its players but no lines, as AHL and junior
                # teams had them in the base roster
                say(str(err))
                for e in ents:
                    b.clear_lines(e)
                rebuilt.discard(slot)
                stats['clubs without a full line-up'] += 1
                continue
            _letters(b, slot, letters)

    # teams elsewhere that lost a player to this league: hand his line slots to a team-mate
    for team, deps in list(b.departures.items()):
        fresh = deps[departures_before.get(team, 0):]
        if fresh and team not in slots and team not in L.NHL_PRIMARY and team not in pools.SPARE_SLOTS:
            b.departures[team] = fresh
            b.fill_lines(team)
            b.departures[team] = deps
    if stats['skipped: no free record']:
        say(f"{league['label']}: {stats['skipped: no free record']} players skipped, "
            "no free player record left (they are listed in the report)")
    for k, v in sorted(stats.items()):
        b.log.append([league['label'], 'summary', k, v, ''])
    b.league_stats[key] = dict(stats)
    b.rebuilt_clubs.update({slot: key for slot in rebuilt})     # Builder.repair_lineups looks at them again at the end
    return rebuilt


def _young(b, prow):
    return b.data.season_year - (b.P.get(prow, 'dnFq') + 1910) < STAY_AGE


def _prospect(b, prow):
    """An undrafted player of a draft still to come (draft.py gives him its year and round 0), young,
    whom no club league lists (that league places him), not even under his name with another
    birthdate (it then makes him anew: the CHL's Arjun Nanubhai)."""
    P = b.P
    year = P.get(prow, 'WzKY')
    return (not P.get(prow, 'Ujcc') and year != UNDRAFTED and year + 1900 > b.data.season_year and _young(b, prow)
            and 'ZZ' not in P.get(prow, 'RMbQ') and prow not in b.league_rows
            and b.person(prow) not in b.donors.reserved)


def _place_prospects(b, key, slots, leftovers, was_pool, live, stats):
    """Undrafted prospects whose home league (HOME_LEAGUE; the CHL for the rest, and when their own
    league is not updated) is this one, and who are in a prospect pool, on the free-agent list or on
    no team, join the club of this league with the most room, best of the earliest draft first. They
    go into `leftovers` like former players, so this run treats them exactly as the next run will
    (they stay: _young). Testers, 0.8.0: the pools sit on custom teams, where the draft does not
    look. Returns their entries."""
    R, U, P, T = b.R, b.U, b.P, b.R.T
    keys = getattr(b, 'league_keys', None) or {key}

    def home(prow):
        k = HOME_LEAGUE.get(NATION_OF.get(P.get(prow, 'hleL')), 'chl')
        return k if k in keys else 'chl'

    def elsewhere(pid, e=None):          # on a club that is no prospect pool (a national team does not count)
        return any(U.get(x, 'BSXd') not in L.NATIONAL and x != e for x in live.get(pid, []))

    stays = lambda e: was_pool[leftovers[e]] is None and _young(b, b.prow_of_entry(e))
    size = {s: sum(1 for e in b.entries_on(s) if e not in leftovers or stays(e)) for s in slots}
    found = []                  # (order, pid, how, entry or link)
    for e in range(U.cur_rec):
        if e in b.deleted:
            continue
        t = U.get(e, 'BSXd')
        if not ((e in leftovers and was_pool[leftovers[e]] is not None) or (t not in slots and pools.is_pool(R, t))):
            continue
        prow, pid = b.prow_of_entry(e), b.pid_of_entry(e)
        if pid not in b.placed and _prospect(b, prow) and home(prow) == key and not elsewhere(pid, e):
            found.append(((P.get(prow, 'WzKY'), -b.quality.get(pid, 0), pid), pid, 'pool', e))
    fa = {R.link_to_pid.get(l): l for l in b.fa_links}
    for prow in range(P.cur_rec):
        pid = P.get(prow, 'zIBw')
        if pid in b.placed or elsewhere(pid) or not _prospect(b, prow) or home(prow) != key:
            continue
        if pid not in fa and any(x not in b.deleted for x in live.get(pid, [])):
            continue            # on a national team only: left alone
        found.append(((P.get(prow, 'WzKY'), -b.quality.get(pid, 0), pid), pid, 'fa' if pid in fa else 'none', fa.get(pid)))
    joined = set()
    for _, pid, how, x in sorted(found):
        # not the Vees: their slot is a custom team on every roster the draft reads, and these players are placed for the draft
        room = [s for s in slots if size[s] < PROSPECT_ROOM and not pools.is_pool(R, s) and s != L.VEES]
        if not room:
            break
        club = min(room, key=lambda s: (size[s], s))
        prow = R.p_by_id[pid]
        if how == 'pool':
            frm = T.get(U.get(x, 'BSXd'), 'JkmY')
            leftovers.pop(x, None)
            b.move_entry(x, club)
            e = x
        else:
            frm = 'free agent' if how == 'fa' else 'no team'
            e = b.new_entry(club, x if how == 'fa' else b.new_link(pid), prow)
            b.arrivals.setdefault(club, []).append(e)
            live.setdefault(pid, []).append(e)
            b.drop_fa(pid)
        leftovers[e] = club
        joined.add(e)
        size[club] += 1
        b.placed.add(pid)
        P.set(prow, 'BSXd', club + 1)
        if not P.get(prow, 'WBbd'):
            for f in ('GDhI', 'dhKk', 'IrlK', 'IzRv'):
                P.set(prow, f, 0)
        b.log.append([T.get(club, 'nnsx'), 'prospect joined', R.name(prow),
                      f"{P.get(prow, 'WzKY') + 1900} draft prospect, from {frm}", U.get(e, 'tRVs')])
        stats['prospects placed'] += 1
    return joined


def _fill_lineup(b, slot, leftovers, live, abbr, stats, max_age=None, staying=()):
    """Top a club up to a dressable 20 (2 G, 6 D, 12 F): first with former players of the slot at the
    missing position (so a second run keeps the same ones), best first, then with prospect-pool
    players and free agents (for a junior club only those of junior age), the ones nearest the club's own level first and
    one better than its best player only when no other is left (an AHL club short of a forward signed Jonathan Toews, the
    best free agent, on the game's own roster: 2026-10-22). Never with a player another
    league lists (`b.league_rows`): its step would take him away again and leave the club short; nor with one under an
    NHL contract whom no list names (`b.contract_org`: Builder.contract_strays places him at the end, and a second run
    would not count him here but fill his place again: Dower-Nilsson at Grand Rapids, 2026-10-22). The former players
    in `staying` (under contract with the parent club) stay anyway and are left out."""
    P, U, T = b.P, b.U, b.R.T
    young_enough = lambda prow: max_age is None or b.data.season_year - (P.get(prow, 'dnFq') + 1910) <= max_age
    usable = lambda prow: young_enough(prow) and prow not in b.league_rows and P.get(prow, 'zIBw') not in b.contract_org
    cls = lambda prow: group('CLRDG'[P.get(prow, 'aljv')])
    have = Counter(cls(b.prow_of_entry(e)) for e in b.entries_on(slot) if e not in leftovers)
    for g, need in CORE.items():
        missing = need - have[g]
        if missing <= 0:
            continue
        former = sorted((e for e, s in leftovers.items() if s == slot and cls(b.prow_of_entry(e)) == g
                         and b.prow_of_entry(e) not in b.league_rows and e not in staying),
                        key=lambda e: (-b.q(e), e))
        for e in former[:missing]:
            leftovers.pop(e)
            P.set(b.prow_of_entry(e), 'BSXd', slot + 1)     # his contract team is the club he stays with
            b.log.append([abbr, 'stays to fill the line-up', b.R.name(b.prow_of_entry(e)), f"needed at {g}",
                          U.get(e, 'tRVs')])
            stats['kept to fill the line-up'] += 1
            missing -= 1
        if missing <= 0:
            continue
        free = []      # (-quality, pid, free-agent link or pool entry, record)
        for link in b.fa_links:
            pid = b.R.link_to_pid.get(link)
            prow = b.R.p_by_id.get(pid)
            if prow is not None and cls(prow) == g and usable(prow) and not any(
                    U.get(x, 'BSXd') not in L.NATIONAL for x in live.get(pid, [])):
                free.append((-b.quality.get(pid, 0), pid, ('fa', link), prow))
        for t in pools.SPARE_SLOTS:
            if T.get(t, 'NYKk') and pools.is_pool(b.R, t):
                for e in b.entries_on(t):
                    prow = b.prow_of_entry(e)
                    pid = b.pid_of_entry(e)
                    if cls(prow) == g and usable(prow) and pid not in b.placed:
                        free.append((-b.quality.get(pid, 0), pid, ('pool', e), prow))
        own = sorted(b.q(e) for e in b.entries_on(slot) if e not in leftovers)
        top, level = (own[-1], own[len(own) // 2]) if own else (None, None)
        fit = lambda q: (top is not None and q > top, abs(q - level) if level is not None else -q, -q)
        for _, pid, (where, x), prow in sorted(free, key=lambda f: (fit(-f[0]), f[1]))[:missing]:
            if where == 'fa':
                e = b.new_entry(slot, x, prow)
                b.arrivals.setdefault(slot, []).append(e)
                live.setdefault(pid, []).append(e)
                b.drop_fa(pid)
                detail = f"free agent, needed at {g}"
            else:
                detail = f"from {T.get(U.get(x, 'BSXd'), 'JkmY')}, needed at {g}"
                e = x
                b.move_entry(e, slot)
            b.placed.add(pid)
            P.set(prow, 'BSXd', slot + 1)
            if slot in L.AHL and pid not in b.list_rated and pid not in b.full_rated and b.data.ratings_list:
                # the ratings step finds AHL players by name (Builder.apply_list_ratings): as a second run would
                birth = (P.get(prow, 'dnFq') + 1910, P.get(prow, 'pLKJ') + 1, P.get(prow, 'iwsK') + 1)
                on_list = b.list_rating_for(P.get(prow, 'PedH'), P.get(prow, 'RMbQ'), birth, by_name=True)
                if on_list and ratings.is_goalie(on_list) == (P.get(prow, 'aljv') == 4):
                    b.write_list_rating(prow, on_list)
            b.log.append([abbr, 'signed to fill the line-up', b.R.name(prow), detail, U.get(e, 'tRVs')])
            stats['signed to fill the line-up'] += 1


def _feed_position(b, row, p, live, name):
    """The league's current position for a player it lists (a feed that only says 'forward' moves a
    defenceman up front, and leaves a forward's position alone). Goalies never change, and neither
    do players on a national team: their squad's lines were dealt by position. True when it changed
    (his club's lines are dealt again)."""
    cur = b.P.get(row, 'aljv')
    want = (0 if cur == 3 else cur) if p['pos'] == 'F' else L.POS_CODE.get(p['pos'])
    if want is None or want == cur or 4 in (cur, want):
        return False
    if any(b.U.get(e, 'BSXd') in L.NATIONAL for e in live.get(b.P.get(row, 'zIBw'), [])):
        return False
    b.set_position(row, want)
    b.log.append([p['team'], 'position changed', name, f"{L.POS_NAME[cur]} to {L.POS_NAME[want]}", ''])
    return True


def affiliates(R):
    """AHL slot -> its NHL parent slot. NHL teams name their farm team in ttOk.ahlaffiliate (AHL
    slot + 1, six bits); Seattle's and Vegas's farm teams sit in custom slots 234/235, beyond that."""
    T = R.T
    out = {T.get(n, 'TxsC') - 1: n for n in sorted(L.NHL_PRIMARY) if T.get(n, 'TxsC')}
    out.update(L.AHL_PARENT_EXTRA)
    return out


def pair_farms(R, teams):
    """Every NHL team 0-29 names as its farm team (ttOk.ahlaffiliate) the AHL club of slots 32-61 whose list (`teams`, with
    each player's `org`) holds most of its players: the game's own roster still pairs them as in 2014 (Colorado with the
    club in Lake Erie's slot, now Chicago's, Carolina's farm). Only a pairing of one club per team is written; returns the
    NHL slots whose farm team changed."""
    T = R.T
    parent = {}
    for t in teams:
        orgs = Counter(L.API_TO_SLOT.get(p.get('org')) for p in t['players'] if p.get('org'))
        top = orgs.most_common(1)
        if 32 <= t['slot'] < 62 and top and top[0][0] is not None and top[0][0] < 30:
            parent[t['slot']] = top[0][0]
    if sorted(parent.values()) != list(range(30)):
        return []
    changed = []
    for club, nhl in sorted(parent.items(), key=lambda cn: cn[1]):
        if T.get(nhl, 'TxsC') != club + 1:
            T.set(nhl, 'TxsC', club + 1)
            changed.append(nhl)
    return changed


def _nhl_contract(b, row, parent):
    """An AHL player on an NHL contract: his NHL organisation holds his rights, and he has a
    two-way deal (a default one if the save had none)."""
    b.set_pro_team(row, parent)
    two_way(b.P, row, b.data.season_year, b.money)


def _rights(b, row, org):
    """The organisation the league's list names (`org`, an NHL.com code) holds the player's rights, with a two-way deal
    (the real one comes later, Builder.real_contracts); none (an AHL-only deal), or one that cannot hold rights (Seattle
    or Vegas on a roster for the unpatched game: contracts.rights_teams): nobody's, so rights an earlier roster left stay
    no more."""
    slot = L.API_TO_SLOT.get(org) if org else None
    if slot is None or not pay.holds_rights(b.P, slot):
        b.P.set(row, 'WBbd', 0)
    else:
        _nhl_contract(b, row, slot)


def two_way(P, row, season_year, scale=pay.GAME):
    """Player row `row` gets a two-way deal: his own terms if he has some, else a default one on the roster's money
    `scale` (contracts.default_terms; gamepatch.rights_fit too)."""
    if not P.get(row, 'GDhI') or not P.get(row, 'dhKk'):
        years, cap = pay.default_terms(P.get(row, 'dnFq') + 1910 >= season_year - 22, scale)
        P.set(row, 'GDhI', years)
        P.set(row, 'dhKk', cap)
        P.set(row, 'IrlK', 0)
        P.set(row, 'IzRv', 0)
    P.set(row, 'contractis2way', 1)


def _is_import(p, league):
    """A player from abroad (only in leagues of one country)."""
    home = L.country_code(league.get('country'))
    return home is not None and bool(p.get('country')) and L.country_code(p['country']) != home


def _bio(b, row, p):
    """Facts the league publishes about a player overwrite what the save had."""
    P = b.P
    if p.get('height_in'):                          # the game's own inches and pounds (the AHL's list)
        P.set(row, 'QBpy', max(0, min(31, p['height_in'] - 54)))
    elif p.get('height_cm'):
        P.set(row, 'QBpy', max(0, min(31, round(p['height_cm'] / 2.54) - 54)))
    if p.get('weight_lb'):
        P.set(row, 'WZNs', max(0, min(255, p['weight_lb'] - 120)))
    elif p.get('weight_kg'):
        P.set(row, 'WZNs', max(0, min(255, round(p['weight_kg'] * 2.20462) - 120)))
    if p.get('shoots') in ('L', 'R'):
        P.set(row, 'pkRG', 0 if p['shoots'] == 'L' else 1)
    if p.get('num'):
        P.set(row, 'tRVs', min(p['num'], 99))


def _letters(b, team, listed):
    """One captain and two alternates among the dressed skaters: the club's own where listed."""
    U = b.U
    ents = b.entries_on(team)
    for e in ents:
        U.set(e, 'lcCm', 0)
    dressed = [e for e in ents if U.get(e, 'jZSh') and b.cls(e) != 'G']
    best = sorted(dressed, key=lambda e: (-b.q(e), e))
    captain = next((e for e in dressed if listed.get(e) == 'C'), None) or (best[0] if best else None)
    if captain is None:
        return
    U.set(captain, 'lcCm', 1)
    alternates = [e for e in dressed if listed.get(e) == 'A' and e != captain][:2]
    alternates += [e for e in best if e != captain and e not in alternates][:2 - len(alternates)]
    for e in alternates:
        U.set(e, 'lcCm', 2)
