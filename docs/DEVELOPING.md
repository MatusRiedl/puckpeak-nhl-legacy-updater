# Developing

How to set up, test, change and build the updater. Read [ARCHITECTURE.md](ARCHITECTURE.md) first
for how the pieces fit; [FORMAT.md](FORMAT.md) for the save format; [MAINTAINING.md](MAINTAINING.md)
for data refreshes and releases; [ROADMAP.md](ROADMAP.md) for what is done and what is next.

## Setup (Windows)

| Need | For | How |
|---|---|---|
| Python 3.10+ (developed on 3.13) | everything | python.org |
| `.venv` with PyInstaller, pywebview (pinned 6.2.1), CustomTkinter | the window, the exe | `powershell -ExecutionPolicy Bypass -File packaging\build.ps1` creates it (and builds) |
| Pillow in `.venv` | images, window screenshots | `.venv\Scripts\python -m pip install pillow` |
| pytest | tests | `python -m pip install pytest` (any Python that can import the package) |
| **A base roster save** | most tests, screenshots | see below |

**The base roster cannot be in git.** It is another modder's work on top of the game's data. Tests
and `tools/window_shot.py` look for a roster save folder (with `SYS-DATA`, `PARAM.SFO`,
`ICON0.PNG`) of the 2025-26 community family at `work/backup/BLES021530202/`, or wherever
`LEGACY_ROSTER_BASE` points. `work/` is git-ignored. On a fresh clone, ask the project owner
for one, or save the community roster in the game and copy its folder. Without it, the tests
that need it are skipped (and say so).

**The game's own roster** (`tests/test_stock.py`) needs the game itself: set `LEGACY_ROSTER_DISC`
to a disc image (`.iso`) or extracted game folder of NHL Legacy Edition, EU or NA. It is only
read, never changed. Without it those tests skip. In PowerShell:
`$env:LEGACY_ROSTER_DISC = 'D:\...\NHL Legacy Edition (USA).iso'`.

Run from source:

```
.venv\Scripts\python -m legacy_roster                     # the window (needs pywebview; --classic: the 0.9 window)
$env:LEGACY_ROSTER_DEVTOOLS='1'                           # before it: the page's developer tools (F12) in the window
python -m legacy_roster list   --rpcs3 <path to rpcs3.exe>
python -m legacy_roster update --rpcs3 <path> --dry-run   # build and check, write nothing
```

**Picture packs.** The window and `update --photos` download `photos.zip` and `looks.zip` from the file server
(`legacy_roster/packs.py`) into `%LOCALAPPDATA%\NHLLegacyRosterUpdater\packs\`. While developing:
- `$env:LEGACY_ROSTER_PACKS='<folder>'`: take the packs from a folder of your own (for example `private\packs`) instead
  of downloading them;
- `$env:LEGACY_ROSTER_FILES_URL='http://localhost:8000/'`: another server for the packs and the data pack (a copy, a
  test); `LEGACY_ROSTER_PACK_URL` moves the data pack alone;
- `python -m legacy_roster packs status|download|remove`: what this PC has.
No test reads this PC's packs: `tests/conftest.py` gives every test an empty packs folder (and drops
`LEGACY_ROSTER_PACKS`); the download tests serve packs of their own from a local http server.

**`private/`** (git-ignored, the maintainer's PC only): the picture packs (`private/packs/`), the tools that make the
look pack and three data pack parts, their tests (`python -m pytest private/tests`) and `private/NOTES.md`. Without it
everything else works: `tools/build_datapack.py` keeps those parts as the bundled pack has them. Nothing in a tracked
file may name where the game's content came from: `python tools/clean_check.py` (also `tests/test_clean.py`,
`build.ps1`) lists every such word with its file and line.

## Layout

```
legacy_roster/   the program (see ARCHITECTURE.md for what each module does)
  tdb.py sfo.py schema.py schema_names.py roster.py layout.py      the save and its layout
  builder.py lines.py ratings.py estimate.py donors.py matching.py the update
  stock.py                                                         the game's own roster (from the disc)
  report.py                                                        the list of changes as a page
  leagues/clubs.py leagues/pools.py                                club leagues, pool relocation
  art/disc.py art/bigf.py art/refpack.py art/dds.py art/lab.py     menu art: the game's file format, the art test
  verify.py                                                        integrity checks
  datasource.py savedata.py pipeline.py                            data, saves, the job
  frontoffice.py seasonsave.py                                     contracts and cap by team; the player's Season saves (read only)
  window/ (pywebview)  app/ (controllers)  web/ (the page)          the window (0.10)
  editor/card.py                                                   the player card's checks (both windows)
  progress.py cli.py __main__.py                                   progress bar, command line, start
  gui.py widgets.py theme.py editor/view.py editor/uniforms.py     the classic window (fallback, frozen)
  data/             data pack, icon, header logos, fonts (Source Sans 3, OFL)
tools/           maintainer scripts, not part of the exe
  build_datapack.py   the data pack            providers/   one module per data source (web.py: shared helpers)
  club_slots.json     club -> team slot        decode_schema.py, isotools.py   game disc
  capacity.py         records and pool room an update needs (read only)
  names_report.py     slots that still show an old name (read only)
  window_shot.py      picture of the window in any state
  build_photopack.py  the photo pack (private/packs/photos.zip)
  publish_packs.py    the packs and the data pack onto the file server (owner's go-ahead)
  clean_check.py      no tracked or shipped file names where the game's content came from
tests/           pytest suite
private/         the maintainer's own tools, packs and notes (git-ignored; see above)
packaging/       build.ps1 (exe), launcher*.py, make_assets.py (images)
docs/            this folder
work/            the original lab scripts and backups (git-ignored, local only; leave untouched)
```

## Tests

```
python tools/quicktest.py           # ONLY the tests of the files you changed, in parallel: 1-3 minutes (use this)
python tools/quicktest.py --list    # which test files that is, without running
python tools/quicktest.py tests/test_clubart.py tests/test_leagues.py   # chosen files, in parallel
python tools/quicktest.py --full    # everything in parallel (5 minutes, 585 tests, measured 2026-10-24): before a release, never beside a build
python -m pytest -q                 # everything, one process: about 20 minutes. Do not.
```

`quicktest.py` needs `pip install pytest pytest-xdist`; it uses `-n` workers and `--dist loadfile` (a file's expensive
roster builds are made once per worker). It picks files from `git status`: a changed test file runs itself, a changed
module runs the test files that name it, and a module nearly everything builds on (`pipeline`, `builder`, `layout`,
`verify`, ...) runs the CORE list in the script. Tests never name real players or clubs of the data pack's NHL snapshot
(it moves on with every `--refresh nhl`): pick them from the build's own log, as `test_contracts.left_out_star` does.

| File | Guards |
|---|---|
| `test_tdb.py` | checksums; an untouched roster rebuilds byte-identical; field read/write; real names as aliases; record add/delete; broken chain detected |
| `test_sfo.py` | PARAM.SFO strings, name length, real save keeps its size |
| `test_pipeline.py` | the full NHL/ratings/national build: integrity, every NHL player on his team, NHL.com's positions (Cole Smith), wingers on their side, mirrors, hard limits, legal line-ups, exact attributes, untouched fields, clean new players, styles, **second run identical**, steps on their own, line builder rules, an unknown layout refused |
| `test_stock.py` | (needs `LEGACY_ROSTER_DISC`) the game's own roster: the save made from the disc matches a real save's tables and wrapper; prepare makes room once; a full update passes every check, skips nobody and a second run is identical; clubs in switched-off custom slots left out |
| `test_leagues.py` | every club league in the pack, built together: real names and listed players (allowing for spelling, NHL call-ups, players another league keeps, skipped players, line-up fillers), playable clubs, contracts, plausible ratings per league, pools moved and nobody lost (on a team or a free agent), free agents without contracts but with their rights, AHL players on NHL contracts belong to the parent club, second run identical, a league added later, running out of records, twins, birthdate matching |
| `test_providers.py` | every feed parser on small samples (no network): HockeyTech rows, Sportality players, DEL roster page, National League players, places to countries |
| `test_datasource.py` | the newest readable pack wins; a pack for a newer program is skipped |
| `test_art.py` | RefPack round trips; art files read and take a new image (parts, trailer kept); 32-bit logos exact; the art test installs into a fake RPCS3 and removes itself, restoring a file that was there before (synthetic art, none of the game's data); the logo styles incl. the favourite-team `r`, only for NHL teams; pictures downloaded once (cache) and originals always kept (another pack's file, a lost list of installed files) |
| `test_pictures.py` | player pictures on a PC with several rosters: people compared across rosters (patch years, Alex / Alexander, twins), a number another roster or a pack's file uses never given out, ours on it forgotten and given back (kept copy back, else deleted), own pictures alone change only their players and go in with Photos off (a second update identical), a photo that cannot be made leaves the row as it was, NHL.com's grey stand-in refused (own black-and-white pictures not) |
| `test_savedata.py` | finding RPCS3 (relocated `dev_hdd0`, several users, folder inside RPCS3, plain-word errors), listing, installing without touching the source, folder numbering, names; an RPCS3 with no roster but the game listed (the game's own roster, PARAM.SFO from scratch byte-identical to a real one, the disc's icon) |
| `test_app.py` | the window's controllers without a window (FakeHost, a pretend RPCS3): the Update tab's state, the editor's Apply / Undo, an unapplied card taken on Save, a bad card on switching player, search, team, My edits, a new player, Jerseys and ice, the game patch row (question, two switches, Unpatch), a patch roster not saved from the editor |
| `test_gamepatch.py` | the game patch: every entry's words, the player entry = the lab entries, the roster fits and their checks, the db files (some need `LEGACY_ROSTER_DISC`) |
| `test_contracts.py` | the money scale's units ($17M = 2334 / 3400), default deals, rescaling, a deal with an extension, the 2026-27 deals in a normal build (McDavid, payrolls in reach of the cap) and in a game-patch build (real dollars, one rescale), verify catching a wrong cap hit / extension / 0 seasons |
| `test_patchinstall.py` | patching a fake RPCS3: only our lines of `patch_config.yml` change and come back byte for byte, another `<TITLE>_patch.yml` is kept, refused while RPCS3 runs, photos' undo leaves the db files; `update(game_patch=)` passes every patch check, a second run is identical, a patch roster with the row off is refused, Restore default unpatches |
| `test_editor_card.py` | the player card's checks: ratings below 40 the game gives are kept, error texts, unchanged vs changed, rename, new player, change notes |
| `test_calendar_office.py` | the Calendar and Front office controllers without a window: the roster's calendar on a month page, an organisation's contracts and cap, the contract window, a made-up Season / Be a GM save |
| `test_contract_edits.py` | contracts set by hand (edits.json `contract`): written after the real deals, checked by verify, a second run identical |
| `test_seasonsave.py` | a made-up Season / Be a GM save (no game data) read back as calendar, records and standings |
| `test_lines_strategy.py` | the editor's own lines and strategies (`lines.check_lineup` / `set_lineup`, `strategy.py`, `edits.apply_teams`) |
| `test_window.py` | the pusher sends each slice once; every page file is local and every import resolves; every `call('x')` in the page exists on `Api` |
| `test_progress.py` | progress mapping replays a real update's messages in order; every other message is a known remark (`progress.REMARKS`) |

The build tests use the bundled data pack only (its NHL snapshot instead of live NHL.com), so
they are reproducible offline.

## Checking a change

Before calling a change done:

1. `python tools/quicktest.py` is green (the files your change touches; and not because the base roster is missing: look for skips).
   The whole suite (`--full`) only before a release.
2. For engine changes: the second-run tests still pass. A build on its own output must be
   byte-identical; if your step is not, it has hidden order or randomness.
3. For window changes: look at it. `tools/window_shot.py` drives the real controllers on a temporary fake
   RPCS3 (never your real saves) into a state and has Microsoft Edge (headless, nothing shows) draw the page with
   that state put into it. Same picture on every PC, at any scaling:
   ```
   .venv\Scripts\python tools\window_shot.py setup    shot.png --show-path C:\Games\RPCS3\rpcs3.exe
   .venv\Scripts\python tools\window_shot.py done     shot.png --all          # runs a real offline update
   .venv\Scripts\python tools\window_shot.py roster   shot.png --scale 1.5 --screen-lines 768
   .venv\Scripts\python tools\window_shot.py calendar shot.png --size 940x640 # the smallest window
   .venv\Scripts\python tools\window_shot.py ready    shot.png --tab patch    # another tab than the state's own
   .venv\Scripts\python tools\window_shot.py ready    x --browser             # the page in your browser, to try CSS live
   ```
   **States** (the tab they show):

   | Tab | States |
   |---|---|
   | Setup | `none` (RPCS3 not set), `setup` (a roster picked), `delete` (the question before a roster goes to the Recycle Bin), `export-ready` |
   | Update | `ready`, `updating`, `done` (a real offline update), `details` (done, the details open), `failed`, `downloading` (the picture packs coming in), `full` (11 EU rosters, one more than the game lists), `export` |
   | Game patch | `patch` (not patched), `patched` (an older patch, a roster tagged "32 teams") |
   | Roster | `roster` (also `editor`), `equipment`, `face` (`SHOT_FACE` typed); `SHOT_GOALIE=1` picks a goalie |
   | Lines, Strategy, Jerseys & ice | `lines` (`SHOT_TAB=pp|pk|ot|so|letters`: another part), `strategy` (also `strategies`), `jerseys` (also `uniforms`) |
   | Calendar | `calendar` (`SHOT_DAY=YYYY-MM-DD` opens that day, `SHOT_MODE=league` all games) |
   | Front office | `office`, `contract` (the contract window for the first player, the cap hit raised by $1M) |

   The team states show Edmonton, or `--team <slot>` (36 Charlotte, 135 Canada). **Options**: `--tab ID` shows another
   tab than the state's own (`setup`, `update`, `patch`, `roster`, `lines`, `strategy`, `jerseys`, `calendar`,
   `office`); `--size WxH` the page's size in the window's units instead of the one `--screen-lines` gives (`940x640`:
   the smallest window); `--scale`, `--screen-lines`, `--disc`, `--show-path`, `--all`, `--saves`, `--live`,
   `--browser` (`python tools\window_shot.py -h` and the file's docstring).
   Check 1, 1.5 and 2 `--scale`, `--screen-lines 768` and `--size 940x640`. The pretend RPCS3 has an EU and
   an NA roster (flags, "Save for"); `--disc <your game image>` (read only) lets the Roster tab's
   card show real portraits, the Jerseys & ice and Equipment windows the game's pictures, and adds the game's own roster
   to the list (with it, `done` also installs the pictures, which downloads the packs: slow). The base roster has the
   game's own 2015-16 calendar: for a picture of the real one, point `LEGACY_ROSTER_BASE` at a copy updated with the
   calendar step (`python -m legacy_roster update --savedata <a copy of the base's folder> --offline`, with
   `LOCALAPPDATA` set to a scratch folder so the reports stay out of your own). `--show-path` also replaces the
   temporary and home folders in the pictured texts (backup paths name the user). `--live` opens the real
   window and paints it with PrintWindow; WebView2 draws on the GPU, so that picture can come out blank or
   cut: trust the headless pictures.
4. For anything shipped: build the exe and start it (MAINTAINING.md, "Smoke test").
5. Anything that changes what is written into the save (new step, new rule, new league) also
   needs a test **in the game** by the project owner before it leaves `pipeline.EXPERIMENTAL`
   (the list of parts still waiting for that check; the window no longer marks them): load the
   roster, open Roster Management, Team Management and lines, and play a game with the
   changed teams.

**Never write test output into the real RPCS3 folder.** Use `--dry-run`, the tests, a copy of
the savedata folder, or `tools/window_shot.py`.

## Common changes

### Change what an update does

The steps are in `pipeline.build()` and run in a fixed order (ARCHITECTURE.md). Engine rules:

- Standard library only; never import Tk in the engine.
- Report progress with `self.progress(...)` / `say(...)` in plain sentences. If the window
  should show progress for a new message, add a pattern to `progress.STAGES`.
- Log every change to `b.log` as `[team, change, player, detail, number]`; the report and the
  summaries are built from it.
- Remove roster entries by adding them to `b.deleted` (removed in `finish()`), never directly.
  To take a player off his team, use `b.release(e, live)`. It puts him on the free-agent list when
  he has no club left. A record left teamless and not a free agent would be reused on the next run
  and break the byte-identical second run.
- A new player record comes from `b.take_record()` (donors), never by growing the table. Club
  leagues pass `required=False` and skip the player when none is left.
- Keep it deterministic: sort with explicit keys, no `random`, no dependence on dict order of
  external data.
- If you make the game accept something new, add the rule to `verify.py` and FORMAT.md
  section 5.

### Add an update step

1. `pipeline.py`: a key, a label in `STEP_LABELS`, the call in `build()` at the right place,
   and the key in `CORE_STEPS` (always offered) or among the club leagues (offered when the data
   pack has it).
2. The code: a `Builder` method or a new module that takes the `Builder`.
3. `progress.STAGES`: a pattern for the step's first message.
4. `BuildResult.headline()` / `summary()`: a line about what it did.
5. Tests in `tests/`. The window and the command line pick the step up through
   `pipeline.steps_for()` (switched on by default); list it in `pipeline.EXPERIMENTAL` and in
   ROADMAP.md until it has been played in the game.

### Add a club league

Every league the game has is in place now (ROADMAP.md). The recipe still applies when a feed has to
be replaced, or for a hand-made source.

1. **The provider.** Write `tools/providers/<name>.py` with `fetch(season_year, sources=(), log=print)`
   returning `{club name in the feed: [player, ...]}`. Use `providers/web.py` for downloads
   (`get_json`, `get_text`, polite pauses, retries), units (`inches_to_cm`, `pounds_to_kg`) and
   countries (`country_of_place`, `ISO2`).
   - **Player fields:** `first`, `last`, `birth` `[y, m, d]`, `pos` (`C L R D G`, or `F` when the
     feed does not split forwards). Where known: `shoots`, `num`, `height_cm`, `weight_kg`,
     `country` (ISO or IOC code), `letter` (`C`/`A`), `rookie`.
   - **AHL:** also `nhl_contract`.
   - **A feed with ages only:** set `birth_approx` (see `penny_del.birth_from_age`).
   - **Season check:** make the provider stop when the feed is not for `season_year`.
2. **The slot map.** Map clubs to team slots in `tools/club_slots.json`: `source` (name in the feed),
   `full`, `short`, `abbr`, `art`.
   - **`art`:** keep the slot's original art abbreviation, so logo and jersey stay the original club's.
     A pool slot's original art is in the stock team table on the disc.
   - **Several of the game's leagues** behind one switch go under `parts`, each with its
     `league_id` (see `chl`).
   - **One slot in another game league:** a slot may carry its own `league_id` (Coachella Valley,
     Henderson: 13).
   - **More clubs than slots:** the game's slots are fixed, so some clubs are left out. They are
     listed in the pack's `left_out` and shown in the window.
3. **Registration.** Add the feed to `FEEDS` in `tools/build_datapack.py`, keyed by the part's name. Check that
   `estimate.LEAGUE_GAP` and `pipeline.LEAGUE_ORDER` have the league (all the game's leagues are there).
4. **Build and test.**
   - Run `python tools/build_datapack.py --refresh <league or part>`. Read the printed counts and any
     "left out … birthdate is not possible" lines.
   - Run `python tools/capacity.py`: records and pool places still enough?
   - Run the tests, add a parser test with a small sample to `tests/test_providers.py`, and add the
     league to `pipeline.EXPERIMENTAL`. `leagues/clubs.py` does the rest.

A league without a usable feed can be supplied the same way from a hand-made JSON turned into
that structure.

### Change the window

- The window is nine tabs in one row (Setup, Game patch, Update, then the team tabs Roster, Lines, Strategy,
  Jerseys & ice, Calendar, Front office); ARCHITECTURE.md "The window" has the map: which page, controller and slice
  each tab has, the shared team list and the followers.
- What the window knows and may do is in the controllers (`app/update.py`, `app/editor.py`, `app/uniforms.py`,
  `app/equipment.py`, `app/lines.py`, `app/strategy.py`, `app/calendar.py`, `app/office.py`, `app/season.py`): add a
  field to `snapshot()`, a method for the action, and call `self.changed()` after changing state (it is pushed to the
  page on the next tick). Take the controller's `lock` in every method the page can call (each call comes on its own
  thread).
- The page's call goes into `window/api.py` (one line per method; `tests/test_window.py` checks that
  every `call('x')` in the page has one). The look is `web/js/*.js` (React through `htm` templates,
  no build step: edit and reload) and `web/css/*.css`; shared pieces (Button, Toggle, Segmented,
  TextField, Modal) are in `ui.js`. Animate only `transform` and `opacity`.
- Try CSS in a normal browser: `tools/window_shot.py <state> x --browser`.
- Text for players stays short and plain, kept in `app/texts.py` or the controller, not in the page.
- The classic window (`gui.py`, `widgets.py`, `theme.py`, `editor/view.py`, `editor/uniforms.py`) is
  frozen: fix only what breaks it; it goes in 0.11.
- Images: `.venv\Scripts\python packaging\make_assets.py "<puck-peak>\assets"` rebuilds the
  header logos (`logo_100/125/150/200.png`, one per screen scaling) and `app.ico` from Puck
  Peak's `BB.png` and favicon. The results are committed.
- Pictures for the README (`docs/shot_*.png`): `tools/window_shot.py <state> docs/shot_<name>.png --size 1064x961
  --show-path "C:\Games\RPCS3\rpcs3.exe"` (`done` → `shot_done`, `roster` → `shot_editor`, `equipment`, `jerseys` →
  `shot_uniforms`, `calendar`, `office`, `prospects-pro` → `shot_prospects`; `--disc` for the game's pictures, but not
  for `done`: with the disc its update also makes the photos and the picture catches it half way). `calendar` and
  `office` come from an updated copy of the base roster (`update --savedata <copy> --source <folder> --in-place
  --offline` with a scratch `LOCALAPPDATA`, then `LEGACY_ROSTER_BASE` = that folder; `SHOT_DAY=2026-10-24` opens a
  day), so they show the real calendar and contracts. Look at every picture before it goes in: never publish one that
  shows a real user name, a personal path, the desktop or other programs.
- **Mockups of new screens** can be made in `private/mockup/` (git-ignored, never in the exe): `python
  private/mockup/serve.py --open` serves its files over `legacy_roster/web/` (a file in `private/mockup` wins, every
  other one is the real page's, only read), so a clickable draft uses the real CSS, fonts and shared pieces. `--shots`
  makes pictures of it, `--test` clicks through it in a hidden browser. Show the owner the mockup before building.

### Add a team tab

A team tab shows the team picked in the shared team list on the left. To add one:

1. **A follower controller** in `app/<name>.py`, without window code: `__init__(self, host, editor, ...)` with an
   `RLock`, ending with `editor.follow_with('<tab>', self)`; `follow(team)` (its tab came into view or the team
   changed: remember the team, `shown = True`, do the work, `self.host.changed(SLICE)`), `hide()` (another tab shows:
   `shown = False`, do nothing more), `roster_changed()` (a roster was read again: drop everything kept for teams) and
   `snapshot()` (its slice, `{'team': None, 'why': ...}` without a team). Optional: `drafts()` (teams with changes not
   applied yet, marked in the list) and `rail_numbers()` (`{slot: {'text', 'tone', 'tip'}}`, the number next to each
   team; `EditorController.rail_view` asks it for the tabs it names). Never call the editor's followers with the
   editor's lock held; a follower takes its own lock first.
2. **Register it** in `window/main.py`: make it after the editor, `host.register('<slice>', x.snapshot)`, pass it to
   `Api` and put it in the `controllers` dict (and in `tools/window_shot.py`'s `controllers()`).
3. **Its calls** in `window/api.py` (`@_safe`, one line each, `<tab>_<action>`).
4. **The tab**: its id in `TEAM_TABS` and `RAIL_TIPS` (`app/editor.py`) and in `TABS`, `TEAM_TABS` and `TIPS` (the Help
   bar's line) in `web/js/main.js`; a page module `web/js/<name>.js` exporting the tab (`useSlice('<slice>')` in
   `main.js`, a `tpane('<tab>', ...)` next to the others); its styles in `web/css/teams.css`. The Save bar shows under
   every team tab but the Calendar (`main.js`).
5. **Test** the controller with a stand-in host (the small `Host` in `tests/test_calendar_office.py`, or
   `tests/test_app.py`'s FakeHost), add a `window_shot.py` state
   (`TEAM_STATES`), and look at it at 100 %, 150 %, 200 %, on a 768-line screen and at `--size 940x640`.

## Linux (and macOS from source)

`savedata.find_rpcs3` accepts the RPCS3 program (rpcs3.exe, rpcs3, an AppImage, RPCS3.app) or, off
Windows, RPCS3's data folder; the data is looked for next to the program, then in
`savedata.data_folders()`. The program's own files go to `datasource.data_home()`
(`~/Library/Application Support`, `$XDG_DATA_HOME` or `~/.local/share`). Folders and pages open with
`savedata.open_path`. Tests simulate both layouts (`tests/test_savedata.py`). The Linux program is built in a
box (`packaging/linux/build_in_docker.sh`, MAINTAINING.md "The Linux program"); on Linux its window uses Qt WebEngine
from PySide6 (`window/main.linux_engine`). There is no Mac program since 0.80.1; from source it runs on a Mac.
`.github/workflows/build.yml` only runs the tests on Linux and Windows.

## Building the exe

```
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Creates `.venv` if needed, installs PyInstaller, pywebview, CustomTkinter, Pillow and certifi there (certifi's
`cacert.pem` goes into the exe as `legacy_roster\data\cacert.pem`, see "Things that are not
obvious"), and writes
`dist\BluelineLegacy.exe` (window: `legacy_roster\web` added as data, `--collect-all` webview, pythonnet,
clr_loader and customtkinter; about 26 MB: no picture pack goes inside, `build.ps1` refuses a zip in
`legacy_roster\data` and any `tools\clean_check.py` hit); since 0.85.0 no copy under the old name
`NHLLegacyRosterUpdater.exe`. No command-line exe since 0.80.1. It carries Pillow for
"Photos and logos";
its image readers are named with `--hidden-import` because Pillow loads them by name.
Close a running copy first: Windows does not let a running exe be replaced (the script stops
with a message). `build/` and `dist/` are git-ignored.

## Debugging

| Symptom | Look at |
|---|---|
| What did an update change? | the report CSV (`%LOCALAPPDATA%\NHLLegacyRosterUpdater\reports\`), or the window's "List of changes" |
| The window says "Something went wrong" | `%LOCALAPPDATA%\NHLLegacyRosterUpdater\logs\error.log` (traceback) |
| "Could not connect safely" / `CERTIFICATE_VERIFY_FAILED` | the PC's date and time, antivirus HTTPS scanning, and whether the exe carries `cacert.pem` ("Things that are not obvious") |
| The safety check failed | the problems in the details panel / CLI output; `verify.py` explains each check |
| A table's contents | `python -m legacy_roster export --rpcs3 <exe> --source <folder> --out tables` (CSV, real column names) |
| The game crashes or ignores a roster | RPCS3's `log\RPCS3.log`: search `ShowSaveDataList` (what was loaded), `Access violation` (crash), `sys_fs_open(path=` (files opened). RPCS3 keeps the log open: read it with shared access |
| Season mode crashes with our roster | `python -m legacy_roster season-test --rpcs3 <exe>` (`seasontest.py`) writes LAB rosters with more and more steps (and trimmed copies) plus `reports\season_test.txt` with the size of each in Season's tables (`seasontest.counts`); the owner loads each and says which one crashes (ROADMAP "Season mode crash") |
| The calendar, jerseys and ice | `calendar-test` (`calendartest.py`, `schedule.py`), `rendering-test` (`art/rendering.py`, `art/rpsgl.py`): LAB rosters / loose files the owner tries in the game; ROADMAP "Calendar" and "Jerseys and the ice" say what to look at |
| A checksum question | `tdb.check_chain(raw)`, FORMAT.md sections 2 and 3 |
| Reproduce an old lab build | hidden `update --research work/research` uses the lab's saved inputs instead of live data |

## Things that are not obvious

- **Hard limits**: 252 team records (table full, team ids 8 bits), league id per team fixed,
  40 entries per team, `proteam`/`draftteam` 5 bits (the team in slot 31, Vegas, cannot hold
  rights; a roster for the game patch gives `proteam` 6 bits, `gamepatch.rights_wide`). See FORMAT.md section 5.
- **Birth years** are stored as year − 1910 in this roster family (stock: − 1900). Records nobody
  updated since the game's 2015 database still hold − 1900 and read ten years young. Their draft year
  (stored − 1900 everywhere) gives them away: `donors.real_birth_year`. About 1,250 teamless
  records are like that.
- **Second runs must be byte-identical**, and the club leagues taught what breaks that. Each of these
  looks harmless but changes the next run:
  - a record left teamless without being a free agent (it becomes a donor next time);
  - a player listed by two feeds (keep him with the first league: `b.placed`);
  - a feed listing a player twice;
  - estimating ratings the list would set once the record exists (`b.list_rating_for`);
  - fillers chosen from people who only become available later in the run;
  - a player retired after the first new player was made (his record is spare only for the next
    update): retire in `settle_free_agents`, the NHL step or `retire_leftovers` only;
  - a free agent the rule would retire (`would_retire`): the next update retires him. So a national
    team never takes one, a rising-star swap never drops one, and places on NHL copies and national
    teams do not stop a retirement (Pietrangelo, on Vegas and its copy);
  - spare records chosen before the ratings step: a retired player the ratings list still rates drops below the
    legend line (Henrique), so `donors.refresh()` runs after it;
  - a feed match that depends on records the same run creates (the DEL's age-only "Nicolas
    Krämmer" became a second record of the game's "Nico", and the IIHF squad then named the new one).

  - a step that changes a club after its league's step (it must happen inside the step, the way the
    next run will see it: `_place_prospects` puts prospects into `leftovers`); and a prospect placed
    on a slot that was a pool until this run is not that pool's player (`joined`);
  - The list's rating matched by name alone (no birthdate) only reaches NHL and AHL players: a player who
    leaves the AHL for Europe counts by his attributes from then on (`Builder.unrate_name_only`);
  - ties in line-ups broken by the entry's row, which moves between runs: break them by player id;
  - a new player of the edits ranked by his reused record's old quality (the next run's Builder rates him by his
    attributes): `edits._set_ratings` sets `b.quality` for him;
  - a new player arriving with his reused record's old number and bumping a team-mate (the next run's league step gives
    the listed number back to the team-mate): without a number of his own he takes a free one (`edits._move(wins=False)`).

  `diff2`-style checking helps: build twice, compare every table field by field, and print the
  second run's change log; the rows it still writes name the culprit.

  `test_a_second_run_with_club_leagues_changes_nothing` catches them. To find the cause, build twice
  and compare the tables record by record.
- **Picture numbers are shared by every roster on the PC.** A portrait is the file `p<artid>.big` in the game folder,
  read by every roster of that game version (and every RPCS3 user). Before 0.10.4's testers it was enough to be
  consistent inside one roster; now `portraits.plan` also asks `Claims` (every roster save, every portrait file) and
  compares people with `same_person` (no birth year: patch rosters shift it). Keep `Registry.id_for` from handing out
  anything in `Claims.used()`; tests build without claims, so the byte-identical second runs do not see them.
- **Records are the scarce resource**:
  - goalies most of all (a skater record can switch position, a goalie's cannot);
  - with every league on, every spare record is used (a newcomer on a later update gets one through
    `Builder.make_room`);
  - `tools/capacity.py` shows the numbers.
- **Ratings** are stored as rating − 36 in 6 bits; the exact field per attribute is in
  `schema.py`. An older correlation-guessed map (`work/research/attr_map.json`) was wrong; do
  not revive it.
- **Mirrors** (custom teams 222–233) must stay identical to their NHL team or the game shows
  different rosters for the "same" team. Community rosters may come with them out of step:
  `check_base` recognises them by name, `sync_mirrors` makes them copies again and releases a
  player who was only on the copy (the 2026-27 roster's Ben Hutton) as a free agent.
- **Custom team names** are the game's text under the team's `shortname`; only keys in the game's
  own style (capitals, digits, underscores: LAS_VEGAS) showed. Write a custom team's city with
  `layout.set_city`, never `T.set(..., 'shortname', ...)`. Texts added to the text file keep their
  key's case (`loc.LocFile.set`). About 11,700 of the game's own text records carry a hash that is
  not that of their stored key; leave them alone.
- **EU and NA** read the same `SYS-DATA` and their discs hold the same art and text files. Code that
  works with a game folder or disc takes the title id of the roster in hand (`Slot.title_id`),
  never a fixed `BLES02153`.
- **The team table of a core build stays untouched** (`test_hard_limits_...`): only steps that name
  teams (club leagues, pools, team edits, team names) may write it.
- **Name fields** are limited in UTF-8 bytes, not characters (`Builder.set_text`).
- **Matching**: twins share last name and birthdate, so first names must agree; club matching
  requires the birthdate (the DEL, which gives ages, matches by full name and birth year);
  Ratings-list name-only matching is limited to NHL and AHL teams; `norm()` spells out ø, æ, ß, ł (otherwise
  "Øby-Olsen" loses a letter). Each rule came from a real mismatch.
- **Draft data** (`draft.py`): `draftposition` is the overall pick, `draftteam` slot + 1 (Vegas cannot
  be stored), a junior not drafted yet has his draft year and round 0. `real_birth_year` must not
  move a junior's birth year with his draft year: a birth year that fits the draft year is the
  record's own.
- **Positions and styles**: defencemen have playing styles 1–4, forwards 5–10. A skater who
  changes between them needs a style of the new range (`Builder.set_position`).
- **Engine messages are an interface** for the progress bar (`progress.py`).
- **CustomTkinter**: `bind()` on a CTk widget binds its inner parts; use `tk.Frame.bind` for the
  widget's own size event. Scaling below 100 % makes 1-pixel outlines disappear.
- **One-file exe** unpacks itself on every start (about 3 s) and is unsigned (SmartScreen). It
  unpacks into Windows' temporary folder (`%TEMP%\_MEI...`), where an antivirus or a cleaning
  program can remove files (a player's `couldn't open ...\_MEI...\logo_100.png`, fixed in 0.7.0). The window
  checks its own files at start (`theme.missing_files`) and asks the player to start it again.
- **Certificates**: Python checks sites against Windows' own list, which Windows fills only when
  its own programs need a root. A player's PC lacked the Let's Encrypt root of search.d3.nhle.com
  (`CERTIFICATE_VERIFY_FAILED ... certificate has expired`, fixed in 0.7.0) while api-web.nhle.com (Google)
  worked. The exe carries Mozilla's list too (`datasource.tls_context`, `CA_BUNDLE`, added by
  `build.ps1`; not in git, so from source only Windows' list is used). A check that still fails
  becomes `NotSafe`: a plain message about the PC's clock and antivirus web scanning.
- `work/` is the reference lab: original scripts, the golden output of the old scripts and the
  base roster backups. Read it, do not change it.
