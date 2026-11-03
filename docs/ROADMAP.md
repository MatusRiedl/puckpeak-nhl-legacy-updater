# Status and roadmap

**State on 2026-11-02: 0.95.0 is built and committed locally, waiting for the owner's final check.** **State on 2026-11-01: version 0.92.0 is released, its data pack published**
(blank window, signing through SignPath, alternate jerseys, custom teams in the normal layout; what is still open: PLAN.md
top). The current state of everything is the "Current state"
section of [AGENTS.md](../AGENTS.md) and [CHANGELOG.md](../CHANGELOG.md); the sections below are older records and
checklists, kept for the open checks. Update this file when something here changes.

Older header (2026-10-05, version 0.8.0):

**Game patch (2026-10-13, lab, not released):** the year 2026 and 32 teams in Season / Be a GM work in the lab (patch 0.7,
round 10). Before a release: the All-Star game kept (stage J; the owner's call 2026-10-13), the draft for 32 (stage K), the
exe installing the patch with undo (Phase D), then the owner's rounds 11-14 (All-Star, draft and next season, Be a Pro, patch
off). Research afterwards, the owner's picks: 82 games, the 2026-27 salary cap, 3-on-3 overtime, the NA version. Details:
docs/GAME_PATCH.md.

0.8.0 answers the testers' feedback on 0.7.0 (owner's decisions below):
- **Free agents:** retired players go, last season's unsigned NHL players come (Reimer, Toews,
  Quick), created if the save lacks them. Rule: `builder.would_retire` (data pack `nhl_last`).
- **Real player data:** every player's real draft (`draft.py`, data pack `drafts`), NHL.com's
  height, weight, hand and birthplace for every NHL player, stricter name matching (Will Smith,
  the two Sebastian Ahos).
- **Logos:** the game's own sizes (they covered the record and spilled out of the calendar), and
  ESPN's dark-background logos (a white Tampa Bay bolt, Washington with white edges).
- **Goalie gear** in the new club's colours.
- **Your own team:** a custom team the player made, named after a club the game has no slot for
  (Jokerit, Ajoie, Penticton, Coachella Valley ...), gets that club's players.
- **Pictures not installed** are named in the List of changes; the Roster editor no longer calls
  every player of the game's own roster "new to the game".
- After the owner's own test: **prospects on real clubs** (`clubs._place_prospects`), juniors the
  list leaves out stay (`STAY_AGE`), **more photos** (Extraliga, last season's CHL/AHL, shaded
  backdrops cut out), **a window that keeps every step in view**, **macOS and Linux**, and **roster
  saves without RPCS3** (`savedata.SaveFolder`).

0.7.0 fixes two problems a tester had with 0.6.0: downloads from the NHL player search failed with
a certificate error (the exe now carries its own list of trusted certificates), and the window
crashed when files it unpacks at start had been removed (it now says so). Nothing new goes into
the save, so the in-game checks below are unchanged.

0.6.0 in one breath:
- **No roster needed:** the game's own roster, read from the player's disc, can be updated
  (`stock.py`).
- **NHL.com positions** for every NHL player, and wingers on their own side of the lines (Cole
  Smith is Chicago's third right wing).
- **Favourite-team logos:** the logos of the "Choose Your Favorite Team" screen are written too
  (`teamlogosreflection`).
- **One program with every picture inside.** Downloaded pictures are kept on the PC, and pictures
  that were there before are always kept.
- **Readable results:** one line per part in the window, and the list of changes as a page grouped
  by team.
- **The window:** flags for EU / NA, and smoother redraws (rosters read in the background, rows
  kept, fewer redraws).
- **Links given back:** player links of removed roster places are reused, so repeated updates no
  longer fill the link table.

0.5.0: EU and NA, the community's 2026-27 roster, every empty national team filled, custom team
names fixed.

## League checklist

Every league the game has, what the updater does with it, and where its data comes from. Slot
numbers and the base roster's contents are in ARCHITECTURE.md ("Team layout"); the club-to-slot
map is `tools/club_slots.json`.

| League | Slots | Status | Data source | Notes |
|---|---|---|---|---|
| NHL | 0–31 | **Done**, live on every update | NHL.com API | – |
| Player ratings | – | **Done** | the current ratings (data pack) | about 4,600 players of every league are rated; everyone else is estimated (`estimate.py`) |
| National teams | 133–153 | **Done**: squads kept current, every empty one filled (0.5.0: also squads a community roster emptied) | IIHF roster PDFs (20 countries) + NHL.com | A country that cannot dress 2 G + 18 skaters stays empty and is named in the summary |
| Liiga | 76–90 | **Done** (played in the game 2026-10-03) | liiga.fi feed | 17 clubs, 15 slots: Jokerit and Jukurit left out. Kiekko-Espoo in the Espoo Blues slot (77) |
| Extraliga | 105–118 | **Done** (played in the game 2026-10-03) | hokej.cz roster pages | Kladno in Chomutov's slot (107), České Budějovice in Zlín's (118) |
| SHL | 62–75 | **Experimental** | shl.se site API (Sportality) | 14 clubs, 14 slots. Björklöven in Karlskrona's slot (67), Timrå in MODO's (71) |
| DEL | 91–104 | **Experimental** | penny-del.org roster pages | 14 clubs, 14 slots. Frankfurt in Düsseldorf's (93), Bremerhaven in Hamburg's (94). Age only: new players get an approximate birthdate |
| National League | 119–130 | **Experimental** | nationalleague.ch app API | 14 clubs, 12 slots: Ajoie and Rapperswil-Jona left out. No nationality, height, weight or hand in the feed |
| Norway | 131–132 | **Experimental** | ehl.no site API (Sportality) | 9 clubs, 2 slots: Stavanger (131, was the USNTDP pool) and Vålerenga (132) |
| AHL | 32–61, 234, 235 | **Experimental** | HockeyTech (league site feed) | 32 clubs, 32 slots. Hamilton Hammers in Bridgeport's slot (35). NHL-contracted players get their parent club's rights (`ahlaffiliate`; Vegas cannot hold rights) |
| OHL / QMJHL / WHL | 154–213 | **Experimental** | HockeyTech | 20 / 18 / 23 clubs for 20 / 18 / 22 slots: Penticton left out. Last in line for player records (see capacity) |
| Top Prospects, Winter Classic, EASHL | 214–221 | Leave alone | – | Event teams |
| Custom | 222–251 | Managed | – | 222–233 mirror NHL teams (kept identical), 234/235 are AHL teams, 236–251 receive relocated pools |

HockeyTech public client keys, taken from the league websites and verified on 2026-10-03 (they can
change): AHL `50c2cd9b5e18e390`, OHL `2976319eb44abe94`, WHL `41b145a848f4bd67`, QMJHL (`lhjmq`)
`f322673b6bcae299`. They live in `tools/providers/hockeytech.py`.

## Waiting for the game

**Checks of 0.75.0 (owner, in the game):** (1) after an update with the new data pack, Arvidsson (Detroit) shows Sock Tuck None and Matthews None,
Ovechkin / Makar Full, in Customize > Edit Player > Customization and on the ice (differences on the ice are small: the boot top); (2) a choice made
in the Roster editor's Equipment window still wins after the next update; (3) a new player (Roster editor) starts with plain gear, not the last
holder's; (4) AHL arena names in the game's intro captions (Coachella Valley: Acrisure Arena, Henderson: Lee's Family Forum, the Barracuda: Tech CU
Arena, one renamed club); (5) the new data pack part `equipment` has to be on the server (`tools/publish_packs.py`, owner's go) before players get it.
Not done: models (stick, helmet, gloves, skates, goalie pads), shoulder pads, jersey tuck and visor of real players (no usable data); the visor
tint row is not greyed when the visor is "No visor" (the game does).

Only the project owner can run these. They decide when a part leaves `pipeline.EXPERIMENTAL`
(the window shows no mark any more; everything is on by default).

| Check | Status |
|---|---|
| NHL rebuild, exe end to end, Liiga + Extraliga, custom pool teams | **Passed** 2026-10-03 (rosters `2026-10-02 22:07`, `22:14 Europe`) |
| Renamed clubs through the text file (Utah, Seattle, Vegas, Timrå, Björklöven) | **Passed** 2026-10-04; custom team names did **not** show → fixed in 0.5.0, check again (below) |
| SHL, DEL, National League, Norway, AHL, CHL | Waiting: build a roster with every switch on and follow the check list below |
| 0.5.0: custom team names, photos and logos | **Passed** 2026-10-04 ("photos, logos and team names work across") |
| 0.5.0: Save for NA | **Passed** 2026-10-04: the roster loads and plays in the NA game, photos show |
| 0.5.0: the community's 2026-27 roster updated | **Passed** 2026-10-04: the refilled national teams are there |
| 0.6.0: favourite-team logos | Waiting: with "Photos, logos and team names" on, "Choose Your Favorite Team" (a new game profile) and the favourite team in the settings show Utah's logo, not the Coyotes' |
| 0.6.0: NHL.com positions | Waiting: Chicago has three right wings (Kane, Kantserov, Cole Smith); on the lines, left wings play left and right wings right |
| 0.6.0: the game's own roster | Waiting: `NHLLegacyRosterUpdater-cli stock-test --rpcs3 "<rpcs3.exe>"` (writes two LAB rosters into RPCS3: "LAB game roster as is" and "LAB game roster updated"). Load each: the roster loads; Team Management opens an NHL club, Seattle (in the Green / Red slot) and a Liiga club; one Play Now game; the free agents list opens. If possible, first save the game's own roster once in the game (a new profile, Roster Management > Save Roster) and send it: it can be compared byte for byte with what `stock.from_disc` makes |
| 0.8.0: free agents | Waiting: Be a GM > Free agents on a roster made from the game's own roster: no Datsyuk, Price or Rask; Reimer, Toews, Quick there; a new unsigned player opens and can be signed |
| 0.8.0: draft data | Waiting: a player card of Will Smith (2023, round 1, 4th, San Jose) and of a junior (his draft year, undrafted); Be a GM's draft still runs |
| 0.8.0: logo sizes | Waiting: Be a GM calendar (logos inside their cells), the team panel of "Next game" (the record readable under the logo), Tampa Bay and Washington visible |
| After 0.8.0: logos | Waiting: "Choose Your Favorite Team" and the plain / Dynasty logos of Tampa Bay, Toronto, Washington, Boston, Vancouver show their own colours (plain ESPN logo with the white edge, `LOGO_DRAWING` '#3'; the banner, watermark and calendar still use the dark variant) |
| After 0.8.0: Select Teams names | Waiting: Play Now > Select Teams shows Utah Mammoth, Seattle Kraken, Vegas Golden Knights (not "Arizona COYOTES", "Green ALL-STARS", "Black ALL-STARS") and the rebuilt clubs' names (Kladno, Timrå, Frankfurt, Hamilton, Belleville); Season's team list too; abbreviations on the scorebug (`NHLTeamName_Abbr3_X`) |
| After 0.8.0: delete / open folder | **Passed** (owner, 2026-10-06): the window's Delete (Recycle Bin) and Open folder next to each roster in step 2 |
| Round 3: logos and names installed | **Passed** (owner, 2026-10-06, after running the new exe with "Photos, logos and team names" on): Tampa Bay and Toronto logos good, Play Now > Select Teams shows Utah Mammoth, Seattle Kraken, Vegas Golden Knights. The 0.8.0 exe had never been replaced (`installed.json` `#2`): tell the owner to run the new exe and restart the game after every release that changes pictures or names |
| 0.10.2: testers' fixes | Waiting (owner, in the game): a roster saved after moving a goalie off Seattle; equipment lists (no blue gear: skates 100-109 gone; helmet 6 / 7 still fine; goalie pads 85-88 kept); type letters on the card match Edit Lines. **Open: the game's exact OVR** (docs/notes/overall.md: read the formula from the EBOOT, else a LAB roster with screenshots) |
| 0.10.0 fixes from testers (owner, in the game) | Waiting: (1) Frölunda's scoreboard says FHC (needs "Photos, logos and team names"; `loc.NAMES_VERSION` '#5'); (2) Utah jersey without the faint coyote; (3) Utah / Seattle / Vegas helmets in their colours with their logo (`builder.nhl_gear`, `looks.decal_file`); (4) Utah's centre ice without the coyote under the logo (`looks.ice_picture_file`); (5) top-left team logos centred (`LOGO_DRAWING` '#5'). Open: Seattle / Vegas home ice still Nashville's (docs/CALENDAR_AND_LOOK.md 2b); the helmet reflection map still shows Arizona's ice |
| Round 3: update in place | Waiting: step 4 "Update this roster" (default): update a roster, start the game, see which roster is loaded at boot with nothing loaded by hand (the log cannot say: candidates are the newest folder and `...00`); then "Save as a new roster"; the backup folder (`%LOCALAPPDATA%\NHLLegacyRosterUpdater\backups`) can be copied back; the Roster editor on a chosen roster, saved in place |
| Calendar 2026-27 (`cli calendar-test`) | Waiting (the owner tests it in a separate session: full hand-over in docs/CALENDAR_AND_LOOK.md). Facts: the schedule is in `nhlschedule` (+ a copy `favoriteteamschedule`), month/day/home/away only, no year (docs/FORMAT.md section 8); the real 2026-27 schedule is in the data pack (1,344 games, 84 per team, 29 Sep - 10 Apr). Owner: `calendar-test --rpcs3 <exe> --source file:<community SYS-DATA>` writes CAL 1 (30 teams, 1,180 games), CAL 2 (+ All-Star game 6 Feb), CAL 3 (32 teams, 80 games each), CAL 4 (CAL 1 with the draft years +11); for each: Season > Select Team > Calendar: month and YEAR named ("October 2015" before), weekdays, September, Anaheim's games (printed by the command; first: 4 Oct home vs Florida, 7 Oct home vs Edmonton, 9 Oct at Winnipeg, 10 Oct at Calgary), play and simulate a week, standings; CAL 3: do Seattle and Vegas play in Season mode (check the log for the crash at `0x00381c24`). Decides: which table the game reads, whether the year is in the roster, 30 vs 32 teams. Switched off by default (`pipeline.EXPERIMENTAL` 'schedule') |
| Jerseys and the ice (`cli rendering-test`) | Waiting (hand-over in docs/CALENDAR_AND_LOOK.md). Written: `art/rpsgl.py` (read and rewrite the game's 3D textures, byte-identical repack), `art/rendering.py`. Owner: close RPCS3, `rendering-test --rpcs3 <exe>`, Play Now with the Utah Mammoth at home (then away): blue jerseys instead of red (home and away, whichever style) and a magenta/yellow "UTAH TEST" circle at centre ice = loose `rendering` files work; then "Restore the game's own pictures". If they work, next: real Utah / Seattle / Vegas jerseys (palette and crest swap on the shared layout, `jersey_`/`pant`/`sock` + menu previews), centre-ice logos for slots 22, 30, 31 (1024x1024, transparent strip for the red line), then other teams' 2025-26 uniforms, arenas, banners, crowd props (later). The game's own roster gets Utah's/Seattle's/Vegas's arena names and colours (`builder.nhl_identity`, waiting) |
| 0.8.0: goalie gear | Waiting: a goalie who changed club (Play Now) wears the new club's colours on pads, blocker and glove |
| 0.8.0: your own team | Waiting: make a custom team "Jokerit" in the game, save the roster, update it: the team has Jokerit's players and still opens |
| Season mode crash (owner, 2026-10-04 and 2026-10-06) | **Fixed and passed** (owner, 2026-10-06: `season-test` rosters 1-4, the full update, play Season mode). Cause: the community roster names a removed player (Jonathan Drouin: `ulGe` row 225, `caBZ` row 2945, header word at 0x18) and our update made him a free agent; the game's player lookup of his old link returned nothing (`0x00381c24`). `builder.drop_removed_player` takes him off first, `verify.py` checks the header words (FORMAT.md section 3). Not the RPCS3 patch, not roster size, not Arizona/Utah. Still to play: updating a roster made by 0.8.0 again (its free agents are relinked, `Builder.relink_free_agents`). `cli season-test` stays for regressions; always start it from the community roster as downloaded (`--source file:<SYS-DATA>`), never from our own output |
| Draft test (`cli draft-test`) | Optional now: since 0.8.0 the update puts undrafted prospects on real clubs anyway (owner asked for the fix, 2026-10-05); the test still tells whether the draft also sees pools or free agents |
| 0.8.0: pictures | Waiting: Extraliga players and juniors no list has any more (Landon DuPont, Everett) show photos; studio photos on a shaded backdrop are cut out like the rest |
| 0.8.0: window | Waiting: after an update in a maximised window the rosters and every step stay visible (the logo folds away, the result scrolls) |
| 0.8.0: without RPCS3 | Waiting: the tester in CrossOver picks the Mac RPCS3's savedata folder (via Z:) and loads the new roster in the Mac RPCS3 |
| 0.8.0: macOS and Linux | Not tried on a real Mac or Linux PC: the GitHub workflow builds and tests there; a tester with a Mac or Linux should try the program |
| 0.8.0: prospects in the draft | Waiting: Be a GM's draft list (or scouting) shows undrafted prospects of the next draft, from junior and European clubs |
| Kaprizov's photo (tester, 0.7.0) | Open: shows on the owner's PC (EU and NA). Asked the tester which roster, the "Photos and logos" line and any "Skipped" lines; 0.8.0's List of changes names skipped pictures |
| League test (LAB, `cli league-test`) | Waiting. The owner chose (2026-10-04) to wait for it rather than put Coachella and Henderson into the Norway slots. Coachella and Henderson no longer wait for it: the owner moved them into the AHL on patch rosters (2026-10-19, stage Y, below) |
| This season's jerseys and centre ice, every league (look pack) | Lab round 31 (agent, 2026-10-17): a home game in every league (NHL, AHL, SHL, Liiga, DEL, Extraliga, NL, Norway, national, OHL, WHL); kits looked at on the ice for the NHL, AHL, SHL and DEL: right. Fixed on the way: style-0 pants / socks (a renamed slot kept the 2014 club's orange socks), the Select Jerseys picture (crest on a square), and the centre ice: the NHL and DEL show the arena's file, the national teams file 501, the rest their own, so the DEL clubs and national teams keep the game's own ice (`looks.own_ice`; the List of changes says so). QMJHL not played. Owner: look at the contact sheets (private/NOTES.md) |
| 0.20.0: current ratings (`'current ratings'`) | Lab round 32: the roster's numbers and type match the ratings for McDavid, Crosby, Makar, Vasilevskiy, Tömmernes, Friberg, Fagemo; Starting Lineups shows type and OVR (within 2 of the source's); one period played. Waiting: the full player cards, Season simulated two weeks. Not copied: potential, traits, growth (docs/notes/full-ratings.md) |
| 0.20.0: sharp centre ice | Lab round 32 (encoder only): still hatched at the soft edges. Now flattened onto the ice (every mip opaque or clear, `dds.flatten`). Waiting: Utah's home faceoff, close-up and slant (no hatch, no stair steps, no white rim); `LOOKS_DRAWING` '#6' redraws installed looks once (docs/notes/centre-ice-quality.md, lab-round-32.md) |
| 0.20.0: Select Jerseys from the look pack's pictures | Lab round 32: Pittsburgh, Toronto, Utah match the pack's menu pictures. Waiting: an AHL and a European club, the 3D Pittsburgh home jersey. Socks / pants that differ from this season's are listed for the owner |
| 0.20.0: line-ups after a position change | Lab round 32, data: Unpatch, then update with Dillon (NJD) and Spence (OTT) forced to LW: saved, 6 D / 2 G (`Builder.repair_lineups`, tests/test_lineups.py). Waiting: Edit Lines, Play Now and Season days on that roster |
| 0.20.0: Utah / Seattle / Vegas arenas on a community roster | Waiting: a Utah home game's intro says Delta Center, Salt Lake City (lab round 32 showed Arizona Arena, Glendale; `Builder.nhl_identity` now runs with the NHL step on every roster) |
| Away v AHL home in white | The game's own choice (round 31): an AHL club's "home" row is its light kit (also in this season's kits), so an NHL visitor and an AHL host both wear white unless the player picks another jersey. Left as the game has it |
| Loading hangs (RPCS3) | Not ours (round 31): a match now and then stops on "Loading" after the Lynx shaders, mostly SHL home games; also with the patch off, the game's own roster and no loose file at all. Restarting RPCS3 clears it. Worth a line in the README's help if players report it |
| Blank names in Select Teams | Built (2026-10-19, `loc.key_hash` uses the game's rule, `NAMES_VERSION` '#6'): 10 club slots carry an art code the game's text file has no `TEAMLINE1/2_<code>` lines for (AHL COLE, CLE, LAV, CHW, TUC, CLG, ABB; CHL BBD, NFR, WW; the codes come from the community roster); their lines now go under the hash the game asks for. Named in lab round 35 by a re-keyed file; waiting: the same through the program ("Photos, logos and team names") |

Check list for each new league (Customize > Save/Load/Delete > Load > Rosters > the new roster, then):

1. Team Management: open two clubs of the league. Real names, about 25 players, full lines, a
   captain and two alternates, numbers.
2. Play Now: one game between two clubs of the league.
3. AHL only: open an AHL player's card. His NHL organisation shows.
4. CUSTOM teams 236–251 (prospect pools) still open.
5. Free agents: the list opens. It is longer now: released club and pool players are there.

## Capacity (measured 2026-10-03 on ROSTER2526, `python tools/capacity.py`)

- **Player records.** The table cannot grow (the updater does not try; growing it would need an
  in-game test). New players take over records. Base: 1,253 blank "ZZ" records (C 278, LW 236,
  RW 235, D 378, G 126). On top of that come 1,555 reusable records of teamless players. Never
  reusable:
  - legends rated 84+;
  - NHL rights holders;
  - anyone estimated younger than 26 (`donors.real_birth_year` reads the draft year of records from the game's own years);
  - free agents;
  - second records of a person (national-team goalies).

  Skater records switch position when one position runs out (goalies cannot).
- **A full build** (every league) creates **2,678 players** and uses **every** record. Every club
  still dresses 20, for three reasons:
  - each league's core line-up is created before any depth;
  - records are held back for later leagues' line-ups;
  - short clubs are topped up from former players, the prospect pools and junior-age free agents.

  Skipped for lack of records: CHL 238 depth players, DEL 5, National League 3, AHL 2. They are listed in the report.
- **Prospect pools.** 952 pool players in 46 pools in the base. With every league on, real clubs
  absorb many of them. The 16 spare custom slots hold 640 (all used) and 73 become free agents
  (`pools.settle`, best prospects kept).
- **40 players per team** at most (roster entry ids are team × 40 + slot).

## Decisions taken (2026-10-03)

1. Liiga and Extraliga confirmed in the game: no longer experimental.
2. Pools: real clubs first; leftovers fill the 16 spare slots best first; overflow becomes free
   agents keeping NHL rights. Event slots stay untouched.
3. Junior leagues: full rosters reusing retired records; when records run out, every club still
   gets a legal 20 and depth players are skipped. The player table is not grown.
4. Photos and logos: built on the player's own PC with an undo button; later the same day the owner
   decided to ship a second exe with every picture inside (photo pack). Since 0.32.0 the pictures are downloaded instead
   (owner, 2026-10-20).

## Decisions taken (2026-10-04)

1. **EU and NA.** Rosters are tagged EU / NA; with both versions in RPCS3, "Save for" saves for EU,
   NA or both, and photos go into both games.
2. **Empty national teams are filled**, also those a community roster emptied (IIHF + NHL + the
   country's players in the save).
3. **No NEW tags; every league on by default.** `pipeline.EXPERIMENTAL` only lists what waits for
   the in-game check.
4. **Coachella Valley and Henderson** stay in custom slots 234/235. Putting them into the Norway slots was considered
   and set aside: they would be listed under Norway, and their NHL link still could not be set. Since 2026-10-19 (the
   owner's decision) a roster for the patched game gives them the AHL's league fields (stage Y, `gamepatch.league_fit`);
   the unpatched game keeps them under Custom.

## Decisions taken (2026-10-04, after the 0.5.0 checks)

1. **One program** with every picture inside (the plain exe without them is gone). New players'
   pictures are downloaded and kept on the PC.
2. **Positions follow NHL.com** for every NHL player (67 differed from the community roster, among
   them Cole Smith: RW, not LW).
3. **The game's own roster** can be started from, for players with no community roster. It gets
   **no custom copies** of NHL teams.
4. The window should not flicker or repaint slowly. The flags of the versions are pictures:
   Windows has no flag emoji.

## Decisions taken (2026-10-04, testers' feedback on 0.7.0)

1. **Retiring** follows NHL.com's last season: whoever played in the NHL last season stays, old free
   agents who did not and whom no league lists retire. Also for community rosters.
2. **Every unsigned NHL player** of last season is a free agent, created if the save lacks him (not
   only regulars), although records are scarce.
3. **A player's own custom team** named after a left-out club gets its players (it stays in the
   Custom group until the league test is played).
4. **Goalie gear** is painted in the new club's colours (not plain white).
5. **Real data for every player** (draft first), fetched into the data pack, never by the players'
   PCs.

## Decisions taken (2026-10-16, data of 2026-27)

Plan docs/plans/is-it-possible-to-jaunty-dongarra.md; notes docs/notes/contracts.md (sources: private/NOTES.md).

1. **This season's jerseys and centre-ice logos** for every team the look pack has, converted to the PS3 layout and put
   onto the player's own disc files. Since 0.32.0 the pack is downloaded, not inside the exe.
2. **Contracts** of 2026-27; only the numbers go into the data pack.
3. **Money:** real 2026-27 dollars on 32-team patch rosters, with a new patch entry for the 2026-27 cap ($104.0M, floor
   $76.9M, minimum $850k); rosters saved without the patch get the same contracts x 0.6865 (71.4 / 104.0).
4. **Roster editor:** the player type and the face become editable (tester requests). Lines and strategies are already
   built (tester request 3).
5. **Round 2 (evening):** the cap follows the real numbers each season (2026-27 $104.0M, 2027-28 $113.5M, 2028-29 the
   league's $127.5M estimate, then held); contract columns show the real seasons ("26-27"); the rookie maximum is the
   real amount; the 82 players under contract whom NHL.com leaves out stay with their team (agent's choice); this
   season's jerseys for every team the pack has, not only the NHL (AHL, CHL, European leagues, national teams).

## Decisions taken (2026-10-20, 0.32.0)

1. **Both picture packs leave the exe** and are downloaded from the program's file server under puckpeak.com while
   "Photos, logos and team names" is on; the data pack comes from there too.
2. **Neutral names** in everything the program ships and git publishes (`tools/clean_check.py`); source tools stay in
   `private/`. README: "Unofficial fan project, not affiliated with or endorsed by the game's makers or the league."
3. **The window:** the Photos row first and in gold; Patch / Unpatch in gold; important things highlighted.
4. **The server part stands alone** (its own folder and container), so it cannot affect the other services.

## Decisions taken (2026-10-20, picture fix and 0.35.0)

1. **Own pictures always go into the game** (also with Photos off, also on the Roster editor's Save); **picture-number
   clashes**: move ours, give theirs back; **a failed photo keeps the old picture**.
2. **Version 0.35.0** holds everything since 0.10.4 (0.20.0 to 0.32.0 were test builds); one CHANGELOG entry.
3. **Players without any photo** (silhouettes) stay as they are for now: "just a couple of people". What could fill
   them: docs/notes/missing-photos.md.

## Decisions taken (2026-10-20 night, 0.50.0: the window with tabs)

Plan docs/plans/listen-right-now-the-robust-walrus.md, notes docs/notes/nhl19-app-ui.md.
1. **One row of nine tabs** (Setup, Game patch, Update | Roster, Lines, Strategy, Jerseys & ice, Calendar, Front office),
   one team list for the six team tabs, Lines / Strategy / Jerseys as tabs. A clickable mockup first
   (`private/mockup/`, git-ignored); the owner approved it ("i love it").
2. **Calendar** = a month page plus the team's games. **Front office** = cap and contracts view, contract edits, and the
   player's own Season / Be a GM saves (read only).
3. **Version 0.50.0** holds everything since 0.10.4 and the new window, one commit and one release.

## Decisions taken (2026-10-22: contracts for every club, the AHL's real rosters, Henderson's own players)

Plan docs/plans/ok-let-me-know-soft-wilkes.md (2026-10-22 version), notes docs/notes/lab-round-42.md.
1. **All 32 AHL clubs' rosters come from the source database**; NHL.com's NHL rosters still win.
2. **A made-up starter deal** for every club player without a deal and without NHL rights (by league and overall,
   `contracts.starter_terms`); an unsigned draft pick stays unsigned.
3. **Vegas calls up from Henderson** through the game patch (0.23: six-bit player rights), not by keeping Henderson's
   players on Vegas's NHL roster.
4. **Free amounts outside NHL organisations**: $5,000 up to the NHL maximum, 1-8 years. The program is an editor for
   every club (Front office, the contract window, the player card), not only NHL / AHL teams.

## Open decisions for the owner

1. **Base roster credits and bundling.** Who made ROSTER2526 (for the README credits), and
   whether they allow bundling it. The bundling switch stays off until they agree.
2. **More room for players** (later): growing the player table by up to ~1,240 records would let the
   junior leagues keep their depth, but needs an in-game test first.

## Suggested order

**From 2026-11-01:** (1) what 0.92.0 left open: the blank window's real cause still needs a tester's start.log, signing
(SignPath application by the owner, then `.github/workflows/windows-release.yml`, never run), alternate jerseys not played on
the patched game nor with the thirds' number sheets; (2) the rest of docs/notes/backlog-2026-11-01.md.
The list below is the order of 2026-10.

1. In-game checks (above): the 0.6.0 checks (favourite-team logos, positions, the game's own
   roster), then the new leagues; then remove them from `pipeline.EXPERIMENTAL`.
2. The owner's check of photos and logos (below), the Roster editor and the league test.
3. Season study, experiment C1 ([SEASON_PLAN.md](SEASON_PLAN.md)). Then, with the owner's go-ahead,
   the `lab` command for C2–C4 and the schedule step.
4. Decide whether ages move to − 1911 for 2026-27 (SEASON_PLAN.md: today every player is one year
   too young in the game).

### Phase B (photos, logos, names): state

- **Done.**
  - The art format is decoded and can be written: `legacy_roster/art/` reads the player's own disc
    and builds new art files from it with only the picture swapped (FORMAT.md section 7). Tests in
    `tests/test_art.py`.
  - `tools/names_report.py`: after a full update, only NHL slots 22/30/31 keep old names.
  - **Art test passed in the game (2026-10-03):** all four pictures showed (results in FORMAT.md
    section 7).
  - **Photos and logos (experimental):** a switch in the window (`--photos` on the command line)
    and "Restore the game's own pictures" (`photos remove`). Built on the player's PC, or taken from
    the photo pack inside the exe. Since 0.5.0 written into the EU and the NA game when the roster is
    saved for both. Details in ARCHITECTURE.md ("Photos and logos").
- **Passed in the game (2026-10-04):** photos, logos and team names, in the EU and the NA game.
- **0.6.0:** the reflection logos of the favourite-team screens (`r<artid>.big`, 256 x 512, NHL
  slots 0-31 only) are written too; waiting for the check above.
- **Names (built 2026-10-03).** With "Photos, logos and team names" on, the game's text files
  (`art/loc.py`, FORMAT.md section 7: Huffman-compressed strings, decoded and rebuilt byte for byte)
  get every rebuilt club's name, city, nickname and abbreviation:
  - Utah, Seattle and Vegas instead of Arizona, Green and Black: **shown in the game** (2026-10-04),
    as were Timrå and Björklöven;
  - the custom teams (Coachella Valley, Henderson, the prospect pools): **not shown** in 0.4.0. Fixed
    in 0.5.0 (keys in the game's style, added keys keep their case); waiting for the check above.

  The prospect pools also get logos of their own: their NHL team's for a "System" pool, a badge with
  the year for a draft class.
- **Not covered:** National League (its feed has no photos) and Extraliga players (hokej.cz has none
  in the roster pages); their club logos are covered.
- **Photo quality (trial on 255 real pictures, 2026-10-03):** NHL, SHL, Liiga and DEL photos are
  cut-outs and look like the game's own. AHL/CHL studio photos on plain backdrops are cut out. Those
  on mottled backdrops are shown in a soft oval instead (`images.prepare`). Norway's photos are
  waist-up shots on a spotlit backdrop and come out smaller. About 0.4 % fail to download and are
  skipped.

### League test (the owner runs this once)

Can a custom team play in a real league? The NHL's Seattle and Vegas use the NHL's own All-Star
slots, but no other league has spare slots, so the only way is to change a custom slot's league
fields. That is untested, and `verify` forbids it everywhere except in this test.

1. With RPCS3 closed or open (only a new roster save is written):
   `NHLLegacyRosterUpdater-cli league-test --rpcs3 "<rpcs3.exe>" --source <a 0.4 roster>`
2. In the game, load "LAB custom teams in leagues":

   | Team | Slot | Should now be in |
   |---|---|---|
   | Coachella Valley, Henderson | 234, 235 | AHL |
   | Jokerit | 250 | Liiga |
   | HC Ajoie | 249 | National League |
   | Penticton Vees | 248 | WHL |

   Each one should be listed there, its roster should open, and one Play Now game against a club of
   that league should work. Also note whether they still show under the custom teams.
3. Report: shown / not shown / crash. Names may be blank in this test (the text file is not written).
4. If everything passes, the league steps can put Jokerit, Jukurit, Ajoie, Rapperswil-Jona,
   Penticton, Coachella and Henderson into custom slots moved into their leagues. Those slots come
   from the 16 spare ones that hold prospect pools today.

### Draft test (the owner runs this once)

Where must an undrafted prospect be for Be a GM's draft to see him? The game's own roster keeps its future
draft classes on junior and European clubs with their draft year and round 0; the community roster
keeps them in "Prospects" pools, which the update moves to custom teams, and the owner saw them
missing from the draft.

1. With a roster made by 0.8.0 or newer:
   `NHLLegacyRosterUpdater-cli draft-test --rpcs3 "<rpcs3.exe>" [--source <that roster>]`
   It saves "LAB draft test" and prints twelve names, two per place (also in
   `%LOCALAPPDATA%\NHLLegacyRosterUpdater\reports\draft_test.txt`): left on the custom pool team,
   free agent, on a Top Prospects team, on a WHL club, on a WHL club without a draft year, on a Liiga
   club.
2. In the game load it, start Be a GM and open the list of draft prospects (scouting or the draft;
   if there is none before the draft, simulate to it).
3. Report which names are in the list. The update then puts every undrafted prospect where the draft
   sees him.

### Art test (done 2026-10-03; kept for reference)

1. Close RPCS3. Make a 0.3.0 roster first (it has Kladno in Extraliga slot 107).
2. In a command window in the folder with the exe:
   `NHLLegacyRosterUpdater-cli art-test install --rpcs3 "<path to rpcs3.exe>"`
   This writes 13 test pictures into RPCS3's game folder (`dev_hdd0\game\BLES02153\USRDIR\fe\...`),
   backs up anything it replaces, and saves a roster "LAB art test".
3. Start the game, *Customize > Save/Load/Delete > Load > Rosters > "LAB art test"*, then look:

   | Test | Where to look | Picture |
   |---|---|---|
   | 1 | Edmonton Oilers, Connor McDavid's player card | red square with "1" instead of his photo |
   | 2 | San Jose Sharks, Macklin Celebrini's card | green "2" (a new portrait id the disc does not use) |
   | 3 | Montreal Canadiens, Ivan Demidov's card | yellow "3" (a new id above the disc's range) |
   | 4 | Extraliga, Kladno (team select, Team Management) | blue "4" instead of the logo |
   | names | NHL team select: Utah, Seattle, Vegas | do the names show (not "Arizona Coyotes", "Green / Red", "Black / Blue")? |

   For each test, report: shown, not shown (the old picture or a silhouette), or crash.
4. Close the game, then: `NHLLegacyRosterUpdater-cli art-test remove`. Every file goes back as it
   was. Delete the "LAB art test" roster in the game if you like.

What each answer means:
- **1 and 4 show:** loose files override the disc, and the file format is right.
- **2 shows:** new portraits can use unused ids.
- **3 shows:** ids above the disc's range work too; the file was written to two candidate folders.
- **Names show:** the save's names are used for NHL slots too.
- **Something does not show:** the next step is to ask the modder (sportshacker) how the community's
  portrait pack is laid out (its players use ids 12,402–13,826).

## Known limitations

- New players get a generic 3D face and no commentary name (no audio can be added). With "Photos and
  logos" on they get a menu photo when their league publishes one.
- Team names in the menus come from the game's own text, not the save: they show only with
  "Photos, logos and team names" on (see Phase B), and the text file is the same for every roster
  of that game version.
- The game's own roster (0.6.0): records for new players are limited to what the community roster
  shows the game can read (6,745 players). 2014's players of 30 and older who are on no team any
  more retire to make room. Their records are reused: they leave the game.
- A player whose edit (Roster editor) was made before 0.6.0 and whose birthdate the NHL step now
  corrects to NHL.com's (players the save had with another birthdate) is no longer found by that
  edit: edit him once more.
- Club ratings are estimates; DEL newcomers have approximate birthdates; National League newcomers
  are listed as Swiss.
- Some junior depth players are skipped when player records run out (all leagues on).
- The NHL has 32 slots: an expansion team cannot be added (hard limit).
- The team in slot 31 (Vegas) cannot hold player rights on a roster for the unpatched game: `proteam` is 5 bits.
  Henderson's NHL contracts carry no rights there. A roster for the game patch gives it 6 bits (patch 0.23, lab round 42):
  Henderson's players hold Vegas's rights as every farm club's hold its parent's.
- **The game lists at most 10 roster saves** (found 2026-10-14 in the lab: `cellSaveDataListLoad2` with
  `dirListMax=10`; RPCS3 hands it the first 10 folders by name, `...0200`-`...0209`). A roster saved as new in
  `...0210` or later never shows in the game's Load list. **Handled (2026-10-16, owner's wish):** a new roster takes the
  lowest free number 01-09, none is made when a version has 10 (`savedata.RosterFull`), step 2 counts "N of 10" and marks
  rows the game does not show. Still to see in the lab: with a gap below 10, does a `...0210` folder show (the "first 10
  by name" rule).
- The exe is unsigned (SmartScreen warns) and Windows-only.
- New data reaches players only with a new exe until `PACK_URL` is set.

## Left as they are until somebody complains (owner, 2026-10-18)

- **The jersey hem of this season's kits** (Letang's jersey looked tucked oddly): `jerseytuck` is 0 for every player,
  so it is the converted hem, not a tuck. The pack's maker (`private/`) maps the source hem (x 290-780) onto the PS3's
  (x 232-818); the corner squares are a flat median colour. A fix would warp the hem rows on their own.
- **The NHL All-Star teams** (Seattle and Vegas took their slots 30 / 31): nothing in the game needs them. Season's
  All-Star game uses EASHL 220 / 221 on patch rosters (`gamepatch.ALL_STAR_RINK`). The custom slots 236-251 are empty and
  could hold them.

## Ideas (not planned yet)

- Each DEL club's own centre ice: a game-patch entry can do it, and the 14 pictures are already in the look pack. Left out by the
  owner on 2026-11-01 ("not important"). The six words are in docs/notes/lab-round-58.md; they have never been played.
- Grow the player table (needs an in-game test) so junior depth is not skipped.
- Photos for players who show a silhouette: the National League's own headshots and NHL.com's (by name and birthdate)
  would give about 350 of the 1,373 one (docs/notes/missing-photos.md; owner 2026-10-20: not now).
- Real nationality for National League players (the federation's site may have it).
- Tell the player in the window when a newer version is released.
- Build the data pack on a schedule (GitHub Actions) and publish it to `PACK_URL`.
- Finer choices: one league only, ratings only, a single team.
- Show the list of changes inside the window (today it opens as a page in the browser).
- Community corrections: a small JSON of manual fixes (preferred number, position, a feed's typo
  like a wrong birth year) applied after the feeds.
- Linux and Steam Deck: RPCS3's folders there (`~/.config/rpcs3`), a build per system.
- The window in other languages (French, German, Swedish, Finnish, Czech).
- **Done in 0.95.0 (docs/notes/native-port.md):** the backlog entry below, and the game patch on the port after all
  (`tools/native_patch/`, GAME_PATCH.md section 8), and online on the port (in step with RPCS3 at `SPU XFloat Accuracy:
  Accurate`, docs/notes/native-patch.md "Every pairing"; still to see: a match's normal end, a second CPU kind, the port's overlay,
  the public server). **Open, the owner's call:** on the game's own
  roster the unpatched game cannot list slots 234, 235 and 251 (lab round 59); moving those teams to low slots would.
- **Backlog (owner, 2026-10-29: not a priority): the native PC port of the game** (US 1.01, a Windows program made by
  static recompilation). Setup would ask "Which NHL Legacy?" RPCS3 / Native; Native keeps its saves in the same
  savedata folders as RPCS3 and reads loose files from its own mods (`mods/<name>/USRDIR`), so rosters, the editor,
  careers and pictures (as a "Puck Peak" mod) can work; the game patch almost certainly cannot (its code is already
  translated into the program); no online play. Probe, folder map and the planned steps: docs/notes/native-port.md.


## Checks after the tester fixes (2026-10-11)
- Select Teams: cycle every league (also with the game in Czech) after updating with "Photos, logos and team names".
- Roster editor: change a player's ratings a lot, save as new, see whether the game's OVR changes (if not, write `FUWe`).
- First start with no saved roster: pick the game, update from the game's own roster, save lands in ...01.

## Checks of 0.21.0 (2026-10-18; in the lab first, lab round 33)
Lab round 33 (2026-10-18, docs/notes/lab-round-33.md) played most of them; the owner's own check still decides
`pipeline.EXPERIMENTAL`.
- Boot with "No pop ups at start": no boxes before the main menu. **Passed** (four boots).
- Main menu with "Photos, logos and team names": no View Player Hub, Leaderboards, Lobby (COMMUNITY); HUT still
  there; every other entry opens. **Passed**: COMMUNITY holds only My Highlights; PLAY, CUSTOMIZE, LIVE THE LIFE, NHL 94
  open. The loose `fe/ion/game/menus/mainmenuitems.big` is read before boot.big (docs/notes/menus.md).
- The game's old offline news panel and the tuner-set notices say "Puck Peak" / "www.puckpeak.com"; the community server's news unchanged.
  **Passed in English** (menu and loading screen; once HUT reaches the community server the panel shows the community server's news). Czech and
  the tuner-set notice not seen.
- Utah: black helmets and gloves (no Arizona red), sticks in team colours. **Passed** (white / grey sticks, the red is
  only Bauer's print). Seattle navy: **passed**. Philadelphia, Washington in their own colours: **passed**.
  **Vegas: steel grey helmets** home and away, as the real team's usual helmet (gold is their alternate; notes
  equipment.md).
- Also passed: Utah's flattened centre ice (a clean ring), Select Jerseys of Abbotsford and Björklöven, the 3D
  Pittsburgh jersey, player cards (McDavid, Crosby, Makar, Silovs, Wallmark).
- Not played: Season for two weeks (it would write the lab's autosaves), Czech, the unpatched path in the game (the
  lab's own "(test)" patch entries come back with `game-patch remove`, so a normal roster reads "damaged" there).
- Face of a player: the head pictures match the heads the game puts on the player. Not checked yet.
- **Loading hangs** (two in round 33) were RPCS3's own: Resolution Scale above 100 % with "Disable Blit Engine
  Upscaling" off. Ticked in the lab's EU config: four games in a row loaded in about 6 s.

## Checks of round 47 (2026-10-23; my pro in the game, running Be a Pro careers, no Press Start)
Notes docs/notes/lab-round-47.md, be-a-pro-save.md, press-start.md. Plan: top section of
docs/plans/another-context-window-is-sorted-liskov.md.
- **Built, tested on copies:** My pro's states read from the roster as saved, the restart gap closed, the pro's team
  NHL / CHL only, the close question; `careersave.py` reads and rebuilds every Be a Pro copy byte for byte (the lab's,
  round 47's game-written ones), `verify.career_problems`, `savedata.update_career` (backup first), the window's "Be a
  Pro careers" view (name with the Load Pro label, ratings 40-99, XP to spend = earned - spent); `art/pressstart.py`,
  on with "Skip the intro" (`patchinstall.NO_PRESS`).
- **Played (lab 47, agent):** 47d: with the quick boot the game opens on the main menu with no press (profile and roster
  autoload, pad 1, Play Now, a Be a Pro and a Season started, saved and loaded, five minutes idle); with the file removed
  Press Start is back. 47a: a pro with 98 everywhere is "99 Overall" under Overall 90-99. 47b: a career saved after
  spending XP and after a game, six copies with one change each (name, XP, ratings ...): all load, play, save and
  reload.
- **Found (47a): the roster the game loads at boot** is the oldest one written since the last boot (the game writes its
  settings save `1300` right after every boot; it loads the roster just above it in the newest-first list). One roster
  written between two boots boots; two written (an update and the editor's Save into another roster), the older one.
  Round 41's open point. **Owner's call:** leave it (players load their roster through Customize > Save/Load/Delete >
  Load > Rosters, as the window says), or let the program set the time of the folder it just wrote so that it is the one
  that boots (only its own folder; no other save touched).
- **Not tried:** Be a GM and online (the community server) with no Press Start; the NA disc (same file); a goalie career's ratings
  (not editable yet).
- **Played by the agent (47c, the built exes):** the window edited a lab career (name, XP, Passing; the backup equals
  the career before, byte for byte); `cli game-patch install --skip-intro --no-login` booted with no key pressed; Load
  Pro listed the new label, Player Growth showed the XP and Passing, the game made the Overall 75 from them; a game
  played into the first intermission; Unpatch removed the press files. **Not played:** the game's own save and reload
  of the edited career (47b did that on copies), the career unpatched, a second edit.
- **To check (owner):** after the next build, save your pro to the roster (the line turns from gold to "in the game"),
  pick him in Be a NHL Pro; change a career's XP or a rating in "Be a Pro careers" with RPCS3 closed, then Load Pro;
  Patch with "Skip the intro" and boot: the main menu with no Press Start.

## Checks of round 46 (2026-10-23; calendars of every league, Coachella's jersey, the RPCS3 path, my pro)
Notes docs/notes/lab-round-46.md, docs/notes/league-calendars.md. Plan: top section of
docs/plans/another-context-window-is-sorted-liskov.md.
- **Played:** Season mode's League Type offers all ten leagues with a table and plays the roster's own table (a swapped
  DEL row showed). Coachella with `jerseystyle` 1: navy with stripes (0 gave a plain jersey). Centre ice: the crest
  showed in every game (from `czlogo/logoct_72_*`). The owner's pro (Anaheim, all 88) is listed under Overall 80-89 in
  Be a NHL Pro; his career starts, saves and shows his created face.
- **Played through the built exe (46c):** Patch + update, then an SHL and an OHL Season: every September / October game
  of the user's club equals the roster's 2026-27 rows (day, opponent, home / away). Unpatch + update, then an AHL Season
  on the unpatched game (30 farm clubs): the same. `'league calendars'` left EXPERIMENTAL. Not played one by one: Liiga,
  Extraliga, National League, QMJHL, WHL (the same writer and the same two id widths).
- **To check (owner):** your roster after its next update: Coachella in navy at home, the crest on centre ice (send a
  picture if the ring is still empty); a Season of a European or CHL league opening on the real date; Setup keeps your
  RPCS3 path.

## Checks of round 45 (2026-10-22; the Draft & Pro tab, created looks, the main-menu news; patch 0.24)
Notes docs/notes/lab-round-45.md. Played by the agent in the lab, made through the window's own controllers.
- **Played:** a random class of 16 and two hand-made prospects (with created looks) in a new Be a GM's 2027 pool with
  the potentials the window gave; every look on Edit Players as set; my pro (Seattle) with his own face in a new Be a GM
  (after the fix: `builder.own_links`, `faces.link_problems`). The patch's news entry boots and the panel shows the
  gg.puckpeak.com line.
- **To check (owner):** the news panel while signed in online (the community server): Puck Peak's line, not the server's news. A
  created look in a running Be a Pro career (my pro picked in Be a Pro, a game played). The career start may move my pro
  to another team of the organisation (Corvin went to Coachella Valley): fine, or should the window warn?

## Checks of round 44 (2026-10-22; draft classes and Be a Pro, plan docs/plans/another-context-window-is-sorted-liskov.md)
Notes docs/notes/lab-round-44.md. Played by the agent in the lab with a hand-made LAB roster (not through the window yet).
- **Played:** made-up juniors on OHL and Liiga clubs are in a new Be a GM's 2027 pool and drafted by potential (a tier-1
  player went 2nd overall); AHL and teamless players are not pooled; the game fits potential into a band per growth tier
  (`draftclass.TIER_BANDS`). Be a NHL Pro lists NHL roster players, Be a CHL Pro the juniors.
- **Bug, not fixed:** Be a CHL Pro crashes in the patched game, with an undrafted junior and (lab round 59) a drafted one when
  the career has 128 team keys (GAME_PATCH.md section 6). Until
  it is fixed, a made-up pro in the patched game should be on an NHL club or a drafted junior.
- **Built (engine only, `'draft classes'` / `'new player records'` experimental):** `draftclass.py`, records held for
  new players (`edits.records_needed`, `Builder.hold_records`), `verify` checks the class. Not played: the second draft
  (June 2028), the face table, commentary names, the built exe.

## Checks of round 42 (2026-10-22; contracts for every club, the AHL's real rosters, patch 0.23; in 0.50.0)
Plan docs/plans/ok-let-me-know-soft-wilkes.md, notes docs/notes/lab-round-42.md. Played by the agent in the lab.
- **Owner:** Patch again (the Game patch tab says "patch again": 0.23; a 32-team roster made before is marked "made
  for another version of the game patch": update it), then in the game: Team Rosters for Coachella Valley and
  Henderson (the real AHL lists, a deal for everyone), an Extraliga club (Kladno: starter deals), a contract edited in
  Front office for a European or AHL-only player; a new Be a GM with Vegas: In the System lists Henderson.
- **Played in the lab:** six-bit rights load; Henderson In the System, a call-up / send-down swap; a season, the June
  2027 draft (32 teams), re-signing and free agency to 31 July 2027 with no crash and ordinary signings.
- **Through the built exe (round 43, docs/notes/lab-round-43.md):** Patch 0.23 + update in place, Team Rosters
  (Extraliga starter deals, Kempný's and McLain's edited deals, Coachella / Henderson with every deal, Vegas), Play Now
  Utah at Coachella; Unpatch + update: the unpatched game loads it, the same deals at the $71.4M scale, Coachella /
  Henderson under Custom; a second run "Already up to date". Found: a hand-copied save folder keeps its original's
  `SAVEDATA_DIRECTORY` (fixed in `update_in_place`), and the load path the program told players was wrong (fixed).
- **Open:** what the game does with European / AHL-only deals when they end (after 2027-28).

## Checks of 0.51.1 (2026-10-24; real captains, docs/notes/captains.md)
- **Real captains** (`'real captains'` experimental): update a roster with the NHL, AHL and Extraliga steps, then in the
  game: Winnipeg's C on Adam Lowry (Team Rosters / Edit Lines > Captains), an AHL club's C (Abbotsford: Wouters), an
  Extraliga club's C (Sparta), one SHL or DEL club, and a national team. A Season game with Winnipeg shows the C on the
  jersey. A team with three A and no C (a captain who left) plays without trouble.
- **"Saved" with a failure after it**: only by hand (a missing pictures folder); the tests cover it.

## Checks of 0.50.4 (2026-10-24; real lines, the AHL from the live feed, Coachella / Henderson as art 900 / 901)
- **Real lines** (`'real lines'` experimental; docs/notes/lines-from-games.md): update a roster with the NHL step, open
  Edit Lines for Edmonton (McDavid's real line, the power play units) and a team that traded lately; a player who left
  keeps the rating's choice. Lines saved in the program still win.
- **AHL from the feed:** Iowa holds Ben Dexheimer; every AHL club dresses; capacity numbers in PLAN.md.
- **Art 900 / 901** (`'club art 900'` experimental, patched game only): Select Teams (names, crests), Select Jerseys
  (home white with the trim colour, away in the main colour), a home game each (jersey, pants, socks, helmet logo, centre
  ice with the crest), a Be a GM with Vegas (Henderson), Unpatch + update (back to Custom, 20073 / 20081). Known: banner,
  puck, goalie helmet and name sheets are Charlotte's / Utica's; the Team kit window (NDEo) shows nothing for them.

## Checks of round 41 (2026-10-21; contract amounts, Roster Management's AHL, UFA / RFA; in 0.50.0)
Plan docs/plans/ok-let-me-know-soft-wilkes.md, notes docs/notes/lab-round-41.md. Played by the agent in the lab.
- **Owner:** Patch again (the Game patch tab says "patch again": 0.22), update the 32-team roster, then in the game:
  Team Rosters (Vegas) shows an amount for Eichel and Hanifin; Roster Management's AHL lists Coachella Valley and
  Henderson; a new Be a GM's Contract Status shows UFA for veterans after their deal, RFA for young players.
- **Open:** after an update in place the lab game booted another roster (0206) at start, not the updated one (0209);
  load it by hand (Customize > Save/Load/Delete > Load > Rosters). Which roster the game loads at boot is still unknown
  (Roster Management's "Set default rosters" not explored).
- **Owner's choice:** four teams start over the $104.0M cap with the real deals (Vegas $112.26M, Florida, NY Rangers,
  Dallas), so every new Be a GM asks "Salary Cap On?" ("Yes" trims their salaries a little). Henderson's line-up is
  topped up with the best free agents (Sewell, Toews, Mrazek).
- **Through the built exe (agent, lab):** Unpatch + update (turned back): the unpatched game loads it, Vegas without
  N/A, the normal money scale right; Patch (0.22) + update: Roster Management's AHL lists Coachella Valley and Henderson
  with their rosters.
- Latent, not seen: a stock roster turned back for the unpatched game keeps slots 234 / 235 switched on.
- **Known, not new:** in the unpatched game, Roster Management's CUSTOM list says "Not Available" on a roster made from
  the game's own (its walk counts 224 switched-on teams and stops before 234 / 235; the community roster has 236 on and
  shows them). Only the patch's walk skips the gaps.

## Checks of 0.50.0 (2026-10-20 night; the window with tabs, Calendar, Front office, contract edits, My season)
Plan docs/plans/listen-right-now-the-robust-walrus.md. Experimental: `'contract edits'`. Nothing else new goes into the save.
- Every tab at 100 / 150 / 200 % and on a 768-line screen; the team list keeps the picked team across the six team
  tabs; Lines / Strategy changes not applied stay with their team; Jerseys & ice loads only while it shows.
- Calendar: October 2026 starts on Monday 28 September; a team's games are the roster calendar's (76-80 on a 30-team roster, 84 on a patch roster); a farm club
  shows the AHL on a patch roster, a note on a normal one; the All-Star row is named, not counted.
- Front office: payroll and cap space per season; NHL / farm / prospects; Vegas's note (no prospect rights).
- **Contract edits, in the game:** set a deal (cap hit, years, two-way, extension), Save, and look at the game's
  Contract Status / payroll screen, then start a new Be a GM: the deal is there, on both money scales (normal and patch
  roster). Then `'contract edits'` leaves EXPERIMENTAL. **Played by the agent in lab round 41** on a patch roster (real
  dollars, `cli update --edits`): Team Rosters, a new Be a GM's Contract Status and Be a Pro Central show the edited
  deals; `'contracts'` and `'contract edits'` left EXPERIMENTAL (2026-10-21). The normal scale (x 0.6865) was played
  through the built exe (Unpatch, then update): Carlsson's edited $9M shows $6.180M, Eichel's $15M $10.300M.
- **My season, against the game's own screens:** the Standings screen's order (ties: fewer games, ROW, wins, goal
  difference are assumed), OT and SO losses counted together as OTL, a save in the preseason (the game's team row counts
  preseason games, the window does not), the farm league's division names on an unpatched save
  (docs/notes/season-saves.md).
- The Seattle / Vegas contracts (fixed 2026-10-20 in the local data pack): a Kraken player NHL.com leaves out stays with
  Seattle, not Vegas. Published to the server on 2026-10-23.

## Checks of the picture fix (2026-10-20, in 0.35.0; testers of 0.10.4: own pictures, wrong faces)
Plan docs/plans/giggly-squishing-candy.md, notes docs/notes/player-pictures.md. Experimental: `'picture numbers'`,
`'own pictures on save'`.
- Roster editor, Photos off: pick a photo for a player (a new one too), Apply, Save with RPCS3 closed: "Your own pictures
  are in the game now."; in the game his card shows it. With RPCS3 running: saved, "Your own pictures go into the game
  when you save with RPCS3 closed." **Played by the agent in lab round 40** (Troy Terry, Save as new, Photos off: his
  card and Player Info show the picture; docs/notes/lab-round-40.md).
- Update with Photos off and an own photo in My edits: the result says "Your own pictures: ..."; team names and jerseys
  unchanged.
- Two rosters on one PC (the community 2026-27 roster and a Puck Peak roster): update the Puck Peak one, then the other;
  Zach Benson, Spencer Knight and Dante Fabbro show their own faces in both (simulated on the owner's rosters, read
  only: 0 strangers after both, 127 before). Until the community roster is updated, those 127 show no picture
  instead of a stranger's.
- A player whose photo NHL.com has not got yet (the grey silhouette: Grzelcyk, Englund, ...) keeps the picture he had;
  the List of changes names him.

## Checks of 0.32.0 (2026-10-20; pictures downloaded, a clean product, gold highlights)
Plan docs/plans/ok-new-plan-check-sprightly-dragonfly.md (top). Nothing new goes into the save.
- A new PC (empty `%LOCALAPPDATA%\NHLLegacyRosterUpdater`): the Photos row is first, gold and on; it says "Downloading
  automatically... %" and then "Downloaded automatically. Ready." without being asked. About 160 MB.
- Update pressed during the download: "Waiting for the download... %", then the update runs with every picture.
- Switch the row off: the download stops, nothing is downloaded at the next start; on again: it goes on.
- No network at start: "Not downloaded yet. It tries again automatically."; the update still runs (pictures one by one,
  jerseys the game's own) and the result says "Some pictures could not be downloaded".
- Jerseys and ice before the download: "This season's jerseys come with Photos, logos and team names (Update tab)."
- Patch / Unpatch in gold, easy to find; "Update roster" the one bright blue button.
- A Utah home game after `update --photos` through the new exe: this season's jersey and ice, as with 0.31.0.
  **Played by the agent (lab round 39, 2026-10-20, unpatched EU):** Select Jerseys, the players' jerseys and the centre
  ice right; the window exe downloaded both packs by itself in 42 s; SHA-256 = the manifest; offline status fine.
- puckpeak.com and cheerin.quest unchanged after many downloads (`docker stats nhl-legacy-files`).

## Checks of 0.31.0 (2026-10-20; jerseys and ice for every team)
Plan docs/plans/ok-new-plan-check-sprightly-dragonfly.md (top), lab round 37 (docs/notes/lab-round-37.md).
`'custom team kits'` and `'shared ice'` are experimental. Lab round 38 (docs/notes/lab-round-38.md) played them
through the program's own update, patched game.
- **Coachella Valley** with a new home / away jersey, pants, socks, numbers and three colours ("Paint everything"),
  then one piece changed by hand (the helmet, away): Select Jerseys and a home game show it; the goalie's gear follows.
  **Passed in the lab** (round 38: Select Jerseys home and away, an away game with the magenta helmets). Not played:
  the goalie's gear, the unpatched game.
- **Coachella's home jersey navy** without any edit (0.30.0 painted the catching glove). Not played since the fix.
- **A custom team (one of the 12 NHL copies) with a crest picture** (with "Photos, logos and team names"): the crest
  on the jerseys, Select Jerseys and the centre ice; no other team wears it. "Restore the game's own pictures" takes it
  away. **Passed in the lab** (round 38, Custom Team 1: menus, loading screen, jerseys, goalie, centre ice; removed
  again by "photos remove").
- **A custom team with one of the game's logos** in the team colours. **Passed in the lab** (round 38, Custom Team 2:
  the bandit, orange, on the jerseys and centre ice). A prospect pool (art id 21000 + slot since 0.4, for its menu
  logo) keeps its menu logo until a crest is picked; its jerseys may show a blue square until then (round 34: an art
  id without create-a-team files). Not looked at in the game.
- **A national team's centre ice** (my picture): every national team's home game shows it. **A DEL club's** the same.
  **Passed in the lab** (round 38: saved on Canada, shown at Austria's home game; saved on slot 91, shown at
  Augsburg's).
- **A Winter Classic team** opens its NHL team's window; a change shows on both. Window only (tests and pictures).

## Checks of 0.30.0, addendum (2026-10-19 evening; Coachella / Henderson in the AHL, Be a Pro, names)
Plan docs/plans/ok-new-plan-check-sprightly-dragonfly.md, notes docs/notes/league-menus.md, lab rounds 35 and 36.
Patch 0.21. `'farm clubs in the AHL'` is experimental.
- **Patched game, "Photos, logos and team names" on:** Play Now > Select Teams > AHL lists 32 clubs, Coachella Valley
  FIREBIRDS and Henderson SILVER KNIGHTS among them with their crests; Custom Teams no longer has them; a game between
  them. **Passed in the lab** through the program's own update (round 36); the game between them in round 35.
- **The same with "Photos, logos and team names" off:** the two are in the AHL list but without names (the names are
  texts the program installs, as for every club). Not played.
- **Unpatched game** (Unpatch, then update): both back under Custom Teams, AHL of 30, no crash. **Passed in the lab**
  (round 36; the lab's own "(test)" entries had to be switched off first, a player's RPCS3 has none). The turn-back now
  also gives slots 30 / 31 the game's own names and divisions back (it kept Seattle / Vegas there since 2026-10-18).
- **Be a Pro** with a Seattle and a Vegas player on the NHL roster (patch 0.21, `0x458ec8`): the career loads, the GM's
  office names the AHL affiliate. **Passed in the lab**: Seattle (round 35), Vegas's Demek (round 36, Henderson named).
- **Blank names**: the AHL's Colorado, Cleveland, Laval, Chicago, Tucson, Calgary, Abbotsford and the CHL's Brantford,
  Newfoundland, Wenatchee are named in Select Teams.
- Season / Be a GM with Seattle or Vegas: the farm clubs as before (Season's lists go by slot).

## Checks of 0.30.0 (2026-10-19; jerseys for every league, Coachella / Henderson crests, HUT, gear)
Plan docs/plans/the-0-21-0-exe-is-parallel-haven.md. `'jerseys every league'`, `'own art ids'` and `'gear colours'` are
experimental. Lab round 34 (docs/notes/lab-round-34.md) played the first three rows, the crests, HUT and the goalie gear.
- Charlotte (AHL): this season's home, the game's own away (picked in the Roster editor). Play Now Select Jerseys and a
  home game: home is this season's, away the game's own.
- A Liiga / SHL club (the classic cut, style 0): home = "My picture" (a template from "This season's template..." painted
  on). Shown in Select Jerseys and in a game, no broken shirt.
- An NHL team with a third (Boston v2, Pittsburgh v6): the third is the game's own again after the update.
- A DEL club: the window keeps the centre ice at the game's own (shared DEL ice).
- **Coachella Valley / Henderson** (played in the lab): art 900 / 901 gave a blue square, so they keep 20073 / 20081
  with the crests (`art/crests.py`) on the ice, the jerseys and Select Jerseys. Still to see: the game's own roster with
  the update (art 20054 → 20073 / 20081), an away game of each.
- **HUT hidden** (played): no Hockey Ultimate Team in the main menu nor in Play.
- **Gear colours**: an AHL / European club's helmets and gloves, goalies of a few teams (Minnesota, Coachella,
  Charlotte played); a goalie with pads 85-88 before the update now wears a drawn model.
