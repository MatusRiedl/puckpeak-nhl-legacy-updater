"""Build the data pack the updater ships with and downloads (legacy_roster/data/datapack.json.gz).

    python tools/build_datapack.py                     rebuild from the caches in tools/cache
    python tools/build_datapack.py --refresh ratings   refresh the current ratings list first (slow, polite; private/)
    python tools/build_datapack.py --refresh iihf      download the IIHF roster PDFs first
    python tools/build_datapack.py --refresh shl,chl   fetch club leagues first (a league or one part: ohl)
    python tools/build_datapack.py --research DIR      reuse the lab's research folder as the cache

The pack holds everything the updater does not fetch live:
    ratings_list the current ratings of NHL players (name, team, overall, attributes)
    iihf         rosters for the national teams the base roster leaves empty
    leagues      club rosters per league, already placed into the game's team slots (tools/club_slots.json)
                 (the AHL's: the 32 clubs' rosters of the maintainer's private source, tools/cache/ahl_rosters.json,
                 with each player's NHL organisation; the feed only adds photos and letters: --refresh ahl_rosters)
    nhl          a snapshot of the NHL rosters, used only when the user is offline
    nhl_last     everyone who played in the NHL last season (birthdate, size, hand, team now): who is
                 retired and who is an unsigned free agent (refreshed with nhl)
    drafts       every NHL draft pick since FIRST_DRAFT (refreshed with nhl)
    schedule     every regular-season game of the season (date, home, away): the game's calendar
                 (refreshed with nhl, or alone: --refresh schedule)
    ahl_schedule every AHL regular-season game (date, home slot, away slot): the 32-team game patch's farm
                 calendar and the AHL's calendar on other rosters (refreshed with ahl, or alone: --refresh ahl_schedule)
    schedules    every regular-season game of the other club leagues, per league part (shl, liiga, extraliga, del,
                 nl, norway, ohl, qmjhl, whl): [date, home, away], a club as its team slot, or as its name in the feed
                 when the game has no slot for it (refreshed with the league, or alone: --refresh schedules, or one
                 league's: --refresh shl_schedule)
    contracts    the real 2026-27 NHL contracts (--refresh contracts [--db FILE]; legacy_roster/contracts.py)
    ratings_full the current ratings, player types and tendencies of every player, all leagues
                 (--refresh ratings_full [--db FILE], no network)
    retired      players who announced their retirement, kept by hand in tools/retired.json (copied on every build;
                 NHL.com marks no retirement); the unsigned of last season aged 38+ retire without it (builder)
    skins        the skin group (medium / brown / dark) of players whose photos say so, kept by hand in tools/skin_marks.json
                 (copied on every build; the builder gives created players a head that fits: donors.py `group_for`)
    equipment    the real sock tuck, pants, tape and neck guard of the NHL's and AHL's players, as raw numbers
                 (--refresh equipment [--db FILE], no network; `datasource.equipment_part`)
    club_lines   the clubs' real lines outside the NHL, per club slot: the Extraliga's match line-ups (--refresh
                 extraliga_lines, hokej.cz) over a larger private database's lines (--refresh club_lines [--db FILE],
                 no network; made from the pack's own rosters, so refresh the leagues first)
    captains     not a part: every league player's `letter` and `lines[code]['letters']` (NHL.com ids) are this
                 season's games' (NHL.com's game rosters, HockeyTech's game summaries, the Extraliga's match line-ups,
                 refreshed with lines / ahl / chl / extraliga_lines), else the larger database's (club_lines) where
                 the games named nobody on that team (give_letters; docs/notes/captains.md)

ratings_list, contracts, ratings_full, equipment and the AHL's rosters are made by the maintainer's private tools (private/, kept
out of git, DEVELOPING.md). Without them those parts are taken over from the pack being replaced, as they are.

Before writing, every part is compared with the pack being replaced: a part that is gone or has
lost more than 40% of its entries stops the build (a feed that changed its layout looks like that).
Pass --accept-drops when the drop is real.
"""
import argparse
import datetime
from collections import Counter
import functools
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from legacy_roster import contracts, datasource  # noqa: E402
from legacy_roster.layout import API_TO_SLOT  # noqa: E402
from providers import (czech, hockeytech, hokejcz_lines, iihf, liiga, nhl_facts, penny_del, sportality, swiss,  # noqa: E402
                       wiki_logo)
import lines_job  # noqa: E402  (the lines' fetching, shared with the server's daily job)

PRIVATE = os.path.join(ROOT, 'private')        # the makers of three parts, kept out of git (DEVELOPING.md)
sys.path.insert(2, PRIVATE)
try:
    import contracts_db  # noqa: E402
    import ratings_full  # noqa: E402
    import ratings_list  # noqa: E402
    import club_rosters_db  # noqa: E402
    import club_lines_db  # noqa: E402
except ImportError:
    contracts_db = ratings_full = ratings_list = club_rosters_db = club_lines_db = None
try:
    import equipment_db  # noqa: E402
except ImportError:
    equipment_db = None
PRIVATE_PARTS = ('ratings_list', 'contracts', 'ratings_full', 'equipment')

# one feed per part of a league (club_slots.json); a part's cache is tools/cache/<part>.json
FEEDS = {'liiga': liiga.fetch, 'extraliga': czech.fetch,
         'shl': functools.partial(sportality.fetch, league='shl'),
         'del': penny_del.fetch, 'nl': swiss.fetch,
         'norway': functools.partial(sportality.fetch, league='norway'),
         'ahl': functools.partial(hockeytech.fetch, client='ahl'),
         'ohl': functools.partial(hockeytech.fetch, client='ohl'),
         'qmjhl': functools.partial(hockeytech.fetch, client='lhjmq'),
         'whl': functools.partial(hockeytech.fetch, client='whl')}
# each part's regular-season calendar: [[date, home club, away club]] with the clubs as `FEEDS` names them
SCHEDULES = {'liiga': lambda season: liiga.schedule(season), 'extraliga': lambda season: czech.schedule(season),
             'shl': lambda season: sportality.schedule(season, league='shl'),
             'del': lambda season: penny_del.schedule(season), 'nl': lambda season: swiss.schedule(season),
             'norway': lambda season: sportality.schedule(season, league='norway'),
             'ohl': functools.partial(hockeytech.schedule, client='ohl'),
             'qmjhl': functools.partial(hockeytech.schedule, client='lhjmq'),
             'whl': functools.partial(hockeytech.schedule, client='whl')}
CACHE = os.path.join(ROOT, 'tools', 'cache')
OUT =os.path.join(ROOT, 'legacy_roster', 'data', 'datapack.json.gz')
RETIRED = os.path.join(ROOT, 'tools', 'retired.json')
SLOTS = os.path.join(ROOT, 'tools', 'club_slots.json')
SEASON = 2026
MIN_FULL_RATINGS = 300          # fewer fully rated players means the ratings parser broke (Oct 2026: 373)
MIN_FULL_PLAYERS = 5000         # fewer players in ratings_full means its reader broke (Oct 2026: 6,968)
MIN_EQUIPMENT = 500             # fewer players in equipment means its reader broke (Oct 2026: about 1,000)
MAX_DROP = 0.4                 # a part that loses more than this share of its entries stops the build
MIN_AGE, MAX_AGE = 15, 45       # club players outside these ages are typos in the feed
LEAGUE_MIN_AGE = {'ahl': 17}    # juniors may be 15 (exceptional status), AHL players not
MAX_SHARED_PHOTO = 3            # this many players with the same photo link: it is a placeholder
# ESPN's logos for dark backgrounds (the game's menus are dark). Several differ from the plain ones
# (Tampa Bay and Washington are all white, Toronto's leaf is white, Boston, Vancouver, Los Angeles and
# Detroit in part): they are used for the banner, watermark and calendar pictures; the pictures with a
# white edge are drawn from the plain logo (install.plain_logo_url, 0.8.1)
NHL_LOGO = "https://a.espncdn.com/i/teamlogos/nhl/500-dark/{}.png"
FIRST_DRAFT = 2005              # the oldest players still playing were drafted about then
ESPN_CODE = {'UTA': 'utah', 'TBL': 'tb', 'NJD': 'nj', 'SJS': 'sj', 'LAK': 'la'}


def file_date(path):
    return f"{datetime.datetime.fromtimestamp(os.path.getmtime(path)):%Y-%m-%d}"


def wiki_logo_of(title):
    """A club's logo link from Wikipedia, remembered in tools/cache/logos.json (None if none)."""
    cache = os.path.join(CACHE, 'logos.json')
    known = {}
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as f:
            known = json.load(f)
    if title not in known:
        try:
            known[title] = wiki_logo.logo_url(title)
        except Exception as err:          # rate limited or offline: try again next build
            print(f"logo of {title}: {err}")
            return None
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(known, f, ensure_ascii=False, indent=0, sort_keys=True)
    if not known[title]:
        print(f"logo of {title}: none on Wikipedia (give the club a 'logo' or 'wiki' in club_slots.json)")
    return known[title]


def nhl_logos():
    """NHL.com team code -> logo link. NHL.com has SVG only; ESPN publishes the same marks as PNG."""
    return {abbr: NHL_LOGO.format(ESPN_CODE.get(abbr, abbr.lower())) for abbr in API_TO_SLOT}


def short_code(name):
    """Three plain capital letters for a club the game has no slot for: the start of its most
    distinctive word ('HC Something' -> 'SOM'), accents dropped."""
    import re
    import unicodedata
    plain = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    words = [re.sub('[^A-Za-z]', '', w) for w in plain.split()]
    words = [w for w in words if len(w) >= 3 and w.upper() not in ('HC', 'EHC', 'EV', 'SC', 'THE')] or words
    return (words[0] if words else 'XXX')[:3].upper().ljust(3, 'X')


def parts_of(conf, key):
    """[(part key, league_id, slots)] of a league in club_slots.json."""
    if 'parts' in conf:
        return [(p, v['league_id'], v['slots']) for p, v in conf['parts'].items()]
    return [(key, conf['league_id'], conf['slots'])]


def build_league(key, conf, refresh, db=None):
    """The pack entry of one club league from its parts' caches (fetched first if asked), or None."""
    teams, left_out, extra, former, dates = [], [], [], [], []
    orgs = False
    for part, league_id, slots in parts_of(conf, key):
        cache = os.path.join(CACHE, f"{part}.json")
        if key in refresh or part in refresh:
            os.makedirs(CACHE, exist_ok=True)
            clubs = FEEDS[part](SEASON, sources=[c['source'] for c in slots.values()])
            with open(cache, 'w', encoding='utf-8') as f:
                json.dump(clubs, f, ensure_ascii=False)
        if part == 'ahl':
            # the 32 clubs' rosters of the private source, each player's NHL organisation with them (owner,
            # 2026-10-22); the feed's photos and letters go into it when it is made (private/)
            rosters = os.path.join(CACHE, 'ahl_rosters.json')
            if club_rosters_db and (key in refresh or 'ahl_rosters' in refresh):
                made = club_rosters_db.extract(db or club_rosters_db.contracts_db.DB,
                                               clubs=[c['source'] for c in slots.values()], feed_path=cache)
                club_rosters_db.report(made)
                with open(rosters, 'w', encoding='utf-8') as f:
                    json.dump(made, f, ensure_ascii=False)
            if os.path.exists(rosters):
                cache, orgs = rosters, True
        if not os.path.exists(cache):
            return None
        with open(cache, encoding='utf-8') as f:
            clubs = json.load(f)
        feed_logos = clubs.pop('_logos', {})
        former += clubs.pop('_former', [])      # last season's players on no list now: their photos
        sources = [c['source'] for c in slots.values()]
        if len(set(sources)) != len(sources):
            sys.exit(f"{part}: a club is mapped to two slots in club_slots.json")
        def plausible(club_name, roster):
            players = []
            for p in roster:
                if SEASON - MAX_AGE <= p['birth'][0] <= SEASON - LEAGUE_MIN_AGE.get(part, MIN_AGE):
                    players.append(p)
                else:           # a typo in the feed (born 2011 in the AHL): left out rather than guessed
                    print(f"{part}: {club_name}: left out {p['first']} {p['last']}, birthdate {p['birth']} "
                          "is not possible")
            return players

        for slot, club in sorted(slots.items(), key=lambda kv: int(kv[0])):
            if club['source'] not in clubs:
                sys.exit(f"{part}: no club named {club['source']!r} in the feed (clubs: {sorted(clubs)})")
            players = plausible(club['full'], clubs[club['source']])
            logo = club.get('logo') or feed_logos.get(club['source']) or wiki_logo_of(club.get('wiki') or club['full'])
            teams.append({'slot': int(slot), 'league_id': club.get('league_id', league_id), 'full': club['full'],
                          'short': club['short'], 'abbr': club['abbr'], 'art': club['art'], 'logo': logo,
                          'players': players})
        for name in sorted(set(clubs) - set(sources)):
            left_out.append(name)
            # no slot in the game: kept for a player's own custom team of that name (clubs.own_teams)
            extra.append({'league_id': league_id, 'full': name, 'short': name, 'abbr': short_code(name),
                          'art': name[:3].upper(), 'logo': feed_logos.get(name), 'players': plausible(name, clubs[name])})
        dates.append(file_date(cache))
    # a picture several players share is a feed's "no photo" placeholder, not a photo
    shared = Counter(p.get('photo') for t in teams for p in t['players'] if p.get('photo'))
    shared.update(p['photo'] for p in former)
    for t in teams + extra:
        t['players'] = [dict(p, photo=None) if shared[p.get('photo')] >= MAX_SHARED_PHOTO else p for p in t['players']]
    former = [p for p in former if shared[p['photo']] < MAX_SHARED_PHOTO]
    entry = {'label': conf['label'], 'country': conf.get('country'), 'teams': teams, 'left_out': left_out,
             'extra': extra, 'former': former}
    if orgs:
        entry['orgs'] = True                    # each player names the NHL organisation that holds his rights
    if 'parts' not in conf:
        entry['league_id'] = conf['league_id']
    source = {'label': f"{conf['label']} rosters", 'date': min(dates), 'count': sum(len(t['players']) for t in teams)}
    return entry, source


def build_schedules(slot_map, refresh):
    """The pack part `schedules` from the caches tools/cache/<part>_schedule.json (fetched first if asked) and its
    source entry, or None. A club becomes its team slot (any part of its league: the OHL's games against QMJHL clubs);
    a club the game has no slot for keeps its name. Stops when a slot's club plays no game (a renamed club)."""
    part_slots = {part: (key, slots) for key, conf in slot_map.items() for part, _id, slots in parts_of(conf, key)}
    found, dates = {}, []
    for part, fetch in SCHEDULES.items():
        league, slots = part_slots[part]
        cache = os.path.join(CACHE, f"{part}_schedule.json")
        if {'schedules', f"{part}_schedule", part, league} & refresh:
            os.makedirs(CACHE, exist_ok=True)
            games = fetch(SEASON)
            with open(cache, 'w', encoding='utf-8') as f:
                json.dump(games, f, ensure_ascii=False)
        if not os.path.exists(cache):
            continue
        with open(cache, encoding='utf-8') as f:
            games = json.load(f)
        slot_of = {c['source']: int(k) for p, (lg, s) in part_slots.items() if lg == league for k, c in s.items()}
        idle = sorted(c['source'] for c in slots.values() if not any(c['source'] in g[1:] for g in games))
        if idle:
            raise SystemExit(f"{part} schedule: no game for {', '.join(idle)} (a club renamed in the feed? "
                             "tools/club_slots.json)")
        found[part] = [[date, slot_of.get(home, home), slot_of.get(away, away)] for date, home, away in games]
        dates.append(file_date(cache))
        named = sorted({c for g in found[part] for c in g[1:] if isinstance(c, str)})
        print(f"{part} schedule: {len(games)} games" + (f", no slot for {', '.join(named)}" if named else ''))
    if not found:
        return None
    return found, {'label': f"League calendars {SEASON}-{(SEASON + 1) % 100:02d}", 'date': min(dates),
                   'count': sum(len(g) for g in found.values())}


def give_letters(pack, base, match, nhl_db):
    """Captains for every team the pack lists (owner, 2026-10-24: real captains for the entire game). A club whose feed
    marked none (Liiga's roster, HockeyTech's game summaries do) gets those of its newest match line-ups (`match`: the
    Extraliga), else the larger database's (`base`, per club slot); an NHL team NHL.com's game reports gave none gets the
    database's (`nhl_db`, by NHL.com id). Players are found by name and birth year (the last name and birth year when
    only one player of the club has them); goalies never wear a letter. Returns {source: teams lettered}."""
    plain = hokejcz_lines.plain
    counts = Counter()
    for key, league in sorted((pack.get('leagues') or {}).items()):
        for team in league.get('teams', []):
            players = [p for p in team.get('players', []) if p.get('pos') != 'G']
            if any(p.get('letter') for p in players):
                counts[f"{key} feed"] += 1
                continue
            slot = str(team.get('slot'))
            for label, src in (('matches', match), ('database', base)):
                wanted = (src.get(slot) or {}).get('letters') or []
                if not wanted:
                    continue
                full = {(plain(p['first'] + p['last']), p['birth'][0]): p for p in players}
                short = Counter((plain(p['last']), p['birth'][0]) for p in players)
                given = 0
                for first, last, year, letter in wanted:
                    p = full.get((plain(first + last), year))
                    if p is None and short[(plain(last), year)] == 1:
                        p = next(x for x in players if (plain(x['last']), x['birth'][0]) == (plain(last), year))
                    if p is not None and not p.get('letter'):
                        p['letter'] = letter
                        given += 1
                if given:
                    counts[f"{key} {label}"] += 1
                    break
    for code, entry in sorted((pack.get('lines') or {}).items()):
        if entry.get('letters'):
            counts['nhl games'] += 1
        elif nhl_db.get(code):
            entry['letters'] = dict(nhl_db[code])
            counts['nhl database'] += 1
    return counts


def check_drops(old, new, accept):
    """Stop when a part of the previous pack is missing or much smaller now."""
    problems = []
    for key, src in (old.get('sources') or {}).items():
        now = new['sources'].get(key)
        if now is None:
            problems.append(f"{key}: in the previous pack ({src['count']} entries), missing now")
        elif src['count'] and now['count'] < (1 - MAX_DROP) * src['count']:
            problems.append(f"{key}: {now['count']} entries, the previous pack had {src['count']}")
    full = sum(1 for p in new.get('ratings_list') or [] if len(p['attrs']) >= 10)
    if 'ratings_list' in new and full < MIN_FULL_RATINGS:
        problems.append(f"ratings_list: only {full} players with full attributes (expected {MIN_FULL_RATINGS} or more)")
    count = len((new.get('ratings_full') or {}).get('players') or [])
    if 'ratings_full' in new and count < MIN_FULL_PLAYERS:
        problems.append(f"ratings_full: only {count} players (expected {MIN_FULL_PLAYERS} or more)")
    count = len((new.get('equipment') or {}).get('players') or [])
    if 'equipment' in new and count < MIN_EQUIPMENT:
        problems.append(f"equipment: only {count} players (expected {MIN_EQUIPMENT} or more)")
    if problems and not accept:
        sys.exit("Not written -- a feed may have changed its layout:\n   " + "\n   ".join(problems) +
                 "\nCheck the provider; if the drop is real, run again with --accept-drops.")
    for p in problems:
        print(f"accepted: {p}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--refresh', default='',
                    help="comma list: ratings, iihf, nhl (also nhl_last, drafts and schedule), lines, ahl_schedule, contracts, "
                         "ratings_full, equipment, ahl_rosters, club_lines, extraliga_lines, schedules (every league's calendar) or <part>_schedule, or a league "
                         "(liiga, extraliga, shl, del, nl, norway, ahl, chl; rosters and calendar) or one part of it "
                         "(ohl, qmjhl, whl)")
    ap.add_argument('--db', default=contracts_db.DB if contracts_db else None,
                    help="the database file for --refresh contracts / ratings_full / equipment / ahl_rosters (private/)")
    ap.add_argument('--research', help="lab research folder to use as the cache (work/research)")
    ap.add_argument('--accept-drops', action='store_true', help="write the pack even if a part shrank or vanished")
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()
    refresh = {x.strip() for x in args.refresh.split(',') if x.strip()}
    ratings_cache = None if ratings_list is None else         os.path.join(args.research, ratings_list.RESEARCH) if args.research else ratings_list.CACHE
    iihf_cache = os.path.join(args.research, 'iihf2026') if args.research else os.path.join(CACHE, 'iihf')
    pack = {'format': datasource.PACK_FORMAT, 'season': SEASON, 'sources': {},
            'generated': f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ}"}

    if 'ratings' in refresh and ratings_list:
        ratings_list.crawl(ratings_cache)
    if ratings_cache and os.path.isdir(ratings_cache):
        players = ratings_list.compact(ratings_list.parse(ratings_cache))
        pack['ratings_list'] = players
        pack['sources']['ratings_list'] = {
            'label': "Current ratings", 'date': file_date(os.path.join(ratings_cache, '_slugs.json')),
            'count': len(players)}
        full = sum(1 for p in players if len(p['attrs']) >= 10)
        print(f"ratings: {len(players)} players ({full} with full attributes)")

    if 'iihf' in refresh or os.path.isdir(iihf_cache):
        rosters = iihf.fetch(iihf_cache)
        pack['iihf'] = rosters
        pack['sources']['iihf'] = {'label': "IIHF rosters", 'date': file_date(os.path.join(iihf_cache, 'AUT.pdf')),
                                   'count': sum(len(v) for v in rosters.values())}

    # club leagues: the feed's clubs are put into the game's team slots as tools/club_slots.json says
    with open(SLOTS, encoding='utf-8') as f:
        slot_map = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
    pack['leagues'] = {}
    for key, conf in slot_map.items():
        built = build_league(key, conf, refresh, args.db)
        if built is None:
            continue
        pack['leagues'][key], pack['sources'][key] = built
        if built[0]['left_out']:
            print(f"{key}: no slot for {', '.join(built[0]['left_out'])}")

    nhl_cache = os.path.join(CACHE, 'nhl.json')
    if 'nhl' in refresh:
        os.makedirs(CACHE, exist_ok=True)
        with open(nhl_cache, 'w', encoding='utf-8') as f:
            json.dump(datasource.fetch_nhl_teams(SEASON, print, fresh=True), f, ensure_ascii=False)
    if os.path.exists(nhl_cache):
        with open(nhl_cache, encoding='utf-8') as f:
            teams = json.load(f)
        pack['nhl'] = teams
        pack['nhl_logos'] = nhl_logos()
        pack['sources']['nhl'] ={'label': "NHL.com rosters (offline copy)", 'date': file_date(nhl_cache),
                                  'count': sum(len(t.get(g, [])) for t in teams.values()
                                               for g in ('forwards', 'defensemen', 'goalies'))}

    # NHL facts for every player: who played last season (retired or unsigned) and the drafts
    for key, fetch in (('nhl_last', lambda: nhl_facts.last_season(SEASON)),
                       ('drafts', lambda: nhl_facts.drafts(FIRST_DRAFT, SEASON)),
                       ('schedule', lambda: nhl_facts.schedule(SEASON))):
        cache = os.path.join(CACHE, f"{key}.json")
        if 'nhl' in refresh or key in refresh:
            os.makedirs(CACHE, exist_ok=True)
            with open(cache, 'w', encoding='utf-8') as f:
                json.dump(fetch(), f, ensure_ascii=False)
        if os.path.exists(cache):
            with open(cache, encoding='utf-8') as f:
                pack[key] = json.load(f)
            label = {'nhl_last': "NHL.com: last season's players", 'drafts': f"NHL drafts since {FIRST_DRAFT}",
                     'schedule': f"NHL.com schedule {SEASON}-{(SEASON + 1) % 100:02d}"}[key]
            pack['sources'][key] = {'label': label, 'date': file_date(cache), 'count': len(pack[key])}

    # players who announced their retirement (kept by hand: NHL.com marks none)
    with open(RETIRED, encoding='utf-8') as f:
        pack['retired'] = [{'first': p['first'], 'last': p['last'], 'birth': p['birth']} for p in json.load(f)['players']]
    pack['sources']['retired'] = {'label': "Retired players", 'date': file_date(RETIRED), 'count': len(pack['retired'])}

    old = datasource.read_pack(args.out) if os.path.exists(args.out) else None

    # the NHL teams' real lines, worked out from their last five games (providers/nhl_lines.py; slots hold NHL.com ids),
    # laid over the pack being replaced the way the server's lines job does (lines_job.lay_nhl: a team whose fetch failed
    # or names a player twice keeps its entry, a category the fetch lacks whole keeps the older one)
    cache = os.path.join(CACHE, 'lines.json')
    if 'lines' in refresh:
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(lines_job.fetch_nhl(SEASON, print), f, ensure_ascii=False)
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as f:
            fetched = json.load(f)
        pack['lines'], laid = lines_job.lay_nhl((old or {}).get('lines'), fetched, letters=False)
        for code, why in laid['nhl_kept'].items():
            print(f"lines: {code} kept from the pack being replaced ({why})")
        for code, older in laid['nhl_older'].items():
            print(f"lines: {code} keeps its older {'/'.join(older)}")
        pack['sources']['lines'] = {'label': "announced lines, and NHL.com's last games", 'date': file_date(cache),
                                    'count': len(pack['lines'])}

    # the lines of the clubs outside the NHL: the private source's (made from the pack's own rosters, so after the leagues),
    # with the Extraliga's match line-ups over their even strength and goalies (providers/hokejcz_lines.py); club slots
    base_cache = os.path.join(CACHE, 'club_lines.json')
    if club_lines_db and 'club_lines' in refresh:
        os.makedirs(CACHE, exist_ok=True)
        with open(base_cache, 'w', encoding='utf-8') as f:
            json.dump(club_lines_db.extract(args.db or club_lines_db.contracts_db.DB, pack), f, ensure_ascii=False)
    cache = os.path.join(CACHE, 'extraliga_lines.json')
    if 'extraliga_lines' in refresh:
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(lines_job.fetch_extraliga(SEASON, print), f, ensure_ascii=False)
    base, match = {}, {}
    for path, into in ((base_cache, base), (cache, match)):
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                into.update(json.load(f))
    nhl_db = base.pop('_nhl', {})
    if base or match:
        pack['club_lines'] = hokejcz_lines.merge(base, match)
        pack['sources']['club_lines'] = {'label': "club lines: match line-ups and a larger database",
                                         'date': file_date(cache if match else base_cache),
                                         'count': len(pack['club_lines'])}
    counts = give_letters(pack, base, match, nhl_db)
    dated = [p for p in (base_cache, cache) if os.path.exists(p)]
    if dated:
        pack['sources']['captains'] = {'label': "captains: this season's games, else a larger database",
                                       'date': file_date(dated[0]), 'count': sum(counts.values())}
    print("captains: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    # the AHL's calendar for the game patch's farm league, clubs as their team slots (tools/club_slots.json)
    cache = os.path.join(CACHE, 'ahl_schedule.json')
    if 'ahl' in refresh or 'ahl_schedule' in refresh:
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(hockeytech.schedule(SEASON), f, ensure_ascii=False)
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as f:
            games = json.load(f)
        slot_of = {v['source']: int(k) for k, v in slot_map['ahl']['slots'].items()}
        missing = sorted({club for g in games for club in g[1:] if club not in slot_of})
        if missing:
            raise SystemExit(f"ahl_schedule: no slot for {', '.join(missing)} (tools/club_slots.json)")
        pack['ahl_schedule'] = [[date, slot_of[home], slot_of[away]] for date, home, away in games]
        pack['sources']['ahl_schedule'] = {'label': f"AHL schedule {SEASON}-{(SEASON + 1) % 100:02d}",
                                           'date': file_date(cache), 'count': len(games)}

    # the other club leagues' calendars (schedule.apply_league writes them into the roster's league tables)
    built = build_schedules(slot_map, refresh)
    if built:
        pack['schedules'], pack['sources']['schedules'] = built

    # the real contracts (only their numbers)
    cache = os.path.join(CACHE, 'contracts.json')
    if 'contracts' in refresh and contracts_db:
        deals = contracts_db.extract(args.db)
        contracts_db.report(deals)
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(deals, f, ensure_ascii=False)
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as f:
            pack['contracts'] = json.load(f)
        pack['sources']['contracts'] = {'label': f"Contracts {SEASON}-{(SEASON + 1) % 100:02d}",
                                        'date': file_date(cache), 'count': len(pack['contracts'])}
        mixed = contracts.misplaced(pack['contracts'], datasource.flatten_nhl(pack.get('nhl') or {}))
        if mixed:
            raise SystemExit("contracts: the deals of " + ', '.join(f"{a} are {b}'s players" for a, b in mixed.items())
                             + ": a team number is mixed up in the source (private/contracts_db.py SOURCE_SLOT)")

    # the current ratings, player types and tendencies of every player (only their numbers)
    cache = os.path.join(CACHE, 'ratings_full.json')
    if 'ratings_full' in refresh and ratings_full:
        part = ratings_full.extract(args.db)
        ratings_full.report(part)
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(part, f, ensure_ascii=False)
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as f:
            pack['ratings_full'] = json.load(f)
        pack['sources']['ratings_full'] = {'label': "Current ratings, player types and tendencies",
                                            'date': file_date(cache), 'count': len(pack['ratings_full']['players'])}

    # the real equipment of the NHL and AHL players (raw numbers; the builder says what they mean)
    cache = os.path.join(CACHE, 'equipment.json')
    if 'equipment' in refresh and equipment_db:
        stats = {}
        part = equipment_db.extract(args.db, stats)
        equipment_db.report(part, stats)
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(part, f, ensure_ascii=False)
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as f:
            pack['equipment'] = json.load(f)
        pack['sources']['equipment'] = {'label': "Real equipment of NHL and AHL players", 'date': file_date(cache),
                                        'count': len(pack['equipment']['players'])}

    # the skin groups of players whose photos show brown or dark skin, kept by hand (tools/skin_marks.json, docs/notes/skin-tones.md)
    marks = os.path.join(ROOT, 'tools', 'skin_marks.json')
    if os.path.exists(marks):
        with open(marks, encoding='utf-8') as f:
            players = json.load(f)
        pack['skins'] = {'format': datasource.SKINS_FORMAT, 'players': players}
        pack['sources']['skins'] = {'label': "Skin groups of players (from their photos)", 'date': file_date(marks),
                                    'count': len(players)}

    for key in PRIVATE_PARTS:                 # no private maker and no cache: keep what the pack has
        if key not in pack and old and key in old:
            pack[key], pack['sources'][key] = old[key], old['sources'][key]
            print(f"{key}: kept from the pack being replaced (no maker in private/)")
    old_ahl = ((old or {}).get('leagues') or {}).get('ahl')
    if old_ahl and old_ahl.get('orgs') and not (pack['leagues'].get('ahl') or {}).get('orgs'):
        pack['leagues']['ahl'], pack['sources']['ahl'] = old_ahl, old['sources']['ahl']
        print("ahl: kept from the pack being replaced (the rosters' maker is in private/)")
    if old:
        check_drops(old, pack, args.accept_drops)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    data = datasource.pack_bytes(pack)            # the same writer as the server's lines job: the same pack, the same bytes
    with open(args.out, 'wb') as f:
        f.write(data)
    raw = len(json.dumps(pack, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    print(f"{args.out}: {len(data) / 1024:.0f} KB ({raw / 1024:.0f} KB of JSON)")
    for key, src in pack['sources'].items():
        print(f"   {key}: {src['count']} entries, dated {src['date']}")


if __name__ == '__main__':
    main()
