# Maintaining

How to keep the updater current: what refreshes itself, how to refresh the data pack, what to
do for a new season, how to ship a new version, and where to look when a data source changes.
Background in [ARCHITECTURE.md](ARCHITECTURE.md), setup in [DEVELOPING.md](DEVELOPING.md).

## What stays current by itself

**NHL rosters.** Every update downloads today's rosters from NHL.com, so trades, call-ups and
signings are in the next roster a player builds. Nothing to do.

**Lines** (owner, 2026-11-09). The lines job on the file server (`tools/lines_job.py`, its container in `deploy/lines/`)
refreshes the published data pack's `lines` (every NHL team: announced lines, the rest from its last 5 games) and the
Extraliga's `club_lines` (newest match line-ups) every day at 10:00 UTC, and replaces the pack by itself when every guard
passes. Both this program and NHL 19 read that pack, so players get the lines at their next Update. The other clubs'
lines stay as the last maintainer's build left them. To check it: `archive/status.json` beside the job (result, teams
kept and why, problems) and `docker logs nhl-legacy-lines`. To stop it, roll a pack back or deploy new code:
`deploy/lines/README.md`. Background: docs/notes/lines-job.md. `tools/publish_packs.py` keeps every team's lines the
server has newer than the local pack (it writes them into the local pack first), so a publish never sends older lines.

Everything else comes from the **data pack** (`legacy_roster/data/datapack.json.gz`, committed)
and only changes when a maintainer refreshes it and puts it on the file server ("Shipping new data").

## Refreshing the data pack

```
python tools/build_datapack.py --refresh ratings              # the current ratings list (crawl, see below; private/)
python tools/build_datapack.py --refresh iihf                 # IIHF roster PDFs
python tools/build_datapack.py --refresh liiga,extraliga,shl,del,nl,norway   # European clubs
python tools/build_datapack.py --refresh ahl,chl              # AHL and the junior leagues (or ohl, qmjhl, whl)
python tools/build_datapack.py --refresh nhl                  # offline NHL snapshot
python tools/build_datapack.py --refresh lines                # every NHL team's lines, announced + its last 5 games (~2 min; the server's lines job does this daily: "Lines" above)
python tools/build_datapack.py --refresh extraliga_lines      # the Extraliga clubs' newest match line-ups (after club_lines; the job too)
python tools/build_datapack.py --refresh contracts --db <file>      # the 2026-27 contracts (private/, see below)
python tools/build_datapack.py --refresh ratings_full --db <file>   # the full current ratings, types, tendencies (same file)
python tools/build_datapack.py                                # rebuild from the caches only
python tools/capacity.py                                      # then: player records and pool room
```

Parts not refreshed are rebuilt from `tools/cache/` (git-ignored), so one part can be refreshed
without losing the others. The script prints each part's count and date.

**Guards.** Before writing, the script compares every part with the pack it replaces:
- a part that vanished, or lost more than 40 %, stops it;
- so do fewer than 300 fully rated players in the ratings list.

That is how a feed that changed its layout shows up. If the drop is real, run again with `--accept-drops`.

The script also leaves out players whose birth year cannot be right and prints them, for example a
feed typo that makes an AHL player 15.

| Part | Source | When | Notes |
|---|---|---|---|
| `ratings_list` | a public ratings list (`private/ratings_list.py`, private/NOTES.md) | about monthly in season | about one request per second; 40 minutes the first time, pages cached under `tools/cache/` |
| `iihf` | stats.iihf.com roster PDFs | once a year, after the World Championships | URLs in `tools/providers/iihf.py` for 20 countries (every national team the game has except Russia, banned since 2022); Belarus uses its last IIHF event (2021). The PDF name ends in its version (`_33_7_1`): take the highest, it lists everyone registered. Keys are ISO codes (DEU, CHE, LVA, DNK) |
| `liiga` | liiga.fi `/api/v2/players/info` | monthly in season, after the trade deadline | one request; season parameter derived from `SEASON` |
| `extraliga` | hokej.cz club roster pages | same | one page per club; the page must say the right season or the provider stops |
| `shl` | shl.se site API (`/api/sports-v2/…`, Sportality) | same | the season filter finds the season and the SHL series; one request per club and one per player (~380, about 3 minutes) |
| `norway` | ehl.no site API (same platform as the SHL) | same | only the clubs mapped to slots are fetched in detail |
| `del` | penny-del.org `/teams/<club>/kader` | same | one page per club; the page must link the current main round (`hauptrunde-2627`); ages only |
| `nl` | nationalleague.ch `/api/teams`, `/api/player/team/<id>` | same | 15 requests; no nationality, height, weight or hand |
| `ahl`, `ohl`, `qmjhl`, `whl` (pack key `chl`) | HockeyTech `lscluster.hockeytech.com/feed/` (`modulekit` views) | same | one request per club; public keys in `tools/providers/hockeytech.py` |
| `nhl` | NHL.com | with every release | only used when the player is offline; `nhl_logos` (ESPN's PNG logos for dark backgrounds, `500-dark`; the program derives the plain `500` link from it for the pictures with a white edge, and `build_photopack.py` packs both) is written with it |
| `nhl_last` | NHL.com statistics (`api.nhle.com/stats/rest/en/{skater,goalie}/bios`, last regular season) | with `nhl` (and after free agency settles in the summer) | 2 requests plus one per unsigned player (photo); decides who is retired and who is an unsigned free agent (`tools/providers/nhl_facts.py`). A new season: it takes the season before `SEASON` |
| `retired` | kept by hand in `tools/retired.json` (NHL.com marks no retirement: `isActive` is false for every unsigned player) | every build copies it; add names when players announce their retirement | unsigned players of last season aged 38+ retire without it (`builder.UNSIGNED_RETIRE_AGE`); list only the younger ones. Players on the list or over the age leave the free-agent list and their team unless NHL.com, a club league or a contract has them |
| `contracts` | a roster database the owner reads on their own PC (`private/contracts_db.py`, private/NOTES.md) | before a release, and when that database changes | no web. Only names, birthdate, position, team and the deal's numbers go into the pack; prints the cap hits' range and each team's 23 dearest deals (docs/notes/contracts.md) |
| `ratings_full` | the same database as `contracts` (`private/ratings_full.py`) | with `contracts` | no web. About 7,000 players in every league: names, birthdate, position, hand, height, weight, team, and the ratings, potential, player type and tendencies that mean the same on the PS3 (which fields and why: docs/notes/full-ratings.md). The guard stops it under 5,000 players. `ratings_list` stays: the owner's other project reads it |
| `drafts` | NHL.com draft lists (`api-web.nhle.com/v1/draft/picks/<year>/all`) | with `nhl`; once a year after the draft | one request per year since `FIRST_DRAFT` (2005), 22 today |
| league `extra` | the league's feed (same caches) | with the league | the clubs the game has no slot for, with their players (a player's own custom team of that name gets them) |
| league `former` | HockeyTech, last season's rosters (AHL, OHL, QMJHL, WHL) | with the league | players on no list now, with their photo (one more request per club) |
| Extraliga `photo` | hokej.cz player pages | with the league | about 400 pages the first time, remembered in `tools/cache/extraliga_photos.json` (delete it to look again) |
| club `logo` | the feed (HockeyTech, Liiga), else English Wikipedia | with the league | links remembered in `tools/cache/logos.json`; delete an entry to look it up again. Wikipedia throttles: a "429" line means that club has no logo in this pack; build again later and the cache fills in |

After a refresh: run the tests (they build with the bundled pack) and `tools/capacity.py`, then
ship it (next section).

## The picture packs (downloaded, not inside the exe)

Since 0.32.0 (owner, 2026-10-20) the program carries no pictures. Two packs live in `private/packs/` (never in git) and
on the program's file server; the program downloads them while "Photos, logos and team names" is on
(`legacy_roster/packs.py`). Without `private/` the three data pack parts `ratings_list`, `contracts` and `ratings_full`
keep the bundled pack's values (the script says so).

**The photo pack** (`private/packs/photos.zip`): after refreshing the data pack,

```
.venv\Scripts\python tools\build_photopack.py      # 4,300 pictures; first time about 15 minutes
```

- **What it does.** It keeps pictures whose links did not change, and downloads and draws only new
  ones (`--fresh` redoes everything).
- **What it prints.** The size (about 60–100 MB) and the failed links. A few failures are normal:
  dead links, or photos without a recognisable head.
- **Logo drawing.** When `images.logo` changes how logos look, raise `install.LOGO_DRAWING`: players
  who have the old pictures then get every logo drawn again once.
- **Players' PCs.** Pictures the pack lacks (players new since it was built) are downloaded by the
  program and kept in `%LOCALAPPDATA%\NHLLegacyRosterUpdater\art\pictures\`, so each is downloaded
  once.

**The look pack** (`private/packs/looks.zip`, about 80 MB): this season's jerseys and centre-ice logos for 214 teams
(517 jerseys, 179 centre-ice logos), a Select Jerseys picture of each kit (`m/<slot>_<role>.webp`) and since
2026-10-27 the number sheet of each home and away kit (`f/<slot>_<role>.webp`, 512 x 512 lossless; docs/notes/
jersey-numbers.md). It is made in `private/` (private/NOTES.md says how), with contact sheets of the kits to look at
before a release; the build lists the kits it left without their own number sheet (none in the 2026-10-27 build).
- **Players' PCs.** Installed with "Photos, logos and team names" (`pipeline.install_looks`); a new pack makes every look
  install again once (`looks.look_digest` covers it). A club whose league step was left out keeps its own look (the List
  of changes says so). Without the pack the Jerseys window says "This season's jerseys come with Photos, logos and team
  names" and teams keep the game's own jerseys.
- **Thirds are not used** (owner, 2026-10-18: home and away only). The pack still carries third kits (`third` in
  `lookpack.ROLES`); `looks.pack_versions` never places them. A later rebuild may drop them to save room.

**Putting them on the server** (only with the owner's go-ahead: it publishes them):

```
python tools/publish_packs.py <ssh-host>:<folder> --dry-run      # what would be sent
python tools/publish_packs.py <ssh-host>:<folder>                # every pack in private/packs, the data pack, then manifest.json
python tools/publish_packs.py <ssh-host>:<folder> --only ice,looks     # just these (the manifest keeps the others)
```

**The small packs** (0.76.0: `arenas`, `ice`, `masks`): made from the community's 26-27 Extras folder by
`private/build_extras.py "<folder>" --ice "<new centre ice folder>"` (`.venv\Scripts\python -I`, `LEGACY_ROSTER_DISC` = the EU
disc, read only). Since 0.78.0 `ice` is the owner's newer centre-ice set (`--ice`: the folder holding
`icesurface/centerlogo_<art>_cm.rpsgl`, art 0-29), each centre's encoded raster as it is; since 0.80.0 it has no row of its
own in the window: "Community centre ice" is its own switch beside "This season's centre ice" (`settings.ICE_ORDER`: the one switched on second lies on top). Run it again when a folder changes;
it prints what it took and what it left out. Arenas carry the sha1 of the disc's file: an NA or other game version whose
file differs is skipped in the player's List of changes, so compare the NA files first. Findings:
docs/notes/community-extras.md.

**The scoreboard pack** (`overlay`, test versions 0.78.0 / 0.80.0) is out of the program (owner, 2026-10-27): its code,
builder and packs are parked in `private/scoreboard/` (README.txt there). Its builder writes there, never into
`private/packs`, so `publish_packs.py` does not send it. The server's manifest still lists `overlay`; nothing reads it.

- It refuses when `tools/clean_check.py --server` finds a word in the data pack or the packs' `index.json` / file names,
  or when the data pack is not the format the program reads.
- Each pack goes up as `<name>-<sha12>.zip`, then the data pack, then `manifest.json` last (each via a temporary name and
  a rename), so a player never sees a manifest for files that are not there yet. The packs the new and the previous
  manifest name stay; older ones are removed.
- Players get a new pack at their next start (or when they switch the Photos row on); unchanged packs are not
  downloaded again.
- The host and folder are given on the command line only (private/NOTES.md): never in a tracked file. The server's
  layout and how to take it down: docs/notes/pack-hosting.md.
- **Git.** No zip is committed (`.gitignore`: `private/`, `legacy_roster/data/*.zip`); `build.ps1` / `build.sh` refuse
  to build with a zip in `legacy_roster/data/`.

## Shipping new data

Since 0.32.0 the data pack comes from the program's file server, next to the picture packs: `datasource.PACK_URL` is
`FILES_URL + 'datapack.json.gz'` (`LEGACY_ROSTER_FILES_URL` moves both, `LEGACY_ROSTER_PACK_URL` the data pack
alone, for testing). On each update the program tries that address (20 s timeout), keeps a valid download in its cache,
and uses whichever pack has the newest `generated` stamp: download, cache or bundled. New data means
`tools/publish_packs.py` (above); no new exe.

`load_pack()` skips a pack whose `format` is not `datasource.PACK_FORMAT` (2 since 0.32.0, when parts were renamed). So
when the pack's layout changes in a way older exes cannot read, raise `PACK_FORMAT` and the `format` written by
`build_datapack.py` together: older exes keep using their own pack and tell the player to update.

## New season checklist

1. `SEASON` in `tools/build_datapack.py`: the year the season starts.
2. When the ratings list moves to the new season: `GAME` in `private/ratings_list.py`, then `--refresh ratings`.
3. NHL changes: a relocated or renamed team keeps its slot; update `layout.API_TO_SLOT` (new
   NHL.com code) and `layout.NHL_TEAM_NAMES`. An expansion team needs a slot decision; there are
   no free NHL slots (ROADMAP.md).
4. **Promotions, relegations, relocations, expansion.** In `tools/club_slots.json`, put the new
   club in the slot of the club that went down or moved, and keep that slot's `art` (logos and
   jerseys are fixed per slot). The build stops with the feed's club list when a mapped club is
   missing, and prints the clubs that have no slot (`left_out`).
   - **`source` per feed:**
     - hokej.cz: the club's page path (`/klub/<name>/<id>`);
     - penny-del.org: the page name (`adler-mannheim`);
     - the others: the club's name in the feed.
   - **Done for 2026-27:**
     - SHL: Björklöven → Karlskrona's slot, Timrå → MODO's;
     - DEL: Frankfurt → Düsseldorf's, Bremerhaven → Hamburg's;
     - AHL: Hamilton → Bridgeport's;
     - WHL: Penticton has no slot.
5. `layout.NOT_ELIGIBLE`: players born in one country who represent another (they must not be
   picked for their birth country's team).
6. IIHF: new PDF URLs in `tools/providers/iihf.py` after the World Championships (the event number
   changes; try `IHM<event>0<IOC code>_33_<n>_<m>.pdf` for the highest `n` that exists).
   The cache keeps the old PDFs under the country's key: delete `tools/cache/iihf/` first.
7. Refresh every part of the data pack, run the tests and `tools/capacity.py`, release.
8. Every provider picks its season from `SEASON`. Check each part's printed count: an empty
   part usually means the league has not published the new season yet.

## Releasing a new version

1. Version: `__version__` in `legacy_roster/__init__.py` (shown in the window title, the
   header and the build output). 0.x until the in-game checks in ROADMAP.md have passed.
2. Data pack refreshed if due (above).
3. `python -m pytest -q` green with the base roster present (no unexpected skips).
4. `powershell -ExecutionPolicy Bypass -File packaging\build.ps1` (it refuses a zip in `legacy_roster\data` and any
   `tools\clean_check.py` hit). The window exe is about 26 MB. Since 0.85.0 there is no copy under the old name
   `NHLLegacyRosterUpdater.exe` (owner): copies of 0.80.0 and older get "Open the download page".
   The Linux program: "The Linux program" below.
5. **Smoke test** the exe (the command line from source, `python -m legacy_roster`):
   - `python -m legacy_roster list --rpcs3 <rpcs3.exe>`: lists the rosters, community rosters "ok";
   - `python -m legacy_roster list --rpcs3 C:\Windows`: "That is not RPCS3…", exit code 1;
   - start `dist\BluelineLegacy.exe`: the window appears within a few seconds with the
     Puck Peak logo, font and icon, and finds RPCS3 when it is running or was used before;
   - with a fresh `LOCALAPPDATA` (a temporary folder): the Photos row downloads by itself ("Downloading
     automatically... %", then "Ready"); `python -m legacy_roster packs status` lists the packs; a second start
     without network still has them;
   - `python tools\start_stress.py --exe dist\BluelineLegacy.exe --runs 30`: every start draws its first tab (0 BAD,
     no WebView2 process left behind); then each of `--fail ready-hang|ready-error|blank|render|js-type|engine|lost-file|lost-always|lost-stall --runs 1`
     must say what it expects (the tool checks start.log's lines; docs/notes/blank-window.md);
   - run one update into a **copy** of a savedata folder (`update --savedata <copy>`), or with
     `--dry-run`; with an EU roster in the copy, `--for both` must add an EU and an NA folder;
   - the game's own roster: a temporary folder with an empty `rpcs3.exe` and `config\games.yml`
     naming your disc image (`BLUS31540: "<image>"`), then `update --rpcs3 <that exe> --dry-run`:
     it starts from `disc:NA` and passes every check.
6. If the release changes what is written into the save: the project owner loads a new roster
   in the game (Roster Management, Team Management, lines, one game) before release.
7. Release notes for players: what is new, what to expect, known issues. Add the version to
   CHANGELOG.md (the release text is made from it) and keep the README's "What it updates" table
   in step.
8. Publish (only with the owner's go-ahead): commit, tag `vX.Y.Z`, push, then a GitHub Release
   with `BluelineLegacy.exe` and the same file as `PuckPeakLegacyUpdater.exe` (both made by `build.ps1`: 0.80.1 to 0.97.1 look only for the second name; before 0.98.0 only one exe since 0.85.0; 0.80.1 / 0.81.0 also carried `NHLLegacyRosterUpdater.exe`),
   `BluelineLegacy-<version>-linux.tar.gz` and `SHA256SUMS.txt` (made by `build.ps1` in `dist\`; add the
   tar.gz's line to it). The data pack and the
   picture packs go to the file server (`tools/publish_packs.py`), not into the release. **The exe's own update check
   (`app/selfupdate.py`) needs the exact asset name `BluelineLegacy.exe` (copies of 0.80.0 and older look for
   `NHLLegacyRosterUpdater.exe`, which releases since 0.85.0 no longer carry) and `SHA256SUMS.txt` (or GitHub's own `digest` of the exe), and a tag like `v0.11.0` (a draft or prerelease is ignored).
   Programs before 0.32.0 still download the data pack from `releases/latest/download/datapack.json.gz` and refuse
   format 2: leave that asset out.** There is no `gh` on the
   owner's PC: the release is made through GitHub's REST API with git's stored login (`git
   credential fill`; 0.6-0.8 did it that way). Pushing the tag also starts
   `.github/workflows/build.yml`, which only runs the tests on Linux and Windows (it attaches nothing since 0.80.1).

## Signing (SignPath)

The exe is not signed yet, so Windows SmartScreen warns (README "Good to know"). Plan (owner, 2026-11-01): SignPath's free
open-source programme (https://signpath.org/). Written in 0.92.0, **not run**: it needs a push (rule 6) and SignPath's approval.

1. **Apply** (the owner): the project is public, has an OSI licence (LICENSE) and a README; apply as a SignPath Foundation
   open-source project, then in SignPath create the project, an artifact configuration for `BluelineLegacy.exe`
   (a zip with the exe at its root) and a signing policy (e.g. `release-signing`).
2. **Repository settings** (GitHub > Settings > Secrets and variables > Actions): secret `SIGNPATH_API_TOKEN`; variables
   `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_POLICY_SLUG`.
3. **Run** `.github/workflows/windows-release.yml` (Actions tab, by hand). It builds the exe with `packaging/build.ps1`, uploads it,
   and, when the variables are set, has SignPath sign it and uploads `BluelineLegacy-signed` with a fresh
   `SHA256SUMS.txt` (signing changes the file, so the sums of `dist\` no longer match; the update check compares them).
   Without the variables it stops after the unsigned upload and says so.
4. The release then carries the signed exe from that artifact instead of the one built on the owner's PC; the release
   steps above (tests, smoke test, the Linux program) stay. When the first signed release is out, change README's
   SmartScreen line (a signed exe from a new publisher can still show a warning until it has a reputation).
5. `build.ps1 -Sign` signs a local build with a certificate of your own (`SIGN_PFX` + `SIGN_PFX_PASSWORD`, or
   `SIGN_THUMBPRINT`); it is skipped with a line when none is set.

## The Linux program

Built and checked in Docker boxes on any Linux machine with Docker (the owner's server; every image and container is
named `legacy-linux-*`, at most 2 cores and 2 GB each, no ports, no folders of the machine):

1. Pack the files git publishes: `git ls-files` (plus new files under `packaging/`) into a `.tgz`, and copy it and
   `packaging/linux/build_in_docker.sh` to the machine.
2. `bash build_in_docker.sh <source.tgz> <out>`: builds in `packaging/linux/Dockerfile` (Ubuntu 22.04, Python 3.12,
   `packaging/build.sh`: PyInstaller one folder, the window's web engine Qt WebEngine from PySide6 inside, a check that
   every library the program links to is inside or part of every Linux), then runs `packaging/linux_check.sh` in plain
   Ubuntu 24.04, Fedora and Arch boxes (`packaging/linux/check/`). Each must say PASS: the new window opened on a
   pretend screen, drew its page (`LEGACY_ROSTER_SMOKE`, `window/main.smoke`) and the screen is not blank, and `--help` runs. `<out>` gets
   `BluelineLegacy-<version>-linux.tar.gz` and `window-<system>.png`; look at the pictures.
3. Copy the tar.gz back, add its line to `SHA256SUMS.txt`, attach both to the release (step 8 above).

Why not GitHub: 0.80.0's Linux program came from there, needed the system's WebKitGTK, and opened the classic window
on players' PCs; nothing checked it. Why Qt and not GTK: a bundled WebKitGTK cannot start its own helper programs.
The system's own libraries (libstdc++, libgbm, X11, fontconfig, glib ...) are taken out of the folder after the build: the graphics driver loads into the program and needs the system's newer ones (with the box's copies inside, Qt got no OpenGL and the window was black). `savedata.clean_environment` keeps the program's own libraries away from RPCS3 (a Qt program), the file manager and
the browser.

## The game patch

- After any change to `gamepatch.py`'s stages: bump `TEAMS_VERSION`; run `python tools/audit_patch.py <EBOOT.ELF>`, which
  must report 0 problems (the decrypted EU EBOOT stays outside the repo); run the tests with `LEGACY_ROSTER_DISC` set to
  the EU disc image; then play a lab round (docs/GAME_PATCH.md). A patch that has not been played never goes to players.
- The patch covers 1.00 (EU, NA) and the game's update 1.01, which is one program for EU and NA. After a stage change, run
  `python tools/port_patch.py <1.00 ELF> <1.01 ELF> --write` (it writes `legacy_roster/patch101.py`), then audit the
  1.01 ELF too. To get the update and decrypt it, see docs/notes/update-101.md.
- `TEAMS_VERSION` changed, or NHL Legacy Native has a new version: build its patch file again and play it on a copy
  (`tools/native_patch/README.md`). With an old pack the window shows "Patch again" for ever; a port version the pack was not
  made for is refused, and its players stay at 30 teams until then.
- A new RPCS3 release: check that it still applies every entry (the log names each one with "Applied patch") and still
  knows `calloc`.
- A new season: the 32-team calendar comes from the data pack's `schedule` part like the 30-team one; the year entry moves
  2015 to 2026 and must move further for 2027-28 (`YEARS_LATER`, `YEAR_WINDOW`, `check_years`). Plan that with the owner.

## When a data source changes

| Source | Symptom | Fix in |
|---|---|---|
| NHL.com roster API | update fails at "NHL rosters", or `KeyError` in `flatten_nhl` | `datasource.fetch_nhl_teams`, `flatten_nhl` |
| NHL.com player search | injured/reassigned players treated as having left | `datasource.find_missing` (`NHL_SEARCH`) |
| the ratings list's site | `ratings: 0 players`, or few with full attributes | `private/ratings_list.py` (it reads the page text with regular expressions) |
| IIHF PDFs | download 404 or no players parsed | `tools/providers/iihf.py` (URLs), `iihf_pdf.py` (text extraction; needs Windows' Arial fonts) |
| liiga.fi | `liiga: 0 players` or missing fields | `tools/providers/liiga.py` (JSON field names) |
| hokej.cz | "expected three roster tables" or wrong season | `tools/providers/czech.py` (`parse_roster`), club paths in `club_slots.json` |
| shl.se / ehl.no | "no SHL regular season … in the site's filter", 404 on `sports-v2` | `tools/providers/sportality.py` (paths are in the site's main script under `SPORTS_v2`) |
| penny-del.org | "not for 2026-2027", 0 players | `tools/providers/penny_del.py` (`parse_roster`: tables after the words Stürmer / Verteidiger / Torhüter) |
| nationalleague.ch | 0 forwards or 0 players | `tools/providers/swiss.py` (`POSITION`: the feed says `forwarder`) |
| HockeyTech | HTTP 403/"invalid key", no regular season | `tools/providers/hockeytech.py` (`KEYS`: copy the new `key=` from the league site's requests) |
| RPCS3 | "That is not RPCS3" or saves not found for a valid install | `savedata._dev_hdd0` (`config\vfs.yml`), `savedata._active_user` (`GuiConfigs`) |
| A new community roster | "… is not a copy of … in this roster" or another layout refusal | `layout.check_base` (`MIRROR_NAMES`); then build it once in memory (as `tests/test_pipeline.py::community_style` does) and look at `verify`'s problems |
| Photo links (any league) | "N could not be downloaded" grows, or players keep old pictures | the provider's `photo` field (HockeyTech `player_image`, Sportality `portraitList`… `srcset`, Liiga `pictureUrl`, DEL roster row `<img>`, NHL.com `headshot`) |
| Logo links | a club shows its old logo with photos on | its `logo` in the pack: feed `_logos`, `tools/cache/logos.json` (Wikipedia), or set `logo` / `wiki` for the club in `club_slots.json` |
| A photo looks wrong (head too big, background left) | – | `legacy_roster/art/images.py` (`cut_out`, `head`, `PORTRAIT_SPOTS`); `tests/test_art.py` has a drawn test photo |

**When the build stops:**
- a provider raised an error: nothing is written;
- a club name is missing from a feed: it stops with the list of names the feed has;
- a part vanished or shrank sharply: the drop guard stops it (see "Refreshing the data pack").

In all three cases `build_datapack.py` stops before the pack is written.
