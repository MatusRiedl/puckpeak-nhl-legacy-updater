"""The Roster editor's "Jerseys and ice" window without a window toolkit: a team's jerseys and centre-ice logo.

    colours      the two colours (and a crest picture) the jerseys are made from
    versions     one row per jersey version the window offers (looks.team_versions: every version Play Now cycles
                 through with "Change Jerseys" for an NHL team, home and away elsewhere): the pack's kit (where the
                 program's look pack has one: art/lookpack.py), keep the game's own, make it from the colours (the
                 shared shirt layout only), or use the player's own picture
    ice          the centre-ice logo: the pack's, the game's own, drawn from the team's logo and arena name, or the player's
                 picture; outside the NHL only where the club's home games show its own (looks.own_ice), or, where
                 several teams share one ice (looks.ice_group: the national teams, the DEL, EASHL), the game's own or a
                 picture for all of them (one per group: saving it takes the group's other teams' ice choice away)

Every team of every league whose jerseys are its own (looks.editable) has the window; the files are the team's art id's
(Charlotte is slot 36, art 162), in its cut (most European clubs and the national teams: the classic cut, style 0). A
team wearing another team's jerseys (the Winter Classic teams, EASHL 2) opens that team's window, with a note
(looks.window_team). A custom team (slots 222-251) has its own form instead: app/teamkit.py.
What is chosen is kept in edits.json (`teams[slot]["uniforms"]` / `["ice"]`, see edits.py) and installed by every update that
has "Photos, logos and team names" on (art/looks.py); "Restore the game's own pictures" puts the game's own back. A player's own
jersey picture is a flat 1024 x 1024 colour map in the version's shirt layout: the window saves the game's own (and the pack's,
where it fits that layout) as a template to paint on. Reading the game's disc takes a moment, so it runs in worker threads
(editor/pictures.py `work`); the small pictures are a slice of their own (`thumbs`), so typing a colour does not send them
all again.
"""
import copy
import threading

from .. import custom_kit, edits
from .. import layout as L
from ..art import looks
from . import dataurl, teamkit
from . import texts as X
from .editor import NO_ROSTER, RAIL

SLICE, THUMBS = 'uniforms', 'thumbs'
GAME, COLOURS, FILE, PACK = 'game', 'colours', 'file', looks.PACK
THUMB = 156                     # pixels of a small picture (shown at 78 on the page, sharp at 200 %)
ICE = 'ice'
GAME_WORDS = {0: "Home", 1: "Away", 2: "Alternate"}     # the game's Select Jerseys words (looks.version_words)


def _hex(colour):
    return '#%02x%02x%02x' % tuple(colour)


class UniformsController:
    def __init__(self, host, editor):
        self.host, self.editor = host, editor
        editor.uniforms = self
        self.lock = threading.RLock()
        self.slot = None                # the team shown (None: the window is closed)
        self.team_kit = None            # a custom team's form (app/teamkit.py), or None
        self.group = None               # (art id, slots) of a centre ice shared by several teams (looks.ice_group)
        self.thumbs = {}                # variant (str) or 'ice' -> data: link (None: no picture)
        self._tokens = {}               # variant -> the latest request (an older picture is dropped)
        # the Jerseys & ice tab: it follows the team picked in the team list, reading the disc only while it shows
        self.tabbed = False
        self.visible = False
        self.shown = None               # the team picked (its window may be another team's: looks.window_team)
        self.why = ''
        self.waiting = False            # a team was picked, its window opens in a moment
        self.stale = False
        self.roster = None
        self.kept = {}                  # slot -> what was changed but not applied (`_state`)
        self.clean = None               # what the shown team keeps (edits.json) as it was opened or applied
        self._timer = None
        self._follow = 0                # the latest pick: a later one drops an earlier one's window
        editor.follow_with('jerseys', self)

    def changed(self):
        self.host.changed(SLICE)

    # --- open and close ------------------------------------------------------------------------------
    def open(self, slot, picked=None, draft=None):
        """The window of team `slot`; `picked` the team the player picked when it wears `slot`'s jerseys; `draft` what
        the player changed on the tab before and did not apply (`_state`)."""
        ed = self.editor
        with ed.lock:
            snap = ed.snap
            if snap is None:
                return
            R = snap.R
            mine = ed.teams.get(str(slot)) or {}
            name = snap.team_name(slot)
            pictures = ed._pictures()
            group_ice = {}
        no_pictures = ("RPCS3 does not say where your game is, so the pictures are not shown here. You can still "
                       "choose; nothing is made until an update with pictures on.") if pictures is None else ''
        if custom_kit.is_custom(slot):
            self._open_custom(slot, name, R, mine, pictures, no_pictures, draft)
            return
        group = None if slot in looks.NHL else looks.ice_group(R, slot)
        if group:                       # the group's picture, set at any of its teams: the lowest slot's (as the update)
            with ed.lock:
                group_ice = next((dict(ed.teams[str(s)]['ice']) for s in group[1]
                                  if ((ed.teams.get(str(s)) or {}).get('ice') or {}).get('use', '').startswith('file:')),
                                 {})
        sharing = [snap.team_name(s) for s in range(R.T.cur_rec)
                   if s != slot and looks.jersey_owner(R, s) == slot]
        with self.lock:
            self.team_kit = None
            self.slot, self.name, self.R = slot, name, R
            self.art, self.style = looks.team_art(R, slot)
            self.default_team = slot in looks.NEW_TEAMS
            self.uniforms = {'colours': dict((mine.get('uniforms') or {}).get('colours') or {}),
                             'versions': dict((mine.get('uniforms') or {}).get('versions') or {})}
            self.ice = dict(mine.get('ice') or {})
            self.group = group
            if group and 'use' not in self.ice and group_ice.get('use'):
                self.ice['use'] = group_ice['use']
            if slot in looks.NHL:       # an NHL team: what an update writes (builder.NHL_ARENAS / NHL_COLOURS)
                from .. import builder
                primary, secondary = builder.NHL_COLOURS[slot]
                arena = builder.NHL_ARENAS[slot]
            else:
                primary, secondary = looks.team_colours(R, slot)
                arena = looks.team_arena(R, slot)
            self.base = {'primary': tuple(primary), 'secondary': tuple(secondary), 'arena': arena}
            self.typed = {part: self.uniforms['colours'].get(part) or _hex(self.base[part])
                          for part in ('primary', 'secondary')}
            self.arena = self.ice.get('arena') or arena
            self.pictures = pictures
            self.versions = looks.team_versions(R, slot)
            self.words = looks.version_words(R, self.art, self.style)
            self.standard = {}         # variant -> uses the shared shirt layout (None: not known yet)
            from ..art.lookpack import LookPack
            self.look_pack = LookPack.open()
            team = looks.pack_team(R, slot, self.look_pack)
            usable = team is not None and not team.why
            self.kits = team.kits if usable else {}            # variant -> the pack's kit (looks.PackKit)
            # a club's new centre ice only shows where its home games show its own file (the update does the same); a
            # shared one takes a picture for the whole group
            self.ice_why = None if slot in looks.NHL or group else looks.own_ice(R, slot, looks.centre_owners(R))
            self.ice_note = looks.ice_note(R, slot) if group else ''
            self.pack_centre = team.centre if usable and not self.ice_why and not group else None
            self.centre_art = group[0] if group else looks.shown_centre(R, slot) if self.ice_why else self.art
            self.club_logo = looks.club_logos(R, (ed.update.pack or {}).get('leagues')).get(slot)
            self.loaded = False
            self.note = no_pictures
            everyone = 'both teams' if len(sharing) == 1 else 'all of them'
            if picked is not None and picked != slot:
                owner = name + ("'" if name.endswith('s') else "'s")
                self.shared_note = f"{snap.team_name(picked)} wears {owner} jerseys: a change shows on {everyone}."
            elif sharing:
                self.shared_note = (f"{' and '.join(sharing)} {'wears' if len(sharing) == 1 else 'wear'} these jerseys "
                                    f"too: a change shows on {everyone}.")
            else:
                self.shared_note = ''
            self.clean = self._collect()
            if draft and draft[0] == 'files':
                self.uniforms, self.ice, self.typed, self.arena = copy.deepcopy(draft[1:])
            self.thumbs, self._tokens = {}, {}
            self.host.changed(THUMBS)
            self.changed()
        self._read_game()

    def _open_custom(self, slot, name, R, mine, pictures, note, draft=None):
        with self.lock:
            self.slot, self.name, self.R = slot, name, R
            self.team_kit = teamkit.TeamKit(R, slot, name, mine.get('kit'))
            # the arena name: what an update keeps, or the one the player gave (a row other teams use is renamed for all)
            self.base = {'arena': looks.team_arena(R, slot)}
            self.arena = (mine.get('ice') or {}).get('arena') or self.base['arena']
            self.ice = dict(mine.get('ice') or {})
            self.clean = self._custom_collect()
            if draft and draft[0] == 'kit':
                self.team_kit = teamkit.TeamKit(R, slot, name, copy.deepcopy(draft[1]))
                self.arena = draft[2] if len(draft) > 2 else self.arena
            self.pictures, self.note, self.loaded = pictures, note, pictures is None
            self.thumbs, self._tokens = {}, {}
            self.host.changed(THUMBS)
            self.changed()
        if pictures is None:
            return

        def done(found):
            with self.lock:
                if not self._alive(slot) or self.team_kit is None:
                    return
                self.thumbs.update(found)
                if not found:
                    self.note = "The game's Create a Team pictures could not be read. You can still choose by number."
                self.loaded = True
                self.host.changed(THUMBS)
                self.changed()
        teamkit.read_menu_pictures(pictures, done)

    # --- a custom team (app/teamkit.py) --------------------------------------------------------------------
    KIT_ACTIONS = {'design': 'set_design', 'colour': 'type_colour', 'paint': 'paint', 'side': 'set_side',
                   'zone': 'set_zone', 'reset': 'reset_piece', 'logo': 'set_logo'}

    def kit(self, action, *args):
        """A choice in a custom team's form: KIT_ACTIONS."""
        with self.lock:
            if self.team_kit is None or action not in self.KIT_ACTIONS:
                return
            try:
                done = getattr(self.team_kit, self.KIT_ACTIONS[action])(*args)
            except TypeError:
                return
            self.changed()          # also when refused: the page shows what is kept again
            return done

    def kit_picture(self):
        """A crest picture of the player's own for a custom team, drawn in its own three main colours."""
        with self.lock:
            if self.team_kit is None:
                return
            slot = self.slot
        link = self.editor.pick_picture("A crest for this team (a logo with a clear background)")
        if not link:
            return
        try:
            from PIL import Image
            from ..art import crests
            with Image.open(link[5:]) as img:
                colours = crests.main_colours(img)
        except Exception:
            colours = [(255, 255, 255)] * 3
        with self.lock:
            if self._alive(slot) and self.team_kit is not None:
                self.team_kit.set_picture(link, colours)
                self.changed()

    def close(self):
        with self.lock:
            self.slot, self.team_kit = None, None
            self.thumbs, self._tokens = {}, {}
            self.host.changed(THUMBS)
            self.changed()

    def _alive(self, slot):
        return self.slot == slot

    # --- the Jerseys & ice tab ------------------------------------------------------------------------------
    DELAY = 0.25                    # seconds after a team is picked before its pictures are read (clicking along the list)

    def follow(self, team):
        """The tab shows `team` (None: no roster yet). What was changed and not applied stays with its team."""
        ed = self.editor
        with ed.lock:
            key, snap, busy = ed.roster_key(), ed.snap, ed.busy
            owner, why = (None, None)
            if snap is not None and isinstance(team, int):
                owner, why = looks.window_team(snap.R, team)
        with self.lock:
            self.tabbed, self.visible = True, True
            if key != self.roster:
                self.roster, self.kept, self.stale = key, {}, True
                self.slot = None
            if team == self.shown and not self.stale and (self.slot is not None or self.waiting or self.why):
                return
            self._keep()
            self._cancel()
            self.shown, self.stale, self.why, self.waiting = team, False, '', False
            self.slot, self.team_kit, self.thumbs, self._tokens = None, None, {}, {}
            if snap is None or team is None:
                self.why = "Reading the roster..." if busy else NO_ROSTER
            elif not isinstance(team, int):
                self.why = "Free agents wear no team's jerseys. Pick a team in the list."
            elif why:
                self.why = why
            else:
                self.waiting = True
                self._follow += 1
                self._timer = threading.Timer(self.DELAY, self._opened, (self._follow, owner, team))
                self._timer.daemon = True
                self._timer.start()
            self.host.changed(THUMBS)
            self.changed()

    def _opened(self, token, owner, team):
        with self.lock:
            if not self.visible or token != self._follow:      # another team was picked, or the tab was left
                return
            self.waiting, self._timer = False, None
            draft = self.kept.pop(owner, None)
        self.open(owner, picked=team, draft=draft)
        with self.lock:
            if token != self._follow and self.slot == owner:   # picked away while it was opening: drop it again
                self._keep()
                self.slot = None
                self.changed()

    def _cancel(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _state(self):
        """What the shown team's form holds, to come back to: ('files', uniforms, ice, typed, arena) or ('kit', kit)."""
        if self.team_kit is not None:
            return 'kit', copy.deepcopy(self.team_kit.collect()), self.arena
        return ('files',) + copy.deepcopy((self.uniforms, self.ice, self.typed, self.arena))

    def _dirty(self):
        if self.slot is None:
            return False
        return (self._custom_collect() if self.team_kit is not None else self._collect()) != self.clean

    def _custom_collect(self):
        """A custom team keeps its look (the kit) and the arena name it was given (the same `ice.arena` a normal team keeps)."""
        arena = self.arena.strip()
        return self.team_kit.collect(), ({'arena': arena} if arena and arena != self.base['arena'] else {})

    def _keep(self):
        if self.slot is None:
            return
        if self._dirty():
            self.kept[self.slot] = self._state()
        else:
            self.kept.pop(self.slot, None)

    def hide(self):
        with self.lock:
            self.visible = False
            if self.waiting:                # not opened yet: it opens when the tab shows again
                self._cancel()
                self.waiting, self.stale = False, True

    def roster_changed(self):
        with self.lock:
            self.stale = True

    def drafts(self):
        """Teams with jerseys or ice changed but not applied."""
        with self.lock:
            return set(self.kept) | ({self.slot} if self._dirty() else set())

    # --- what is chosen --------------------------------------------------------------------------------
    def _light(self, variant):
        return next((light for v, light, _d in self.versions if v == variant), False)

    def _default_mode(self, variant, light):
        return looks.default_use(self.slot, variant, light, self.kits)

    def _use(self, variant):
        use = self.uniforms['versions'].get(str(variant)) or self._default_mode(variant, self._light(variant))
        if use == PACK and variant not in self.kits:          # no look pack in this program: what the update does
            use = looks.default_use(self.slot, variant, self._light(variant), {})
        return use

    def _mode(self, variant):
        use = self._use(variant)
        return FILE if use.startswith('file:') else use

    def _default_ice(self):
        return looks.default_ice(self.slot, self.pack_centre)

    def _ice_use(self):
        use = self.ice.get('use') or self._default_ice()
        return looks.default_ice(self.slot, None) if use == PACK and not self.pack_centre else use

    def _ice_mode(self):
        use = self._ice_use()
        return FILE if use.startswith('file:') else COLOURS if use == 'logo' else PACK if use == PACK else GAME

    def _colour(self, part):
        return looks.parse_colour(self.typed.get(part), self.base[part])

    def _variant(self, variant):
        try:
            variant = int(variant)
        except (TypeError, ValueError):
            return None
        return variant if any(v == variant for v, _l, _d in self.versions) else None

    def set_colour(self, part, text):
        with self.lock:
            if self.slot is None or self.team_kit is not None or part not in ('primary', 'secondary'):
                return
            before = self._colour(part)
            self.typed[part] = str(text or '')
            self.changed()
            if self._colour(part) != before:
                self._refresh_colour_rows()

    def choose_crest(self):
        with self.lock:
            if self.slot is None or self.team_kit is not None:
                return
            slot = self.slot
        link = self.editor.pick_picture("A crest for this team's jerseys")
        with self.lock:
            if link and self._alive(slot):
                self.uniforms['colours']['crest'] = link
                self.changed()
                self._refresh_colour_rows()

    def clear_crest(self):
        with self.lock:
            if self.slot is None or self.team_kit is not None:
                return
            self.uniforms['colours'].pop('crest', None)
            self.changed()
            self._refresh_colour_rows()

    def pick(self, variant, value):
        with self.lock:
            variant = self._variant(variant) if self.slot is not None else None
            if variant is None or value not in (GAME, COLOURS, FILE, PACK) or (value == PACK and variant not in self.kits) \
                    or (value == COLOURS and self.style != looks.STYLE):
                return
            slot = self.slot
        if value == FILE:
            link = self.editor.pick_picture("Your colour map for this jersey (a flat 1024 x 1024 picture)")
            if not link:
                self.changed()          # the page shows the earlier choice again
                return
            value = link
        with self.lock:
            if not self._alive(slot):
                return
            self.uniforms['versions'][str(variant)] = value
            self.changed()
            self._thumb(variant)

    def pick_ice(self, value):
        with self.lock:
            allowed = (GAME, FILE) if self.team_kit is None and self.group else (GAME, COLOURS, FILE, PACK)
            if self.slot is None or self.team_kit is not None or value not in allowed \
                    or (value == PACK and not self.pack_centre) or (self.ice_why and value != GAME):
                return
            slot = self.slot
        if value == FILE:
            link = self.editor.pick_picture("Your centre-ice logo (1024 x 1024, clear background)")
            if not link:
                self.changed()
                return
            use = link
        else:
            use = 'logo' if value == COLOURS else PACK if value == PACK else GAME
        with self.lock:
            if not self._alive(slot):
                return
            self.ice['use'] = use
            self.changed()
            self._ice_thumb()

    def set_arena(self, text):
        with self.lock:
            if self.slot is None:
                return
            self.arena = str(text or '')
            self.changed()
            if self.team_kit is None and self._ice_mode() == COLOURS:
                self._ice_thumb()

    # --- pictures, made in worker threads ------------------------------------------------------------------
    def _read_game(self):
        """Which versions use the shared shirt layout, then the pictures."""
        with self.lock:
            slot, pictures, versions = self.slot, self.pictures, list(self.versions)
            art, style = self.art, self.style
        if pictures is None:
            with self.lock:
                self.loaded = True
                self.changed()
            return

        def job():
            try:
                found = pictures.work(lambda m: {v: m.standard(art, v, style) for v, _l, _d in versions})
            except Exception:
                found = {}
            with self.lock:
                if not self._alive(slot):
                    return
                self.standard.update(found)
                self.loaded = True
                self.changed()
                for variant, _light, _d in self.versions:
                    self._thumb(variant)
                self._ice_thumb()
        threading.Thread(target=job, daemon=True).start()

    def _logo(self, plain=False):
        """The team's logo for the previews (a Pillow picture or None)."""
        link = self.uniforms['colours'].get('crest') or (self.editor.teams.get(str(self.slot)) or {}).get('logo') \
            or self.club_logo
        if not link:
            code = next((a for a, s in L.API_TO_SLOT.items() if s == self.slot), None)
            link = ((self.editor.update.pack or {}).get('nhl_logos') or {}).get(code)
        if not link:
            return None
        from ..art import install
        from ..art.photopack import PhotoPack, PictureCache
        return looks.team_logo(install.plain_logo_url(link) if plain else link, PhotoPack.open(), PictureCache())

    def _request(self, key):
        token = self._tokens.get(key, 0) + 1
        self._tokens[key] = token
        return token

    def _deliver(self, slot, key, token, img):
        url = dataurl.picture(img, (THUMB, THUMB)) if img is not None else None
        with self.lock:
            if not self._alive(slot) or self._tokens.get(key) != token:
                return
            self.thumbs[key] = url
            self.host.changed(THUMBS)

    def _thumb(self, variant):
        if self.pictures is None or self.slot is None:
            return
        slot, pictures, key = self.slot, self.pictures, str(variant)
        art, style = self.art, self.style
        token = self._request(key)
        light = self._light(variant)
        use = self._use(variant)
        kind = FILE if use.startswith('file:') or use == PACK else use
        colours = (self._colour('primary'), self._colour('secondary'))
        logo_wanted = kind == COLOURS
        kit, look_pack = self.kits.get(variant), self.look_pack

        def job():
            try:
                from PIL import Image
                picture = menu = None
                if use == PACK:                               # the pack's own menu picture of the kit, as Select Jerseys shows it
                    member = (kit.menu or '').split('#')[0]
                    if member and look_pack.has(member):
                        menu = look_pack.picture(member)
                    else:                                      # else its colour map, shown like a picture of the player's
                        picture = look_pack.picture(kit.member).convert('RGB').resize((1024, 1024))
                elif kind == FILE:
                    picture = Image.open(use[5:])
                    picture.load()
                    picture = picture.convert('RGB').resize((1024, 1024))
                logo = self._logo(light) if logo_wanted else None
                img = pictures.work(lambda m: m.thumbnail(art, variant, light, kind, logo, colours, picture, menu, style))
            except Exception:
                img = None
            self._deliver(slot, key, token, img)
        threading.Thread(target=job, daemon=True).start()

    def _refresh_colour_rows(self):
        for variant, _light, _d in self.versions:
            if self._use(variant) == COLOURS:
                self._thumb(variant)
        if self._ice_mode() == COLOURS:
            self._ice_thumb()

    def _ice_thumb(self):
        if self.pictures is None or self.slot is None:
            return
        slot, pictures, centre_art = self.slot, self.pictures, self.centre_art
        token = self._request(ICE)
        mode, use = self._ice_mode(), self.ice.get('use') or ''
        arena, ink = self.arena.strip() or self.base['arena'], looks._ink(self._colour('secondary'))
        look_pack, pack_centre = self.look_pack, self.pack_centre

        def job():
            try:
                from PIL import Image
                if mode == PACK:
                    img = looks.finish_centre(look_pack.picture(pack_centre[5:].split('#')[0]).convert('RGBA'))
                elif mode == FILE:
                    img = Image.open(use[5:])
                    img.load()
                    img = looks.finish_centre(img.convert('RGBA').resize((1024, 1024)))
                elif mode == COLOURS:
                    img = looks.centre_logo(self._logo(True), arena, ink)
                else:
                    img = pictures.work(lambda m: m.own_centre(centre_art))
                if img is not None:
                    back = Image.new('RGBA', img.size, (190, 215, 240, 255))
                    back.alpha_composite(img.convert('RGBA'))
                    img = back
            except Exception:
                img = None
            self._deliver(slot, ICE, token, img)
        threading.Thread(target=job, daemon=True).start()

    def _templates(self, variant):
        """The templates a version's row offers: the pack's colour map where it is painted in the layout "My picture" uses
        for this version (the classic cut, or a version on the shared shirt layout), and the game's own."""
        fits = self.style != looks.STYLE or self.standard.get(variant) is True
        return ([PACK] if variant in self.kits and fits else []) + [GAME]

    def template(self, variant=None, which=GAME):
        """Save the game's own colour map of a jersey version (`which` PACK: the pack's kit), or with no version the
        centre-ice logo, as a picture to paint on."""
        with self.lock:
            if self.slot is None or self.team_kit is not None:
                return
            slot, pictures, art, style = self.slot, self.pictures, self.art, self.style
            centre_art, look_pack = self.centre_art, self.look_pack
            ice = variant is None or variant == ICE
            kit = None
            if not ice:
                variant = self._variant(variant)
                if variant is None or which not in self._templates(variant):
                    return
                kit = self.kits.get(variant) if which == PACK else None
        if ice:
            filename = f"centre_ice_{centre_art}.png"
        else:
            filename = f"jersey_{art}_{variant}" + ("_season.png" if kit else ".png")
        path = self.editor.host.ask_save("Save the template", filename, ['PNG (*.png)'])
        if not path or (pictures is None and kit is None):
            return
        if not path.lower().endswith('.png'):
            path += '.png'

        def job():
            try:
                if ice:
                    pictures.work(lambda m: m.own_centre(centre_art)).save(path)
                    text = "Saved. Paint over it, keep it 1024 x 1024 with a clear background, then use \"My picture...\"."
                else:
                    if kit is not None:
                        img = looks._full_size(look_pack.picture(kit.member))
                    else:
                        img = pictures.work(lambda m: m.own_colour_map(art, variant, style)).convert('RGB')
                    img.save(path)
                    text = "Saved. Paint over it in any picture program and keep it 1024 x 1024, then use \"My picture...\"."
            except Exception as err:
                text = f"The template could not be saved: {err}"
            with self.lock:
                if self._alive(slot):
                    self.note = text
                    self.changed()
        threading.Thread(target=job, daemon=True).start()

    # --- keeping it --------------------------------------------------------------------------------------
    def _collect(self):
        """The team edit's 'uniforms' and 'ice' parts: only what differs from what the update does anyway."""
        colours = {}
        for part in ('primary', 'secondary'):
            if self._colour(part) != self.base[part]:
                colours[part] = _hex(self._colour(part))
        if self.uniforms['colours'].get('crest'):
            colours['crest'] = self.uniforms['colours']['crest']
        versions = {}
        for variant, light, _d in self.versions:
            use = self.uniforms['versions'].get(str(variant))
            if use and use != self._default_mode(variant, light):
                versions[str(variant)] = use
        uniforms = {}
        if colours:
            uniforms['colours'] = colours
        if versions:
            uniforms['versions'] = versions
        ice = {}
        default = self._default_ice()
        if self.ice.get('use') and self.ice['use'] != default and not self.ice_why:
            ice['use'] = self.ice['use']
        arena = self.arena.strip()
        if arena and arena != self.base['arena'] and not self.group:
            ice['arena'] = arena
        return uniforms, ice

    def _save(self, uniforms=None, ice=None, kit=None):
        """Keep the parts in edits.json (an empty part is dropped). A shared ice (ice_group) is the group's: the other
        teams of the group lose their own choice of it."""
        ed = self.editor
        parts = {'kit': kit, 'ice': ice} if self.team_kit is not None else {'uniforms': uniforms, 'ice': ice}
        with ed.lock:
            team = dict(ed.teams.get(str(self.slot)) or {})
            for key, value in parts.items():
                if value:
                    team[key] = value
                else:
                    team.pop(key, None)
            changes = {self.slot: team}
            for other in (self.group[1] if self.team_kit is None and self.group else ()):
                theirs = dict(ed.teams.get(str(other)) or {})
                if other != self.slot and (theirs.get('ice') or {}).get('use'):
                    rest = {k: v for k, v in theirs['ice'].items() if k != 'use'}
                    if rest:
                        theirs['ice'] = rest
                    else:
                        theirs.pop('ice')
                    changes[other] = theirs
            for slot, team in changes.items():
                if team:
                    ed.teams[str(slot)] = team
                else:
                    ed.teams.pop(str(slot), None)
                ed.looks_touched.add(slot)      # its files go in (or back to the game's own) with the next Save
            ed._edits_saved(players=False)
            ed.changed()

    def apply(self):
        with self.lock:
            if self.slot is None:
                return
            custom = self.team_kit is not None
            if custom:
                kit, ice = self._custom_collect()
                self._save(kit=kit, ice=ice)
            else:
                self._save(*self._collect())
            tabbed = self.tabbed
            if tabbed:                      # the tab stays on the team
                self.clean = self._custom_collect() if custom else self._collect()
                self.kept.pop(self.slot, None)
                self.changed()
        self.host.changed(RAIL)
        if custom:
            self.editor.set_status("The team's look is kept. It is put into the next update with My edits on; a crest "
                                   "picture also needs \"Photos and logos\" on.", 'warn')
        else:
            self.editor.set_status("Jerseys and ice kept. They are made in the next update with \"Photos, logos and "
                                   "team names\" on (and My edits on).", 'warn')
        if not tabbed:
            self.close()

    def undo(self):
        with self.lock:
            if self.slot is None:
                return
            self._save()
            slot, team, tabbed = self.slot, self.shown, self.tabbed
            self.kept.pop(slot, None)
        self.editor.set_status("This team's jerseys and ice are back to what the update makes (a changed game keeps "
                               "them until the next update).", 'warn')
        self.host.changed(RAIL)
        if tabbed:                          # the tab reads the team again, as the update makes it
            self.open(slot, picked=team)
        else:
            self.close()

    # --- what the page shows ------------------------------------------------------------------------------
    def _label(self, variant, light, default):
        # the game's own word (Charlotte's Home jersey is its light one), then the colour
        word = GAME_WORDS.get(self.words.get(variant))
        colour = "light" if light else "dark"
        if word and default:
            return f"{word} ({colour})"
        return f"{word} ({colour}), version {variant}" if word else f"{colour.capitalize()}, another version ({variant})"

    def _legs(self, variant):
        """What the version's socks and pants become: the pack kit's own, made in the jersey's colours (the chassis'), or
        the game's own."""
        mode = self._mode(variant)
        if mode == GAME:
            return X.LEGS_GAME
        kit = self.kits.get(variant) if mode == PACK else None
        return X.LEGS_PACK if kit is not None and kit.sock else X.LEGS_MADE

    def snapshot(self):
        with self.lock:
            view = self.editor.team_view(self.shown) if self.tabbed else None
            if self.slot is None:
                return {'why': self.why, 'loading': self.waiting, 'view': view} if self.tabbed else None
            if self.team_kit is not None:
                out = self.team_kit.snapshot(self.note, self.loaded, self.pictures is not None)
                return dict(out, view=view, dirty=self._dirty(), arena=self.arena) if isinstance(out, dict) else out
            rows = []
            for variant, light, default in self.versions:
                options = [[PACK, "This season's"]] if variant in self.kits else []
                options.append([GAME, "The game's own"])
                if self.style == looks.STYLE and self.standard.get(variant) is not False:     # the shared layout only
                    options.append([COLOURS, "From the colours"])
                options.append([FILE, "My picture..."])
                rows.append({'variant': variant, 'label': self._label(variant, light, default), 'light': light,
                             'mode': self._mode(variant), 'options': options, 'templates': self._templates(variant),
                             'legs': self._legs(variant)})
            if self.ice_why:
                ice_options = [[GAME, "The game's own"]]
            elif self.group:
                ice_options = [[GAME, "The game's own"], [FILE, "My picture..."]]
            else:
                ice_options = ([[PACK, "This season's"]] if self.pack_centre else []) \
                    + [[GAME, "The game's own"], [COLOURS, "From the logo"], [FILE, "My picture..."]]
            return {'kind': 'files', 'slot': self.slot, 'title': f"{self.name}: jerseys and ice", 'note': self.note,
                    'shared': self.shared_note, 'art': self.art,
                    'pack_note': X.LOOKS_MISSING if self.loaded and getattr(self, 'look_pack', None) is None else None,
                    # the colours and crest make "From the colours" (the shared layout) and "From the logo" (the ice)
                    'colours_used': self.style == looks.STYLE or not (self.ice_why or self.group),
                    'loaded': self.loaded, 'pictures': self.pictures is not None,
                    'colours': {part: {'text': self.typed[part], 'hex': _hex(self._colour(part))}
                                for part in ('primary', 'secondary')},
                    'crest': "Crest: your picture" if self.uniforms['colours'].get('crest') else "Crest: the team's logo",
                    'crest_mine': bool(self.uniforms['colours'].get('crest')),
                    'rows': rows if self.loaded else [],
                    'ice': {'mode': GAME if self.ice_why else self._ice_mode(), 'arena': self.arena,
                            'options': ice_options, 'locked': bool(self.ice_why), 'group': self.ice_note,
                            'why': f"Only the game's own: {self.ice_why}." if self.ice_why else ''},
                    'view': view, 'dirty': self._dirty()}

    def thumbs_view(self):
        with self.lock:
            return dict(self.thumbs) if self.slot is not None else {}
