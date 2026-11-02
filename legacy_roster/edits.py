"""The player's own edits: kept on the PC and applied on top of every roster this program builds.

The roster editor (gui) stores what the player changed by hand; `pipeline.build()` applies it as
its last step, after the downloaded data, so a correction survives every later update. Edits are
about people, not records: each one names a player by plain name and birthdate (`person_key`), so
it finds him in any later roster whichever record he has there.

    edits.json  {"version": 1, "players": {who: edit}, "teams": {slot: team edit}}
    team edit   {"full", "city", "abbr", "logo": "file:<path>",
                 "equipment": {"tape": 1, "sock_tuck": 3, ...},   for every skater of the team, except what he chose himself
                 "uniforms": {"colours": {"primary": "#rrggbb", "secondary": "#rrggbb", "crest": "file:<path>"},
                              "versions": {"<variant>": "game" | "colours" | "file:<path of a 1024 x 1024 colour map>"}},
                 "ice": {"use": "game" | "logo" | "file:<path>", "arena": "<name on the ice>"},   (apply_teams;
                 the jerseys and the ice are installed by art/looks.py with the photos and logos; on a team whose
                 home ice other teams share (looks.ice_group) it is the group's)
                 "kit": {"jersey": [home, away] (0-8), "pants": 0-5, "socks": 0-5, "font": 0-5,   a custom team's look
                         "colours": ["#rrggbb"] * 3,        (slots 222-251, custom_kit.py; only what the player set):
                         "pieces": {"<piece>/<1 home | 2 away>": ["#rrggbb" per zone]},   team colours paint every
                         "crest": "logo:<n>" | "file:<path>"},     piece, then the pieces set one by one
                                                            (custom_kit.PIECES); a crest picture is installed
                                                            with the photos (art/crests.py)
                 "lines": {"slots": {"l1c": who, ...  all 71 (schema.SLOT_TAG)}, "letters": {who: "C" | "A"}},
                 "strategy": {"oz_forecheck": 2, "forward1_bias1": 6, ...}}   (strategy.FIELDS; only the changed ones)
    edit        {"label": "Connor McDavid",              shown in the editor's list
                 "was": {"first", "last", "birth"},         his name before a rename (see restore())
                 "set": {"first", "last", "num", "pos" (C/L/R/D/G), "shoots" (L/R),
                         "birth": [y, m, d], "country" (ISO3), "height_in", "weight_lb",
                         "style": 7,                    player type (ratings.STYLE_CHOICES of his position)
                         "head": 60012, "skin": 2, "eyes": 2},   his face (faces.py; the hair comes with the head)
                 "look": {"shape": 5, "tone": 8, "hair": 3, ...},   a created look (the game's Create Player "Custom
                                                            Head", faces.LOOK, the game's numbers): only a new player
                                                            gets one, on a record the game's Create Player fills
                                                            (faces.RESERVED); it replaces `set` head / skin / eyes
                 "ratings": {"Passing": 90, ...},           the ratings list's attribute names (schema.LIST_SKATER / LIST_GOALIE)
                 "ovr": 75,                                 a new player without ratings: all attributes at this level
                 "team": <slot> or "FA",                    move, sign or release
                 "equipment": {"stick": 105, "tape": 1, ...},  skaters: equipment.CHOICES, goalies: equipment.GOALIE_CHOICES
                                                            (the game's own model numbers)
                 "mask_picture": "file:<path>",             a goalie's own picture on his mask (512 x 512)
                 "photo": "file:<path>",                    a picture of the player's own
                 "contract": {"cap": 12500000, "years": 2,  his contract in real dollars (both money scales: the
                              "two_way": 0 | 1,             roster's scale is applied when it is written), the cap hit
                              "ext": [years, cap, two_way] | null},   per season; written after the real deals
                                                            (apply_contracts), on an NHL roster or to a player whose
                                                            rights an NHL team holds (contracts.edit_problems)
                 "new": true}                               a player the game does not have: created

Rules the game enforces are kept: at most 40 a team, numbers unique on a team, goalies stay
goalies, a new player needs a spare record. What cannot be done is skipped and written to the
report ("edit skipped: ..."), never half done. `verify()` still checks the result.
"""
import json
import os
from collections import Counter

from . import contracts, custom_kit, datasource, equipment, faces, lines, ratings, stock
from . import layout as L
from .art.portraits import person_key
from .schema import LIST_GOALIE, LIST_SKATER, RATING_BASE

VERSION = 1
POSITIONS = ('C', 'L', 'R', 'D', 'G')


def path():
    return datasource.app_dir('edits.json')


def _load_all(file=None):
    try:
        with open(file or path(), encoding='utf-8') as f:
            data = json.load(f)
        return data if data.get('version') == VERSION else {}
    except (OSError, ValueError, AttributeError):
        return {}


def load(file=None):
    """The player edits: {who: edit}."""
    return _load_all(file).get('players', {})


def load_teams(file=None):
    """The team edits: {slot (as text): {"full", "city", "abbr", "logo": "file:<path>"}}."""
    return _load_all(file).get('teams', {})


def save(players=None, file=None, teams=None):
    """Store the edits; the part not given (players or teams) stays as it was."""
    target = file or path()
    data = _load_all(target)
    out = {'version': VERSION, 'players': data.get('players', {}) if players is None else players,
           'teams': data.get('teams', {}) if teams is None else teams}
    tmp = target + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, target)


def keep_picture(source):
    """A copy of a picture the player chose, kept with the program's files (the original may be
    moved or deleted later). Returns the 'file:' link edits and photos use."""
    import hashlib
    import shutil
    with open(source, 'rb') as f:
        digest = hashlib.sha1(f.read()).hexdigest()[:16]
    target = datasource.app_dir('art', 'mine', digest + os.path.splitext(source)[1].lower())
    if not os.path.exists(target):
        shutil.copyfile(source, target)
    return 'file:' + target


def apply_teams(b, teams, say=None):
    """The player's own team names and logos (Roster editor). The menus show the names through
    the game's text file, written with photos and logos (art/portraits.names, loc.py)."""
    T = b.R.T
    for key in sorted(teams, key=int):
        slot, e = int(key), teams[key]
        if not 0 <= slot < T.cur_rec:
            continue
        team_name(b, slot, e)
        if e.get('logo'):
            b.logos[slot] = e['logo']
            b.own_logos.add(slot)
        if e.get('equipment'):
            _team_equipment(b, slot, e['equipment'])
        if e.get('uniforms') or e.get('ice'):
            b.looks_edits[slot] = {k: e[k] for k in ('uniforms', 'ice') if e.get(k)}
            _team_colours_arena(b, slot, e)
        if e.get('kit') and custom_kit.is_custom(slot):
            _team_kit(b, slot, e['kit'], keep_logo=bool(e.get('logo')))
        if e.get('strategy'):
            _team_strategy(b, slot, e['strategy'])
        if e.get('lines'):
            _team_lines(b, slot, e['lines'])
        b.log.append(['edits', 'team edited', b.R.team_name(slot), ', '.join(sorted(e)), ''])
    if teams and say:
        say(f"My edits: {len(teams)} teams")


def team_name(b, slot, e):
    """The name, city and short code the player gave a team, into the roster."""
    T = b.R.T
    for field, part in (('fullname', 'full'), ('shortname', 'city'), ('abbrname', 'abbr')):
        if e.get(part):
            limit = T.field(field).bits // 8 - 1
            text = e[part]
            while len(text.encode('utf-8')) > limit:
                text = text[:-1]
            if field == 'shortname':
                L.set_city(T, slot, text)       # a custom team's city is a key (layout.city_key)
            else:
                T.set(slot, field, text)
    if any(e.get(p) for p in ('full', 'city', 'abbr')):
        b.team_names[slot] = True


def _team_colours_arena(b, slot, e):
    """The colours and the arena name the player gave a team in the Jerseys & ice tab, into the roster (the game's menus,
    sticks and gear read them there): the two team colours (`ttOk`) and the arena name on the team's own arena row. The
    pictures take the same values from `b.looks_edits`. A team whose arena needs a row of its own while the table is full
    keeps its name (the list of changes says so)."""
    T = b.R.T
    given = ((e.get('uniforms') or {}).get('colours') or {})
    for kind in ('primary', 'secondary'):
        colour = custom_kit.rgb(given.get(kind))
        if colour:
            for channel, value in zip('rgb', colour):
                T.set(slot, f"{kind}color_{channel}", value)
    name = ((e.get('ice') or {}).get('arena') or '').strip()
    if name:
        limit = b.R.f['OEtS'].field('arenaname').bits // 8 - 1
        while len(name.encode('utf-8')) > limit:
            name = name[:-1]
        if b.set_arena(slot, name, alone=True) is False:
            b.log.append(['edits', 'arena not changed', b.R.team_name(slot), "the arena table has no room for its own row", ''])


def _team_kit(b, slot, kit, keep_logo=False):
    """A custom team's look (custom_kit.write): designs, colours, crest. A crest picture is installed with the photos
    (art/crests.py) on a create-a-team logo no other team wears, and is the team's menu logo unless the player gave it
    one (`keep_logo`)."""
    own, T = L.OWN_ART.get(slot), b.R.T
    # logos another team's own crest is drawn on (Coachella Valley's, Henderson's, a crest picture given earlier)
    reserved = {custom_kit.logo_of(art) for s, art in L.OWN_ART.items() if s != slot}
    reserved |= {custom_kit.logo_of(T.get(s, 'artid')) for s in b.crest_pictures if s != slot}
    words, picture = custom_kit.write(b.R, slot, kit, reserved=reserved, own_art=own)
    crest = str(kit.get('crest') or '')
    if picture:
        b.crest_pictures[slot] = picture
        if not keep_logo:
            b.logos[slot] = picture
    elif crest.startswith('file:'):
        b.log.append(['edits', 'edit skipped', b.R.team_name(slot), "crest picture: every create-a-team logo is taken",
                      ''])
    elif crest.startswith('logo:') and "crest" not in words:
        b.log.append(['edits', 'edit skipped', b.R.team_name(slot), "crest: another team's own crest is drawn on it",
                      ''])
    if words:
        b.log.append(['edits', 'team look', b.R.team_name(slot), ', '.join(words), ''])


def birth_of(P, prow, base=1910):
    """A record's birthdate. `base` 1900: the game's own roster before stock.prepare moved its
    birth years to this program's convention."""
    return (P.get(prow, 'dnFq') + base, P.get(prow, 'pLKJ') + 1, P.get(prow, 'iwsK') + 1)


def who_of(P, prow, base=1910):
    """The person key of a player record (what an edit names him by)."""
    return person_key(P.get(prow, 'PedH'), P.get(prow, 'RMbQ'), birth_of(P, prow, base))


def people(b):
    """person key -> player row, for everyone on a team or on the free-agent list. A person with
    two records (national-team goalies) is found by the one on a club team."""
    return people_and_copies(b)[0]


def people_and_copies(b):
    """(people(b), person key -> the player's other records): a person on a club and a national team
    (23 goalies, Binnington) has a record for each, and an edit has to reach both."""
    R, P = b.R, b.P
    live = b.live_entries()
    fa = {R.link_to_pid.get(l) for l in b.fa_links}
    rank = {}
    for pid, ents in live.items():
        prow = R.p_by_id.get(pid)
        if prow is None or not ents:
            continue
        club = any(b.U.get(e, 'BSXd') not in L.NATIONAL for e in ents)
        rank[prow] = 0 if club else 1
    for pid in fa:
        prow = R.p_by_id.get(pid)
        if prow is not None:
            rank.setdefault(prow, 0)
    out, copies = {}, {}
    for prow in sorted(rank, key=lambda r: (rank[r], r)):
        who = who_of(P, prow, stock.birth_base(R))
        if who in out:
            copies.setdefault(who, []).append(prow)
        else:
            out[who] = prow
    return out, copies


def records_needed(b, edits):
    """{position code: count} of the player's new players who are not in the roster yet: Builder.hold_records takes
    their records before the leagues', so a full update does not use them up. On a second run the players are there
    and need none; the leagues then find the same records left as on the first run. A new player with a created look
    takes one of the game's Create Player records instead (no league ever does), while they last (_look_records)."""
    found = people(b)
    free = _look_records(b)
    left = {kind: len(rows) for kind, rows in free.items()}
    out = Counter()
    for who in sorted(edits or {}):
        e = edits[who]
        if e.get('new') and who not in found:
            pos = L.POS_CODE.get((e.get('set') or {}).get('pos') or 'C', 0)
            if e.get('look') and left[pos == 4]:
                left[pos == 4] -= 1
                continue
            out[pos] += 1
    return out


def _look_records(b):
    """{goalie?: [free Create Player records this program may take, the highest game id first]} (faces.free_reserved),
    worked out once per build: no league step takes or frees one."""
    if not hasattr(b, 'look_records'):
        b.look_records = {kind: faces.free_reserved(b.R, kind) for kind in (False, True)}
    return b.look_records


def restore(R, edits):
    """Before an update: players the player renamed (or gave another birthdate) get their original
    name back, so the downloaded data still recognises them; `apply()` renames them again at the
    end. Without this a renamed NHL player would look new to the update and be created twice."""
    P = R.P
    base = stock.birth_base(R)
    index = {}
    for prow in range(P.cur_rec):
        index.setdefault(who_of(P, prow, base), []).append(prow)
    for who in sorted(edits):
        e = edits[who]
        was, now = e.get('was'), e.get('set') or {}
        if not was or not was.get('birth') or not was.get('first') or not was.get('last') \
                or not any(now.get(k) for k in ('first', 'last', 'birth')):
            continue
        edited = person_key(now.get('first') or was['first'], now.get('last') or was['last'],
                            now.get('birth') or was['birth'])
        if edited == who:
            continue
        for prow in index.get(edited, []):
            P.set(prow, 'PedH', was['first'])
            P.set(prow, 'RMbQ', was['last'])
            y, m, d = was['birth']
            P.set(prow, 'dnFq', y - base)
            P.set(prow, 'pLKJ', m - 1)
            P.set(prow, 'iwsK', d - 1)


def apply(b, edits, say=None):
    """Apply the player's edits to a roster being built. Returns the teams whose players changed."""
    say = say or (lambda msg: None)
    if not edits:
        return set()
    found, copies = people_and_copies(b)
    changed = set()
    done = skipped = 0
    b.edited = (set(edits), set())     # who the edits name and the records they changed (verify lets them differ)
    for who in sorted(edits):
        e = edits[who]
        label = e.get('label') or who
        prow = found.get(who)
        if prow is None and e.get('new'):
            prow = _create(b, who, e)
            if prow is None:
                b.log.append(['edits', 'edit skipped', label, 'no spare player record left for a new player', ''])
                skipped += 1
                continue
            found[who] = prow
            changed |= _teams_of(b, prow)
        if prow is None:
            b.log.append(['edits', 'edit skipped', label, 'player not found in this roster', ''])
            skipped += 1
            continue
        b.edited[1].add(prow)
        if e.get('photo'):                  # a picture of the player's own: always installed (portraits.plan own_only)
            b.photos[prow] = e['photo']
            b.own_photos.add(prow)
        fields = e.get('set') or {}
        if e.get('look'):           # the look's head, skin and eyes win
            fields = {k: v for k, v in fields.items() if k not in faces.FIELDS}
        problems = _set_fields(b, prow, fields, changed)
        if e.get('look'):
            problems += _set_look(b, prow, e['look'])
        _set_ratings(b, prow, e.get('ratings') or {}, e.get('ovr') if e.get('new') else None, bool(e.get('new')))
        problems += _set_equipment(b, prow, e.get('equipment'))
        for other in copies.get(who, []):          # the same person's national-team record: same name, same ratings
            b.edited[1].add(other)
            _set_fields(b, other, {k: v for k, v in (e.get('set') or {}).items() if k not in ('pos', 'num')}, set())
            _set_ratings(b, other, e.get('ratings') or {})
            _set_equipment(b, other, e.get('equipment'))
        if e.get('mask_picture'):
            problems += _mask_picture(b, [prow] + list(copies.get(who, [])), e['mask_picture'])
        if 'team' in e:
            problems += _move(b, prow, e['team'], changed, wins=not e.get('new') or bool((e.get('set') or {}).get('num')))
            if e.get('new') and e['team'] not in (None, 'FA'):
                changed.add(int(e['team']))     # dealt into the lines on every run, so a second run deals the same
        for text in problems:
            b.log.append(['edits', 'edit skipped', label, text, ''])
        parts = sorted(k for k in e if k not in ('label', 'contract'))      # the contract: apply_contracts
        if parts:
            b.log.append(['edits', 'edited', label, ', '.join(parts), ''])
            done += 1
    for rows in b.held_records.values():   # held for a new player who did not need one after all: left as it was
        b.created.difference_update(rows)
    b.held_records = {}
    _relines(b, changed, say)
    if done or skipped:
        say(f"My edits: {done} applied" + (f", {skipped} skipped (see the report)" if skipped else ""))
    return changed


def apply_contracts(b, edits, say=None):
    """The contracts the player set ("contract", real dollars), written on the roster's money scale (`b.money`). It runs
    after the real and the starter deals (Builder.real_contracts / starter_contracts would write over them,
    pipeline.build), so a second run writes the same. The deal is with his NHL organisation or else his club
    (contracts.contract_home; free amounts outside the NHL organisations); one the game cannot hold
    (contracts.edit_problems) or a player on no club and with no NHL organisation is left out and named in the report.
    His rights stay as they are. Returns {player row: deal} of those written (verify checks them)."""
    say = say or (lambda msg: None)
    wanted = {who: e for who, e in sorted(edits.items()) if e.get('contract')}
    if not wanted:
        return {}
    found = people(b)
    clubs = contracts.contract_clubs(b.R)
    written = {}
    for who, e in wanted.items():
        label, deal = e.get('label') or who, dict(e['contract'])
        prow = found.get(who)
        teams = _teams_of(b, prow) if prow is not None else set()
        home = contracts.contract_home(b.P, prow, teams, clubs) if prow is not None else None
        why = (["player not found in this roster"] if prow is None else
               ["contract: he is on no club and with no NHL organisation (a free agent, a national team only)"]
               if home is None else [f"contract: {text}" for text in contracts.edit_problems(deal, nhl=home[1])])
        if why:
            b.log.append(['edits', 'edit skipped', label, '; '.join(why), ''])
            continue
        if b.P.get(prow, 'BSXd') and b.P.get(prow, 'BSXd') - 1 not in teams:   # with a team he is on (verify)
            b.P.set(prow, 'BSXd', (home[0] if home[0] in teams else min(teams & clubs or teams)) + 1)
        contracts.write(b.P, prow, deal, b.money)
        written[prow] = deal
        b.log.append(['edits', 'edited', label, "contract: " + contract_text(deal), ''])
    if written:
        say(f"My edits: {len(written)} contract{'s' if len(written) != 1 else ''} set")
    return written


def contract_text(deal):
    """'$12.5M x 2 seasons, two-way, then 8 x $16M': a contract in the player's words."""
    years = deal['years']
    text = f"{contracts.money(deal['cap'])} x {years} season{'s' if years != 1 else ''}"
    if deal.get('two_way'):
        text += ", two-way"
    if deal.get('ext'):
        text += f", then {deal['ext'][0]} x {contracts.money(deal['ext'][1])}"
    return text


# --- the parts of an edit ---------------------------------------------------------------------------
def _teams_of(b, prow):
    pid = b.P.get(prow, 'zIBw')
    return {b.U.get(e, 'BSXd') for e in b.live_entries().get(pid, [])}


def _set_fields(b, prow, fields, changed):
    P, U = b.P, b.U
    problems = []
    if fields.get('first'):
        b.set_text(prow, 'PedH', fields['first'])
    if fields.get('last'):
        b.set_text(prow, 'RMbQ', fields['last'])
    if fields.get('pos') in POSITIONS:
        new, old = L.POS_CODE[fields['pos']], P.get(prow, 'aljv')
        if (new == 4) != (old == 4):
            problems.append("a goalie cannot become a skater or the other way round")
        else:
            b.set_position(prow, new)
            if new != old:
                changed |= _teams_of(b, prow)
    if fields.get('style') is not None:
        style, kind = int(fields['style']), ratings.style_class(P.get(prow, 'aljv'))
        if style not in ratings.FREE_STYLES[kind]:
            problems.append(f"player type {ratings.style_label(style, kind == 'G')} is not a {'goalie' if kind == 'G' else 'skater'}'s")
        else:                   # the lines stay: they go by ratings and position, not by type
            b.set_style(prow, style)
    face = {key: int(fields[key]) for key in faces.FIELDS if fields.get(key) is not None}
    if face:
        why = faces.wrong(face, faces.heads(b.R))
        if why:
            problems.append(f"face: {why}")
        else:
            faces.write(P, prow, face)
    if fields.get('shoots') in ('L', 'R'):
        P.set(prow, 'pkRG', 0 if fields['shoots'] == 'L' else 1)
    if fields.get('birth'):
        y, m, d = fields['birth']
        P.set(prow, 'dnFq', max(0, y - stock.birth_base(b.R)))
        P.set(prow, 'pLKJ', m - 1)
        P.set(prow, 'iwsK', d - 1)
    if fields.get('country'):
        code = L.country_code(fields['country'])
        if code is None:
            problems.append(f"the game has no country {fields['country']}")
        else:
            P.set(prow, 'hleL', code)
    if fields.get('height_in'):
        P.set(prow, 'QBpy', max(0, min(31, int(fields['height_in']) - 54)))
    if fields.get('weight_lb'):
        P.set(prow, 'WZNs', max(0, min(255, int(fields['weight_lb']) - 120)))
    if fields.get('num'):
        n = int(fields['num'])
        if not 1 <= n <= 99:
            problems.append(f"number {n}: numbers go from 1 to 99")
        else:
            P.set(prow, 'tRVs', n)
            pid = P.get(prow, 'zIBw')
            for e in b.live_entries().get(pid, []):
                U.set(e, 'tRVs', n)
                _free_number(b, U.get(e, 'BSXd'), e, n)
    return problems


def _set_look(b, prow, look):
    """A created look (faces.LOOK) on a player of one of the game's Create Player records; others keep their head."""
    if not faces.is_reserved(b.P, prow):
        return ["a created look needs a new player made in this program (this one keeps his head)"]
    whole, problems = faces.clean_look(look)
    faces.write_look(b.R, prow, whole)
    return [f"look: {why} (the game's default kept)" for why in problems]


def _free_number(b, team, keep, n):
    """Another player on `team` wearing `n` gets the next free number (the edited one wins)."""
    U = b.U
    ents = b.entries_on(team)
    taken = {U.get(e, 'tRVs') for e in ents}
    for e in ents:
        if e != keep and U.get(e, 'tRVs') == n:
            free = next(x for x in range(2, 99) if x not in taken)
            U.set(e, 'tRVs', free)
            taken.add(free)
            b.log.append([b.R.team_name(team), 'number changed', b.R.name(b.prow_of_entry(e)),
                          f"#{n} given to an edited player", free])


def _set_ratings(b, prow, values, ovr=None, new=False):
    P = b.P
    goalie = P.get(prow, 'aljv') == 4
    tname = ratings.GOALIE_TABLE if goalie else ratings.SKATER_TABLE
    row = b.ai_row[tname].get(P.get(prow, 'zIBw'))
    if row is None:
        return
    table = b.R.f[tname]
    amap = LIST_GOALIE if goalie else LIST_SKATER
    if ovr and not values:
        ratings.write_attributes(table, row, {'ovr': ovr}, b.ovr_offset[goalie])
    for label, v in values.items():
        if label in amap and v is not None:
            table.set(row, amap[label], ratings.clamp(int(v) - RATING_BASE))
    if new or values:       # rated by his attributes, as the next run's Builder rates him: lines deal the same
        b.quality[P.get(prow, 'zIBw')] = ratings.level(table, row) + b.ovr_offset[goalie]


def _set_equipment(b, prow, values):
    """A player's own equipment choices (equipment.CHOICES for skaters, equipment.GOALIE_CHOICES for goalies).
    Returns the problems."""
    if not values:
        return []
    kind = 'goalie' if b.P.get(prow, 'aljv') == 4 else 'skater'
    table = b.R.f[equipment.KINDS[kind][0]]
    row = b.equipment_row(prow, kind)
    if row is None:
        return ["equipment: this player has no equipment record"]
    ok, problems = equipment.clean(values, table, kind)
    equipment.write(table, row, ok, kind)
    if kind == 'goalie' and 'mask' in ok:
        table.set(row, equipment.GOALIE_CODE[equipment.MASK_TYPE], 0)
    if not hasattr(b, 'equipment_set'):
        b.equipment_set = {}
    b.equipment_set.setdefault(prow, set()).update(ok)       # the team's choices do not override these
    return problems


def _mask_picture(b, prows, path):
    """A goalie's own picture on his mask (art/masks.py installs it). The goalie (and his national-team copies, `prows`)
    wears a mask number that has a texture on the disc and that nobody else wears: his own when it is that already (so a
    second run changes nothing), else the highest free one. Returns the problems."""
    rows = [r for r in (b.equipment_row(p, 'goalie') for p in prows if b.P.get(p, 'aljv') == 4) if r is not None]
    if not rows:
        return ["mask picture: only a goalie has a mask"]
    if not hasattr(b, 'mask_looks'):
        b.mask_looks = {}
    table = b.R.f[equipment.GOALIE_TABLE]
    code = equipment.GOALIE_CODE
    now = table.get(rows[0], code['maskid'])
    wearers = {i for i in range(table.cur_rec)
               if table.get(i, code[equipment.MASK_TYPE]) == 0 and table.get(i, code['maskid']) == now}
    same = [n for n, other in b.mask_looks.items() if other == path]       # the same picture, the same mask
    if same:
        n = same[0]
    elif (table.get(rows[0], code[equipment.MASK_TYPE]) == 0 and 0 < now <= equipment.MASK_LARGEST
          and now not in equipment.MASK_FILES_MISSING and now not in b.mask_looks and wearers <= set(rows)):
        n = now
    else:
        free = equipment.free_mask_ids(table, b.mask_looks)
        if not free:
            return ["mask picture: no free mask is left"]
        n = free[0]
    for row in rows:
        table.set(row, code['maskid'], n)
        table.set(row, code[equipment.MASK_TYPE], 0)
    b.mask_looks[n] = path
    return []


def _team_equipment(b, slot, values):
    """Choices for a whole team (tape, tucks, ...): every skater on it, except for what he has a choice of his own."""
    table = b.R.f[equipment.TABLE]
    ok, problems = equipment.clean({c: v for c, v in values.items() if c in equipment.TEAM_WIDE}, table)
    own = getattr(b, 'equipment_set', {})
    n = 0
    for e in b.entries_on(slot):
        prow = b.prow_of_entry(e)
        if prow is None or b.P.get(prow, 'aljv') == 4:
            continue
        row = b.equipment_row(prow)
        if row is not None:
            equipment.write(table, row, {c: v for c, v in ok.items() if c not in own.get(prow, ())})
            n += 1
    for text in problems:
        b.log.append(['edits', 'edit skipped', b.R.team_name(slot), text, ''])
    b.log.append(['edits', 'team equipment', b.R.team_name(slot), f"{n} skaters", ''])


def team_lineup_view(b, team):
    """({slot name: entry}, {entry: 'C' | 'A'}, {entry: position letter}, {entry: name}, {entry: person key}) of a team."""
    P = b.P
    slots, letters = lines.lineup(b, team)
    pos, name, who = {}, {}, {}
    for e in b.entries_on(team):
        prow = b.prow_of_entry(e)
        pos[e] = 'CLRDG'[P.get(prow, 'aljv')]
        name[e] = b.R.name(prow)
        who[e] = who_of(P, prow, stock.birth_base(b.R))
    return slots, letters, pos, name, who


def _team_lines(b, slot, saved):
    """The player's own lines and letters (Roster editor's Lines): `saved` {"slots": {slot name: person key},
    "letters": {person key: "C" | "A"}}. Lines that no longer fit the team (a player left, a rule is broken) are
    left out for this run and named in the List of changes: the team keeps the lines the update gave it."""
    team = b.R.team_name(slot)
    if slot in b.mirror_of:
        return
    _, _, pos, name, who = team_lineup_view(b, slot)
    entry = {w: e for e, w in sorted(who.items())}
    gone = sorted({w for w in list(saved.get('slots', {}).values()) + list(saved.get('letters', {})) if w not in entry})
    if gone:
        names = ', '.join(w.split('|')[0].title() + ' ' + w.split('|')[1].title() for w in gone[:3])
        b.log.append(['edits', 'edit skipped', team, f"your lines: {names} no longer on the team; the update's lines "
                      "are used", ''])
        return
    slots = {s: entry[w] for s, w in saved.get('slots', {}).items() if s in lines.S}
    letters = {entry[w]: l for w, l in saved.get('letters', {}).items() if l in ('C', 'A')}
    problems = lines.check_lineup(slots, letters, pos, name, nhl=slot in L.NHL_PRIMARY, repeats=True, free_letters=True)
    if problems:
        b.log.append(['edits', 'edit skipped', team, f"your lines: {problems[0]} The update's lines are used", ''])
        return
    lines.set_lineup(b, slot, slots, letters)
    b.log.append(['edits', 'own lines', team, 'lines, special teams and letters', ''])


def _team_strategy(b, slot, saved):
    """The player's own strategies (Roster editor's Strategies): {field: value}, only the fields he changed."""
    from . import strategy
    ok, problems = strategy.clean({k: v for k, v in saved.items()})
    for text in problems:
        b.log.append(['edits', 'edit skipped', b.R.team_name(slot), text, ''])
    if strategy.write(b.R, slot, ok):
        b.log.append(['edits', 'own strategies', b.R.team_name(slot), f"{len(ok)} strategies", ''])


def _move(b, prow, target, changed, wins=True):
    """Put a player on team `target` (a slot), or release him to the free agents ('FA'). `wins`: his number wins a
    clash; False for a new player without a number of his own, whose record's old number would take a team-mate's
    (the next run's league step gives it back to the team-mate, so the two runs would differ)."""
    R, U, P = b.R, b.U, b.P
    pid = P.get(prow, 'zIBw')
    live = b.live_entries()
    clubs = [e for e in live.get(pid, []) if U.get(e, 'BSXd') not in L.NATIONAL and U.get(e, 'BSXd') not in b.mirror_of]
    if target != 'FA' and any(U.get(e, 'BSXd') == int(target) for e in clubs):
        return []
    if target == 'FA':
        for e in clubs:
            changed.add(U.get(e, 'BSXd'))
            b.release(e, live)
        P.set(prow, 'BSXd', 0)
        return []
    target = int(target)
    if target in b.mirror_of or not 0 <= target < R.T.cur_rec:
        return [f"team {target} cannot be chosen"]
    if any(U.get(e, 'BSXd') == target for e in clubs):
        return []
    if len(b.entries_on(target)) >= L.MAX_PER_TEAM:
        return [f"{R.team_name(target)} has {L.MAX_PER_TEAM} players already (the most the game allows)"]
    if clubs:
        first, rest = clubs[0], clubs[1:]
        changed.add(U.get(first, 'BSXd'))
        b.move_entry(first, target)
        for e in rest:
            changed.add(U.get(e, 'BSXd'))
            b.release(e, live)
        entry = first
    else:
        fa = [l for l in b.fa_links if R.link_to_pid.get(l) == pid]
        entry = b.new_entry(target, fa[0] if fa else b.new_link(pid), prow)
        b.arrivals.setdefault(target, []).append(entry)
        b.drop_fa(pid)
    changed.add(target)
    if wins:
        _free_number(b, target, entry, U.get(entry, 'tRVs'))
    else:
        taken = {U.get(e, 'tRVs') for e in b.entries_on(target) if e != entry}
        n = next(x for x in (U.get(entry, 'tRVs'), *range(2, 99)) if x and x not in taken)
        U.set(entry, 'tRVs', n)
        P.set(prow, 'tRVs', n)
    if target not in L.NATIONAL:        # a player's contract team is his club (as the leagues set it)
        P.set(prow, 'BSXd', target + 1)
    if target in L.NHL_PRIMARY:
        b.set_pro_team(prow, target)
    return []


def _create(b, who, e):
    """A new player on a spare record (as the club leagues create theirs). None when none is left."""
    fields = e.get('set') or {}
    pos = L.POS_CODE.get(fields.get('pos') or 'C', 0)
    name = f"{fields.get('first', '')} {fields.get('last', '')}".strip()
    looks = _look_records(b)[pos == 4] if e.get('look') else []
    if looks:                   # one of the game's Create Player records: the only ones a created look shows on
        prow = looks.pop(0)
        b.created.add(prow)
        b.P.set(prow, 'NYKk', 1)        # active: the game's Create Player no longer sees it as free
        if pos != b.P.get(prow, 'aljv'):
            b.set_position(prow, pos)
        country = fields.get('country') or 'CAN'       # an empty record has none (127)
    else:
        held = b.held_records.get(pos)
        prow = held.pop(0) if held else b.take_record(pos, name, required=False)
        country = fields.get('country')
    if prow is None:
        return None
    y = (fields.get('birth') or [b.data.season_year - 22, 1, 1])[0]
    b.donors.reset_identity(prow, name, L.country_code(country), y)
    b.P.set(prow, 'JzFM', '')
    b.P.set(prow, 'BSXd', 0)
    for f in contracts.FIELDS:      # not the record's last wearer's deal: his club's starter deal or an NHL one
        b.P.set(prow, f, 0)
    b.P.set(prow, contracts.STATUS, 0)
    b.placed.add(b.P.get(prow, 'zIBw'))
    if not fields.get('birth'):
        fields = dict(fields, birth=[y, 1, 1])
    _set_fields(b, prow, fields, set())
    if pos != 4:        # the record's last wearer's gear goes: a new player starts with Edit Pro's plain choices
        row = b.equipment_row(prow)
        if row is not None:
            table = b.R.f[equipment.TABLE]
            equipment.write(table, row, equipment.clean(equipment.NEW_PLAYER, table)[0])
    b.log.append(['edits', 'created', name, 'a new player of your own', fields.get('num') or ''])
    if e.get('team') in (None, 'FA'):
        b.fa_links.append(b.new_link(b.P.get(prow, 'zIBw')))
    return prow


def _hand_on_letters(b, team, before):
    """A team that cannot dress 20 gets no new lines, but its captain and alternates who left must not leave it without
    letters: `before` ({entry: 'C' / 'A' / None}, what the team had) says how many it had of each; the missing ones go to the
    best skaters who wear none (an NHL team gets one captain and two alternates)."""
    U = b.U
    ents = b.entries_on(team)
    now = [U.get(e, 'lcCm') for e in ents]
    want = {1: sum(1 for v in before.values() if v == 'C'), 2: sum(1 for v in before.values() if v == 'A')}
    if team in L.NHL_PRIMARY:           # the game's NHL teams wear one captain and two alternates
        want = {1: max(want[1], 1), 2: max(want[2], 2)}
    free = sorted((e for e in ents if not U.get(e, 'lcCm') and b.cls(e) != 'G'), key=lambda e: (-b.q(e), e))
    for letter in (1, 2):
        for _ in range(want[letter] - now.count(letter)):
            if free:
                U.set(free.pop(0), 'lcCm', letter)


def _relines(b, changed, say):
    """Lines of the teams the edits changed, dealt afresh by rating and position (lines.py): the
    same players always get the same lines, so a later update with the same edits changes nothing.
    (Copying the team's previous line pattern would not: the pattern itself moves between runs.)"""
    from .leagues.clubs import _letters
    for team in sorted(t for t in changed if t not in b.mirror_of):
        if not b.entries_on(team):
            continue
        # the captain and alternates who are still there keep their letters; a missing one is
        # given to the best dressed skater
        letters = {e: {1: 'C', 2: 'A'}.get(b.U.get(e, 'lcCm')) for e in b.entries_on(team)}
        try:
            lines.build_lines(b, team)
            _letters(b, team, letters)
        except lines.NotEnoughPlayers as err:
            say(f"My edits: {err}")
            for e in b.entries_on(team):          # no lines, but the captain and alternates keep their letters
                letter = b.U.get(e, 'lcCm')
                b.clear_lines(e)
                b.U.set(e, 'lcCm', letter)
            _hand_on_letters(b, team, letters)
    if any(t in L.NHL_PRIMARY for t in changed):
        b.sync_mirrors()
