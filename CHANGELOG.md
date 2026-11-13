# Changelog

What changed in each version, for players. Developers: details in [AGENTS.md](AGENTS.md)
("Current state") and [docs/ROADMAP.md](docs/ROADMAP.md).

## 0.98.1 (2026-11-13)

**Play NHL Legacy.** A green button at the top right starts the game: in RPCS3 it boots NHL Legacy straight away, on
NHL Legacy Native it opens the launcher (press PLAY there). It stays grey until you have found your game in Setup.

**The other Puck Peak apps.** At the top left: Overtime (NHL 19) and Faceoff (NHL 27). Point at one to see what it is,
click it to open its page. Blueline, the app you are in, is lit and says "You are here".

**The same look as our other apps.** Switches and ticks are green when on. The bar at the bottom shows progress only while
something runs, and a green tick when all is ready. Delete and Restore default stay grey until you point at them. Setup
says it shorter: ticks for what is downloaded, "2 used · 8 free of 10 save slots", "Up to date" next to "Check now", and
Discord and Ko-fi sit at the bottom, under your rosters.

## 0.98.0 (2026-11-13)

**New name: Blueline.** The program is now called Blueline, brought to you by Puck Peak, with a header like Overtime's, our NHL 19
app. The Windows program is `BluelineLegacy.exe` (Linux: `BluelineLegacy`). Your settings, edits and backups stay where they were, and
an older copy updates itself to the new version as before.

**NHL Legacy Native 1.0.1.** The game patch (32 teams, the year 2026) now works on the new version of NHL Legacy Native as well as
on 1.0.0. If you patched 1.0.0 and then updated NHL Legacy Native to 1.0.1, the Game patch tab says so: press Patch again. Rosters,
pictures, team names and the editors work on 1.0.1 as before.

## 0.97.1 (2026-11-10)

**Sharper jerseys, crests and centre ice.** The jerseys, the Select Jerseys pictures and the logos on them were being shrunk and
stretched several times on the way into the game, which made crests (HV71's, for one) look blocky and blotchy. Each picture is now
made once, straight from its full-size original, and stored without quality loss; the colour compression the game's file format needs
is done more carefully; the centre-ice logo and the player photos are drawn more cleanly too. The game's own jersey files are a fixed
size, so this is the best they can show. The jersey pack is bigger to download (about 157 MB instead of 94 MB), and the first update
after this version redraws the jerseys once, which takes a while.

The pictures step also holds less in memory while it installs the photos. If it ever stops with "MemoryError", close other big
programs (another emulator, for one) and press Update again.

## 0.97.0 (2026-11-09)

**A new Multiplayer tab, in three columns.** Left: you and a short checklist (roster, game patch, server, RPCS3 version), each
with the button that fixes it. Middle: host a lobby or join one with a code, the public lobbies, then the two players, Ready,
chat and what to press in the game. Right: your rating with a bar to the next tier, and your matches, stats, box scores and the
leaderboard. On a smaller window the right column moves below the other two.

**Real lines every day.** The real line-ups (NHL and Extraliga) are now refreshed every morning on our server, so each Update gets that day's lines; no new version is needed for them.

**Community centre ice switched off for now.** It showed a grey square around the logo for some players. Its switch is greyed out
and cannot be turned on; your next update with pictures puts the game's own centres back where it had laid them (or this season's,
if that switch is on). It comes back once it is fixed. **This season's centre ice** stays and now also gives the national teams
their IIHF centre ice (before, that came with the community switch).

**Fixed: "wgjx: table full (749)" when updating for the patched game.** A roster that version 0.92.0 had updated for the
32-team game could not be updated again: its list of jersey versions was full, and the Penticton Vees (new in 0.95.0) need two
more. The program now takes out as many of the third jerseys it added earlier as it needs, starting with the clubs of the
smaller leagues, and the List of changes names those teams. Nothing was saved when the error came, so no roster was damaged.

## 0.96.0 (2026-11-05)

**Fixed: NHL Legacy Native forgot that it was patched.** After you patched the port and started the program again, it said "not
patched" and marked your roster as not fitting. The program looked in RPCS3's list instead of the port's. It now looks at the port's
own list from the first moment. RPCS3 was never affected.

**Players made by the program now have a fitting face.** New players (for example the Japanese national team, or a player the
leagues list that the game does not have) were all given a light-skinned head. The program now picks the skin from the player's
photo (a simple colour check of the face, no graphics card needed). Players without a photo get a skin by country where that is
clear (Japan, Korea, China and others). Players who already had a head that does not fit their photo get a fitting one. Real
scanned faces and faces you edited yourself are never touched.

**Two centre-ice switches instead of one.** In step 4 there are now **This season's centre ice** and **Community centre ice**, next
to "This season's jerseys". Use one, or both: the one you switch on second is laid on top of the first, for the teams both have.
Your own centre ice (Jerseys & ice tab) still wins over both. The community centre ice is the newer set and has the ice colour
under the logo, which should remove the square seen around some centre logos. Each switch has its own Restore. A settings file from
before turns both on together with the jerseys, as before.

**The little arrow on the Photos and logos row is bigger**, so it is clear that the row opens.

**What to do:** nothing. The new centre-ice set and the skin data arrive as downloads.

## 0.95.2 (2026-11-04)

**Fixed: Be a CHL Pro crashed at the start of a career in the patched game** (32 teams), on RPCS3 and on NHL Legacy Native. The game
has room for 128 teams in a Be a Pro career, and a junior's career with the 32-team patch needed exactly 128, one of which the game
reads as "no team". Game patch 0.27 leaves the two Top Prospects teams out of Be a Pro careers, so everything fits. A Be a Pro career
no longer has a Top Prospects game. Season mode and Be a GM are not changed.

**What to do:** open the program and press **Patch again** on the Game patch tab (RPCS3 and NHL Legacy Native). A Be a CHL Pro
career started before the fix still crashes: start it again after patching. Other careers keep going. To play online, both players need this version.

## 0.95.1 (2026-11-03)

**Fixed: "The new roster failed the safety checks ... free agent Nick Jensen is also on Knights".** On a roster that began as the
game's own, the program treated custom teams 222-233 as copies of NHL teams, as they are on the community roster. A player who
left his NHL team but was also on one of those custom teams went onto the free-agent list and stayed on the custom team, and the
safety check stopped the save. He now keeps his custom team place. Also, if any step ever leaves a player on a team and on the
free-agent list, the program takes him off the list by itself (the List of changes says so) instead of refusing to save.

**Fewer refused updates on rosters other people made.** When an update leaves something behind that the safety check would refuse
and that has one safe answer (a player listed twice on a team or on the free-agent list, a player on two clubs, a contract naming
the wrong team, an NHL player with no contract), the program now puts it right itself and lists it under "Repairs" in the List of
changes. Problems the roster already had before the update are still never held against it.

**Fixed on the community's 26-27 roster:** the update stopped with "Devon Toews on [7, 31]" (slot 31 there was still the All-Star
team "Black / Blue", holding players of other NHL teams). A player on NHL.com's roster now leaves every other NHL team. Also: a club
player whose birthday differs from the league's list is no longer doubled, Kopitar (on the Kings' copy only) retires at once, and a
club over 40 players lets young players its list leaves out go before a player the list names.

**Updating twice changes nothing.** A second update of a roster no longer moves Lukas Reichel (Providence) from left wing to centre.

## 0.95.0 (2026-11-03)

**NHL Legacy Native.** The program now works with the PC port as well as with RPCS3. Pick `NHLLauncher.exe` or the port's
folder in the same place you pick `rpcs3.exe`; the program works out the rest. Rosters, the Roster editor, careers, photos,
logos, team names, jerseys and centre ice all work. Your pictures go into a mod called "Puck Peak", so nothing of the
game's is replaced. If you have both, a link on the Setup tab switches between them. **The game patch works here too:** press
Patch and the port has 32 teams and 84 games in Season and Be a GM and the year 2026, as on RPCS3. It adds one small file next to
`NHLLegacy.exe`, and Unpatch takes it out. **Online play works on the port too**, with the patch on: the Play online tab works as
on RPCS3 (you type the name you play under), and NHL Legacy Native players and RPCS3 players play each other.

**Online matches stay in step.** The program's online setup for RPCS3 now uses RPCS3's exact maths, so a match against NHL Legacy
Native or between the EU and the NA game does not drift apart. Everyone in a lobby needs this version of the program: older versions
cannot join its lobbies.

**The Penticton Vees.** On the patched game the Vees are in the WHL in Play Now and Roster Management, with their real
roster, crest, jerseys and arena. Their 68 games are in the Calendar tab. Season, Be a GM and Be a Pro keep 22 WHL clubs, so
the Vees are not in careers and do not play in the game's own WHL calendar. On the unpatched game, RPCS3 or NHL Legacy
Native, they are at the end of the custom teams, as **Custom Team 30** in Select Teams (the game numbers every custom team there),
and from Starting Lineups on the game says Penticton Vees. A roster made from the game's own disc has no room for them
there, so it has no Vees unless the game is patched. The program's team list shows them under the WHL on every roster.

**Apply names.** The Team names row has a new button. It changes only the team names, in seconds: no roster is saved and no
picture is looked at.

**Real socks and pants.** With this season's jerseys on, every team wore Utah's socks in its own colours (one wide stripe,
too low) and nearly always black pants. Now each team wears its real socks and pants colours (the Leafs in blue pants, the
Bruins in black and gold socks with the white stripe). The Jerseys & ice tab says under each jersey where its socks and pants
come from. The program downloads this season's jerseys once more and makes them again at the next update.

**Goalie masks.** A goalie who moved to another team could keep the mask of whoever had his place before (Swayman in Boston
wore a red European club's mask). A goalie who changes team now wears his new NHL team's mask, or a plain one. Masks you
picked yourself in the Roster editor stay.

**Be a Pro careers of update 1.01.** The Be a Pro careers view said "This save is damaged or not complete." for every
career made with the game's update 1.01. They open and save now, on RPCS3 and on NHL Legacy Native.

**Unpatch on one RPCS3 no longer touches another.** If you keep two copies of RPCS3, Unpatch took the patch out of both.

## 0.92.0 (2026-11-01)

**The window no longer stays blank.** Some PCs opened the program to a window that was only blue or black and could not be
clicked. The page now says "Starting..." at once, and if it cannot start it says why, with "Try again", "Open the simple
window" and "Open the start log" buttons. The program also watches its own start: it reloads the page, then restarts without
the graphics card, and if that fails too it opens the simple window by itself and says why. Opening the program again right
after it ended could leave the window blue; every start now has its own browser folder. If the window cannot get one of its
files, it now loads itself again at once instead of staying blue. A PC that
names the program's files wrongly (a setting another program can change) no longer stops the window. The last 20 starts are written to
`start.log` (the button above, or `%LOCALAPPDATA%\NHLLegacyRosterUpdater\logs\start.log`), so a window that still fails can
be explained. If it happens to you, send that file.

**Alternate jerseys.** This season's third jersey is now in the game for nearly all of the 89 teams that have one (NHL,
AHL, OHL, WHL, QMJHL, Extraliga). Pick "Alternate" in Select Jerseys (and in the Jerseys & ice tab). Teams that had no
third in the game get one added. They come with the switch "This season's jerseys and centre ice". A team whose game
third has no counterpart this season keeps the game's own, and a few clubs whose jersey layout differs keep theirs too. If
you take this season's jerseys away later, an added Alternate shows plain blue until you start again from a roster without
it (the jerseys stop being there, the row in the roster stays).

**New rinks.** The 12 Swiss clubs and Björklöven have new centre ice, and all 21 national teams now share a rink with the
IIHF logo. They come with the same switch.

**Custom teams.** The Jerseys & ice tab of a custom team (Coachella Valley, Henderson, ...) has an arena name field like
the other teams. A colour typed there leaves Coachella Valley's and Henderson's hand-made jerseys alone; "Paint everything
with these colours" paints them too.

**The simple window** (the one the program falls back to) now follows the game patch and tells you why it opened.

**Real lines from the first update.** A team that took in a player under contract during an update played lines worked out
from the ratings until the next update. It now plays its real lines straight away.

## 0.91.0 (2026-10-30)

**Your own players are saved again.** A player made in the game's Create Player (or with another tool) could stop every
save with "head 20300 is not one of Create Player's head shapes". The game has 24 created heads, and its menu shows 15
of them; the program knew only those 15. Now every head the game has is fine, and anything your roster already had
(a head, a skin colour, a player's link, a team's logo or farm team) never stops a save.

**Contracts you set yourself are not checked against the program's limits.** The Roster editor's contract changes were
already free; a second check could still refuse them. It no longer does.

**Custom team colours stay.** Team colours typed on a custom team's kit (Coachella Valley, Henderson and the other custom
teams) are kept when you save, also without pressing "Paint everything". A piece you set by itself keeps its colour.

## 0.90.0 (2026-10-29)

**Edit your roster freely.** The Roster editor no longer refuses what the game itself plays. Add yourself, move anyone to
any team, release players, give a forward a defenceman's player type, fill a team to 40: Save keeps it. The program
only stops a save that would make the game say "The roster seems to be damaged" or crash it, for example a 41st player
on one team (the game's file holds 40 per team). If your changes leave a team with fewer than 2 goalies or 18 skaters,
Save still works and one gold line says so: the game hangs when you play a game with that team, so add players before
you play with it.

**Play online: ranks, chat and an overlay.**

- **Ranks and a leaderboard.** Every online match you play through a lobby counts. Both games report the score; when the
  two reports agree, the match is rated. Your rank shows after five games (Minor League up to Hall of Fame). The You card shows your tier and rating. Ranks has four views: your matches (opponent, teams, score, rating
  change), **My stats** (record, streak, best rating, goals, the last 7 days, your form, your rating over the last
  matches, and how you did against each friend and with each team), **Box score** (press a match: shots, hits,
  faceoffs, power play and more for both sides, as the games reported them) and the leaderboard, with a link to the board in your browser. The board shows RPCN names. "Show me on the
  leaderboard" takes yours off it.
- **A friend who leaves loses.** If your friend quits or disconnects and their game never reports, the match counts as
  their loss after an hour.
- **Chat in the lobby**, with six quick phrases (Good game, Nice one!, ...).
- **Result window.** After a match it shows the score and your rating before and after.
- **Over the game (Windows).** Your friend's chat lines and the result card show over the game window. Ctrl+Shift+F1 to F6
  send the six phrases without leaving the game. Switch it off on the You card ("Show chat and results over the game").
  To make the overlay visible, the program's online setup runs RPCS3 in borderless fullscreen instead of exclusive
  fullscreen.
- **"Roster broken" for the friend who joins.** The program now checks the host's roster against your own game before
  Ready. A roster for the patched game in an unpatched game (or the other way round) is refused, with a button to the
  Game patch tab.
- The You card lists what online play needs (roster, game patch, Puck Peak server, RPCS3 version), each with a button to
  where you fix it.

**Retired players retire.** Kopitar and other players who ended their careers no longer show up as free agents to sign
in Be a GM or Be a Pro. Unsigned players of last season aged 38 or more also retire. Careers you already started keep
whoever they signed.

**Jerseys, centre ice and crests go in with the Roster editor's Save.** Before, they only reached the game with an update.
Now Save puts in the pictures of the teams you changed (RPCS3 must be closed). Setting a team back to the game's own puts
the game's pictures back.

**Clubs of your own in slots 222 to 233.** On the game's own roster, the Roster editor, Lines, Strategy and Front office
treat those slots as the clubs they are, not as copies of NHL teams.

## 0.85.0 (2026-10-28)

**Linux: the game patch now switches on where RPCS3 looks for it.** On Linux (and Mac) RPCS3 reads its list of switched-on
patches from `~/.config/rpcs3/patch_config.yml`. The program wrote it into a `config` folder inside, which RPCS3 never
reads there, so after Patch the program thought the game was patched while RPCS3 ran it unpatched, and a 32-team roster
said "The roster seems to be damaged". If you pressed Patch with 0.80.1 or 0.81.0, the program moves the switches to the
right place by itself when it starts, so your 32-team rosters load. The Play online tab also finds your RPCN name on
Linux now.

The Windows program is now one file, `PuckPeakLegacyUpdater.exe` (the second copy under the old name is gone). Copies
older than 0.80.1 cannot update themselves to it: download it from the release page.

Fixes from a tester's roster with KHL clubs of their own.

- **"Not playable yet: Joe Sakic (COL): a cap hit of $0.000M".** The game itself had saved him on Colorado and on the
  free-agent list at the same time, and the program then cleared his contract. A player who is on a club now leaves the
  free-agent list and keeps the contract the game gave him. The List of changes names him ("taken off the free-agent
  list").
- **"1 not saved yet" stayed after Save as a new roster.** After that save, Setup picks the new roster and the team tabs
  open it, so your edits count as saved and the next ones go into it.
- **Export files to a folder from a roster file:** after "Or pick a roster file" the team tabs (Roster, Lines, ...) show
  that file, not the roster picked in Setup before (often the game's own 2014-15 roster). They never save into the file:
  your edits stay in My edits and go into the export.
- **Clubs of your own in the custom slots of the game's own roster** (a tester's KHL clubs) are treated as clubs. Before,
  the update moved a player from such a club to an AHL farm club ("Reilly Walsh is on two club teams"), and spare
  players copied from players you had moved between forward and defence got a wrong player type ("David ZZ has player
  type 4, which no forward has"). Both stopped the update.

## 0.81.0 (2026-10-28)

Fixes from testers' reports.

- **Better player photos.** The photo pack now has 765 new, sharper-coloured player photos (the NHL players' headshots from a
  new set). They are made to fit the game's portrait frame, and a long face is drawn a little smaller so the chin is never
  cut off. Players the set lacks keep their old photo. The pack downloads by itself when "Photos, logos and team names" is on.

- **The Roster editor can save the game's own roster.** Before, saving it stopped with "Seattle Kraken has 0 captain(s)
  and 0 alternate(s)": the program made a 2026 roster out of it first. Now an edit-only save keeps it the game's own
  2014 roster (All-Star teams, birth years and all) with just your changes. The 2026 update only runs when you press
  Update.
- **Export files to a folder from the game's own roster:** a roster updated from the disc can be picked as the roster
  file. Only the untouched disc roster is refused, and the message says to pick "New from EU disc" (or NA) in the list.
- **"'NoneType' object is not subscriptable" while updating:** a player page from NHL.com without a birthdate or a name
  is now skipped instead of stopping the update. Unexpected errors now say where in the program they happened.
- On the game's own roster the Roster editor shows slots 30 and 31 as the All-Star teams they are, not as Seattle and Vegas.
- A team that cannot dress 20 players keeps a captain and two alternates when you move its letter holders away.
- **Any letters you like.** In the Lines tab a team can have no letters, one captain, or a whole team of captains
  (even a goalie with a letter). The game played all of these in a test game. The update itself still gives each
  NHL team three letters; yours are kept on top.

## 0.80.1 (2026-10-27, Linux; a new name)

**The program is now called Puck Peak Legacy Updater** (`PuckPeakLegacyUpdater.exe` on Windows). Your copy updates
itself as before; your settings, edits and backups stay where they are.

**The Linux program now opens the same window as on Windows**, with every tab: Setup, Game patch, Update, the Roster
editor's tabs, Calendar, Front office, Draft & Pro, Play online and Export. Until 0.80.0 it opened the old window from
0.10 (two tabs, no game patch, no export) on most Linux PCs, because the web engine the window needs was missing.

- **Nothing to install:** the window brings its own web engine. Download `PuckPeakLegacyUpdater-0.80.1-linux.tar.gz`,
  unpack it and start `PuckPeakLegacyUpdater` in the folder (README-LINUX.txt in it says the same).
- **Find RPCS3:** pick your RPCS3 AppImage, the `rpcs3` program, or RPCS3's folder (`~/.config/rpcs3`; the Flatpak's
  `~/.var/app/net.rpcs3.RPCS3/config/rpcs3`). Games and saves kept in another folder (EmuDeck) are found from there.
- Runs on 64-bit Linux from 2022 or newer (Ubuntu 22.04, Debian 12, Fedora, Arch, SteamOS 3 in Desktop Mode).
- RPCS3, the file manager and links started from the program no longer inherit its own libraries.
- **No Mac program and no separate command-line program any more.** On a Mac, use "Export files to a folder" with the
  Windows program (CrossOver) or a Windows / Linux PC. The command line is inside the Linux program
  (`./PuckPeakLegacyUpdater --help`) and runs from source on any system (`python -m legacy_roster --help`).

## 0.80.0 (2026-10-27)

**Highlights** (this version also carries everything from the test versions 0.60.0 to 0.78.0 below; none of them was
released on its own):

1. **New centre ice for the NHL.** "This season's jerseys and centre ice" now brings centre-ice logos with the arenas'
   current names for 30 NHL teams (Utah's mammoth too); the clubs keep this season's. A centre ice you chose in Jerseys &
   ice still wins. Seattle and Vegas still play their home games on Nashville's centre ice, as before: the game has no
   full arena of their own.
2. **Play online with a friend.** A new tab: make a lobby with a six-letter code (or list it publicly), your friend joins,
   you both press Ready and RPCS3 starts on both PCs and takes you straight to Select Teams. The lobby host's roster is sent
   to the friend, so you both play with the same players. Europe and US games can play each other; a mixed pair is warned
   that the match may lose step.
3. **Download only the pictures you want.** The picture switch is split into Team names (no download, quick), Photos and
   logos, This season's jerseys and centre ice, NHL arenas and Team goalie masks, each with its own Restore.
4. **Newer arenas and goalie masks.** Newer boards and banners in the 32 NHL arenas, and the goalie masks of the teams.
5. **This season's jerseys with this season's names and numbers**, also on the sleeves and helmets, with no stray lines
   around the number.
6. **Real equipment, arenas and colours.** Sock tuck, pant length, stick tape and goalie neck guard follow the real
   players; all 32 NHL arenas and team colours are the real ones, and the AHL clubs play in their current arenas.
7. **Export files to a folder** (Windows, Linux, Flatpak, Mac) and **Linux support** for starting RPCS3.
8. **Lines and roster fixes.** Picking a player in Lines changes only the spot you picked; a damaged roster save is listed
   as "Cannot be used" instead of breaking the list; online no longer loads forever at a resolution scale other than 100 %.

### All changes in 0.80.0

- **The new scoreboard is gone.** It did not look right in the game, so it is out of the program. If you tried it in a test
  version, your next update puts the game's own scoreboard back by itself while one of the picture switches is on (Team
  names is on at first), with RPCS3 closed. Restore default does it too.
- **The new centre ice comes with "This season's jerseys and centre ice"** and has no switch of its own any more: the 30
  NHL teams it has get it and the clubs keep this season's. There is nothing to choose between.
- **A picture part that could not be downloaded says so.** Its row reads "Not available for download yet" instead of
  "Downloaded automatically", the update's result names the parts it had to leave out, and the List of changes has a row
  for each. Before, such a part could be switched on, the update ran and nothing changed in the game, without a word.
- Command line: `--photos`, `--looks` and `packs download` bring the new centre ice too; `--bright-ice` alone gives only the
  new centre ice.

## 0.78.0 (2026-10-27, test version)

**Highlights:**

1. **New centre ice.** The "Bright ice" part is now **New centre ice**: centre-ice logos with the arenas' current names for
   30 NHL teams (Utah's too), laid into your own game's files on your PC. Seattle, Vegas and the clubs keep this season's
   centre ice. It now works together with "This season's jerseys and centre ice": each team gets one centre ice, the one
   you chose in Jerseys & ice, else the new one, else this season's.
2. **New scoreboard** (off to start with; taken out again in 0.80.0). A broadcast look for the scoreboard and the game's
   on-screen boxes: dark navy boxes with white text and a red power-play bar. It has its own row in step 4 of the Update
   tab. While it is on, pick the corner logo: **SN**, **Puck Peak**, **no logo** or **a picture of your own**.

### All changes

- **New centre ice** replaces the old Bright ice circles on white ice. The download is about 6 MB. Utah's rink no longer
  shows Arizona's coyote under the new centre circle. A team whose centre ice you chose in Jerseys & ice keeps your
  choice. Bright ice and "This season's jerseys and centre ice" no longer turn each other off.
- **New scoreboard.** Changes the score bug, the drop-down message bar, the replay bug, the player card, the warning bar,
  the line change bar and the team pill. The clock and the messages are white on navy. The power-play text and the score
  of the team on the power play are white on the red bar. The game's spinning logo in the corner (score bug, replay,
  match intro, shootout, skills) is replaced by the logo you pick. The team logo on the player card is no longer covered.
  The small team logos show while the scoreboard is in its long form; at times the game switches to a short form without them.
  It is made on your PC from your own game's files, and its Restore puts the game's own scoreboard back.
  On the command line: `--overlay`, `--overlay-logo sn|puckpeak|none|<picture>`, `photos remove --part overlay`.

## 0.76.0 (2026-10-27, test version)

**Highlights** (this version also carries everything from the test versions 0.60.0 to 0.75.0 below):

1. **Play online with a friend.** A new tab: make a lobby with a six-letter code (or list it publicly), your friend joins,
   you both press Ready and RPCS3 starts on both PCs and takes you straight to Select Teams. The lobby host's roster is sent
   to the friend, so you both play with the same players. Europe and US games can play each other; a mixed pair is warned
   that the match may lose step.
2. **Linux support.** The program starts RPCS3 for you whether it is the `rpcs3` program, an AppImage or the Flatpak, finds
   its log and takes the program or its folder in the RPCS3 picker. (Not tried on a real Linux PC yet.)
3. **Export files to a folder** (Windows, Linux, Flatpak, Mac): everything the program would put into RPCS3, laid out like
   RPCS3's own folders with a `HOW-TO-INSTALL.txt` for your system. Nothing in RPCS3 is changed.
4. **Download only the pictures you want.** The picture switch is split into Team names (no download, quick), Photos and
   logos, This season's jerseys and centre ice, NHL arenas, Bright ice and Team goalie masks, each with its own Restore.
5. **Newer arenas, centre ice and masks.** Newer boards and banners in the 32 NHL arenas, sharper centre-ice circles
   (Bright ice) and the goalie masks of the teams.
6. **This season's jerseys with this season's names and numbers.** Each jersey wears its own lettering: the same
   letters, digits, colours and outlines, also on the sleeves and helmets, and no stray lines around the number.
7. **Real equipment.** Sock tuck, pant length, stick tape and goalie neck guard follow the real players, and the Equipment
   window uses the game's own words.
8. **Real arenas and colours.** All 32 NHL arenas and team colours, and the AHL clubs in their current arenas, with their
   capacities.
9. **Lines and roster fixes.** Picking a player in Lines changes only the spot you picked; a damaged roster save is listed
   as "Cannot be used" instead of breaking the list; online no longer loads forever at a resolution scale other than 100 %.

### All changes

- **Pictures are split into switches, so you download only what you want.** "Photos, logos and team names" is now two
  rows in step 4 of the Update tab. **Team names** needs no download and is on to start with. **Photos and logos** is one
  switch for everything heavy: press its arrow to choose the parts (**Player photos and team logos**, about 105 MB;
  **This season's jerseys and centre ice**, about 80 MB; **NHL arenas**, **Bright ice** and **Team goalie masks**, small
  downloads), or just switch the row on and every part comes with it. Each part is downloaded only when it is on, and has
  its own **Restore** that puts back only its own files (the row's Restore does all of them). If you had the old switch
  on, Photos and logos and the jerseys stay on.
- **NHL arenas.** Newer boards and banners in the 32 NHL arenas. Made on your PC from your own game's files; the download
  holds only the differences.
- **Bright ice.** Sharper centre-ice circles with the arenas' current names, on solid white ice. It is the other way to get a new centre ice:
  "This season's jerseys and centre ice" and Bright ice never run together (turning one on turns the other off), and the
  group switch turns on this season's.
- **Jersey names and numbers in the right colours.** The player names on the back were painted in the colour of the
  numbers (orange names on Edmonton's blue jersey), and numbers lost their outline when it was thin or shared the
  shirt's colour. Now the names have their own colour, the numbers keep their two outlines and the small numbers on light
  jerseys are the right way round. Needs the updated jersey download; jerseys already installed are redrawn once.
- **This season's lettering on every jersey of this season.** The names and numbers were the game's own letters
  recoloured, with an outline grown outwards: a line showed under the back number and above it (McDavid), every
  number had one colour (Pittsburgh's sleeve numbers were gold instead of black) and Utah's home jersey was the one made
  from the team's colours. Now each home and away jersey of this season wears its own names and numbers (letters, digits,
  colours and outlines; sleeves and helmets too), marks such as the apostrophe in O'Reilly come from your own game, and
  Utah, Seattle and Vegas wear this season's jerseys on every version. Jerseys made from colours keep their outlines
  inside the letters, so no lines appear there either. The jersey download grows to about 80 MB; installed jerseys are
  redrawn once.
- **Team goalie masks.** The goalie masks of the teams (Utah, Seattle and Vegas keep the game's own masks for now). A
  goalie's own mask picture from the Roster editor always wins.
- **Team names alone are quick.** An update with only Team names on downloads nothing and takes seconds. RPCS3 must be
  closed (the names are written into the game's folder).
- The command line has `--names`, `--looks`, `--arenas`, `--bright-ice` and `--team-masks` (`--photos` still means
  photos, logos, names and jerseys); `photos remove --part <name>` undoes one part.
- **One damaged roster no longer breaks the whole list.** A roster save in your RPCS3 folder whose data could not be
  unpacked stopped the scan with "Error -3 while decompressing data" and left step 1 empty. It is now listed as "Cannot
  be used" and the other rosters work. It has nothing to do with the game being present.

## 0.75.0 (2026-10-26)

- **Real equipment for the players.** Players now dress like their real selves where the program's data knows them (almost
  every NHL player, plus the AHL players and goalies it has): **sock tuck**, **pant length**, **stick tape colour** (black or
  white) and the goalies' **neck guard** are filled in with every update. Viktor Arvidsson no longer tucks his socks, Auston
  Matthews wears them the way he does in real life. Stick, helmet, gloves, skates and the other models are not copied (the
  numbers do not match the game), and whatever you pick in the Roster editor's Equipment window always wins. Needs the
  newest data pack (the program downloads it).
- **The Equipment window uses the game's own words.** Tested in the game: sock tuck 0 is **Full** (the sock goes into the
  skate, the usual tucked look), 1 None, 2 Front, 3 Back; visor Straight / Curved / No visor (and its tint colours by name,
  with the right picture for each visor); shoulder pads Small / Big; goalie neck guard Off / On. Before, the window had the
  sock words in the wrong order, which made tucked players look untucked. A choice made in the window reaches the game.
- **New players start plain.** A new player used to wear the tucks, tape and visor of whoever held the record before.
- **AHL arenas.** The AHL clubs play in their real, current arenas (Coachella Valley: Acrisure Arena, Henderson: Lee's
  Family Forum, the Barracuda: Tech CU Arena, many more renamed), with their capacities.

Also in this version (unreleased before):

- **Multiplayer: when the game stays on a menu, the steps show up.** After a live match a friend's game stopped at the
  Online menu while the other one went into the search by itself. When the game has been signed in for 90 seconds and has
  no session, the tab now lists what to press (host: Create Game Session, guest: Browse and join). The message for the
  game's own roster says what to do: press Update once, then pick the new roster in Setup.

- **Lines: picking a player never moves anybody else.** Before, picking a player who already played in another place of
  the same kind (a line, a pair) swapped the two, so fixing one spot sent him back to the other: a circle. Now only the
  picked spot changes; a player left in two places is named in red until you give one of them to someone else. On the
  power play, penalty kill, overtime, shootout and extra attackers one player may now hold several places. The four lines,
  three pairs and two goalies still need 20 different players (the game dresses 20).

- **Linux: the program starts RPCS3 for you** whether it is the `rpcs3` program, an AppImage or the Flatpak, finds RPCS3's
  log there, and the RPCS3 picker takes the program or its folder. Not tried on a real Linux PC yet.
- **"Export files to a folder" (Windows, Linux, Flatpak, Mac).** It replaces "Export only SYS-DATA roster". Tick it in Setup
  and the program makes everything it would put into RPCS3 (the roster, with Photos the pictures and names, with the game
  patch the patch file) in a new folder `NHL Legacy export <date time>`, laid out like RPCS3's own folders, with a
  `HOW-TO-INSTALL.txt`. Nothing in RPCS3 is changed. A window "Your files are ready" says, for your system, where each
  folder goes, which patch entries to tick in RPCS3, how to load the roster and how to undo it. A roster file (SYS-DATA)
  still works when you have no RPCS3; pictures, the patch and the game's own roster need your copy of the game.
  Command line: `export-files`.
- **Play online: no more endless loading** when RPCS3's resolution scale is not 100 %. The program now ticks RPCS3's
  "Disable Blit Engine Upscaling" in its own online config (your own RPCS3 settings are not touched).

## 0.70.0 (2026-10-26, test version)

- **All 32 NHL arenas and team colours are the real ones** (the game's venue list, Team Select, sticks and gear follow).
- **Jerseys & ice: the colour and venue-name fields now change the game**, not only the pictures. A change reaches the
  roster on the next update or the Roster editor's Save.
- **Lines: a pick changes only the spot you picked.** A forward chosen for a defence spot no longer swaps lines, and a
  new player no longer takes every power-play / penalty-kill place of the one he replaces; a button offers to put him there too.
- **Play online: different games can play together.** Europe and US, or 1.00 and 1.01, are no longer refused; the lobby warns
  that the match may lose step. Lobby server: the game-version check is gone.

## 0.65.0 (2026-10-26, test version)

- **"Photos, logos and team names" starts off.** It takes a long time, so you tick it yourself when you want it (everyone
  starts off once; a choice you make afterwards is kept). Playing online never waits for pictures: only the roster and the
  game patch have to match.
- **Play online: Public is the default.** A lobby is listed for everybody unless you choose Private.
- **The online start does not need the pictures any more.** Going straight to Select Teams works with Photos off.
- The match itself is the game's standard online match (5 minute periods, NHL rules); the lobby says so. The game
  takes these from its own Play Now settings, so they cannot be changed from the program.
- **Server:** the lobby server on the Puck Peak box is updated (Public by default, members must prove who they are).
  Update both PCs to 0.65.0.
- **Both players need the same game: same region (Europe or US) and same version (1.00 or the update 1.01).** In our tests
  only equal games stayed in step; mixed ones stalled while loading or lost step in the first period. The lobby now says so
  and does not start such a pair; the open-games list greys them out.
- The first start after a game or RPCS3 update can take up to half an hour while RPCS3 prepares the game; the steps say so.

## 0.60.0 (2026-10-25, test version)

- **New tab: Play online.** Set up online once (it adds the online part of the game patch to RPCS3 and your RPCN name is
  read from RPCS3), then make a lobby or join your friend's with a six-letter code. When both press Ready, RPCS3 starts
  on both PCs.
- **The roster is the lobby host's.** Make a lobby with the roster you picked in Setup: it is copied to your own "Puck Peak
  Online" save and sent to your friend, whose PC copies it when they join (a backup of that save is kept). Your other
  rosters are not touched.
- **Both of you play with the same game patch**, or both without it. If they differ, Ready waits and the tab says what
  to press in the Game patch tab.
- **Nothing to press in the game.** When both of you are Ready, the game starts, signs in and takes both of you straight to
  Select Teams, with the game as it came on the disc and with its update 1.01 (EU and NA; an EU and an NA game can play each other). Pick your team and side.
- **Safer lobbies.** Only someone who is in a lobby can ready, leave or change it, and a roster from a friend is checked
  before the program puts it into your game.

## 0.52.0 (2026-10-25)

- **The Calendar shows your games again** in Be a GM and Season mode on the patched game: every game day has the
  other team's logo and the Home / Away corner, for the NHL team and its AHL club. Press **Patch again** in the Game
  patch tab once (game patch 0.26).
- An update no longer stops with "Kraken has 49 players (max 40)" when NHL.com's player search puts a whole farm team
  with its NHL club (Coachella Valley's players with Seattle). Such players join their NHL team only while it has
  room; the rest stay with their club.

## 0.51.2 (2026-10-24)

- An update no longer stops with "Kraken has 49 players (max 40)" when the roster lists a player twice on one of its
  copies of an NHL team (Kraken is the copy of Seattle). The copy keeps him once.
- A roster the patched game saved itself (with room for more games next season) is brought back to the patch's size
  for next season's calendar when it is updated again.

## 0.51.1 (2026-10-24)

- **Real captains on every team.** The C and the two A's were picked by rating before (Winnipeg's captain Adam Lowry
  had no letter, Mark Scheifele wore the C). Now every NHL team wears the letters of its last five games on NHL.com,
  the AHL and CHL clubs those of their last five games, the Czech Extraliga clubs those of their latest matches, and
  the other European clubs those of a larger database where their own league names none. A captain who is not on the
  team leaves his C open: the team then has three alternates, as the game allows. National teams the program fills
  are led by a player who captains his own team. Letters you set in the Roster editor are still kept.
- **"Saved" means saved.** When something after the save fails (the pictures, the list of changes), the window now
  says the roster is saved and shows what went wrong in red, instead of "Nothing was saved".
- **A fuller error log.** Every failure now writes the program's version, the roster, the folders it used (each one
  marked "missing" when it is not there) and the details to the error log (Show details > Error log). Send that file
  with a bug report.
- The update of the game's own roster always fills Seattle and Vegas (with "Restore default" and the game patch they
  were left empty, and the update stopped with "Seattle Kraken has 0 captain(s)").
- **Restore no longer stops with "The system cannot find the path specified"** when an older version put pictures into
  a game folder that has moved or is gone (RPCS3 moved to another drive, the game reinstalled). There is no need to
  delete the program's folder: it holds your edits and the roster backups.

## 0.51.0 (2026-10-24)

- **The NHL's lines are the announced ones.** The lines, pairs, goalies, power play and penalty kill now come first from
  the teams' announced line combinations (Daily Faceoff), so a centre such as Connor McDavid plays centre next to another
  centre such as Leon Draisaitl, and the power-play units are the real units. Where a team's announced lines cannot be
  matched to its NHL.com roster (a new player, an unfinished unit), that part still comes from its last five games.
- **Real lines for the clubs outside the NHL.** The AHL, the CHL, the Czech Extraliga, the SHL, Liiga, the DEL and the
  National League play lines, pairs and goalies taken from real data instead of being dealt by rating, wherever every
  player of a line is on the club. The Czech Extraliga clubs use their latest match line-up from hokej.cz (their first
  goalie is the one who started most of the last games). A club whose data names a player who is not on it keeps the
  lines it had for that part.
- Lines set in the Roster editor are still kept; lines set inside the game are replaced by the real ones at the next update.

## 0.50.4 (2026-10-24)

- **Lines come from real games.** Every NHL team's lines, pairs, goalies, power play and penalty kill are now worked
  out from its last five games on NHL.com: who really skated together at even strength, who played on the power play
  and the penalty kill, and who started in goal. The first line is the one with the most ice time. A team whose real
  lines name a player who has left keeps the lines it had for that part. Overtime, the shootout and the extra
  attackers are still picked by rating. Lines you set yourself in the Roster editor are still kept. Lines you set
  inside the game are replaced by the real ones at the next update.
- **The AHL matches real life.** Who plays for each AHL club now comes from the AHL's own live lists (803 players
  today, for example Ben Dexheimer at Iowa), not from an old snapshot. Players who hold an NHL organisation's rights
  keep them. Players the AHL lists on an NHL contract but whom the old snapshot did not know belong to their club's
  NHL team.
- **A "Buy me a coffee" button** under the Discord button in the Setup tab opens ko-fi.com/iksperial (tips for the development).
- **Coachella Valley and Henderson have their own jerseys and ice in the patched game.** They are club teams of the
  AHL now, like Charlotte or Utica, with their own team numbers (900 and 901) instead of a made-up team's: jerseys, pants,
  socks, helmet logo, menu picture and centre ice are made from their colours and crest when "Photos, logos and team
  names" is on. Their banner, puck and goalie helmet are still a donor club's pictures. Only on a roster for the patched
  game; the unpatched game keeps what it had. A Coachella jersey you made in the Roster editor's team window does not
  show there; use the Jerseys & ice tab instead.

## 0.50.3 (2026-10-23)

- **The program looks for a newer version every time it starts.** Before, it looked at most every 12 hours, so a
  version released the same day was not offered. The question also waits until another question on screen is
  answered, instead of being dropped. "Look for a newer version when this program starts" in the Setup tab switches
  it off.

## 0.50.2 (2026-10-23)

- **Season mode no longer crashes when it starts** (game without the game patch). The update gave some players the
  rights of the Seattle Kraken, a team the unpatched game's Season does not have, and the game crashed on them while
  setting up a new Season. Seattle and Vegas now hold no player rights on a roster for the unpatched game, as the
  community's roster has it. If your Season crashed, update your roster again with 0.50.2 (the Roster editor's Save
  fixes it too), then start a new Season. Rosters for the patched game (32 teams) are not affected.
- **The Join our Discord button is now at the top of the Setup tab**, above "Where is RPCS3?", where it is easier to
  see.

## 0.50.1 (2026-10-23)

- **Join our Discord.** A button at the top of the window, and one at the top of the GitHub page, open the Puck Peak
  Discord ([gg.puckpeak.com](https://gg.puckpeak.com)): questions, news and help.
- **A second update no longer stops with "no spare player record left for ...".** After a full update every free
  player record of the game is in use. When NHL.com then lists a new player (a call-up, a new signing), the update now
  makes room: an old free agent nobody needs retires, or for a goalie a junior club's third goalie leaves. The List of
  changes names who made room. If you saw this error, update to 0.50.1 and run the update again.
- **The game patch works with the game's update 1.01 too** (EU and NA). RPCS3 installs this update for many players,
  and the game patch of 0.50.0 only fitted the game without it: the patch never ran, so a 32-team roster showed as
  "damaged". The patch now fits both, and RPCS3 uses the right one by itself. If your game has update 1.01 and you
  patched with 0.50.0, the Game patch tab says "Patch again": press it (RPCS3 closed), then start the game. The
  program does not update a roster until then.
- **Team names and Puck Peak texts keep update 1.01's own texts** (such as "5 Min (3 on 3) then Shootout" in the
  overtime choices): the program now starts from the update's text files when your game has it.

## 0.50.0 (2026-10-23)

The biggest update yet: everything new since 0.10.4, and a new window. The versions in between (0.20.0 to 0.35.0) were
test builds and never released; the number jumps so the program's own update check sees 0.50.0 as newer.

### A new window with tabs

- **Ten tabs in one row**, like a game menu, in the order you use them: **Setup**, **Game patch**, **Update**, then **Roster**, **Lines**,
  **Strategy**, **Jerseys & ice**, **Calendar**, **Front office** and **Draft & Pro**. Each part has a page of its own instead of one
  crowded page. The program always opens on Setup. Ctrl+1 to Ctrl+9 and Ctrl+0 open a tab, Ctrl+PgUp and Ctrl+PgDn go to the tab
  on the left or right.
- **Setup**: pick RPCS3 and the roster to start from, with Open folder and Delete next to each roster, and whether the
  pictures are downloaded and the program is up to date.
- **Update**: what to update, "Photos, logos and team names", update in place or make a new roster, and the result.
- **Game patch**: Patch, Unpatch and the two switches on a page of their own, and for each game version (EU, NA) what is
  in the game now.
- **One team list on the left** for the six team tabs. The team you pick stays picked when you change tab, so you can
  look at a team's lines, then its strategy, its jerseys, its games and its contracts. Each team shows a number that fits
  the tab: players, games or payroll.
- **Lines, Strategy and Jerseys & ice are tabs now**, no longer windows on top of the editor. Changes you have not
  applied yet stay with their team when you click another team.
- **One Save bar** under Roster, Lines, Strategy, Jerseys & ice and Front office: My edits, update in place or as a new
  roster, Save (Ctrl+S).

### Calendar (new)

- **A month page**, Monday to Sunday, with arrows for the month before and after. The team you pick has its games marked
  on each day ("vs EDM" at home in gold, "@ CGY" away in blue); the other days show how many games there are.
- **Click a day** to see all its games. **The team's games** are listed on the side, month by month, with games
  played, home and away; click one to go to its day.
- **Every league's calendar**: the NHL, the AHL, the SHL, Liiga, the DEL, the Extraliga, the National League, the OHL,
  the QMJHL and the WHL, as your roster holds them, and Norway's real games (the game has no calendar for Norway). A
  note says when a roster still has the game's own old calendar of a league.
- **This season's calendars in the game.** An update with the calendar on now also writes the real 2026-27 calendar of
  every league whose clubs it updates. Season mode plays all ten leagues (New Season > League Type) from these
  calendars. Only games between clubs the game has are written (Liiga and the WHL have more clubs than the game).
- **My season.** Switch the calendar to your latest Season or Be a GM save and it shows the games you have played with
  their scores (won in gold, lost in blue, OT and SO marked), today's date in your season, the next game and the
  playoffs. Front office then shows your team's record, points and place, and the standings. The program only reads
  your save, never changes it, and waits while the game is still saving.

### Front office (new)

- **A team's money at a glance**: payroll, the salary cap and the cap space, for this season and the four after it.
- **Every player under contract** with the organisation: the NHL roster, the farm club and the prospects, with cap hit,
  seasons left, one-way or two-way, and an extension he has signed. Sort by any column.
- **Edit a contract** (from Front office, or from the player card in Roster): cap hit, seasons, one-way or two-way, and
  an extension. The window shows the team's cap space before and after, and refuses a deal the game does not allow.
  The new deal goes into My edits and is kept through every later update. Amounts are always real dollars; a roster for
  the game without the patch holds them scaled to the game's $71.4M cap, as every contract is.
- **Every club, not only the NHL.** Pick any team: an AHL club, an Extraliga, SHL or junior club, a custom team. Front
  office shows its own roster with each player's deal as the game's Team Rosters shows it, and its payroll. An AHL club
  links to its NHL team. **Edit any club player's contract**, and make up your own: outside an NHL organisation any
  amount from $5,000 up to the NHL's most, one to eight seasons. A free agent can be signed to a team with a deal.
  National teams are read only (a player's contract belongs to his club).

### Draft & Pro (new)

- **The next four drafts** (2027 to 2030) and **your own Be a Pro player**, each with its list of players.
- **Add a prospect**, or **make a whole class** at once: 16 to 64 made-up players, a weak, normal or strong class, and a
  class number (the same number makes the same class again). Made-up names mix first and last names of real players of
  the same country, never a real player's full name.
- **Every prospect on the Roster editor's card**: name, number, position, type, birthdate, country, size, face and
  ratings, plus his **potential in stars** (as the game shows it, 5 stars the best) and the potential number, the two
  things the game drafts him by. The list reads like a draft board, the best first.
- **The game's Create Player look** for a player you make (a prospect, your pro or any new player): head shape, skin
  tone, hairstyle and hair colour, facial hair, eyebrows, eye colour, freckles, scars and a black eye, with the game's
  own words and its own menu pictures from your disc. Random makes one up. The game has 180 places for created faces;
  the program leaves a few free for the game's own Create Player and says how many are left.
- **Share classes.** **Export...** saves a class as a file; **Import...** puts a class file into the draft you have
  open. Birth dates move to that draft, and a window says who was added, who went to another club and who was skipped.
- **My pro.** Make your own player, put him on a team and pick him in Be a Pro. In the patched game put him on an NHL
  team: a Be a CHL Pro career with an undrafted junior does not start yet. The tab says where the game lists him:
  Career > Live the Life > New Pro > Be a NHL Pro, his team, his position, then step Overall until he shows (it starts
  on 70-79; a pro with 88 everywhere is on 80-89, one with 98 on 90-99).
- **Your pro is never lost.** The tab says whether he is in the game already or still waiting for Save (a gold "Not in
  the game yet" line). A pro or class you made and did not save yet is still saved by the next Save after you restart
  the program, and closing the window with edits not saved asks first: Save now, Close anyway or Cancel. Be a Pro picks
  a pro only on an NHL team or a CHL club, so the card offers only those.
- **Be a Pro careers.** The careers you saved in Live the Life, with your pro's ratings as the career has them. Change
  his name (Load Pro then lists the career under the new name), his ratings (40 to 99; not for a goalie yet) or the
  experience points he has to spend in Player Growth and press **Save this career** (RPCS3 closed):
  the whole career is copied to the program's backups first (the newest 10 are kept), and only what you changed is
  written.
- The game drafts juniors and European players without NHL rights, by birth date, so class players play on a CHL or
  European club. Classes work in the patched game (32 teams, the year 2026). Save writes them into the roster, and every
  later update keeps them.

### The program

- **A much smaller program.** The pictures are no longer inside it: the program is about 26 MB instead of 173 MB, so a
  new version downloads in seconds.
- **Pictures downloaded automatically.** While "Photos, logos and team names" is on, the program downloads its pictures
  by itself in the background (about 160 MB, once, and again only when they change), and the next update puts them in.
  The row shows how far it is. Press Update during the download and the update waits for it. Switch it off and nothing
  is downloaded.
- **A bigger window.** The program opens big and in the middle of the screen.
- **"Photos, logos and team names" comes first** in the list of what to update, and stands out in gold.
- **Less clutter.** "Restore default" is one small red button, so "Update roster" is the one big button; "Restore" on the
  Photos row puts the game's own pictures back. Patch, Unpatch and Update say
  so when RPCS3 must be closed.
- **The game shows at most 10 rosters per version.** Setup now counts them ("7 of 10" for EU and NA) and says to keep
  10 or fewer. A new roster takes a free place among the 10 (one freed by Delete is used again); when all 10 are in use,
  "Make new roster" is greyed: delete a roster you no longer play, or update one in place. Before, an 11th roster was
  saved where the game never shows it. Such a roster is now marked "not in the game".
- **The right way to load a roster.** The program used to say "Roster Management > Load Roster", which the game does
  not have. It now says **Customize > Save/Load/Delete > Load > Rosters**.
- **A roster folder you copied by hand** loaded the roster it was copied from (the copy kept the original's name inside),
  and the game could call it damaged. Updating the copy in place now gives it its own name.
- **The command line** has `packs download | status | remove`, and `update --photos` downloads what it needs first.
- **Fixed: Setup showed an RPCS3 in a temporary folder** and Patch failed. The program no longer takes an RPCS3 from a
  temporary folder; it looks for the running one or the usual place instead.
- **Fixed: the window could open empty** (dark, with nothing in it). The window asks for its fonts and pictures all at
  once and Windows turned some of those requests away. It now takes them all.

### Game patch: 32 teams and the year 2026

- **Patch the game** (the gold button on the Game patch tab) patches NHL Legacy in RPCS3, every version you have, so
  that Season, Be a GM and Be a Pro have Seattle and Vegas: 32 NHL and 32 AHL teams, 84 games, the year 2026. The tab
  says whether the game is patched, with **Unpatch** next to it. Point at the **"?"** next to Patch to read everything the
  patch does: what changes in the game, the two switches, what it writes on your PC, what it means for your rosters
  and saves, and what Unpatch puts back.
- **Two switches**, changed at once while the game is patched: **Skip the intro** (straight to the main menu: no
  intro videos and no Press Start) and **No pop ups at start** (no sign-in boxes when the game starts; online modes still sign in when
  you open them, so online play through the community servers works with it on).
- **Puck Peak's news on the main menu, also online.** The patch keeps the main menu's news panel on the Puck Peak
  lines (they come with Photos, logos and team names) when you are signed in, where the online server's old news showed
  before. If you patched with an earlier build, press **Patch again**.
- **Rosters that do not fit the game are marked.** The patched game cannot load a roster made without the patch (it
  says the roster is "damaged"), and the game without the patch cannot load a 32-team roster. Such a roster shows a red
  line in Setup, on the Update tab and on the Game patch tab. After Patch or Unpatch the program asks whether to update
  the roster you picked right away (in place, a backup first).
- **Every update follows the game.** Patched, it makes a roster for 32 teams from any roster, also the game's own; not
  patched, a roster for the game as it is. A roster made for the patched game is marked "32 teams"; after Unpatch,
  updating it makes it a roster for the game as it is again. With the game's own roster, Coachella Valley and
  Henderson get their real AHL players too, so Seattle and Vegas have their farm clubs there.
- **Coachella Valley and Henderson in the AHL.** With the patch, Play Now's Select Teams lists them in the AHL with
  their names and crests, no longer under Custom Teams, and the Roster editor does the same. Without the patch they
  stay under Custom Teams, where the game needs them. Their names need "Photos, logos and team names".
  Roster Management's Team Rosters lists them in the AHL too (before, it missed them on a roster made from the game's
  own): press **Patch** again when the Game patch tab says "patch again".
- **Vegas calls up from Henderson** (patch 0.23). Henderson's players now hold Vegas's rights, as every farm club's
  hold their NHL team's: Be a GM lists them under Vegas's "In the System", calls them up and sends them down, and the
  other teams trade for them. Before, the game had no room to note Vegas's rights, so the update kept a farm club's
  worth of players on Vegas's own NHL roster and Henderson was filled up with free agents. Press **Patch** again when
  the Game patch tab says "patch again", then update your 32-team roster: a roster made for the older patch shows a
  red line ("made for another version of the game patch") until it is updated.
- **The real salary cap.** Be a GM's cap is $104.0M (the game's own: $71.4M), the floor $76.9M, the most one player
  can earn $20.8M and the lowest salary $850,000. The next seasons follow the real numbers: 2027-28 $113.5M, 2028-29
  $127.5M (the league's estimate), then the cap holds. Contract Status shows the real seasons ("26-27") instead of
  "15-16". Only with a roster made for the patched game, which holds the real contracts.

### The update

- **Every team can dress 20 after an update.** When NHL.com moves a player to another position (a defenceman listed as
  a left wing, for example), the update now deals that team's lines again. A team left short of goalies or defencemen
  calls the missing player up from its farm club, or signs a free agent, and the List of changes says who. Before, such
  a roster could fail the safety checks ("Ottawa Senators dresses 20 players ... the game needs 2 G and at least 6 D")
  and was not saved.
- **Current ratings for every league.** Every player the current ratings cover, in every league, gets them, his player
  type when it fits his position, and how he likes to play (shoot or pass, attack or defend, carry or dump). About
  4,600 players of the community roster are covered; the rest are estimated from their stats as before. The result
  says how many are current and how many estimated. Height, weight and hand come from the ratings only for players
  NHL.com does not list. Your own Roster editor changes still win.
- **The AHL's real rosters.** All 32 AHL clubs get this season's real rosters, with each player's real organisation
  (NHL.com's NHL rosters still come first). Before, the AHL list's own marks put some players with the wrong team
  (Coachella Valley missed 7 of its players and had 5 others). An AHL club short of a player signs a free agent near
  its own level: before, Henderson signed the best free agents (Jonathan Toews among them).
- **A contract for every club player.** A player on a club who has no deal and whose rights no NHL team holds gets a
  made-up starter deal with his club, by league and how good he is (an AHL-only deal, a National League deal, a junior
  deal ...): one season from 27 on, else two. The game's Team Rosters shows an amount for him instead of "N/A". An
  unsigned draft pick stays unsigned. Change any of them in Front office. NHL prospects playing in Europe or junior get
  their real NHL deal too.
- **Real contracts for 2026-27.** Every NHL player gets his real deal: what he earns per season, the seasons left,
  one-way or two-way, and an extension he has signed for next season. The game's own salary cap is $71.4M, so a roster
  for the normal game holds every deal times 0.6865 (a $17M deal shows as $11.67M) and each team's payroll fits the
  game's cap as the real one fits the real $104M cap. A roster for the patched game holds the real dollars. The List
  of changes shows each NHL team's payroll. A player under contract for 2026-27 stays with his team even when NHL.com's
  roster lists leave him out (Dylan Larkin, for example), instead of becoming a free agent.
- **Every contract shows in the game.** Roster Management's Team Rosters showed "N/A" instead of the contract for some
  players who changed teams (Jack Eichel and Noah Hanifin at Vegas). Every player under contract now shows his deal
  there, in a new Be a GM's Contract Status and in Be a Pro, also a contract you edited. Be a GM also shows UFA and
  RFA right after a deal ends (before, Mark Stone at 34 showed as a restricted free agent): a player becomes a UFA in
  the year he turns 27, as in the game's own roster. A Be a GM or Be a Pro started before an update keeps the
  contracts it started with.
- **Utah's, Seattle's and Vegas's arenas on the community roster.** A Utah home game said "Arizona Arena, Glendale"
  and Seattle and Vegas played in Nashville's arena by name. The NHL step now gives them Delta Center, Climate Pledge
  Arena and T-Mobile Arena on every roster; the community roster's own team colours stay.
- **Utah's helmets and gloves in Utah's colours.** Since 0.10.0 the NHL step painted the wrong teams (Philadelphia and
  Washington got Utah's and Seattle's colours, Utah and Vegas got nothing). Utah now wears black, Seattle navy, Vegas
  steel grey (their usual helmet; gold is their alternate); an update gives Philadelphia, Washington and Seattle their
  own colours back.
- **Gear in team colours.** Helmets and gloves of the AHL, junior and European clubs, and the goalies' gear on every
  team, no longer show colours their team does not wear (blue gear for a red and black team). Gloves, pads and
  helmets the game could only draw plain blue get a model it draws.
- **Sticks in team colours.** An NHL player whose stick shows a colour his team does not wear (Utah's red sticks) gets
  a stick of the same brand in a team colour, or a plain one. The List of changes counts them. A stick picked in the
  Roster editor stays.
- **Fixed: "Aatu Räty still on VAN".** With NHL.com's rosters of October the safety check stopped the update of the
  community roster: Aku Räty's contract (Edmonton) was taken for Aatu Räty, whose record has the same last name. A
  player's record now goes to the player it fits best.

### Photos, logos and team names

- **No more wrong faces when you keep several rosters.** Every roster on your PC shares the game's picture files, and a
  picture number could belong to one player in one roster and to another player in another (for example the
  community's 2026-27 roster next to a Puck Peak roster). The program now looks at all your rosters and pictures first
  and never gives a player a number someone else uses. Where it had done so, it moves its picture away; the other
  roster then shows no picture for those players until you update it too.
- **A player without a real photo keeps his old picture.** When a photo cannot be made (NHL.com shows only a grey
  silhouette, no face found, the download fails), the player keeps the picture he had instead of an empty one.
- **This season's jerseys and centre ice.** The teams wear this season's home and away jerseys: the 32 NHL teams, the
  AHL, the OHL, QMJHL and WHL, the SHL, Liiga, DEL, Extraliga, National League, Norway's two clubs and the national
  teams, with numbers, socks, pants and the Select Jerseys pictures to match. Third jerseys and every other version stay
  the game's own. This season's centre-ice logo goes in where the game shows a club's own ice; the DEL clubs share one
  rink in the game and the national teams play on the international ice, so they keep the game's own. The first install
  takes about 18 minutes and about 0.8 GB per game version.
- **Select Jerseys shows this season's pictures.** The Home and Away pictures in Select Jerseys (and in the Roster
  Jerseys & ice tab) are pictures of this season's kits. Before, they were the game's picture of Utah's
  jersey painted in three of the team's colours, so Pittsburgh's sleeves came out gold.
- **Sharper centre ice and jerseys.** The centre-ice logos (Utah's Delta Center ring, for example) no longer look
  blocky, blotchy or hatched, above all at a slant from the camera, and their edges no longer show a white rim. The same
  goes for the number sheets.
- **Coachella Valley and Henderson wear their own crests.** Before, their centre ice showed a black square and their
  jerseys were plain black. The Firebirds' and the Silver Knights' crests are now on the centre ice, on the jerseys and
  in Select Jerseys, and Coachella plays in navy. This works on every roster, also on the game's own. The game draws
  them as create-a-team teams, so whoever builds a team of their own with create-a-team logo 72 or 80 sees these crests
  too.
- **Fixed: Coachella Valley in a plain jersey.** On a roster made from the game's own roster, Coachella's home jersey
  came out plain (white, or black on newer RPCS3 versions) without stripes. It now wears its navy jersey with the red and
  teal stripes. A roster you already have is fixed by its next update. A custom team's kit you paint in Jerseys & ice
  gets the same jersey design.
- **Fixed: blank team names in Select Teams.** The AHL's Colorado, Cleveland, Laval, Chicago, Tucson, Calgary and
  Abbotsford and the CHL's Brantford, Newfoundland and Wenatchee had no name there. They are named now.
- **No dead online entries in the menus.** View Player Hub, Leaderboards and Lobby (their online servers are gone, so
  they never opened) and Hockey Ultimate Team are left out of the main menu and Play. Online versus, EASHL and GM
  Connected stay (the community server serves them). "Restore" on the Photos row puts them back.
- **Puck Peak in the game.** Every news text on the main menu (also the fighting tip and NHL 94) says "Puck Peak" and
  "Updates, patches, statistics! Join us on gg.puckpeak.com"; the "new tuner set" notices say "www.puckpeak.com", in
  every language. With the game patch the news panel keeps these lines when you play online too (without it the
  online server's old news show there). The community server's other notices and the HUT banner stay as they are.

### Roster, Lines, Strategy, Jerseys & ice

- **Your own player photos go into the game.** A photo you pick now goes into the game when you press Save (close RPCS3
  first), and with every update, also with "Photos, logos and team names" off. Before, it only went in with an update
  with that switch on. The same goes for a logo you pick for a team. A picture with nobody in it is refused when you
  pick it.
- **Jerseys and ice for every team.** The Jerseys & ice tab works for every team in the game, not only the NHL. Outside
  the NHL it shows the home and away jersey. For each: this season's, the game's own, made from the team's colours
  (where the shirt allows it) or your own picture. Each row can save the game's jersey, and this season's, as a picture
  to paint on. A club's centre ice can be changed where the game shows the club's own ice.
- **The custom teams** (the 12 NHL copies under Custom Teams, Coachella Valley, Henderson, the prospect pools) are drawn
  by the game like teams made in Create a Team, so their Jerseys & ice opens a window that looks like Create a Team:
  - pick the crest out of the game's create-a-team logos, use your own picture, or keep the team's own crest
    (Coachella Valley, Henderson);
  - pick the home jersey, the away jersey, the pants, the socks and the numbers, with the game's own pictures;
  - type three team colours and press "Paint everything with these colours";
  - then fine-tune each piece (jersey, pants, socks, helmet, gloves, numbers, crest, the goalie's gear) for home and away.

  The centre ice at their home games shows the crest. Goalie gear follows the new colours. A crest picture needs
  "Photos, logos and team names".
- **Shared centre ice.** The national teams all play on one centre ice, and so do the DEL clubs. You can put your own
  picture on it; the window says that the change shows at every one of their home games.
- **Winter Classic teams** (and the second EASHL team) show the jerseys of the team whose jerseys they wear, with a note
  that a change shows on both.
- **Lines.** Set a team's four lines, three pairs and two goalies, the power play (also with 4 skaters), the penalty
  kill (4 and 3 skaters), overtime, the five shootout shooters, the two extra attackers, and who wears the C and the A.
  Click a place, then a player. The tab checks the game's rules as you go (20 dressed, goalies only in goal, nobody
  twice in one unit group, at least 6 defencemen, the letters). The game plays your lines in Play Now and shows them in
  Roster Management > Edit Lines; a new Season or Be a GM picks its own lines at the start (change them there in
  Coaching Options). Every later update keeps your lines while all those players are still on the team; if one has
  left, the update's lines are used and the List of changes says so.
- **Strategy.** The game's own Strategy menu, with its words and in its order: Forecheck, Neutral Zone, NZ / FC, Off
  Pressure, Defensive Pressure, Defensive Strategy, Penalty Kill, Powerplay, PP Carry / PP Dump, and the sliders of each
  forward line and defence pair. A new Season or Be a GM starts with them. The roster also holds tendencies the game's
  menu never shows; they are at the end of each part, marked "not in the game's menu". Kept through later updates too.
- **Player type and face** (testers' wish). The card has a **Type** list with the game's own letters: forwards GRN
  Grinder, PLY Playmaker, SNP Sniper, PWF Power forward, TWF Two-way, ENF Enforcer; defencemen DFD, OFD, ENF, TWD;
  goalies STD Stand-up, HYB Hybrid, BUT Butterfly. Edit Lines and Team Rosters show the type next to the player's
  rating. A player who moves from forward to defence gets his new position's usual type. **Face**: the head number (the
  hair comes with it), skin and eye colour; "Face of a player..." finds a player and takes his face, or picks one of the
  game's generic heads (shown as pictures). Only faces the game has can be picked.

## 0.10.4 (2026-10-13)

- **Equipment and "Jerseys and ice..." now really fill the whole window**, over the Puck Peak logo. In 0.10.3 they still
  started below the logo.

## 0.10.3 (2026-10-13)

- **After "Update now" the old window closes by itself.** Before, the new version opened but the old window stayed
  behind and said "A roster is being made right now" when you tried to close it; only Task Manager helped. This version
  closes it, and when it starts it also closes an old window left behind by an earlier update.
- **Equipment uses the game's own words.** Jersey tuck: None, Left, Right, Full. Sock tuck: None, Front, Back, Full.
  Stick tape: ten colours (Black, White, Blue, Red, Yellow, Green, Orange, Light blue, Pink, Purple).
- **New in the Equipment window (skaters):** Visor tint, Shoulder pads (Small / Large) and Pant length (Short / Long), like
  the game's Customization menu. A player you create in the editor starts with the game's plain choices (no visor, no
  tucks, white tape). A neck guard is only possible for goalies: skaters have no such setting in the game's roster.
- **Equipment and "Jerseys and ice..." are bigger still**: they now cover the Puck Peak logo too, so more gear fits on
  the screen.
- **For testers: `equipment-test`** (command line) saves a roster in which each player wears one tuck, tape colour,
  tint, pads or pants number, so the words can be checked in the game's Edit Players. We have not seen the new numbers in the game yet:
  tell us if a word does not match what the game shows.

## 0.10.2 (2026-10-12)

Fixes from testers of 0.10.1.

- **Saving a roster no longer fails with "Green / Red has 0 captain(s) and 0 alternate(s)".** It happened after a goalie or
  skater was moved off a team that then could not dress 2 goalies and 18 skaters: the team lost its captain and alternates and the
  safety check refused to save. The Roster editor now says so when you press Apply ("Seattle Kraken would have only 1 goalie. A team
  needs 2 goalies and 18 skaters.") and the player stays where he is. The safety messages also call those two teams Seattle
  Kraken and Vegas Golden Knights instead of "Green / Red" and "Black / Blue".
- **The game's own roster works with more kinds of game folders.** "The game's icon was not found" came up when the game
  folder had a different layout; the program now takes the icon from wherever it lies, and uses its own picture when there is none,
  so the roster is still made. (If the game still says "no disc": make sure you start from the version listed in RPCS3, and use
  this version; older ones had other problems with it.)
- **Equipment: only gear the game can draw.** The game's table holds the sticks, gloves, skates and helmets of NHL 10 to 14 too,
  and NHL Legacy draws those plain blue. The Equipment window now lists only the models Legacy has pictures for (what a player
  wears now always stays listed). Goalie pads, blockers, trappers, sticks and masks too.
- **Equipment and "Jerseys and ice..." fill the whole window**, with bigger pictures.
- **The editor shows the player type** (GRN, PLY, SNP, PWF, TWF) next to the overall. The game works out its own overall from the
  ratings and that type, so the number can differ from the one the editor shows (your edited ratings are in the game as you set
  them). Making the editor's overall match the game's exactly is planned.

## 0.10.1 (2026-10-11)

- **Easier short names for European clubs** on the scoreboard and in Select Teams: three letters, the way each club is best
  known: Frölunda **FRO**, Färjestad **FAR**, Davos **DAV**, Servette **SER**, Nürnberg **NUR**, Sparta **SPA** and so on for
  the SHL, Liiga, Extraliga, DEL, National League and Norway. (The old ones were the leagues' own codes: FHC, FBK, HCD, GSHC ...)
  AHL and junior clubs keep theirs. Run the update once more with "Photos, logos and team names" on to get them.

## 0.10.0 (2026-10-11)

- **The program looks for a newer version** when it starts (at most twice a day, silently when you are offline). If one is out
  it asks: **Update now** downloads it, checks the file, and restarts into the new version; **Later**; or **Skip this version**.
  Your settings and rosters stay. It can be switched off in step 1. Ratings and league data are also downloaded from the
  newest release, so they stay fresh between versions. (Windows only; Mac and Linux are shown the download page.)
- **"Start RPCS3" from the program** no longer ends in RPCS3's error "vcruntime140.dll was incorrectly installed": RPCS3 was
  given the program's own temporary folder in its search path and loaded our copy of that file. (A first fix only cleaned the
  path; the program also told Windows to look in its own folder first. Both are cleared now.)
- **Goalies' equipment and a picture of your own on the mask.** On a goalie's card, **Equipment...** has the mask, pads, blocker,
  trapper, stick, tape, jersey tuck and neck guard (the game's own choices, with its pictures). **My picture...** puts a picture
  of your own on his mask (512 x 512; **Save the mask layout to paint on** gives you the game's own to paint over). The goalie gets
  a mask number nobody else wears, so no other goalie changes; it shows in the game after "Photos, logos and team names" is run.
  A goalie's jersey is his team's jersey: use **Jerseys and ice...** (My picture) for it. Not played in the game yet.
- **Equipment in the Roster editor.** On a skater's card, **Equipment...** opens the game's own choices: stick (with the game's
  menu pictures), tape (black / white), helmet, visor, gloves, skates, jersey tuck and sock tuck. **Apply to this player**, or
  **Apply to the whole team** for tape, helmet, visor and the tucks. Kept in My edits and applied after every update. The game has
  2014 models only: pick the nearest to what the player uses. Which tuck number is which (front /
  back, none / short / long / full) is a guess from the game's words until someone checks it in the game.
- **Short team names on the scoreboard.** Clubs whose name the game already knows kept their old short code (Frölunda
  showed "VF" instead of "FHC"). The short codes are now written for every club. Run the update once more with
  "Photos, logos and team names" on.
- **Utah's jersey** no longer shows a faint Arizona coyote under the new logo (the shine map still carried it).
- **Helmets:** Utah, Seattle and Vegas now have their own logo on the helmet, and their helmets, gloves and gear are in
  their own colours instead of Arizona's red and the All-Star colours.
- **Centre ice (Utah):** the rink picture under the centre-ice logo no longer shows the coyote.
- **Team logos** on the team screens (top left) were drawn a little up and to the left of their frame; they are now centred.
- Not done yet: the home ice of Seattle and Vegas still uses Nashville's centre logo (they share its arena in the game's files).

- **A new window in the look of the game's menus.** Stadium blue, the white and red arc, the Help bar at the bottom
  with the keys (Enter updates, D shows the details, L1 / R1 or Ctrl+Page Up / Page Down switch tabs). The window no longer flickers or tears when
  you move it or change its size, and buttons, tabs and lists move smoothly.
- **A real progress bar** in the Help bar, with the percentage and what is being done right now.
- The result of an update opens in its own panel next to step 2 and stays (dimmed) while the next update runs.
- Questions (delete a roster, restore default, close while working) and the Roster editor's windows (Team, My edits,
  Jerseys and ice) now open inside the window.
- Roster editor: click a column title to sort the players, arrow keys move through the list, Ctrl+S saves.
- Roster editor: a rating below 40 that the game's own roster gives a player (for example a defenceman's Faceoffs)
  no longer stops Apply.
- Windows: the window needs Microsoft Edge WebView2 Runtime (part of Windows 11 and an updated Windows 10). Without it
  the old window opens, as before.

## 0.9.3 (2026-10-11)

- **Game crash in Select Teams** (switching league, for example to the Czech one). The team names the program wrote were
  longer than the game has room for. Names are now cut to fit the game's own limits (long names split over two lines,
  for example "Motor České" / "Budějovice"), and a text file that would still be too long is not installed.
  Run the update once more with "Photos, logos and team names" on to rewrite the names.
- **Likely real cause of that crash:** the program wrote some team name lines as an empty text (for example the small line
  above "Timrå IK"); the game's own files never do that and Select Teams crashed on those teams. Empty lines are now written
  as the game writes them. Run the update once more with "Photos, logos and team names" on.
- **Restore default** put back the pictures but left the roster as it was: it took the roster you were restoring (made
  by this program from the game's own roster) for the game's own roster. It now starts from your game disc.
- **"Something went wrong: 273 does not fit in 8 bits"** (a tester with the American game and rosters of the game's own
  layout). A placeholder player record with an impossible birth year made the draft step fail; such records are now left alone.
- **Roster editor ratings.** Changes you typed but had not pressed Apply on are now taken when you save or click another
  player, and a player who is also on a national team gets the new ratings on both cards.
- **First start without any saved roster.** If RPCS3 does not list your game, the window asks you to pick the game
  (.iso file or its folder) and starts from the game's own roster. Command line: `--game`. A new save never takes the
  game's own slot (...00) any more; the first one is ...01.

## 0.9.2 (2026-10-07)

- **Linux fix** (from a tester's own fixes, who ran it on Linux). The Linux window now starts (it stopped at start before).
  Teams without an IIHF roster, such as Russia, no longer end up with too few defencemen and left empty: places are kept for
  every position.

## 0.9.1 (2026-10-07)

- **Restore buttons.** Every row in "What should be updated?" has a **Restore** button: press it and, in the next save, that part
  comes back as the game had it (press again to undo). Rosters (NHL, ratings, national teams, leagues) start from the game's own
  roster, with the rows you left on applied on top; the calendar is the game's own calendar (Season mode and Be a GM have their
  complete 82-game season back); "Photos, logos and team names" puts the game's own pictures, team names and jerseys back.
  The game's own roster is read from the game's clean roster save (`...0200`) when it still is the game's own, otherwise from your game disc.
  It is only read, never changed.
- **Restore default.** One big button puts everything back: rosters, calendar, pictures, team names and jerseys. It asks first, then saves
  as a new roster or replaces the picked roster (after a backup copy), as you chose in step 4.
- Not changed in this version: the calendar still has the 30 original teams, so teams play 76-80 games; use **Restore** on the
  calendar row if that bothers you in Season mode.

## 0.9.0 (2026-10-07)

- **New jerseys and centre-ice logos for Utah, Seattle and Vegas.** With "Photos, logos and team names" on, the update
  also installs home and away jerseys, pants, socks, number sheets and Select Jerseys pictures in each club's colours with
  its logo, and a centre-ice logo with the arena's name (Delta Center, Climate Pledge Arena, T-Mobile Arena). They are made
  on your PC from your own game disc, and "Restore the game's own pictures" puts the old ones back. Not yet checked in the
  game (`looks-test` writes only these files). The older Arizona versions, the Jets throwbacks and the old All-Star versions
  are left as the game has them.
- **Export only SYS-DATA roster (no RPCS3 needed).** Tick it in step 1, pick the community roster's SYS-DATA file in step 2, press
  **Make new roster**: the updated SYS-DATA is written into a new folder next to the program. For a Mac or Linux PC that cannot run
  RPCS3. No pictures, logos or jerseys are in it. (Replaces the link "No RPCS3 on this computer?"; the command line has `export-roster`.)
- **Roster editor: "Jerseys and ice...".** Pick an NHL team, press the button: change its two colours and crest, and for each jersey version
  the game has (the ones "Change Jerseys" shows) choose the game's own, a jersey made from your colours, or your own picture
  (a flat 1024 x 1024 colour map; the window saves the game's own as a template to paint on). The centre-ice logo can be the game's
  own, drawn from the team's logo and arena name, or your own picture. Kept on your PC and made in every update with "Photos, logos
  and team names" on (and My edits on); a version set back to "the game's own" is put back as it was.

- **Calendar 2026-27 is a normal step now (on by default).** The owner played all four test calendars: every game and
  date matched NHL.com. The game still calls the year 2015, and Seattle and Vegas cannot be in Season mode or Be a GM
  (those modes are built for 30 teams), so the calendar has the 30 original teams (they play 76-80 games).

## 0.8.1 (2026-10-06)

From the owner's tests of 0.8.0. Confirmed in the game: the Tampa Bay and Toronto logos, the team names on
the Select Teams screen, Delete / Open folder, and Season mode with a full update.

- **Update the roster itself:** step 4 now has **Update this roster** (the default: the roster you picked
  gets the newest data, so you do not collect new folders and load them) and **Save as a new roster**. Before a
  roster is changed, its old version is copied to the program's backups folder (the last 10 of each are
  kept). RPCS3 must be closed. The game's own roster is always saved as a new roster.
- **Roster editor:** no more As is / To be. It shows the roster you picked as it is, and **Save** updates that
  roster or makes a new one, like the Update tab.
- **Calendar 2026-27 (a test, switched off):** the real 2026-27 games and dates for Season mode (30 teams;
  `calendar-test` also makes a 32-team version). Switch it on in step 3 ("Calendar 2026-27 (test)") to try it.
  Not played in the game yet, so the game may still show its old dates.
- **Utah, Seattle and Vegas on the game's own roster:** the arena names, cities and team colours of the
  community roster (it has them already). `rendering-test` checks whether the game takes 3D textures
  (jerseys, the ice) from loose files, the first step towards new jerseys and a Utah centre-ice logo.
- **Manage your saves in the window:** each roster in step 2 has **Open folder** and **Delete**
  (to the Recycle Bin, with a question first; not while RPCS3 is running).
- **Logos:** the Toronto calendar and wide logos are blue now, like the game's own (Tampa Bay's stay white,
  as the game's own are). The Tampa Bay, Toronto, Washington, Boston and Vancouver logos on the favourite-team
  screen (and the plain and Dynasty logos) are no longer washed out white: they have their own
  colours again.
- **Team names on the team-select screens:** Play Now's "Select Teams" showed "Black All-Stars"
  for Vegas, "Green All-Stars" for Seattle and "Arizona Coyotes" for Utah, and old names for the
  rebuilt clubs. The names are now written to the lines that screen reads.
- **Season mode crash:** the game crashed when it started a season with a roster made by 0.8.0 (the
  community roster and the game's own roster play it fine). It was not an Arizona or Utah problem:
  the community roster carries a player the game had already removed (Jonathan Drouin), and the
  update made him a free agent. He is taken off first now; checked in the game (the full update plays
  Season mode). A roster made by 0.8.0 gets its free agents on new links when updated again (not yet
  played). The command `season-test` makes a set of test rosters if it ever happens again.

Not yet checked in the game: the calendar, which roster the game loads at start after "Update this roster",
the arena names and colours of the game's own roster, and the loose 3D textures test (`rendering-test`).

## 0.8.0 (2026-10-05)

From the testers' feedback on 0.7.0.

**Players and rosters**
- **Free agents:** retired players leave the free-agent list (Datsyuk, Price, Rask...); NHL players
  without a contract today are on it (Reimer, Toews, Quick), and are added to the game if it did
  not have them.
- **Draft:** every player has his real draft: year, round, pick and team (NHL drafts since 2005).
  Will Smith and Stenberg are right now.
- **Draft prospects** play for a real club of their country (the CHL for North Americans) instead of
  custom "Prospects" teams, where the game's draft did not see them. A junior missing from his
  league's list stays with his club (Landon DuPont stays in Everett).
- **NHL.com's height, weight and hand** for every NHL player; players with the same name are no
  longer mixed up.
- **Goalie equipment** in the new team's colours after a trade.
- **Your own team for a missing club:** name a custom team after a club the game has no place for
  (Jokerit, Ajoie, Penticton, Coachella Valley...) and the update fills it with that club's players.

**Pictures**
- Logos have the game's own size (they no longer cover the record or spill out of the calendar);
  the Lightning logo is white, the Capitals logo has white edges.
- Extraliga players have photos now, and so do juniors their league's list leaves out (last
  season's photo). Studio photos on a grey backdrop are cut out like the rest. About 6,100 photos
  come with the program.
- Pictures that could not be installed are named in the List of changes.

**The program**
- Runs on **macOS and Linux** too (it finds RPCS3's folder there by itself).
- **Works without RPCS3:** pick a folder with roster saves instead (CrossOver, Wine, saves from
  elsewhere).
- The window keeps every step and your rosters in view after an update, and the steps stand out
  more.

Not yet checked in the game: free agents, draft data, prospects in the draft, logo sizes, goalie
gear, your own team. Known: Season mode crashed once when picking Arizona/Utah; it is being looked
into (tell us if it happens to you).

## 0.7.0 (2026-10-04)

- Fixed: updates stopping with "CERTIFICATE_VERIFY_FAILED" while checking NHL players.
- Fixed: the program closing at start with "couldn't open ... logo_100.png" (an antivirus or a
  cleaning program had removed its files).

## 0.6.0 (2026-10-04)

- No roster needed: start from the game's own roster on your disc.
- Positions from NHL.com, wingers on their own side of the lines.
- Today's logos on the favourite-team screen.
- One program with every picture inside; your own pictures are always kept.
- A clearer result and a List of changes grouped by team; EU / NA flags.
