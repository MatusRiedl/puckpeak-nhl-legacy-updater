"""The parts of "pictures" a player switches on one by one (0.76.0; before, one switch did all of it).

    names       the game's text files (team names, Puck Peak texts) and the main menu: made from the player's disc, no download
    photos      players' photos, club logos, crests, the player's own goalie masks (pack `photos`)
    looks       this season's jerseys, pants and socks (pack `looks`)
    pack_ice    this season's centre ice (pack `looks`; since 0.96.0 a switch of its own)
    arenas      the NHL arenas' newer pictures (pack `arenas`)
    bright_ice  the community's centre ice (pack `ice`; since 0.96.0 a switch of its own; before, it came with `looks`)
    team_masks  the goalie masks of the teams (pack `masks`)

The player's own pictures (Roster editor) go in whatever is switched on. Every part writes its files with a source tag
of its own in the installed-files list (art/install.py `_Writer`), so one part's clean-up never touches another's files
and Restore can undo one part.

Retired: the new scoreboard (`overlay:`, test versions 0.78.0 / 0.80.0; the owner took it out on 2026-10-27, parked in
private/scoreboard). Its files are put back wherever they are found (install.remove_retired).
"""
NAMES, PHOTOS, LOOKS, ARENAS, BRIGHT_ICE, TEAM_MASKS = 'names', 'photos', 'looks', 'arenas', 'bright_ice', 'team_masks'
PACK_ICE = 'pack_ice'
ALL = (NAMES, PHOTOS, LOOKS, PACK_ICE, ARENAS, BRIGHT_ICE, TEAM_MASKS)
LEGACY = frozenset({NAMES, PHOTOS, LOOKS, PACK_ICE})   # what the one switch "Photos, logos and team names" always did
PACK_OF = {PHOTOS: 'photos', LOOKS: 'looks', PACK_ICE: 'looks', ARENAS: 'arenas', BRIGHT_ICE: 'ice', TEAM_MASKS: 'masks'}
# Two sets of centre ice can be on together (0.96.0). The one switched on second is laid over the first (settings
# `ice_order`, the keys in the order they were switched on); this is the order when nothing says: the community's on top.
DEFAULT_ICE_ORDER = (PACK_ICE, BRIGHT_ICE)
# Parts the window shows greyed out and nothing installs (owner, 2026-11-06: the community centre ice showed a grey square
# around the logo for players; it stays in the program, switched off, until it is fixed). Files a player has from before
# go back to the game's own at the next update with pictures (install.remove_disabled).
DISABLED = frozenset({BRIGHT_ICE})
# Packs a part needs besides its own (PACK_OF): this season's centre ice also takes the national teams' shared ice (art
# 501, the IIHF logo of this season's set) from the `ice` pack (art/brightice.py SEASON_ARTS).
MORE_PACKS = {PACK_ICE: ('ice',)}
CENTRE_PATHS = ('rendering/icesurface/centerlogo_', 'rendering/icesurface/icesurface_')   # what this season's centre ice writes

# the tag a part's files carry in the installed-files list (`source` starts with it); photos and logos carry their link
ARENA_TAG, ICE_TAG, TEAM_MASK_TAG, OVERLAY_TAG = 'arenas:', 'ice:', 'teammask:', 'overlay:'
SEASON_ICE_TAG = 'seasonice:'   # this season's centres read from the `ice` pack (art/brightice.py SEASON_ARTS), row pack_ice
TAGS = {NAMES: ('names:', 'menus:'), LOOKS: ('looks:',), PACK_ICE: ('looks:', SEASON_ICE_TAG), ARENAS: (ARENA_TAG,),
        BRIGHT_ICE: (ICE_TAG,), TEAM_MASKS: (TEAM_MASK_TAG,)}
RETIRED_TAGS = (OVERLAY_TAG,)   # parts taken out again: their files go back to the game's own (install.remove_retired)
OTHER_TAGS = tuple(tag for tags in TAGS.values() for tag in tags) + ('crests:', 'mask:') + RETIRED_TAGS


def packs_for(parts):
    """The packs (names in packs.NAMES) the parts need, in the order of ALL (a pack once)."""
    out = []
    for p in ALL:
        if p in parts and p in PACK_OF:
            for name in (PACK_OF[p],) + MORE_PACKS.get(p, ()):
                if name not in out:
                    out.append(name)
    return out


def ice_order(order, parts):
    """The centre-ice parts among `parts`, the first switched on first: `order` (a list of keys, or None), then the
    ones it lacks in DEFAULT_ICE_ORDER."""
    on = [p for p in (order or ()) if p in DEFAULT_ICE_ORDER and p in parts]
    return on + [p for p in DEFAULT_ICE_ORDER if p in parts and p not in on]


def writes_centre(key):
    """Is `key` (a path inside the game's USRDIR) a centre-ice or rink picture file?"""
    return str(key).startswith(CENTRE_PATHS)


def belongs(source, part, key=None):
    """Does an installed file written from `source` belong to `part`? Photos and logos are what no other tag claims
    (crests and the player's own masks go with them). `key`: the file's path; this season's jerseys and centre ice are
    written with one tag, so the path tells which of the two rows a file belongs to."""
    source = str(source or '')
    if part == PHOTOS:
        return not source.startswith(tuple(t for t in OTHER_TAGS if t not in ('crests:', 'mask:')))
    if part in (LOOKS, PACK_ICE) and key is not None:
        return source.startswith(TAGS[part]) and writes_centre(key) == (part == PACK_ICE)
    return source.startswith(TAGS[part])
