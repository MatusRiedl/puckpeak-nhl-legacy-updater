"""The Calendar tab without a window toolkit: the picked team's games on a month page (Monday to Sunday), a day's
games, the team's list of games, and with the "My season" switch the results of the player's own Season or Be a GM
save (app/season.py, read only).

The roster's calendar is the NHL's (`nhlschedule`: the real 2026-27 one after an update with the calendar step, else
the game's own, which is 2015-16's) and every club league's own table (schedule.LEAGUES; the AHL's of 32 on a roster made
for the game patch: schedule.read_ahl). Norway has no table: the data pack's real games are shown. The All-Star game is
shown on its day and counted for nobody. A save's games are the save's own calendar: the playoffs, the farm league of a
Be a GM; a save of the unpatched game counts its seasons from 2015 and is shown in this program's seasons
(app/season.py `offset`).
"""
import calendar
import datetime
import threading

from .. import layout as L
from .. import schedule, seasonsave
from .season import (DAYS, MONTHS, SeasonSource, date_text, moved, place_text, record_text, season_note,
                     standing)

SLICE, OFFICE = 'calendar', 'office'
MODES = ('team', 'league')
NO_ROSTER = "Pick a roster in Setup first."
ALL_STAR = "All-Star Game"
LABELS = dict({'nhl': 'NHL', 'norway': 'Norway'}, **schedule.LEAGUE_LABELS)
OWN_NOTE = ("This roster has the game's own {league} calendar (an old season). An update with the calendar and the "
            "{league} clubs on gives this season's.")
SEASON_NOTE = "Season mode plays the {league} too: New Season > League Type."
FARM_NOTE = "On the patched game the AHL's 32 clubs are the NHL teams' farm league in Season and Be a GM."
NORWAY_NOTE = "The game has no calendar for Norway and Season mode does not offer it: these are the real games."
VEES_CLUB = "Penticton Vees"        # as the data pack's WHL calendar names them
VEES_NOTE = "The Vees' real games. They are not in the game's own WHL calendar, so Season mode does not play them."


def _dated(rows, season):
    """schedule.dated, leaving out a date the season does not have (29 February)."""
    out = []
    for row in rows:
        try:
            out += schedule.dated([row], season)
        except ValueError:
            pass
    return out


class Book:
    """The calendars of one roster (read once per Snapshot): [(date, home, away)] of the NHL's games, the All-Star
    game's [(date, home, away)] and the season they are; `leagues` {part: [(date, home, away)]} of every club league
    (Norway's from the data pack `pack`, a club without a slot by its name), `own` the parts whose table is not this
    season's (known only with the pack), `farm` True when the AHL is the patch's 32, `vees` the Penticton Vees' real games
    from the pack, which no table of the game holds ([] without the Vees)."""

    def __init__(self, R, season_year, pack=None):
        rows = schedule.read(R)
        self.season = schedule.season_of(rows, season_year)
        games, stars = schedule.split_all_star(rows)
        self.nhl, self.stars = _dated(games, self.season), _dated(stars, self.season)
        farm = schedule.read_ahl(R)
        self.farm = farm is not None
        real = schedule.league_schedules(pack or {})
        self.leagues, self.own = {}, set()
        for part, (_tag, slots) in schedule.LEAGUES.items():
            rows = farm if part == 'ahl' and self.farm else schedule.read_league(R, part)
            self.leagues[part] = _dated(rows, schedule.season_of(rows, season_year))
            games = real.get(part)
            if games is not None:
                want = sorted(games, key=lambda g: g[0]) if part == 'ahl' and self.farm else \
                    schedule.league_rows(games, set(slots))
                if rows != [(int(d[5:7]) - 1, int(d[8:10]) - 1, h, a) for d, h, a in want]:
                    self.own.add(part)
        norway = ((pack or {}).get('schedules') or {}).get('norway') or []
        self.leagues['norway'] = [(datetime.date.fromisoformat(d), h, a) for d, h, a in sorted(norway, key=lambda g: g[0])]
        slot_of = lambda club: L.VEES if club == VEES_CLUB else club
        self.vees = [(datetime.date.fromisoformat(d), slot_of(h), slot_of(a))
                     for d, h, a in sorted(real.get('whl') or [], key=lambda g: g[0])
                     if VEES_CLUB in (h, a)] if L.is_vees(R.T) else []


class CalendarController:
    def __init__(self, host, editor, season=None):
        self.host, self.editor = host, editor
        self.source = season or SeasonSource(editor)
        self.lock = threading.RLock()
        self.team = None                # the team followed (None: no team picked)
        self.shown = False
        self._month = None              # (year, month) on the page; None: today's, or the first with games
        self._day = None                # the day opened (datetime.date) or None
        self._mode = 'team'             # 'team': the team's games on the page; 'league': how many games each day
        self.clock = datetime.date.today
        self._book = (None, None)       # (Snapshot, Book)
        follow = getattr(editor, 'follow_with', None)
        if follow is not None:
            follow('calendar', self)

    def changed(self):
        self.host.changed(SLICE)

    # --- the followed team --------------------------------------------------------------------------------
    def follow(self, team):
        with self.lock:
            self.team, self.shown = team, True
            if team is None:
                self._day = None
        self.source.load(fresh=True)        # a save played meanwhile, or a roster of another version
        self.changed()

    def hide(self):
        with self.lock:
            self.shown = False

    def roster_changed(self):
        with self.lock:
            self._book = (None, None)
            self._day = None
        self.changed()

    # --- the calls ------------------------------------------------------------------------------------------
    def month(self, step):
        """The month before (step < 0) or after."""
        with self.lock:
            games = self._view()
            if games is None or games['why'] or self._month is None:
                return
            y, m = self._month
            n = y * 12 + m - 1 + (1 if step > 0 else -1)
            self._month = self._clamp((n // 12, n % 12 + 1), games['range'])
        self.changed()

    def day(self, date):
        """Open a day (an ISO date), or close it (None, or the day open)."""
        with self.lock:
            when = _date(date)
            if when is None or when == self._day:
                self._day = None
            else:
                self._day = when
                self._month = (when.year, when.month)
        self.changed()

    def today(self):
        with self.lock:
            games = self._view()
            if games is None or games['why']:
                return
            today = games['today']
            first, last = games['range']
            if first <= (today.year, today.month) <= last:
                self._month, self._day = (today.year, today.month), today
            else:
                self._month = first
        self.changed()

    def mode(self, mode):
        """'team' (the team's games on the page) or 'league' (how many games each day)."""
        with self.lock:
            if mode in MODES:
                self._mode = mode
        self.changed()

    def season(self, on):
        """The "My season" switch."""
        self.source.switch(on)
        with self.lock:
            today = self.source.today() if on else None
            if today is not None:
                self._month, self._day = (today.year, today.month), None
        self.changed()
        self.host.changed(OFFICE)          # the Front office shows the record while it is on

    # --- what is shown --------------------------------------------------------------------------------------
    def _snap(self):
        return getattr(self.editor, 'snap', None)

    def book(self):
        snap = self._snap()
        if snap is None:
            return None
        if self._book[0] is not snap:
            season_year = getattr(snap, 'season_year', None) or getattr(self.editor, 'season', None) or 2026
            pack = getattr(getattr(self.editor, 'update', None), 'pack', None)
            try:
                book = Book(snap.R, season_year, pack)
            except Exception:
                book = None
            self._book = (snap, book)
        return self._book[1]

    def part_of(self, team):
        """The calendar a slot plays in: 'nhl', a part of schedule.LEAGUES, 'norway', or None."""
        if team in L.NHL_PRIMARY:
            return 'nhl'
        for part, (_tag, slots) in schedule.LEAGUES.items():
            if team in slots:
                return part
        book = self.book()
        if team in L.AHL and book is not None and book.farm:      # Coachella Valley / Henderson on a patch roster
            return 'ahl'
        if team == L.VEES and book is not None and book.vees:     # their own games, _vees_games
            return 'whl'
        return 'norway' if team in L.NORWAY else None

    def league_of(self, team):
        """The name of a slot's league in the shown roster ('NHL', 'SHL', ...)."""
        part = self.part_of(team)
        if part is not None:
            return LABELS[part]
        snap = self._snap()
        return snap.team_league.get(team, '') if snap is not None else ''

    def _team_view(self, team):
        if isinstance(team, str):                   # a club the game has no slot for (Norway's calendar)
            return {'id': None, 'code': team.split()[0][:3].upper(), 'name': team, 'colours': ['#2c4560', '#ffffff'],
                    'league': ''}
        return team_view(self.editor, team)

    def _games(self, part):
        """The games of the calendar `part` (part_of) to show: (games, from the save) where games is
        [{'date', 'home', 'away', 'score', 'extra', 'star', 'playoffs'}], or (None, False) when there are none. A save
        has the NHL's and its farm league's."""
        season = self.source.shown() if part in ('nhl', 'ahl') else None
        if season is not None:
            tier = seasonsave.NHL if part == 'nhl' else seasonsave.FARM
            years = self.source.offset(season)
            out = []
            for g in season.games:
                if g.league != tier or (g.playoffs and g.status == seasonsave.NOT_NEEDED):
                    continue
                star = g.home == g.away or (tier == seasonsave.NHL and not {g.home, g.away} <= L.NHL_PRIMARY)
                out.append({'date': moved(g.date, years), 'home': g.home, 'away': g.away, 'score': g.score,
                            'extra': g.extra, 'star': star, 'playoffs': g.playoffs})
            if out:
                return sorted(out, key=lambda g: (g['date'], g['star'])), True
        book = self.book()
        if book is None:
            return None, False
        rows = book.nhl if part == 'nhl' else book.leagues.get(part)
        if not rows:
            return None, False
        out = [{'date': d, 'home': h, 'away': a, 'score': None, 'extra': None, 'star': False, 'playoffs': False}
               for d, h, a in rows]
        if part == 'nhl':
            out += [{'date': d, 'home': h, 'away': a, 'score': None, 'extra': None, 'star': True, 'playoffs': False}
                    for d, h, a in book.stars]
        return sorted(out, key=lambda g: (g['date'], g['star'])), False

    def _vees_games(self):
        """The WHL's games with the Vees' real ones: the only team whose list is not the roster's table."""
        games = [{'date': d, 'home': h, 'away': a, 'score': None, 'extra': None, 'star': False, 'playoffs': False}
                 for d, h, a in self.book().vees]
        return sorted((self._games('whl')[0] or []) + games, key=lambda g: g['date'])

    def _view(self):
        """What the page shows for the team followed, or None: {'team', 'league', 'games', 'mine', 'saved', 'range',
        'today', 'why'}."""
        team = self.team
        snap = self._snap()
        if snap is None or team is None:
            return None
        part = self.part_of(team)
        season = self.source.shown()
        if part is None and season is not None and any(
                g.league == seasonsave.FARM and team in (g.home, g.away) for g in season.games):
            part = 'ahl'                    # a club the save's farm league has (Coachella Valley in a patched Be a GM)
        league = LABELS[part] if part else self.league_of(team)
        out = {'team': team, 'part': part, 'league': league, 'why': None}
        if part is None:
            out['why'] = (f"{snap.team_name(team)} is in no league with a calendar"
                          + (" (on the unpatched game it is a custom team)." if team in L.AHL else "."))
            return out
        games, saved = (self._vees_games(), False) if team == L.VEES else self._games(part)
        if games is None:
            out['why'] = f"This roster has no {league} calendar."
            return out
        mine = [g for g in games if team in (g['home'], g['away']) and not g['star']]
        if not mine:
            name = snap.team_name(team)
            out['why'] = (f"{name} plays no games in this roster's calendar: the unpatched game's Season has 30 teams. "
                          f"A roster made for the game patch has its games." if team in (30, 31) and not saved else
                          f"{name} plays no games in this calendar.")
            return out
        dates = [g['date'] for g in games]
        first, last = min(dates), max(dates)
        today = (self.source.today() if saved else None) or self.clock()
        out.update(games=games, mine=mine, saved=saved, today=today,
                   range=((first.year, first.month), (last.year, last.month)))
        if self._month is None:
            self._month = (today.year, today.month)
            if not out['range'][0] <= self._month <= out['range'][1]:      # another season: today's month in this one
                autumn = first.year - (first.month < 7)
                self._month = (autumn + (today.month < 7), today.month)
        self._month = self._clamp(self._month, out['range'])
        return out

    @staticmethod
    def _clamp(month, span):
        first, last = span
        return first if month < first else last if month > last else month

    def _mine(self, g, team):
        """{'vs', 'home', 'result'} of a game of `team` as its row and day show it."""
        home = g['home'] == team
        result = None
        if g['score'] is not None:
            h, a = g['score']
            me, them = (h, a) if home else (a, h)
            result = {'text': f"{'W' if me > them else 'L'} {me}-{them}{' ' + g['extra'] if g['extra'] else ''}",
                      'tone': 'good' if me > them else 'bad'}
        return {'vs': self._team_view(g['away'] if home else g['home'])['code'], 'home': home, 'result': result}

    def snapshot(self):
        with self.lock:
            snap = self._snap()
            if snap is None or self.team is None:
                return {'team': None, 'why': NO_ROSTER}
            v = self._view()
            team = self.team
            view = self._team_view(team)
            if v is None or v['why']:
                return {'team': view, 'why': v['why'] if v else NO_ROSTER, 'season': self._season_view(False)}
            games, mine, today, saved, league = v['games'], v['mine'], v['today'], v['saved'], v['league']
            by_day = {}
            for g in games:
                by_day.setdefault(g['date'], []).append(g)
            mine_by_day = {g['date']: g for g in mine}
            y, m = self._month
            weeks = []
            for week in calendar.Calendar(0).monthdatescalendar(y, m):
                row = []
                for d in week:
                    day = by_day.get(d, [])
                    g = mine_by_day.get(d)
                    row.append({'date': d.isoformat(), 'n': d.day, 'out': d.month != m, 'today': d == today,
                                'sel': d == self._day, 'count': sum(1 for x in day if not x['star']),
                                'allstar': any(x['star'] for x in day), 'mine': self._mine(g, team) if g else None})
                weeks.append(row)
            day = None
            if self._day is not None:
                listed = sorted(by_day.get(self._day, []), key=lambda x: (team not in (x['home'], x['away']), x['star']))
                day = {'date': self._day.isoformat(),
                       'title': f"{DAYS[self._day.weekday()]} {self._day.day} {MONTHS[self._day.month - 1]}",
                       'games': [{'home': self._team_view(x['home']), 'away': self._team_view(x['away']),
                                  'mine': team in (x['home'], x['away']) and not x['star'],
                                  'score': (f"{x['score'][0]}-{x['score'][1]}{' ' + x['extra'] if x['extra'] else ''}"
                                            if x['score'] is not None else None),
                                  'label': ALL_STAR if x['star'] else 'Playoffs' if x['playoffs'] else None}
                                 for x in listed]}
            months = []
            for g in mine:
                d = g['date']
                label = MONTHS[d.month - 1]
                if not months or months[-1]['ym'] != d.strftime('%Y-%m'):
                    months.append({'label': label, 'ym': d.strftime('%Y-%m'), 'games': []})
                months[-1]['games'].append(dict(self._mine(g, team), date=d.isoformat(), label=date_text(d),
                                                sel=d == self._day, past=d < today,
                                                playoffs=g['playoffs']))
            home = sum(1 for g in mine if g['home'] == team)
            nxt = next((g for g in mine if g['date'] >= today and g['score'] is None), None)
            summary = {'gp': len(mine), 'home': home, 'away': len(mine) - home,
                       'next': (f"{date_text(nxt['date'])} {'vs' if nxt['home'] == team else '@'} "
                                f"{self._mine(nxt, team)['vs']}") if nxt else None}
            record, standings = self._record(team, v['part']) if saved else (None, None)
            per_team = {}
            for g in games:
                if not g['star'] and not g['playoffs']:
                    for t in (g['home'], g['away']):
                        per_team[t] = per_team.get(t, 0) + 1
            counts = sorted(set(per_team.values()))
            per = (f"{counts[0]}" if len(counts) == 1 else f"{counts[0]} to {counts[-1]}") if counts else '0'
            n = sum(1 for g in games if not g['star'])
            played = sum(1 for g in games if g['score'] is not None and not g['star'])
            book, part = self.book(), v['part']
            league_note = None
            if saved or book is None:
                pass
            elif team == L.VEES:
                league_note = VEES_NOTE
            elif part == 'nhl':
                if book.season == schedule.GAME_SEASON:
                    league_note = ("This roster has the game's own calendar (2015-16). An update with the calendar on "
                                   "gives the real one.")
            elif part in book.own:
                league_note = OWN_NOTE.format(league=league)
            elif part == 'norway':
                league_note = NORWAY_NOTE
            elif part == 'ahl' and book.farm:
                league_note = FARM_NOTE
            else:
                league_note = SEASON_NOTE.format(league=league)
            return {
                'team': view, 'league': league, 'month': f"{y:04d}-{m:02d}", 'title': f"{MONTHS[m - 1]} {y}",
                'can_prev': (y, m) > v['range'][0], 'can_next': (y, m) < v['range'][1], 'mode': self._mode,
                'weeks': weeks, 'day': day, 'summary': summary, 'months': months, 'record': record,
                'standings': standings, 'season': self._season_view(saved), 'league_note': league_note,
                'count_note': None if self._mode == 'team' else
                (f"{played:,} of {n:,} games played." if saved else f"{n:,} games, {per} per team."),
            }

    def _season_view(self, saved):
        src = self.source
        available = src.available()
        on = bool(src.on and available)
        return {'on': on, 'available': available, 'label': src.label() if available else None,
                'note': (season_note(src) if saved else
                         "Your save has no games of this league." if on else
                         None if available else src.note)}

    def _record(self, team, part):
        """(record, standings) of `team` in the save shown, as the Calendar's side shows them."""
        season = self.source.shown()
        if season is None:
            return None, None
        tier = seasonsave.NHL if part == 'nhl' else seasonsave.FARM
        try:
            group, row = standing(season, team, tier)
        except Exception:
            return None, None
        if row is None:
            return None, None
        record = {'text': record_text(row), 'pts': row['pts'], 'gp': row['gp'], 'place': row['place'],
                  'division': group['division'], 'place_text': f"{place_text(row['place'])} in {group['division']}"}
        return record, standings_view(group, team, self._team_view)

    def rail_numbers(self):
        """{slot: {'text', 'tip'}}: the games each team plays in its league's calendar shown."""
        with self.lock:
            snap = self._snap()
            if snap is None:
                return {}
            out = {}
            for part in ('nhl',) + tuple(schedule.LEAGUES) + ('norway',):
                games, _saved = self._games(part)
                for g in games or []:
                    if g['star']:
                        continue
                    for t in (g['home'], g['away']):
                        if isinstance(t, int):
                            out[t] = out.get(t, 0) + 1
            book = self.book()
            if book is not None and book.vees:
                out[L.VEES] = len(book.vees)
            return {t: {'text': str(n), 'tip': 'games'} for t, n in out.items()}


def team_view(editor, team):
    """{id, code, name, colours, league} of a team: the Roster editor's (EditorController.team_view), else from the
    roster."""
    fn = getattr(editor, 'team_view', None)
    if fn is not None:
        try:
            view = fn(team)
            if view:
                return view
        except Exception:
            pass
    snap = getattr(editor, 'snap', None)
    name = snap.team_name(team) if snap is not None else f"#{team}"
    code = ''
    try:
        code = str(snap.R.T.get(team, 'abbrname') or '').strip()
    except Exception:
        pass
    league = 'NHL' if team in L.NHL_PRIMARY else snap.team_league.get(team, '') if snap is not None else ''
    return {'id': team, 'code': (code or name[:3]).upper()[:4], 'name': name, 'colours': ['#2c4560', '#ffffff'],
            'league': league}


def standing_row(row, team, view):
    """A seasonsave standings row as the window shows it: {'slot', 'code', 'colours', 'place', 'gp', 'w', 'l', 'otl',
    'pts', 'mine'}; `view` gives a slot's team view."""
    v = view(row['slot'])
    return {'slot': row['slot'], 'code': v.get('code') or row['abbr'], 'colours': v.get('colours'),
            'place': row['place'], 'gp': row['gp'], 'w': row['w'], 'l': row['l'], 'otl': row['otl'], 'pts': row['pts'],
            'mine': row['slot'] == team}


def standings_view(group, team, view):
    """{'division', 'conference', 'rows'} of a seasonsave standings group, `team` marked."""
    return {'division': group['division'], 'conference': group['conference'],
            'rows': [standing_row(r, team, view) for r in group['rows']]}


def _date(text):
    if not text:
        return None
    if isinstance(text, datetime.date):
        return text
    try:
        return datetime.date.fromisoformat(str(text)[:10])
    except ValueError:
        return None
