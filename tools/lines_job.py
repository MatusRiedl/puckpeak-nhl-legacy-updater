"""Keep the data pack's lines fresh on the program's file server (docs/notes/lines-job.md; owner, 2026-11-09: every day,
published by itself when every guard passes; AGENTS.md rule 6).

    python tools/lines_job.py once --pack FILE [--out FILE] [--dry-run] [--archive DIR]   one run
    python tools/lines_job.py serve --pack FILE --at 10:00 [--archive DIR]               every day at that time (UTC)

Both games read one data pack (Legacy: datasource.load_pack; NHL 19: the same address) and its parts `lines` (the NHL
teams, by NHL.com id) and `club_lines` (the clubs, by name). A run fetches what build_datapack.py's `--refresh lines` and
`--refresh extraliga_lines` fetch, lays it into the pack and writes the pack back:
  * `lines`: each NHL team's announced lines with the categories they lack from its last games (fetch_nhl); a category
    neither gives whole stays the pack's older one (with_older); a team whose fetch failed or whose lines name a player
    twice keeps the pack's entry, and one the games gave no captains keeps the pack's letters (lay_nhl, which
    build_datapack.py's `--refresh lines` runs too);
  * `club_lines`: each Extraliga club's newest match line-up over its even strength and goalies, laid over the pack's own
    entry the way hokejcz_lines.merge does (the special teams stay the larger database's); every other club is left as
    it is. The clubs' captains live in the league rosters and are not touched;
  * `generated` is now and the two parts' dates today; `format` and `season` never change (a newer format is refused
    by older programs, another season by NHL 19's reader).
The pack is replaced only when `guards` finds nothing: the format and season, no part that shrank by more than 40 %,
enough NHL teams with whole even strength, the announced lines not gone (a changed page layout looks like that), and no
word tools/clean_check.py refuses. The pack before is kept as `<pack>.prev`, every published pack in `--archive` (the
newest KEEP_RUNS), and the last run's result in `<archive>/status.json`. Standard library only (the server's container,
deploy/lines/).
"""
import argparse
import datetime
import json
import os
import shutil
import signal
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
for _p in (ROOT, TOOLS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from legacy_roster import datasource  # noqa: E402
from providers import dailyfaceoff, hokejcz_lines, nhl_lines  # noqa: E402
import clean_check  # noqa: E402

SLOTS = os.path.join(ROOT, 'tools', 'club_slots.json')
MAX_DROP = 0.4               # as build_datapack.MAX_DROP: a part that loses more of its entries is a broken feed
MIN_FULL_TEAMS = 28          # NHL teams with whole even strength and goalies (the 2026-11-05 pack: 30)
ANNOUNCED_SHARE = 0.6        # announced even strength on fewer teams than this share of the pack's: the page changed
KEEP_RUNS = 8                # published packs kept in the archive
RETRY_AFTER = 3600           # seconds before the one retry of a run that published nothing
EVEN = tuple(f"l{n}{s}" for n in (1, 2, 3, 4) for s in ('lw', 'c', 'rw')) + \
    tuple(f"l{n}{s}" for n in (1, 2, 3) for s in ('ld', 'rd')) + ('g1', 'g2')


def log(msg):
    print(f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


# --- fetching (build_datapack.py runs the same two) ----------------------------------------------------------------------
def fetch_nhl(season, say=log):
    """{team code: {'date', 'source', 'games', 'slots', 'letters'}}: the announced lines with what they lack from the
    team's last games (providers/dailyfaceoff.py, nhl_lines.py)."""
    return dailyfaceoff.merge(dailyfaceoff.lines(season, log=say), nhl_lines.lines(season, log=say))


def fetch_extraliga(season, say=log, today=None):
    """{club slot: {'date', 'game', 'games', 'slots', 'letters'}}: the Extraliga clubs' newest match line-ups
    (providers/hokejcz_lines.py)."""
    return hokejcz_lines.lines(season, SLOTS, today, say)


# --- laying it into the pack ---------------------------------------------------------------------------------------------
def twice(slots):
    """The first player an entry names twice at even strength or in goal (None when none)."""
    seen = set()
    for name in EVEN:
        who = slots.get(name)
        if who is None:
            continue
        key = tuple(who) if isinstance(who, list) else who
        if key in seen:
            return who
        seen.add(key)
    return None


def whole(entry):
    """An NHL entry with all four lines, three pairs and two goalies."""
    return all((entry or {}).get('slots', {}).get(name) is not None for name in EVEN)


def announced(entry):
    return 'l:announced' in ((entry or {}).get('source') or '')


def with_older(entry, old):
    """(entry, prefixes): a fetched NHL entry with every category it lacks a whole of (even strength, goalies, power play,
    penalty kill: dailyfaceoff.CATEGORIES) taken from the pack's `old` entry when that one has it whole, marked
    '<prefix>:older' in the source. The game drops a group naming a player who left, so an older group is never worse
    than none (2026-11-09: New Jersey's and Tampa's announced lines named a player NHL.com's roster lacked and their last
    games gave no whole even strength)."""
    slots, mine, older = dict(entry['slots']), (old or {}).get('slots') or {}, []
    for prefix, size in dailyfaceoff.CATEGORIES.items():
        have = sum(1 for k in slots if k.startswith(prefix))
        theirs = {k: v for k, v in mine.items() if k.startswith(prefix)}
        if have < size and len(theirs) == size:
            slots = {k: v for k, v in slots.items() if not k.startswith(prefix)}
            slots.update(theirs)
            older.append(prefix)
    if not older:
        return entry, []
    source = ' '.join([entry.get('source') or ''] + [f"{p}:older" for p in older]).strip()
    return dict(entry, slots=slots, source=source), older


def lay_nhl(old_lines, nhl, letters=True):
    """(lines, report): the fetched NHL entries laid over the pack's `old_lines`; build_datapack.py's `--refresh lines`
    runs the same. A team with nothing fetched, or whose lines name a player twice, keeps its old entry; a category the
    fetch lacks whole comes from the old entry (with_older); with `letters`, a team the games gave no captains keeps its
    old letters (build_datapack.py gives those from the larger database instead). Teams not fetched stay as they were."""
    old_lines = old_lines or {}
    lines = dict(old_lines)
    report = {'nhl': [], 'nhl_kept': {}, 'nhl_older': {}}
    for code, entry in sorted(nhl.items()):
        if not entry.get('slots'):
            report['nhl_kept'][code] = "no lines fetched"
            continue
        entry, older = with_older(entry, old_lines.get(code))
        if older:
            report['nhl_older'][code] = older
        dup = twice(entry['slots'])
        if dup is not None:
            report['nhl_kept'][code] = f"names player {dup} twice"
            continue
        if letters and not entry.get('letters') and (old_lines.get(code) or {}).get('letters'):
            entry = dict(entry, letters=old_lines[code]['letters'])
        lines[code] = entry
        report['nhl'].append(code)
    return lines, report


def refresh(pack, nhl, extraliga, when=None):
    """(new pack, report): `pack` with the fetched lines laid in (the module's notes). `pack` itself is not changed."""
    when = when or now_utc()
    today = f"{when:%Y-%m-%d}"
    new = dict(pack)
    old_clubs = pack.get('club_lines') or {}
    clubs = dict(old_clubs)
    lines, report = lay_nhl(pack.get('lines'), nhl)
    report.update(extraliga=[], extraliga_kept={})
    for slot, entry in sorted(extraliga.items(), key=lambda kv: int(kv[0])):
        base = old_clubs.get(slot)
        merged = hokejcz_lines.merge({slot: base} if base else {}, {slot: entry})[slot]
        dup = twice(merged['slots'])
        if dup is not None:
            report['extraliga_kept'][slot] = f"names {' '.join(map(str, dup))} twice"
            continue
        clubs[slot] = merged
        report['extraliga'].append(slot)
    new['lines'], new['club_lines'] = lines, clubs
    sources = {k: dict(v) for k, v in (pack.get('sources') or {}).items()}
    if report['nhl'] and 'lines' in sources:
        sources['lines'].update(date=today, count=len(lines))
    if report['extraliga'] and 'club_lines' in sources:
        sources['club_lines'].update(date=today, count=len(clubs))
    new['sources'] = sources
    new['generated'] = f"{when:%Y-%m-%dT%H:%M:%SZ}"
    return new, report


def guards(old, new):
    """Every reason not to publish `new` in place of `old` (an empty list: publish)."""
    problems = []
    for key in ('format', 'season'):
        if new.get(key) != old.get(key):
            problems.append(f"{key} {new.get(key)!r}, the published pack has {old.get(key)!r}")
    if not datasource.usable(new):
        problems.append("the programs could not read this pack")
    for key, src in (old.get('sources') or {}).items():
        now = (new.get('sources') or {}).get(key)
        if now is None:
            problems.append(f"{key}: in the published pack, missing now")
        elif src.get('count') and now.get('count', 0) < (1 - MAX_DROP) * src['count']:
            problems.append(f"{key}: {now.get('count')} entries, the published pack has {src['count']}")
    lines, before = new.get('lines') or {}, old.get('lines') or {}
    full, had = sum(map(whole, lines.values())), sum(map(whole, before.values()))
    if full < min(MIN_FULL_TEAMS, had):
        problems.append(f"lines: {full} NHL teams with whole even strength and goalies, the published pack has {had}")
    said, was = sum(map(announced, lines.values())), sum(map(announced, before.values()))
    if said < ANNOUNCED_SHARE * was:
        problems.append(f"lines: {said} NHL teams with announced even strength, the published pack has {was} "
                        "(the announced lines' page may have changed)")
    hits = clean_check.pack_hits(json.dumps(new, ensure_ascii=False))
    problems += [f"a word that must not ship: {h}" for h in hits[:5]]
    return problems


def take_newer(local, server, when=None):
    """(pack, taken): the maintainer's `local` pack with every NHL team's `lines` entry and every club's `club_lines` entry
    the `server`'s pack has with a later date (this job wrote it since the local pack was built), so a publish never sends
    older lines (tools/publish_packs.py). `taken` names them; when it is empty, `pack` is `local` itself."""
    taken, out = [], dict(local)
    for part in ('lines', 'club_lines'):
        mine, theirs = dict(local.get(part) or {}), server.get(part) or {}
        for key, entry in sorted(theirs.items()):
            if (entry or {}).get('date', '') > ((mine.get(key) or {}).get('date') or ''):
                mine[key] = entry
                taken.append(f"{part}:{key}")
        out[part] = mine
    if not taken:
        return local, []
    sources = {k: dict(v) for k, v in (local.get('sources') or {}).items()}
    for part in ('lines', 'club_lines'):
        theirs = (server.get('sources') or {}).get(part) or {}
        if part in sources and theirs.get('date', '') > sources[part].get('date', ''):
            sources[part].update(date=theirs['date'], count=len(out[part]))
    out['sources'] = sources
    out['generated'] = f"{(when or now_utc()):%Y-%m-%dT%H:%M:%SZ}"   # newer than the server's: the players take it
    return out, taken


# --- writing -------------------------------------------------------------------------------------------------------------
def write_pack(path, pack, keep_prev=True):
    """Replace the pack at `path` in one step (a player's download sees the old file or the new one, never half of one);
    the one before stays as `<path>.prev`."""
    data = datasource.pack_bytes(pack)
    tmp = path + '.lines-tmp'                   # publish_packs.py sends its own pack as .tmp
    with open(tmp, 'wb') as f:
        f.write(data)
    try:
        if not datasource.usable(datasource.read_pack(tmp)):
            raise ValueError("the written pack does not read back")
        if keep_prev and os.path.exists(path):
            shutil.copyfile(path, path + '.prev')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return len(data)


def archive_pack(folder, path, generated):
    """A copy of the published pack in `folder`; the newest KEEP_RUNS stay."""
    os.makedirs(folder, exist_ok=True)
    stamp = generated.replace('-', '').replace(':', '')
    shutil.copyfile(path, os.path.join(folder, f"datapack-{stamp}.json.gz"))
    kept = sorted(n for n in os.listdir(folder) if n.startswith('datapack-') and n.endswith('.json.gz'))
    for name in kept[:-KEEP_RUNS]:
        os.remove(os.path.join(folder, name))


def write_status(folder, status):
    if not folder:
        return
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, 'status.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=1, sort_keys=True)
    os.replace(tmp, os.path.join(folder, 'status.json'))


def run_once(pack_path, out=None, dry_run=False, archive=None, fetch=None, when=None):
    """One run. Returns 'published', 'unchanged', 'refused' (a guard), or 'failed' (the sources or the file).
    `fetch(season) -> (nhl, extraliga)` replaces the web (tests)."""
    status = {'run': f"{now_utc():%Y-%m-%dT%H:%M:%SZ}", 'pack': pack_path}
    try:
        old = datasource.read_pack(pack_path)
        season = old['season']
        if fetch:
            nhl, extraliga = fetch(season)
        else:
            nhl = fetch_nhl(season)
            try:
                extraliga = fetch_extraliga(season)
            except Exception as err:            # the Extraliga's files are unofficial: the NHL goes out without them
                log(f"extraliga: {err}")
                extraliga = {}
        if not nhl:
            raise RuntimeError("no NHL lines could be fetched")
        new, report = refresh(old, nhl, extraliga, when)
        status.update(nhl=len(report['nhl']), nhl_kept=report['nhl_kept'], extraliga=len(report['extraliga']),
                      extraliga_kept=report['extraliga_kept'])
        status['nhl_older'] = report['nhl_older']
        log(f"NHL: {len(report['nhl'])} teams fetched" + "".join(f"; {c} kept ({why})" for c, why in report['nhl_kept'].items())
            + "".join(f"; {c} older {'/'.join(p)}" for c, p in report['nhl_older'].items()))
        log(f"Extraliga: {len(report['extraliga'])} clubs fetched"
            + "".join(f"; {s} kept ({why})" for s, why in report['extraliga_kept'].items()))
        if new.get('lines') == old.get('lines') and new.get('club_lines') == old.get('club_lines'):
            status['result'] = 'unchanged'
            log("nothing new: the pack stays as it is")
            return 'unchanged'
        problems = guards(old, new)
        if problems:
            status.update(result='refused', problems=problems)
            log("not published:\n   " + "\n   ".join(problems))
            return 'refused'
        target = out or pack_path
        if dry_run and not out:
            status['result'] = 'dry run'
            log("dry run: every guard passed, nothing written")
            return 'published'
        size = write_pack(target, new, keep_prev=not dry_run)
        status.update(result='dry run' if dry_run else 'published', generated=new['generated'], bytes=size, written=target)
        if archive and not dry_run:
            archive_pack(archive, target, new['generated'])
        log(f"{'written' if dry_run else 'published'}: {target}, {size / 1024:.0f} KB, generated {new['generated']}")
        return 'published'
    except Exception as err:                    # a run never stops the service: the pack stays, tomorrow comes
        status.update(result='failed', problems=[f"{type(err).__name__}: {err}"])
        log(f"failed: {err}\n{traceback.format_exc()}")
        return 'failed'
    finally:
        write_status(archive, status)


def next_run(now, at):
    """The next `at` ('HH:MM', UTC) after `now`."""
    hour, minute = (int(x) for x in at.split(':'))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target if target > now else target + datetime.timedelta(days=1)


def serve(pack_path, at, archive=None):
    """Every day at `at` (UTC): run_once, and once more RETRY_AFTER later when it published nothing for a reason."""
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))       # docker stop
    log(f"lines job: {pack_path}, every day at {at} UTC")
    while True:
        target = next_run(now_utc(), at)
        log(f"next run {target:%Y-%m-%d %H:%M} UTC")
        while (wait := (target - now_utc()).total_seconds()) > 0:
            time.sleep(min(wait, 600))
        if run_once(pack_path, archive=archive) in ('refused', 'failed'):
            time.sleep(RETRY_AFTER)
            run_once(pack_path, archive=archive)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('command', choices=('once', 'serve'))
    ap.add_argument('--pack', required=True, help="the published data pack (datapack.json.gz)")
    ap.add_argument('--out', help="once: write the new pack here instead (the published one is left alone)")
    ap.add_argument('--dry-run', action='store_true', help="once: fetch and check, write only to --out")
    ap.add_argument('--at', default='10:00', help="serve: the time of day, UTC (default 10:00)")
    ap.add_argument('--archive', help="keep the published packs and status.json here")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors='backslashreplace')
    if args.command == 'serve':
        next_run(now_utc(), args.at)                            # a bad --at stops here, not at midnight
        serve(args.pack, args.at, args.archive)
    result = run_once(args.pack, out=args.out, dry_run=args.dry_run, archive=args.archive)
    return 0 if result in ('published', 'unchanged') else 1


if __name__ == '__main__':
    sys.exit(main())
