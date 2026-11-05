"""Command-line front end.

    list    --rpcs3 <rpcs3.exe>                       roster saves found there (and the game's own roster)
    update  --rpcs3 <rpcs3.exe> [--source <save>]     build and save an updated roster
            [--source disc[:EU|:NA]]                  start from the game's own roster on your disc
            [--leagues nhl,ratings,national,liiga,... | all] [--name "<roster name>"] [--dry-run] [--offline]
            [--for EU|NA|both]                        which version(s) of the game to save it for
            [--in-place]                              update the roster save itself (old one copied first), no new folder
            [--photos]                                also install team names, photos and logos, this season's jerseys (RPCS3 closed)
            [--names] [--looks] [--pack-ice] [--arenas] [--bright-ice] [--team-masks]   the parts one by one (each downloads only its own pack)
            [--edits]                                apply your edits from the window's Roster editor
                                                      a patched RPCS3 (game-patch install) gets a roster for 32
                                                      teams and the year 2026, an unpatched one a normal roster
            [--game-patch [--skip-intro] [--no-login]]   patch RPCS3 first (RPCS3 closed), then update
    game-patch install [--skip-intro] [--no-login] | status | remove | online | online-off --rpcs3 <rpcs3.exe>
                                                      patch the game for 32 teams and the year 2026, is it patched,
                                                      take the patch out again
    export-roster --file <SYS-DATA> [--out <folder>] [--for-patch]   update a roster file without RPCS3: writes a new
                                                      SYS-DATA folder next to the program (--for-patch: for a patched game)
    photos remove [--part names|photos|looks|pack_ice|arenas|bright_ice|team_masks]   take the pictures away again (all, or only that part)
    packs download | status | remove                  the pictures for --photos: download them now, show what is on
                                                      this PC, free the space (update --photos downloads by itself)
    export-files [--rpcs3 <rpcs3.exe> | --savedata <folder>] [--source <save>|<SYS-DATA>] --out <folder> [--photos]
            [--game-patch] [--version EU|NA|both] [--game <iso>]   the files an update would put into RPCS3, in a new folder
                                                      to copy by hand (RPCS3 is not touched; prints how to install them)
    stock-test --rpcs3 <rpcs3.exe> [--version EU|NA]  the in-game check of the game's own roster (two LAB rosters)
    draft-test --rpcs3 <rpcs3.exe> [--source <save>]  the in-game check of where the draft finds prospects
    rendering-test --rpcs3 <rpcs3.exe> [--version EU|NA]   Utah's jerseys and centre-ice logo as loud loose files (in-game test)
    looks-test --rpcs3 <rpcs3.exe> [--version EU|NA]   the new Utah, Seattle and Vegas jerseys and centre-ice logos as loose files (in-game test)
    equipment-test --rpcs3 <rpcs3.exe> [--source <save>|file:<SYS-DATA>]   LAB roster: every tuck / tape colour on a player (in-game test)
    calendar-test --rpcs3 <rpcs3.exe> [--source <save>|file:<SYS-DATA>]   LAB rosters with the real 2026-27 calendar (in-game test)
    year-test --rpcs3 <rpcs3.exe> [--source <save>|file:<SYS-DATA>]   a LAB roster for the year 2026 game patch, and the patch file
    team32-test --rpcs3 <rpcs3.exe> [--source <save>|file:<SYS-DATA>] [--photos] [--version EU|NA]   a LAB roster for the 32-team game patch, the patch file and the game's database description
    season-test --rpcs3 <rpcs3.exe> [--source <save>|disc]   LAB rosters with more and more update steps: which one crashes Season mode
    export  --rpcs3 <rpcs3.exe> [--source <save>] --out <folder>    every table as CSV, real names

--savedata <folder> can be given instead of --rpcs3 when the saves are not in an RPCS3 folder.
"""
import argparse
import os
import sys

from . import APP_NAME, __version__, datasource, edits, layout, pipeline, savedata
from .builder import Data
from .roster import Roster
from .tdb import RosterFile

RPCS3_HELP = ("your rpcs3.exe or NHLLauncher.exe (or the folder it is in)" if savedata.WINDOWS else
              "your RPCS3: the rpcs3 program, its AppImage, RPCS3.app, or RPCS3's data folder")


def _find(args):
    """RPCS3 from --rpcs3; --game (the .iso or its folder) says where the game is when RPCS3 does not know."""
    games = {}
    for path in getattr(args, 'game', None) or []:
        title = savedata.game_title_id(path)
        if title not in savedata.GAMES:
            sys.exit(f"{path} is not a copy of NHL Legacy Edition (give the .iso file or the folder with PS3_GAME)")
        games[title] = path
    from .art import install
    found = savedata.find_rpcs3(args.rpcs3, games=games or None)
    install.use_host(found)
    return found


def _folder(args):
    """(savedata folder, roster folder pointed at or None) from --rpcs3 or --savedata."""
    if args.rpcs3:
        return _find(args).savedata, None
    return savedata.find_savedata(args.savedata)


def _disc_slot(args, wanted='disc'):
    """The game's own roster on the disc RPCS3 has (`wanted`: 'disc', 'disc:EU' or 'disc:NA')."""
    if not args.rpcs3:
        sys.exit("the game's own roster needs --rpcs3 <rpcs3.exe>: the disc is found from RPCS3's games list")
    found = _find(args)
    region = wanted.partition(':')[2].upper()
    slots = [s for s in found.disc_slots() if not region or s.region == region]
    if not slots:
        sys.exit("RPCS3 does not list " + (f"the {region} version of " if region else "") + "the game, so its own "
                 "roster cannot be read. Start the game once from RPCS3's game list.")
    return found.savedata, slots[0]


def _source(args):
    wanted = getattr(args, 'source', None)
    if wanted and wanted.lower().startswith('disc'):
        return _disc_slot(args, wanted.lower())
    folder, preselected = _folder(args)
    slots = savedata.list_rosters(folder)
    if not slots and not wanted:
        return _disc_slot(args)             # no roster saved yet: the game's own roster
    wanted = wanted or preselected
    if wanted:
        slot = next((s for s in slots if s.folder == wanted or s.name == wanted), None)
        if slot is None:
            sys.exit(f"roster save '{wanted}' not found in {folder}")
        return folder, slot
    return folder, slots[0]


def cmd_list(args):
    folder, _ = _folder(args)
    print(folder)
    slots = savedata.list_rosters(folder)
    titles = sorted({s.title_id for s in slots})
    hidden = set().union(*(savedata.hidden_in_game(folder, t) for t in titles)) if titles else set()
    for s in slots:
        try:
            kind = layout.check_base(Roster(s.sys_data))
            status = "ok" if kind == layout.COMMUNITY else "ok (the game's own roster)"
        except (layout.LayoutError, ValueError) as err:
            status = f"not usable: {err}"
        if s.folder in hidden:
            status += "  (the game does not show it: it lists only 10)"
        print(f"  {s.folder}  {s.region:<3} {s.name:<24} {s.modified:%Y-%m-%d %H:%M}  {status}")
    for t in titles:
        print(f"  {savedata.region(t)}: {savedata.roster_count(folder, t)} of {savedata.GAME_LISTS} rosters the game lists")
    if args.rpcs3:
        for s in _find(args).disc_slots():
            print(f"  disc:{s.region}        {s.region:<3} {s.name}  (from {s.path})")


def cmd_export_roster(args):
    """Update a roster file without RPCS3 or a save folder: the new SYS-DATA goes into a new folder."""
    pack = datasource.load_pack(offline=True)
    available = pipeline.steps_for(pack)
    steps = available if args.leagues == 'all' else pipeline.default_steps(pack) if args.leagues == 'default' \
        else [s for s in args.leagues.split(',') if s]
    unknown = [s for s in steps if s not in available]
    if unknown:
        sys.exit(f"unknown or unavailable: {', '.join(unknown)}; choose from {', '.join(available)}")
    try:
        res = pipeline.export_sysdata(args.file, steps, args.name, print, args.offline,
                                      my_edits=edits.load() if args.edits else None,
                                      team_edits=edits.load_teams() if args.edits else None, out_root=args.out,
                                      game_patch=args.for_patch)
    except (FileNotFoundError, layout.LayoutError, datasource.Offline) as err:
        sys.exit(str(err))
    for line in res.build.summary():
        print(line)
    if not res.build.ok:
        for p in res.build.problems[:40]:
            print("  problem:", p)
        sys.exit(2)
    print("Report:", res.report_path)
    print("New SYS-DATA:", res.exported)


def cmd_export_files(args):
    """Everything an update would put into RPCS3, as files in a new folder: nothing is written to RPCS3."""
    from . import export
    pack = datasource.load_pack(offline=True)
    available = pipeline.steps_for(pack)
    steps = available if args.leagues == 'all' else pipeline.default_steps(pack) if args.leagues == 'default' \
        else [s for s in args.leagues.split(',') if s]
    unknown = [s for s in steps if s not in available]
    if unknown:
        sys.exit(f"unknown or unavailable: {', '.join(unknown)}; choose from {', '.join(available)}")
    wanted = args.source
    rpcs3, source = None, None
    if args.rpcs3:
        rpcs3 = _find(args)
    elif args.savedata:
        try:
            rpcs3, _ = savedata.open_saves(args.savedata)
        except FileNotFoundError as err:
            sys.exit(str(err))
    if wanted and os.path.isfile(wanted):
        source = wanted                                   # a SYS-DATA file: no RPCS3 needed
    elif rpcs3 is None:
        sys.exit("--export-files needs --rpcs3 <rpcs3.exe>, --savedata <folder>, or --source <a SYS-DATA file>")
    else:
        source = _source(args)[1]
    targets = None
    if args.save_for:
        targets = list(savedata.GAMES) if args.save_for.lower() == 'both' else [savedata.title_of(args.save_for)]
        if None in targets:
            sys.exit("--version takes EU, NA or both")
    games = {}
    for path in args.game or []:
        title = savedata.game_title_id(path)
        if title not in savedata.GAMES:
            sys.exit(f"{path} is not a copy of NHL Legacy Edition (give the .iso file or the folder with PS3_GAME)")
        games[title] = path
    if (args.skip_intro or args.no_login) and not args.game_patch:
        sys.exit("--skip-intro and --no-login go with --game-patch")
    if args.photos and not args.offline:
        _download_packs()
    try:
        res = export.run(args.out, source, rpcs3=rpcs3, steps=steps, targets=targets, name=args.name,
                         photos=args.photos, game_patch=args.game_patch, intro=args.skip_intro, login=args.no_login,
                         my_edits=edits.load() if args.edits else None,
                         team_edits=edits.load_teams() if args.edits else None, progress=print, offline=args.offline,
                         games=games, art_parts=_photo_parts() if args.photos else None, ice_order=_ice_order())
    except (export.ExportError, FileNotFoundError, layout.LayoutError, datasource.Offline, RuntimeError) as err:
        sys.exit(str(err))
    for line in res.update.build.summary():
        print(line)
    if res.folder is None:
        for p in res.update.build.problems[:40]:
            print("  problem:", p)
        sys.exit(2)
    print()
    print(res.text)
    print("Files:", res.folder)


def cmd_update(args):
    pack = datasource.load_pack(offline=True)
    available = pipeline.steps_for(pack)
    if args.leagues == 'all':
        steps = available
    elif args.leagues == 'default':
        steps = pipeline.default_steps(pack)
    else:
        steps = [s for s in args.leagues.split(',') if s]
    unknown = [s for s in steps if s not in available]
    if unknown:
        sys.exit(f"unknown or unavailable: {', '.join(unknown)}; choose from {', '.join(available)}")
    folder, slot = _source(args)
    if args.in_place and (getattr(slot, 'disc', False) or (args.save_for and args.save_for.lower() not in
                                                         (slot.region.lower(),))):
        sys.exit("--in-place updates a roster save in its own version of the game; the game's own roster and the "
                 "other version need a new roster (leave --in-place out)")
    targets = None
    if args.save_for:
        wanted = list(savedata.GAMES) if args.save_for.lower() == 'both' else [savedata.title_of(args.save_for)]
        if None in wanted:
            sys.exit("--for takes EU, NA or both")
        targets = wanted
    rpcs3 = _find(args) if args.rpcs3 else None     # the roster follows RPCS3: patched or not (game-patch install)
    game_patch = None
    if args.game_patch:
        if rpcs3 is None:
            sys.exit("--game-patch needs --rpcs3 <rpcs3.exe>: the patch goes into that RPCS3")
        game_patch = True
        if not args.dry_run:
            from . import patchinstall
            try:
                patchinstall.install_patch(rpcs3, rpcs3.games(), intro=args.skip_intro, login=args.no_login)
            except (RuntimeError, datasource.Offline, OSError) as err:
                sys.exit(str(err))
    elif args.skip_intro or args.no_login:
        sys.exit("--skip-intro and --no-login go with --game-patch")
    art_rpcs3, art_parts = None, _art_parts(args)
    if args.photos or art_parts:
        if not args.rpcs3:
            sys.exit("--photos and the other picture switches need --rpcs3 <rpcs3.exe>: the pictures go into RPCS3's game folder")
        art_rpcs3 = _find(args)
        if not args.offline and not args.dry_run:
            _download_packs(art_parts)
    data = None
    if args.research:      # saved inputs instead of live data (tests, reproducing an old build)
        r = datasource.load_research_dir(args.research)
        data = Data(nhl_players=datasource.flatten_nhl(r['teams'], r['extra']) if pipeline.NHL in steps else [],
                    ratings_list=r['ratings_list'] if pipeline.RATINGS in steps else None,
                    iihf=r['iihf'] if pipeline.NATIONAL in steps else None,
                    leagues={k: v for k, v in pack.get('leagues', {}).items() if k in steps})
    try:
        mine = edits.load() if args.edits else None
        teams = edits.load_teams() if args.edits else None
        if args.edits:
            print(f"My edits: {len(mine)} players, {len(teams)} teams from {edits.path()}")
        res = pipeline.update(folder, slot.folder, steps, args.name, print, args.offline, args.dry_run, data,
                              art_rpcs3=art_rpcs3, my_edits=mine, team_edits=teams,
                              targets=targets, disc=slot if getattr(slot, 'disc', False) else None,
                              in_place=args.in_place, rpcs3=rpcs3, game_patch=game_patch, art_parts=art_parts,
                              ice_order=_ice_order())
    except layout.LayoutError as err:    # e.g. EU patched, NA not, saving for both
        sys.exit(str(err))
    except RuntimeError as err:         # photos and logos: RPCS3 running, game not found; in place: refused
        sys.exit(str(err))
    for line in res.build.summary() + ([res.art_line()] if res.art_line() else []) + res.patch_lines():
        print(line)
    if not res.build.ok:
        for p in res.build.problems[:40]:
            print("  problem:", p)
        sys.exit(2)
    print("Report:", res.report_path)
    if res.slot and res.in_place:
        print("Already up to date." if res.unchanged else f"Updated {res.saved_where()}.")
        if res.backup:
            print(f"The old roster is kept in {res.backup}")
        print(f"In the game: start it; if \"{res.slot.name}\" is not the roster in use, Customize > Save/Load/Delete > "
              "Load > Rosters, then save it once.")
    elif res.slot:
        print(f"Saved in {res.saved_where()}.")
        print(f"In the game: Customize > Save/Load/Delete > Load > Rosters > \"{res.slot.name}\", then save it once.")
    else:
        print("Dry run: nothing was written.")


def cmd_stock_test(args):
    """The owner's in-game check of the game's own roster: two LAB rosters, one as the disc has it
    (does the game load a roster made from its own database?), one updated (does it play?)."""
    from . import stock
    folder, slot = _disc_slot(args, f"disc:{args.version}" if args.version else 'disc')
    try:
        raw = slot.read()
        plain = savedata.install(folder, slot, raw, "LAB game roster as is")
        print(f"Saved \"{plain.name}\" in {plain.folder}.")
        res = pipeline.update(folder, None, pipeline.default_steps(datasource.load_pack(offline=True)),
                              "LAB game roster updated", print, disc=slot)
    except (RuntimeError, stock.StockError) as err:
        sys.exit(str(err))
    if not res.build.ok:
        for p in res.build.problems[:40]:
            print("  problem:", p)
        sys.exit(2)
    print(f"Saved \"{res.slot.name}\" in {res.saved_where()}.")
    print("In the game: Customize > Save/Load/Delete > Load > Rosters, load each LAB roster in turn and check what "
          "docs/ROADMAP.md (\"The game's own roster\") lists.")


def _lab_source(args, allow_disc=True):
    """(save folder, starting roster) of an in-game test: a roster save, `file:<SYS-DATA>` (a roster file as
    downloaded) or, for the tests that can, `disc` (the game's own roster)."""
    from . import seasontest
    if allow_disc and args.source and args.source.lower().startswith('disc'):
        return _disc_slot(args, args.source.lower())
    folder = _find(args).savedata
    saves = savedata.list_rosters(folder)
    if args.source and args.source.lower().startswith('file:'):
        path = args.source[5:].strip('"')
        if not os.path.isfile(path) or not saves:
            sys.exit("the roster file was not found (or there is no roster save to take the icon from)")
        return folder, seasontest.file_slot(saves[0], path)
    slot = seasontest.pick_source(saves, args.source)
    if slot is None:
        sys.exit("no roster save to start from" + (f" ({args.source})" if args.source else ""))
    return folder, slot


def cmd_rendering_test(args):
    """The owner's in-game check that the game takes 3D textures (jerseys, the ice) from loose files."""
    from .art import install, rendering
    found = _find(args)
    title = {'EU': 'BLES02153', 'NA': 'BLUS31540'}.get(args.version) if args.version else next(
        (t for t in savedata.GAMES if found.game_disc(t)), None)
    if title is None:
        sys.exit("RPCS3 does not list the game, so the textures cannot be made. Start the game once from RPCS3's game list.")
    try:
        n = rendering.rendering_test(found, title, print)
    except install.ArtError as err:
        sys.exit(str(err))
    print(f"Wrote {n} files into the game folder of {savedata.region(title)}. In the game: Play Now, pick the Utah "
          "Mammoth as the home team, start a game: the jerseys should be BLUE (not red) and the centre-ice logo a "
          "magenta/yellow circle with UTAH TEST. Then pick Utah as the visitor: the same for the away jersey. Tell us "
          "which of the three show. Afterwards: 'photos remove' (the window's \"Restore the game's own pictures\").")


def cmd_looks_test(args):
    """The owner's in-game check of the new Utah, Seattle and Vegas jerseys and centre-ice logos."""
    from .art import install, looks
    from .art.photopack import PhotoPack, PictureCache
    found = _find(args)
    title = {'EU': 'BLES02153', 'NA': 'BLUS31540'}.get(args.version) if args.version else next(
        (t for t in savedata.GAMES if found.game_disc(t)), None)
    if title is None:
        sys.exit("RPCS3 does not list the game, so the textures cannot be made. Start the game once from RPCS3's game list.")
    pack = datasource.load_pack(offline=True)
    try:
        made = looks.default_looks(pack['nhl_logos'], PhotoPack.open(), PictureCache())
        n = looks.install_looks(found, title, made, print)
    except install.ArtError as err:
        sys.exit(str(err))
    print(f"Wrote {n} files into the game folder of {savedata.region(title)}. In the game: Play Now, pick the Utah Mammoth "
          "(then Seattle Kraken, then Vegas Golden Knights) as home and as visitor: look at the jerseys on the Select "
          "Jerseys screen (press the left stick to change jerseys) and in the game, and at the centre-ice logo. "
          "Afterwards: 'photos remove' (the window's \"Restore the game's own pictures\").")


def cmd_equipment_test(args):
    """The owner's in-game check of the equipment numbers (tucks, tape, visor tint, pads, pants): one LAB roster."""
    from . import equipmenttest
    try:
        folder, slot = _lab_source(args, allow_disc=False)
        equipmenttest.equipment_test(folder, slot, print)
    except (RuntimeError, ValueError) as err:
        sys.exit(str(err))
    print("Saved the roster \"EQUIPMENT TEST\". In the game: Customize > Save/Load/Delete > Load > Rosters, then Edit Players > Anaheim or Winnipeg > "
          "each player > Customization: do the game's words match the list above?")


def cmd_year_test(args):
    """The owner's in-game check of the year patch: a LAB roster made for it and the patch file."""
    from . import calendartest
    try:
        folder, slot = _lab_source(args, allow_disc=False)
        calendartest.year_test(folder, slot, print)
    except (RuntimeError, ValueError) as err:
        sys.exit(str(err))


def cmd_team32_test(args):
    """The owner's in-game check of the 32-team patch: a LAB roster made for it, the patch file with every entry, and the
    game's database description for 32 teams in that RPCS3's game folder (RPCS3 closed; undo: game-patch remove)."""
    from . import calendartest
    try:
        folder, slot = _lab_source(args, allow_disc=False)
        rpcs3 = _find(args)
        calendartest.team32_test(folder, slot, print, art_rpcs3=rpcs3 if args.photos else None, rpcs3=rpcs3,
                                 title_id={'EU': 'BLES02153', 'NA': 'BLUS31540'}.get(args.version))
    except (RuntimeError, ValueError) as err:          # also install.ArtError (RPCS3 running, game not found)
        sys.exit(str(err))


def cmd_calendar_test(args):
    """The owner's in-game check of the 2026-27 calendar: LAB rosters with the real schedule written in."""
    from . import calendartest
    try:
        folder, slot = _lab_source(args, allow_disc=False)
        saved = calendartest.calendar_test(folder, slot, print)
    except (RuntimeError, ValueError) as err:
        sys.exit(str(err))
    print(f"Saved {len(saved)} rosters. In the game: Customize > Save/Load/Delete > Load > Rosters, load each \"CAL\" roster in "
          "turn, then Season mode > Select Team > Calendar (docs/ROADMAP.md, \"Calendar\"; the list above says what to look at).")


def cmd_season_test(args):
    """The owner's in-game check of Season mode: four LAB rosters (core, + Europe, + AHL, + everything)
    made from the community roster (or one from the game's own roster)."""
    from . import seasontest, stock
    try:
        folder, slot = _lab_source(args)
        saved = seasontest.season_test(folder, slot, print)
    except (RuntimeError, stock.StockError) as err:
        sys.exit(str(err))
    print(f"Saved {len(saved)} rosters. In the game: Customize > Save/Load/Delete > Load > Rosters, load each \"SEASON\" roster in "
          "turn, then Season mode > pick a team and wait for it to load (docs/ROADMAP.md, \"Season mode crash\").")


def cmd_export(args):
    _, slot = _source(args)
    RosterFile(data=savedata.read_roster(slot)).export_csv(args.out)
    print(f"{slot.name} exported to {args.out}")


def cmd_photos(args):
    from .art import install
    try:
        if args.part:
            install.remove_parts(args.part)
        else:
            install.remove()
    except RuntimeError as err:
        sys.exit(str(err))


def _photo_parts(chosen=None):
    """`chosen` (default --photos: team names, photos and logos, this season's jerseys and centre ice) with both centre
    ices when this season's jerseys are in it (as since 0.80.0; 0.96.0: the window has a switch for each)."""
    from .art import parts
    chosen = set(parts.LEGACY if chosen is None else chosen)
    return frozenset(chosen | ({parts.PACK_ICE, parts.BRIGHT_ICE} if parts.LOOKS in chosen else set()))


def _ice_order(argv=None):
    """The two centre ices in the order the options named them (--pack-ice, --bright-ice): the second lies over the first.
    Nothing or one named: None (the community's on top, as before)."""
    argv = list(sys.argv if argv is None else argv)
    at = {name: argv.index(flag) for name, flag in (('pack_ice', '--pack-ice'), ('bright_ice', '--bright-ice')) if flag in argv}
    return sorted(at, key=at.get) if len(at) == 2 else None


def _art_parts(args):
    """The picture parts the options ask for (art/parts.py), or None: --photos alone is team names, photos and logos and
    this season's jerseys and centre ice. The other switches add to it: --arenas alone is only the arenas."""
    from .art import parts
    extra = {p for p, flag in ((parts.NAMES, args.names), (parts.LOOKS, args.looks), (parts.ARENAS, args.arenas),
                               (parts.PACK_ICE, args.pack_ice), (parts.BRIGHT_ICE, args.bright_ice),
                               (parts.TEAM_MASKS, args.team_masks)) if flag}
    if not extra and not args.photos:
        return None
    return _photo_parts(extra | (parts.LEGACY if args.photos else set()))


def _download_packs(art_parts=None):
    """The pictures for --photos (packs.py): what is missing or changed, with a line per tenth. `art_parts`: only the
    packs these parts need (default: --photos's)."""
    from . import packs
    from .art import parts
    wanted = parts.packs_for(art_parts if art_parts is not None else _photo_parts())
    listed = packs.manifest()
    names = packs.missing(listed, wanted) if listed is not None else []
    if names:
        print(f"Downloading the pictures ({packs.size_of(listed, names) / 1e6:.0f} MB)...")
    shown = [-1]

    def step(at):
        if int(at * 10) > shown[0]:
            shown[0] = int(at * 10)
            print(f"   {int(at * 100)} %")
    done, why = packs.sync(step if names else None, listed=listed, wanted=wanted) if listed is not None else ([], 'offline')
    if why:
        have = [n for n in wanted if packs.have(n)]
        print("The pictures were not downloaded" + ("" if why == 'offline' else f" ({why})") + ": "
              + ("the copy on this PC is used." if have else "photos come one by one, jerseys stay the game's own."))
    return done


def cmd_names(args):
    """The picked roster's team names into the game: no roster saved, no picture touched."""
    from . import edits
    from .art.install import ArtError
    folder, slot = _source(args)
    with open(slot.sys_data, 'rb') as f:
        data = f.read()
    try:
        count = pipeline.apply_names(_find(args), data, slot.title_id, team_edits=edits.load_teams() if args.edits else None)
    except ArtError as err:
        sys.exit(str(err))
    print(f"Team names of {slot.name}: {count} teams. Your graphics were not touched.")


def cmd_packs(args):
    from . import packs
    if args.action == 'download':
        _download_packs()
    elif args.action == 'remove':
        print(f"Removed {packs.remove_all() / 1e6:.0f} MB. What an update put into the game stays "
              "(photos remove takes it away).")
    for name, have in packs.status().items():
        print(f"   {name}: " + (f"{have[0]}, {have[1] / 1e6:.0f} MB" if have else "not on this PC"))
    print(f"   folder: {packs.folder()}")


def cmd_game_patch(args):
    from . import patchinstall
    rpcs3 = _find(args)
    if args.action != 'install' and (args.skip_intro or args.no_login):
        sys.exit("--skip-intro and --no-login go with 'game-patch install'")
    try:
        if args.action == 'remove':
            patchinstall.remove(rpcs3)
            return
        if args.action == 'install':
            patchinstall.install_patch(rpcs3, rpcs3.games(), intro=args.skip_intro, login=args.no_login)
            print("Now update a roster with --rpcs3: it is made for the patched game.")
            return
        if args.action in ('online', 'online-off'):
            patchinstall.set_online(rpcs3, rpcs3.games(), args.action == 'online')
            return
    except (RuntimeError, datasource.Offline, OSError) as err:     # RPCS3 running, no disc
        sys.exit(str(err))
    if not rpcs3.patchable and not rpcs3.native:
        print("Not patched: the game patch needs RPCS3.")
        return
    for title, st in patchinstall.state(rpcs3).items():
        if st['online']:
            print(f"{savedata.region(title)}: online play is set up")
        if st['patched']:
            extra = [what for what, on in (("the intro skipped", st['intro']), ("no pop-ups at start", st['login'])) if on]
            print(f"{savedata.region(title)}: patched for 32 teams and the year 2026 ({st['version']}, game "
                  f"{st['game']})" + (f", {', '.join(extra)}" if extra else ""))
        elif st['stale'] and rpcs3.native:
            print(patchinstall.PORT_OTHER + " Run game-patch remove.")
        elif st['stale']:
            print(f"{savedata.region(title)}: the game has update {st['game']}, the patch ({st['version']}) is older: "
                  "run game-patch install again")
        else:
            print(f"{savedata.region(title)}: not patched")


def cmd_league_test(args):
    from .art import lab
    try:
        lab_slot = lab.league_test(_find(args), args.source)
    except RuntimeError as err:
        sys.exit(str(err))
    print(f"In the game: Customize > Save/Load/Delete > Load > Rosters > \"{lab_slot.name}\". Then look, as docs/ROADMAP.md "
          "(\"League test\") says, whether Coachella and Henderson are in the AHL list, Jokerit in Liiga, Ajoie in "
          "the National League and Penticton in the WHL, and play one game with each.")


def cmd_draft_test(args):
    from .art import lab
    try:
        lab_slot = lab.draft_test(_find(args), args.source)
    except RuntimeError as err:
        sys.exit(str(err))
    print(f"In the game: Customize > Save/Load/Delete > Load > Rosters > \"{lab_slot.name}\". Start Be a GM and open the list of "
          "draft prospects (scouting or the draft); if there is none yet, simulate to the draft. Tell us which of "
          "the names above are in it (docs/ROADMAP.md, \"Draft test\").")


def cmd_art_test(args):
    from .art import lab
    try:
        if args.action == 'remove':
            lab.remove()
            return
        if not args.rpcs3:
            sys.exit("art-test install needs --rpcs3 <rpcs3.exe>")
        lab_slot = lab.install(_find(args), args.source)
    except RuntimeError as err:          # RPCS3 running, test already installed: a sentence for the user
        sys.exit(str(err))
    print(f"In the game: Customize > Save/Load/Delete > Load > Rosters > \"{lab_slot.name}\". Then look at the pictures "
          "listed in docs/ROADMAP.md (\"Art test\"). Afterwards: art-test remove.")


def main(argv=None):
    ap = argparse.ArgumentParser(prog='PuckPeakLegacyUpdater', description=f"{APP_NAME} {__version__}")
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name, fn, text in (('list', cmd_list, "show the roster saves in a savedata folder"),
                           ('update', cmd_update, "build an updated roster and save it as a new roster save"),
                           ('export', cmd_export, "dump every table of a roster save to CSV")):
        p = sub.add_parser(name, help=text)
        p.set_defaults(fn=fn)
        where = p.add_mutually_exclusive_group(required=True)
        where.add_argument('--rpcs3', help=RPCS3_HELP + "; the saves are found from there")
        where.add_argument('--savedata',
                           help="instead of --rpcs3: a savedata folder, anything above it, or one roster save folder")
        p.add_argument('--game', action='append', metavar='ISO_OR_FOLDER',
                       help="where your NHL Legacy game is (.iso or its folder), when RPCS3 does not list it; "
                            "repeat for the EU and the NA game")
        if name != 'list':
            p.add_argument('--source', help="roster save to start from (folder or roster name), or disc / disc:EU / "
                                            "disc:NA for the game's own roster; default: the newest save")
        if name == 'update':
            p.add_argument('--leagues', default='default',
                           help="comma list of " + ', '.join(pipeline.CORE_STEPS + pipeline.LEAGUE_ORDER)
                                + ", or 'all'; default: everything the data pack has")
            p.add_argument('--name', help="in-game name of the new roster (default: current date and time)")
            p.add_argument('--for', dest='save_for', metavar='EU|NA|both',
                           help="the version(s) of the game to save the new roster for (default: the version "
                                "of the roster it starts from); the two read the same roster file")
            p.add_argument('--dry-run', action='store_true', help="build and check, but write nothing")
            p.add_argument('--in-place', action='store_true',
                           help="update the roster save itself instead of making a new one (its old files are "
                                "copied to the program's backups folder first; RPCS3 must be closed)")
            p.add_argument('--offline', action='store_true', help="use the data shipped with the program only")
            p.add_argument('--photos', action='store_true',
                           help="also install current photos and logos into RPCS3's game folder (new; RPCS3 must "
                                "be closed; 'photos remove' takes them away); with team names and this season's jerseys and centre ice")
            p.add_argument('--names', action='store_true', help="team names, short codes and menu texts in the game (RPCS3 closed)")
            p.add_argument('--looks', action='store_true', help="this season's jerseys, with both centre ices (the community's on top; downloads the look and ice packs)")
            p.add_argument('--pack-ice', action='store_true', help="only this season's centre ice (downloads the look pack; name --pack-ice and --bright-ice both: the second lies over the first)")
            p.add_argument('--arenas', action='store_true', help="the NHL arenas' newer pictures (downloads the arena pack)")
            p.add_argument('--bright-ice', action='store_true', help="only the community's centre ice for 30 NHL teams (downloads the ice pack; --looks has it too)")
            p.add_argument('--team-masks', action='store_true', help="the goalie masks of the teams (downloads the mask pack)")
            p.add_argument('--edits', action='store_true',
                           help="apply your own edits from the window's Roster editor after the update")
            p.add_argument('--game-patch', action='store_true',
                           help="patch the game in RPCS3 for 32 teams and the year 2026 first (as 'game-patch install'; "
                                "RPCS3 must be closed), then make the roster for it ('game-patch remove' takes it out)")
            p.add_argument('--skip-intro', action='store_true', help="with --game-patch: start at the main menu, no intro")
            p.add_argument('--no-login', action='store_true',
                           help="with --game-patch: no pop ups at start (no sign-in boxes; online modes still sign in when opened)")
            p.add_argument('--research', help=argparse.SUPPRESS)
        if name == 'export':
            p.add_argument('--out', required=True)
    p = sub.add_parser('export-roster', help="update a roster file (SYS-DATA) without RPCS3: the new SYS-DATA goes into a new folder")
    p.set_defaults(fn=cmd_export_roster)
    p.add_argument('--file', required=True, help="the roster's SYS-DATA file (the community roster)")
    p.add_argument('--out', help="the folder to make the new one in (default: next to the program)")
    p.add_argument('--leagues', default='default', help="nhl,ratings,national,liiga,... | all | default")
    p.add_argument('--name')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--edits', action='store_true', help="apply your edits from the window's Roster editor")
    p.add_argument('--for-patch', action='store_true', help="make it for a game patched for 32 teams and the year 2026")
    p = sub.add_parser('export-files', help="make the files an update would put into RPCS3 (roster, pictures, game patch) "
                                            "in a new folder, to copy over by hand; RPCS3 is not touched")
    p.set_defaults(fn=cmd_export_files)
    p.add_argument('--rpcs3', help=RPCS3_HELP + " (read only)")
    p.add_argument('--savedata', help="instead of --rpcs3: a savedata folder or one roster save folder (read only)")
    p.add_argument('--source', help="a roster file (SYS-DATA), or with --rpcs3 / --savedata a roster save (folder or "
                                    "name) or disc / disc:EU / disc:NA; default: the newest save")
    p.add_argument('--out', help="the folder to make the new one in (default: next to the program)")
    p.add_argument('--game', action='append', metavar='ISO_OR_FOLDER', help="where your NHL Legacy game is (.iso or its folder)")
    p.add_argument('--version', '--for', dest='save_for', metavar='EU|NA|both', help="the version(s) of the game to make it for")
    p.add_argument('--leagues', default='default', help="nhl,ratings,national,liiga,... | all | default")
    p.add_argument('--name')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--photos', action='store_true', help="also make the photos, logos and names (needs the game)")
    p.add_argument('--edits', action='store_true', help="apply your edits from the window's Roster editor")
    p.add_argument('--game-patch', action='store_true', help="also make the game patch files (32 teams, the year 2026; needs the game)")
    p.add_argument('--skip-intro', action='store_true', help="with --game-patch: offer the 'skip the intro' entry")
    p.add_argument('--no-login', action='store_true', help="with --game-patch: offer the 'no pop ups at start' entry")
    p = sub.add_parser('game-patch', help="patch the game for 32 teams and the year 2026, is it patched, take the patch "
                                          "out again")
    p.set_defaults(fn=cmd_game_patch)
    p.add_argument('action', choices=('install', 'status', 'remove', 'online', 'online-off'))
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--skip-intro', action='store_true', help="with install: start at the main menu, no intro")
    p.add_argument('--no-login', action='store_true',
                   help="with install: no pop ups at start (no sign-in boxes; online modes still sign in when opened)")
    p = sub.add_parser('photos', help="remove the installed photos and logos (every file goes back as it was)")
    p.set_defaults(fn=cmd_photos)
    p.add_argument('action', choices=('remove',))
    p.add_argument('--part', action='append', choices=('names', 'photos', 'looks', 'pack_ice', 'arenas', 'bright_ice', 'team_masks'),
                   help="take away only this part (repeat for more); default: all of them")
    p = sub.add_parser('names', help="write the team names of a roster into the game, and nothing else")
    p.set_defaults(fn=cmd_names)
    p.add_argument('action', choices=('apply',))
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--savedata', help=argparse.SUPPRESS)
    p.add_argument('--game', action='append', metavar='ISO_OR_FOLDER', help="where your NHL Legacy game is, when RPCS3 does not list it")
    p.add_argument('--source', help="roster save to take the names from (folder or roster name); default: the newest save")
    p.add_argument('--edits', action='store_true', help="with your own team names from the window's Roster editor")
    p = sub.add_parser('packs', help="the pictures for --photos: download them now, show them, free the space")
    p.set_defaults(fn=cmd_packs)
    p.add_argument('action', choices=('download', 'status', 'remove'))
    p = sub.add_parser('stock-test', help="save two LAB rosters made from the game's own roster (in-game test)")
    p.set_defaults(fn=cmd_stock_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--version', choices=('EU', 'NA'), help="which version's disc (default: the first RPCS3 lists)")
    p = sub.add_parser('rendering-test', help="write loud Utah jerseys and centre-ice logo as loose files (in-game test)")
    p.set_defaults(fn=cmd_rendering_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--version', choices=('EU', 'NA'), help="which version's game folder (default: the first RPCS3 lists)")
    p = sub.add_parser('looks-test', help="write the new Utah, Seattle and Vegas jerseys and ice logos as loose files (in-game test)")
    p.set_defaults(fn=cmd_looks_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--version', choices=('EU', 'NA'), help="which version's game folder (default: the first RPCS3 lists)")
    p = sub.add_parser('calendar-test', help="save LAB rosters with the real 2026-27 calendar (in-game test)")
    p.set_defaults(fn=cmd_calendar_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--source', help="roster save to start from, or file:<a roster file such as a downloaded community "
                                    "SYS-DATA> (default: the newest roster this program did not make)")
    p = sub.add_parser('equipment-test', help="save a LAB roster with every tuck, tape colour ... on a player (in-game test)")
    p.set_defaults(fn=cmd_equipment_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--source', help="roster save to start from, or file:<a roster file> (default: the newest roster this "
                                    "program did not make)")
    p = sub.add_parser('year-test', help="save a LAB roster for the year 2026 game patch, and the patch file (in-game test)")
    p.set_defaults(fn=cmd_year_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--source', help="roster save to start from, or file:<a roster file such as a downloaded community "
                                    "SYS-DATA> (default: the newest roster this program did not make)")
    p = sub.add_parser('team32-test', help="save a LAB roster for the 32-team game patch, the patch file and the game's "
                                                   "database description for 32 teams (in-game test; RPCS3 closed)")
    p.set_defaults(fn=cmd_team32_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--source', help="roster save to start from, or file:<a roster file such as a downloaded community "
                                    "SYS-DATA> (default: the newest roster this program did not make)")
    p.add_argument('--photos', action='store_true', help="also install the team names, NHL logos and new jerseys into "
                                                         "that RPCS3's game folder (RPCS3 closed; undo: photos remove)")
    p.add_argument('--version', choices=('EU', 'NA'), help="which version of the game to save for (default: the source's)")
    p = sub.add_parser('season-test', help="save LAB rosters with more and more update steps (finds what crashes Season mode)")
    p.set_defaults(fn=cmd_season_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--source', help="roster save to start from, disc / disc:EU / disc:NA, or file:<a roster file such as a "
                                    "downloaded community SYS-DATA> (default: the newest roster this program did not make)")
    p = sub.add_parser('league-test', help="save a LAB roster with custom teams moved into real leagues (in-game test)")
    p.set_defaults(fn=cmd_league_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--source', help="roster save to start from (default: newest)")
    p = sub.add_parser('draft-test', help="save a LAB roster with prospects in different places (in-game test)")
    p.set_defaults(fn=cmd_draft_test)
    p.add_argument('--rpcs3', required=True, help=RPCS3_HELP)
    p.add_argument('--source', help="roster save to start from, made with 0.8.0 or newer (default: newest)")
    p = sub.add_parser('art-test', help="install or remove the in-game test of photos and logos (see docs/ROADMAP.md)")
    p.set_defaults(fn=cmd_art_test)
    p.add_argument('action', choices=('install', 'remove'))
    p.add_argument('--rpcs3', help=RPCS3_HELP + " (needed for install)")
    p.add_argument('--source', help="roster save to start from (default: newest)")
    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except (FileNotFoundError, layout.LayoutError, datasource.Offline) as err:
        sys.exit(str(err))


if __name__ == '__main__':
    main()
