# NHL Legacy roster save format

What is known about the roster save of NHL Legacy Edition (PS3, `BLES02153` / `BLUS31540`),
and the rules the game enforces on it. Everything here is implemented in `legacy_roster/`.

The game gives no error for a bad roster: it crashes in a menu, or silently keeps the previous
roster. `legacy_roster/verify.py` checks every rule in section 5 before a save is written.

## 1. Save folder

A roster save is a folder `<TITLEID>02NN` in `dev_hdd0\home\<user>\savedata` holding `ICON0.PNG`,
`PARAM.SFO` and `SYS-DATA`. Other saves of the game use other numbers (`0000` profile, `08xx`
hockey card, `13xx` Build Your AI).

`PARAM.SFO`: `SAVEDATA_DIRECTORY` must equal the folder name; `SUB_TITLE` (up to 127 bytes) is
the roster name shown in the load list; `DETAIL` is `Rosters`. RPCS3 saves are not signed.

**EU and NA.** The European version is `BLES02153`, the North American `BLUS31540`. Their saves'
`PARAM.SFO` differ only in `TITLE` ("NHL™ Legacy Edition" / "NHL® Legacy Edition") and the folder
name (`PARAMS` is empty in RPCS3 saves). Both read the same `SYS-DATA`: the community shares one
roster file for both, dropped into `BLES021530200` or `BLUS315400200`. Both discs hold the same
`cache.big`, `nocache.big` and `cacheboot.big` contents (same entry counts, same 8 text files).

## 2. SYS-DATA wrapper

Big-endian unless noted. File length = `0x2C` + section size (2,456,120 bytes for rosters). The section size is the
length of the game's roster database in memory, and the game reads a roster of that length only: a roster for the
game patch's stage S is 864 bytes longer (docs/GAME_PATCH.md, `gamepatch.SECTION_SIZE`).

| Offset | Content |
|---|---|
| 0x00 | 16-byte magic `PS3RosterFile` |
| 0x10 | CRC-32 (zlib) over `[0x1C, end of file)` |
| 0x14 | version 4; 0x18 zero; 0x1C compressed flag; 0x20 a small counter |
| 0x24 | section size |
| 0x28 | CRC-32/BZIP2 (poly 04C11DB7, init and xorout FFFFFFFF, not reflected) over the section |
| 0x2C | zlib length (little-endian), zlib stream at 0x30, zero padding to the section end |

zlib level 6, memLevel 9, wbits 15 reproduces the game's own output byte for byte. Saves written
by other tools may be compressed differently; only the content has to match.

## 3. The database inside ("TDB")

- `DB` header (0x18 bytes): `44 42 00 08`, `01000000`, db size, 0, table count, CRC-32/MPEG-2
  (init FFFFFFFF, xorout 0) of bytes 0..0x14.
- Table index: 4-character tag + offset per table, then the tables, then a trailer.
- Table: 40-byte header, 16-byte field definitions, fixed-length bit-packed big-endian records
  (`max records x record length`), optional tail. Header +0x08 record length, +0x14/+0x16 max and
  current record count, +0x1C field count, +0x24 CRC-32/MPEG-2 of header bytes 4..0x24.
- Field definition: type (0 = UTF-8 string, 3 = unsigned integer), bit offset, tag, bit count.
- **Checksum chain.** Each table's first four bytes hold the CRC-32/MPEG-2 of what precedes it:
  the table index for the first table, the previous table's bytes from 0x28 on for the others.
  The last table ends with the CRC of its own bytes from 0x28. A broken chain makes the game
  ignore the file without a message.
- Records past the current count hold stale data. Table order has no meaning.
- **Header word at 0x18** is `0000ffff` in every table of the game's own roster, ROSTER2526 and what this
  program writes. The community's 2026-27 roster has `00010b81` in `caBZ` and `000100e1` in `ulGe`:
  flag 1 and a row, the last row the game removed (link row 2945 and entry row 225 are Jonathan Drouin's;
  he has no contract team and is on no free-agent list: a player removed in the game before the roster
  was saved). Our update did not know, treated him as a player of St. Louis, made him a free agent, and
  Season mode crashed on his link (`0x00381c24`, owner 2026-10-06). `builder.drop_removed_player` removes
  the two rows before anything else and clears the words; `verify.py` insists they are `0000ffff`.
  The meaning is inferred from this one roster; removing the player fixed Season mode (owner, 2026-10-06).
  A roster made by 0.8.0 from it keeps the words but the rows moved: `stale_markers`, free agents relinked.

## 4. Names and meanings

Table and field tags in the file are scrambled (`cPbu`, `RMbQ`...). The game disc carries the
real names: `db/nhlng-meta.xml` inside `PS3_GAME/USRDIR/cacheboot.big` lists every table and
field with tag and name. `tools/decode_schema.py` turns it into `legacy_roster/schema_names.py`,
and every table then answers to both (`P.get(i, 'lastname')` equals `P.get(i, 'RMbQ')`).

The tables that matter:

| Tag | Name | Notes |
|---|---|---|
| `ttOk` | exhibitionteams | 252 teams, table full. `league`, `fullname`, `shortname`, `artabbr`, `artid`, `ahlaffiliate` |
| `cPbu` | exhibitionplayerbiotable | one record per player; key `game_id` |
| `ulGe` | exhibitionrostertable | one entry per player per team; 71 one-bit line slots |
| `caBZ` | exhibitionplayers | link id (`index`) to `playerid`; roster entries point at links |
| `QEoV` | exhibitionfreeagents | link ids of unattached players |
| `yvSd` / `yuHm` | exhibitionskaterai / exhibitiongoalieai | attributes, keyed by `game_id` |
| `lVMf` | exhibitiongoalieequipment | a goalie's gear, keyed by `game_id`: `pads`, `blocker`, `trapper` models and nine zones of colour each (`padszone1color_r` ... `trapperzone9color_b`), `showcustomcolors` |

**Teams** (`ttOk.league`): 0 NHL, 1 AHL, 2 SHL, 3 Liiga, 4 DEL, 5 Extraliga, 6 National League,
7 Norway, 8 national teams, 9 OHL, 10 QMJHL, 11 WHL, 12 Top Prospects, 13 custom, 14 Winter
Classic, 15 EASHL.

**Players.** `position` 0 C, 1 LW, 2 RW, 3 D, 4 G. `handedness` 0 left. `height` inches - 54,
`weight` pounds - 120. `intlcountry` is a country code; `state` is a province/state code for
North Americans and the country code for everyone else. `headid` is the 3D head model (60000
and up are generic heads), `artid` + `hasportrait` the menu photo, `audioid` the commentary
name. `team` is the contract team + 1 (0 = none), `contractlength`, `contractdollars`.
`proteam` and `draftteam` are NHL team + 1 in five bits (Vegas, slot 31, cannot be stored). A roster for the game patch
gives `proteam` six bits (`gamepatch.rights_wide`, patch 0.23: the patch's `db/nhlng-meta.xml` describes the same six bits,
and the game reads a roster whose fields differ from that description as damaged); `draftteam` stays five.
`draftyear` is the year - 1900, 255 for undrafted; `draftround` (4 bits) and `draftposition` (9
bits) are the round and the **overall** pick (the disc: Gaudreau round 4, pick 104; Saad round 2,
pick 43). The game gives a junior who is not drafted yet his draft year with round 0 (2014-2017 on the
disc), and the disc's Legacy Edition already holds the 2015 draft. `draft.py` writes NHL.com's
picks (0.8.0).

**Goalie equipment.** The game painted every goalie's gear in his 2014 team's colours on white
(`showcustomcolors` 1 for all 62 NHL goalies on the disc; Hiller's pads Calgary red and gold).
The colours are free RGB values; `Builder.goalie_gear` repaints the coloured zones of a goalie who
changed club (0.8.0, waiting for the in-game check).

**Attributes.** Stored value = rating - 36 (six bits, ratings 36 to 99). The field for each
attribute is in `legacy_roster/schema.py` (`LIST_SKATER`, `LIST_GOALIE`); for example `c_speed` =
`bEdA`, `c_faceoffs` = `KrwV`, `c_gsh` = `DTrq`. `c_potential`, the growth fields and the
traits are not in the ratings list and are left alone.

**Roster entries.** `key` = team x 40 + slot. `playerindex` is the link id. `rosterstatus` = 1
when dressed. `captain` 1 = C, 2 = A. `playerstyle` equals the player's style in his attribute
record. The line slots are named: `l1lw l1c l1rw l1ld l1rd` ... `l4rw`, `pp1*`, `pp2*`,
`pp4_1*`, `pp4_2*`, `pk4_1*`, `pk4_2*`, `pk3_1*`, `pk3_2*`, `ot_1*`..`ot_3*`, `s1`..`s5`, `x1`,
`x2`, `g1`, `g2`.

## 5. Rules the game enforces

1. All five checksums (section 2 and 3).
2. Roster entry keys are team x 40 + slot, slots 0..n-1 without gaps, at most 40 per team.
   Breaking it crashes Roster and Team Management.
3. A player's contract team must be a team he is on. NHL players need a length and a salary;
   free agents have no contract fields set.
4. Each line slot has at most one holder per team; a player is dressed exactly when he holds a
   slot. NHL and national teams dress 20: 12 forwards, 6 defencemen, 2 goalies.
5. Letters: the update gives every NHL team three (one C and two A, or three A), but since 0.81.0 the game and
   `verify` accept any number, none included (lab round 55: Play Now and Edit Lines with none, all C, all A and a
   goalie's letter). Season / Be a GM with such teams is not played yet.
6. The free-agent list only holds links that no roster entry uses.
7. **Hard limits.** No team can be added (the team table is full and team ids are 8-bit) and no
   team can change league. Only existing slots can be refilled.

## 6. The community rosters

The updater works on this roster family (the 2025-26 roster "ROSTER2526" and its successors); its
conventions differ from the game's own roster.

- 32 NHL teams: slot 22 (the old Arizona slot) holds Utah, the two All-Star slots 30 and 31
  hold Seattle and Vegas. Custom teams 222-233 are copies of twelve NHL teams with current
  branding and must mirror their primary team. Custom slots 234 and 235 are two AHL teams.
- Birth years are stored as year - 1910 (stock: year - 1900), so ages are right in a game whose
  calendar starts in 2015.
- About 1,250 blanked player records (last name starting `ZZ`) are spare records for new players.
  About 1,250 more teamless records still carry the game's − 1900 birth year (their draft year shows it).
- The European league slots hold draft-class pools and NHL prospect pools; 27 club slots are
  empty. Pool slots got pool names and pool art abbreviations (`P261` …); their original art
  (for example `BIF`, `VF`, `HCAP`, `STAV`) is in the stock database on the disc.
- Eight national teams are empty.
- AHL, CHL and pool teams do not have complete lines.
- **Names of the NHL slots in the save** are still the old ones: slot 22 "Arizona Coyotes" (art
  `PHX`), 30 "Green / Red", 31 "Black / Blue" (All-Star art `EAS` / `WES`). Utah, Seattle and Vegas
  carry their names and branding through custom slots 229, 228 and 226; in the game's menus they
  are listed under the custom teams, not the NHL (owner, 2026-10-03). AHL abbreviations
  (`abbrname`) were stale in the base (Utica `ALB`); the AHL step writes current ones.
- National-team goalies have second player records of their own (same name and birthdate).
- **The community's 2026-27 roster** (shared as one SYS-DATA, October 2026) keeps the same layout,
  with these differences:
  - slots 22/30/31 are named Utah Mammoth, Seattle Kraken, Vegas Golden Knights, with a few more
    team fields changed (colours, `Nzao`, `aDub`; the update leaves them as they are);
  - the custom copies 222–233 are out of step with their NHL teams (14–25 of ~25 players shared;
    Ben Hutton only on the Golden Knights copy);
  - France, Germany, Italy, Latvia, Slovakia and Switzerland are empty; Czech Republic and
    Denmark dress 20 but hold no line slot (the community ships it so; the update deals lines);
  - 6,770 player records (25 more), 52 free agents;
  - slot 67 is named "Karlskrona Hockey" with no players.

**The game's own roster** (`db/nhlng.db` on the disc; `stock.py`, 0.6.0). Facts measured on the NA
disc (the EU one has the same archives):
- **Tables.** The database has 134 tables. All 39 of a roster save are among them, with the same
  record lengths and field definitions. A roster save differs only in these points:
  - it holds those 39, in its own order (`stock.ROSTER_MAX`);
  - each table has room to grow: the save's maximum is the disc's count plus room (cPbu 5,632 →
    7,988, ulGe 5,532 → 10,879, caBZ 6,087 → 9,955);
  - every table header has byte 7 = 6 (disc 2);
  - the player-link table `caBZ` carries one index: header byte 0x1D = 1, then 16 bytes after its
    records, `prCe` 01 01 00 00 00 00 00 02 00 00 00 01;
  - the database ends with four `DB` bytes;
  - the wrapper is `PS3RosterFile`, version 4, compressed, counter 1, section 2,456,120 − 0x2C.
- **Layout.** Every club slot has its real 2014-15 club with players. Slots 30/31 hold the All-Star
  teams (49 players, all also on their own teams). Custom slots 222–251 are "Custom Team 00–29",
  switched off (`active` 0) and empty. The 21 national teams have squads; there are 340 free
  agents. Birth years are year − 1900; there are no blank records.
- **Player ids** (`game_id`) are 14 bits, and the disc already uses ids up to 16,343. New records
  take free ids in the gaps.
- **A PARAM.SFO** for a version that has no save to copy: `savedata.roster_sfo` makes one from
  scratch that is byte-identical to the game's own (14 keys, `*ICON0.PNG`/`*SYS-DATA` flags 0/1,
  `RPCS3_BLIST`, `DETAIL` "Rosters", …). The icon is the disc's `PS3_GAME/ICON0.PNG`.
- **Not proven yet:** that the game loads a roster made this way (`cli stock-test`, ROADMAP).

**Table capacities** (current / maximum records in a roster save):

| Table | Current | Max | Notes |
|---|---|---|---|
| `cPbu` players | 6,745 | 7,988 | could grow; untested in the game |
| `yvSd` / `yuHm` skater / goalie attributes | 6,056 / 689 | 7,331 / 957 | one row per player, by `game_id` |
| `ulGe` roster entries | 3,600 | 10,879 | |
| `caBZ` links | 3,611 | 9,955 | |
| `QEoV` free agents | 17 | 1,767 | |
| `ttOk` teams | 252 | 252 | full |
| `caBZ` / `vaHq` | | | `vaHq` (draft picks) points at player links too (`playerindex`); links nothing uses are dropped by `Builder.finish` |
| `vaHq` draft picks | 1,260 | 1,260 | full: 6 years × 30 teams × 7 rounds |
| `xieT` salary extras | 30 | 30 | one per NHL team 0–29 |
| `ihmS` / `byED` NHL schedule / future schedule | 1,231 | 1,291 | see section 8 |

## 7. Game files and overrides

The disc holds a few large "EB" v3 archives (`cache.big`, `nocache.big`, ...; layout in
`tools/isotools.py`). Before reading an archive the game looks for a loose file under
`dev_hdd0\game\<TITLEID>\USRDIR\`, so single files can be replaced without repacking:

| What | Path |
|---|---|
| Menu portrait | `fe/ion/artassets/playerheads/p8001_12000/p<artid>.big` (folders `p0_4000`, `p4001_8000`, `p8001_12000` for every id above 8,000, `silhouettes`; + `playerheadssmall`) |
| Team logo (menus) | `fe/ion/artassets/teamlogos/t<artid>.big`; variants `teamlogossmall/s`, `teamlogoswide/w`, `teamlogoscalendar/c`, `teamlogosdynasty/d`, `teamlogosreflection/r` (NHL only) |
| Text | `fe/loc/nhl_<lang>.db` (same TDB format) |
| Main-menu lists | `fe/ion/game/menus/mainmenuitems.big` (in `boot.big`; a BIGF with an Apt movie; `art/menus.py`, docs/notes/menus.md). A loose copy in USRDIR is read first (lab, 2026-10-18) |
| Default database | `db/nhlng.db`, `db/nhlng-meta.xml` (in `cacheboot.big`, stored uncompressed) |
| 3D heads, jerseys, ice | `rendering/**/*.rpsgl` (`\x89RW4ps3`) |

**3D textures** (read 2026-10-06; `art/rpsgl.py`; archives `nocacherender.big` 1.7 GB and `cacherender.big` 1.4 GB, EU
and NA identical). A `.rpsgl` is a "chunkzip" (128 KB chunks of raw deflate) around a RenderWare PS3 file with
named DXT1/DXT5 rasters and a full mipmap chain; repacked with zlib level 9 it is byte-identical to the disc's.
The game's makers made each mip by hand (not a box filter); under alpha 0 the centre-ice files hold the ice's own colour (231, 233,
231), and the game's logos are an opaque disc with thin edges. Partial alpha on the ice showed as a hatch in the lab (round 32),
so the centre ice is flattened onto that colour: every mip opaque or clear (`dds.flatten`, `Rpsgl.replace(flat=)`).
`Rpsgl.replace(coverage=)` makes the mips from
alpha-weighted colour with a 3-pixel colour bleed (`dds.mipmaps`, `bleed`) and encodes them with `dds.encode_level`
(Pillow's blocks, the poor ones encoded again: Pillow's DXT5 alpha never reaches a block's end values). Normal maps
(`*_nm`) get mips per channel; opaque DXT1 keeps Pillow's blocks (`OPAQUE_SLACK`). docs/notes/centre-ice-quality.md.
Named by the team's numeric art id (22 Utah, 30 Seattle, 31 Vegas; the Arizona files are still the ones for 22):
`rendering/jersey/texlib_<style>_<art>_<variant>` (rasters `jersey_.._cm`, `_sm`, `_0_nm`, `font_..`; the same UV
layout for every team; Utah has variants 0, 1, 3, 4 in styles 0 and 1, 3 and 4 the home and away), `name_<style>_<art>_<variant>_cm`,
`pant/texlib_..`, `sock/sock_.._cm`, `icesurface/centerlogo_<art>_cm` (1024x1024 DXT5, the centre-ice logo;
`exhibitionarena.centericelogo` is 0 in every row of the rosters seen and the game does not read it, lab round 58), `icesurface_<arena art>_bm` (rink picture), `banner_`,
`crowd/prop_team_`. **Which centre-ice file a home game shows depends on the league** (lab rounds 31 and 58, RPCS3's log):
the DEL's clubs take their arena's art (`OEtS.arenaartid` of the team's `arenaid`: all 14 the DEL's 197), the national teams
always 501, every other league the home team's own art, the NHL too (`looks.shown_centre`). A centre file the disc lacks draws as a plain blue square, no crash; an `arenaartid` with no stadium
files crashes. The menu previews of jerseys are
`fe/ion/artassets/jerseys/jersey_<style>_<art>_<variant>.big` (BIGF, readable as above). The game asks for
`<game folder>/rendering/...` first (RPCS3 log) and loose files there are used (`cli rendering-test`, 0.9.0). The community roster already
has Utah, Seattle and Vegas arenas (`exhibitionarena` rows 181, 186, 162) and colours; the game's own roster has
Arizona's and the All-Star slots' (`builder.nhl_identity` sets them for that source).

**Which id.** A portrait file is named by the player's `artid` (`cPbu.rnOl`) and shows when `hasportrait`
is 1. A logo file is named by the team's `ttOk.artid` (NHL slots 0–31: the slot number; custom
teams 20000+).

**Art files.** Each `.big` above is a small `BIGF` archive:
- header: big-endian file count at +8, header size at +12;
- entries: u32 offset, u32 size, NUL-terminated name.

It holds an "Apt" UI movie:
- part `0` "Apt Data:1:5:4";
- part `1` "Apt constant file";
- a 288-byte part, and empty `sg1`/`sg2` markers;
- **one image**: RefPack-compressed (`10 FB` + 3-byte size), which unpacks to a DDS.

| File | DDS |
|---|---|
| portrait `p` | 512×512 DXT5, no mipmaps |
| small portrait | 256×128 DXT5 |
| silhouette | 512×256 DXT5 |
| logo `t` | 256×256 uncompressed 32-bit |
| logo `s` / `d` / `c` / `w` / `r` | 128×64 / 128×128 / 128×128 / 256×256 / 256×512 |

A community loose-file logo seen in the wild had the same layout with mipmaps in its DDS.

More details:
- **The Apt data part** (`0`) is itself RefPack-compressed in about 60 % of the files. The image is the
  RefPack part that unpacks to a DDS (`legacy_roster/art/bigf.py`).
- **Part names** (the movie's character ids: `7`/`6`, `3`/`2`, `157`/`156` …) differ from file to file.
  So a new art file is always made from an existing one of the same kind, with only the image swapped
  (`ArtFile.with_image`).
- **The 16-byte trailer** after the last part is no hash of the file, its parts or the image that we could
  find (MD5, SHA-1, SHA-256 tried). It is kept from the template, and the game does not mind (art test,
  2026-10-03).
- **Portrait geometry.**
  - 6,567 of 9,224 portraits are 512×512, the rest 512×256. The photo always sits in the top
    512×256: a cut-out (transparent background), the top of the hair at y 26, the middle of the head
    at x 235, the head 144 px wide at its widest, nothing below y 247 (medians of `images.head()` over
    the disc; the head width varies 8 % between players).
  - The small portrait (256×128) is the same picture at half size (top 13, middle 101, width 74).
  - Logos are drawn with transparency, inside an area that depends on the kind (medians of the
    disc's NHL logos, alpha above 40; `images.LOGO_BOX`): `t` 0.16-0.84 × 0.20-0.79 of the picture,
    `d` 0.14-0.86 × 0.19-0.83, `c` 0.05-0.70 × 0.05-0.62 (top left only), `w` 0.09-0.89 × 0.11-0.90,
    `s` 0.05-0.95 × 0.14-0.86. Drawn over the whole canvas (0.4-0.7) they covered the record on the
    team screens and spilled out of the calendar's cells. `t` has a white edge and a soft
    shadow; `d` is a small `t`; `c` is the logo enlarged and cut off on the right; `w` is a big
    zoomed piece faded to a circle; `s` is a banner in the team's colours with part of the logo.
  - `r` (256×512, `teamlogosreflection`, NHL art ids 0–29 on the disc) is the logo in the upper
    half (about 190×180 px around y 125) standing on a faint mirror image of itself that fades out
    within about 50 px; the rest is transparent. This is the picture of the favourite-team
    carousel ("Choose Your Favorite Team" on a new profile, owner's screenshot 2026-10-04: Utah's
    name with the disc's `r22`, the Coyotes). The carousel is sorted by city, so Utah sits where
    Arizona was. The updater writes `r` for the 32 NHL slots since 0.6.0 (Seattle and Vegas, 30/31,
    from `r0` as template).
- **Portrait ids.**
  - The disc's ids run 1–12,401 in three folders.
  - The community roster gives 134 players ids from 12,402 to 13,826, so a loose-file portrait pack of
    its own must exist; the owner's RPCS3 has none.
  - **Folder rule** (from the RPCS3 log): ids up to 4,000 are in `p0_4000`, up to 8,000 in
    `p4001_8000`, every higher id in `p8001_12000` (the game asked for `p8001_12000/p12402.big`).
  - `artid` is 16 bits; the updater gives new portraits ids from 20,000 (`art/portraits.py`), since 2026-10-20 from
    40,000 (`FRESH_IDS`).
  - **A portrait file is shared by every roster of that game version** (and every RPCS3 user). The community's
    2026-27 roster uses ids up to 30,007 (165 inside 20,082-30,007). A number is good for one person on the whole PC:
    `install.scan_claims` reads every roster save and portrait file; the updater never gives out a number someone else
    uses and takes its own file off one that turns out to be someone else's (docs/notes/player-pictures.md).
- **Proven in the game (art test, 2026-10-03):** a loose portrait replaces the disc's (McDavid); a
  new id below 4,000 and one above the disc's range both show; a loose logo replaces the disc's (the
  Team Rosters screen shows the dynasty variant `d`). A missing loose file falls back to the
  silhouette. Nothing needs a mipmap.
- **Team names are not read from the save for most teams.** Slot 107 was "Kladno" in the save; the
  game still showed "Chomutov". The game takes them from its text file (below). Custom teams show
  the text whose key is their `shortname` (`LAS_VEGAS` shows "Las Vegas"; a shortname with no text,
  like "2026 Prospects 2", shows nothing). In the game (owner, 2026-10-04) texts the update added
  under "2026 PROSPECTS 2" and "Coachella Valley" for custom teams with those shortnames still
  showed nothing, while every changed text of an existing key showed (Utah, Timrå). The keys that
  work are all in the game's style (capitals, digits, underscores); since 0.5.0 custom shortnames
  are written that way (`2026_PROSPECTS_2`, `COACHELLA_VALLEY`) and added keys keep their case.
  Waiting for the in-game check.
- **Code.** Reading and writing: `legacy_roster/art/` (`disc.py` reads the player's own disc image or
  folder, `bigf.py`, `refpack.py`, `dds.py`). Photos and logos: `portraits.py` (ids in the roster),
  `images.py` (Pillow: cut-out, head finding, logo styles), `install.py` (download, write, back up,
  remove). The one-off in-game experiment is `lab.py` (`cli art-test`).

### The text file (`fe/loc/nhl_<language>.db`)

On the disc in `cacheboot.big`, one per language (`eng_us`, `fre_fr`, `ger_de`, `swe_se`, `fin_fi`,
`cze_cz`, `rus_ru`; `lng_lg` is the language list). The game reads a loose copy from
`dev_hdd0/game/<TITLEID>/USRDIR/fe/loc/` first (RPCS3 log). Code: `legacy_roster/art/loc.py`, which
rebuilds every language file of the disc byte for byte.

- **Layout.** A "DB" with one table `LanguageStrings` (`GJCv`): `hashid` (`jKhj`, 32 bits),
  `stringid` (`VhAs`, type 13) and `sourcetext` (`bYbZ`, type 14), 16-byte records sorted by hash.
  Types 13/14 are Huffman-compressed strings stored after the records.
- **Huffman tree.** Node *n* is the 2-byte entries 2*n* (bit 0) and 2*n*+1 (bit 1). An entry (k, 0)
  goes to node k, an entry (0, c) is byte c. Node 0 is the root; the English tree is 660 bytes.
- **Strings.** Each one sits at its record's offset (from the start of the tree), with a length
  prefix of 1 byte (key) or 2 bytes (text) in bytes, then the bits, most significant first, in
  bits // 8 + 1 bytes. Offset 0xFFFFFFFF means no string.
- **After the strings.** Zero bytes to a multiple of 8, then the CRC-32/MPEG-2 of the table from
  0x28 on (the same chain rule as the saves). Table header +0x10 = where the strings end.
- **Key hash (found 2026-10-19, lab round 35).** `hashid` = `zlib.crc32(bytes(b & 0xdf for b in key), 0xFFFFFFFF) ^
  0xFFFFFFFF` (the game's `0xdbae20`): every byte loses bit 5, so letters lose their case and digits, `_` and spaces
  change too (`1` 0x31 -> 0x11). All 25,783 records of all 7 language files of the EU disc match. Until then this
  program took `key.upper()`, which is the same rule only for keys of letters alone; the "odd hashes" (about 45 % of the
  fixed keys) were the keys with a digit or a space, and every text the program added under such a key was never found
  (`TEAMLINE1_X`, `NICKLINE2_X`: the blank Select Teams names of 7 AHL and 3 CHL clubs). The meta file declares
  `hashid` a signed 32-bit key with an index sorted on it; the records are sorted unsigned and the game copes. Stored
  keys keep their own case (`NHLTeamName_MOD`, `NHLTEAMNAME_CHOM`, `ChangeDay`).
- **Team keys.** For a team with art code X the game asks for `NHLTeamName_X` (full name),
  `NHLCityName_X` (city: the Team Rosters header), `TXT_NICKNAME_X`, `TXT_NICKNAME_ALT_X` and
  `X_XLA_TEAM_X` (abbreviation). NHL slot 22 has art `PHX`, slots 30/31 `EAS`/`WES`. The disc
  already has some clubs the base roster does not use (`KLA` Kladno).
- **Select Teams keys (found 2026-10-06).** Play Now's "Select Teams" and Season's team lists read
  other texts: `TEAMLINE1_X` (the small line above the name: the city, or the nickname for a name
  that ends in its city: `Piráti` / `Chomutov`; empty for `MODO Hockey`), `TEAMLINE2_X` (the big line;
  NHL clubs carry ® or ™), `NICKLINE2_X` (the big line again, NHL and some clubs only) and
  `NHLTeamName_Abbr3_X` (the short code). The NHL slots also have texts under their number:
  `NHLTeamName_22`, `NHLCityName_22`, `CITYLINE1_22`, `NICKLINE2_22`, `NHLTeamName_Abbr3_22` (22, 30,
  31 held Arizona, Eastern and Western All-Stars; `Logo46` still reads Arizona, not found on a screen).
  `set_select_lines` changes them, and adds the lines a club has none of (an empty line 1 only empties an existing
  text); `loc.select_lines` splits a name the game's way. Until 0.8.0 the update wrote only the five keys
  above, so Select Teams showed 'Black ALL-STARS' for Vegas, 'Green ALL-STARS' for Seattle and
  'Arizona COYOTES' for Utah, and the old names of every rebuilt club (owner's screenshots,
  2026-10-06). `loc.NAMES_VERSION` rewrites the installed files when the set of texts changes ('#6': the game's hash).
- **Created teams in a real league (stage Y, 2026-10-19).** The game names a created team (slots 222-251) "Custom Team
  N" or by its city key (`COACHELLA_VALLEY`). With the patch's stage Y and a league other than Custom it asks for the
  club texts of its art code instead (`NHLTeamName_CVF`, `TEAMLINE1_CVF` ..., `HSK`): `portraits.names` writes both.
- **Text limits (found 2026-10-11, Select Teams crashed on switching league).** The longest text, in bytes, that the
  game's own English file keeps per kind of key: `TEAMLINE1_` 21, `TEAMLINE2_` 17, `NICKLINE2_` 14,
  `TXT_NICKNAME(_ALT)_` 16, `NHLTEAMNAME_` 31, `NHLCITYNAME_` 21, `CITYLINE1_` 12, `NHLTeamName_Abbr3_` 4,
  `X_XLA_TEAM_` 6. `loc.fit`/`loc.select_lines` keep every written text within them (each language's own file may
  have longer ones: `LocFile.limits()` takes the larger), and `install_names` refuses to install a file with a text
  over its limit. Not proven in the game that a longer text crashes.
- **An empty text is "no text" (found 2026-10-11).** In the game's own files all 33 empty texts (English) are stored
  with offset 0xFFFFFFFF (no string); none is a string of length 0. Writing one (the small `TEAMLINE1_` line of
  `Timrå IK`, `FRI`, `BLU`...) is the most likely cause of the Select Teams crash on SHL/Extraliga teams, because
  every changed team with an empty first line had one (`LocFile.set`/`set_existing` now mark an empty text absent).
  The owner's log: access violation in the `EAAudioCore Dac` thread (corrupted memory), the main thread holding
  the strings `LINE1_NAME`/`LINE2_NAME`, 190 ms after the team's logo was read. Waiting for the in-game check.
- **Promo texts (0.21.0).** The main menu's offline news panel (`TXT_OFFLINE_DYNAMIC_MSG_TITLE_<n>` / `_BODY_<n>`, 0-4;
  3 is the fighting tip, `_CLASSIC_` NHL 94) and the tuner-set notices (`TXT_TUNER_SET(S)_..._AVAIL(ABLE)`) are fixed
  keys (the HUT banner `FUT_NEWS_AND_EVENTS(_DESC)` stays: the community server serves HUT): `loc.PROMO` writes them with `set_existing`, the
  same text in every language, each within the longest text any language keeps for that key (`promo_limits`).
  docs/notes/promo-texts.md.

## 8. Schedules

Each league has a schedule table in the roster save except Norway:
`nhlschedule`, `nhlfutureschedule`, `favoriteteamschedule`, `ahlschedule`, `ohl…`, `qmjhl…`,
`whl…`, `swedish…`, `finnish…`, `german…`, `czech…`, `swissschedule`.

- **Fields.** Every record has `round` (3 bits), `status` (2), `day` (5, 0-based), `month` (4, 0-based:
  9 = October), `index` (= row number) and `home` / `away` team ids. The team ids are 5 bits in the NHL
  and AHL tables and 4 bits in the European ones. There is **no year**.
- **What the NHL tables hold** (read 2026-10-06, 81 of Anaheim's 82 games checked against NHL.com).
  `nhlschedule` is the real 2015-16 calendar before any revision (7 Oct to 9 Apr, with a 29 Feb); the
  owner's Season-mode calendar screenshot matches it row by row (Anaheim: 10 Oct at San Jose, 12 Oct home
  Vancouver ...). `favoriteteamschedule` is a byte copy with 200 spare rows (what the game uses it for is
  unknown). `nhlfutureschedule` is the real 2014-15 calendar. Only slots 0–29 play, 82 games each (41 home);
  slots 30/31 meet once (31 Jan: the All-Star game). Identical on the disc and in every community roster; the
  AHL and WHL tables differ in the community roster (2015-16 AHL, a WHL cut to 454 rows, not sorted).
  The year the calendar shows ("October 2015") is in no table; October-February 2015/16 and 2026/27 have
  the same weekdays (March-April: a day off if the game's February has 29 days).
- **The 2026-27 calendar** (`schedule.py`, step `schedule`, off by default, `cli calendar-test`): NHL.com's
  `club-schedule-season/<ABBR>/20262027` gives 1,344 regular-season games (84 per team), 29 Sep 2026 to 10 Apr
  2027, stored in the data pack part `schedule`. They do not fit (1,291 rows): the update writes only games
  between slots 0-29 (1,180; 76-80 per team) or, as a test, all 32 teams trimmed to 80 each (a flow over
  home/away pairs, `schedule.trim`). Written into `nhlschedule` and `favoriteteamschedule`; `verify.py` /
  `schedule.check` insist on the game's rules (rows in date order, valid dates Sep-Jun, nobody twice a day,
  `index` = row, both tables equal, no other schedule table changed). Not played in the game yet.
- **Room.** The maximum is the stock count + 60 (`maxinsert` in `nhlng-meta.xml`). That is 1,291 rows
  for the NHL. 32 teams × 82 games = 1,312 do not fit; 80 games (1,280) would.
- **Divisions.** These live in `ttOk.conferencegroup` / `divisiongroup` (6 bits):
  - NHL: conferences 1 West, 2 East; divisions 3 Pacific, 4 Central, 5 Atlantic, 6 Metropolitan;
  - slots 30/31: 2/2 and 1/1 (the conferences' own groups). A roster for the 32-team patch files them in the Pacific (1/3)
    and Utah (slot 22) in the Central (1/4): `gamepatch.divisions_fit`, checked by `verify(farm_patch=True)`.
- **Be a GM / season tables** (`league…`, `dynasty`) are not in the roster save. The game builds them
  when a mode starts; `leaguegmdata` has 30 rows. It takes their row counts from `db/nhlng-meta.xml` (`maxinsert`) and
  their field bits from the empty template tables in `db/nhlng.db`; a loose copy of either in the game folder wins over the
  disc's (the game patch writes both: 32 rows, 6-bit team fields).
- **The All-Star game in the calendar.** The game's calendar loader (30 teams) reads a row whose home team is 30 or more as
  the All-Star game and plays it between the two All-Star teams (slots 30 / 31, made by the Season). The game's own row is
  31 Jan, 30 v 31. With the 32-team game patch 30 / 31 are Seattle and Vegas, so that rule is off (stage E); stage J
  makes a row of a team against itself the All-Star game, between EASHL 1 / 2 (slots 220 / 221, named Eastern / Western
  All-Stars). The patched roster has exactly one such row, on `schedule.all_star_date` in the break (`schedule.ALL_PATCH`,
  `gamepatch.check_all_star`). No calendar of the game's own has a row with home == away.
- **A roster for the game patch** (`gamepatch.py`) differs from a normal one: birth years as year - 1911 (not - 1910: the
  league's own clock, which the patch leaves at 2015 = 2026), pick years 11 later (`year_shift`); `ahlschedule` holds the AHL's 2026-27 calendar by farm place (slot - 32 for
  slots 32-61, Coachella Valley 234 = 30, Henderson 235 = 31; `farm_fit`, `FARM_PLACE`); the AHL clubs in their 2026-27
  divisions (`FARM_DIVISIONS`); every NHL slot's `ahlaffiliate` names its own club in slots 32-61, Seattle / Vegas none (the
  patch gives them 234 / 235: `ttOk.ahlaffiliate` has 6 bits); Seattle / Vegas in the Pacific, Utah in the Central (`divisions_fit`). `verify(farm_patch=True)` checks it. It plays right only with the
  patch on, and the patch only with such a roster.
- **Later seasons' calendars** (Season / Be a GM, season 2 on) are not stored anywhere: the game makes them from the loaded
  roster's `nhlfutureschedule` (`byED`) and `ahlschedule`, rotating each division's teams by one place a year and shifting
  the weekdays (`0x283800`; docs/notes/autoplay.md, run 16). The game's own `byED` names 30 teams, so in season 2 two NHL
  clubs had no games. A roster for the game patch holds the 2026-27 calendar of 32 in `byED` too (`gamepatch.future_fit`,
  `check_future`), and stage R widens the game's map to 32 teams.
- **The club leagues' tables** (lab round 46, docs/notes/league-calendars.md): Season mode's League Type offers all ten
  leagues with a table (NHL, AHL, SHL, Liiga, DEL, Extraliga, National League, OHL, QMJHL, WHL; not Norway) and plays
  the roster's own table (a swapped DEL row showed in a new DEL season). A team id is the club's place in its league:
  slot - the league's first slot (`schedule.LEAGUES`: AHL `AJKN` 32-61, SHL `LmeT` 62-75, Liiga `RBQQ` 76-90, DEL
  `Njxh` 91-104, Extraliga `RzQW` 105-118, National League `inlv` 119-130, OHL `uiEj` 154-173, QMJHL `ySfc` 174-191,
  WHL `kTZD` 192-213). Room = stock rows + 60. The update writes the real 2026-27 games between clubs with a slot
  (`schedule.apply_league`, checked by `check_league`); Be a GM is NHL only, Be a Pro starts in the NHL or the CHL.

docs/SEASON_PLAN.md uses these facts.

## 9. Debugging with the RPCS3 log

RPCS3 keeps `log\RPCS3.log` open; read it with shared access. Useful searches:
`ShowSaveDataList` (which roster was loaded), `Access violation` (crashes),
`sys_fs_open(path=` (which screens and art files were opened).

## 10. Looks: rasters of the 3D files (read 2026-10-11, EU disc)

- `rendering/jersey/texlib_<style>_<art>_<v>.rpsgl`: `jersey_.._cm` (DXT1), `jersey_.._sm` (shine, DXT1, carries the crest), `jersey_.._0_nm`
  (relief, DXT5), `font_.._cm/nm/sm` (numbers). `rendering/jersey/name_<style>_<art>_<v>_cm.rpsgl` is a small name plate (not touched).
- `rendering/logo/texlib_<art>_<style>_<v>.rpsgl`: `logo_.._0` 256x128 DXT5, the logo on helmet and shoulder; `_1` (128x64) and `_2`
  (128x128) are empty for Utah.
- `rendering/enviro/helmet_<art>.rpsgl`: a cube map (6 DXT5 faces of 256x256 with 9 mipmaps, 87424 bytes each from byte 512): the
  arena as the helmet reflects it. `Rpsgl` reads it as "not DXT1 or DXT5" (one raster of 524544 bytes).
- `rendering/icesurface/`: `centerlogo_<art>_cm` 1024x1024, `icesurface_<art>_bm` 512x512 (rink from above, the logo baked in),
  `ice_cline_`, `ice_hotspot_`. Arena art 30 / 31 (All-Star) have no `_bm`, no crowd, no `helmet_` and no environment movie.
- `stockteamequipmenttable` (`vbHh`): rows per team, equipment 1-8, variant, brand, era; 9 colour zones (`zone<n>_r/g/b`).
  **`team` is the slot + 1** (found 2026-10-18): team 22 is slot 21, Philadelphia, so the orange (218,57,28) / (207,61,28)
  in zone 3 of its equipment 1-4 is Philadelphia's, not Arizona's. `stockgoalieequipment` (`nAUy`, blocker / pads / trapper
  zones) and `customteamequipmenttable` (`NDEo`) count the same way; `sozv` (throwbacks) is keyed by the slot itself. Until
  0.21.0 `Builder.nhl_gear` took `team` for the slot: it painted Philadelphia, Washington and Seattle and left Utah and Vegas
  as they were (`GEAR_SLIPS`, docs/notes/equipment.md). Equipment 8 is taken for the helmet (zone 1 shell, 2 / 3 trim) and 5
  for the gloves; not proven in the game yet.
- **Sticks** (`ajmx.stick`): the colours are baked into `rendering/playerstick/texlib_<id>.rpsgl` (`playerstick_<id>_cm`,
  1024x128 DXT1, no tint mask), so a stick in team colours means another model (`sticks.py`, `tools/stick_colours.py`).

### Custom teams (slots 222-251): the Create a Team look (lab round 37, 2026-10-20)

The game draws every custom slot like a team made in Create a Team, whatever its art id (round 34). `custom_kit.py`.

- **Design fields** (`ttOk`): `jerseybackhome` (spwD, 5 bits) / `jerseybackaway` (tjNg) 0-8 (9 falls back to 0; the
  community has one 9), `pantsstyle` (ztft, 3 bits) / `sockstyle` (wzfn) / `font` (sgrR) 0-5. `jerseystyle` (ucaK, 1
  bit) is not the design but whether the game draws it: 0 (every custom slot of the game's own roster) gives a plain
  jersey in the game, without the design or its colours (white in lab round 46, black in the owner's newer RPCS3), while
  Select Jerseys still shows the design; 1 (the community's teams) draws it. `custom_kit.write` and `clubs.own_kit`
  write 1 (`layout.OWN_DESIGN`). The design follows the side a team plays on (Select Jerseys' Home / Away switch changes
  only the label).
- Jersey value to `rendering/czjersey/jerseyct_<cut>_<n>`: 0 `0_0`, 1 `0_1`, 2 `1_0`, 3 `1_1`, 4 `2_0`, 5 `4_0`, 6 `4_1`,
  7 `5_0`, 8 `5_1`. Pants `czpant/pantct_<n>`, socks `czsock/texlib_<n>`, font `czfont/czfont_<n>`. Crest
  `czlogo/logoct_<logo>_*`, `artid` = 20001 + logo (0-86, 54 has no files); its bump / shine files follow the jersey cut.
- Menu pictures (cache.big, 256x128 RGBA): `fe/ion/artassets/createteam/{jersey,pants,socks,font}/<kind><n>.big` and
  `logo/logo<artid>.big` (20001-20086 without 20055).
- **Colours** (`customteamequipmenttable`, `NDEo`, team = slot + 1, variant 1 home / 2 away, zones 1-9 RGB, `brand` 0):

| Piece | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| What | goalie catching glove | goalie blocker | goalie pads | goalie stick | gloves | socks | pants | helmet | jersey | name and numbers | crest |
| Zones used | 9 | 9 | 9 | 3 | 9 | 3 | 3 | 3 | 6 | 3 | 6 |

  Jersey zones: 1 body, 2 / 3 stripes and side panels, 4 collar, 5 shoulders, 6 trim. The crest picture's weights
  (`0_tm`) are made against piece 11's colours. `cTuP` (customteamjerseys) is left alone.

