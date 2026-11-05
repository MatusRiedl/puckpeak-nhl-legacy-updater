"""Where the updater gets its facts.

  * NHL rosters come live from NHL.com, so a roster built now reflects today's moves.
  * Everything else (ratings, IIHF national teams, later the other leagues) comes from one
    "data pack": a small JSON file built by the project maintainers (tools/build_datapack.py).
    The newest pack is downloaded when possible; a copy shipped with the program is the fallback.
"""
import gzip
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from . import layout as L
from .builder import Data
from .matching import match, norm

# The program's own file server (0.32.0): the newest data pack and the picture packs (packs.py; MAINTAINING.md,
# tools/publish_packs.py). LEGACY_ROSTER_FILES_URL names another one (tests, a local copy); LEGACY_ROSTER_PACK_URL
# overrides the data pack's address alone.
FILES_URL = "https://puckpeak.com/legacy-roster/"
PACK_URL = FILES_URL + "datapack.json.gz"
BUNDLED_PACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'datapack.json.gz')
# Mozilla's list of trusted certificates (certifi's cacert.pem), put into the exe by build.ps1; not in git
CA_BUNDLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cacert.pem')
# the newest data pack layout this program understands; a pack with a higher number was made for
# a newer version of the program and is ignored (raise it only together with the code that reads it)
PACK_FORMAT = 2
OLDEST_FORMAT = 2              # format 1 named two parts differently (0.32.0): such a pack would hide them
NHL_API = "https://api-web.nhle.com/v1"
NHL_SEARCH = "https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit=20&q="
ROSTER_TTL = 20 * 60          # seconds a downloaded NHL roster set stays fresh
MISSING_TTL = 6 * 3600


def data_home():
    """Where programs keep their own files on this system: %LOCALAPPDATA% on Windows,
    ~/Library/Application Support on a Mac, $XDG_DATA_HOME (~/.local/share) on Linux."""
    home = os.path.expanduser('~')
    if os.name == 'nt':
        return os.environ.get('LOCALAPPDATA') or home
    if sys.platform == 'darwin':
        return os.path.join(home, 'Library', 'Application Support')
    return os.environ.get('XDG_DATA_HOME') or os.path.join(home, '.local', 'share')


def app_dir(*parts):
    path = os.path.join(data_home(), 'NHLLegacyRosterUpdater', *parts)
    os.makedirs(os.path.dirname(path) if os.path.splitext(path)[1] else path, exist_ok=True)
    return path


class Offline(Exception):
    """A download failed and there is nothing cached to fall back on."""


class NotSafe(Offline):
    """A site's certificate could not be checked, so nothing was downloaded from it."""


_tls = None


def tls_context():
    """Windows' own trusted certificates plus Mozilla's list when the program carries it.

    Windows fetches some root certificates only when one of its own programs needs them, so a PC
    can lack the one a site uses (search.d3.nhle.com: Let's Encrypt) while browsers, which bring
    their own lists, work fine. Python then reports a missing or expired certificate."""
    global _tls
    if _tls is None:
        ctx = ssl.create_default_context()
        if os.path.exists(CA_BUNDLE):
            try:
                ctx.load_verify_locations(CA_BUNDLE)
            except (OSError, ssl.SSLError):
                pass
        _tls = ctx
    return _tls


def http_get(url, timeout=30, retries=3):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (NHLLegacyRosterUpdater)'})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=tls_context()) as r:
                return r.read()
        except urllib.error.HTTPError as err:
            if err.code == 404 or attempt == retries:
                raise
            time.sleep(2 + 4 * attempt)       # rate limited or a hiccup: back off politely
        except urllib.error.URLError as err:
            if isinstance(err.reason, ssl.SSLCertVerificationError):     # trying again will not help
                why = getattr(err.reason, 'verify_message', '') or 'certificate check failed'
                raise NotSafe(
                    f"Could not connect safely to {urllib.parse.urlsplit(url).hostname} ({why}). "
                    "Check that the date and time on your PC are right, then try again. "
                    "An antivirus that checks web traffic can also cause this: "
                    "turn its web or HTTPS scanning off for a moment and try again.") from err
            if attempt == retries:
                raise
            time.sleep(1 + 2 * attempt)
        except OSError:
            if attempt == retries:
                raise
            time.sleep(1 + 2 * attempt)


def http_json(url):
    return json.loads(http_get(url))


def files_url():
    """The file server's address, ending in '/' (FILES_URL unless LEGACY_ROSTER_FILES_URL names another)."""
    url = os.environ.get('LEGACY_ROSTER_FILES_URL') or FILES_URL
    return url if url.endswith('/') else url + '/'


def download_to(url, path, on_block=None, timeout=60, chunk=256 * 1024):
    """Stream `url` into a new file `path`; `on_block(bytes)` sees every piece and may raise to stop. The file is
    removed when the download fails or is stopped. Returns the number of bytes."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (NHLLegacyRosterUpdater)'})
    got = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=tls_context()) as r, open(path, 'wb') as out:
            while True:
                block = r.read(chunk)
                if not block:
                    break
                out.write(block)
                got += len(block)
                if on_block:
                    on_block(block)
    except BaseException:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    return got


def _cached(name, ttl):
    path = app_dir('cache', name)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return None


def _store(name, obj):
    with open(app_dir('cache', name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)


# --- NHL.com ---------------------------------------------------------------------------------
def flatten_nhl(teams, extra=()):
    """NHL.com roster responses -> one flat list of players, in team-slot order.

    `teams` maps a team code to the /v1/roster response; `extra` are players the roster
    endpoint leaves out (injured, reassigned), found by find_missing()."""
    out = []
    for abbr in L.API_TO_SLOT:
        d = teams.get(abbr) or {}
        for g in ('forwards', 'defensemen', 'goalies'):
            for p in d.get(g, []):
                if not p.get('birthDate') or not (p.get('firstName') or {}).get('default')                         or not (p.get('lastName') or {}).get('default'):
                    continue            # a page without a birthdate or a name cannot be matched to anyone
                y, m, dd = (int(x) for x in p['birthDate'].split('-'))
                out.append({'team': abbr, 'first': p['firstName']['default'], 'last': p['lastName']['default'],
                            'num': p.get('sweaterNumber'), 'pos': p['positionCode'], 'shoots': p.get('shootsCatches'),
                            'birth': (y, m, dd), 'nhl_id': p['id'], 'height_in': p.get('heightInInches'),
                            'weight_lb': p.get('weightInPounds'), 'country': p.get('birthCountry'),
                            'city': (p.get('birthCity') or {}).get('default'), 'photo': p.get('headshot')})
    for p in extra:
        q = dict(p)
        q['birth'] = tuple(q['birth'])
        out.append(q)
    return out


def fetch_nhl_teams(season_year, progress=None, fresh=False):
    """Current rosters of all 32 teams: {'ANA': <roster response>, ...}."""
    say = progress or (lambda msg: None)
    name = f"nhl_{season_year}.json"
    teams = None if fresh else _cached(name, ROSTER_TTL)
    if teams:
        say("NHL rosters: using the copy downloaded a few minutes ago")
        return teams
    season = f"{season_year}{season_year + 1}"
    teams = {}
    for k, abbr in enumerate(L.API_TO_SLOT):
        say(f"NHL rosters: {abbr} ({k + 1}/32)")
        d = http_json(f"{NHL_API}/roster/{abbr}/{season}")
        if not any(d.get(g) for g in ('forwards', 'defensemen', 'goalies')):
            d = http_json(f"{NHL_API}/roster/{abbr}/current")
        teams[abbr] = d
        time.sleep(0.15)
    _store(name, teams)
    return teams


def _search_player(name, year, prow):
    """NHL.com's search and player pages for one player the roster lists leave out: his entry for find_missing, or None
    (no active namesake born within a year of `year`, not on an NHL team, or a page with no birthdate or name)."""
    hits = http_json(NHL_SEARCH + urllib.parse.quote(name))
    best = None
    for h in hits or ():
        if norm(h.get('name', '')) != norm(name) or not h.get('active'):
            continue
        land = http_json(f"{NHL_API}/player/{h['playerId']}/landing")
        if not land or not land.get('birthDate'):
            continue
        by = int(land['birthDate'][:4])
        if best is None or abs(by - year) < abs(best[0] - year):
            best = (by, land)
        time.sleep(0.05)
    if best is None or abs(best[0] - year) > 1:
        return None
    land = best[1]
    team = land.get('currentTeamAbbrev')
    first, last = (land.get('firstName') or {}).get('default'), (land.get('lastName') or {}).get('default')
    if not land.get('isActive') or team not in L.API_TO_SLOT or not first or not last:
        return None
    y, m, d = (int(x) for x in land['birthDate'].split('-'))
    return {'team': team, 'first': first, 'last': last,
            'num': land.get('sweaterNumber'), 'pos': land.get('position'),
            'shoots': land.get('shootsCatches'), 'birth': [y, m, d], 'nhl_id': land['playerId'],
            'height_in': land.get('heightInInches'), 'weight_lb': land.get('weightInPounds'),
            'country': land.get('birthCountry'), 'city': (land.get('birthCity') or {}).get('default'),
            'photo': land.get('headshot'), 'db_row': prow, 'source': 'player search'}


def find_missing(R, players, progress=None, fresh=False):
    """Players on the source roster's NHL teams that the roster lists leave out.

    The NHL roster endpoint omits injured and some reassigned players. Each one is looked up
    with the player search; those still active with an NHL organisation are returned with
    their current team (and 'db_row', the record they were looked up for)."""
    say = progress or (lambda msg: None)
    api = match(R, [dict(p) for p in players])
    found = {p['row'] for p in api if p['row'] is not None}
    P, U = R.P, R.U
    missing = []
    for i in range(U.cur_rec):
        if U.get(i, 'BSXd') in L.SLOT_TO_API:
            prow = R.p_by_id.get(R.link_to_pid.get(U.get(i, 'TWSX')))
            if prow is not None and prow not in found and prow not in missing:
                missing.append(prow)
    key = hashlib.sha1(repr(sorted((P.get(r, 'zIBw'), P.get(r, 'PedH'), P.get(r, 'RMbQ')) for r in missing)).encode()).hexdigest()[:16]
    cached = None if fresh else _cached(f"missing_{key}.json", MISSING_TTL)
    if cached is not None:
        say(f"NHL: {len(missing)} players not on the roster lists (using earlier look-ups)")
        return cached
    extra = []
    for k, prow in enumerate(missing):
        name = f"{P.get(prow, 'PedH')} {P.get(prow, 'RMbQ')}"
        if k % 10 == 0:
            say(f"NHL: checking players the roster lists leave out ({k + 1}/{len(missing)})")
        year = P.get(prow, 'dnFq') + 1910
        try:                    # a best-effort look-up: a player whose page is odd is left out, never the whole update
            found_one = _search_player(name, year, prow)
        except (urllib.error.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            continue
        if found_one:
            extra.append(found_one)
        time.sleep(0.05)
    _store(f"missing_{key}.json", extra)
    return extra


# --- data pack ---------------------------------------------------------------------------------
def read_pack(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def usable(pack):
    """A pack this program can read: a dict in a layout from OLDEST_FORMAT to PACK_FORMAT."""
    return isinstance(pack, dict) and isinstance(pack.get('format'), int) and OLDEST_FORMAT <= pack['format'] <= PACK_FORMAT


EQUIPMENT_FORMAT = 1


def equipment_part(pack):
    """The pack's real-equipment part (`equipment`: {'format', 'count', 'values': 'raw', 'players': [{'first', 'last',
    'birth': [y, m, d], 'pos', and, left out when at the default: 'sock', 'pants', 'neck', 'tape' ('black' | 'white'),
    'goalie'}]}, keyed like `ratings_full`) or None when the pack has none or one in a layout this program does not know."""
    part = (pack or {}).get('equipment')
    if isinstance(part, dict) and part.get('format') == EQUIPMENT_FORMAT and part.get('values') == 'raw' and part.get('players'):
        return part
    return None


SKINS_FORMAT = 1


def skins_part(pack):
    """The pack's skin groups of players (`skins`: {'format', 'players': {"<name, letters only>|<birth year>": 'brown' |
    'dark'}}, from the photos, tools/skin_tones.py) as {name: [(birth year, group)]}, or None when the pack has none or
    one in a layout this program does not know. Only the groups that differ from the game's usual light one are listed."""
    part = (pack or {}).get('skins')
    if not (isinstance(part, dict) and part.get('format') == SKINS_FORMAT and part.get('players')):
        return None
    out = {}
    for key, group in sorted(part['players'].items()):
        name, _, year = key.rpartition('|')
        if name and year.isdigit() and group in ('medium', 'brown', 'dark'):
            out.setdefault(name, []).append((int(year), group))
    return out or None


def load_pack(progress=None, offline=False, bundled=None):
    """The newest data pack available: downloaded if a newer one is published, else the cached
    download, else the copy shipped with the program. Packs made for a newer program are skipped."""
    say = progress or (lambda msg: None)
    packs = []
    cached = app_dir('cache', 'datapack.json.gz')
    url = os.environ.get('LEGACY_ROSTER_PACK_URL') or (files_url() + 'datapack.json.gz'
                                                      if os.environ.get('LEGACY_ROSTER_FILES_URL') else PACK_URL)
    if url and not offline:
        try:
            raw = http_get(url, timeout=20, retries=1)
            pack = json.loads(gzip.decompress(raw))      # make sure it is a pack before keeping it
            if usable(pack):
                with open(cached, 'wb') as f:
                    f.write(raw)
                say("Data pack: downloaded the latest")
            else:
                say("Data pack: the published one needs a newer version of this program; "
                    "download the new version to get the latest data")
        except Exception as err:                   # no connection, no release yet: use what we have
            say(f"Data pack: could not download a newer one ({err})")
    for path in (cached, bundled or BUNDLED_PACK):
        if os.path.exists(path):
            try:
                pack = read_pack(path)
            except (OSError, ValueError):
                continue
            if usable(pack):
                packs.append(pack)
    if not packs:
        raise Offline("no data pack found")
    return max(packs, key=lambda p: p.get('generated', ''))


def gather(R, steps, pack, progress=None, offline=False, fresh=False):
    """Collect everything the selected steps need into a builder.Data."""
    from . import pipeline, schedule
    season = pack.get('season', time.localtime().tm_year)
    players = []
    if pipeline.NHL in steps:
        if offline:
            teams = _cached(f"nhl_{season}.json", 10 ** 9) or pack.get('nhl')
            if not teams:
                raise Offline("NHL rosters need an internet connection")
            (progress or (lambda msg: None))(
                "Offline: using saved NHL rosters. Injured and reassigned players that the roster lists "
                "leave out are treated as having left their team.")
            players = flatten_nhl(teams)
        else:
            teams = fetch_nhl_teams(season, progress, fresh)
            players = flatten_nhl(teams)
            players = flatten_nhl(teams, find_missing(R, players, progress, fresh))
    return Data(nhl_players=players,
                ratings_list=pack.get('ratings_list') if pipeline.RATINGS in steps else None,
                ratings_full=pack.get('ratings_full') if pipeline.RATINGS in steps else None,
                iihf=pack.get('iihf') if pipeline.NATIONAL in steps else None,
                season_year=season,
                leagues={k: v for k, v in pack.get('leagues', {}).items() if k in steps},
                nhl_logos=pack.get('nhl_logos') if pipeline.NHL in steps else None,
                nhl_last=pack.get('nhl_last') if pipeline.NHL in steps else None,
                retired=pack.get('retired') if pipeline.NHL in steps else None,
                contracts=pack.get('contracts') if pipeline.NHL in steps else None,
                real_lines=pack.get('lines') if pipeline.NHL in steps else None,
                equipment=equipment_part(pack) if pipeline.NHL in steps else None,
                skins=skins_part(pack),
                club_lines=pack.get('club_lines') if any(k in steps for k in pack.get('leagues', {})) else None,
                drafts=pack.get('drafts'),
                schedule=pack.get('schedule') if pipeline.SCHEDULE in steps else None,
                league_schedules=schedule.league_schedules(pack) if pipeline.SCHEDULE in steps else None)


def load_research_dir(folder):
    """Inputs saved by the original lab scripts (work/research): {'teams', 'extra', 'ratings_list', 'iihf'}."""
    def read(name, default=None):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            return default
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    rated = sorted(n for n in os.listdir(folder) if n.endswith('ratings.json')) if os.path.isdir(folder) else []
    return {'teams': {abbr: read(f"{abbr}.json") for abbr in L.API_TO_SLOT},
            'extra': read('extra_players.json', []),
            'ratings_list': read(rated[0]) if rated else None,     # the ratings list the lab saved
            'iihf': read(os.path.join('iihf2026', 'rosters.json'))}
