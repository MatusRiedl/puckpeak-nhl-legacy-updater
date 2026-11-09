# Start here (for AI agents and new developers)

**Puck Peak Legacy Updater** (called NHL Legacy Roster Updater before 0.80.1) keeps the rosters of *NHL Legacy Edition* (PS3, played on the
RPCS3 emulator) up to date. Players start a Windows exe, pick `rpcs3.exe`, choose a roster and
what to update, and get that roster updated (a backup first) or a **new** roster save named with the date
and time. It is built for the NHL Legacy community. Explain changes to the project owner in plain words, without jargon, and
leave decisions about publishing, credits and game-design trade-offs to them.

The window carries the look and logo of **Puck Peak**, the owner's other NHL project. Keep it.

**Shared servers** (the boxes, their ports and who may change what) follow the rules in the owner's private infra repo.
Its COORDINATION.md is imported through the git-ignored CLAUDE.md. Never put its path or its contents into a tracked file.

## Read in this order

1. [README.md](README.md): what players see and do ([CHANGELOG.md](CHANGELOG.md): what each version changed).
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the exe works, from button to new save, and
   where new features plug in.
3. [docs/DEVELOPING.md](docs/DEVELOPING.md): setup, tests, how to make common changes, debugging,
   pitfalls.
4. [docs/MAINTAINING.md](docs/MAINTAINING.md): refreshing data, new seasons, releases, broken feeds.
5. [docs/ROADMAP.md](docs/ROADMAP.md): league checklist, pending in-game checks, capacity facts,
   open decisions, ideas.
6. [docs/FORMAT.md](docs/FORMAT.md): the save format, the rules the game enforces, the art files and
   the schedule tables.
7. [docs/SEASON_PLAN.md](docs/SEASON_PLAN.md): the study of Season / Be a GM in the newest season
   (a plan with experiments, not built yet).
8. [docs/CALENDAR_AND_LOOK.md](docs/CALENDAR_AND_LOOK.md): the hand-over for the 2026-27 calendar, the Utah /
   Seattle / Vegas jerseys and the home-ice logo: what is built, the three in-game tests the owner runs, how to
   read their answers, and what to build next. **Read it when the owner talks about testing the calendar,
   jerseys or the ice.**
9. [docs/GAME_PATCH.md](docs/GAME_PATCH.md): the RPCS3 game patch (the year 2026, 32 teams in Season / Be a GM): every
   entry and why, the lab and its rounds, reading a crash, adding a stage, what is open. **Read it when the owner talks
   about the patch, the lab, 32 teams, All-Stars or a crash in Season / Be a GM.**

## Rules that must not be broken

1. **Never change, overwrite or delete an existing save by yourself.** An update is a new folder
   `<TITLEID>02NN` (`savedata.install`) unless the player chose "Update this roster" (the window's default
   since 2026-10-06, owner's wish): `savedata.update_in_place` replaces the picked roster's `SYS-DATA` after
   a backup copy in the program's own folder (the newest 10 per roster are kept; only those copies are ever
   pruned), never while RPCS3 runs, never the game's own roster, never a folder that is not a roster save
   directly in the save folder. The one removal is the player's own **Delete** button next to a roster:
   `savedata.trash_save` moves it to the Recycle Bin / Trash, with a question first, never permanently.
   A **Be a Pro career** (`<TITLEID>05NN`; owner, 2026-10-23) is changed only when the player presses Save on it in the
   window (`savedata.update_career`): first the whole folder is copied to the program's backups (the newest 10 per career
   are kept), never while RPCS3 runs or within 5 s of the game writing it, and only if `verify.career_problems` finds
   nothing. Tests and the lab use copies. On NHL Legacy Native the same rules hold for its saves (`user/gamedata/dev_hdd0/...`;
   "RPCS3 runs" = `NHLLegacy.exe` runs).
2. **Never add a team and never change a team's league.** The team table is full (252 records,
   8-bit ids) and leagues are fixed per slot; only existing slots can be refilled. At most 40
   players per team. `verify.py` enforces this; keep it that way.
   The one exception is the in-game league test (`cli league-test`, `lab.LEAGUE_MOVES`, ROADMAP
   "League test"), which may move named custom slots into a real league in a LAB roster. Only
   after the owner has played it may the league steps do the same.
   A second exception (owner, 2026-10-19): on a roster for the patched game, Coachella Valley and Henderson (slots
   234 / 235) carry the AHL Pacific's league fields (`gamepatch.league_fit`, last in `pipeline.patch_roster`; the
   patch's stage Y lists and names them there). Reading a patch roster puts Custom's fields back (`unleague`, so the
   builder works as before), and the unpatched game keeps them under Custom (`unpatch_roster`). `verify` allows exactly
   this pair, nothing else.
   A third exception (owner, 2026-11-02): **the Penticton Vees** in the last custom slot (`layout.VEES` = 251). On a roster
   for the patched game they carry a WHL B.C. Division club's league fields (`gamepatch.LEAGUE_SLOTS`) and art 902; in the
   unpatched game, on RPCS3 or NHL Legacy Native, they are a Custom team (Select Teams calls it Custom Team 30; a roster from the
   game's own disc gets no Vees there: `pipeline.with_vees(listed=)`, lab round 59). The `whl` calendar table keeps 22 clubs. `verify`
   allows exactly these three slots. A player's own team in slot 251 keeps it (no Vees then); a prospect pool moves out.
3. **Nothing is saved while `verify()` reports a problem that stops the roster loading. The player's own edits are
   free otherwise** (owner, 2026-10-29: "allow everything possible that will not really break the roster from loading").
   What the builder's update steps make is still held to every check (a problem there is our bug); what the player's
   edits did is only held to the checks that stop loading or crash the game (`verify(free=)`, `FREE_TEAM_FLAWS` /
   `FREE_PLAYER_FLAWS`, docs/notes/free-editing.md has the table and the proof of each). A team the edits leave under
   2 goalies / 18 skaters gets one heads-up line and is saved. If you teach the builder something new about the
   game's rules, teach `verify.py` first.
4. **A build on its own output must be byte-identical** (tests check it). New steps must be
   deterministic.
5. **Never write test output into the owner's real RPCS3 folder or real NHL Legacy Native install.** Use the tests,
   `--dry-run`, a copy of the savedata folder, or `tools/window_shot.py` (it makes a fake RPCS3; `--native`: a fake port).
   On the port the program writes only `mods/Puck Peak`, `user/.../savedata`, `[launcher] mod_order` and, on Patch, our
   `XINPUT1_4.dll` next to `NHLLegacy.exe` (owner, 2026-11-02; Unpatch takes it out, a file of that name that was there
   comes back); `data/hdd0` is the launcher's (it is hard-linked to `data/update` and the mods) and is never written by
   us, and `NHLLegacy.exe` is never changed.
6. **No git commit or push, and nothing published, without the owner's explicit go-ahead.**
   The project is public at https://github.com/MatusRiedl/puckpeak-nhl-legacy-updater (0.6.0
   and 0.7.0 released on 2026-10-04, 0.8.0 on 2026-10-05, 0.8.1 on 2026-10-06, 0.50.0 to 0.50.3 on 2026-10-23, 0.50.4 to 0.51.2 on 2026-10-24, 0.52.0 on 2026-10-25, 0.80.0 and 0.80.1 on 2026-10-27, 0.90.0 on 2026-10-29, 0.91.0 on 2026-10-30, 0.92.0 on 2026-11-01, 0.95.0 and 0.95.1 on 2026-11-03, 0.95.2 on 2026-11-04, 0.96.0 on 2026-11-05, 0.97.0 on 2026-11-09, each with the owner's go-ahead). Every further commit,
   push or release needs the go-ahead again. Before pushing, check that no base roster (`work/`),
   picture pack (`private/packs/`, a zip in `legacy_roster/data/`), anything from `private/`, personal path or user name
   goes in, and that `python tools/clean_check.py` finds nothing.
   The one standing exception (owner, 2026-11-09): **the lines job on the server** (`tools/lines_job.py`, `deploy/lines/`)
   may publish the data pack's refreshed lines daily when its guards pass. Deploying or changing the job itself still
   needs the go-ahead.
7. **Public pictures must not show the owner's user name, desktop or other programs.** Use
   `tools/window_shot.py --show-path`.
8. The engine (`legacy_roster/` except `window/`, `web/`, `gui.py`, `widgets.py`, `theme.py` and `editor/`) uses the
   standard library only; the exceptions are `art/images.py`, `art/looks.py` and `art/crests.py` (Pillow, imported only when "Photos
   and logos" is on). `app/` (the window's logic) uses the standard library, and Pillow only inside functions.
   pywebview is imported only in `window/`. `web/` is the page: plain files, offline (React and htm vendored in
   `web/vendor/`, no Node, no build step, nothing loaded from the internet). The classic window (`gui.py`,
   `widgets.py`, `theme.py`, `editor/view.py`, `editor/uniforms.py`) may use CustomTkinter; it is frozen in 0.10.x
   and goes in 0.11. Leave `work/` (the original lab) untouched.
9. **Pictures are downloaded, never inside the exe** (owner, 2026-10-20, 0.32.0). The photos and logos (`photos.zip`,
    made by `tools/build_photopack.py`) and this season's jerseys, centre-ice logos and menu pictures (`looks.zip`) are
    kept in `private/packs/` (never in git) and on the program's file server (`datasource.FILES_URL`, put there by
    `tools/publish_packs.py`, which also sends the data pack). The program downloads them while "Photos, logos and team
    names" is on (`packs.py`, `UpdateController.download_pictures`, `cli packs`); pictures missing from them are
    downloaded one by one and kept on the player's PC. Art files are always made on the player's PC from templates of
    their own game disc, and the game's own roster (`stock.py`) is read from their disc. The base roster is still not
    shipped (rule 7). No tracked file and no shipped file names where the game's content came from: `tools/clean_check.py`
    checks it (`tests/test_clean.py`, `build.ps1`, `build.sh`, `publish_packs.py`); source details stay in `private/`.
    The game patch of NHL Legacy Native holds translated game functions, so it is the same: pack `portpatch`, made by
    `tools/native_patch/build.py`, never in git or the exe.
10. **Pictures that were in the game folder before are never lost.** The installer keeps a copy of
    every file it replaces (also one another picture pack put there later), never overwrites a
    kept copy with its own file, and the Photos row's "Restore" (or "Restore default") puts them back
    (`art/install.py`).

## Commands

```
python tools\quicktest.py                                      # the tests of the files you changed, parallel, minutes (--full: all, ~5 min)
.venv\Scripts\python -m legacy_roster                          # the window, from source (needs pywebview; --classic: the old one)
python -m legacy_roster list   --rpcs3 <rpcs3.exe>             # the command line
python -m legacy_roster update --rpcs3 <rpcs3.exe> --dry-run   # build and check, write nothing
python -m legacy_roster update --rpcs3 <rpcs3.exe> --for both  # save for the EU and the NA version
python -m legacy_roster update --rpcs3 <rpcs3.exe> --source disc   # start from the game's own roster (no community roster)
python -m legacy_roster stock-test --rpcs3 <rpcs3.exe>         # the in-game check of the game's own roster (owner only)
.venv\Scripts\python tools\window_shot.py <state> out.png [--native]   # picture of the window (headless Edge; --native: a fake port): none|setup|ready|patch|updating|done|details|failed|delete|export|roster|lines|strategy|jerseys|calendar|office|contract|equipment|face|downloading|misfit|prospects|prospects-pro|prospects-make|prospects-class|prospects-import|export-roster; --tab ID, --size WxH, --scale, --screen-lines, --live, --browser
python tools\build_datapack.py --refresh ratings,iihf,liiga,extraliga,shl,del,nl,norway,ahl,chl,nhl   # refresh the data pack
python tools\capacity.py                                       # player records and pool room a full update needs
python -m legacy_roster update --rpcs3 <rpcs3.exe> --photos    # also install photos and logos (RPCS3 closed)
python -m legacy_roster photos remove                          # take them away again
python -m legacy_roster update --rpcs3 <rpcs3.exe> --edits     # also apply the Roster editor's edits
.venv\Scripts\python tools\build_photopack.py                  # the photo pack, private\packs\photos.zip (after the data pack)
python tools\publish_packs.py <ssh-host>:<folder> [--dry-run]   # the packs + the data pack onto the file server (owner's go-ahead; keeps the server's newer lines)
python tools\lines_job.py once --pack <datapack.json.gz> --dry-run [--out <file>]   # the server's daily lines job, one run (deploy/lines/README.md)
python deploy\lines\context.py lines.tgz                        # the lines job's container files, to copy to the server
python -m legacy_roster packs download|status|remove            # the picture packs on this PC
python tools\clean_check.py                                     # no tracked or shipped file names where the content came from
python -m legacy_roster art-test install|remove --rpcs3 <rpcs3.exe>   # the one-off in-game art test (done)
python -m legacy_roster draft-test --rpcs3 <rpcs3.exe>         # LAB roster: where does the draft see prospects (owner)
python -m legacy_roster season-test --rpcs3 <rpcs3.exe>        # LAB rosters with more and more update steps: which one crashes Season mode (owner)
python -m legacy_roster rendering-test --rpcs3 <rpcs3.exe>     # loud Utah jerseys / centre-ice logo as loose files (owner; undo: photos remove)
python -m legacy_roster looks-test --rpcs3 <rpcs3.exe>        # new Utah/Seattle/Vegas jerseys + centre-ice logos as loose files (owner; undo: photos remove)
python -m legacy_roster equipment-test --rpcs3 <rpcs3.exe>        # LAB roster: every tuck / tape colour / tint / pads / pants number on a player (owner)
python -m legacy_roster calendar-test --rpcs3 <rpcs3.exe> --source file:<community SYS-DATA>   # LAB rosters with the real 2026-27 calendar (owner)
python -m legacy_roster year-test --rpcs3 <rpcs3.exe>          # LAB roster + patch file for the year 2026 game patch (owner; gamepatch.py)
python -m legacy_roster team32-test --rpcs3 <rpcs3.exe> [--photos]   # LAB roster + patch file + db/nhlng-meta.xml, db/nhlng.db for the 32-team game patch (owner; lab only; RPCS3 closed; --photos: names, logos, looks; undo: photos remove; docs/GAME_PATCH.md)
python tools\audit_patch.py <EBOOT.ELF>                        # check the game patch's words against the decrypted EBOOT
python -m legacy_roster update --rpcs3 <NHLLauncher.exe>       # every command's --rpcs3 also takes NHL Legacy Native (its exe or folder)
python -m legacy_roster names apply --rpcs3 <rpcs3.exe>        # only the team names, from the picked roster, in seconds (no roster saved, no picture looked at)
python -m legacy_roster update --rpcs3 <rpcs3.exe> --in-place  # update the picked roster itself (backup first)
python -m legacy_roster game-patch install [--skip-intro] [--no-login] --rpcs3 <rpcs3.exe>   # patch RPCS3 (32 teams, year 2026; RPCS3 closed; docs/GAME_PATCH.md section 7)
python -m legacy_roster update --rpcs3 <rpcs3.exe> [--game-patch]   # follows RPCS3: patched -> 32-team roster, else normal (a patch roster is turned back); --game-patch patches first
python -m legacy_roster game-patch status|remove --rpcs3 <rpcs3.exe>   # is RPCS3 patched / unpatch it
python -m legacy_roster game-patch online|online-off --rpcs3 <rpcs3.exe>   # only the online entry (the community patch's words, `gamepatch.ONLINE_ENTRY`; docs/notes/multiplayer.md)
powershell -ExecutionPolicy Bypass -File packaging\build.ps1   # build dist\*.exe (close a running copy first)
bash packaging/linux/build_in_docker.sh <src.tgz> <out>        # the Linux program, built + checked in Docker boxes (MAINTAINING.md "The Linux program")
```

## Environment

- Windows 10/11 (also runs on macOS and Linux: `packaging/build.sh`). Python 3.10+ (developed on 3.13).
- `.venv` (made by `packaging\build.ps1`) holds PyInstaller, CustomTkinter and, for images and
  screenshots, Pillow. The tests run with any Python that has pytest.
- Tests and screenshots need a roster save of the 2025-26 community family ("ROSTER2526") in
  `work/backup/BLES021530202/` or at `LEGACY_ROSTER_BASE`. Without it most tests skip. Ask the
  owner for one. The tests of the game's own roster also need `LEGACY_ROSTER_DISC` (a disc image of
  the game, read only; DEVELOPING.md).
- The program's own files on a PC: `%LOCALAPPDATA%\NHLLegacyRosterUpdater\` (settings, caches,
  reports, error log).

## How to check your work

1. Tests green, with the base roster present: **`python tools/quicktest.py`** (only the files your change touches, in
   parallel, minutes; owner, 2026-10-24: testing must take minutes, never 45). `--full` (parallel, ~5 min; a test that loops over records must build its `Roster` once: one such test took 27 min) only before a
   release, alone, never beside a build or a long job. Name the files you ran when you report.
2. Engine change: the second-run tests still pass.
3. Window change: look at it with `tools/window_shot.py` at 100 %, 150 % and 200 % scaling, on a
   768-line screen and in the smallest window (`--size 940x640`), every tab it touches (`--tab`).
4. Shipped change: build the exe and run the smoke test (MAINTAINING.md).
5. Anything that changes what goes into the save: the owner loads a roster in the game before the
   change leaves `pipeline.EXPERIMENTAL` and ROADMAP.md's list of checks (the window shows no mark).

## Where things are

| Area | Files |
|---|---|
| Save format, tables | `tdb.py`, `sfo.py`, `schema.py`, `schema_names.py`, `roster.py`, `layout.py` |
| The update | `pipeline.py` (order of steps), `builder.py` (also free agents and retiring, goalie gear), `leagues/`, `lines.py`, `ratings.py`, `estimate.py`, `donors.py`, `matching.py`, `draft.py` (real draft data), `sticks.py` (sticks in team colours), `report.py` (the list of changes as a page) |
| The game's own roster | `stock.py` (from the disc, made updatable), `savedata.DiscSlot`, `savedata.roster_sfo` |
| Safety | `verify.py` |
| Data | `datasource.py` (NHL.com, data pack), `tools/build_datapack.py`, `tools/providers/` (`nhl_facts.py`: last season's players, drafts), `tools/club_slots.json` (club → slot for every league), `tools/capacity.py` |
| Lines job (server, 2026-11-09) | `tools/lines_job.py` (`fetch_nhl` / `fetch_extraliga` and `lay_nhl` (letters=False there), also used by `build_datapack.py`; `with_older`, `refresh`, `guards`, `write_pack` (`.prev`), `take_newer` (used by `publish_packs.py`), `run_once`, `serve --at 10:00`), `datasource.pack_bytes` (one writer for the pack file), `clean_check.pack_hits`, `deploy/lines/` (Dockerfile, compose.yml, `context.py`, README.md: deploy, rollback, stop), tests/test_lines_job.py, docs/notes/lines-job.md; NHL 19 reads the same pack |
| Contracts | `contracts.py` (units of $5,000, money scale `REAL` on game-patch rosters / `GAME` = 71.4 / 104.0, `default_terms`, `rescale`, `terms`, `problems` for verify), `Builder.real_contracts` (data pack `contracts`), `pipeline.build` (`b.money`, one rescale), `private/contracts_db.py` (dev only; `SOURCE_SLOT`: the source numbers Vegas before Seattle), `misplaced` (`tools/build_datapack.py` refuses a pack whose deals belong to another team's players), docs/notes/contracts.md. Contract status / UFA year (round 41): `status_fit` / `status_problems` (`QwoG`: Team Rosters' CONT / SAL), `ufa_fit` / `ufa_problems` (`zKKG` = birth year + 27: Be a GM's UFA / RFA). **Contract edits** (0.50.0, seen in the game in round 41): `deal_of` / `real` / `money` / `cap_in` / `edit_problems` / `organisation`, edits.json `players[key]['contract']` (real dollars), `edits.apply_contracts` right after `b.real_contracts()` in `pipeline.build`, `verify.contract_edit_problems`; the window: `app/office.py` `contract_*`, `web/js/office.js` |
| Front office | `frontoffice.py` (`org`: NHL / farm / prospects of an organisation, `seasons`, `cap_space`, `season_label`, 5 seasons 2026-27..2030-31, always real dollars), `app/office.py` (`OfficeController`: groups, sort, the contract window, record and standings from a season save), `web/js/office.js`; `tools/window_shot.py office` |
| RPCS3 and saves | `savedata.py` (also the game's own folder and disc: `Rpcs3.game_folder`, `game_disc`; the versions EU / NA: `GAMES`, `Rpcs3.games`, `install(title_id=)`) |
| NHL Legacy Native (the PC port, 0.95.0) | `savedata.Native` (a second host next to `Rpcs3`: `find_rpcs3` picks it from `NHLLauncher.exe` / `NHLLegacy.exe` / their folder; reads `nhl_settings.ini` `[paths]`; `game_folder` = `mods/Puck Peak/USRDIR`, `patchable` True on the exe the patch was built for), `native.py` (`first_in_order`: the mod at the top of `mod_order`, `compose`: `NHLLauncher.exe --compose`, no window, `settle`, `notes`: the Setup tab's lines), `art/install` (a picture list per host: `art/native-<hash>`), `app/update.py` (`hosts`, `switch_host`), `texts.NATIVE_NOTE` / `ONLINE_NATIVE`, `tools/window_shot.py --native`, tests/test_native.py, docs/notes/native-port.md |
| Team names alone (0.95.0) | `pipeline.apply_names` (a `Builder` with no steps, `portraits.names`, `install.install_names` / `install_menus`: never a roster saved, never a pack read), `UpdateController.apply_names`, the Team names row's button, `cli names apply`, `texts.NAMES_DONE` |
| Penticton Vees (0.95.0) | `layout.VEES` / `VEES_RINK` / `is_vees`, `OWN_ART` 20085, `CLUB_ART` 902, `CLUB_DONOR`, `pipeline.with_vees` (switches slot 251 on before the CHL step; `clubs.own_teams` fills it from `chl.whl.extra`, no data pack change), `gamepatch.LEAGUE_SLOTS`, `builder.vees_arena`, `app/calendar.py` `VEES_NOTE` (68 games from the data pack), tests/test_vees.py, docs/notes/lab-round-59.md |
| Menu art and names (portraits, logos, team names) | `art/` (`loc.py` the game's text file and the Puck Peak texts `PROMO`; `menus.py` the main menu without the dead online entries; `disc.py` the player's own disc, `bigf.py`, `refpack.py`, `dds.py`; photos and logos: `portraits.py` ids in the roster, `images.py` drawing, `install.py` download, write, undo; `lab.py` the one-off art test; `crests.py` Coachella's / Henderson's crests as create-a-team logos 72 / 80), `tools/providers/wiki_logo.py`, `tools/names_report.py` |
| The window (0.10; nine tabs since 0.50) | `window/` (`main.py` start and fallback, registers the slices `update`, `editor`, `rail`, `lines`, `strategy`, `uniforms`, `calendar`, `office`, `contract`, ...; `host.py` pushes state to the page at most 25 times a second, `api.py` the page's calls (`tab`, `rail_league` / `rail_team` / `rail_step`, `calendar_*`, `office_*`, `contract_*`), `webview2.py`, smallest window 940 x 640), `app/` (controllers holding all state: `update.py`, `editor.py` (also the team list's owner: `follow_with`, `show_tab`, `rail_snapshot`, `team_view`; the six team tabs' controllers are followers that work only while their tab shows), `lines.py`, `strategy.py`, `uniforms.py`, `calendar.py`, `office.py`, `season.py`; `jobs.py`, `settings.py`, `texts.py`, `dataurl.py`), `web/` (`index.html`, `css/` (`teams.css`: the team list, calendar, front office), `js/`: `main.js` (the tabs: Setup, Game patch, Update | Roster, Lines, Strategy, Jerseys & ice, Calendar, Front office; Ctrl+1..9, Ctrl+PgUp/PgDn, Alt+Up/Down), `rail.js` (the team list), `update.js` (`SetupTab`, `UpdateTab`, `PatchTab`), `editor.js` (`RosterTab`, `LinesTab`, `StrategyTab`, `JerseysTab`, `SaveBar`, the pop-up windows), `calendar.js`, `office.js` (`OfficeTab`, `ContractWindow`), `ui.js`, `shell.js`, `bridge.js`, `store.js`, `demo.js`), `editor/card.py` (the player card's checks), `progress.py`. Mockups of new screens: `private/mockup/` (git-ignored; `serve.py --open` serves its files over `web/`) |
| Front ends | `cli.py`; the classic window (fallback, `--classic`): `gui.py`, `widgets.py`, `theme.py`, `editor/view.py`, `editor/uniforms.py` |
| Jerseys and ice | `app/uniforms.py` (a follower: loads a team 250 ms after the pick, only while the tab shows) + `web/js/editor.js` `JerseysTab` / `UniformsBody` (the Jerseys & ice tab for every team of any league with jerseys of its own, `looks.editable`: colours + crest, one row per version (NHL: all, elsewhere home and away, `looks.team_versions`): this season's (the look pack) / the game's own / from the colours / the player's own picture, the centre-ice logo (locked where `looks.own_ice` says the game shows another); the game's and this season's templates to paint on), by art id (`looks.team_art`), kept in edits.json (`uniforms`, `ice`), installed by `looks.looks_from` / `install_looks` with the photos; `tools/window_shot.py jerseys --team <slot>`; AHL art ids docs/notes/ahl-art-ids.md; Coachella Valley / Henderson as art 900 / 901 on patched rosters: `art/clubart.py` (`AliasDisc`), `gamepatch.art_fit` / `unart`, `looks.with_club_defaults`; classic window: `editor/uniforms.py` (NHL only, frozen). Shared ice (national 501, DEL 197, EASHL 255): `looks.ice_group` / `ice_note`, one picture for the group (lowest slot wins). Winter Classic / EASHL 2: `looks.window_team` shows the owner's jerseys. Custom slots 222-251 (create-a-team drawing): `custom_kit.py` (`ttOk` design fields, `NDEo` pieces `PIECES`, `fill`, `write`, `free_logo`, `problems` for verify; lab round 37, docs/notes/lab-round-37.md), edits.json `teams[slot]['kit']` (`edits._team_kit`), `app/teamkit.py` (`TeamKit`, the game's Create a Team menu pictures), `web/js/editor.js` `CustomKitBody`, crest pictures by `art/crests.py` (`pictures=`) |
| 3D textures | `art/rpsgl.py` (jerseys, ice: read, replace a raster, repack), `art/rendering.py` (`cli rendering-test`, done), `art/looks.py` (the real Utah/Seattle/Vegas jerseys, pants, socks, numbers, menu pictures, centre-ice logo; `cli looks-test`; `tools/look_preview.py` makes PNG sheets) |
| Game patch on NHL Legacy Native (2026-11-02) | a stand-in `XINPUT1_4.dll` next to `NHLLegacy.exe` that replaces the patched functions with its own compiled copies: `tools/native_patch/` (README.md: build, a new build of the port; `BUILDS`), pack `portpatch` (`private/packs`, index.json `version`, `stamp`, `image`), `savedata.NATIVE_PATCHED` / `exe_id` / `Native.patchable`, `patchinstall._port_pack` / `_port_state` (Patch / Unpatch through the store `patch`), `texts.PATCH_NATIVE` / `MISFIT_PORT`, tests/test_native.py, docs/notes/native-patch.md. Rebuild when `TEAMS_VERSION` changes. Online on the port (2026-11-03): the same DLL answers the sign-in, sends the redirector to our server, sets the console clock to RPCS3's 80 MHz, lists the lobby's roster first and starts the search (`tools/native_patch/proxy.cpp`, README "Online"); `onlinecfg.port_launch` / `good_name` (a typed name, no RPCN), `OnlineController.port`, `texts.ONLINE_NATIVE` (a port the patch was not made for) |
| Game patch (RPCS3) | `gamepatch.py` (the year entry, `TEAM_STAGES` A-Y with every word and why, `league_fit` / `unleague` / `check_league_fit` (Coachella / Henderson in the AHL, stage Y), `INTRO_ENTRIES` (the optional intro skip / no boot login, and `NEWS_ENTRY`: the main menu's offline news also when signed in, ticked with the patch, `patchinstall._wanted`), `all_star_fit` / `check_all_star`, `patch_text`, the roster rules `year_shift` / `farm_fit` / `divisions_fit` / `future_fit` (`FUTURE_DAYS`) and their checks, the db files `fit_meta` / `fit_db`), `PLAYER_ENTRY` / `player_patch_text` (the one entry players switch on), `is_patch_roster` / `unshift` / `mend_years`), `patchinstall.py` (RPCS3's `patches/` and `config/patch_config.yml` as text, the db files in the store `patch`, `state`, `remove`), `pipeline.update(game_patch=)` / `patch_roster`, `rights_wide` / `rights_narrow` / `rights_fit` / `check_rights` (six-bit rights on patch rosters, 0.23), `calendartest.team32_test` / `year_test` (the lab rosters), `tools/audit_patch.py` (words against the decrypted EBOOT, 1.00 or 1.01), update 1.01 (`UPDATE_HASH`, `VERSIONS`, `at`, `hash_of`, `legacy_roster/patch101.py` made by `tools/port_patch.py`; `patchinstall.game_version`, `stale`), docs/GAME_PATCH.md, docs/notes/update-101.md |
| Calendar | `schedule.py` (the real schedule into `nhlschedule` / `favoriteteamschedule`, `check`; every club league's table: `LEAGUES` (tag, slots), `league_schedules` (data pack part `schedules` + `ahl_schedule`), `league_rows`, `apply_league`, `read_league`, `check_league` (verify), `pipeline.CALENDAR_STEP`; for the Calendar tab `read`, `dated`, `season_of`, `split_all_star`, `read_ahl` (patch rosters' AHL)), `calendartest.py` (`cli calendar-test`), data pack part `schedule` (`tools/providers/nhl_facts.py`); the tab: `app/calendar.py` (`CalendarController`: month, day, mode, `season(on)` = My season), `web/js/calendar.js`; `tools/window_shot.py calendar` |
| Be a Pro careers (`careersave.py`, P6) | `careersave.py` (a `<TITLE>05NN` save of 1.00 or 1.01, `VERSIONS`: read and built again byte for byte: `Career` = the database + ten chunks, chunk 8 the pro as the career began, chunk 24 his XP earned / spent; the game shows and plays the database's `wiLv` `c_` ratings; `Pro`, `set_xp` (to spend = earned - spent), `set_ratings` (40-99, skaters), `set_name`, `sub_title` / `renamed_label` (the Load Pro label the game made: LAST + slot + 1), `EDITABLE`, `find`, `read` (5 s settle), `pieces`), `verify.career_problems` (only the allowed bytes / rows change), `savedata.update_career` (backup of the whole folder, newest 10, never while RPCS3 runs; `label=` sets PARAM.SFO's SUB_TITLE), tests/test_careersave.py (copies under `LEGACY_ROSTER_CAREERS`: every one byte for byte), docs/notes/be-a-pro-save.md; the window: `app/career.py` (`CareerController`, slice `career`: `look`, `open`, `set` name / XP / ratings, `save` asks first (rule 1), `closing`), Draft & Pro's last view `careers` (`app/prospects.CAREERS`), `web/js/prospects.js` `CareerTab` / `CareerPro`, api `career_*`, tests/test_career_app.py, `tools/window_shot.py prospects-career` (needs `LEGACY_ROSTER_CAREERS`). The birth year is not shown (a patched game's career keeps it shifted) |
| No Press Start (`art/pressstart.py`, lab 47d) | `skip_file` / `skip_files`: the disc's `03_pressstart.big` (cacheboot.big, `SIZE` / `SHA1`) with `transitionDone` calling `startPressed(0)` after a quick boot (found by name, 18 bytes, same length); tests/test_pressstart.py, docs/notes/press-start.md |
| Season / Be a GM saves (read only) | `seasonsave.py` (`find`, `read` -> `Season`: `today`, `human` / `farm`, `games` with scores, `results`, `records`, `standings`, `place`; refuses a save written in the last 5 s), `app/season.py` (`SeasonSource`: the picked roster's game version, newest save, cached), docs/notes/season-saves.md; never writes |
| Season-mode test | `seasontest.py` (`cli season-test`) |
| Lines and strategies (Roster editor) | `lines.py` (`GROUPS`, `check_lineup`: the rules, `set_lineup`, `slot_label`), `strategy.py` (table `oYeE`: `SECTIONS`, `CHOICES` words, ranges `top`, `clean`, `write`, `out_of_range` for verify; the game's menu order and words, lab round 28, docs/notes/strategies.md), `edits._team_lines` / `_team_strategy` (edits.json `teams[slot]` `lines` / `strategy`, applied in `apply_teams`), `app/lines.py`, `app/strategy.py` (followers of the team list; drafts not applied are kept per team), `web/js/editor.js` `LinesTab` / `StrategyTab`; `tools/window_shot.py lines|strategy` |
| Roster editor | `editor/model.py` (a roster as teams and players, `apply_edits`), `editor/view.py` (the tab: the picked roster as it is plus this visit's edits; saves in place or as new), `editor/pictures.py` (the player's picture on the card), `edits.py` (the player's edits, kept in edits.json and applied after every update); player type: `ratings.STYLES` / `GOALIE_STYLES` / `STYLE_CHOICES` (all named in the lab 2026-10-16), `style_label` / `style_choice`, `Builder.set_style`, `verify.style_problems`; face: `faces.py` (`DaPp` / `QDTK` / `jfuZ`, valid heads = table `vuqu`, `problems` for verify), `app/editor.py` `face_open` / `face_search` / `face_pick_*` (the "Face of a player" window), docs/notes/faces.md; **created look** (the game's Create Player: head shape, skin tone, hair, facial hair, eyebrows, eyes, black eye, scars, freckles; P1b): `faces.LOOK` / `write_look` / `read_look` / `random_look` / `look_problems` (verify), only on the reserved Create Player records 16000-16179 (`faces.RESERVED`, `free_reserved` highest id first, `KEEP_FREE` 10 skaters / 5 goalies for the game), edits.json `players[key]['look']` (`edits._look_records` / `_set_look`, `_create`), the card's Look... window (`app/editor.py` `look_open` / `look_set` / `look_random` / `look_done`, slice `look_pics`: the menu's pictures from the disc; `editor.js` `LookPart` / `LookWindow`; `tools/window_shot.py prospects-look`), docs/notes/draft-class.md "How the program makes a created look" |
| Draft classes and my pro (P1 engine, P2 tab, P3 class files + random maker built; plan docs/plans/another-context-window-is-sorted-liskov.md) | `draftclass.py` (`DRAFT_SLOTS` European + CHL clubs, `TIER_BANDS` potential per growth tier, `eligible_year` 15 September rule, `apply` after the last `draft.apply`, `problems` for verify), a class player = a new player in edits.json with a `prospect` block (`class`, `tier`, `potential`); records held before the leagues (`edits.records_needed`, `Builder.hold_records`, `held_records`); a new player without his own number takes a free one (`edits._move(wins=False)`); `'draft classes'` / `'new player records'` experimental; the tab "Draft & Pro" (10th, Ctrl+0): `app/prospects.py` (`ProspectsController`, a follower; Add / pick open the editor's card: `EditorController.new_player(preset, extra)`, `open_person`), `web/js/prospects.js` (`ClassRail` in the team list's place, `ProspectsTab`), the card shared with the Roster tab (`editor.js` `useCardForm`); class files `draftclass.class_file` / `read_class` (JSON `legacy-roster-draft-class` v1, cards as typed, club by league + name, `shift_birth` to another draft; `ProspectsController.export_class` / `import_class` / `import_text`, report window), random maker `draftclass.make` (seeded; names mixed from non-NHL players of the same country, never a roster full name; `tiers_for` by strength; potential as the game's stars `draftclass.stars`; class files carry a created look; `spread` over the league's clubs; `ProspectsController.make_open` / `make_set` / `make`; `EditorController.next_note`); `tools/window_shot.py prospects|prospects-pro|prospects-make|prospects-class|prospects-import`; lab round 44 docs/notes/lab-round-44.md, research docs/notes/draft-class.md |
| Picture parts (0.76.0) | `art/parts.py` (the seven switches, `PACK_OF`, `packs_for`, `belongs`, `RETIRED_TAGS`), `art/extrapack.py` (`ExtraPack`: a small pack zip with index.json), `art/arenas.py`, `art/brightice.py` (community centre ice, 0.78.0; since 0.96.0 its own row beside `pack_ice` = this season's centres: `settings.ICE_ORDER` / `parts.ice_order`, the second switched on lies on top), `masks.install_team_masks`, `pipeline.Pictures(parts=)` / `new_centres` / `install_arenas` / `install_bright_ice` / `install_team_masks`, `install.remove_parts` / `remove_retired`, `restore.picture_part`, `private/build_extras.py`, tests/test_extras.py |
| New scoreboard (0.78.0, **out of the program since 2026-10-27**, owner) | parked in `private/scoreboard/` (README.txt: `overlay.py`, `test_overlay.py`, `build_overlay.py`, the packs, `hooks.patch` = the app's hooks as taken out); what stays: `parts.OVERLAY_TAG` in `RETIRED_TAGS`, `install.remove_retired` (called first in `pipeline.Pictures.put_in`: files a test exe put in go back), `tools/apt_dump.py`; docs/notes/overlay.md, lab-round-53.md, lab-round-54.md |
| Picture packs (downloaded, 0.32.0) | `packs.py` (`manifest`, `path`, `have`, `missing`, `sync`, `fetch`, `prune`, `remove_all`; folder `app_dir('packs')`, `<name>-<sha12>.zip` + `state.json`; `LEGACY_ROSTER_PACKS`), `datasource.FILES_URL` / `files_url` (`LEGACY_ROSTER_FILES_URL`), `art/photopack.py` / `art/lookpack.py` open `packs.path(...)`, `app/update.py` `download_pictures` / `_photos_row` (the Photos row, first and gold), `tools/publish_packs.py`, `tools/clean_check.py`; the server: docs/notes/pack-hosting.md |
| Online play (plan private/Multiplayer.txt, docs/notes/multiplayer.md; **0.60.0 test build, nothing released**) | `gamepatch.ONLINE_ENTRY` / `online_entry_lines` (the community patch's words, 1.00 and 1.01, own switch: `patchinstall.set_online`, state `online`), `onlinecfg.py` (RPCN name from rpcn.yml, the app's own config with the Net block and the exact SPU maths `maths_config` (`MATHS` = `SPU XFloat Accuracy: Accurate`, lobby word "0.26 exact" `MATHS_WORD`: at Approximate RPCS3 parts from the port and from other RPCS3s, docs/notes/native-patch.md), `launch_args`, `log_state`, `roster_crc`; the player's own config is only read), `lobby.py` (the server's lobby API client, `LEGACY_ROSTER_ONLINE_URL`), `app/online.py` (`OnlineController`, slice `online`, a follower: refresh, one-press setup (the online entry only), create (the picked roster is copied to the app's own "Puck Peak Online" save and uploaded) / join (the host's roster is downloaded, CRC checked, installed) / ready / leave, the patch word `patch_word()` (version or "none") compared with the host's, RPCS3 started once per lobby, steps by role: host Create Game Session, guest Browse + Join), `web/js/online.js` (the 11th tab, no number key; since 2026-11-09 three columns as NHL 19's Multiplayer tab: you + pre-flight checks | lobby | rating + history, CSS `.online .mp-*` in `css/teams.css`, plan docs/plans/multiplayer-three-columns.md), api `online_*`, the overlay over the game (0.90.0, Windows only: `legacy_roster/hud/` ported from the owner's NHL 19 project, stdlib ctypes, a layered click-through window over RPCS3's game window `hud.emulator_rect` / `is_game_title`; partner chat toasts, the result card `app/online.hud_card`, Ctrl+Shift+F1..F6 = the six phrases; setting `online_overlay`, default on, You card switch; the online config asks for borderless fullscreen `onlinecfg.borderless_config`; demo `python -m legacy_roster.hud`; tests test_hud; not seen in the lab yet), the Ranks card's views `RANKS_TABS` (matches, My stats `stats_view` from the rank card, Box score `box_view` /
`box_lines` from the server's `GET /api/match?id=` = each side's CPRT versus stats, labels `BOX_LINES` unproven (only
zeros seen in the lab); a server without the route hides only the box score, `box_on`), `tools/window_shot.py
online|online-lobby|online-ready|online-ingame|online-failed|online-stats|online-box`, tests test_online / test_lobby / test_onlinecfg / `tests/fake_lobby.py`. Server: the private repo the private server repository ("Overtime" = the owner's own servers; the community server is never named here), deployed on the owner's box; the host is the reference (roster CRC + patch word), the host's gzip roster is kept in memory (8 MB each, 48 MB all), the host leaving closes the lobby; the in-game flow is not tried through the app yet (owner + one tester in 0.60.0) |
| Export files to a folder (0.72.0, every system) | `export.py` (`ExportTarget` = a pretend RPCS3 in `<out>`, `run`, `instructions` / `how_to_text`: per-system text, `HOW-TO-INSTALL.txt`; layout `dev_hdd0/game`, `dev_hdd0/home/<user>/savedata/<T>02NN`, `patches/<T>_patch.yml`, never `config/patch_config.yml`), `savedata.exporting`, `art/install.redirected`, `app/update.py` (`export_mode`, `_start_export`, `_ask_export`), `web/js/shell.js` `Question` rows, `cli export-files`, `tools/window_shot.py export|export-done`, tests/test_export_files.py, docs/notes/export.md; the old SYS-DATA-only `pipeline.export_sysdata` / `cli export-roster` stay |
| Packaging | `packaging/build.ps1`, `packaging/build.sh` (refuse a zip in `legacy_roster/data/` and a `clean_check` hit), `packaging/make_assets.py` |

## Writing for players

Window texts, errors and the README are read by players, not programmers: short sentences,
no jargon, and say what to do next ("Pick the file rpcs3.exe in your RPCS3 folder."). Engine
progress messages are shown to players too, and the progress bar recognises them by their
wording (`progress.py`).

## Current state

**Version 0.97.0 (2026-11-09, released with the owner's go-ahead: GitHub release with the exe, the Linux tar.gz and `SHA256SUMS.txt`)** carries everything below since 0.96.0: the Multiplayer tab in three columns as NHL 19's (plan docs/plans/multiplayer-three-columns.md), the community centre ice greyed out, the `wgjx` table-full fix and the lines job's code. Redeploy the lines job from this commit (`deploy/lines/README.md`).

**After 0.96.0 (2026-11-06, part of 0.97.0; owner: "grey it out ... let's not allow players to use it", without a game check):**
the community centre ice (`bright_ice`) is greyed out: `art/parts.py` `DISABLED` (the row `enabled` False, `texts.PICTURE_DISABLED`,
`set_step` and the group skip it, forced off at start, `cli --bright-ice` says so and is ignored, `pipeline.Pictures` drops it).
`install.remove_disabled` (start of `Pictures.put_in`, any update with pictures) puts its files back. Its one centre of this season's, the national
teams' IIHF ice (art 501, `c/501.bin` of the `ice` pack), now comes with **This season's centre ice**: `brightice.SEASON_ARTS` /
`install_season`, tag `parts.SEASON_ICE_TAG` (in `TAGS[PACK_ICE]`, so that row's Restore undoes it), `pipeline.install_season_ice`,
`parts.MORE_PACKS` (pack_ice also downloads `ice`). No pack change, nothing to publish. Every other centre of this season's was already in the look pack
(private/notes/rinks.md); the DEL (patch words parked), Canada's own file (no disc template) and Norway (not in this season's set) stay the game's.
To bring it back: empty `DISABLED`; the community mechanics' tests run with it emptied (`tests/test_extras.py` `update_pictures`).
**Also after 0.96.0 (2026-11-09, not committed): "wgjx: table full (749)"** (a tester's patched update): 0.92.0's Alternate rows
left room for 4 club rows, the Vees need 6. `gamepatch.make_room` (called by `art_fit(R, dropped)`) takes this season's Alternate
rows out of the table's end, last first; `patch_roster` names the teams in the List of changes; a table full of its own rows gets a
`LayoutError`. Tester roster `2026-11-09-wgjx-full`; docs/notes/wgjx-full.md. `update_context` no longer marks every roster "(missing)". Exe built 2026-11-09 with the owner's go (still numbered 0.96.0, not opened, not released).
**Lines job (2026-11-09, DEPLOYED on the file server with the owner's go, 20:21 UTC; not committed; plan docs/plans/ticklish-cooking-steele.md):** the
lines audit (docs/notes/lines-audit.md) found players' lines as old as the last pack publish. `tools/lines_job.py` refreshes the
published pack's NHL `lines` and Extraliga `club_lines` every day at 10:00 UTC in its own container beside the file server
(`deploy/lines/`) and publishes by itself when its guards pass (rule 6's exception). Both games get the lines at their next Update,
no release. First run published the live pack (generated 2026-11-09T20:25:04Z); next runs daily. Changing or redeploying the job
needs the owner's go (`deploy/lines/README.md` "Update the code", COORDINATION's post-change checks, a STATUS line); the bundle
running now is the uncommitted tree of 2026-11-09, so redeploy from the commit once it exists. docs/notes/lines-job.md.

**Version 0.96.0 (2026-11-05, RELEASED the same day with the owner's go-ahead: tag `v0.96.0` on 8b25f19, GitHub release with the exe, the Linux tar.gz (Ubuntu / Fedora / Arch passed) and `SHA256SUMS.txt`; open: players on scanned heads (Byfield, head 2176) keep a light face, planned 0.96.1; plan docs/plans/quiet-soaring-beaver.md, notes docs/notes/skin-tones.md):**
four asks of the owner. (1) **Native forgot its patch state**: `scan()` read `patchinstall.state` before `art_install.use_host(found)`, so
`_port_entry` read RPCS3's list; `use_host` now comes first (also "Switch to"), `_port_entry` reads the host's list explicitly, the DLL's entry is
keyed by `os.path.normcase(folder)` (old key still read). RPCS3 was never affected. tests/test_native.py (a new controller after Patch still
says patched). (2) **Arrow** `.step .arrow` 26 px. (3) **Faces that fit**: data pack part `skins` (`tools/skin_tones.py`, `tools/skin_marks.json`,
`--refresh skins`; photo colour of the face, hand-marked by the owner's sample, no GPU), `faces.BUCKET_OF` / `COUNTRY_SKIN`, `donors.group_for` /
`head_of` / `fit_skins` (runs in `pipeline.build` after the leagues only when a step that places players runs: a ratings-only build changes no
record), `reset_identity` picks the head by group. Scanned heads (< 60000), Create Player records and `QDTK`-less heads are never touched; idempotent.
Not seen in the game: that the game draws a generic head in the skin `QDTK` says. (4) **Two centre-ice switches** (`art/parts.py` `PACK_ICE` =
this season's centres from the look pack, `BRIGHT_ICE` = community centre ice; the Jerseys row does jerseys only): settings `ice_order`, the one switched
on second is laid on top (`parts.ice_order`, `pipeline.Pictures.put_in`, `looks.split_looks`, `install_looks(kind=)`), `belongs(source, part, key)` is path-aware
so each row's Restore undoes only its own files, old settings turn both on, cli `--pack-ice` / `--bright-ice` order. The community pack is rebuilt from the
owner's icesurface folder (`private/build_extras.py --ice --out`, candidate `private/ice_candidate/ice.zip`, 35 centres, the ad files left out, every raster
finished with the ice colour under clear pixels like the game's own files and `looks.finish_centre`; the published `private/packs/ice.zip` is untouched).
**Lab round 62 (docs/notes/lab-round-62.md): the "square" on New Jersey's ice was NOT reproduced** (lab RPCS3 and lab port; the owner's installed centre files are byte-identical to the published pack's). The old pack has partial alpha in mips 3-7; the rebuilt one has none, which removes the only mechanism found, but **a fix against the owner's actual square is not confirmed**(if it stays: ask for the camera and RPCS3 resolution scale). Port restart check passed (still patched 0.27). Committed locally as b97e91a (not pushed, not released). **Published 2026-11-05 (owner's go): the data pack with `skins` and `ice-677f268c7d77.zip` (35 centres); the prune removed `portpatch-fd92fc28cc5c.zip` (0.26).** Release (tag, push, GitHub release) waits for the owner's go.

**Fix 0.95.2 (2026-11-04, built and played in the lab, released 2026-11-04 with the owner's go-ahead (commit 1f7425f, tag `v0.95.2`, GitHub release with the exe, the Linux tar.gz (Ubuntu / Fedora / Arch passed) and `SHA256SUMS.txt`), pack `portpatch` 0.27 published the same day; owner: "do all 4 points"):** a
tester's NHL Legacy Native crashed at the start of a Be a CHL Pro career (the round 44 bug, GAME_PATCH.md section 6). A patched CHL
career had 128 team keys in a 7-bit field; key 127 (Victoria Royals) is the field's "no team". **Stage Z** (`gamepatch.STAGE_Z`, patch
**0.27**, `TEAMS_VERSION`): `0x28715c` `bl 0x285740` (the Top Prospects maker, only in Be a Pro modes) -> nop (1.01 `0x28824c`,
`patch101.py` regenerated); a career keeps 126 keys and has no Top Prospects game. `tools/audit_patch.py` 0 problems on EU 1.00, NA 1.00,
1.01. Lab round 61 (docs/notes/lab-round-61.md): RPCS3 control crashed on 12 Sep, Z played to 13 Mar 2027 + save / reload; the port's DLL
rebuilt (`private/packs/portpatch.zip` 0.27, the 0.26 one kept as `portpatch-026-20261103.zip.bak`), Patch again / Unpatch through the
program, a CHL career to 22 Nov 2026. CHANGELOG 0.95.2, `__version__` 0.95.2. Then (owner: "do the testing ... rebuild exe and Linux and upload new patch"): a QMJHL career
(Blace, Moncton) on the port to 13 Nov, 19 games, no crash; exe 0.95.2 built; **`portpatch` 0.27 published 2026-11-04**
(`portpatch-8d77c107ac86.zip`), the program not released yet. **Pack and app go out together** (a 0.27 pack under 0.95.1
or the 0.26 pack under 0.95.2 shows "Patch again" for ever; online word "0.27 exact"). Open: Quinn Kennedy (QMJHL) crashes loading his
Be a Pro career with or without Z; the lab RPCS3's own hand-made patch files are lost (lab-round-61.md "The lab afterwards").

**Hotfix 0.95.1 (released 2026-11-03 with the owner's go-ahead: commit 74867b5, tag `v0.95.1`, GitHub release with `PuckPeakLegacyUpdater.exe`, the Linux tar.gz (Ubuntu / Fedora / Arch boxes passed) and `SHA256SUMS.txt`; no pack or server change):** a tester's roster that began as the game's own (patched) failed verify:
"free agent Nick Jensen is also on Knights". The builder used `L.NHL_ALL` (the community layout's copies 222-233) where a
roster from the disc has real custom teams there, so the NHL step listed Jensen as a free agent and left his places on 222 / 223.
`Builder.nhl_all` (= NHL + this roster's copies) replaces it in `nhl_rosters`, `fill_empty_national` and `clubs.update_league`;
`contracts()` runs `unlist_club_players` again (skips deleted entries), so any such double is mended with a List of changes row
instead of refusing the save. Tests `test_stock.py::test_a_player_who_leaves_his_nhl_team_keeps_his_custom_team_place`,
`test_listed_on_a_club.py::test_a_step_that_leaves_a_club_player_on_the_free_agent_list_is_mended_before_the_contracts`. The QMJHL
"No slot in the game for Rouyn-Noranda, Val-d'Or" line is the game's 16 QMJHL slots (rule 2), not a fault.
Then (owner: "do 1, 2, 3 and Reichel"): (1) `verify.multi_club` follows the roster's layout (`layout_mirrors`). (2) `Builder.mend(source)`,
last before `finish()` in `pipeline.build`: what a step left that verify would refuse and has one safe answer is put right with a row
under `builder.REPAIRS` ("Repairs" in the List of changes, a line in the result): a second place on one team, a player on two NHL / AHL
clubs (contract team, else NHL, else lowest), free-agent list doubles and club players on it, free agents' deals, a deal naming another
team, an NHL player without a deal (default terms). What the source already had and the player's own edits (`free`) are left alone.
tests/test_mend.py. (3) **Tester rosters** (`tests/test_tester_rosters.py`): every roster in `private/tester_rosters/<name>/SYS-DATA`
(git-ignored, README there; or `LEGACY_ROSTER_TESTERS`) gets a full offline update (+ `patch_roster` when patched) that must pass and
be byte-identical on a second update. Add each refused tester roster there once fixed. Held now: the Jensen roster and the community's
26-27 Extras roster. The latter showed: `nhl_rosters` step 2 drops a listed player's places on other NHL teams (slot 31 still the
All-Star "Black / Blue"); step 1b retires a copy-only leaver (Kopitar on 227); `clubs._match_on_club` (a listed player with another
birthday found on his own club by name + year, takes the list's birthdate: Livingstone was doubled); the 40 cap drops kept juniors
before listed players (Kaiser). (4) **Reichel**: `clubs._feed_position` defers a position change of a player still on a national
team (`Builder.later_positions`), `clubs.late_positions` applies it after `national_teams()`.

**Socks, pants and masks (2026-11-03, part of the held 0.95.0; plan top of docs/plans/we-have-big-job-cached-ladybug.md):** two
testers: Leafs in black pants, Bruins' socks with Utah's one low stripe, Swayman in a red club's mask. (1) The look pack carries each
kit's own sock (`s/<slot>_<role>.webp`, the game's layout 1024 x 512) and pants colours (index `kits.<role>.pants`); `PackKit.sock` /
`pants`, `Maker.cut_files` -> `sock_file(picture=)` (`shaded_sock`: the chassis' garter / skate shading, `sock_shade`, `SOCK_SHADE`) and
`pant_file(colours=)`; both in `look_digest` only when present (old packs: same digest, same files). Pack made by `private/build_looks.py
--add-legs` (extends the published pack, every old member byte for byte; 0.92.0 reads it and redraws nothing): candidate
`private/looks_candidate/looks_legs.zip`, **not published** (owner's go). (2) `Builder.fit_mask` / `team_masks` in `goalie_gear`: a goalie
who moved or took over a record wears his NHL team's mask (art 0-29 but Utah's 22), else the mask the team's unmoved goalies wear that no
other team wears, else plain 120; `masktype` 0 only; the player's own mask edits win. (3) Jerseys & ice: a "Socks and pants: ..." line per
version (`UniformsController._legs`, `texts.LEGS_*`). Tests `test_looks.py::test_a_pack_kit_wears_its_own_socks_and_pants...`,
`test_stock.py::test_goalies_who_came_to_a_team_wear_its_mask`. Lab round 60 (docs/notes/lab-round-60.md): Boston's real socks, Toronto's blue pants and striped
socks, Swayman's Bruins mask seen in a game; Utah / Davos not seen on the ice.

**Game patch on the port (2026-11-02, part of the held 0.95.0; plan top of docs/plans/we-have-big-job-cached-ladybug.md, notes
docs/notes/native-patch.md, `tools/native_patch/README.md`):** the owner wants the port 1 to 1 with RPCS3, through our app alone. A stand-in
`XINPUT1_4.dll` (pack `portpatch`, not published) swaps the functions the patch changes for its own compiled copies; 157 functions, patch
0.26 as on RPCS3, on the exe of port v1.0.0 only. Played on the lab copy through the DLL: a Vegas Season to 84 GP and the first playoff game, a Vegas
Be a GM through playoffs, draft and off-season to 20 Oct 2027, a Be a Pro Seattle prospect, the Vees in the WHL through a real update, Unpatch +
update back to normal. **Online on the port (2026-11-03, Gates 2 and 3):** the port and RPCS3 parted on the first frames because RPCS3 at
`SPU XFloat Accuracy: Approximate` folds the game's SPU refine recipes into exact sums; the app's online config now sets Accurate (lobby word
"0.26 exact", so older apps cannot join). On the lab server every pair stayed in step, 0 replay rounds: port vs RPCS3 NA 1.01 (23 min through a
shootout, a quit filed by both sides), EU 1.01, EU 1.00, the port's AVX2 copy, port vs port, RPCS3 vs RPCS3, and the release DLL installed through
the app. Not seen: a normal match end with a goal, a real second CPU kind, the port's overlay / fullscreen, the public server (docs/notes/native-patch.md
"Every pairing").

**Version 0.95.0 (released 2026-11-03 with the owner's go-ahead: commit 40d751f, tag `v0.95.0`, GitHub release with
`PuckPeakLegacyUpdater.exe`, the Linux tar.gz and `SHA256SUMS.txt`; packs `looks` and `portpatch` were already on the server, the data
pack of 2026-11-01 unchanged; plan
docs/plans/we-have-big-job-cached-ladybug.md, PLAN.md top, notes docs/notes/native-port.md, lab-round-59.md):** (1) **NHL Legacy
Native**, the PC port, as a second host (`savedata.Native`, `native.py`, one picture list per host). Played on a
copy: rosters, pictures through `--compose`, a game, a Season to 22 Oct, a Be a NHL Pro career edited by the program. Not played
there: the Roster editor's Save through the window, the launcher's PLAY. (2) **Penticton Vees** in slot 251: WHL in Play Now and
Roster Management on the patched game (art 902), Custom Team 30 elsewhere, on the game's own roster unpatched left out (the
unpatched lists walk ids with no gaps: `layout.listed`, `with_vees(listed=)`). The 16th prospect pool merges into the others. Their
games in the game's calendar failed in the lab (a hang on 25 Sep), so the 68 games are in our Calendar tab only. Patch stays 0.26.
(3) **Apply names** (`pipeline.apply_names`, `cli names apply`). (4) Found on the way: every update 1.01 career was refused by
`careersave` (`VERSIONS`); `install.remove_store(folders=)`: Unpatch reached every RPCS3 in the patch list; `contracts.starter_league`
counts the Vees as CHL. Be a CHL Pro's crash (GAME_PATCH.md, round 44) also hits a drafted junior; not fixed, needs a patch round.

**Version 0.92.0 (2026-11-01, released with the owner's go-ahead: commit c6b6433, tag `v0.92.0`, GitHub release with
`PuckPeakLegacyUpdater.exe`, the Linux tar.gz (Ubuntu / Fedora / Arch boxes passed) and `SHA256SUMS.txt`; the data pack of
2026-11-01 was published the same day, the game patch stays 0.26; plan docs/plans/eventual-baking-thacker.md, PLAN.md top):**
(1) **Blank window** (01690f0): the page says "Starting..." before any script, `bridge.js` waits with a time limit and shows "Try again",
`store.receive` shows an `{error}` reply, a Python watchdog in `window/main.py` reloads the page, restarts once with the GPU off, then
opens the classic window by itself; `start.log` (last 20 starts) in the app folder; `web/manifest.txt` lists the page's files
(`missing_files`); `tools/start_stress.py`. The tester's real cause is not known. **Second pass** (2026-11-01, table with what was
reproduced in docs/notes/blank-window.md): `Guard` in `main.js` (an error while drawing left an empty window that nothing noticed),
`__lrOk` after the first tab drew and `Api.page_up` (the watchdog waits for that, not for `ready_done`), `main.web_types` (the PC's
registry names the local server's file types), a reload that really reloads (`load_url` of the same address did nothing and
stopped pywebview answering), `startlog.listen` / `engine_failed` (pywebview's words into start.log, a dead engine wakes the watchdog),
`startlog.watch_requests`, `check_engine` (mshtml: simple window), `watchdog.browser_folder` (`webview/<pid>`, a folder per start: a shared
one gave a real blank start, WebView2 "0x800700AA ... in use", right after a close; `sweep` clears what dead starts left; a retry after an
engine failure is not remembered as "graphics off", `AFTER_ENGINE`),
`boot.js` `loadAgain` (a file that fails: the page loads itself again, 5 times at most, after `pywebviewready`, or pywebview forgets its
first question; a second real blank start: Windows refused one connection to the page's own server, error 10055), `bridge.js` `firstData`
(asks again at each `pywebviewready`: a page replaced while loading gets pywebview's setup twice), the watchdog's own address `?reloaded=1`,
`WebHost._read` (a slice that fails is told once, `update` alone stops the start), the failure screen's two buttons (they never worked).
Also `looks.ROWS_KEPT` (the alternate rows leave `art_fit` its 4). (2) **Cleanup** (75d4641): the classic window follows the
game patch and says why it opened; `.github/workflows/windows-release.yml` signs through SignPath (written, not run: needs a push and
the owner's SignPath account); Multiplayer.txt moved to `private/`. (3) **Alternate jerseys** (4506572): `looks.pack_versions` /
`team_versions` take the pack's `third` kit for the team's Alternate row (`locstring` 2); a team with none gets a new `wgjx` row
(`looks.alternate_rows`, run in `pipeline.build` only when this season's jerseys are being installed, before `gamepatch.art_fit`'s rows)
whose files are borrowed from its Away version (`looks.Borrow`, `renamed_variant`; `'alternate jerseys'` experimental). Lab round 57
(docs/notes/lab-round-57.md): a new row with files is listed and worn; a row without files draws a plain blue jersey (no crash). The
pack with the thirds' number sheets (`private/build_looks.py`, `FONT_ROLES = ROLES`) is published (2026-11-01, owner's go, 88 MB): the
pictures of the pack before it, byte for byte, plus 89 `f/<slot>_third.webp`; those sheets are not seen in the game yet. Only 0.92.0
wears the thirds (0.91.0's `pack_team` skips them, no redraw). (4) **Custom teams**: the Jerseys & ice tab has an arena name field (`ice.arena`, `uniforms.set_arena`); typed team
colours leave `layout.OWN_KIT` pieces alone (`custom_kit.hand_made`) unless the kit says `all` ("Paint everything"). (5) **Centre ice** (lab round 58, docs/notes/lab-round-58.md):
`looks.shown_centre` said the NHL shows its arena's art; it shows the team's own (`ARENA_ICE_LEAGUES` = the DEL). The DEL's 14 clubs
keep their one shared file and the national teams theirs (501): the owner left a patch entry for the DEL out (2026-11-01, "not
important"; its words, never played, are kept in that note, and the patch stays 0.26). (6) **Real lines after a late signing**
(found by the data pack of 2026-11-01's second-run test): `contract_strays` deals a team again after `lines_from_games` took
its place, so the team lost its real lines until the next update; it now lays them back on (`lines_from_games(teams=)`).

**Version 0.91.0 (2026-10-30, hotfix, owner: "support all the heads ... dont limit the save or hinder the editing";
released with the owner's go-ahead: commit 4b997b6, tag `v0.91.0`, GitHub release with `PuckPeakLegacyUpdater.exe`, the
Linux tar.gz (Ubuntu / Fedora / Arch boxes passed) and `SHA256SUMS.txt`; no data pack or server change):** a
tester's own player (Create Player record) wore head 20300, one of the game's 24 created heads but not one of the menu's
15, and `faces.look_problems` refused every save. Now `faces.CREATED_HEADS` (all 24, or the roster's `vuqu` rows) are
accepted, and what the source already held is never blamed: created head, skin vs tone (`look_problems`), Create Player
links (`link_problems`), art ids 20073 / 20081 and farm teams (`verify`; 900 / 901 still follow the patch). The player's
own edited deals skip `contracts.problems` (`free=mine_pid`; `contract_edit_problems` already allowed them). The Look
window still offers only the 15 (owner: no editor change now). Also the custom-team kit keeps typed team colours without
"Paint everything" (`app/teamkit.py`). Audit of every value check: docs/notes/free-editing.md. Not touched (lab first):
strategy values above the menu, draft-class tiers 8-9, forward types 1-4 for the builder. Test
`test_created_looks.py::test_a_created_head_off_the_menu_that_the_roster_had_is_saved`.

**Version 0.90.0 (2026-10-29, released with the owner's go-ahead: commit 6c8956c, tag `v0.90.0`, GitHub release with
`PuckPeakLegacyUpdater.exe`, the Linux tar.gz (Ubuntu / Fedora / Arch boxes passed) and `SHA256SUMS.txt`; the game server
and the data pack were updated the same day; plan docs/plans/transient-marinating-curry.md, PLAN.md top):** Phase 0 **free editing** done: `verify(free=)` drops `FREE_TEAM_FLAWS` / `FREE_PLAYER_FLAWS`,
`multi_club`, `contract_violations`, `style_problems` (`ratings.FREE_STYLES`), the rating range and contract-edit bounds
for the player's own edits (`b.free`: True on an edit-only save, else the edited rows / slots); the builder's own output
still meets every check. `verify.short_teams` -> `info['heads_up']` (gold line in the editor, "Heads up" rows in the
result); `Builder.players_team` keeps call-ups off teams the player shortened; editor locks `_too_few_without` gone.
Table of checks with proofs: docs/notes/free-editing.md; lab round 56 played every freed check, unpatched and patched
(docs/notes/lab-round-56.md). Tests tests/test_free_editing.py. Phases 1-2 (server repo, not deployed): every match report as JSON lines in `reports/`,
MatchBook / Elo / board / chat / `/board` page (deploy + Caddy `handle /board*` need the owner's go). Phase 3: the Play online
tab's guest check (`OnlineController.guest_problem`: the host's roster against the guest's patch), You card, chat with six
phrases, my matches / leaderboard / hide me, result window; works without the new routes (cards hide). Phase 4: the overlay
(`legacy_roster/hud/`, row "Online play"). Phase 5: retired players (data pack part `retired` from `tools/retired.json`,
Kopitar only so far; unsigned last-season players 38+). Phase 6: the editor's Save installs the edited teams' jerseys / ice /
crests (`pipeline.Pictures(looks_for=)`). Phase 7: no rules card (docs/notes/online-settings.md "Phase 7"). Phase 8: editor /
edits follow the roster's layout for 222-233 (`layout.copies`, `Snapshot.copies`, `Player.clubs`). The native PC
port is on the backlog (ROADMAP "Ideas", docs/notes/native-port.md).

**Version 0.85.0 (2026-10-28, built, committed locally (b98e5b0), not pushed; notes docs/notes/tester-reports-2026-10-28b.md, PLAN.md top):**
(1) **Linux / Mac patch switches**: RPCS3 adds `config/` only on Windows (`fs::get_config_dir(true)`), so on Linux it
reads `~/.config/rpcs3/patch_config.yml`; we wrote `config/patch_config.yml`, never read there (the game ran unpatched,
the program believed it patched). `patchinstall.config_file` follows RPCS3; `carry_over` (via `_read_config`, in every
read of the switches) moves our switches from a `config/patch_config.yml` of 0.80.1 / 0.81.0 into RPCS3's file, so a game
patched then (patch file and db files in) is patched now; `onlinecfg.account` also reads the top-level `rpcn.yml`.
Checked in an RPCS3 box on the server (real RPCS3 Linux AppImage, `legacy-linux-rpcs3`): PLAN.md top. (2) One Windows exe:
`build.ps1` no longer copies `NHLLegacyRosterUpdater.exe` (owner; `selfupdate.OLD_EXE_ASSET` stays for reading old
releases). (3) Everything below ("After 0.81.0"). Online match reports: docs/notes/online-match-reports.md (the game
sends them, the server keeps nothing).

**After 0.81.0 (2026-10-28, part of 0.85.0; notes docs/notes/on-a-team-and-free-agent.md):** a
tester's game-saved 2014 roster with KHL clubs in custom slots. `Builder.unlist_club_players` (a club player on the
free-agent list leaves it and keeps the game's deal; verify `('fa on team')` covers every club); after Save as new the
editor opens the new roster (`EditorController._open_saved`, `UpdateController.set_rpcs3(then=)`); in an export from a
roster file the team tabs show the file, Save off (`UpdateController.roster_file`, `editor.RosterFile`, `SaveBar` `save.file`;
`tools/window_shot.py export-roster`); `Builder.mirror_of` / `same_team` follow the layout (no copies on the game's own
roster), `stock.add_spares` skips models whose type is not their position's. The window / edits still treat 222-233 as
copies on every roster (follow-up). Open: the game's link-0 places (Kukkonen "on every team"), lab first.

**Photo pack (2026-10-28, part of 0.81.0, published with the owner's go):** the owner's folder of 848 player photos replaced 765 portraits of `photos.zip` (new `photos-691d56680e8a.zip` on the server, old pack kept there; notes docs/notes/photo-folder.md, tool `private/photos_folder.py`; long faces scaled so the jaw stays above the shoulder fade).

**Version 0.81.0 (2026-10-28, built, committed locally, not pushed; plan docs/plans/purring-watching-pearl.md, PLAN.md top, lab notes
docs/notes/lab-round-55.md):** three testers' reports. (1) **The Roster editor saves the game's own roster**: `pipeline.build`
runs `stock.prepare` only when an update step runs (`as_disc`), so an edit-only save keeps the 2014 roster (All-Star teams, birth
years from 1900: `stock.untouched` / `birth_base`, used by `edits`); `export_sysdata` refuses only the untouched disc roster.
(2) **Export / picker**: `UpdateController.use_export_file` refuses only `stock.untouched` files (text `texts.GAME_ROSTER_FILE`);
a roster updated from the disc is an ordinary roster file. (3) **"NoneType" while updating**: `datasource.flatten_nhl` /
`find_missing` skip pages without birthDate / names; `jobs.where` puts `file:line in function` into "Something went wrong".
(4) **Any letters** (lab round 55: none, all C, all A, goalie letters played in Play Now, Edit Lines opens): `lines.check_lineup(
free_letters=True)` for the player's own lines (`app/lines.py`, `edits._team_lines`), `verify.structure` no longer counts letters,
`set_letter` no longer clears other captains; the builder's automatic lines keep three letters per NHL team; a letter on a player
not on the team stays refused. Season mode / Be a GM with such teams: not played. Version in `__init__` 0.81.0, CHANGELOG entry.
Tests: test_stock_edits (new), test_lines_strategy, test_captains. Not built yet: Exe / Linux builds, window shots, slots 30 / 31
shown with the All-Star names on a 2014 roster.

**Version 0.80.1 (2026-10-27, released with the owner's go-ahead: commit 16985e2, tag `v0.80.1`, GitHub release with both exe names, the Linux tar.gz and `SHA256SUMS.txt`; plan PLAN.md top "LINUX PROGRAM"):** a tester's Linux program opened the
classic window (0.80.0's from GitHub needed the system's WebKitGTK). Now: the program is named **PuckPeakLegacyUpdater**
(owner; `selfupdate.EXE_ASSET`, the release also carries `NHLLegacyRosterUpdater.exe` for older copies' update check;
the data folder `NHLLegacyRosterUpdater` stays), only the Windows exe and the Linux program ship (no Mac, no cli exe;
owner), the Linux program uses Qt WebEngine from PySide6 (`window/main.linux_engine`) as a PyInstaller folder,
built and checked in Docker boxes on the owner's server (`packaging/linux/`, `linux_check.sh`: the new window must
open on Ubuntu 24.04, Fedora, Arch), `savedata.clean_environment` keeps the program's libraries away from RPCS3 /
xdg-open / gio. GitHub's workflow only tests (Linux, Windows).

**Version 0.80.0 (2026-10-27, released with the owner's go-ahead: commit 1f0c212, tag `v0.80.0`, GitHub release with the exe
and `SHA256SUMS.txt`; carries every test version since 0.52.0 (0.60.0-0.78.0 were never released on their own); plan
docs/plans/while-the-other-sessions-pure-goblet.md, notes docs/notes/overlay.md 10b, community-extras.md "New centre ice"):**
the owner's asks after 0.78.0. **The new scoreboard is out** (owner, 2026-10-27, after lab round 54's pictures: the SN badge
a white box on navy, the score bug's team logos off centre, a see-through gap under the power-play bar, an odd player card;
"restore back to normal ... leave this feature out even from the app"): parked in `private/scoreboard/` (README.txt, `hooks.patch`).
`parts.OVERLAY_TAG` is a retired tag (`RETIRED_TAGS`, belongs to no part); `install.remove_retired(say)`, first in
`pipeline.Pictures.put_in` (RPCS3 closed), puts back what a test exe (0.78.0 / 0.80.0 test build) installed with that tag;
Restore default does it too. An old settings file's `overlay` / `overlay_logo` keys are ignored. The server's manifest still
lists `overlay-f285aae725b5.zip`; nothing reads it (taking it off needs the owner's go). The lab was put back (round 54).
(1) **Pack `ice` published** (owner's go, 2026-10-27: `publish_packs.py --only ice,overlay`; the data pack went with them
unchanged). A pack the manifest lacks was treated as fine (`packs.sync`), so a row said "Downloaded automatically" and the
update installed nothing. Now `UpdateController.not_served` gives such a row `texts.PICTURE_NOT_SERVED`, `pictures_short` (a
list of pack names) puts `texts.pictures_short` into the result, and `pipeline._extra` a "... not installed" row into the List
of changes. (2) **The new centre ice comes with this season's jerseys** (no row, no choice):
`settings.TOGETHER` = {`looks`: (`looks`, `bright_ice`)}, `row_parts`; `bright_ice` follows `looks` at start (also from an
older settings file), in `set_step`, the group count (`GROUP` without it) and Restore; cli `--looks` adds it (`--bright-ice`
alone still works), and so do `--photos`, `packs download` and `export-files --photos` (`cli._photo_parts`). Precedence unchanged (own > new set for art 0-29 > this season's > game's); Seattle / Vegas play at arena
art 16 (Nashville's file) on the owner's roster, as before. `brightice.covered` ignores an old pack's entries. Tests
test_extras / test_app (the scoreboard's left with it; a retired-tag test and an old-settings test added). Built again
2026-10-27 18:43 without the scoreboard (window opens as 0.80.0, cli has no --overlay). Below, 0.78.0 as it stood:

**Version 0.78.0 (2026-10-27, built locally, not committed; plan docs/plans/while-the-other-sessions-pure-goblet.md, notes
docs/notes/overlay.md, community-extras.md "New centre ice", lab-round-53.md):** (1) **New centre ice** (the Bright ice
switch, key `bright_ice`, pack `ice` 5.5 MB, `'new centre ice'` experimental): the owner's newer centre-ice set for art
0-29, each encoded raster laid into the player's own disc file (`art/brightice.py` `centre_file`, `covered`; built by
`private/build_extras.py --ice <folder>`). It works beside this season's: the player's own centre (Jerseys & ice) >
the new set > this season's (Seattle, Vegas, clubs) > the game's (`pipeline.Pictures.new_centres`, `install_looks(new_ice=)`
-> `looks.OTHER`: no centre file, Utah's rink picture still drawn; with looks off `brightice.rink_file` takes the coyote out
of `icesurface_22_bm`). The 0.76.0 "one or the other" rule is gone. (2) **New scoreboard** (taken out again in 0.80.0; `parts.OVERLAY`, pack `overlay`
~30 KB, its own row, default OFF, not in the Photos group; `'new scoreboard'` experimental): `art/overlay.py` rebuilds the
player's own `cacheoverlay.big` files (`fe/ion/game/overlays/<name>.big`, a BIGF of an Apt movie + RefPack'd DDS pictures;
`rebuilt` keeps the game's layout, every disc file comes back byte for byte) with the pack's pieces (`clear`, `picture`,
`tint`: the game's shape in our colour), same-length byte edits of the movie and the corner logo boxes (`boxed`: `inset`,
`plate`, `fill`), each file tied to the sha1 of the disc's; loose files, tag `overlay:`. Corner logo = the player's choice
(`overlay.LOGOS`: SN from the pack, Puck Peak = `data/app_256.png`, none, own picture copied into the app folder;
settings `overlay_logo` / `overlay_logo_file`, `UpdateController.set_overlay_logo` / `pick_overlay_logo`, `update.js`
`LogoPick`; cli `--overlay --overlay-logo`). The pack: `private/build_overlay.py "<overlay folder>" --fix` (the owner's mod
as diffs + `FIX` / `SPIN`: white plates navy, power-play text / score white, the game's band / mask / separator / card
grill back, the stock spinning logo boxed in overlay_0 / 1 / 17 / 24 / 27 / 28 / 29). Team logos in the score bug show
in its long form (the game's extended mode; lab 53 saw it much of the game) and not in its short form (docs/notes/overlay.md 4). `tools/apt_dump.py` reads Apt
movies. Lab 53 / 53b (docs/notes/lab-round-53.md, the lab's EU 1.00, through `private/lab/round53.py`): the game reads the loose
overlay files (no crash); the fixed pack showed the score bug (both forms), the goal line, the player card, the penalty /
offside / replay boxes in navy with white text; Utah's new centre ice with clean edges and no coyote; put back byte for
byte. Not seen: the power-play bar (no power play came), overlay_17 / 27 / 28 / 29 (never loaded in that game); a faint
light bevel line inside the bug's slanted right end. Packs published 2026-10-27 (see 0.80.0); "SN" is a real broadcaster's mark (owner's call). Version 0.78.0 in `__init__`, CHANGELOG.

**Jersey lettering (2026-10-27, after 0.76.0; plan docs/plans/i-got-access-to-structured-bunny.md, notes
docs/notes/jersey-numbers.md):** the owner saw lines above / under McDavid's number, Utah's home jersey in light-blue
digits and Pittsburgh's sleeve numbers gold. The look pack now carries each home / away kit's own number sheet
(`f/<slot>_<role>.webp`, index `font`, `private/build_looks.py` `font_sheet` / `without_plate`); `looks.put_sheet` writes
it as `font_cm` / `_sm` / `_nm` in both cuts, `with_marks` fills marks the sheet lacks (apostrophe, period, hyphen) from
the player's own disc; Utah / Seattle / Vegas versions `DEFAULT_VERSIONS` made from colours wear the pack's kit
(`pack_team`); the fallback `recolour_numbers` carves its rings inside the glyphs. `LOOKS_DRAWING` '#8'. Lab 2026-10-27:
sleeve = small row 1, helmet = small row 2 (sheets go in as they are). Lab, the program's own files (`pack_team` ->
`pack_files`) from the rebuilt pack (214 teams, 82 MB): Utah's Home (variant 0) white digits with a light-blue ring and
white name, Pittsburgh gold back / black sleeve digits with a white ring and the gold C, Edmonton's blue digits with
no line above or under and the hyphen of NUGENT-HOPKINS (`with_marks`). Not played through the exe yet (the owner).

**Version 0.76.0 (2026-10-27, built locally, not committed; plan docs/plans/i-got-access-to-structured-bunny.md, notes docs/notes/community-extras.md):**
the owner's community "26-27 Extras" folder (`Community data/`, git-ignored) and the split of the one picture switch. (1) **Six
picture switches** (`art/parts.py`: `NAMES`, `PHOTOS`, `LOOKS`, `ARENAS`, `BRIGHT_ICE`, `TEAM_MASKS`; settings keys in
`app/settings.py`, rows `UpdateController._picture_row` / `texts.PICTURE_ROWS`): team names need no download and default ON, photos +
logos (~105 MB) are the gold row, the rest are small packs. `pipeline.Pictures(parts=)`, `pipeline.update(art_parts=)` (default
`parts.LEGACY` = names + photos + looks: the old switch), `install.install(pictures=False)` = names / menus only. Each installed file
carries a source tag (`names:` / `menus:`, `looks:`, `arenas:`, `ice:`, `teammask:`, `crests:`, `mask:`, photos = none), so
`install.remove_parts` / `restore.picture_part` undo one part without touching another (rule 10 holds); `Restore default` still removes
everything. A settings file from before with photos on turns `names` and `looks` on. The classic window (`gui.py`) keeps the old one switch.
**Behaviour change:** names default ON, so on a real RPCS3 an update goes through the pictures path (RPCS3 closed also for a new save).
(2) **Packs** (`packs.NAMES` = photos, looks, arenas, ice, masks; `packs.sync(wanted=)`; a manifest without a pack is fine; the update waits
only for the packs its switches need). `private/build_extras.py "<community folder>"` makes `arenas.zip` (13 MB: per art id the sha1 of the
disc's unpacked stadium file + byte runs; `art/arenas.py` lays them over the player's own file, a sha1 mismatch = another game version,
skipped with a line), `ice.zip` (`art/brightice.py`: ice_hotspot_0_* and the white-backed centre circles, lossless WebP, same raster
size as the disc; a centre ice the look pack installed is left alone), `masks.zip` (`masks.install_team_masks`: team ids 2-29 without
22; the player's own mask ids win). `tools/publish_packs.py` sends every pack in `private/packs` (`--only a,b`; manifest merged,
last). Left out by the owner: the community's jerseys. Not built: the heads fill (their `.big` heads do not open in Pillow). tests/test_extras.py.
**Not seen in the game:** the arenas (lab check first, drop the switch if wrong), bright ice, team masks; EU vs NA base files of the
arenas (compare before publishing). Nothing published, nothing pushed.

**Version 0.75.0 (2026-10-26, built, committed locally with the owner's go, not pushed; plan docs/plans/plan-the-debugging-and-magical-nest.md):**
(1) **Real equipment** (`'real equipment'` experimental; notes docs/notes/equipment-accuracy.md, equipment-labels.md): lab round 51 named every
number in the game's Edit Player menu (sock tuck 0 Full / 1 None / 2 Front / 3 Back, visor 0 Straight / 1 Curved / 2 None, tint, pads Small / Big,
goalie neck Off / On; `equipment.OPTIONS`, `VISOR_FILE` for the menu pictures; the old window had the sock words in the wrong order). Data pack part
`equipment` (private maker `private/equipment_db.py`, `--refresh equipment`, read by `datasource.equipment_part`, raw numbers: sock, pants, tape class,
neck guard; the NHL's and the AHL's curated rows, 1,137 players; never a model number), `Data.equipment`, `Builder.real_equipment()` (full name +
birthdate + goalie / skater, exactly one entry; `equipment.REAL` / `real_values` copy sock, pants 0/1, tape black 0 / white 1, neck), run in
`pipeline.build` before the player's own edits, which win. `Builder.take_record` gives a new player `equipment.NEW_PLAYER` (not the last holder's gear).
Read back on the community roster: 715 sock tucks, 143 pants, 425 tape, 51 neck guards changed, 0 other fields, second build identical.
Players get it only after `tools/publish_packs.py` has put the new data pack on the server (owner's go). tests/test_real_equipment.py,
test_equipment_data.py, test_equipmenttest.py. (2) **AHL arenas** (`builder.AHL_ARENAS`, `ahl_identity`, runs with the AHL step; Coachella Valley,
Henderson and the Barracuda get rows of their own: 191 of 192 arena rows used). Not seen in the game yet: the new look of sock tucks on the ice, the AHL
arena captions. Custom match dropped (owner). Not pushed.
Below, 0.70.0 as it stood:
**Version 0.70.0 (2026-10-26, committed locally with the owner's go, not pushed; plan docs/plans/plan-the-debugging-and-magical-nest.md, PLAN.md top):**
the owner's tester list `Features`. 32 NHL arenas + colours (`builder.NHL_LOOK`, `nhl_identity` on every roster), the Jerseys tab's colour / arena edits
written into `ttOk` / `OEtS` (`edits._team_colours_arena`; `'team colours and arenas'` experimental, notes docs/notes/arenas-colours.md), Lines `place`
changes only the picked slot (`LinesController.carry`), mixed game versions allowed with a warning (`OnlineController.game_note`; the server's version gate
is gone from the source, not deployed from here). Not yet: the in-game check of the arenas / colours, lab debugging of mixed versions, custom match, Linux, export.
Below, 0.65.0 as it stood:
**Version 0.65.0 (2026-10-26, test build for the owner's human test, not committed; plan PLAN.md top):** (1) "Photos, logos and team
names" starts off for everyone once (`settings.PHOTOS_DEFAULT`, `UpdateController.__init__`; a later choice is kept); the online
start (`patchinstall.set_screens`) now writes its own `mainmenuitems.big` (`MENU_SOURCE`, `_menu_in`, store `PATCH_STORE`) so zero
presses work with Photos off, and `install_menus` skips a file the online setup put in. (2) Play online: Public is the default (app
`OnlineController.public`, `lobby.create(public=True)`, server `LobbyApi` `IsPublic ?? true`). (3) **Spike S4 (docs/notes/online-settings.md):**
Quick Match sends PeriodLength 5 / Rules 1 / Injuries / Fighting / Penalties / CreatedPlays as fixed search values; a server override
of `PeriodLength` reached the game's data but the game still played 5 minutes, so there is **no match settings card** (the lobby says
"standard online match"). (4) Lab (EU 1.00 host vs NA 1.00 guest, by hand through the lobby API): the two pair and reach Select Teams, no
region gate; NA online needs `game-patch online` in its RPCS3 (done in lab2). **Game 1.01** (the owner's two update packages, installed in the lab copies only): the start entry is ported (`gamepatch.ONLINE_START_101` at 0x1063e24, 1.00's 0x1062514 moved by 0x1910, 21 words around it alike; `tools/audit_patch.py` on EU and NA 1.01: 0 problems), `patchinstall.auto_start` / `set_online_start` / `set_screens` follow the game version RPCS3 runs. Lab (2026-10-26): EU 1.01 alone went to Online Versus Play and searched by itself (no key); EU 1.01 host + NA 1.00 guest, ready lobby: both on Select Teams, Ranked, 5 MIN, NHL rules (docs/notes/update-101.md "Online start on 1.01"). NA 1.01 and EU 1.00 against EU 1.01 not played (same program as EU 1.01 / same word as 1.00). (5) **Server
deployed 2026-10-26** (owner's go; backup `/opt/overtime-legacy-src-bak-20261026.tgz`, 41 tests in the box's SDK container, live smoke ok);
the S4 logging / override code was removed before it. Not played through the exe by two people yet.

**Version 0.60.0 (2026-10-25, test build for one tester, not committed; plan docs/plans/spicy-napping-mountain.md):** the Play
online tab uses the **lobby host's roster** (owner's decision), not an official one from manifest.json. `app/online.py`
(`create` copies the picked Setup roster into the online save and uploads it; `_sync_roster` downloads, checks the CRC and
installs it for a guest, never while RPCS3 runs; `_sync_me` tells the server a changed patch), `lobby.py` (`put_roster`,
`get_roster`, `update_me`), server routes `PUT/GET /api/lobby/{code}/roster`, `POST .../me`. Both players need the same
patch word or Ready is refused (hint: update the program). **Online play needs the game patch** (owner, 2026-10-25): Set up online asks, then patches;
the RPCS3 build (`onlinecfg.rpcs3_build`, log header) is told to the friend, a build under `onlinecfg.MIN_RPCS3` is refused; the game version 1.00 / 1.01 is not flagged
(test first); plan docs/plans/last-message-from-you-effervescent-boot.md (Part B, settings in the app, is a lab spike first). Tests: test_online (19), test_lobby, test_onlinecfg;
quicktest 214 passed. Public lobbies (`lobby.lobbies()`, `OnlineController.rows` / `list_once`, the tab's Private / Public switch and "Open lobbies" list) are built in the app and the server code; the server is not deployed yet. Not played in the game; which roster the game loads at boot is still unconfirmed, so the steps keep
"Load the online roster". No commit, push or release without the owner's go-ahead.
**Zero presses (2026-10-26, lab-proven on EU 1.00, not played through the app):** `art/onlinestart.py` (start cave + Welcome Back + matchmaking gate), `patchinstall.set_screens` / `auto_start` / `set_online_start`, `app/online.py` `_start_game` ticks the start entry for one launch; member tokens (`X-Lobby-Token`, `lobby._tokens`), `onlinecfg.roster_check`; the server's `PairLobbies` pairs only lobbies in state starting (source in the private server repository, deploy needs the owner's go); docs/notes/online-boot-hook.md, multiplayer.md "Security and what is stored".

**Version 0.52.0 (2026-10-25, released with the owner's go-ahead; plan docs/plans/can-you-check-and-partitioned-kitten.md):**
(1) **"Kraken has 49 players" again after 0.51.2**: online, `datasource.find_missing` looks up players NHL.com's roster
lists leave out and gives each his NHL organisation, so a farm club's players come back with their parent (Coachella
Valley's as `SEA`); `nhl_rosters` put them all on the team. `Builder.searched_room` (before `nhl_rosters`): a searched
player a club league lists stays there, the rest join while the team holds fewer than `NHL_KEEP_ROOM`; `b.nhl_listed`
is what the NHL step placed (verify gets it). tests/test_nhl_search.py (fails on the old code). Online export of the
community roster on 2026-10-25: Seattle 26, every team <= 40. The tester's file was not seen.
(2) **Calendar marks** (patch 0.26, year entry 0.9, docs/notes/lab-round-49.md): `GetTeamMatchIDByDate` (`0x4078b0`)
gave no game for a year after the league year + 1, and the screen's year is 11 later with the patch: three words in
`YEAR_LABELS` (`0x407954` / `0x407960` / `0x407964`). Played in lab round 49 (Be a GM: NHL and AHL views); players
see "Patch again".

**Version 0.51.2 (2026-10-24, released with the owner's go-ahead; plan docs/plans/can-you-check-and-partitioned-kitten.md):**
also `gamepatch.future_fit` shrinks the next season's calendar table to `schedule.PATCH_ROWS` when the patched game saved
the roster with room for 1,459 (`test_gamepatch.py::test_the_next_seasons_calendar_is_trimmed_...`). A tester's export
stopped with "Kraken has 49 players (max 40)". Kraken is slot 228, the community roster's copy of Seattle;
`Builder.sync_mirrors` indexed the copy by player, so second entries of one player were never taken off and Seattle's
players were added on top. It now keeps one entry per player (twins and entries naming no player go, a summary line says
how many); `verify.structure` names a team listing a player twice (`'twice'`) and the mirror check compares counts.
tests/test_mirrors.py (fails on the old code with the tester's error). The tester's own file was not seen: the most
likely cause, not confirmed.

**Version 0.51.1 (2026-10-24, released with the owner's go-ahead: commit 254739a, tag `v0.51.1`, GitHub release, data pack published; plan docs/plans/also-we-issued-0-51-0-vivid-hellman.md, notes
docs/notes/captains.md):** a tester: Winnipeg's captain Lowry had no letter (0.51.0 did not cause it: letters were never
real except Liiga's). (1) **Real captains** (`'real captains'` experimental): NHL from NHL.com's game roster reports
(`nhl_lines.read_letters` / `game_letters`), AHL / CHL from HockeyTech game summaries (`hockeytech.club_letters`),
Extraliga from the onlajny match rosters (`hokejcz_lines.letters_of`), each counted over the last 5 games
(`tools/providers/letters.count_letters`); the private database's `lcCm` fills clubs and NHL teams the live sources leave
without letters (`private/club_lines_db.py`, `build_datapack.give_letters`). Builder: `real_letters` (NHL in
`lines_from_games`, every club in `feed_letters` at the end of `repair_lineups`), `national_letters` (national teams
filled this run: their players' own C / A first); `real_line_up` checks clubs with `nhl=False` now. `verify.structure`
checks every team's letters (one C, three at most, no goalie). Result line "Captains". (2) **Error log**: `jobs.run(context=)`
/ `jobs.log_block` write one block per failure (time, version, roster, folders marked "missing", steps, traceback);
`app/update.update_context`; safety-check failures and failures after the save are logged too. (3) **Honest "saved"**:
`pipeline.update` runs everything after the save through `then` (`UpdateResult.after`); the window keeps "Saved as" /
"Updated" and shows red lines (`show_result(bad=)`, `texts.SAVED_DESPITE`), with an "Error log" button. (4) On the
game's own roster the NHL step always runs (Restore default + patch left Seattle / Vegas empty: "0 captain(s)").
(5) **Restore / Unpatch past a game folder that is gone** (the tester's "[WinError 3]"; deleting the app folder "fixed"
it, but never do that: edits, backups, kept originals): `install._put_back` skips a game folder that is not there and
keeps its entries (`_forget_handled`, `_left_line`), recreates a missing subfolder before putting a kept copy back
(also `_Writer.drop`); `check` and `installed` ignore vanished folders. Tests `test_art.py::
test_restore_gets_past_a_game_folder_that_moved_or_lost_a_folder`, `test_patchinstall.py::
test_unpatch_gets_past_db_files_of_a_game_folder_that_is_gone`.
Tests tests/test_captains.py, test_app (error log, after the save); full suite 565 passed. Dry run on the community roster:
"32 NHL teams and 161 clubs wear this season's letters, 8 national teams ..." (Norway's 2 clubs: no source). Data pack
`--refresh lines,ahl,chl,extraliga,extraliga_lines,club_lines` on 2026-10-24; the release needs `tools/publish_packs.py`
too (players read the letters from the pack). Not played in the game.

**Version 0.51.0 (2026-10-24, released; owner: "fix and support the lines for AHL and others", Extraliga a focus; notes
docs/notes/lines-from-games.md, lines-other-leagues.md):** (1) **NHL lines announced first**: `tools/providers/dailyfaceoff.py`
(the team pages' data, matched to NHL.com's roster; `merge` per category with the games' lines; tests/test_announced_lines.py)
fixed McDavid at LW / RW. (2) **Real lines for the clubs outside the NHL**, data pack part `club_lines` = {club slot (str):
{'date', 'source', 'slots': {slot name: [first, last, birth year]}}}: the private maker `private/club_lines_db.py` takes the lines
of a larger database (table `ulGe`, 49 of the 71 slots: no 5-skater power play pp1 / pp2 and no overtime; it has even strength, goalies, the 4-skater power play, both penalty kills, shootout, extras) and matches each of its teams to a club slot by the players they share
(`--refresh club_lines`, no network, after the leagues); `tools/providers/hokejcz_lines.py` reads the Extraliga's match
line-ups from hokej.cz's own files (day list `json.esports.cz/hokejcz/scoreboard/onlajny/<date>.json`, roster file
`data.onlajny.com/hockey/roster/<year>/<id>.json`; slot codes 101/102 goalies, 21x-24x pairs, 31x-34x forward lines, middle = centre,
inferred) and `merge` lays them over even strength + goalies (`--refresh extraliga_lines`; power play / kill stay the database's).
`Builder.real_club_lines(slots)` runs last in `repair_lineups` (after every step that moves players, else a second run differs) and
uses `real_line_up` per club, players found on the club by name; result row "Club lines". Built roster: Extraliga 14/14, Liiga 15/15,
SHL 14/14, DEL 14/14, NL 12/12, AHL 32/32, CHL 58/60, Norway 0/2 (no data). The database's lines are older than the live rosters, so
`Builder.fill_real_gaps` completes a group when at most 40 % of its slots are open (the player who holds the slot now, else the club's
best of that kind) and drops a group with more gone; a player of the wrong kind for a line slot counts as gone. Shootout / extra
attackers replaced in `real_line_up` are forwards (they were any skater: a second run differed). tests/test_club_lines.py.
Pack must be refreshed before a release (`--refresh lines,extraliga_lines` for daily changes). Not played in the game.

**Version 0.50.4 (2026-10-24, owner's asks after the community's reports; plan docs/plans/warm-tumbling-sunrise.md):**
(1) **Real lines** from NHL.com's last five games per team (`tools/providers/nhl_lines.py`, data pack part `lines`,
`Builder.lines_from_games` / `real_line_up` after the rating deal in `nhl_lines`, `'real lines'` experimental, notes
docs/notes/lines-from-games.md, tests/test_real_lines.py). (2) **The AHL from the live feed** (owner: "match real
life"): `private/club_rosters_db.py` now takes who plays where from the feed (`tools/cache/ahl.json`, 803 players on
2026-10-24) and only adds each player's NHL organisation (`org`) from the database, else the club's parent when the feed
marks an NHL contract; pack AHL has `orgs`; `test_leagues.py` knows that Seattle / Vegas hold no rights unpatched.
(3) **Coachella Valley / Henderson as art 900 / 901** (owner: "Coachella as 900 and Henderson 901"; lab round 48 proved
the probe, docs/notes/lab-round-48.md: lab 34's blue square was the created-team flag left on with no rows and no files).
Only on a roster for the patched game: `gamepatch.art_fit` (last in `pipeline.patch_roster`, after `league_fit`: `ttOk`
`artid` 900 / 901, `BERR` `table` 0, the donor's `wgjx` rows re-keyed: Charlotte's 162 variants 3 / 4, Utica's 141 variants
0 / 1; `layout.CLUB_ART`, `CLUB_DONOR`), `gamepatch.unart` (called with `unleague` in `pipeline.build` and `unshifted`: the
builder sees 20073 / 20081 as before), `check_art_fit` + `verify` (900 / 901 only on 234 / 235 and only with `farm_patch`;
`custom_kit.problems` allows them). Files: `art/clubart.py` (`AliasDisc`: art 900 / 901 paths are read from the donor's file
with the art number renamed in the container header, same digit count; `Maker.__init__` wraps every disc in it, so the
existing "From the colours" maker paints them; `extra_files`: name sheets, banner, puck, goalie helmet as the donor's),
`looks.looks_from` / `with_club_defaults` (default: both versions from the colours, `OWN_COLOURS` with the main colour as
the dark jersey, and the crest drawn on the centre ice; the player's Jerseys & ice choices and the look pack win),
`clubart.rekey_logos` in `Pictures.put_in` (menu logos t900.big ... from the 20073 logos; install falls back to a template
of art 0). `'club art 900'` experimental; tests/test_clubart.py. **Not played in the game**: lab 48 played the plain donor
copies (Select Teams, Select Jerseys, a home game each; Be a GM, the unpatched game, helmet close-up and `r` logo not
checked); the painted version through the program is the owner's / the next lab round's check (ROADMAP).
Data pack refreshed 2026-10-24 (`--refresh ahl,lines,nhl`); release needs the owner's go-ahead (rule 6), and
`tools/publish_packs.py` for the pack.

**Version 0.50.3 (2026-10-23, released with the owner's go-ahead):** the update check looks at GitHub at every start (owner: "if there is new
update it should show up pop up"); `selfupdate.due` only reads the switch (before: at most every 12 hours, `CHECK_EVERY`
and the `update_checked` setting are gone), and `UpdateController._look_for_update` waits until no update runs and no
question shows before it offers (before, the offer was dropped). Copies of 0.50.2 and older still wait their 12 hours.
Tests `test_selfupdate.py::test_due_at_every_start_and_not_when_switched_off`,
`test_app.py::test_a_newer_version_is_offered_once_the_question_on_screen_is_answered`.

**Version 0.50.2 (2026-10-23, hotfix, released with the owner's go-ahead):** (1) **Season start crash on the unpatched
game** (a tester's NA 1.00 log, RPCS3 on Linux, no patch): the Season setup `0x2850c8` walks the club teams' players and
looks each one's NHL rights up in a 30-team table (`0x285628`: `lwz r11, 0x208(r6 + team * 4)`); Seattle's rights
(proteam 31, which five bits can store) read past it (`0x01dbdbdb` - 30 as an index, crash at `0x2710e4`). The
community's roster gives Seattle / Vegas nobody's rights; ours gave 48 players Seattle's (21 on Coachella Valley, CHL /
national copies). `contracts.rights_teams` (30 on five bits, 32 on six) / `holds_rights` in `Builder.set_pro_team`
(now sets 0 for a team that cannot hold rights), `real_contracts`, `clubs._rights`, `frontoffice` `rights_room`;
`contracts.drop_rights` in `pipeline.build` before `status_fit` (cleans rosters of 0.50.0 / 0.50.1, also on the
editor's Save), `verify` runs `contracts.rights_problems`. Test `test_contracts.py::
test_seattle_and_vegas_hold_no_rights_on_a_roster_for_the_unpatched_game`. Not played in the game (only targeted tests,
owner's wish for a fast release). (2) The **Join our Discord** button moved from the header to the top of the Setup
tab's left column (`shell.js` `DiscordButton`, `update.js` `SetupTab`, `.discord` in `css/app.css`).

**Version 0.50.1 (2026-10-23, released with the owner's go-ahead):** a **Join our Discord** button at the top right of
the window's header (`web/js/shell.js` `Header`, `.header .discord` in `css/app.css`, api `open_discord`,
`texts.DISCORD` = https://gg.puckpeak.com, a redirect to the Puck Peak Discord) and a Discord badge at the top of
README.md (also QUICKSTART.md, `docs/shot_done.png` remade). Also the Mac fix of `tests/test_patchinstall.py` (the
backup folder through `datasource.app_dir`, not LOCALAPPDATA). **A tester's crash fixed**: a second update after a full
one stopped with "no spare player record left for Owen Michaels" (the first update gives every spare record to the
club leagues, so an NHL.com newcomer found none). `Builder.make_room` (called by `take_record` when `required`): first
the least needed free agent of the same kind retires (`retires(force=True)`; never last season's NHL players, NHL.com's,
contracted, attached, listed, reserved names or Create Player records), else a CHL club with more than 2 G / 18
skaters of that kind gives up its weakest single-record player without NHL rights ("left to make room", logged under
the CHL part). Test `tests/test_leagues.py::test_newcomers_on_nhl_rosters_get_a_record_when_the_leagues_used_every_one`
(five newcomers after a full build; a third build byte-identical).
**Update 1.01** (a tester's NA roster "damaged"; notes docs/notes/update-101.md): the game's update 1.01 (EU and NA, from
Sony's server; RPCS3 then boots `dev_hdd0/game/<TITLE>/USRDIR/EBOOT.BIN`) has one program for both versions, PPU hash
`gamepatch.UPDATE_HASH` (EU and NA decrypt to the same bytes), with every place the patch names moved by 0 to 0x2030
bytes. Patch **0.25** writes each entry three times: EU 1.00, NA 1.00, and 1.01 for both titles
(`gamepatch.VERSIONS`, `at` / `ported_word` / `ported_code` through `legacy_roster/patch101.py` `ADDRESSES`, made by
`tools/port_patch.py <1.00 ELF> <1.01 ELF> --write`; `tools/audit_patch.py` checks either program: 0 problems on EU 1.00,
NA 1.00 and 1.01). Every title's patch file is the same text; `patchinstall` ticks both versions (`config_with(version=)`,
one 1.01 entry listing both serials, entries of others kept per hash), `game_version` reads the update's PARAM.SFO,
`state()` says `game` and `stale` (a 0.50.0 install on a game with 1.01: the window's "Patch again", `texts.MISFIT_STALE`,
`pipeline.update` refuses until then). `art/install.update_texts`: the loose text files start from patch.big's (13 more
texts, also the 3-on-3 overtime), since the game reads loose files before patch.big. Lab (NA 1.01, cli): Applied patch
under the 1.01 hash, the patch roster loads, Be a GM with Vegas at the $104M cap simulated to 15 Oct 2026 and saved, a
Vegas Be a Pro loads and saves; lab put back. EU 1.01 not booted (the same program bytes).

**Version 0.50.0 (2026-10-20 night, the owner's pick; released 2026-10-23 with the owner's go-ahead; plan
docs/plans/listen-right-now-the-robust-walrus.md):** the owner compared the window with the NHL19 companion app (notes
docs/notes/nhl19-app-ui.md), approved a clickable mockup (`private/mockup/`) and asked for it as "absolutely major
update" 0.50.0. Everything since 0.10.4 (the 0.35.0 entry below and older test builds) goes out with it in one commit;
CHANGELOG.md has one 0.50.0 entry (the release text is made from it).
- **Nine tabs** (`web/js/main.js`): Setup, Game patch, Update | Roster, Lines, Strategy, Jerseys & ice, Calendar, Front
  office. One team list (`web/js/rail.js`, slice `rail`) for the six team tabs, owned by `EditorController`
  (`follow_with`, `show_tab`, `team_view`); the team tabs' controllers are followers (`follow(team)`, `hide()`,
  `roster_changed()`) that work only while their tab shows; Lines / Strategy drafts are kept per team; Jerseys loads 250 ms
  after a pick. One Save bar (`SaveBar`). Smallest window 940 x 640. Lines, Strategy and Jerseys are tabs now (Equipment,
  Face, Team, My edits, the custom-team kit stay pop-up windows).
- **2026-10-21 (owner, after a "damaged" roster in the patched game):** tab order Setup, Game patch, Update; the window
  always opens on Setup (`main.js` `startTab`). `UpdateController.misfit` marks a roster the game as RPCS3 has it cannot
  load (normal roster + patched version, 32-team roster + unpatched; `texts.MISFIT_*`) in Setup, the Update tab's bar and
  the Game patch tab; after Patch / Unpatch the next scan asks to update the picked roster (`_ask_fit`, "Update it now"
  = in place, its own name, whatever the save mode: `_fit` in `start`). News bodies: "Updates, patches, statistics! Join
  us on gg.puckpeak.com" (`loc._NEWS`, `PROMO_VERSION` '#3'). `tools/window_shot.py misfit`. Not seen in the game yet.
- **Calendar** (`app/calendar.py`, `web/js/calendar.js`): month page from the roster's own calendar (`schedule.read`,
  `dated`, `season_of`, `split_all_star`), the AHL on patch rosters (`schedule.read_ahl`), a day's games, the team's list.
- **Front office** (`frontoffice.py`, `app/office.py`, `web/js/office.js`): payroll, cap and space for five seasons (always
  real dollars), NHL / farm / prospects. **Contract edits** (seen in the game, lab round 41): the contract window, edits.json `players[key]['contract']`, `edits.apply_contracts` after `b.real_contracts()`,
  `verify.contract_edit_problems` first.
- **My season** (`seasonsave.py`, `app/season.py`, docs/notes/season-saves.md): the player's newest Season / Be a GM save,
  read only (never while it was written in the last 5 s): results, today, next game, playoffs in the Calendar; record,
  place and standings in Front office. Checked on 13 lab saves (records = the game's own for every team); the Standings
  screen's tie order and the preseason are not checked (ROADMAP "Checks of 0.50.0").
- **Seattle / Vegas contracts fixed**: the data pack had their deals swapped (`private/contracts_db.py` `SOURCE_SLOT`);
  `contracts.misplaced` + `tools/build_datapack.py` refuse such a pack now. The local pack is rebuilt and was published
  on 2026-10-23 (owner's go-ahead).
- **Round 41 (2026-10-21, the owner's report; plan docs/plans/ok-let-me-know-soft-wilkes.md, docs/notes/lab-round-41.md):**
  Team Rosters' CONT / SAL "N/A" (Eichel, Hanifin at Vegas) = contract status `cPbu.QwoG` 0: `contracts.status_fit` /
  `status_problems`. Be a GM's UFA / RFA come from `cPbu.zKKG` = birth year + 27 (the disc's rule): `contracts.ufa_fit` /
  `ufa_problems`. Both run in `pipeline.build` after `b.finish()` (all records after a step that moves players, else only
  contract-edited rows / none) and in `patch_roster`. Roster Management's AHL lacked Coachella Valley / Henderson on a
  roster from the game's own (the list walk `0x128348` stopped at 223): patch **0.22**, stage Y's cave `0x1283bc`. Played
  in the lab: all three fixed; real and edited contracts in Team Rosters, a new Be a GM and Be a Pro Central, so
  `'contracts'` and `'contract edits'` left EXPERIMENTAL. Checked again through the built exe (Patch 0.22 + update,
  Unpatch + update, both money scales). Open: the game booted another roster than the one updated in place (ROADMAP
  "Checks of round 41").
- **Round 42 (2026-10-22, the owner's asks: contracts for every club, Coachella's real roster, an editor without locks;
  plan docs/plans/ok-let-me-know-soft-wilkes.md, docs/notes/lab-round-42.md):** the AHL's 32 rosters come from the source
  (data pack part `leagues.ahl`, `private/club_rosters_db.py`; rights from the list's `org`, `clubs._rights`). Real deals
  wherever a player plays; **starter deals** (`contracts.STARTER` / `starter_terms`, `Builder.starter_contracts`) for
  every club player without a deal or NHL rights; status / UFA / verify for every club (`contracts.contract_clubs`);
  contract edits for anyone on a club (free bounds outside NHL organisations, `contracts.organisation`); Front office,
  the contract window and the card for every club, free agents can be signed. **Patch 0.23**: the roster's player rights
  `cPbu.WBbd` have six bits on patch rosters (`gamepatch.rights_wide` / `rights_narrow`, `tdb.Table.widen` / `narrow`,
  the db description's proteam at six: `META_TEAMS`), so Henderson is Vegas's farm (`vegas_depth` is gone);
  `UpdateController.misfit` marks a patch roster whose bits differ from the installed patch (`MISFIT_VERSION`,
  `patchinstall.installed_rights`). `pair_farms` runs before the NHL step; `clubs._fill_lineup` takes players near the
  club's level and never one under an NHL contract no list names. Played in the lab: Henderson In the System, call-ups,
  a Vegas Be a GM through the season, the 2027 draft and free agency.
- **Round 43 (2026-10-22, through the built exe; docs/notes/lab-round-43.md):** Patch 0.23 + update in place, Team
  Rosters with every club's deals and both edits, Play Now at Coachella; Unpatch + update: the unpatched game loads it at
  the $71.4M scale. Fixed: `savedata.update_in_place` sets PARAM.SFO's `SAVEDATA_DIRECTORY` to the folder's own name (a
  hand-copied folder loaded its original); the load path told to players is "Customize > Save/Load/Delete > Load >
  Rosters" (`texts.HOW_TO_LOAD*`, cli, README, QUICKSTART). Note: Unpatch puts back what RPCS3 had before the first
  Patch, also an older patch of ours put in by hand.
- **Draft & Pro, rounds 44-45 (2026-10-22; plan docs/plans/another-context-window-is-sorted-liskov.md, notes
  docs/notes/lab-round-44.md, lab-round-45.md):** the 10th tab (rows "Roster editor" and "Draft classes" above). Round
  45: a career copies a created look only for a player listed through his Create Player record's own link (`caBZ` BERR 1,
  qEfv = qFky = game id); the builder lists new players that way, verify refuses another link (`faces.link_problems`); a
  new Be a GM career then showed the created face (my pro in Be a Pro: not played). Edits reach Season / Be a GM / Be a
  Pro when a career is started (the game copies the roster then); running careers are never changed (P6 not built).
- **Main menu news (2026-10-22, owner: "all these texts should say the same gg.puckpeak.com"):** `loc.PROMO` '#4' (every
  news title and body, also the fighting tip and NHL 94: "Puck Peak" / the gg.puckpeak.com line); patch **0.24** = 0.23's
  words + `gamepatch.NEWS_ENTRY` (0x7e8d58, ticked with the patch): signed in, the game showed the server's news (the
  2014 texts) over our text file; the entry keeps the offline ones. Lab: boots, the panel shows the line (signed out).
  Online is the owner's check (docs/notes/promo-texts.md section 5).
- **Round 46 (2026-10-22/23, the owner's report; plan top section of docs/plans/another-context-window-is-sorted-liskov.md,
  notes docs/notes/lab-round-46.md, league-calendars.md):** (1) the exe showed a test's fake RPCS3: a test's late rescan
  wrote the real settings.json; `tests/conftest.py` `pytest_configure` points LOCALAPPDATA / XDG_* (HOME off Windows) at
  one temp folder for the whole run (`test_app` checks it), and the exe neither uses nor remembers an RPCS3 in the temp
  folder (`app/update.temporary`, `start_up`, `_scanned`). (2) **Calendars of
  every league** (`'league calendars'`, out of EXPERIMENTAL since the exe round 46c): Season mode plays all ten leagues
  with a table from the roster (lab: DEL, SHL, OHL patched, AHL unpatched, game for game); data pack part `schedules` (9 leagues, on the server since 2026-10-23);
  `schedule.LEAGUES` / `apply_league` / `check_league` (verify), written in the calendar step for every league whose clubs
  step runs (`pipeline.CALENDAR_STEP`); the Calendar tab shows every league (Norway from the pack, "game's own" note).
  (3) Coachella's plain jersey: `layout.OWN_DESIGN` (`jerseystyle` 1) in `clubs.own_kit`; centre ice showed the crest in
  the lab. (4) The owner's pro was in Be a Pro under Overall 80-89 (the filter opens on 70-79): `prospects.PRO_WHERE`.
  Lab trap: "Unpatch" in the lab puts back the lab's old hand-installed test patch (0.18 stages ticked), under which a
  normal roster is "damaged"; switch the lab's entries off for an unpatched check (lab-round-46.md, 46c).
- **Round 47 (2026-10-23, the owner's report; plan top section of docs/plans/another-context-window-is-sorted-liskov.md,
  notes docs/notes/be-a-pro-save.md, press-start.md):** the owner's Florida pro was never in the game (made after the last
  Save; the game loaded the older file). (A) **My pro**: row states read from the roster as saved (`in` / `unsaved` /
  `waiting`, `ProspectsController._saved` on `editor.raw`); new players of edits.json the saved roster lacks join the
  visit's `session` when a roster opens (`EditorController._not_saved`), so Save writes them after a restart; the pro's
  team is an NHL team or a CHL club (`pro_team`, Apply refuses others); a gold "Not in the game yet" line; closing with
  edits not saved asks Save now / Close anyway / Cancel. (B) **Running Be a Pro careers** (P6 v1, rule 1's career text):
  `careersave.py`, `verify.career_problems`, `savedata.update_career`, Draft & Pro's last view "Be a Pro careers"
  (`app/career.py`): the pro's name (also the Load Pro label the game made from it), his ratings (`c_`, 40-99; not for a
  goalie career yet) and the XP to spend in Player Growth (earned - spent); the Overall is not shown (the game works it
  out when the career loads). (C) **No Press Start**: `art/pressstart.py`, put in by `patchinstall.set_press` with "Skip
  the intro" (`NO_PRESS = True` since lab 47d passed on the EU disc; the NA file is the same bytes), removed on Unpatch;
  `'no press start'` experimental. **Lab round 47** (docs/notes/lab-round-47.md): 47d boots to the main menu with no
  press (profile and roster autoload, Be a Pro, Season, Save and Exit; Be a GM and online not tried); 47a: the game loads
  at boot the **oldest roster written since the last boot** (round 41's open point; what the program should do is the
  owner's call, ROADMAP), a pro with 98 everywhere is "99 Overall" under 90-99; 47b: six one-change copies of a career
  load, play, save and reload (be-a-pro-save.md). A misfit roster (older patch rights) crashed Pick an NHL Pro (already
  marked by `misfit`). 47c (the built exes): the window edited a lab career, the game loaded it (Player Growth showed
  the XP and rating, Overall worked out by the game), boot with no key pressed, Unpatch removed the press files.
- Tests 562 passed, 3 skipped (with the disc; 2026-10-23 afternoon; since then only
  `test_the_pages_server_takes_many_connections_at_once`, run alone; a last full run was stopped at the owner's word).
  Built again for release 2026-10-23 17:25 (window 26.4 MB, cli 18.5 MB, no code change since 16:00), `clean_check` 0
  hits; smoke test: the window opens with the ten tabs (not blank), `cli list` / `game-patch status` on the lab.
  **Released 2026-10-23** (the owner's go): commit and tag `v0.50.0`, GitHub release with `NHLLegacyRosterUpdater.exe`
  and `SHA256SUMS.txt` (no data pack asset: MAINTAINING.md step 8).
  **Blank window fixed** (found in lab 47c): pywebview's local server listened with Python's queue of 5 connections and
  Windows refused the page's other font / script requests, so the window could stay empty (4 of 4 starts with WebView2's
  debug port, from source too); `window/main.roomy_server` sets the queue to 64 before `webview.start` (0 of 8 blank). The Jerseys test
  (`test_the_jerseys_window_says_this_seasons_come_with_the_photos`, 120 s wait) timed out once while a build ran beside
  the suite; alone it passes.

**Version 0.35.0 (2026-10-20; now part of 0.50.0, never released on its own):** everything since 0.10.4 in one version
(0.20.0 to 0.32.0 below were test builds, never on GitHub); its CHANGELOG entry became the 0.50.0 entry. Its last part is the picture fix below. Players who still show a silhouette (no photo anywhere the
program looks): not built, "just a couple of people" (owner); findings in docs/notes/missing-photos.md.

**Picture fix (2026-10-20, in 0.35.0; plan docs/plans/giggly-squishing-candy.md, notes docs/notes/player-pictures.md):**
testers of 0.10.4: an own picture (Troy Terry) never showed; "almost all player images are wrong". Owner's picks: own
pictures always go in; clashes: move ours, give theirs back; a failed photo keeps the old picture.
- **Own pictures** (`'own pictures on save'` experimental): `Builder.own_photos` / `own_logos` (edits.py);
  `pipeline.Pictures(own_only=True)` plans and installs only those (no names, menus, jerseys, crests, masks, pool logos):
  on the Roster editor's Save (`app/editor.save`, RPCS3 closed; also photos / logos of earlier visits,
  `_picture_edits`; never at the same time as an update, `saving_pictures`) and on an update with Photos off.
- **Picture numbers** (`'picture numbers'` experimental): `install.scan_claims` -> `portraits.Claims` (every roster
  save of every RPCS3 user, every portrait file); `same_person` (no birth year); `Registry.id_for` never gives out a
  number someone else uses, new ones from `FRESH_IDS` (40,000); `forget_conflicts` + `install.give_back` after the
  save. Simulated on the owner's rosters (read only): 0 strangers after updating both, 127 before.
- **Failed photos keep the old picture**: `install.prefetch` before `plan` (`Builder.bad_pictures`, `art_line` "could
  not be made"); `images.stand_in` (NHL.com's grey silhouette; downloaded links only); `tools/build_photopack.py` leaves
  stand-ins out. Pick time: `NO_FACE` for a cut-out without a head.
- Tests: tests/test_pictures.py, `test_app` editor Save. Checks: ROADMAP "Checks of the picture fix".
- Lab round 40 (agent, docs/notes/lab-round-40.md): the Roster editor's Save with Photos off gave Troy Terry an own
  picture, shown on his card in the game. Built (window 26.1 MB, cli 18.4 MB) and smoke-tested.

**Version 0.32.0 (2026-10-20, not committed; plan docs/plans/ok-new-plan-check-sprightly-dragonfly.md top part, notes
docs/notes/pack-hosting.md, private/NOTES.md):** the owner wants none of the game's content inside the exe and no word
pointing to where it came from.
- **Packs leave the exe** (rule 9): `photos.zip` (102.8 MB) and `looks.zip` (54.6 MB) are downloaded from
  `https://puckpeak.com/legacy-roster/` (`manifest.json` format 1: per pack `file`, `size`, `sha256`, `built`; files named
  `<name>-<sha12>.zip`, so a pack open on Windows is never replaced; the old one is pruned at the next start). The
  window starts the download at start and when the Photos switch goes on (`UpdateController.download_pictures`); an
  update pressed meanwhile waits ("Waiting for the download..."); a failed download leaves the update to run with
  pictures one by one, and the result says "Some pictures could not be downloaded". The classic window and `cli update
  --photos` call `packs.sync()` first. Window exe 26.1 MB (was 172.8), cli 18.4 MB.
- **The server stands alone**: `/opt/nhl-legacy/` with its own nginx container (read-only, 0.5 CPU, 64 MB, 4 MB/s per
  download, 50 at once, GET / HEAD only, 404 outside the manifest / data pack / packs), one Caddy route in puckpeak.com's
  block. puckpeak.com and cheerin.quest checked after. `tools/publish_packs.py` sends packs, the data pack, then the
  manifest last.
- **Data pack format 2**: parts `ratings_list` / `ratings_full` (renamed), neutral `sources` labels, served from the same
  folder (`datasource.PACK_URL`); 0.10.x programs refuse format 2 and keep their own.
- **Neutral names everywhere** (`tools/clean_check.py`, `tests/test_clean.py`): "this season's" jerseys, "current
  ratings", `looks.PACK = 'pack'`, experimental `'current ratings'`; the source tools and their tests moved to
  `private/` (git-ignored). README: "Unofficial fan project, not affiliated with or endorsed by the game's makers or the
  league."
- **Window**: "Photos, logos and team names" is the first row of step 4, highlighted in gold (`featured`, gold toggle,
  a thin progress bar), with texts that never say where from (`texts.PHOTOS_*`, `photos_will`); Patch is a gold button,
  Unpatch a gold outline; "Restore default" is a small red glowing button (the page's "Restore the game's own pictures"
  is gone: the Photos row's Restore does it); no "RPCS3 is running" pill in step 1 and no close-RPCS3 line in step 2
  (Patch / Unpatch / the switches stay on and check RPCS3 when pressed); the "?" next to Patch (`texts.PATCH_INFO`,
  `ui.Info`) says everything the patch does; the Jerseys
  window says "This season's jerseys come with Photos, logos and team names" without the look pack.
  `tools/window_shot.py downloading`.
- Built and smoke-tested; lab round 39 (agent, docs/notes/lab-round-39.md): the packs downloaded by the exes, a Utah
  home game with this season's jersey and centre ice, the lab put back. Checks: ROADMAP "Checks of 0.32.0".

**Version 0.31.0 (2026-10-20, not committed; plan docs/plans/ok-new-plan-check-sprightly-dragonfly.md top part, notes
docs/notes/lab-round-37.md):** the owner asked why Coachella Valley could not change jerseys and for "editable
everything". Owner's picks: shared ice edited as a group with a note; custom colours "quick + detailed".
- **Custom teams 222-251** (`'custom team kits'` experimental): the game draws them like Create a Team teams. Lab round
  37 named the `ttOk` design fields (`jerseybackhome` / `away` 0-8, `pantsstyle` / `sockstyle` / `font` 0-5;
  `jerseystyle` left alone) and the 11 `NDEo` pieces (1-4 goalie glove / blocker / pads / stick, 5 gloves, 6 socks,
  7 pants, 8 helmet, 9 jersey, 10 numbers, 11 crest). `custom_kit.write` sets designs, `primarycolor` /
  `secondarycolor`, three team colours painted on every piece (`fill`), then the pieces set one by one; the crest is a
  create-a-team logo (`artid` 20001 + n), the team's own (234 / 235) or a picture on a free logo (`free_logo`, never 54,
  never another team's `OWN_ART`). `verify` runs `custom_kit.problems` (ranges, `NDEo` rows unchanged, a crest picture's
  art id on one team only). `edits._team_kit` runs in `apply_teams`, before `club_gear` / `goalie_gear`.
- **Round 34's mistake fixed**: piece 1 is the catching glove, not the jersey; `layout.OWN_KIT` now paints Coachella's
  jersey (piece 9) navy.
- **Shared ice** (`'shared ice'` experimental): `looks.ice_group` (national 501, DEL 197, EASHL 255; never a group with
  an NHL slot), options the game's own / my picture, the window moves the picture to the saving team.
- **Winter Classic 216-219 / EASHL 2**: `looks.window_team` opens the team whose jerseys they wear, with a note.
- Lab round 38 played it through the program (patched game, docs/notes/lab-round-38.md): Coachella's new kit and hand-
  painted away helmet, a picture crest and a game logo on custom teams (jerseys, menus, centre ice), the national and DEL
  group ice. Not played: unpatched, goalie gear colours. Checks: ROADMAP "Checks of 0.31.0".

**0.30.0 addendum (2026-10-19 evening, not committed; plan docs/plans/ok-new-plan-check-sprightly-dragonfly.md, notes
docs/notes/league-menus.md, lab rounds 35 and 36):** the owner asked for Coachella Valley / Henderson under the AHL, in
the game and in the exe, and overruled rule 2 for them (rule 2 above). Round 36 played it through the program: patched
AHL of 32 named with crests, a Vegas pro, Unpatch + update back to Custom (docs/notes/lab-round-36.md).
- **Turn-back fix**: `PATCHED_TEAM_FIELDS` joins its parts per slot (`_joined`); before, NO_FARM's entry replaced
  Seattle's / Vegas's names and divisions, so a turned-back roster kept them in slots 30 / 31 (since 2026-10-18).
- **Patch 0.21** (`TEAMS_VERSION`): stage Y = 11 words of the front end's created-team gate (`0x128408`) + 5 name caves
  (`NAME_SITES`): a created team whose league is not Custom is listed in its league and named by its art code (CVF /
  HSK). Stage W gains `0x458ec8` (a Seattle / Vegas pro on the NHL roster crashed while loading Be a Pro).
  `tools/audit_patch.py`: 352 words, 0 problems.
- **Roster**: `gamepatch.league_fit` / `unleague` / `check_league_fit`, `LEAGUE_FIELDS` in `PATCHED_TEAM_FIELDS`;
  `verify` allows 234 / 235 between Custom and the AHL's Pacific only (`farm_patch` picks which). `'farm clubs in the AHL'`
  experimental.
- **Names**: `loc.key_hash` uses the game's rule (bytes & 0xdf; the upper-case CRC hid every key with a digit, which
  left 10 clubs blank in Select Teams); `set_select_lines` adds the lines a club lacks; `portraits.names` writes CVF /
  HSK's club texts next to the city key; `NAMES_VERSION` '#6'. Names still need "Photos, logos and team names".
- **Roster editor**: 234 / 235 under AHL only when the roster is for the patched game (`Snapshot(farm_ahl=)`).
- Checks: ROADMAP "Checks of 0.30.0, addendum". The version number stays 0.30.0 until the owner picks one.

**Version 0.30.0 (2026-10-19, not committed; plan docs/plans/the-0-21-0-exe-is-parallel-haven.md):** the owner asked why
only NHL teams could change jerseys, then for gear in team colours, crests for Coachella / Henderson and HUT hidden.
- **Jerseys for every league, per team** (`'jerseys every league'` experimental): the NHL-only lock is gone
  (`app/editor.py` `team_tools.uniforms` / `uniforms_why` from `looks.editable`). `looks.looks_from` is one loop and keys
  every look by art id; edits of clubs are honoured (before, slots 32+ got this season's whatever the player chose).
  "My picture" works in the classic cut (`Maker.cut_files`), "From the colours" only on the shared layout. A club's ice
  edit is refused where the game shows another file (`own_ice`; List of changes "Centre ice not installed").
- **This season's: home and away only** (owner): `looks.pack_versions` has no `third`; NHL thirds are the game's own again.
- **Templates**: "This season's template..." where the pack's colour map fits "My picture" (style 0, or a version on the shared
  layout), next to the game's.
- **Coachella Valley / Henderson crests** (`'own art ids'` experimental; lab round 34, docs/notes/lab-round-34.md): art
  900 / 901 gave a blue square (the game draws custom slots 222-251 from the create-a-team files whatever the art id),
  so `layout.OWN_ART` = 20073 / 20081 on every roster (also the game's own), `clubs.own_kit` writes `OWN_COLOURS` (ttOk)
  and `OWN_KIT` (table `NDEo`, eq 11 = the crest's colours), and `art/crests.py` installs `rendering/czlogo/logoct_72_*` /
  `logoct_80_*` with the photos (weights in `0_tm`, bump / shine maps from the closest of the game's own logos). Played: crests on the
  ice, the jerseys and Select Jerseys, Coachella navy.
- **HUT hidden** (owner, 0.30.0): `menus.DEAD` has `TXT_HUT` in the root menu and in Play (`MENUS_VERSION` '#3'); played.
- **Gear colours** (`'gear colours'` experimental): `Builder.club_gear` (vbHh helmets / gloves of clubs 32-213 in
  colours their club wears; NDEo is left alone), `goalie_gear(mend=)` (goalies in a colour off their club's hues get the
  nearest club colour), `equipment.fix_models` / `model_problems` (models the game draws plain blue, `DRAWABLE`); only
  with update steps, so the Roster editor's edits alone change nothing. tests/test_gear.py.
- **`matching.closest`** (verify's contract check only): a 'last+year' match (last name, birth year within one, first
  initial) gives up a record another person of the same list matches more closely (Aku / Aatu Räty: verify read
  Aatu's deal as Edmonton's and refused the update with NHL.com's rosters of 2026-10-19; 0.21.0 had it too). Doing
  this inside `match` broke the byte-identical second runs (7 tests): the builder's picks stay as they are.
- Version 0.30.0 (owner). Checks: ROADMAP "Checks of 0.30.0".

**Version 0.21.0 (2026-10-18, built and smoke-tested, not committed; plan docs/plans/the-game-patch-is-vectorized-scone.md,
top part):** the owner's review of the 0.20.0 exe. Lab round 33 played it (docs/notes/lab-round-33.md). Left out by the owner "until somebody complains": a jersey hem (Letang) and the
All-Star teams (ROADMAP.md). Checks: ROADMAP "Checks of 0.21.0".
- **Window:**
  - `window/main.fit` / `work_area` / `window_box` open it big and centred (90 % x 94 % of the free screen, at least
    1080 x 780, at most `LARGEST`).
  - Step 2 (patch) moved to the left column. The patched / unpatched result panel is gone; step 2's status line says it
    (`texts.patched_status`, `UNPATCHED`).
  - `.card.rosters` keeps a minimum height (a smaller one at 768 lines while a result shows); the percent shows once.
  - "No pop ups at start" is the label of `LOGIN_ENTRY`'s switch (the entry's name stays).
  - `tools/window_shot.py` draws the window at the size `fit` gives on the screen.
- **Equipment tables count teams as slot + 1** (`vbHh`, `nAUy`, `NDEo`; `sozv` by slot). `Builder.nhl_gear` had painted
  Philadelphia, Washington and Seattle; it now paints 22 / 30 / 31 in `NHL_GEAR` (Utah black, Seattle navy, Vegas gold /
  steel; Vegas's helmet comes out steel grey, as the real one: round 33, docs/notes/equipment.md) and repairs `GEAR_SLIPS` from the game's own roster (`own=`) or the team's colours (`_gear_back`).
  `'nhl gear'` is experimental.
- **Sticks in team colours** (`sticks.py`, `tools/stick_colours.py`): NHL skaters with a stick in a colour their team
  does not wear get a model of the same brand in a team colour, else a plain one. The swap runs in pipeline's NHL step,
  before the edits; `verify` runs `sticks.problems`. `'team sticks'` is experimental.
- **Puck Peak texts** (`loc.PROMO`, docs/notes/promo-texts.md): the game's old offline news panel and the tuner-set notices,
  with the names. The community server's news and the HUT banner stay (owner: keep the community server's messages and promotions).
  `'puck peak texts'` is experimental.
- **Dead online entries hidden** (`art/menus.py`, docs/notes/menus.md): View Player Hub, Leaderboards and Lobby
  (COMMUNITY) are marked `isHidden` in a loose `fe/ion/game/menus/mainmenuitems.big` made from the player's `boot.big`
  (`install.install_menus`, with the photos). HUT stays (the community server serves it, owner 2026-10-18). Lab probe 2026-10-18: the
  game reads the loose file before boot.big, hidden entries leave no gap, the cursor skips them, no crash.
  `'hidden menus'` is experimental.
- **Face of a player shows head pictures** (`app/editor.face_pics_view`, cache.big `createplayer/head/head<id>.big`).

**Version 0.20.0 (2026-10-18, not committed; plan docs/plans/the-game-patch-is-vectorized-scone.md):** the owner's asks
after the step-2 exe. The version jumps to 0.20.0 (the owner's pick: `app/selfupdate.parse_version` compares numbers, so
"0.2.0" would be older than 0.10.4).
- **Line-ups always dress** (the owner's Ottawa failure after Unpatch: NHL.com made MacDermid D a LW and the kept lines
  still had him on defence). `Builder.position_teams`, `nhl_lines` re-deals a team that is changed, had a position
  change or fails `lines.lineup_flaws`; `Builder.repair_lineups` (start of `contracts()`) calls up from the farm or signs
  a free agent when a team cannot dress 2 G / 6 D / its forwards (`call_ups`, `bring_in`; List of changes "called up to
  fill the line-up"); `clubs._feed_position` marks the club changed. tests/test_lineups.py.
- **Select Jerseys from the look pack's own menu pictures** (`teamjerseysxl/jersey_<cut>_<art>_0_<variant>`, format
  0x3c = BC3): the look pack holds `m/<slot>_<role>.webp` (55 MB now), `looks.menu_picture` fits it onto the game's
  figure, `PackKit.menu`, `pack_preview`; the Roster editor's thumbnails use it too (`app/uniforms._thumb`). Socks /
  pants that differ from this season's are listed in the owner's report (not changed in this round).
- **Sharp centre ice and jerseys** (the owner's blocky Utah ring): Pillow's DXT5 encoder never reached a block's end
  alpha values (stair steps, error up to 51) and mixed colour ends (purple blotches). `art/dds.py` re-encodes the poor
  blocks (`colour_block`, `alpha_block`, `encode_level`), mips are alpha-weighted with a 3-px colour bleed (`mipmaps`,
  `bleed`; `Rpsgl.replace(coverage=)`). Utah alpha p99 47 -> 11, colour p99 40 -> 16; about +8 % install time. Lab round
  32 still showed a hatch at the ring's soft edges (partial alpha on the ice), so the centre ice is now **flattened**
  onto the ice colour, every mip opaque or clear (`dds.flatten`, `FLAT_CUT` 64, `mipmaps(flat=)`, `looks.centre_file`
  `flat=ICE`); not seen in the game yet. `LOOKS_DRAWING` '#6'. tests/test_textures.py, docs/notes/centre-ice-quality.md.
- **Utah / Seattle / Vegas arena names on every roster**: the community roster still had Arizona Arena (Glendale) in 22
  and Nashville's arena in 30 / 31 (lab round 32); `Builder.nhl_identity(colours=)` now runs with the NHL step on every
  roster (colours only on the game's own roster; the community's own colours stay). Not seen in the game yet.
  Not done (options): portraits still use Pillow's DXT5 (`install._dds_bytes`), opaque DXT1 jerseys keep Pillow's blocks
  (`rpsgl.OPAQUE_SLACK`), no cache of encoded rasters.
- **Current ratings** for every player the data pack's full list has (`'current ratings'` experimental): data pack part
  `ratings_full` (6,968 players, made in `private/`). `ratings.full_index` / `match_full` (full name + birth, last name +
  birth with a fitting first name, a unique name within a year; goalies only with goalies), `write_full` (`c_*` - 36
  clamped, the biases / fighting / consistency as they are; `schema.FULL_RATED`, `FULL_ASIS`), `Builder.apply_full`
  first, then the ratings list (`ratings_list`), then `estimate.py` (also in `clubs.update_league`, `create_national`,
  `set_position`); type only when it fits the record's class; bio only where NHL.com has none. `verify.rating_problems`;
  verify's mirror check now uses the roster's own layout (`verify.layout_mirrors`). Result "Player ratings: 4612
  current, 573 estimated" (community base). `Builder.feed_letters`: `contract_strays` keeps only the league's own C / A
  letters (a second run moved Coachella's A). Not copied: potential, traits, growth. Options: refit
  `estimate.LEAGUE_GAP` on the full list (estimated players sit 1-2 above rated team-mates in Extraliga, DEL, NL).
  tests/test_full_ratings.py, docs/notes/full-ratings.md.
- **"No online login at start"**: the owner played online through the community server with it on; the "leave it off to play online"
  warnings are gone, the switch stays.
- **Promo texts** (main menu tiles, news): docs/notes/promo-texts.md, `tools/find_texts.py`; nothing changed yet, the
  owner writes the Puck Peak words later.

**Game patch as step 2 (2026-10-18, not committed; plan docs/plans/sunny-nibbling-goblet.md, GAME_PATCH.md section 7):**
the owner's wish after the test exe refused the game's own roster ("slot 234 holds only 0 F"). The patch is its own step
2 (Patch / Unpatch, the two switches, applied at once while patched); every update follows RPCS3 (patched: a patch roster
from any roster; not patched: a normal one, a patch roster is turned back with `gamepatch.unpatch_roster`); the game's own
roster gets Coachella Valley / Henderson from the AHL data and Vegas its depth. Tests green (322); lab played
2026-10-18 (GAME_PATCH.md section 7: own roster + patch, Be a GM Seattle / Vegas to 15 Nov; turned back and played
unpatched; community regression).

**Data of 2026-27 (2026-10-16, not committed; plan docs/plans/is-it-possible-to-jaunty-dongarra.md, private/NOTES.md):**
player type and face in the Roster editor (types named in the lab, `'type and face edits'` experimental); **real 2026-27
contracts** (data pack part `contracts`, `'contracts'` experimental; real dollars on a patch roster, x 71.4 / 104.0
otherwise; the result has a "Contracts" line; the 82 players under contract whom NHL.com's roster copy leaves out stay
with their team, notes contracts.md). **Stage X v2** (patch 0.20, `CAP_TABLE`): the real cap by season (2026-27
$104.0M, 2027-28 $113.5M, 2028-29 $127.5M, then held; floor, lowest and rookie maximum too; notes salary-cap.md) and the
year entry 0.8 (Contract Status columns "26-27"); lab round 30 played both through season 2's start. **This season's
jerseys** (the look pack, round 2, 2026-10-17; 214 teams, made in `private/`): `art/lookpack.py`, `looks.pack_team` /
`kit_palette` (style 1 and style 0), installed with the photos; **lab round 31 done** (a home game in every league but
the QMJHL; install 18 min, 834 MB per game version). The centre-ice file a home game shows depends on the league (NHL /
DEL: the arena's, national teams: 501, others: the team's own; `looks.shown_centre`, `own_ice`), so DEL clubs and
national teams keep the game's own ice. Loading hangs in SHL home games are RPCS3's / the game's own (also with nothing
of ours installed). MAINTAINING.md "The look pack".

**Game patch (2026-10-15, not committed, nothing published; docs/GAME_PATCH.md, plans docs/plans/fluffy-dazzling-scone.md,
this-was-written-from-stateful-bee.md):** the year 2026 and 32 teams in Season / Be a GM / Be a Pro, patch 0.19 (stages A-X), year 0.7, plus two
optional intro entries.
**84 games (0.14, rounds 18-20):** the real 2026-27 calendar (1,344 games + the All-Star row); the game sets a roster
calendar's room itself (1,291 rows, data table `0x1acc878`), stage S raises it to 1,345, so the patch roster's save is 864
bytes longer (`gamepatch.SECTION_SIZE`, `section_fit`; with S on a normal roster "appears to be damaged"). A new Be a GM
holds 32 x 84 and played a whole season with 84 GP for all 32, the playoffs, the June 2027 draft and season 2's calendar of
32 x 84 (round 20). **Stage T (0.15, round 21):** season 2's preseason crashed (the team rankings of 17 stats have room for
30 teams; `RANK_ROOM`); each ranking now keeps 30. **Rounds 21-22:** season 2 played to the end, 84 GP for all 32, the
playoffs; one hang in a computer team's game (25 Jan 2028, the engine's lineup for Vegas held strangers and empty places)
did not come back on a replay (GAME_PATCH.md section 6). **Stage U (0.16, round 22):** the second draft (June 2028) crashed:
the game keyed each year's picks for 30 teams, so a new year overwrote 14 first-round picks of the next draft; the keys are
now (year mod 6) x 224 + pick (`PICKS_PER_YEAR`); only a Season / Be a GM started with 0.16 has them. What 2026-27 still lacks: docs/notes/2026-27-gaps.md. Lab rounds 12-17 were played by the agent with a scratch
driver (docs/notes/autoplay.md; the owner asked not to be asked to test): 32 NHL + 32 AHL with their real parents, the All-Star
game (EASHL 1 / 2 with art 30 / 31, `ALL_STAR_RINK`), Seattle's call-ups (stage O), the trade deadline, the end of the season,
a 16-team bracket. A reloaded Vegas Season lost its team (the human-team mask `leaguestates.value` had 31 bits): fixed by
`META_MASKS` (32 bits in the db files), confirmed in the lab. Be a GM with Vegas (rounds 14-17): a full season, the playoffs,
the draft of 32 (stage K), the off-season; fixed: Seattle / Vegas roster upkeep loops (P), a season-2 crash in the game-day step
(Q), season 2's calendar left Anaheim / Calgary without games (R + the roster's `byED` = the 2026-27 calendar,
`gamepatch.future_fit`; confirmed: 32 x 80 NHL, 32 x 72 AHL). A human team under the roster minimum hangs its first game (the
game's own rule: call up / sign first). Run 17: season 2 to late October, a Vegas send-down / call-up, Save and Exit: no crash.
**Rounds 23-26 (2026-10-15):** stage U held through the June 2027 draft; at season 2's new year (13 Sep 2027) the computer
teams took stars off their NHL rows. Patch off (round 24) they did not: the computer GMs count ages from the league's own year
(2015), so **year 0.6** stores patch-roster birth years as real - 1911 (`year_shift`) and adds 11 back in the two date ages
(`0x1631e4`, `0x372008`). With right ages (round 25) four computer teams still sent 10-17 NHL players each to the farm at the new
year; round 26 (the year entry alone) did not. **Round 27 (full patch, Be a GM with Anaheim, 2026-10-15), all fixed and
played:** (1) computer-run Seattle / Vegas got no call-ups (the roster planner counted keys 30 / 31 as non-NHL), Vegas ran
short and a sim hung: **stage V** (0.17); (2) the stars on the farm came from the calendar's timing: with the real 29 Sep
opener season 2's preseason began before the game's fixed new year (11 Sep), its first day was not counted and the final
roster cut (`0x1ca618` mode 7) never ran; `future_fit` now stores the next seasons' calendar **a week later**
(`FUTURE_DAYS`), season 2 opens on 6 Oct and all 31 computer teams get the cut (run E7: 0 teams lost a third of their NHL
pay, 6 before; docs/notes/gm-brain.md, GAME_PATCH.md row 27). (3) **Intro skip** (owner's wish): two optional entries in
`patch_text`, `INTRO_ENTRY` (the game's own quick boot + no autosave notice: Press Start at once, one press to the main
menu) and `LOGIN_ENTRY` (no online login at boot; online modes still sign in when opened: the owner played through the community server with it on, 2026-10-18), played in the lab (docs/notes/intro-skip.md).
Also fixed: `donors.real_birth_year` made 75 community-updated undrafted records
(Krug, Goodrow) ten years older (now it needs `TNEo` at 12 or younger); this also touched the normal update.
**Round 28 (2026-10-16, docs/notes/be-a-pro.md):** season 2 to the June 2028 draft played (84 GP, all 7 rounds, no hang).
Be a Pro: Edmonton played; a Seattle prospect crashed while loading: **year 0.7** gives a new career's job list room for 16
(`0x33a4d0`; the year entry adds a 9th job), **stage W** (0.18) lets the "which team is this player on" query see keys 60-63
(Coachella Valley / Henderson) plus six Be a Pro compares; the career then loads, saves and plays. `gamepatch.NAMES_2026`
names slots 22 / 30 / 31 in the patch roster's team table (Be a Pro said "GREEN / RED organization"). Plain Season mode with
Vegas: 84 GP for all 32, the playoffs, the Cup (no crash). **Still to play:** the rare engine hang (rounds 21 / 23, not seen since). **The owner releases nothing until 32 NHL + 32 AHL + the All-Stars work, with 84
games.** **Phase D (2026-10-15, built, tests green, NOT played through the exe, not committed; plan
docs/plans/zazzy-leaping-stearns.md, GAME_PATCH.md section 7):** the window's row "32 teams and the year 2026 (game patch)"
(question first, "Skip the intro" / "No online login at start", Unpatch), `update --game-patch`, `game-patch status|remove`;
EU and NA. Next: the lab check through the exe (section 7, "To play"), then build and the owner's go-ahead. Later, the
owner's picks: the 2026-27 salary cap, 3-on-3 overtime.

Version 0.10.3 (2026-10-13, from the owner's tests of 0.10.2; plan: docs/plans/we-are-fixing-bugs-tidy-treehouse.md): **old window stuck after
"Update now"** fixed (`UpdateController.quitting`: `closing()` lets the window go once the new exe runs; `WebHost.quit` ends the process after
3 s; the new exe ends a stuck `<exe>.old` copy at start, `savedata.end_process_of`). **Equipment uses the game's menu words** (`equipment.OPTIONS`:
jersey tuck None/Left/Right/Full, sock tuck None/Front/Back/Full, tape 10 colours) and has visor tint, shoulder pads, pant length
(`CHOICES`, `NEW_PLAYER` defaults for created players); skaters have no neck guard field. Equipment / Jerseys-and-ice windows cover the logo
too (`.modal-back.full` fixed). `cli equipment-test` (`equipmenttest.py`) = the owner's in-game check of the numbers: NOT played yet.
Open: why Front / Back showed nothing in the game (probably the owner looked at Edit Pro, see docs/notes/equipment.md).

Version 0.10.2 (2026-10-12, from testers of 0.10.1; plan: docs/plans/i-got-some-bugs-polished-flamingo.md): **"Green / Red has 0 captain(s)"**
fixed: `edits._move` refuses a move that leaves a team that could dress 20 without 2 goalies / 18 skaters (`_too_few_without`; the editor says so
at Apply: `EditorController.too_few_without`), `_relines` keeps the letters when a team cannot dress, `verify` names slots 30 / 31 Seattle /
Vegas. **Equipment lists only models with a 3D picture on the disc** (`equipment.available`, `app/equipment._usable`: cacherender.big
file names; ids the roster already holds stay; NHL 10-14 models drew blue). **Equipment and Jerseys-and-ice windows fill the window**
(`Modal full`). **`stock.disc_icon`** takes any `ICON0.PNG` of the game folder, else the program's own picture. **Editor shows the player
type** (`ratings.STYLES`; 5 GRN, 6 PLY, 7 SNP, 8 PWF, 9 TWF, defence 1-4 unnamed); **the game's own OVR is NOT reproduced** (formula is in the
game program, `FUWe` is not it): research and next steps in docs/notes/overall.md. Not played in the game yet: helmet ids read from the
file names (`rendering/helmet/...`), goalie pads 85-88 have no file on the EU disc but are worn by 44 goalies (kept: worn ids stay).

Version 0.10.1 (2026-10-11, hotfix): European clubs' short codes are three plain letters (Frölunda FRO, Färjestad FAR, Davos DAV ...): `abbr` in `tools/club_slots.json` for SHL, Liiga, Extraliga, DEL, National League, Norway (AHL / CHL unchanged), data pack rebuilt (only `abbr` fields differ), `build_datapack.short_code` for left-out clubs. Reaches a roster on the next update with "Photos, logos and team names" on (the names hash includes the code). Not checked in the game yet.

Version 0.10.0 addendum (2026-10-11 evening, owner's testers): **Start RPCS3** really fixed: `savedata.launch()` also clears the
exe launcher's `SetDllDirectory` (the child inherited it; 0.10.0's first fix only cleaned PATH): NOT tried by the owner yet; if
the error stays, remove the buttons. **Equipment editor** (skaters): `equipment.py` (table `ajmx`, the choices), `app/equipment.py`
+ `web/js/editor.js` `EquipmentWindow` (the game's menu pictures from the disc, `cache.big` `createplayer/...`), edits.json
`equipment` per player and per team (`edits._set_equipment`, `_team_equipment`; a player's own choice wins over his team's);
research in docs/notes/equipment.md. Waiting for the owner: do the tuck / tape numbers match the labels (`equipment.OPTIONS`),
does the game show the stick / helmet / gloves; own equipment pictures (`rendering/glove/feglove_*`) not built (owner dropped them).
**Goalies** (same evening): `equipment.GOALIE_CHOICES` (table `lVMf`: mask, pads, blocker, trapper, stick, tape, tuck, neck) in the same window;
`mask_picture` edit: the goalie gets a mask number nobody wears (`edits._mask_picture`, reuses his own when he is its only wearer, so a
second run changes nothing) and `art/masks.py` writes the picture into `rendering/goaliehelmet/goaliehelmet_0_<n>_cm.rpsgl` (512x512 DXT1)
as a loose file with the photos (`pipeline.install_masks`). **NOT played**: does the game read the loose mask texture and does maskid
map to that file name (assumed; masktype 0 = 280 files, ids 234-245 have none). Goalie jersey = the team's jersey (Jerseys and ice).

Version 0.10.0 (2026-10-11, built, NOT committed, waiting for the owner's check): **the new window.** The CustomTkinter
window tore and redrew while it was moved or resized; it is replaced by a web page in a native window (pywebview: Edge
WebView2 on Windows, WebKit on Mac / Linux) in the look of the game's menus (the owner's Claude Design proposal + the game's
stadium blue, arcs and Help bar; Puck Peak logo kept). Plan: docs/plans/look-at-the-ux-ui-gleaming-noodle.md.
- Python holds all state (`app/` controllers, tested without a window: tests/test_app.py); the page only shows the JSON it
  is sent (`window/host.py`, at most 25 Hz) and calls `window/api.py`. Both tabs, Jerseys and ice, My edits, the Team
  window, questions (Delete, Restore default, close while busy) are in-page windows; file pickers are the system's own.
- The old window stays for 0.10.x: `--classic`, and used by itself when WebView2 / pywebview is missing or fails
  (logged in error.log). Delete it in 0.11.
- `tools/window_shot.py` now draws the page with headless Edge from the real controllers' state (`--live` for the
  real window). `editor/card.py`: ratings below 40 that the game's own roster has (Faceoffs 35) no longer block Apply.
- **Also in 0.10.0 (2026-10-11, from testers of 0.9.0; exe rebuilt with all of it, starts, tests 218 passed with the EU disc in
  `LEGACY_ROSTER_DISC`; NOT played in the game yet).** Plan: docs/plans/please-check-and-propose-fizzy-snowglobe.md.
  - *Fixed, waiting for the owner's check:* scoreboard short codes (`loc.apply_names` writes `X_XLA_TEAM_` / `Abbr3_` also when the
    full name matches; `NAMES_VERSION` '#5'; needs "Photos, logos and team names"); top-left logos centred
    (`images._crop_centred`, `LOGO_DRAWING` '#5'); Utah jersey shine map flattened (`looks.jersey_file`); helmet logo decals
    (`looks.decal_file`); helmet / gear colours of Utah, Seattle, Vegas (`builder.nhl_gear`, table `vbHh`, runs with the NHL step);
    Utah's rink picture `icesurface_22_bm` (`looks.ice_picture_file`); **Start RPCS3 from the tool** no longer fails with
    "vcruntime140.dll incorrectly installed" (`savedata.clean_environment`: the exe's `_MEI` folder was in RPCS3's DLL path; the
    fix is in the rebuilt exe, still to try by the owner).
  - *Already fixed earlier (0.9.2):* "Russia dresses 5 D" safety failure (`builder.fill_empty_national`, `room_for`); testers
    should use 0.9.2+.
  - *Open, not built:* Seattle / Vegas home ice (they share Nashville's arena art 16; arena art 30 / 31 files are incomplete, see
    docs/CALENDAR_AND_LOOK.md 2b); the helmet reflection cube map `enviro/helmet_<art>` still shows Arizona's ice; per-team ice size
    NHL / European (no field known; `exhibitionarena.arenatype` / `bouncemap` are the only candidates; owner: research later);
    Seattle / Vegas helmet colour mapping is a heuristic (`nhl_gear`).
  - Tests that need the disc: `$env:LEGACY_ROSTER_DISC` = the EU iso (where the owner keeps it:
    private/NOTES.md; read only). `.venv` has no pytest; run tests with `python`, pictures with `.venv\Scripts\python.exe`.
- **To check (owner):** move / resize the window while an update runs (smooth?), every button of both tabs, the size of
  the exe, and on a PC without WebView2 if possible. Nothing in the save changes.

Version 0.9.3 (2026-10-11, built, NOT committed; owner will do a UX/UI and logic redesign first): fixes from testers. Read
[docs/HANDOVER.md](docs/HANDOVER.md) and [docs/notes/select-teams-crash.md](docs/notes/select-teams-crash.md) first.
- **Select Teams crash on switching league** (SHL, Extraliga, AHL): most likely the program wrote empty team-name lines as texts of
  length 0 (the game's files never do; `loc.LocFile.set/set_existing` now mark an empty text absent) and over-long texts
  (`loc.fit`, `limits`, `select_lines`, `install_names` check; `NAMES_VERSION '#4'`). **Not confirmed in the game yet.**
- **Restore default** now starts from the game disc (`restore.default_slot`); before it took the updated roster as its own default.
- **Roster editor ratings:** unapplied card is applied on Save / player switch; national-team copy gets the same edits.
- **No roster / game not in RPCS3's list:** "Pick the game" buttons, `cli --game`, `savedata.NoGameError`, first save `...01`.
- **Draft step** skips placeholder records with impossible birth years (tester error "273 does not fit in 8 bits").

Version 0.9.1 (2026-10-07): **Restore.** `restore.py` (`default_slot`: the version's `...0200` save when `check_base` says it is the game's own
roster, else the disc; `copy_calendar`), `pipeline.update(restore_parts=, default=)` (ROSTERS: start from the default, written as it is when no step
is left; CALENDAR: copy `ihmS`/`Iwiq`, `verify(calendar_source=)`; PICTURES: `art.install.remove`), a Restore button per row (`widgets.SwitchRow(restore=)`,
`App.toggle_restore`) and the big **Restore default** (`App.restore_default`). The default is only read. Not built: balancing games played per team
(the 30-team calendar gives 76-80), per-kind picture removal (names / jerseys separately), equipment (docs: plan not built).

Version 0.9.0 (released 2026-10-07; CHANGELOG.md has the players' version), from the owner's tests of 0.8.1 on 2026-10-06:
- **Calendar 2026-27: confirmed in the game** (all four CAL tests matched NHL.com), now a normal step, on by default, 30 teams.
  The game's year label stays 2015 (not in any data file; owner: leave it). Seattle and Vegas cannot be in Season mode / Be a GM.
- **Loose 3D textures: confirmed** (`cli rendering-test`). **New, not played yet:** the real Utah / Seattle / Vegas jerseys, pants,
  socks, number sheets, Select Jerseys pictures and centre-ice logos (`art/looks.py`, installed with "Photos, logos and team names":
  `pipeline.install_looks`; `cli looks-test` writes only them), the Roster editor's **Jerseys and ice...** window for the 32 NHL teams
  (`editor/uniforms.py`; edits.json `uniforms` / `ice`), and **Export only SYS-DATA roster** (`pipeline.export_sysdata`, `cli export-roster`;
  for a PC without RPCS3). Docs/CALENDAR_AND_LOOK.md says what to check in the game and what is not built (extra jersey versions,
  old-layout versions from colours, the Jets throwbacks and old All-Star versions stay the game's own).

Version 0.8.1 (released 2026-10-06; CHANGELOG.md has the players' version): the owner's tests of 0.8.0 in the
game, in two rounds. **Confirmed in the game by the owner (2026-10-06):** the Tampa Bay and Toronto logos, the
Select Teams names (Utah Mammoth, Seattle Kraken, Vegas Golden Knights), Delete / Open folder, and Season mode
with the full update. **Still to be checked in the game** (ROADMAP "Round 3" rows): update in place (which roster
the game loads at boot), re-updating a roster made by 0.8.0, the Roster editor's save, the arena names and colours of
the game's own roster, and the **calendar 2026-27, the loose 3D textures (jerseys, ice) and the new jerseys / ice
logos, which the owner tests in a separate session: read docs/CALENDAR_AND_LOOK.md**.
First round:
- **Window:** every roster in step 2 has **Open folder** and **Delete** (`widgets.RosterRow`,
  `App.ask_delete` / `delete_save` / `open_save`, `savedata.trash_save`); `tools/window_shot.py delete`.
- **Logos:** the pictures with a white edge (`t`, `d`, `r`) are drawn from ESPN's plain logo
  (`install.EDGED_KINDS`, `plain_logo_url`), the others from the dark one; `LOGO_DRAWING` '#3';
  the photo pack was rebuilt with the 32 plain logos (kept out of git).
- **Team names:** Select Teams reads `TEAMLINE1/2_X`, `NICKLINE2_X`, `NHLTeamName_Abbr3_X` and the NHL
  slots' numbered texts, which `art/loc.py` now writes (`set_existing`, `set_select_lines`,
  `NAMES_VERSION`; FORMAT.md section 7). All three wait for the in-game check (ROADMAP).
Second round (evening):
- **Logos/names did not change in the game because the new code had never been installed** (the owner ran the
  0.8.0 exe; `installed.json` still had `#2`): after running the new exe with "Photos, logos and team names" on they
  were right. Calendar (`c`) and wide (`w`) logos now also take the plain logo where the dark one is a
  white silhouette and the game's own picture is coloured (Toronto; `LOGO_DRAWING` '#4').
- **Update in place** (default) or save as new: `savedata.update_in_place`, `pipeline.update(in_place=True)`,
  `cli update --in-place`, window card 4 and the editor's save bar share `App.save_mode`.
- **Roster editor** has one view (no As is / To be): the picked roster as it is plus this visit's edits.
- **Calendar 2026-27** (`schedule.py`, step `schedule`, OFF by default, `pipeline.EXPERIMENTAL`): written, tested
  offline, **not played yet** (`cli calendar-test`: CAL 1-4; hand-over in docs/CALENDAR_AND_LOOK.md).
- **Utah/Seattle/Vegas look, ice logo, jerseys**: `art/rpsgl.py` reads and rewrites the game's `.rpsgl` textures
  (byte-identical repack); `cli rendering-test` is the one in-game test (loose `rendering` files, never tried);
  `builder.nhl_identity` gives the game's own roster Utah's/Seattle's/Vegas's arenas and colours (the community
  roster has them). Real jerseys and centre-ice logos wait for the test (docs/CALENDAR_AND_LOOK.md).
- **Season mode crash: fixed** (owner played `season-test` rosters 1-4, the full update, 2026-10-06). The
  community roster names a removed player (Drouin) in two table headers and our update made him a free
  agent; `builder.drop_removed_player` removes him first, `verify.py` checks the header words; a roster
  made by 0.8.0 (stale markers) gets its free agents relinked (`Builder.relink_free_agents`, not played
  yet). `cli season-test` (`seasontest.py`) stays as the owner's check for sizes and regressions.

Version 0.8.0 (released 2026-10-05; CHANGELOG.md has the players' version): the testers' feedback on 0.7.0, with the
owner's decisions (ROADMAP.md, "Decisions taken ... testers' feedback"). Everything waits for the
in-game check (`pipeline.EXPERIMENTAL`: 'free agents', 'goalie gear', 'draft', 'own teams'):
- **Free agents:** `builder.would_retire` (retire_age: 30 on the game's own roster, 35 otherwise;
  never who played in the NHL last season, is on an NHL.com roster or is listed by a league or an
  IIHF squad). `settle_free_agents` retires old free agents, `add_unsigned` makes last season's
  unsigned NHL players free agents (created if missing). Data pack part `nhl_last`
  (`tools/providers/nhl_facts.py`). The game's own roster rebuilds its 2014 national teams on the
  first update (`clear_national`). All retirements happen before any player is created
  (DEVELOPING.md lists what breaks a byte-identical second run).
- **Real player data:** `draft.py` (data pack `drafts`, every pick since 2005) for every record,
  NHL.com's height, weight, hand and birthplace for every NHL player (`nhl_bio`). Name matching:
  full-name matches need a fitting birth year, namesakes go by the closest one, the DEL's age-only
  match accepts Nico / Nicolas.
- **Logos** in the game's own sizes (`images.LOGO_BOX`), ESPN's dark-background NHL logos,
  `install.LOGO_DRAWING` redraws installed logos once. Photo pack rebuilt.
- **Goalie gear** repainted in the new club's colours (`Builder.goalie_gear`, table `lVMf`).
- **Own teams:** a player's custom team named after a left-out club gets its players
  (`clubs.own_teams`, data pack `leagues.<key>.extra`); `stock.is_stock` no longer trips over one.
- Skipped pictures are named in the List of changes (`pipeline.note_skipped`); the Roster editor
  reads the unprepared disc roster's birth years right.
- After the owner's own test (2026-10-04/05):
  - players under 20 whom their league's list leaves out stay with their club (`clubs.STAY_AGE`,
    DuPont);
  - undrafted prospects of the next drafts (draft year still to come, round 0) in prospect pools, on
    the free-agent list or on no team join a real club of their country's league (`clubs.HOME_LEAGUE`,
    the CHL for the rest) inside that league's step (`_place_prospects`), as the game's own roster keeps its
    draft classes; `cli draft-test` (`art/lab.draft_lab`) remains to check where the draft looks;
  - pictures: Extraliga photos from hokej.cz's player pages (`tools/providers/czech.py`), last
    season's AHL/CHL photos for players this season's lists leave out (league `former`,
    `Builder.former_photos`); the National League publishes none;
  - the window keeps every step in view when the result shows (the big logo folds, the result's
    lines scroll: `App.fit_banner`, `compact_header`), and the cards have more contrast;
  - macOS and Linux: `savedata` finds RPCS3's data folder there (`data_folders`, `is_program`,
    `open_path`, `_running_posix`), `datasource.data_home`, `packaging/build.sh`,
    `.github/workflows/build.yml` (tests on three systems, Mac and Linux builds). Not tried on a real
    Mac or Linux PC yet.
  - without RPCS3 (a tester on a Mac in CrossOver): step 1 also takes a folder with roster saves
    (`savedata.SaveFolder`, `open_saves`; since 0.9.0 the window has the checkbox "Export only SYS-DATA roster" instead of the link:
    `pipeline.export_sysdata`, `cli export-roster`, docs/ARCHITECTURE.md "Without RPCS3"); photos and
    the game's own roster are not offered then.
  - Season mode crash: fixed for a roster updated from the community roster (ROADMAP "Season mode crash"); re-updating a roster made by 0.8.0 still to be played.

Version 0.7.0 (2026-10-04): fixes for two problems a tester had with 0.6.0 (nothing new goes into
the save):
- **Certificates:** the exe carries Mozilla's list of trusted certificates (certifi's
  `cacert.pem`, added by `build.ps1`) besides Windows' own, which lacked search.d3.nhle.com's
  Let's Encrypt root on the tester's PC. A check that still fails gives a plain message
  (`datasource.NotSafe`: PC clock, antivirus web scanning).
- **Missing files at start:** the window checks its unpacked files (`theme.missing_files`) and asks
  the player to start it again instead of crashing (an antivirus or cleaner removed them).

Version 0.6.0 (2026-10-04), built after the owner's checks of 0.5.0 (passed in the game:
photos, logos and team names; Save for EU + NA; the refilled national teams):
- **The game's own roster** (`stock.py`): players without a community roster start from the
  roster on their disc (window: last row "The game's own roster"; cli `--source disc`). No custom
  copies. 2014's players of 30+ retire to make room. Waiting for `cli stock-test` in the game.
- **NHL.com positions** for every NHL player (Cole Smith RW: Chicago has three right wings) and
  wingers on their own side of the lines. NHL players matched by name get NHL.com's birthdate; a
  goalie never matches a skater's record. Waiting for the in-game check.
- **Favourite-team logos** (`teamlogosreflection/r`, NHL slots only). Waiting for the in-game check.
- **One program** with every picture inside. Downloaded pictures are kept on the PC
  (`PictureCache`). Kept copies of replaced pictures are safer; the button is now "Restore the
  game's own pictures".
- **Readable results:** one line per part in the window (`BuildResult.lines`). "List of changes" is
  an HTML page grouped by part and team (`report.py`); the change log rows carry their part
  (`builder.ChangeLog`).
- **Window:** EU / US flags (drawn, `widgets.flag_image`), fewer redraws (background roster scan,
  rows kept, `configure_if_changed`, batched progress, the banner kept during an update).
- **Player links** of removed roster places are given back (`Builder.finish`), so repeated updates
  no longer fill the link table.

Version 0.5.0 (2026-10-04):
- **EU and NA:** rosters of both versions are listed with a tag; "Save for" (window) / `--for`
  (command line) saves for EU, NA or both; photos, logos and names go into both games. Saving into
  the NA version is waiting for the owner's in-game check.
- **Community rosters:** the community's 2026-27 roster is accepted (custom copies out of step) and
  updated; every empty national team is filled (IIHF rosters for 20 countries in the data pack).
- **Custom team names** use keys in the game's style (COACHELLA_VALLEY); the 0.4 names did not show
  for custom teams. Waiting for the in-game check.
- **Window:** no NEW tags, everything on by default; in the Roster editor "To be" runs the update
  by itself ("Refresh update" runs it again) and the card shows the player's picture
  (`editor/pictures.py`).
- **Disk space:** the owner's project drive has run full during work (another program filling it);
  check free space before builds and data refreshes.

Earlier (0.4.0, 2026-10-03):
- **Done:** NHL, ratings, national teams, and Liiga and Extraliga (confirmed in the game).
- **Experimental**, waiting for the owner's in-game check: SHL, DEL, National League, Norway, AHL and CHL.
- **Capacity:** with every league on, every spare player record is used. Junior depth players are
  skipped; every club still dresses 20.
- **Nothing published** (until 0.6.0).
- **Phase B:** the art test passed in the game (2026-10-03). "Photos, logos and team names" is
  built: current photos and logos made on the player's PC, with undo. Team names are written into
  the game's text file (`art/loc.py`): Utah, Seattle and Vegas instead of Arizona and the All-Star
  teams, every rebuilt club, and texts for the custom teams. The prospect pools in the custom
  slots get logos of their own. The owner saw the renamed clubs in the game (2026-10-04); the
  custom team names were still missing (keys the installer adds, see ROADMAP.md).
- **League test** (`cli league-test`): built, not played yet. It moves Coachella and Henderson into
  the AHL, Jokerit into Liiga, Ajoie into the National League and Penticton into the WHL in a LAB
  roster.
- **Phase C:** docs/SEASON_PLAN.md is written. Experiment C1 waits for the owner.
- **0.4.0:** three programs (plain, Photos with every picture inside, command line); the Puck Peak
  link and tagline in the header; the **Roster editor** tab (as is / to be, edit basics, ratings,
  team, new players, a player's own photo, a team's name, city, abbreviation and logo; edits kept
  and re-applied after every update). Waiting for the owner's check.

Details and next steps in [docs/ROADMAP.md](docs/ROADMAP.md).
