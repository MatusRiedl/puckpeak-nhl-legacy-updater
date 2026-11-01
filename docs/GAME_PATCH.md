# The game patch: the year 2026 and 32 teams in Season and Be a GM

The hand-over for the game patch, for the next developer and the owner. The source of truth is
[`legacy_roster/gamepatch.py`](../legacy_roster/gamepatch.py): every address, the game's word and our word, with a comment
saying why. The research log, round by round, is [notes/patch-design.md](notes/patch-design.md). The plan for the release is
[plans/fluffy-dazzling-scone.md](plans/fluffy-dazzling-scone.md).

**Status 2026-10-22** (lab rounds 12-45 played by the scratch autoplay, not by the owner; patch 0.24, stages A-Y, year 0.8,
intro / login / news entries 0.1):
- Played in the lab and working:
  - the year 2026;
  - 32 NHL teams in Season mode: the calendar, a whole season simulated, the standings;
  - the favourite-team list of 32;
  - Be a GM: the team picker, trades, signings, simulating, three franchises in one session (round 10);
  - the farm league of 32 AHL clubs (stages L, M), Seattle's call-ups (stage O);
  - the All-Star game on 6 Feb (stage J, in EASHL's places with art 30 / 31);
  - the trade deadline, the end of the season, a 16-team playoff bracket with Seattle and Vegas;
  - saving and reloading a Vegas Season (the 32-bit `leaguestates.value`);
  - Be a GM with Vegas (rounds 14-17): a whole season, the playoffs, the draft of 32 (stage K), the off-season, season 2's
    calendar of 32 (stage R: 32 x 80 NHL, 32 x 72 AHL), signings, call-ups and a send-down with Henderson, season 2 to
    late October, Save and Exit from Be a GM in season 2.
  - 84 games (stage S, rounds 20-22): Be a GM with Seattle, seasons 1 and 2 each ended with **84 GP for all 32** in the
    standings; season 2's preseason (stage T), its playoffs (Winnipeg won the Cup, the Chicago Wolves the Calder Cup).
  - The second draft (June 2028) crashed in round 22: the game numbered the picks for 30 teams, so the new year's picks
    overwrote 14 first-round picks of the next draft. Stage U (0.16) numbers them for 32 (round 23, section 3): confirmed
    through the June 2027 draft and season 2's new year (every year 224 picks, none doubled).
  - Ages (year 0.6, rounds 23-25): the patch roster keeps birth years on the league's own clock and the year entry
    corrects the two date-based ages; with real birth years the computer GMs sent stars to junior or the farm at the new
    year (round 23), with the patch off they did not (round 24).
  - Round 27 (Be a GM with Anaheim, Seattle and Vegas computer-run): stage V gives them their call-ups (both held 22-24
    players all season). The stars that still went to the farm at season 2 came from the calendar's timing: the next
    seasons' calendar is now a week later (`FUTURE_DAYS`, 0.17), and every computer team got its final preseason cut
    (section 6).
  - Two optional entries of their own (round 27): "skip the intro" (the game starts at Press Start, one press to the main
    menu, no notices) and "no online login at boot". Played with two boots and a game.
  - Round 42 (0.23): six-bit player rights, so Henderson's own players are Vegas's (In the System, call-ups, trades);
    a Be a GM with Vegas through the season, the June 2027 draft and free agency.
- Built, not played yet: the exe makes the patch roster and patches / unpatches RPCS3 itself (Phase D, 2026-10-15;
  section 7). The lab rounds above used `cli team32-test` and the lab's 25 "(test)" entries.
  - Round 28: season 2 of a Be a GM to the end, 84 GP, the playoffs and the **June 2028 draft** (all 7 rounds); Be a Pro with
    Edmonton (a game played) and, with stage W and year 0.7, with Seattle (career start, save, reload, a preseason game);
    plain Season mode with Vegas: 84 GP for all 32, the playoffs, the Cup.
  - Round 29 (stage X, 0.19, patched by the program itself: `cli update --game-patch --in-place` from source, not the exe):
    the 2026-27 salary cap of
    $104.0M with the real contracts. Select Team and Be a GM's Contract Status show the cap for every team checked and
    the real deals (McDavid $12.500M for two seasons, Marner $11.790M, the Tkachuks); the "not salary cap compliant" question
    came up (Yes: the computer fixes the teams over the cap). Then simulated through the June 2027 draft, the summer and
    the 2027-28 preseason (5 Oct 2027): after the final cut no team has lost a third of its NHL pay (round 27's measure);
    the game raised its cap to $107.235M and the floor to $80.135M by itself (docs/notes/salary-cap.md).
  - Round 30 (stage X v2, 0.20, year 0.8, 2026-10-17): the real cap per season. 2026-27 $104.0M / floor $76.9M, then
    after season 1 the game took 2027-28 from the table: $113.5M / $83.9M, lowest $0.900M, rookie maximum $1.075M;
    Contract Status reads "26-27 / 27-28", then "27-28 / 28-29"; Larkin stayed on Detroit (the 82 players NHL.com
    leaves out are kept with their teams). Season 2 to 12 Oct 2027: no team buried its stars.
- Not played yet:
  - switching the patch off again with an old Season or Be a GM (round 24 played a new Be a GM on the community roster
    with the patch off: fine; the patch roster with the patch off crashes a new Be a GM).
- Seen once, not repeated: a hang in a computer team's game (round 21, section 6).
- Nothing is published.

## 1. What it is

The game is *NHL Legacy Edition* EU (`BLES02153`, version 01.00, PPU hash `c93019e83e820ad7ce6ac2428d022e7c09d484d3`). Out of
the box its Season and Be a GM know 30 NHL teams, and its calendar starts in 2015. The patch has three parts. All three
have to be there together.

**Update 1.01** (since patch 0.25, 0.50.1): RPCS3 boots the update's `dev_hdd0/game/<TITLE>/USRDIR/EBOOT.BIN` when it
is installed. EU and NA 1.01 are one program, PPU hash `d4bbaf00a080a924e862c1b3f7705380a3499edb`
(`gamepatch.UPDATE_HASH`). Every entry is written for 1.00 EU, 1.00 NA and 1.01. The 1.01 addresses
(`legacy_roster/patch101.py`) come from `tools/port_patch.py`. The window says "Patch again" when the patch is in but not
for the version RPCS3 runs (`patchinstall.stale`). Notes: notes/update-101.md.

1. **RPCS3 patch entries.** RPCS3 reads `<rpcs3>/patches/BLES02153_patch.yml`, along with `patch.yml` and
   `imported_patch.yml`, and the switches in `<rpcs3>/config/patch_config.yml`. At every boot it changes the game's
   instructions in memory and logs "Applied patch". The game's EBOOT.BIN on disk is never changed or re-signed. The patch
   uses RPCS3's patch format 1.2:
   - `be32` writes, which replace one 4-byte instruction;
   - `calloc` caves, a few words of our own code that RPCS3 runs in place of one game instruction.

   In every cave the game's own instruction is the last word. An RPCS3 that does not know `calloc` writes the words one
   after another at the hook, so only that last word stays there and the game runs as it was.
2. **Two loose database files**, `db/nhlng-meta.xml` (the description) and `db/nhlng.db` (the empty Season / Be a GM
   tables), in the game's own folder (`dev_hdd0/game/BLES02153/USRDIR/db`). The game reads them at boot in place of the
   copies in `cacheboot.big`.
   - The program makes them from the player's own disc: `gamepatch.disc_meta` / `fit_meta` / `check_meta` and `disc_db` /
     `fit_db` / `check_db`. None of the game's own bytes ship.
   - They give 11 team fields 6 bits instead of 5, so that Vegas (31) is not stored as "no team" (-1), and
     `leagueteams.ahlaffiliate` 7 bits (`META_KEYS`), so that the farm keys 32-63 fit.
   - They give Be a GM 32 rows (`META_ROWS`).
3. **A roster made for the patch.** `pipeline.update(game_patch=...)` (the window's row, `cli update --game-patch`) or
   `calendartest.team32_test` (the lab) make one with `pipeline.patch_roster`.
   - `year_shift`: birth years on the league's own clock, the real year - 1911 (our usual update stores year - 1910 for
     the game's 2015), and the teams' draft picks 11 years later (2026-2031). Contract and debut years stay: the game reads
     them against its league year, which the patch does not move (year entry 0.5 / 0.6, rounds 24-25; section 6).
   - The 32-team 2026-27 calendar.
   - `farm_fit`: the AHL clubs in their 2026-27 divisions, Seattle and Vegas with no farm team named (the patch gives
     them Coachella Valley and Henderson), and the AHL's real 2026-27 calendar (data pack `ahl_schedule`, 1,152 games)
     in the farm calendar.
   - `divisions_fit`: Utah in the Central, Seattle and Vegas in the Pacific.
   - `verify(farm_patch=True)` checks all of it.

   With the patch on, other rosters do not load (stage S makes the roster's save 864 bytes longer).

**Online entry (2026-10-25, patch file 0.26+, `gamepatch.ONLINE_ENTRY`).** The program carries the community patch's words (1.00: `0x8bc4bc` / `0x8bc494` -> `4e800020`, `0x104f0bc` -> `4bfd6524`, `0x211df0` -> `4bff8760`; the old words are checked against the decrypted EU program by `tools/audit_patch.py`) and, for update 1.01, `0x87b11c` / `0x87a010` -> `2c030001` (old words not known, not audited). It is its own switch (`patchinstall.set_online`, `cli game-patch online`), also without the 32-team patch, kept by the other switches and removed by Unpatch. The "Play online" tab sets it up (docs/notes/multiplayer.md).

**Online.** The community online patch ("multiplayer patch", in RPCS3's own `patch.yml`) changes four words, none of them
ours, so both patches can be on together. The owner played online through the community server with the patch and the "no
online login at boot" entry on (2026-10-18): an online mode signs in when it is opened. Not looked at in detail: a game
between a patched and an unpatched player (team numbers 30 / 31 and the dates differ).

## 2. The entries

Today each stage is its own entry, so that the lab can switch them separately. The release will have two entries,
"NHL Legacy 2026 (PuckPeak)" and "NHL Legacy 32 teams (PuckPeak)" (plan Part 4).

| Entry | What it does | Found by | Key addresses |
|---|---|---|---|
| **year** (`YEAR_CAVE`, 0.3) | The game's years 2010-2025 become 11 later; 2026 and later stay, so a date does not drift on every round trip. | 0.1 crashed creating a Season (it added 11 to every year); 0.2 used a cave keyword RPCS3 does not know; 0.3 passed (2026-10-12). | `0x731d04` in the date-to-day converter `0x731ce8` |
| **year: contract seasons** (0.8) | Be a GM's Contract Status names each season of a deal "15-16", "16-17" ...: `GetSalaryCapYearStrings` (registered at `0x19b17a0`, OPD `0x215b3c0` -> `0x1060034`, entry 0xc8 of the GM vtable `0x1cd7c30` = `0x402c50`) prints DISPLAY "%d-%d" and DISPLAY_ABBREVIATION (year - 2000, "0%d" / "%d", "%s-%s") from the league year; `ori r23,r3,0` becomes `addi r23,r3,11` ("26-27"). DISPLAY_ABBREVIATION is also read at `0x43d8dc` (not changed: look for any "15-16" left in the lab). | Owner's wish (2026-10-16 evening): real seasons. Not played yet (round 30). | `0x402d24` |
| **year: job list** (0.7) | A new Season / Be a GM / Be a Pro runs a list of jobs on its first day, made with room for 8 (`0x33a470`). In a year other than 2015 the new season's roster job (`0x29bcc4` -> `0x22d1b8`) is added too: the 9th job was written past the list. Room for 16. | Round 28: a Be a Pro with Seattle ran the list into a broken job (executing `0x20e5d70` at `0x33a554`, jobs 0-7 done; docs/notes/be-a-pro.md). | `0x33a4d0` |
| **year: calendar marks** (0.9) | The Calendar screen (Season / Be a GM) and Be a Pro Central's week (lab round 50: on 0.25 a Vegas pro's week was empty, the same save showed its games on 0.26) ask each day's game with the year it shows: `GetTeamMatchIDByDate` (registered at `0x19ad4fc`, OPD `0x215a778` -> `0x105435c`, entry 0xc of `CCalendarAdapter`'s vtable `0x1cd7e88` = `0x4078b0`) gives none for a year after the league year + 1 (`0x407944`-`0x40795c`), and with the patch the screen's year is 11 later. `addic r3,r3,1` becomes `+12`, the second ask for the league year becomes `addic r3,r3,-1` + `b 0x407978` (the league year + 11). | Lab rounds 19-27: no Home / Away marks with the year entry, marks with the patch off. Round 49 (2026-10-25, a Be a GM of round 42): marks in September / October 2026, March / June 2027 and the AHL view. | `0x407954`, `0x407960`, `0x407964` |
| **A** Be a GM tables | GmLogic's flags and SalaryCapManager's 30 money records grow to 32. | Reading (keys 30 / 31 write past tables of 30). | `0x31b958`, `0x3c5f1c`, `SCM_FLAGS`, `SCM_WORD` |
| **B** League lists | The League object's list A (farm key), list B (teams) and list C (the farm clubs' rosters, Be a GM) move to its new end with room for 32. | Reading. | constructor `0x270c50`, size `0x287f3c` / `0x2899b8`, list C `0x27c4b0` |
| **C** team numbers | NHL keys 0-31, the farm league's keys after them; farm key - 32 = farm place. Since 0.9 only with L and M. | Reading ("I-60", then "I-66"). | is-NHL `0x1639b4`, farm places `0x27fc04` |
| **L** farm league of 32 | The farm list takes AHL slots 32-61, then Coachella Valley (234) and Henderson (235), in the 2026-27 divisions (Pacific 10). | Reading ([notes/keys64.md](notes/keys64.md)); not played. | farm list `0x22fb2c`, caves `0x22fbb8`, `0x22fda4`, four division fills |
| **M** 64 league teams | Every "60 league teams" becomes 64; a farm key is the farm club's slot; Seattle / Vegas get keys 62 / 63; the All-Stars become 64 / 65 by themselves. | Reading (every site in keys64.md); not played. | `0x128754` ... `0xf40194`, caves `0x27b9d8`, `0x27ba78`, `0x27d0b8` |
| **N** Seattle, Vegas in the NHL | The Season's NHL competition (written in code) gets slots 0-31; Seattle and Vegas join the Pacific, Utah the Central. | Reading. | NHL list `0x22fe30` |
| **D** simulator | The Season's simulator object and its block get room for 32 teams. | Round 1: simulating crashed at `0xdf7fc`. | object `0xdca44`, `_SIM_BLOCK`, day run `0xdf2f0` |
| **E** home games | The calendar loader's team count, 30 -> 32. A home team at or above the count meant "the All-Star game", so all 80 Seattle / Vegas home games became an empty "60 v 61" and the week's sim hung. | Round 2. | `0x3ddc74` (count for `0x3de1dc`) |
| **F** favourite list | "Pick favourite team" counts NHL teams numbered below 32; team lists sort 0-31 by name. | Rounds 3-6 (30 teams shown). | `0x129b44`, order `0x12709c` |
| **G** Be a GM picker | GetTeamIDsForDivisionId's stack table of 30 team records grows by two. | Round 6: Be a GM crashed as its screen opened. | `0x2dd1fc` |
| **H** staff counts | StaffLogic's mDraftStorage, 30 records of 12 bytes, grows to 32. | Round 7: a second Be a GM crashed in the allocator. | `0x3bc428`, `0x3bc448`, `0x3bc53c` |
| **I** preseason | The season calendar buffer holds 1,464 games: the preseason (28 per division of 8, no limit) ran 42 games past the old 1,350. | Rounds 7-9 (heap damage); round 10 passed. | `0x2849f0`, `0x284a18` (`0x28470c`, preseason `0x2843e8`) |
| **J** All-Star game | The All-Star teams come from EASHL 1 / 2 (slots 220 / 221, data words) instead of 30 / 31; the calendar loader takes a team playing itself as the All-Star game. The roster names the two places and puts them in the conferences (`all_star_fit`) and has one self-row (`schedule.ALL_PATCH`). | Reading ([notes/all-star.md](notes/all-star.md)); not played. | `0x1ab0688` / `0x1ab068c`, cave `0x3de66c` |
| **K** draft | The draft object's 30 teams become 32: the order, the lottery (one draw among the 16 that miss the playoffs, today's odds), numbering the picks, the Season's picks every year; Be a GM's copy of the order stays 30 and the sim reads only that. | Reading ([notes/draft.md](notes/draft.md)); not played. | count `0x3c4084` / `0x3c4b84`, lottery `0x3c4e34`, caves `0x3c4f0c` (draw), `0x3c50d4`, `0xdfef0`, Season picks `0x228050` |
| **O** farm work of Seattle, Vegas | Five words that still said "an NHL team is below 30": a call-up by Seattle / Vegas went nowhere (`0x1c7750` sent the player to the farm key's parent only for keys below 30), a player joining them was marked AHL (`0x1c42f4`), and the new-season roster work (`0x29bcc4` -> list `0x22d1b8`, step `0x1cc86c`) had 30 places and skipped keys 30 / 31. | Lab round 12, driven by the scratch autoplay: Seattle and Vegas made no call-ups in 4 months, Seattle dressed short and a sim hung. | `0x1c7898`, `0x1c42f4`, `0x1cc88c`, `0x29be68`, `0x22d1f4` |
| **P** roster upkeep of Seattle, Vegas | Eight loops of the league's daily and off-season steps still ran over teams 0-29: the computer GMs' daily roster work (`0x281c34`, `0x28ac78`), the daily roster and line check (`0xf3b8c4`, three loops), re-signing (`0x29c590`) and the new season's roster fill and lines (`0x29d338`, two loops). Every table they reach already holds 32. | Round 14: a computer trade left Seattle with 19 dressed and the next Be a GM sim crashed in the line picker (`0x151fb4`). | `0x281ca4`, `0x28ad54`, `0xf3bb88`, `0xf3bc14`, `0xf3bc5c`, `0x29c91c`, `0x29d608`, `0x29d77c` |
| **Q** game-day moves with one partner | The game-day step (`0x290a50`) checks a player against the partner club's org brain and, when he is not in it, against a second partner's brain without asking whether there is one: only a farm team shared by two NHL clubs has two. Two words ask first (`cmpwi r31,0` / `beq`) in place of a lookup whose answer was never used: no second partner = no move. | Round 15: season 2 of Vegas Be a GM crashed on 2 October 2027 (Vegas - Anaheim; Anaheim's Mrazek, on San Diego's roster, was not in San Diego's brain; CIA in `0x1c4154`, LR `0x2967e0`). | `0x2967d8`, `0x2967dc` |
| **R** next season's calendar | A new season's games are the roster's `nhlfutureschedule` (`byED`) and `ahlschedule` moved to the new weekdays, each team taking the games of the team before it in its division (`0x283800` -> `0x283498`). That team map was a stack table of 30 (`r1+0xc0`); the words of teams 30 / 31 lay in the next table, cleared before use, so their games went to key 0. The frame grows by 0x80 and the map of 32 moves to `r1+0x790`. The roster's `byED` gets the 32-team calendar (`gamepatch.future_fit`, `check_future`; the game's own has 30 teams). | Round 15: season 2 had Anaheim and Calgary without games, AHL Colorado / Ontario too, "Anaheim" in 144 AHL games; their game days ran Be a GM's money code for AHL clubs (flags past SalaryCapManager's 32, over the StatsCache) and leaving Be a GM crashed freeing `0x01000000`. | `0x283800`, `0x283808`, `0x283840`, `0x28399c`, `0x28415c`, `0x284160`, `0x284200`, `0x284250` |
| **S** calendar of 84 games | The game gives 35 tables of a roster a room of its own (`0x3dd69c` reads pairs "table, rows" from the data at `0x1acc878`, whatever the roster file, the meta or `nhlng.db` say); `nhlschedule` / `nhlfutureschedule` get 1,291 rows there, now 1,345. The game then reads a roster save whose section is 864 bytes longer (`SECTION_SIZE`, `section_fit`): with S on, a roster of the game's own length "appears to be damaged", and without S a roster made for it does too. | Rounds 18-20: more than 1,291 rows crashed a new Be a GM; with `nhlng.db` grown it started but kept rows 0-1,290 (teams at 80-82 games). | data words `0x1acc90c`, `0x1acc914` |
| **T** team rankings of 32 | The league's StatsCache (`0x140aa8`, 0xf674 bytes) ranks the teams in 17 team stats (`0x1405f0`: query `0x3a2818` with the stat from `0x21bf750`, row count `0x3a47f0`), each in a block of 0x360 with room for 30 entries of 0x1c, the stat's flags at +0x350 and the count at +0x364. With 31 / 32 teams the 31st entry lies over the flags and the count, and the next block's first entry marks its team pointer's high byte with 1. The count is capped at 30 (cave), as when teams have not played yet; the blocks are read across the menus, so they do not grow. | Round 20: Be a GM's second preseason (24 September 2027) crashed in `0x1402f8` (`0x1404a8`, reading `0x8db30180`) through team 31's pointer `0x01aefde0`. | cave `0x140684` |
| **U** draft pick numbers | The Season keeps 6 drafts of picks (`leaguedraftpick`, 1,344 rows) under a key of 11 bits: (year mod 6) x 210 + pick number, at the Season's set-up (`0x227e74`) and when a new year's picks are made (`0x2281d4`, it replaces the oldest year by key). With 224 picks a year the keys of one year ran 14 into the next: at set-up 70 keys were doubled, and at the first new year the new picks overwrote 14 round-1 picks of the following draft (teams 0-13) and 14 round-7 picks of the year after. Five words at each place make the key (year mod 6) x 224 + pick number (0-1,343). Only for a Season or Be a GM started with it: an older one keeps its doubled keys. | Round 22: at the June 2028 draft 14 first-round places had no pick (NHL shields on the board, names twice), and the draft crashed in the heap allocator (`0xc9bc18` writing `0xd9d`, from the draft `0x3c3030` -> roster upkeep `0x1c96cc` -> free) as Seattle's auto-pick began. | `0x227e74`, `0x2281d4` (`PICKS_PER_YEAR`) |
| **V** call-ups of Seattle, Vegas | The computer's roster planner (`0x3ccfd4`, rerun by every roster commit `0x1ca618`) marks each player of a club's pool "on an NHL team" when his team key is 0-29 (`0x48678c`), and its count (`0x48c82c`) put every player of a team key 30 or more on the NHL roster (in the game's own league those were farm and European clubs). Seattle's and Vegas's own players were "not on an NHL team" and their whole pool, farm included, counted as NHL roster, so the planner sent every call-up down again. The SalaryCapManager refresh after a plan (`0x494ac8` -> `0x3a8a30`) also skipped them. Three compares become 32. | Round 27: with Anaheim as the human team the computer's Vegas fell to 16-17 players by November 2026 with 13 healthy players of its own in Henderson; the sim hung in the line picker (runs 8-10). With V (run 11) both held 22-24 to the end of the season ([notes/gm-brain.md](notes/gm-brain.md)). | `0x486cf8`, `0x48c8b4`, `0x494b84` |
| **W** Seattle's / Vegas's farm players, Be a Pro with Seattle, Vegas | The game's "which team is this player on" query (`0x220834` mode 0 via `0x221124`, ten callers; and `0x2211d8`) asked the league's roster table for a team below 60, the old count of league teams that stage M made 64. A player on Coachella Valley / Henderson (keys 62 / 63) was on no team: a Seattle prospect's Be a Pro career set its pro's team to -1 and crashed while loading. Both queries now ask below 64. Six more compares of Be a Pro's own code take Seattle / Vegas as NHL teams (30 becomes 32): its set-up, its league pick, four branches; and (0.21) `0x458ec8`, where a pro's NHL team and farm team are told apart: with 30 a pro on Seattle's / Vegas's NHL roster got his farm club as NHL team and his NHL team as farm team, and the career crashed while loading. Only with all other 32-team entries. | Round 28: a New Pro with Seattle's Berkly Catton (put on Coachella Valley by the league) crashed while loading (`0x1c0098` reading `0x1c0`); the six compares alone did not help, the two queries did: the career loads, saves, the preseason starts. Edmonton's Colton Dach loaded and played before W (docs/notes/be-a-pro.md). Round 35: Seattle's Jake O'Brien (NHL roster) crashed while loading Be a Pro (`0x1c4814` reading `0x66`); with `0x458ec8` at 32 the career loads, saves, the GM's office reads "AHL Affiliate is the COACHELLA VALLEY FIREBIRDS", a preseason game was played (docs/notes/lab-round-35.md). | `0x2209c0`, `0x2212d4`, `0x460eb8`, `0x459904`, `0x45bba4`, `0x45bc6c`, `0x45bd7c`, `0x45be38`, `0x458ec8` |
| **X** salary cap by season (0.20) | Be a GM's money comes from two functions of the game's resource table: `0x4a7240(obj, r4, n)` (r4 = 0 the floor, 1 the cap; a base x $100,000 plus the yearly rises x $1,000) and `0x4a73b0(obj, r4, n)` (r4 = 3 the lowest salary, 4 the highest rookie salary, x $1,000); n = the season's number (0 = 2026-27). Only the wrappers `0x4a7360` / `0x4a7388` / `0x4a7498` (cap / 5, the most one player earns) / `0x4a7448` / `0x4a7470` call them. A cave in place of `0x4a7240`'s first word (the `stdu`: none of the game's function runs) answers from `CAP_TABLE` with `lis` / `ori` / `blr` (n below 0 counts as 0, past the table as the last season), and `0x4a73b0` becomes `b 0x4a7240`. The real numbers (owner, 2026-10-16 evening): 2026-27 cap $104.0M / floor $76.9M / lowest $850,000 / rookie max $1,025,000; 2027-28 $113.5M / $83.9M / $900,000 / $1,075,000; 2028-29 $127.5M (the league's estimate) / $94.35M / $950,000 / $1,125,000; 2029-30 on the cap and floor held, $1.0M / $1,175,000 (docs/notes/salary-cap.md). The game's own lift stays: at a new year (`0x3c6740`) cap and floor rise by as much as the highest team payroll is over the cap (`0x3c691c`), the table wins when it is higher. Callers: Be a GM's set-up (`0x3c6030`), each new year, contract demands (`0x31ab98`, `0x31acc8`). Only with a roster that holds real dollars (`contracts.REAL`: the patch roster). | 0.19 (round 29): Select Team and Contract Status showed $104.000M, McDavid $12.500M; its +$1.5M a year gave 2027-28 $105.5M and the game's lift made it $107.235M. 0.20 not played yet (round 30). | cave `0x4a7240`, `0x4a73b0` (`CAP_TABLE`, `cap_of`) |
| **Y** Coachella Valley, Henderson in the AHL (0.21) | The front end's team lists (Play Now's Select Teams) come from `0x128348`: one `exhibitionteams` record each, kept when its league (record +0x90, which follows the roster's `ttOk` league) matches the list's. Before that, a gate (`0x128408`-`0x128430`, 11 words) left a created team (+0xa0 = 1, as slots 222-251 are) out of every list but Custom. Our words: a created team whose league is not 13 (Custom) goes to the league check like a club; the rest as before (a created Custom team the caller allows goes to the league check, which drops it from any list but Custom / 16, so every list holds what it held). Five name functions (full name `0x2a6784`, city, nickname, Select Teams line 1 / 2) build "Custom Team N" for a created team; a cave at each `lbz r3,0x110(r1)` clears the flag when the league is not 13, so the game names it by its art code (`NHLTeamName_CVF`, `TEAMLINE1_CVF` ...). The roster side: `league_fit` gives slots 234 / 235 an AHL Pacific club's league fields (league 1, leaguegroup 7, conferencegroup 8, divisiongroup 13) at the end of `patch_roster`; `unleague` puts Custom's back when a patch roster is read, `unpatch_roster` when it is turned back (the unpatched game keeps them under Custom). The names need "Photos, logos and team names" (`art/loc.py`, which also had the game's text hash wrong: bytes & 0xdf). Season / Be a GM had them in the AHL already (stage L, by slot). **0.22 (round 41):** the list builder `0x12865c` counts the switched-on teams (`ttOk.NYKk` = 1) and `0x128348` walks ids 0, 1, 2 ... that many times, as if the switched-on teams came first; a roster from the game's own has custom slots 222-233 switched off, so the walk ended at 223 and Roster Management's AHL list (and Play Now's, on such a roster) never reached 234 / 235. A cave at the walk's top (`0x1283bc`, `_skip_cave`) moves an id from 222 on to the next switched-on team (asked the database as `0x129c04` does), and ends the walk (`0x128618`) when none is left; ids below 222 are walked as before. | Round 35 (probes Y, Y2): Play Now's AHL list of 32 with Coachella Valley FIREBIRDS and Henderson SILVER KNIGHTS (names, crests), Custom Teams without them, Henderson at Coachella Valley played to the end; Be a GM with Seattle: Coachella players "In the System" with the AHL badge, simulated to 30 Oct. Not played yet through the program's own build (`farm clubs in the AHL` experimental). Round 41 (0.22): Roster Management's AHL list of 32 with Coachella Valley / Henderson, their rosters open (docs/notes/lab-round-41.md). | `0x128408`-`0x128430`; caves `0x1283bc` (0.22), `0x2a67d8`, `0x2a69e0`, `0x2a6ba8`, `0x2a6d28`, `0x2a6e6c` (`STAGE_Y`, `STAGE_Y_CAVES`, `league_fit`) |
| **skip the intro** (`INTRO_ENTRY`, optional) | The game's own quick boot (the full-boot byte `0x220a64c` = 0, read at four places): no language pick (RPCS3's console language), no intro videos, no legal screen; and `FlowBoot::Start` always takes step 2 (no autosave notice; autosave stays on). The Start press is gone too since round 47: with the entry ticked, the program also puts a changed copy of the title screen (`fe/ion/game/screens/bootflow/03_pressstart.big`, made from the player's disc by `art/pressstart.py`) into the game folder, which presses Start by itself after a quick boot; Unpatch or the switch off takes it away. | Owner's wish (2026-10-15); [notes/intro-skip.md](notes/intro-skip.md); round 27: two boots, a game; round 47 ([notes/press-start.md](notes/press-start.md)): the main menu with no press, with and without the login entry, a Season and Be a Pro, more than 5 minutes idle. | `0x220a64c` (data), `0xfb2f24` |
| **no online login at boot** (`LOGIN_ENTRY`, optional) | `COnlineSession`'s `ShouldDoBootFlowLogin` (vtable slot 25) answers no: no online login and no online boxes at start. Online play still works: an online mode signs in when it is opened. | Same; round 27. The owner played online through the community server with it on (2026-10-18). | `0x1cd411c` (data) |
| **Puck Peak news on the main menu** (`NEWS_ENTRY`, ticked with the patch) | `RequestDynamicMessages` (`0x7e8cd8`) always takes its signed-out branch (`beq 0x7e9230` -> `b`): the main menu's news panel shows the offline messages of the game's text file (the program's gg.puckpeak.com line, `loc.PROMO` '#4') also when signed in, never the server's news (which are the game's 2014 texts). | Owner, 2026-10-22: "all these texts should say the same gg.puckpeak.com"; [notes/promo-texts.md](notes/promo-texts.md) section 5; round 45: boots to the main menu, the panel shows the text file's line. Online not seen yet. | `0x7e8d58` |
| **Z** (lab only) | A crash detail: dumps the bytes around a broken heap block into the registers RPCS3 logs. Never in `TEAM_STAGES`, never shipped. | Round 8. | cave at `0xc9aadc` (scratch `lab_z.py`) |

`TEAMS_VERSION` is the version of the 32-team entries (0.14: 84 games, stage S; 0.15: stage T; 0.16: stage U; 0.17: stage V and
the next seasons' calendar a week later; 0.18: stage W; 0.19: stage X; 0.20: stage X by season; 0.21: stage Y and stage W's `0x458ec8`; 0.22: stage Y's list walk; 0.23: the roster's player rights in six bits, no new words; 0.24: the same words, the news entry ticked with them, so a game patched with 0.23 shows "Patch again"; 0.25: the same words, also for update 1.01; 0.26: the year entry 0.9); the year entry has `PATCH_VERSION` (0.7: the job list; 0.8: the contract seasons), the intro, login and news entries `INTRO_VERSION`. Bump the
version on every change: RPCS3 shows it, and the lab README names it. The intro entries stand apart from the rest: each
works on its own, with or without the year and team entries, and `patch_text` always writes them last.

**Data, not code.** The roster rules that go with the entries:
- the Season's farm teams are slots 32-61, 234, 235 (`FARM_SLOTS`; farm places 0-31), in the divisions of
  `FARM_DIVISIONS`; every NHL team but Seattle and Vegas names its own farm team in slots 32-61 (`check_farm`);
- the farm calendar is the AHL's own 2026-27 calendar, 72 games per club;
- the divisions are those of 2026-27 (`TEAMS_2026`);
- the Season keeps its human teams as one bit per team of a league in `leaguestates.value` (31 bits in the game):
  Vegas is bit 31 (Henderson too, key 63), so `fit_meta` / `fit_db` give that field 32 bits (`META_MASKS`). Without it
  a Vegas Season saves no human team and comes back as "undefined" with Play Next Game greyed (Seattle, bit 30, fits).
  The Season copies the bits when it is made: a Vegas Season made before the new db files stays broken;
- the next seasons' calendar (`byED`, nhlfutureschedule) is the 32-team calendar `FUTURE_DAYS` (7) days later, the same
  weekdays (`future_fit`, `future_rows`, `check_future`), so season 2's preseason starts after the game's fixed new year
  of 11 September (round 27); `fit_db` copies it into `nhlng.db`;
- the 32-team calendar is the real 2026-27 one: 84 games per team (42 at home), 1,344 rows and one All-Star row, a team
  against itself on `schedule.all_star_date` (`schedule.ALL_PATCH`; `check_all_star`, `check_games`). The roster's
  `ihmS` / `byED` have room for 1,345 rows, the same as stage S gives them in the game, and its save section is
  `SECTION_SIZE` (2,456,940 bytes, the game's own 2,456,076 + 2 x 54 rows x 8 bytes; `section_fit`);
- EASHL 1 / 2 are named "Eastern All-Stars" / "Western All-Stars", in conference groups 2 / 1 (`ALL_STAR_LOOK`). Their own
  players stay: the Season never copies them into the All-Star teams.

## 3. The lab

All patch work is played in a lab, never in the owner's real RPCS3. The lab is a folder outside the repo, with:
- `rpcs3/`, its own RPCS3: the patch file and switches, the game folder with the loose db files, the saves;
- `appdata/`, which is `LOCALAPPDATA` for the program while it writes into the lab, so its art list and kept copies stay
  there;
- `launch_lab.ps1`, which starts the lab's RPCS3 with the disc image;
- `README.md`, the owner's steps for every round (the newest at the top);
- the decrypted `EBOOT.ELF` next to it (read only; never shipped, never committed).

How a round is made:
1. `python -m legacy_roster team32-test --rpcs3 <lab rpcs3.exe> [--photos]` with `LOCALAPPDATA` set to the lab's
   `appdata`. It writes:
   - the LAB roster "32 TEAMS 2026";
   - the db files, into the lab's game folder;
   - with `--photos`, the names, logos and looks;
   - the patch with every entry, to the program's reports folder.
2. The lab's patch file is written by a scratch script (it adds Z), and every entry is switched on in the lab's
   `patch_config.yml`. Only while the lab RPCS3 is closed.
3. The owner plays the README's steps and reports. If RPCS3 says the game crashed, the owner closes RPCS3 and does not
   start it again: the next start replaces `rpcs3/log/RPCS3.log`.

| Round | Patch | What the owner saw | What it led to |
|---|---|---|---|
| year 0.1-0.3 | year | 0.1: 2026 shown, Season crashed; 0.2: same; 0.3: 2026, Crosby 39, Season and Be a GM start | the year window (`YEAR_WINDOW`) |
| 1 | A, B, C, N | Season with 32 teams, Seattle's calendar right; simulating crashed | stage D |
| 2 | + D | Vegas's home games missing, a week's sim hung | stage E |
| 3 | + E | Vegas's games there; simulating past one crashed; favourite list 30 | the fitted meta (6-bit team fields) |
| 4 | same | the sim crashed again | `nhlng.db` (the Season takes the field bits from it) |
| 5 | 0.3 + db | days fine, months crashed (a shared farm team ran out of players) | `farm_lend` (0.4), first F |
| 6 | 0.4 | a whole season fine; favourite list 30; Be a GM crashed opening | F (the right list), G (0.5) |
| 7 | 0.5 | F and G fine; Be a GM played; a second Be a GM crashed | H (0.6) |
| 8 | 0.6 | the second Be a GM still crashed | lab entry Z |
| 9 | 0.6 + Z | crash while freeing a calendar buffer | I (0.7) |
| 10 | 0.7 + Z | three Be a GMs in one session, no crash | passed |
| 11 | 0.8 + Z | not played: folded into round 12 (patch kept as `round11_BLES02153_patch.yml` in the lab) | |
| 12 | 0.9 | played by the scratch autoplay (no owner): 32 NHL + 32 AHL, the calendar to 6 Feb; the All-Star game hung on EASHL's arena; Seattle / Vegas made no call-ups, Seattle dressed short and a sim hung | `ALL_STAR_RINK` (art 30 / 31), O (0.10) |
| 13 | 0.10 | autoplay, roster `0216`: the All-Star game played, Seattle called players up, the trade deadline, the end of the season, a 16-team bracket with Seattle and Vegas; a **reloaded** Vegas Season had no team ("undefined", Play Next Game greyed) | `leaguestates.value` 32 bits (`META_MASKS`): a reloaded Vegas Season works |
| 14 | 0.10-0.11 | Vegas Be a GM: a whole season, the playoffs, the draft of 32; a computer trade left Seattle with 19 dressed and the next sim crashed in the line picker | P (0.11) |
| 15 | 0.11 | season 2 crashed on 2 Oct 2027 in the game-day step; Anaheim / Calgary had no games in season 2 | Q (0.12), R (0.13) |
| 16-17 | 0.13 | season 2's calendar 32 x 80 NHL, 32 x 72 AHL; Vegas filled from Henderson, season 2 to 29 Oct 2027, send-down / call-up, Save and Exit | passed |
| 18 | 0.14 (84 games) | a new Be a GM crashed while loading (`0x381c24`, `LeagueFreeAgentsReader`: a free agent's player not found). Bisected: 80 games start, 82 / 84 crash, whatever the meta's `maxinsert`. Vegas's rights in a six-bit `cPbu.WBbd` crashed every new Be a GM too (round 42: that crash was the calendar's room, stage S, not the rights) | `cPbu` stayed five bits until 0.23 (`VEGAS_DEPTH`, `check_rights`); `fit_db` grows `nhlng.db`'s `ihmS` / `byED` to 1,345 rows |
| 19 | 0.14 | Be a GM with Seattle and 84 games starts (`BE A GM8`), but its calendar has 1,291 rows: the last 54 games (4-10 April) are missing, teams play 80-82 | the game's own room table (`0x1acc878`): stage S |
| 20 | 0.14 + S | roster `0206` made by `team32-test` (section 2,456,940); without the longer section the patched game called the roster damaged. A new Be a GM with Seattle (`BE A GM9`) holds 1,345 rows: 32 x 84 NHL, 32 x 72 AHL, the All-Star row. Simulated to 11 April 2027 with no crash: the league standings show **84 GP for all 32**, 16 teams marked for the playoffs (Utah and Vegas among them). The playoffs, the Cup, the draft of June 2027 (7 x 32), the off-season and season 2's calendar (32 x 84) followed; season 2's preseason crashed on 24 September 2027 (`0x1404a8`: the team rankings of 17 stats have room for 30) | stage T (0.15) |
| 21 | 0.15 (T) | from the autosave of 15 September 2027: 24 September passed, the regular season began. A hang on 18 October was the human team's own: Seattle had 15 players after the off-season (the game fills only computer teams; every computer team dressed 20); after six call-ups and Best Lines it played on. A second hang on 25 January 2028 (Vegas at Nashville, both computer teams): the game engine's lineup for Vegas held one Calgary skater, 15 Vegas skaters, two empty places and Seattle's two goalies, so the line picker `0x1528f8` found no one for a line and asked again forever | keep the human team at 20+ (notes/autoplay.md); engine hang open (section 6) |
| 22 | 0.15 (T) | replayed from the autosave of 22 January 2028 with a scratch sampler of the engine's lineups (723 lineups, none with an empty place): 25 January passed, the rest of season 2 played, the standings show **84 GP for all 32**, the playoffs (Stanley Cup Winnipeg, Calder Cup Chicago Wolves). The off-season to the draft of 23 June 2028: the board showed NHL shields and names twice in 14 first-round places and the draft crashed as Seattle's auto-pick began (heap allocator `0xc9bc18`). The save's `leaguedraftpick`: year 2028 (117) had lost picks 0-13 of round 1 to the June 2027 new year, whose keys ran into 2028's (key = (year mod 6) x 210 + number) | stage U (0.16) |
| 23 | 0.16 (U) | a new Be a GM with Seattle (`BE A GM10`). The pick numbers: 6 years x 224 at set-up, after the June 2027 draft and after season 2's new year (13 Sep 2027), none doubled, every one on the rule. Seattle filled to 18 skaters + 2 goalies by call-ups. Season 2's first preseason day (14 Sep 2027) hung in a computer team's game: the engine's lineup for Vegas had every line place unset and no second goalie (Vegas had one goalie on its roster after the new year; Obvintsev of Vancouver's organisation in the lineup), so the line picker found no one. Replayed from the 13 Sep autosave: passed (to 16 Sep). At the new year the computer teams took stars off their rosters while keeping their contracts (McDavid, Kyrou, Thomas: no roster; Kaprizov, Nugent-Hopkins, Ekholm: the farm) | engine hang open (section 6); the stars: notes/salary-cap.md |
| 24 | off | every NHL Legacy entry off, no loose db files, the community roster `0204`: a new Be a GM with Seattle to the new year (15 Sep 2016). The stars stayed on their NHL rosters; the organisations grew by contracts as in round 23 and the cap was the same. At the new year the game moved mostly 20-24-year-olds (99 of 167 NHL rows), 7 of 425 aged 25+; round 23 had counted 389 NHL players 19 or younger (130 moved). The calendar showed Home / Away marks. The patch roster `0205` with the patch off crashed a new Be a GM (heap, `0xc9a5d4`) | year 0.5: birth years on the league's clock (`year_shift`), the age word `0x16320c` |
| 25 | year 0.6 + 0.16 | a new Be a GM with Seattle (`BE A GM12`) on the patch roster `0206`: Seattle 46-31-7 = 84 GP, the standings 84 GP for all 32, the playoffs, the June 2027 draft (7 x 32), the off-season, the new year of 13 Sep 2027 (`BE A GM13`); no crash. Ages right everywhere (Select Team's average 29.5, Contract Status). At the new year Edmonton, Minnesota, St. Louis and San Jose (the same four as round 23) still swapped 10-17 NHL players for farm players (San Jose's organisation was under the cap); the other computer teams moved 0-4 young ones. The patch roster held about 75 updated players ten years too old (Krug, Goodrow: `donors.real_birth_year`) | birth-year rule fixed (`TNEo`); the stars at the new year: open (section 6) |
| 26 | year 0.6 only (30 teams) | a bisect: every other entry off, no loose db files, the `year-test` roster `0207`, a new Be a GM with Anaheim (`BE A GM14`) to the draft of 23 June 2027, the off-season and the new year (14 Sep 2027, `BE A GM15`); no crash. **No team buried its stars**: Edmonton, Minnesota, St. Louis, San Jose moved 4-7 young players each, like the patch off. The Sep 2026 / Sep-Oct 2027 calendars had no Home / Away marks here too | the stars problem lies in the 32-team part, not the year entry (section 6) |
| 27 | 0.16-0.17 + year 0.6 | the full patch, roster `0206`, a new Be a GM with Anaheim (`BE A GM16`). Computer-run Vegas fell to 16-17 players by November 2026 (no call-ups for keys 30 / 31) and a sim hung in the line picker (runs 6-10); with V (run 11) Seattle and Vegas held 22-24 to the end of the season, the playoffs and the June 2027 draft passed. At season 2 (E1, V on) 26 of 31 computer teams lost more than a third of their NHL-row pay to the farm. Probes (E5 / E6): season 2's preseason began on 12 Sep 2027, before the new year of 11 / 13 Sep; every team counted 6 of 7 games and the final cut (`0x1ca618` mode 7) never ran. E7 (`byED` a week later, new `0206` from `team32-test`, the 13 Aug 2027 save): season 2 opened on 6 Oct, all 31 computer teams got the cut; 0 teams lost a third of their pay (E4 unshifted: 6), 26 farm players over $3M (E4: 138), those sent down rated below those kept (39.5 / 44.5). Also the intro skip: Press Start at once, one press to the main menu, a game, a second boot | V (0.17), `FUTURE_DAYS` (0.17), the two intro entries |
| 28 | 0.17-0.18 + year 0.6-0.7 | Be a GM with Anaheim from the 10 Oct 2027 save: season 2 to the end (84 GP), the playoffs, the June 2028 draft (7 rounds, all 32), no hang. Be a Pro: Edmonton's Dach (`DACH1`) loaded and played a game. Seattle's Catton crashed while loading, twice: first the job list's 9th job (executing `0x20e5d70`), then `0x1c0098` (his team was -1: on Coachella Valley, key 62, which the team query's "below 60" left out). With both fixed the career loaded and saved (`CATTON2`), the preseason began. Be a Pro's texts said "GREEN / RED organization": the roster's team table still held the game's All-Star names for slots 30 / 31. After the names fix (`0206` given `NAMES_2026`): `CATTON2` reloaded after a restart, played a preseason game (Kraken at Calgary), saved again; a **plain Season mode** with Vegas (`SEASON8`): Select Team showed Seattle Kraken / Vegas Golden Knights in an 8-team Pacific, the season simulated to 11 April 2027 with **84 GP for all 32**, the All-Star game and the trade deadline passed, 16 teams in the playoffs, Minnesota beat Florida 4-2 for the Cup, the awards on 4 June; no crash, no hang | year 0.7 (job list), W (0.18), `NAMES_2026` (Utah / Seattle / Vegas named in the patch roster's team table) |
| 29 | 0.19 (X) + year 0.7 | the lab roster patched by `cli update --game-patch --in-place` (the real contracts in dollars), a new Be a GM: Select Team and Contract Status show the cap $104.0M and the real deals; the "not salary cap compliant" question (Yes: the computer fixes the teams). Simulated through the June 2027 draft to 5 Oct 2027: no team lost a third of its NHL pay; the game lifted its cap to $107.235M and the floor to $80.135M itself (the highest payroll beat the 0.19 table's rise) | the real cap per season: X v2 (0.20); the season labels (year 0.8) |
| 30 | 0.20 (X v2) + year 0.8 | the lab roster `0206` updated in place with the 82 contract players kept, a new Be a GM with Detroit (`BE A GM24`): Select Team and Contract Status show $104.000M, the columns read "26-27 / 27-28" and "2027-2028", Larkin on Detroit at $8.700M; memory: floor $76.9M, cap $104.0M, lowest $850,000, rookie maximum $1,025,000. Season 1 to the June 2027 draft (Detroit 35-37-12 = 84 GP), the draft (auto, 7 rounds). After season 1 the game's table moved to **2027-28: cap $113.5M, floor $83.9M, lowest $900,000, rookie maximum $1,075,000** (no lift: no payroll above $113.5M); Contract Status in the re-sign phase: "Salary Cap $113.500M", columns "27-28 / 28-29", deals at the old minimum raised to $0.900M; the hub "2027-2028 Season". Past the new year (14 Sep) and the opener to 12 Oct 2027 (`BE A GM25`): every NHL team 22-23 on its NHL roster, payrolls $84.3M (Detroit, human) to $112.3M, **no team lost a third of its NHL pay** against the start (one, Pittsburgh, at the 13 Sep autosave, back by 12 Oct) | passed |
| 35 | 0.20 + probes Y, Y2, W2 (= 0.21) | a patch roster with 234 / 235 in the AHL's Pacific (`league_probe.py`), the text file re-keyed to the game's hash: Play Now's AHL list of 32 with Coachella Valley / Henderson named and with their crests, Custom Teams without them, Henderson at Coachella Valley played; Be a GM with Seattle to 30 Oct; Be a Pro with Seattle's O'Brien (NHL roster) crashed while loading, W2 fixed it (docs/notes/lab-round-35.md, league-menus.md) | passed with W2: stage Y and `0x458ec8` in 0.21 |
| 36 | 0.21 through the program (`game-patch install`, `update --photos` from the lab's community roster) | Play Now: AHL of 32 with Coachella Valley FIREBIRDS / Henderson SILVER KNIGHTS (names, crests), Custom Teams without them; Be a Pro with Vegas's Demek (NHL roster) loads, the GM's office names "our AHL affiliate, the HENDERSON SILVER KNIGHTS". `game-patch remove` + `update --in-place`: the roster turned back (234 / 235 in Custom again) loads unpatched, AHL of 30, both under Custom. Found: the turn-back kept Seattle's / Vegas's names and divisions in slots 30 / 31 (`PATCHED_TEAM_FIELDS` lost them), fixed (docs/notes/lab-round-36.md) | passed |
| 41 | 0.21 + the list-walk cave (= 0.22) | the owner's report: Team Rosters (Vegas) CONT / SAL "N/A" for Eichel, Hanifin (the roster's contract status `QwoG` 0, not the patch: `contracts.status_fit`), Roster Management's AHL without Coachella Valley / Henderson (the list walk ended at slot 223 on a roster from the game's own): AHL of 32 with both; contracts and contract edits in Team Rosters, a new Be a GM (UFA / RFA by `zKKG`: `contracts.ufa_fit`) and Be a Pro Central (docs/notes/lab-round-41.md) | passed |
| 45 | 0.23 + the news entry (= 0.24) | the entry ticked next to the lab's test entries: RPCS3 applied it, the game booted to the main menu (signed out); with `PROMO` '#4' in a copy of the lab's `nhl_eng_us.db` the news panel said "Updates, patches, statistics! Join us on gg.puckpeak.com". Signed in (the owner's the community server setup) not played (docs/notes/lab-round-45.md, promo-texts.md section 5) | passed signed out |
| 42 | 0.23 (six-bit rights) | a patch roster with six-bit player rights (`cPbu.WBbd`) and the db description at six for both proteam fields loads; Henderson = the source's 28 with their deals, rights Vegas; a new Be a GM with Vegas lists Henderson In the System, a call-up / send-down swap, computer GMs trade for Henderson players; the season to the end (Vegas 45-32-7, 84 GP), the June 2027 draft (32 teams, 7 rounds), re-signing and free agency to 31 July 2027 (ordinary signings, the 2027-28 cap $113.5M); no crash (docs/notes/lab-round-42.md) | passed |
| 58 | 0.26 + one word, then a narrower cave | which number names the centre-ice file: the home team's attribute `+0x7c`, read at `0x15a0d04`, is what the game shows; the arena table's `centericelogo` is not read; a roster `arenaartid` with no stadium files crashes. One word (art instead of `+0x7c`): Berlin showed its own crest, Canada a plain blue square (no file on the disc) (docs/notes/lab-round-58.md) | **not in the patch** (owner, 2026-11-01): DEL clubs keep the shared ice; the words are kept in the note |

## 4. Reading a crash

- RPCS3 writes the crash into `RPCS3.log`. Read it with full sharing while RPCS3 runs (CLAUDE.md).
  - The **call stack** is the most reliable part.
  - The PC it names is often the return point after the last call, not the faulting instruction.
- The thread context prints every register with the 8 bytes it points to. Under the LLVM recompiler the registers can
  **lag** the faulting instruction. A call forces them out first: syscall 24 is a null syscall that logs r3-r10 as
  "Unimplemented syscall ... -> CELL_OK" and lets the game go on. Use it in a detail entry when the values matter.
- **The game's heap** is dlmalloc-like:
  - heap state at `0x60000080`, in a `sys_memory` area at `0x60000000`;
  - a block's size word sits at block - 4: bit 0 = the one before is in use, `0x40000000` = in a large bin;
  - free blocks link fd +8 / bk +0xc, large ones also +0x10 / +0x14;
  - malloc `0xc9a720`, free `0xc9b588`, unlink `0xc995a8`.
  
  A crash in there is almost always an earlier overrun. The fingerprint of rounds 7-9 was a size word of 0x10-0x13 and a
  link of 20-31: team numbers written over a block's head.
- **Finding the writer:** look for tables sized for 30 teams. Search for `0x1e` or 30 x record size, and for 0x168, 0x258
  or 0x93a8. Then look for loops that run to a count from the League (+0x29c, now 32) or that add rows without a limit.

## 5. Adding or changing a stage

1. Read the code in the decrypted ELF. Ghidra or capstone, outside the repo (notes/re-workbench.md). Every claim goes into
   notes/patch-design.md, round by round.
2. Add the words to `gamepatch.py`:
   - a change is `(address, the game's word, our word, why)`, our word made with `_imm` / `_li` / `_ds` from the game's;
   - a cave is `(address, the game's word, [(word, what)], why)`, with the game's word last when it can run as it was;
   - a new stage goes into `TEAM_STAGES`;
   - bump `TEAMS_VERSION`.
3. `python tools/audit_patch.py <EBOOT.ELF>` must report 0 problems. It checks every game word against the ELF and shows
   both instructions.
   - Then `python tools/port_patch.py --write <1.00 ELF> <1.01 ELF>` finds the new or moved words in update 1.01 and
     writes `legacy_roster/patch101.py`.
   - Audit the 1.01 ELF too (0 problems). Decrypt it with scetool, as notes/update-101.md describes.
4. Tests: `tests/test_gamepatch.py`, with `LEGACY_ROSTER_DISC` set to the EU disc image (the .iso, not its folder).
5. Write the lab's patch file (RPCS3 closed), add the round to the lab README, and let the owner play it.
6. Update this file's table and AGENTS.md.

## 6. Open items

The full list of what the 2026-27 season still lacks, with a status per item: [notes/2026-27-gaps.md](notes/2026-27-gaps.md).
What the patch itself leaves open:
- **All-Star game (stage J): played** (rounds 12-13, 20). The Season picks the All-Stars itself at the break
  ([notes/all-star.md](notes/all-star.md)); the game is played in EASHL 1 / 2's places (slots 220 / 221, art 30 / 31).
  Open: the All-Star teams wear EASHL's jerseys and logos; Seattle / Vegas get no guaranteed All-Star (`0x455b00` loops
  over 30).
- **The draft for 32 (stage K): played** (rounds 14, 20): 7 rounds x 32. The lottery draws among all 16 teams that miss
  the playoffs (the owner's wish, `LOTTERY_ODDS`; the NHL has two draws and a 10-place limit). The draft board shows 30 rows
  per round. About 15 loops of 30 in Be a GM's object are left ([notes/draft.md](notes/draft.md)); none has shown.
  The second draft needs stage U (pick numbers of 32); a Season or Be a GM started before 0.16 keeps the doubled numbers
  and its second draft will crash.
- **Team rankings (stage T):** each of the 17 team-stat rankings keeps 30 teams (the game's room); two teams are left out
  of each list.
- **Farm league of 32 (stages L, M, O): played** ([notes/keys64.md](notes/keys64.md)). Open: the standings rank builder
  `0x298b18` ranks keys 0-29 and 30-59 as two groups (Seattle / Vegas and farm keys 60-63 may get odd ranks, no overflow);
  `0x366424` and `0x1311e8` are not checked; Abbotsford shows Utica's logo, Tucson Springfield's.
- **A human GM keeps their own roster filled.** The game fills only the computer teams; a human team under 18 skaters /
  2 goalies hangs its next game in the line picker (round 21). This is the game's own rule.
- **A rare hang in a computer team's game (rounds 21 and 23; a replay of the same day passed both times).** Both times
  Vegas's lineup in the game engine was wrong and the line picker `0x1528f8` looped on `0x32cda4` while a team's
  candidate count (engine `+0x4674`) was 0:
  - round 21 (25 Jan 2028): a Calgary skater and Seattle's goalies in Vegas's lineup, two places empty;
  - round 23 (14 Sep 2027, season 2's first preseason day, patch 0.16 so not the doubled pick numbers): all 80 line
    places unset, no second goalie, Vancouver's prospect goalie Obvintsev in the lineup. Vegas had one goalie on its
    roster after the new year.
  Where the wrong players come from is not known: old places left from an earlier game, a computer move that day, or a
  loop of 30 / 31 not found yet (Vegas is team 31 both times). The engine object, its record layout and the scratch
  samplers are in [notes/autoplay.md](notes/autoplay.md). A guard that leaves the loop would need the code after it to
  cope with no candidate; not designed.
- **Stars on the farm in season 2: found and fixed (0.17, round 27).** At season 2's start computer teams kept stars
  under contract but put them in the farm or on no roster (rounds 23, 25; E1 of round 27 with stage V: 26 of 31 teams).
  Two causes:
  - The age (fixed in year 0.6): the computer GMs count it from the league's own year, so the roster keeps birth years on
    the league's clock (real - 1911, `year_shift`) and the year entry corrects the two date-based ages (`0x16320c`,
    `0x3721a4`).
  - The calendar's timing (fixed in 0.17): the preseason routine `0x28b75c` puts every player on the farm and picks
    NHL rosters at random before each preseason game; its final cut (commit `0x1ca618` mode 7, which runs the roster
    planner) comes when a team has played all but one of its preseason games. The new year is fixed on 11 September and
    the preseason starts 17 days before the opener (`0x284b80`). With the real calendar's opener of 29 September season 2's
    preseason began on 12 September 2027; its first day ran in the old year and was not counted, so no team reached the
    final cut and the random rosters stayed all season. `future_fit` now stores the next seasons' calendar a week later
    (`FUTURE_DAYS`; same weekdays): season 2 opens in early October, the preseason starts after the new year.
    **Round 27, run E7:** all 31 computer teams counted 7 of 7 preseason games and got the final cut (none in E5 / E6).
  Details: [notes/gm-brain.md](notes/gm-brain.md) "The preseason roster routine", [notes/2026-27-gaps.md](notes/2026-27-gaps.md)
  "Round 27".
- **Be a CHL Pro with an undrafted junior crashes (round 44, 0.23, not fixed).** The career has no next game ("Play
  Next Game" greyed) and crashes on the first simulated day; a drafted junior and the unpatched game are fine. Such a
  career fills all 128 team keys (NHL 0-31, AHL 32-63, All-Stars 64-65, Top Prospects 66-67, CHL 68-127); the unpatched
  one uses 124, a drafted junior's 126. Crash sites: the front-end team list `0x12865c` (its no-Season path `0x128830`
  -> `0xdc5c48`, a read of 0x3) and `0x164cf0` -> `0x28cb30` -> `0x241044`. Guess: something of 128 indexed by key + 1,
  or a constant that puts the CHL at 64. Needs a round of its own with GDB; details in
  [notes/lab-round-44.md](notes/lab-round-44.md).
- **Smaller, no memory risk found:** `0x3bdd18` gives Seattle / Vegas Anaheim's staff tuning, `0x38fb94` team 29's
  computer-GM settings; StaffLogic's 30-loops `0x3bb500` / `0x3bb7a0`; WaiverBrain's claim list (30 words) overflows only
  if 31 teams claim one player; Vegas's rival is Vegas, Seattle / Vegas `artabbr` is EAS / WES.
- **Not played:** switching the patch off and loading old saves. Online play through the community server with the patch
  and the "no online login at boot" entry on works (the owner, 2026-10-18).
- **Round 28 (2026-10-16, 0.17, Be a GM with Anaheim, lab save from 10 Oct 2027):** season 2 simmed to the end, 84 GP
  (Anaheim 35-44-5), the playoffs, and the **June 2028 draft**, which crashed before stage U: the board showed all 32
  teams, Auto Draft ran all 7 rounds, "The NHL Entry Draft is now complete", back to the calendar. No hang in the
  whole season (the rare engine hang of rounds 21 / 23 did not come back).
- **The NA version** (`BLUS31540`, 2026-10-15): the same code, its own PPU hash (`gamepatch.NA_HASH`); `patch_text`
  writes both blocks, `cli team32-test --version NA`. Lab: all 25 entries applied, Be a GM with Vegas simmed to
  mid-November, saved and reloaded, no crash ([notes/na-version.md](notes/na-version.md)). Not played as far as EU.
- **Later seasons open a week late** (0.17): season 2 and on start in early October, not late September (the price of
  the stars fix; season 1 is the real calendar).
- **Phase D (built 2026-10-15, not played):** section 7.
- **Later (the owner's picks):** the salary cap of 2026-27 (no field found; the game raises its 2014 cap by itself each
  summer), 3-on-3 overtime.

## 7. The exe patches the game (Phase D)

Built 2026-10-15 (plan [plans/zazzy-leaping-stearns.md](plans/zazzy-leaping-stearns.md)); tested offline, on a fake
RPCS3 and **played in the lab through the exe's own path** (below).

- **Window (since 2026-10-18, owner's wish; plan [plans/sunny-nibbling-goblet.md](plans/sunny-nibbling-goblet.md)):**
  its own **step 2** "32 teams and the year 2026 (game patch)", above the roster list (roster 3, steps 4, save 5). It
  says whether RPCS3 is patched (`patchinstall.state`), has **Patch the game** (a question the first time,
  `PATCH_ASKED`; "Patch again" when the patch file is older than `TEAMS_VERSION`; "Patch NA too" when one version is
  missing), **Unpatch**, and the switches "Skip the intro" (on) and "No pop ups at start" (off; "No online login at start" before 0.21.0), always shown and
  put into a patched RPCS3 at once (`patchinstall.set_switches`). Patch puts the patch into every version RPCS3 lists.
  `app/update.py`: `patch`, `unpatch`, `set_patch_switch`, `_patch_view`; rows made for the patch carry the tag
  "32 teams". **Restore default** also unpatches (`restore.PATCH`). The Roster editor shows a patch roster but does
  not save it. `tools/window_shot.py patched` draws the step.
- **The update follows RPCS3:** `pipeline.update(game_patch=None)` reads `patchinstall.patched_titles` for the versions
  it saves for: all patched, a patch roster (and `refresh_db` makes the db files again when the program's data has
  newer calendars); none, a normal roster; mixed ("Save for" EU + NA, one patched), refused. A patch roster picked
  while the game is unpatched is **turned back** (`gamepatch.unpatch_roster` with the game's own roster of that version,
  `restore.default_slot`): the game's calendars and their room (`Table.shrink`), the section size, the team fields
  `farm_fit` / `divisions_fit` / `all_star_fit` wrote (`PATCHED_TEAM_FIELDS`); years are unshifted and money rescaled
  as before. A turned-back roster counts as a normal one for the stale-years guess, so its second run is
  byte-identical.
- **Patch without a roster:** `patchinstall.install_patch(roster=None)` makes the db files' next-season tables from
  `calendar_roster` (the game's own roster from the disc + `schedule.ALL_PATCH` + `farm_fit` + `future_fit`, the same
  calendars every patch roster made from that data pack holds).
- **The game's own roster for the patch:** slots 234 / 235 (Coachella Valley / Henderson, "Custom Team 12 / 13",
  switched off on the disc) are switched on (`NYKk` 1) on a patch build, so the AHL step fills and names them (the
  AHL's real rosters; Henderson's players hold Vegas's rights since 0.23). A farm club still short of `FARM_DEPTH` under
  its parent's rights gets its youngest players without NHL rights signed to two-way deals (`rights_fit`; San Diego's
  contract D are on Anaheim in the data).
- **Command line:** `game-patch install [--skip-intro] [--no-login] | status | remove --rpcs3 <rpcs3.exe>`; `update
  --rpcs3` follows RPCS3; `update --game-patch` patches first, then updates; `export-roster --for-patch`.
- **One switch for players:** `gamepatch.PLAYER_ENTRY` ("NHL Legacy 32 teams and the year 2026") holds the year entry's
  and stages A-V's patches in the lab's order (`player_patch_text`; a test checks it equals the 25 lab entries), plus
  `INTRO_ENTRY` / `LOGIN_ENTRY` (the window's two switches) and `NEWS_ENTRY` (always ticked with the patch,
  `patchinstall._wanted`). The lab keeps `patch_text` and its "(test)" names.
- **RPCS3's side** (`patchinstall.py`): `patches/<TITLE>_patch.yml` (a file there that is not ours is kept and comes
  back) and our lines in `config/patch_config.yml` (else the old `patch_config.yml`), edited as text: only the lines of
  our entries under our PPU hash change, the rest stays byte for byte; entries the file already had under our names
  (ticked by hand, or the lab's) are remembered before the first change (`patch/config_before.json`) and come back where
  they were on Unpatch (`entries_before`, `config_restored`); a copy of the file is kept in
  `%LOCALAPPDATA%\NHLLegacyRosterUpdater\patch\backup`. The db files go into each version's game folder with their own
  list and kept copies (store `patch`, `art/install.py` stores); "Restore the game's own pictures" no longer touches
  them (db files the 32-team test put in the pictures' list are moved over). Refused while RPCS3 runs or without the
  game disc (the db files are made from it; EU and NA have the same files).
- **The roster** (`pipeline.update(game_patch=)`): the calendar and AHL steps run too, `schedule.ALL_PATCH`, then
  `patch_roster` (year_shift, farm_fit, divisions_fit, all_star_fit, future_fit, section_fit, rights_fit) and
  `verify(farm_patch=True)`. Two things the lab roster never needed:
  - **Vegas's rights** (patch 0.23, lab round 42): the roster's `cPbu.WBbd` gets six bits (`gamepatch.rights_wide`,
    in `pipeline.build` when `game_patch` and in `patch_roster`; `tdb.Table.widen` moves the fields after it), and the
    patch's `db/nhlng-meta.xml` describes the same six bits (`META_TEAMS`). Henderson's players hold Vegas's rights as
    every farm club's hold its parent's (`rights_fit`, `check_rights`), so a computer-run or human Vegas calls up from
    Henderson. Until 0.22 Vegas kept a farm club's depth on its own NHL roster (`VEGAS_DEPTH`, 18 F / 8 D / 3 G,
    `Builder.vegas_depth`, gone) and Henderson was topped up with free agents (Toews, a 95-rated Sewell). A roster made
    for 0.22 (five bits) under 0.23's db files reads as damaged: the window marks it ("Made for another version of the
    game patch", `UpdateController.misfit` against `patchinstall.installed_rights`) and offers the update. Turned back
    for the unpatched game, the rights get five bits again (`rights_narrow`: Vegas's go).
  - **A second run is byte-identical** (rule 4): a patch roster is unshifted first (`gamepatch.unshift`), and a patch
    roster's first build mends the game's ten-years-off birth years before anything else (`gamepatch.mend_years`, no stale
    guessing after it), so the first run sees what a re-update sees. Without it a namesake's 2005 draft and list ratings
    matched only on the second run.
- Until 2026-10-18 a patch roster with the row off was refused; now it is turned back (above).
- **Played in the lab (2026-10-18, step 2; `cli game-patch install --skip-intro`, `update --source disc:EU`, lab test
  entries off):**
  - (a) The game's own roster made for the patch ("R32 OWN PATCH") loads. Be a GM with Seattle (Select Team: 26
    players): Coachella Valley is its farm club with its real AHL players (Hayden, Olofsson, Kokko); simulated to
    15 Nov 2026: Seattle 6-10-2, Coachella 4-10-1; Save and Exit. Be a GM with Vegas (29 players): farm Henderson,
    15 Nov 2026: Vegas 12-6-3, Henderson 9-4-1. No crash line. No call-up was made by hand (the phone boxes were
    answered by the driver).
  - (b) `game-patch remove`, then `update --source <that roster> --in-place`: "This roster was made for the patched
    game. The new one is for your unpatched game". The unpatched game (no entry applied) boots and loads it with no
    "damaged" box; Season shows 30 teams, the year 2015-16; Anaheim simulated to 15 Oct (5 games), no crash.
  - (c) Patched again; the lab's unmodified community roster updated to a new patch roster "R32 COMMUNITY": loads,
    Season shows 32 teams, Vegas simulated to 22 Oct 2026 (6-4-1), no crash.
  - Seen, not new: Select Team says "AHL Affiliate: Free Agents" for Seattle / Vegas, and the hub's title for
    Coachella / Henderson repeats the name in capitals (the same on the older community patch roster 0206).
- **Played in the lab (2026-10-15, `cli update --game-patch --skip-intro --offline`, from the lab's community roster):**
  - EU: only our 10 lines added to `patch_config.yml`; RPCS3's log: "NHL Legacy 32 teams and the year 2026" and "skip
    the intro" applied (495 patches); the roster "EXE PATCH EU" loads; Be a GM with Vegas (Select Team: 29 players,
    "AHL Affiliate: Free Agents", the usual salary cap question) simulated to 15 Nov 2026: Vegas 10-10-1, all 32 teams
    18-21 games played, Save and Exit, no crash line.
  - A second update of that roster in place: "Already up to date" (byte-identical).
  - NA (`--for NA` from the EU patch roster; the same SYS-DATA): both entries applied under NA's hash, "EXE PATCH NA"
    loads, Be a GM with Anaheim simulated to 22 Oct 2026, no crash line.
  - `game-patch remove`: patch files and db files back byte for byte; the first try dropped two lab entries that had our
    intro entries' names (fixed, test `test_entries_of_our_names_that_were_ticked_before_come_back_where_they_were`);
    after the fix a patch / unpatch cycle leaves `patch_config.yml` byte-identical.
  - Smoke test of the built exe: a patch dry run from a lab `team32-test` roster stopped on "Henderson dresses 19":
    Vegas's depth (until 0.22) took five Henderson players, the AHL step kept a junior (Nobert) to fill the forwards and the CHL step
    then took him to Halifax. Fixed for every update: `clubs._fill_lineup` never uses a player another league lists
    (`b.league_rows`); test `test_a_player_who_fills_a_line_up_stays_there`. Also `Builder.depth` (donor levels) and the
    Vegas depth record shared a name: the record is now `Builder.joined_depth`.
  - Seen, not caused by the patch: a roster saved as new got folder `...0210`, which the game never lists (it lists
    `0200`-`0209`; ROADMAP "capacity facts", owner to decide); wrong letters in some menu words after a long sim (as on
    NA before: an emulator text-cache slip). Not shown in the lab: an unpatched boot (the lab ticks its own "(test)"
    entries).
