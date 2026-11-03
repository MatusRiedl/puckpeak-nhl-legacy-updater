"""The list of changes as a page people can read: what each part of the update did, then every
change, grouped by part (NHL, a league, national teams ...) and team, one change per line, with
the teams' full names. Opened in the browser by "List of changes"; the same rows also go into a
CSV next to it for spreadsheets (pipeline.write_report)."""
import datetime
import html as markup
import re

from . import layout as L
from . import pipeline as P

# what a change is called on the page, and the order changes are listed in within a team
WORDS = {
    'moved': "traded here", 'added': "joined", 'joined': "joined", 'created': "new in the game",
    'national team: added': "added", 'signed to fill the line-up': "signed to fill the line-up",
    'called up to fill the line-up': "called up to fill the line-up",
    'left NHL roster': "left", 'left the club': "left", 'left to make room': "left (room for a new NHL player)",
    'national team: removed': "removed",
    'national team: left empty': "left empty",
    'position changed': "position", 'number changed': "number",
    'stays to fill the line-up': "stays to fill the line-up", 'skipped': "not added",
    'stays under contract': "stays (under contract)", 'farm under contract': "joined the farm (under contract)",
    'prospect pool moved': "pool moved", 'prospect pool merged': "pool merged",
    'prospect pool: moved for room': "moved for room", 'prospect pool: no room': "no room",
    'edited': "edited", 'team edited': "team edited", 'edit skipped': "edit skipped",
}
ORDER = ['moved', 'added', 'joined', 'national team: added', 'created', 'called up to fill the line-up',
         'signed to fill the line-up', 'stays to fill the line-up', 'stays under contract', 'farm under contract', 'left NHL roster', 'left the club', 'left to make room', 'national team: removed', 'position changed', 'number changed']
TOTALS = {'summary', 'Current ratings', 'Current ratings (second list)', 'contracts'}        # counts, not players: listed as totals
NHL_NAMES = {code: name for name, code in L.NHL_TEAM_NAMES.items()}

STYLE = """
:root { --bg:#f6f7f9; --card:#ffffff; --text:#1d232a; --muted:#5d6873; --line:#e2e6ea; --accent:#1593c2;
        --soft:#e8f5fb; --chip:#eef1f4; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#12171b; --card:#1a2126; --text:#e8edf1; --muted:#97a3ad; --line:#2a3238; --accent:#38b6e3;
          --soft:#16303b; --chip:#232b31; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:15px/1.5 "Segoe UI", system-ui, sans-serif; }
main { max-width: 980px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 24px; margin: 0; }
.sub { color: var(--muted); margin: 2px 0 18px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 18px; margin-bottom: 14px; }
table.sum { border-collapse: collapse; width: 100%; }
table.sum td { padding: 4px 0; vertical-align: top; border-bottom: 1px solid var(--line); }
table.sum tr:last-child td { border-bottom: 0; }
table.sum td:first-child { font-weight: 600; width: 190px; padding-right: 12px; }
input { width: 100%; padding: 9px 12px; border-radius: 10px; border: 1px solid var(--line);
        background: var(--card); color: var(--text); font: inherit; margin-bottom: 14px; }
details { background: var(--card); border: 1px solid var(--line); border-radius: 12px; margin-bottom: 12px; }
summary { cursor: pointer; padding: 12px 18px; font-weight: 700; font-size: 17px; }
summary span { font-weight: 400; color: var(--muted); font-size: 14px; margin-left: 8px; }
.part { padding: 0 18px 12px; }
h3 { font-size: 15px; margin: 14px 0 4px; color: var(--accent); }
ul { list-style: none; margin: 0; padding: 0; }
li { padding: 3px 0; border-bottom: 1px solid var(--line); display: flex; gap: 10px; flex-wrap: wrap; }
li:last-child { border-bottom: 0; }
.what { flex: 0 0 150px; color: var(--muted); }
.who { font-weight: 600; }
.num { color: var(--muted); }
.detail { color: var(--muted); }
.totals li .what { flex-basis: 260px; }
footer { color: var(--muted); font-size: 13px; margin-top: 20px; }
a { color: var(--accent); }
@media (max-width: 600px) { .what { flex-basis: 100%; } table.sum td:first-child { width: 120px; } }
"""

SCRIPT = """
document.getElementById('find').addEventListener('input', function () {
  var q = this.value.trim().toLowerCase();
  document.querySelectorAll('li[data-text]').forEach(function (li) {
    li.style.display = !q || li.dataset.text.indexOf(q) >= 0 ? '' : 'none';
  });
  document.querySelectorAll('.team').forEach(function (t) {
    var shown = Array.prototype.some.call(t.querySelectorAll('li'), function (li) { return li.style.display !== 'none'; });
    t.style.display = shown ? '' : 'none';
  });
  if (q) document.querySelectorAll('details').forEach(function (d) { d.open = true; });
});
"""


def team_names(result, leagues):
    """{part: {abbreviation: full name}}, and the names every part may fall back on ('')."""
    names = {'': {}}
    R = getattr(result.builder, 'R', None)
    if R is not None:
        for t in range(R.T.cur_rec):
            for field in ('abbrname', 'artabbr'):
                code = R.T.get(t, field)
                if code:
                    names[''].setdefault(code, R.team_name(t).replace('®', '').strip())
        for abbr, iso in L.NATIONAL_ISO.items():
            slot = next((t for t in L.NATIONAL if R.T.get(t, 'artabbr') == abbr), None)
            if slot is not None:
                names.setdefault(P.SECTION_NATIONAL, {})[iso] = R.team_name(slot)
    names[P.SECTION_NHL] = dict(NHL_NAMES)
    for key, league in (leagues or {}).items():
        part = names.setdefault(P.LEAGUE_NAMES.get(key, key), {})
        for team in league.get('teams', []):
            if team.get('abbr') and team.get('full'):
                part[team['abbr']] = team['full']
    return names


def _name(names, part, code):
    code = str(code)
    return names.get(part, {}).get(code) or names[''].get(code) or code


def _detail(names, part, row):
    detail = str(row[3] if row[3] is not None else '')
    if row[1] == 'created':
        return "a spare player record was used" if 'IIHF' not in detail else "from the IIHF roster"
    # 'from NSH' -> 'from Nashville Predators'
    return re.sub(r'\b(from|replaces|to) ([A-Z]{2,4})\b',
                  lambda m: f"{m.group(1)} {_name(names, part, m.group(2)) if part == P.SECTION_NHL else m.group(2)}",
                  detail)


def html_page(result, heading, leagues=None, csv_name=None, when=None):
    names = team_names(result, leagues)
    esc = markup.escape
    when = when or datetime.datetime.now()
    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f'<title>List of changes</title><style>{STYLE}</style></head><body><main>',
           '<h1>List of changes</h1>',
           f'<p class="sub">{esc(heading)} &middot; {when:%Y-%m-%d %H:%M}</p>']
    lines = result.lines()
    out.append('<div class="card"><table class="sum">')
    for title, text in lines or [("Result", "Nothing needed changing.")]:
        out.append(f'<tr><td>{esc(title)}</td><td>{esc(text)}</td></tr>')
    out.append('</table></div>')
    if result.problems:
        out.append('<div class="card"><b>Not saved: the new roster failed these checks</b><ul>')
        out += [f'<li>{esc(p)}</li>' for p in result.problems[:50]]
        out.append('</ul></div>')
    out.append('<input id="find" type="search" placeholder="Find a player or a team">')

    parts = {}
    for row in result.log:
        parts.setdefault(P.section_of(row), []).append(row)
    order = ([P.SECTION_STOCK, P.SECTION_NHL, P.SECTION_FREE_AGENTS, P.SECTION_RATINGS, P.SECTION_NATIONAL]
             + [P.LEAGUE_NAMES[k] for k in P.LEAGUE_ORDER]
             + [P.SECTION_POOLS, P.SECTION_EDITS, P.SECTION_PLAYER_DATA, P.SECTION_CONTRACTS, P.SECTION_REPAIRS, P.SECTION_PICTURES])
    order += sorted(k for k in parts if k not in order)
    summary = dict(lines)
    for part in order:
        rows = parts.get(part)
        if not rows:
            continue
        title = part or "Other changes"
        big = part not in (P.SECTION_NHL, P.SECTION_NATIONAL) and len(rows) > 400
        out.append(f'<details{"" if big else " open"}><summary>{esc(title)}'
                   f'<span>{esc(summary.get(part, ""))}</span></summary><div class="part">')
        totals = [r for r in rows if r[1] in TOTALS or r[0] == 'ALL']
        if totals:
            out.append('<ul class="totals">')
            for r in totals:
                out.append(f'<li><span class="what">{esc(str(r[2]))}</span><span>{esc(str(r[3]))}</span></li>')
            out.append('</ul>')
        teams = {}
        for r in rows:
            if r not in totals:
                teams.setdefault(_name(names, part, r[0]), []).append(r)
        for team in sorted(teams):
            out.append(f'<div class="team"><h3>{esc(team)}</h3><ul>')
            for r in sorted(teams[team], key=lambda r: (ORDER.index(r[1]) if r[1] in ORDER else len(ORDER),
                                                        str(r[1]), str(r[2]))):
                what = WORDS.get(r[1], str(r[1]))
                num = f'#{r[4]}' if r[4] not in (None, '', 0) else ''
                detail = _detail(names, part, r)
                text = ' '.join(str(x) for x in (team, what, r[2], num, detail)).lower()
                out.append(f'<li data-text="{esc(text)}"><span class="what">{esc(what)}</span>'
                           f'<span class="who">{esc(str(r[2]))}</span><span class="num">{esc(num)}</span>'
                           f'<span class="detail">{esc(detail)}</span></li>')
            out.append('</ul></div>')
        out.append('</div></details>')
    if csv_name:
        out.append(f'<footer>The same changes as a table for a spreadsheet: <a href="{esc(csv_name)}">'
                   f'{esc(csv_name)}</a></footer>')
    out.append(f'<script>{SCRIPT}</script></main></body></html>')
    return '\n'.join(out)


def html(result, heading, leagues=None, csv_name=None):
    """The page for a pipeline.BuildResult (pipeline.write_report)."""
    return html_page(result, heading, leagues, csv_name)
