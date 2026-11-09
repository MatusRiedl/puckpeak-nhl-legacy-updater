"""The game patch for RPCS3 (docs/notes/patch-design.md): the game's dates in 2026 instead of 2015, and later 32 teams in
Season, Be a GM and Be a Pro. RPCS3 applies it while the game runs; the game's own files are never changed.

Only the year entry exists so far (`cli year-test`, the in-game check). Version 0.1 showed 13 October 2026 in the lab
and crashed creating a Season; 0.2 wrote `code_alloc`, a name RPCS3 does not know (the same crash). Version 0.3 (the year
window, YEAR_CAVE, `calloc`) PASSED in the lab (2026-10-12): the game shows 2026, Crosby is 39, Season and Be a GM start,
Anaheim has its real games.

The patch moves the game's dates by 11 years: the calendar, the season's start, the day ages are counted on. The
league's own year stays 2015 (YEAR_LABELS), and the game counts ages from it too, so the date-based age takes the birth
year 11 later and the roster keeps birth years on the league's clock: the real year - 1911, where this program's
normal update stores year - 1910 (docs/FORMAT.md). `year_shift` turns a roster into the patched way; the normal update
does not do it.
"""
import datetime
import re
import struct

from . import layout as L
from . import schedule
from .donors import real_birth_year

EU_HASH = 'c93019e83e820ad7ce6ac2428d022e7c09d484d3'     # PPU hash of NHL Legacy EU (BLES02153 01.00)
# The NA program (BLUS31540 01.00) has the same code: same length, 3,506 data bytes differ (online ids, keys), all past
# every word the patch touches (audit_patch: 0 problems on the NA ELF; docs/notes/na-version.md). Same entries, own hash.
NA_HASH = 'cf2651406b00ee9c2af61fc1daf37fce50303474'
HASHES = {'BLES02153': EU_HASH, 'BLUS31540': NA_HASH}
# Update 1.01 (on the PlayStation Store for both versions; a tester's NA game had it, 2026-10-23): RPCS3 runs the update's
# program dev_hdd0/game/<TITLEID>/USRDIR/EBOOT.BIN instead of the disc's, one program for EU and NA under its own hash, so
# entries under the 1.00 hashes never ran there and a patch roster "appears to be damaged". The patch is written a second
# time for it at 1.01's addresses (port, patch101.py).
UPDATE_HASH = 'd4bbaf00a080a924e862c1b3f7705380a3499edb'
VERSIONS = ('01.00', '01.01')
YEARS_LATER = 11                                         # 2015 -> 2026
YEAR_ENTRY = "NHL Legacy year 2026 (test)"
PATCH_VERSION = '0.9'                                    # 0.9: the Calendar screen's Home / Away marks
TEAMS_VERSION = '0.27'                                   # 0.27: stage Z (Be a CHL Pro); 0.23: the roster's player rights in six bits, Vegas's too (lab round 42);
#                                                          0.24: the same words, the news entry (NEWS_ENTRY) ticked with them;
#                                                          0.25: the same words, also for update 1.01;
#                                                          0.26: the year entry 0.9 (the Calendar screen's marks)
INTRO_VERSION = '0.1'                                    # the intro entries (INTRO_ENTRIES)

# FUN_00731ce8(out, year, month, day) turns a date into a day number; 0x731d04 copies the year (ori r29,r4,0). The patch
# sends that one instruction to a few of its own (RPCS3 `calloc`): the year moves 11 later only when it is one of the
# game's own years, 2010-2025. A year that is 2026 or later already (a date the game split from a day number and joins
# again) stays, so dates do not drift by 11 more on every round trip. Version 0.1 added 11 to every year: the game
# crashed creating a Season (lab, 2026-10-12: event lookup 0x183010 found nothing, called from 0x273d20).
YEAR_HOOK = (0x731d04, 0x609d0000)                      # address, the game's word there
YEAR_WINDOW = (2010, 16)                                # years 2010 .. 2025 move
# The game's own instruction comes last: if an RPCS3 does not know `calloc`, it skips that line and writes the other
# lines one after another at the hook itself, so the last one stays there and the game runs as it was.
YEAR_CAVE = (
    (0x3804f826, "addi r0,r4,-2010"),
    (0x28000010, "cmplwi r0,16      a year of 2010-2025?"),
    (0x3ba4000b, "addi r29,r4,11    r29 = the year 11 later"),
    (0x41800008, "blt +8            yes: keep that"),
    (0x609d0000, "ori r29,r4,0      no: the game's own instruction, r29 = the year"),
)
# The league keeps its own year (leaguestates type 13: 2015, +1 every season; read through 0x22b6e8, 2015 when missing;
# LeagueManager +0xc, set by 0x33a5a8, read in about 100 places), and the game reckons with it (year - 2015 = the
# season's number, the calendar's turn, the draft years, the Season's own picks 2015-2020), so it stays. Only what the
# menus show of it moves: Be a GM / Season showed "2016-2017 Season" in season 2 (lab run 17).
# Ages: the computer GMs' roster work counts a player's age from the league year (at Be a GM's first new year, 0.4 with
# real birth years: 389 of 640 NHL players counted 19 or younger, McDavid / Kyrou / Thomas went back to junior,
# Kaprizov / Nugent-Hopkins / Ekholm to the farm; lab round 23 against the patch-off round 24). So the roster keeps birth
# years on the league's clock (year_shift: the real year - 11), and the date-based ages take the birth year + 11:
# 0x1631e4 (the date's year, 2026 with the patch, minus the birth year; contracts, the draft) and 0x372008 (the same as a
# fraction, the player object's birth year at +0x5e; Select Team's "Average Age" showed 40.5 for Seattle without it, lab
# round 25).
# Job list (0.7): a new career's first day runs a list of jobs made with room for 8 (0x33a470): one, the new season's
# roster job, then 5 leagues, then 2 more (0x29bcc4, 0x29b800); the roster job is made only when the league's first date
# is not in 2015, so with the patch there are 9 and the 9th lies over the next heap block. Mostly unseen; a Be a Pro with
# Seattle's Catton ran the list into a broken job (lab round 28: executing 0x20e5d70 at 0x33a554, jobs 0-7 done).
YEAR_LABELS = (
    (0x40cb7c, 0x60660000, 0x38c3000b,
     "GetCurrentSeasonYearRangeForLeague (entry 0x7c of 0x1cd7e88) prints \"%d-%d\": the league year + 11 (and + 12)"),
    (0x2e2b98, 0x306307df, 0x306307df + YEARS_LATER,
     "GetSeasonYear (entry 0x50 of 0x1cd40b8): 2015 + the season's month count -> 2026 + it"),
    (0x16320c, 0x60790000, 0x3b230000 | YEARS_LATER,
     "age (0x1631e4) of a birth year at a date: the birth year + 11 (addi r25,r3,11; was ori r25,r3,0), as the league "
     "year counts it"),
    (0x3721a4, 0x78630020, 0x38630000 | (-YEARS_LATER & 0xffff),
     "age as a fraction (0x372008, the player pages and the teams' average age): today's year - the birth year - 11 "
     "(addi r3,r3,-11; was clrldi r3,r3,32 on a difference that is never negative)"),
    (0x33a4d0, 0x38800008, 0x38800010,
     "the job list of a new Season / Be a GM / Be a Pro (0x33a470) has room for 8; in a year other than 2015 the new "
     "season's roster job (0x29bcc4 -> 0x22d1b8) is the 9th, written past the list: room for 16"),
    (0x402d24, 0x60770000, 0x3ae30000 | YEARS_LATER,
     "GetSalaryCapYearStrings (entry 0xc8 of 0x1cd7c30) prints each contract season as \"%d-%d\" and \"%s-%s\" (Be a GM's "
     "Contract Status \"15-16\"): the league year + 11 (addi r23,r3,11; was ori r23,r3,0)"),
    # The Calendar screen asks for each day's game with the year it shows (2026 with the patch) and GetTeamMatchIDByDate
    # gives none for a year after the league year + 1: no Home / Away marks in Season / Be a GM (docs/notes/2026-27-gaps.md).
    (0x407954, 0x30630001, 0x3063000c,
     "GetTeamMatchIDByDate (entry 0xc of 0x1cd7e88, the Calendar screen's Home / Away marks): no game in a year after "
     "the league year + 1; the screen's year is 11 later, so the league year + 12 (addic r3,r3,12; was addic r3,r3,1)"),
    (0x407960, 0x809c0000, 0x3063ffff,
     "GetTeamMatchIDByDate: every day up to the league year + 11 counts (addic r3,r3,-1 on the + 12; was the second call "
     "for the league year, lwz r4,0(r28))"),
    (0x407964, 0x63830000, 0x48000014,
     "GetTeamMatchIDByDate: on to its compare at 0x407978 (b +0x14; was ori r3,r28,0)"),
)


# --- 32 teams (docs/notes/patch-design.md; built in stages, each its own RPCS3 entry, NOT played yet) -------------------
# A change is (address, the game's word, our word, why). Our word is the game's word with one field changed (`_imm`), so
# tools/audit_patch.py can check the game's word against the EBOOT and show both. A cave is (address, the game's word,
# [(word, what)], why): RPCS3 runs our words in place of that one instruction, then goes on after it.
NOP = 0x60000000


def _imm(word, value):
    """The game's instruction `word` with a new 16-bit immediate or displacement."""
    return (word & 0xffff0000) | (value & 0xffff)


def _li(rt, value):
    return 0x38000000 | rt << 21 | value & 0xffff


def _stw(rs, disp, ra):
    return 0x90000000 | rs << 21 | ra << 16 | disp & 0xffff


def _addis(rt, ra, value):
    return 0x3c000000 | rt << 21 | ra << 16 | value & 0xffff


def _addic(rt, ra, value):
    return 0x30000000 | rt << 21 | ra << 16 | value & 0xffff


# Stage A, Be a GM's two per-team objects (keys 30 and 31 would write past their tables of 30) and one stack table.
# SalaryCapManager (*0x2201f1c, made at 0x3c5eec): 30 money records of 0x14c, 30 "loaded" flags at +0x26e8, a word at
# +0x2708, 0x270c bytes. With 32: records to 0x2980, flags +0x2980, the word +0x29a0, 0x29a4 bytes.
SCM_FLAGS = (0x3a7f30, 0x3a7f90, 0x3a8014, 0x3a8a74, 0x3a8be8, 0x3aa9c8, 0x3aaf2c, 0x3c5ed0, 0x3c5f78, 0x3c68a0, 0x3c6ad4,
             0x3c6bac, 0x3c6d2c, 0x3c6ee0, 0x3c6fac, 0x3c7158, 0x3c722c, 0x3c72b8, 0x3c7380, 0x3c7980, 0x3c7a04, 0x3c7a90,
             0x3c7b18, 0x3c7cec, 0x3c7d9c, 0x3c7e5c, 0x3c85c4, 0x3c98ac, 0x3c9a80, 0x3c9bcc, 0x3c9cc8)
SCM_WORD = (0x3c5f70, 0x3c6584, 0x3c65c4, 0x3c65e4, 0x3c6664, 0x3c66bc, 0x3c682c, 0x3c68b8, 0x3c6abc, 0x3c6b34, 0x3c6ec8,
            0x3c6f18, 0x3c9cb0, 0x3c9cfc)
# the game's words at those addresses (lbz / stb / lwz / stw with the displacement 0x26e8 or 0x2708)
_SCM_OLD = dict(zip(SCM_FLAGS, (
    0x98a426e8, 0x886326e8, 0x886326e8, 0x886326e8, 0x886326e8, 0x886326e8, 0x886326e8, 0x988326e8, 0x9bc426e8, 0x886326e8,
    0x886326e8, 0x886326e8, 0x886326e8, 0x886326e8, 0x886326e8, 0x886426e8, 0x886326e8, 0x886326e8, 0x886326e8, 0x886326e8,
    0x886426e8, 0x886326e8, 0x886326e8, 0x886426e8, 0x886426e8, 0x886426e8, 0x886426e8, 0x886426e8, 0x886426e8, 0x886426e8,
    0x886326e8)))
_SCM_OLD.update(zip(SCM_WORD, (
    0x93df2708, 0x93df2708, 0x807f2708, 0x807f2708, 0x807d2708, 0x807d2708, 0x809a2708, 0x809a2708, 0x807f2708, 0x807f2708,
    0x807e2708, 0x807e2708, 0x807e2708, 0x807e2708)))

STAGE_A = (
    [(0x285cf8, 0x93030080, NOP, "season set-up: a stack table of 30 written and never read; 30/31 would hit the next one")]
    + [(0x31b958, 0x38603e4c, _imm(0x38603e4c, 0x3e6c), "GmLogic: 0x20 bytes more for 32 flags at the end"),
       (0x31b8f4, 0x3860001e, _imm(0x3860001e, 32), "GmLogic constructor: clear 32 flags"),
       (0x31b900, 0x9be43dc9, _imm(0x9be43dc9, 0x3e4c), "GmLogic constructor: the flags at the new end"),
       (0x31f2b4, 0x98833dc9, _imm(0x98833dc9, 0x3e4c), "GmLogic: set a team's flag"),
       (0x31f2c4, 0x88633dc9, _imm(0x88633dc9, 0x3e4c), "GmLogic: read a team's flag"),
       (0x31f2cc, 0x38a0001e, _imm(0x38a0001e, 32), "GmLogic: clear 32 flags"),
       (0x31f2d8, 0x98833dc9, _imm(0x98833dc9, 0x3e4c), "GmLogic: clear, the flags at the new end")]
    + [(0x3c5f1c, 0x3860270c, _imm(0x3860270c, 0x29a4), "SalaryCapManager: 32 records, the flags and the word after them"),
       (0x3c5f60, 0x2c1c001e, _imm(0x2c1c001e, 32), "SalaryCapManager: build 32 records"),
       (0x3c5f68, 0x3860001e, _imm(0x3860001e, 32), "SalaryCapManager constructor: clear 32 flags"),
       (0x3c5ec4, 0x38a0001e, _imm(0x38a0001e, 32), "SalaryCapManager: clear 32 flags")]
    + [(a, _SCM_OLD[a], _imm(_SCM_OLD[a], 0x2980), "SalaryCapManager: a team's flag at the new place") for a in SCM_FLAGS]
    + [(a, _SCM_OLD[a], _imm(_SCM_OLD[a], 0x29a0), "SalaryCapManager: the word after the flags at the new place")
       for a in SCM_WORD])
STAGE_A_CAVES = ()

# Stage "NHL list": the Season's NHL competition is written in code (0x22fe30: slots 0-29 and four divisions); a team's key
# is its place in the lists, so this makes Seattle (slot 30) and Vegas (31) keys 30 and 31 and moves the AHL to keys 32-61.
# 2026-27 divisions: Utah (slot 22) to the Central, Seattle and Vegas to the Pacific: 8 teams in each. Only with stage C.
STAGE_NHL = (
    (0x22fee0, 0x2c19001d, _imm(0x2c19001d, 31), "the NHL list: slots 0-31"),
    (0x22fee8, 0x38600016, _imm(0x38600016, 30), "Pacific: Seattle (30) in Utah's (22) place"),
)
STAGE_NHL_CAVES = (
    (0x22ff28, 0x38800007, [(_li(4, 31), "li r4,31          Vegas"),
                            (_stw(4, 0x8c, 1), "stw r4,0x8c(r1)   the Pacific's 8th team"),
                            (_li(4, 8), "li r4,8           8 teams")], "Pacific: 8 teams with Vegas"),
    (0x22ff78, 0x38800007, [(_li(4, 22), "li r4,22          Utah"),
                            (_stw(4, 0x8c, 1), "stw r4,0x8c(r1)   the Central's 8th team"),
                            (_li(4, 8), "li r4,8           8 teams")], "Central: 8 teams with Utah"),
)

# Stage B, the League object (0x5704 bytes, constructor 0x270c50; one per competition, one inside the LeagueManager at +0x80)
# holds three lists of 30: A (+0x208, by NHL key: a team's farm key), B (+0x284, the competition's teams) and C (+0x304, by
# farm place: the farm clubs' roster info, filled by 0x27c4b0). All three move to the object's new end with room for 32
# (A +0x5704, B +0x5784, C +0x5804; 0x180 bytes more). The League's fields after C (+0x37c..+0x390) stay.
LEAGUE_SIZE = 0x5704 + 3 * 0x80
STAGE_B = (
    (0x28041c, 0x38605784, _imm(0x38605784, 0x80 + LEAGUE_SIZE), "LeagueManager: 0x180 bytes more (its own League grows)"),
    (0x287f3c, 0x38605704, _imm(0x38605704, LEAGUE_SIZE), "a League: 0x180 bytes more for lists A, B and C of 32 at the end"),
    (0x2899b8, 0x38605704, _imm(0x38605704, LEAGUE_SIZE), "a League: 0x180 bytes more (second place it is made)"),
    (0x270da0, 0x307d0208, _imm(0x307d0208, 0x5704), "League constructor: clear list A at its new place"),
    (0x270dac, 0x38a00078, _imm(0x38a00078, 0x80), "League constructor: list A holds 32"),
    (0x270db4, 0x307d0284, _imm(0x307d0284, 0x5784), "League constructor: clear list B at its new place"),
    (0x270dbc, 0x38a00078, _imm(0x38a00078, 0x80), "League constructor: list B holds 32"),
    (0x270dc4, 0x307d0304, _imm(0x307d0304, 0x5804), "League constructor: clear list C at its new place"),
    (0x270dcc, 0x38a00078, _imm(0x38a00078, 0x80), "League constructor: list C holds 32"),
    (0x2710e4, 0x80630304, _imm(0x80630304, 0x5804), "list C (a farm club's roster info) at its new place"),
    (0x27c590, 0x935c0304, _imm(0x935c0304, 0x5804), "list C: fill it at its new place"),
    (0x27cfa4, 0x327a0304, _imm(0x327a0304, 0x5804), "list C at its new place (Season set-up)"),
    (0x27f34c, 0x30740304, _imm(0x30740304, 0x5804), "list C at its new place"),
    (0x27c598, 0x2c19001e, _imm(0x2c19001e, 0x20), "list C: 32 farm clubs"),
) + tuple((a, old, _imm(old, 0x5704), "list A (a team's farm key) at its new place") for a, old in (
    (0x271b98, 0x33bf0208), (0x279ee8, 0x80a30208), (0x279f64, 0x80c30208), (0x279f84, 0x807d0208),
    (0x27a410, 0x80850208), (0x27b9e4, 0x90830208), (0x27b9f4, 0x331d0208), (0x27baf4, 0x90830208),
    (0x27bb08, 0x90830208), (0x27bcc8, 0x32570208), (0x27ca50, 0x80c30208), (0x27cc20, 0x80640208),
    (0x27d0a4, 0x83c30208), (0x27d2c0, 0x83e30208), (0x27d43c, 0x83c30208), (0x27f1b4, 0x80840208),
    (0x27f3f0, 0x81c30208), (0x285628, 0x81630208), (0x286f20, 0x325b0208))
) + tuple((a, old, _imm(old, 0x5784), "list B (the competition's teams) at its new place") for a, old in (
    (0x27bc40, 0x33170284), (0x27bfac, 0x80630284), (0x27c768, 0x33b70284))
) + tuple((a, old, _imm(old, 0x20), why) for a, old, why in (
    (0x271bc8, 0x2c1b001e, "list A for 32 teams"),
    (0x279fac, 0x2c1c001e, "list A, look through 32 teams"),
    (0x27a400, 0x3860001e, "list A, count over 32 teams"),
    (0x27b988, 0x2c1c001e, "the NHL competition, 32 places"),
    (0x27b9e0, 0x2c18001e, "list A for 32 teams"),
    (0x27ba80, 0x2c17001e, "list A for 32 teams"),
    (0x27bc7c, 0x2c1a001e, "list B for 32 teams"),
    (0x27bfc8, 0x2c1b001e, "list B, find among 32"),
    (0x27c7b4, 0x2c1e001e, "list B for 32 teams"),
    (0x286f50, 0x2c1a001e, "list A for 32 teams"),
    (0x27bc60, 0x2804001e, "list B, slots 30 and 31 are NHL teams too (the switch is for numbers above the NHL)"),
    (0x27c79c, 0x2804001e, "list B, slots 30 and 31 are NHL teams too (the switch is for numbers above the NHL)")))
STAGE_B_CAVES = ()

# Stage C, the keys. The Season numbers its teams ("keys") in the order it adds them (0x12d84c): the NHL's, then the farm
# league's, then the two All-Star teams. With 32 + 32 that is NHL 0-31, farm 32-63, All-Stars 64 / 65 (design I-66,
# docs/notes/keys64.md). A farm key - 32 is the club's farm place (list C, the farm calendar).
STAGE_C = tuple((a, old, _imm(old, new), why) for a, old, new, why in (
    (0x1639b4, 0x2c84001e, 0x20, "is NHL team - keys 0-31"),
    (0x27d68c, 0x3bc0001e, 0x20, "the farm league's first key is 32"),
    (0x27cc24, 0x3063ffe2, -0x20, "farm key to farm place"),
    (0x27cfa8, 0x328effe2, -0x20, "farm key to farm place"),
    (0x27d2c8, 0x309fffe2, -0x20, "farm key to farm place"),
    (0x27d444, 0x307dffe2, -0x20, "farm key to farm place"),
    (0x27f3f4, 0x306effe2, -0x20, "farm key to farm place"),
    (0x285630, 0x308bffe2, -0x20, "farm key to farm place"),
    (0x2710b4, 0x30bf001e, 0x20, "farm place to farm key"),
    (0x27fa10, 0x309f001e, 0x20, "farm place to farm key"),
    (0x27fc04, 0x2c1f001e, 0x20, "the Season's 32 farm teams"),
    (0x27f994, 0x2c16001e, 0x20, "season set-up, the 32 NHL teams' farm teams"),
    (0x27feb8, 0x2c1d001e, 0x20, "season set-up, the 32 NHL teams' records"),
    (0x2889f8, 0x3a80001e, 0x20, "season set-up, 32 NHL team records"),
    (0x288a1c, 0x3860232c, 4 + 32 * 300, "season set-up, room for 32 records of 300 bytes"),
    (0x288a64, 0x2c1e001e, 0x20, "season set-up, build 32 records"),
    (0x288a84, 0x38a0001e, 0x20, "season set-up, 32 records"),
    (0x288d18, 0x38a0001e, 0x20, "season set-up, 32 records"),
    (0x288da8, 0x38a0001e, 0x20, "season set-up, 32 records")))
STAGE_C_CAVES = ()

# Stage L, the farm league of 32 (the farm list 0x22fb2c). The game lists AHL slots 32-61 (`li r27,32` .. `cmpwi r27,61`,
# `bl 0x130920` adds one), files them in four divisions (each from a stack array of at most 8, handed to 0x1243a4, which
# keeps its own copy of `count` words) and two conferences, and maps each slot to its farm place, slot - 32 (0x1242d8
# writes the place over the slot in the divisions). With 32 the loops run to 63 and the slot of number 62 / 63 is Coachella
# Valley (234) / Henderson (235), custom slots of the roster (their league stays; only this list takes them in): farm
# places 0-29 = slot - 32, 30 and 31 = Coachella and Henderson. Each division's copy is written again right after the
# game made it, with the 2026-27 AHL clubs (docs/notes/ahl-2026.md; the Pacific has 10). The game's division and
# conference numbers stay: 12 Central and 13 Pacific in conference 8 (West), 10 Atlantic and 11 North in 9 (East), the
# groups the roster's AHL clubs carry (farm_fit files them there too).
FARM_SLOTS = tuple(range(32, 62)) + (234, 235)          # the Season's farm league: keys 32-63 in this order
FARM_PLACE = {slot: place for place, slot in enumerate(FARM_SLOTS)}
FARM_DIVISIONS = (   # (division, conference, name, slots), in the order the game builds them
    (12, 8, 'Central', (52, 38, 41, 44, 45, 50, 58)),
    (13, 8, 'Pacific', (60, 33, 56, 234, 37, 235, 46, 53, 54, 55)),
    (10, 9, 'Atlantic', (36, 39, 40, 43, 48, 47, 61)),
    (11, 9, 'North', (34, 42, 35, 51, 49, 57, 59, 32)),
)
# per division: (the count `li r4,n`, the instruction after its 0x1243a4 call, the division's list pointer on the stack)
_FARM_FILLS = ((0x22fc28, 0x38800008, 0x22fc38, 0x38600021, 0x98), (0x22fc84, 0x38800007, 0x22fc94, 0x38c00008, 0xb4),
               (0x22fcfc, 0x38800008, 0x22fd0c, 0x38600020, 0x98), (0x22fd54, 0x38800007, 0x22fd64, 0x38c00009, 0xb4))


def _cmpwi(ra, value):
    return 0x2c000000 | ra << 16 | value & 0xffff


def _addi(rt, ra, value):
    return 0x38000000 | rt << 21 | ra << 16 | value & 0xffff


def _lwz(rt, disp, ra):
    return 0x80000000 | rt << 21 | ra << 16 | disp & 0xffff


def _ori(ra, rs):
    return 0x60000000 | rs << 21 | ra << 16


BLE_8, BGE_8 = 0x40810008, 0x40800008                   # skip the next instruction when <= / >= (cr0)


def _farm_slot(reg):
    """r4 = the slot of farm number `reg` (32-63): itself up to 61, then 234 and 235."""
    return [(_ori(4, reg), f"ori r4,r{reg},0       the game's own instruction: slot = number"),
            (_cmpwi(reg, 61), f"cmpwi r{reg},61"),
            (BLE_8, "ble +8            32-61: that is the slot"),
            (_addi(4, reg, 234 - 62), f"addi r4,r{reg},172   62 / 63: Coachella Valley 234 / Henderson 235")]


def _division_fill(disp, slots, own):
    code = [(_lwz(4, disp, 1), f"lwz r4,0x{disp:x}(r1)   the division's own list")]
    for k, slot in enumerate(slots):
        code += [(_li(3, slot), f"li r3,{slot}"), (_stw(3, 4 * k, 4), f"stw r3,{4 * k}(r4)")]
    return code + [(own, "the game's own instruction")]


STAGE_L = (
    (0x22fbcc, 0x2c1b003d, _imm(0x2c1b003d, 63), "farm list: numbers 32-63"),
    (0x22fdbc, 0x2c1c003d, _imm(0x2c1c003d, 63), "farm places 0-31"),
) + tuple((count_at, count_old, _imm(count_old, len(slots)), f"farm division {name}: {len(slots)} clubs")
          for (count_at, count_old, *_), (_, _, name, slots) in zip(_FARM_FILLS, FARM_DIVISIONS))
STAGE_L_CAVES = (
    (0x22fbb8, 0x63640000, _farm_slot(27), "farm list: Coachella Valley and Henderson after slots 32-61"),
    (0x22fda4, 0x63840000, _farm_slot(28), "farm places: Coachella Valley 30, Henderson 31"),
) + tuple((at, own, _division_fill(disp, slots, own), f"farm division {name}: the 2026-27 clubs")
          for (_, _, at, own, disp), (_, _, name, slots) in zip(_FARM_FILLS, FARM_DIVISIONS))

# Stage M, 64 league teams (docs/notes/keys64.md, every site with its verdict). The game counts 60 league teams (30 NHL +
# 30 farm) and calls a key of 60 or more an All-Star; with 32 + 32 that is 64. A farm key was the roster's affiliate slot
# (team info byte +0xbe) - 2; now the farm list's numbers are the slots, so it is the slot itself. Seattle and Vegas name no
# farm club in the roster (their affiliate is -1: six bits cannot hold 234 / 235, and Play Now reads the byte as a slot),
# so their farm key is their own key + 32: 62 Coachella Valley, 63 Henderson. 0x27d0b8 gives a farm club's players its
# own key from its slot.
STAGE_M = tuple((a, old, _imm(old, new), why) for a, old, new, why in (
    (0x128754, 0x2c05003c, 64, "team cache: league keys 0-63"),
    (0x279f20, 0x2c9e003c, 64, "a club's farm team: league keys below 64"),
    (0x21d75c, 0x2c1f003c, 64, "kind of game: a key of 64 or more is the All-Star game"),
    (0x221728, 0x2c03003c, 64, "season rows of league keys below 64"),
    (0x221794, 0x2c05003c, 64, "season rows of league keys below 64"),
    (0x23c130, 0x2c1d003c, 64, "slot to key: look through keys 0-63"),
    (0x460914, 0x3860003c, 64, "kind of team: farm keys below 64"),
    (0xec9fb0, 0x2c03003c, 64, "league keys 0-63"),
    (0xeca0c0, 0x2c03003c, 64, "league keys 0-63"),
    (0xeca3f8, 0x2c03003c, 64, "league keys 0-63"),
    (0xeca840, 0x2c03003c, 64, "league keys 0-63"),
    (0xf40194, 0x2c03003c, 64, "league keys 0-63"),
    (0x27bac4, 0x38800032, 52, "the fixed farm team Chicago Wolves: key 52 (its slot)")))
STAGE_M_CAVES = (
    (0x27b9d8, 0x3084fffe, [(_cmpwi(4, 0), "cmpwi r4,0        the club's farm slot (= its key now)"),
                            (BGE_8, "bge +8            named: keep it"),
                            (_addi(4, 24, 31), "addi r4,r24,31    none (Seattle, Vegas): its key + 32 (r24 is one on)")],
     "a club's farm key: its farm slot; Seattle and Vegas 62 / 63"),
    (0x27ba78, 0x3084fffe, [(_cmpwi(4, 0), "cmpwi r4,0        the club's farm slot (= its key now)"),
                            (BGE_8, "bge +8            named: keep it"),
                            (_addi(4, 23, 31), "addi r4,r23,31    none (Seattle, Vegas): its key + 32 (r23 is one on)")],
     "a club's farm key: its farm slot; Seattle and Vegas 62 / 63 (second way)"),
    (0x27d0b8, 0x30c6fffe, [(_cmpwi(6, 32), "cmpwi r6,32       the team's slot"),
                            (BGE_8, "bge +8"),
                            (0x30c6fffe, "addic r6,r6,-2    below 32: as the game did"),
                            (_cmpwi(6, 63), "cmpwi r6,63"),
                            (BLE_8, "ble +8            a farm slot 32-61 is its key"),
                            (_addi(6, 6, 62 - 234), "addi r6,r6,-172   234 / 235: keys 62 / 63")],
     "a farm club's players: its key from its slot"),
)
NO_FARM = (30, 31)                                      # Seattle, Vegas: no farm club in the roster, keys 62 / 63
FARM_TABLE, AFFILIATE = 'AJKN', 'TxsC'                  # ahlschedule; ttOk.ahlaffiliate (slot + 1, 0 = none)
FARM_ROW = {'index': 'qEfv', 'home': 'qkhY', 'away': 'rOMv', 'day': 'iwsK', 'month': 'pLKJ'}
# A computer GM replaces a hurt player by calling up one of his own: a player of his farm club who holds his rights
# (cPbu.proteam, NHL team + 1, 0 = nobody's). In Be a GM's season 2 (lab run 18, 2026-10-14) Seattle's farm club held 3
# forwards, 1 defenceman and 1 goalie of Seattle's (the lab roster had skipped the AHL step), three defencemen got hurt,
# Seattle dressed 16 and the game's line picker (0x1528f8) drew for ever. After a full update every other farm club holds
# at least 6 / 2 / 1 of its parent's. The game's proteam keeps -1..30 in five bits, and Vegas is 31 (stored as 32).
# Round 18 gave it six bits in the roster and in the db files and every new Be a GM crashed (0x381c24); that crash was the
# calendar's room (stage S: a clean five-bit roster crashed there too), not the rights. Round 42 (2026-10-22) gave the
# patch roster's proteam six bits again (rights_wide; the game reads the roster by the description in db/nhlng-meta.xml,
# whose proteam gets the same six bits: META_TEAMS): the roster loads, a new Be a GM with Vegas lists Henderson's players
# "In the System", a call-up / send-down swap works, the computer GMs trade for them, and the Season ran (lab round 42).
# Before, Vegas kept a farm club's depth on its own NHL roster (Builder.vegas_depth, 18 F / 8 D / 3 G) and Henderson was
# topped up with free agents. A roster for the unpatched game keeps five bits (unpatch_roster narrows it).
RIGHTS_TABLE, RIGHTS = 'cPbu', 'WBbd'                   # exhibitionplayerbiotable.proteam
RIGHTS_BITS = 6                                         # on a roster for the game patch: NHL slots 0-31 as 1-32
FARM_DEPTH = {'F': 6, 'D': 2, 'G': 1}                   # the fewest of its parent's players a farm club may hold
FUTURE_TABLE = 'byED'                                   # nhlfutureschedule: every later season's calendar (stage R)
# The real 2026-27 season has 84 games per team: 1,344 rows and the All-Star row (schedule.PATCH_ROWS). The game's database
# has 1,231 rows in nhlschedule and nhlfutureschedule, and the game gives a roster's copies a room of 1,291 of its own
# (stage S). With more rows in the roster a new Be a GM crashed as it loaded (lab round 18: 0x381c24,
# LeagueFreeAgentsReader, a free agent's player not found; 80 games passed, 82 and 84 crashed); with the patch's
# db/nhlng.db's own tables grown to PATCH_ROWS (fit_db) it started (round 19) but kept rows 0-1,290 only: every team lost
# the season's last week. Stage S gives the roster's tables the room, the roster's tables grow to it, and the roster's
# save section grows with them (SECTION_SIZE: the game takes a section of another length for a damaged save). The meta's
# `maxinsert` (META_ROWS) keeps the same room. The game's own buffers hold the season: the calendar loader's three of
# 1,350 rows (0x3de25c, 0x3de554, 0x3de72c), the season's 1,464 with the preseason (stage I: 1,345 + 112), the Season
# save's leaguescheduletable 4,000 (yvnq).
CALENDAR_STOCK = 1231
CALENDAR_ROOM = 1291                                    # the game's own room for a roster's calendar (stage S)
CALENDAR_ROW = 8                                        # bytes of a calendar row
CALENDAR_TABLES = (schedule.TABLE, FUTURE_TABLE)          # grown to schedule.PATCH_ROWS (favoriteteamschedule has 1,431)
# A new season's calendars come from the roster in the game's memory at the new year (lab round 27, 2026-10-15): stage R
# reads nhlfutureschedule and ahlschedule there; a Be a GM / Season save holds no copy. The game loads its own database
# (db/nhlng.db) at start and then the last roster it saved. When that roster is not the patch's (a "damaged" box
# cancelled, another roster, none) the game's own 30-team calendars stood in: lab run 11's season 2 gave Anaheim and
# Calgary one game each (the All-Star row), the other 30 NHL teams 82 and the AHL clubs 68-76. With the patch roster
# loaded (run E1) season 2 had 84 games for all 32 and 72 for all 32 AHL clubs. So the patch's db/nhlng.db carries the
# patch roster's two tables too (fit_db with the roster, check_db).
NEXT_SEASON_TABLES = {FUTURE_TABLE: "next seasons' NHL calendar (nhlfutureschedule)",
                      FARM_TABLE: "AHL calendar (ahlschedule)"}
SAVE_SECTION = 2456076                                  # a roster save's section in the game (stock.SAVE_SIZE - 0x2C)
SECTION_SIZE = SAVE_SECTION + len(CALENDAR_TABLES) * (schedule.PATCH_ROWS - CALENDAR_ROOM) * CALENDAR_ROW

# A roster for the patch also files the teams in their 2026-27 divisions (`ttOk.conferencegroup` / `divisiongroup`), as stage N
# does for the Season: the game's own roster keeps the All-Star teams (Seattle, Vegas) in groups 2 / 1, the conferences
# themselves, and Arizona (Utah) in the Pacific. Menus that read the roster's groups leave a team without a division out
# (probably "Pick favourite team": round 3 showed 30 NHL teams there).
CONFERENCE, DIVISION = 'uTwO', 'KMGC'
DIVISIONS = {3: 1, 4: 1, 5: 2, 6: 2}                   # division -> its conference: Pacific, Central (West), Atlantic, Metropolitan
TEAMS_2026 = {22: 4, 30: 3, 31: 3}                      # Utah: the Central; Seattle, Vegas: the Pacific
# ... and their names in the team table (fullname, shortname, abbrname; the art code `RPbr`, which the text file's keys use,
# stays). The roster still holds the game's: Be a Pro / Be a GM texts read the table, so a Seattle career said "GREEN / RED
# organization" (lab round 28, 2026-10-16). The menus' names come from the text file (art/loc.py, with the photos).
NAMES_2026 = {22: ('Utah Mammoth', 'Utah', 'UTA'), 30: ('Seattle Kraken', 'Seattle', 'SEA'),
              31: ('Vegas Golden Knights', 'Vegas', 'VGK')}

# Stage D, the Season's simulator (lab 2026-10-13: "simulate" crashed at 0xdf7fc with A, B, C and N on). Its one object
# (*0x21b5bd8, 0xfa54 bytes, made at 0xdca14, constructor 0xdc768) holds by team list A (+0x2b0, each team's working
# object) and list B (+0x328, a word) of 30, and a block (*(+8), 0x10d08 bytes): 30 team records of 0x14 bytes at 0, a byte
# per team at 0x258, fields at 0x276-0x281, a 64 KB table by player number from 0x282, more fields from 0x10281. Loops run
# to the team count (+0x29c, 32 now), so teams 31 and 32 wrote over list B and the fields after the records.
# With 32: list A grows in place; list B moves to the object's new end (+0xfa54, 0x80 bytes more: too far for one
# instruction, so three bits of own code); in the block the bytes move 0x28 up and the fields and the table 0x2c, the table
# ending where it did (0x2c bytes shorter: it is indexed by player numbers, never above 0x7fff). The function that runs a
# day (0xdf2f0) keeps the teams' numbers in a stack table of 30 (r1+0x94) just under a loop counter (r1+0x110): the
# counter moves to r1+0x78, which the function no longer uses by then.
SIM_SIZE, SIM_LIST_B = 0xfa54, 0xfa54                   # the object's size in the game; list B's new place = the old end
_SIM_BLOCK = (   # (the game's displacement, ours, what, [(address, the game's word)])
    (0x258, 0x280, "a team's byte", (
        (0xdcd84, 0x9bc30258), (0xdcddc, 0x88c50258), (0xdcde0, 0x88840258), (0xdcde4, 0x98850258),
        (0xdcdf4, 0x98c30258), (0xdce88, 0x99030258), (0xdcf58, 0x9bc50258), (0xe07f8, 0x88c40258),
        (0xe0800, 0x98c40258), (0xe0820, 0x88c60258), (0xe0d04, 0x9ae30258), (0xe0e10, 0x8b630258),
        (0xe0e2c, 0x9ae30258), (0xe0fc8, 0x9ae30258))),
    (0x276, 0x2a2, "a half-word after the bytes", (
        (0xdcb00, 0xb0830276), (0xdcefc, 0xb0a30276), (0xe0d38, 0xa0850276), (0xe0d4c, 0xb0650276),
        (0xe0d54, 0xa0830276))),
    (0x278, 0x2a4, "a word after the bytes", ((0xdcb08, 0x90830278), (0xdcef8, 0x80a30278), (0xe0d58, 0x80a30278))),
    (0x27c, 0x2a8, "the player's team", (
        (0xdcb10, 0x90a3027c), (0xddfc0, 0x93a3027c), (0xddfe0, 0x9064027c), (0xde058, 0x9083027c),
        (0xdec10, 0x8083027c), (0xe03a4, 0x8383027c))),
    (0x280, 0x2ac, "a flag after the bytes", (
        (0xdd0d0, 0x98a60280), (0xe0cd0, 0x88640280), (0xe0ce0, 0x9ae40280), (0xe0f98, 0x88640280),
        (0xe0fa4, 0x9ae40280))),
    (0x281, 0x2ad, "a flag after the bytes", (
        (0xdcf04, 0x98830281), (0xdff44, 0x98860281), (0xe0d78, 0x98830281), (0xe0d88, 0x88840281),
        (0xe0ef0, 0x88c60281))),
    (0x282, 0x2ae, "the table by player", (
        (0xd0230, 0x98830282), (0xd0544, 0x98640282), (0xd07d4, 0x98640282), (0xd2738, 0x30630282),
        (0xd27cc, 0x98a30282), (0xd27f8, 0x88630282), (0xdd02c, 0x30630282), (0xdeba0, 0x98640282),
        (0xe0b18, 0x88a60282), (0xe0b2c, 0x98a60282), (0xe0b3c, 0x98a60282))),
    (0xffff, 0xffd3, "the table's length", ((0xd2734, 0x60a5ffff), (0xdd028, 0x60a5ffff), (0xe0b08, 0x6084ffff))),
    (0x110, 0x78, "a day's run: its loop counter, out of the stack table's way", (
        (0xdf938, 0xfb210110), (0xdf948, 0xe8610110), (0xdfc18, 0xe8610110), (0xdfc24, 0xf8610110),
        (0xdfd24, 0xfa210110))),
)
STAGE_D = (
    (0xdca44, 0x6063fa54, _imm(0x6063fa54, SIM_SIZE + 0x80), "the simulator: 0x80 bytes more, list B of 32 at the end"),
    (0xdc8ec, 0x38a00078, _imm(0x38a00078, 0x80), "simulator constructor: clear list B of 32"),
    (0xdc9b8, 0x38a00078, _imm(0x38a00078, 0x80), "simulator constructor: clear list A of 32"),
    (0xdf438, 0x38a00078, _imm(0x38a00078, 0x80), "a day's run: clear list A of 32"),
    (0xdf54c, 0x38a00078, _imm(0x38a00078, 0x80), "a day's run: clear its stack table of 32 teams"),
) + tuple((a, old, _imm(old, new), f"simulator: {what}, now 0x{new:x}")
          for _, new, what, sites in _SIM_BLOCK for a, old in sites)
STAGE_D_CAVES = (   # list B at +0xfa54: 0x10000 - 0x5ac
    (0xdc8e4, 0x307f0328, [(_addis(3, 31, 1), "addis r3,r31,1    the simulator + 0x10000"),
                           (_addic(3, 3, SIM_LIST_B - 0x10000), "addic r3,r3,-0x5ac  list B's new place")],
     "simulator constructor: clear list B at its new place"),
    (0xe3650, 0x90a30328, [(_addis(3, 3, 1), "addis r3,r3,1     the simulator + 4 x team + 0x10000"),
                           (_imm(0x90a30328, SIM_LIST_B - 0x10000), "stw r5,-0x5ac(r3)  list B's new place")],
     "list B: set a team's word"),
    (0xe367c, 0x80a30328, [(_addis(3, 3, 1), "addis r3,r3,1     the simulator + 4 x team + 0x10000"),
                           (_imm(0x80a30328, SIM_LIST_B - 0x10000), "lwz r5,-0x5ac(r3)  list B's new place")],
     "list B: read a team's word"),
)

# Stage E, the calendar loader (lab 2026-10-13: Vegas's home games were missing and simulating a week hung). The loader
# (0x3de1dc, from `_GenerateLeagueSchedule` 0x28470c) takes its team count from 0x3ddc64 (30 for the NHL kinds) and reads
# every row whose home team is at or above it as the All-Star game: keys 60 / 61 (settings 0x37 / 0x38, slots 30 / 31 made
# All-Star teams by 0x27b780 when option 2 is 2), which hold no players. So all 80 Seattle and Vegas home games became
# "60 v 61" and the sim tried to play them. With 32 a row at home 30 / 31 is Seattle's or Vegas's game; the 32-team calendar
# has no All-Star row (the community roster's one, January 31, 30 v 31, is gone with it). The All-Star competition itself
# stays as the game makes it, empty and never played.
STAGE_E = tuple((a, old, _imm(old, new), why) for a, old, new, why in (
    (0x3ddc74, 0x38e0001e, 0x20, "calendar loader: 32 NHL teams (a home team at or above the count is the All-Star game)"),
))
STAGE_E_CAVES = ()

# Stage F, the favourite-team list (Settings, a new profile; lab round 6: still 30). Its screen asks for the NHL's teams with
# the filter FRANCHISE (14, 0x1f7204), which shows the first `count` teams of the NHL's list: count = the teams numbered below
# 30 (0x129aac, only this list asks it), and the list is in the order of 0x12709c, numbers below 30 first by name, then the
# rest. Round 0.4 changed filter 3 (DYNASTY, 0x1f6298) instead, which this screen does not use. The order also sorts the
# Season's and Be a GM's team pickers, where Seattle and Vegas now come in their place by name, not after the others.
STAGE_F = tuple((a, old, _imm(old, 32), why) for a, old, why in (
    (0x129b44, 0x3880001e, "favourite-team list: count the NHL teams numbered below 32"),
    (0x12710c, 0x2c85001e, "team lists' order: teams 0-31 first, by name (first team)"),
    (0x127118, 0x2c05001e, "team lists' order: teams 0-31 first, by name (second team)"),
    (0x127130, 0x2c05001e, "team lists' order: teams 0-31 first, by name (first team 32 or more)"),
))
STAGE_F_CAVES = ()


def _ds(word, disp):
    """The game's std / stdu / ld `word` with a new displacement (the last two bits are the instruction's own)."""
    return (word & 0xffff0003) | (disp & 0xfffc)


# Stage G, Be a GM's team picker (lab round 6: Be a GM crashed as its screen opened). Its call GetTeamIDsForDivisionId
# (0x2dd1fc, ION handler vf+0x70) copies the teams it shows onto the stack, 200 bytes each, in room for 30 (+0x80 .. +0x17f0)
# before the function's saved registers. Be a GM asks for the whole league: with Seattle and Vegas in the Pacific that is 32
# teams, and the last two wrote over the saved registers and the return address. The frame grows by two teams.
PICK_FRAME, PICK_MORE = 0x1830, 2 * 200
_PICK_SAVES = ((0x2dd204, 0xf8011840), (0x2dd208, 0xfbe11828), (0x2dd210, 0xfba11818), (0x2dd214, 0xfb411800),
               (0x2dd220, 0xfbc11820), (0x2dd234, 0xfb811810), (0x2dd238, 0xfb611808), (0x2dd23c, 0xfb2117f8),
               (0x2dd240, 0xfb0117f0), (0x2dd568, 0xe8011840), (0x2dd570, 0xeb0117f0), (0x2dd574, 0xeb2117f8),
               (0x2dd578, 0xeb411800), (0x2dd57c, 0xeb611808), (0x2dd580, 0xeb811810), (0x2dd584, 0xeba11818),
               (0x2dd588, 0xebc11820), (0x2dd58c, 0xebe11828))
STAGE_G = (
    ((0x2dd1fc, 0xf821e7d1, _ds(0xf821e7d1, -(PICK_FRAME + PICK_MORE)), "Be a GM team picker: room for 32 teams on the stack"),)
    + tuple((a, old, _ds(old, (old & 0xfffc) + PICK_MORE), "Be a GM team picker: a saved register above the 32 teams")
            for a, old in _PICK_SAVES)
    + ((0x2dd590, 0x38211830, _imm(0x38211830, PICK_FRAME + PICK_MORE), "Be a GM team picker: give the bigger frame back"),))
STAGE_G_CAVES = ()

# Stage H, the staff count per team (lab round 7: the first Be a GM played, the second one in the same session crashed in the
# game's memory allocator, 0xc9aa14, reading a free block's link at 0). StaffLogic's mDraftStorage (StaffLogic+0xbcfc, made at
# 0x3bc3e4 for every Be a GM / Season) holds 30 records of 12 bytes (byte 0 the team, then counts by role); 0x3bd7c8 adds
# one to record[team] for every staff member it gives a team. Seattle's and Vegas's records (30 and 31) lie up to 24 bytes
# past the block, over the next block's size and links, which the allocator trips over later. The block grows to 32 records.
STAGE_H = (
    (0x3bc428, 0x38600168, _imm(0x38600168, 32 * 12), "staff counts: room for 32 teams"),
    (0x3bc448, 0x38800168, _imm(0x38800168, 32 * 12), "staff counts: clear 32 teams"),
    (0x3bc53c, 0x2c18001e, _imm(0x2c18001e, 32), "staff counts: number 32 teams"),
)
STAGE_H_CAVES = ()

# Stage I, the preseason (lab round 9: the second Be a GM in one session crashed as it loaded, freeing a calendar buffer whose
# next block read size 0x10 / link 20, two team numbers; rounds 7 and 8 crashed in the allocator too). 0x28470c copies each
# league's games into a buffer of 1,350 games (0x1c bytes each, the copy stops at 1,350), and for the NHL 0x2843e8 then adds
# the preseason after them without any limit: one game a day for 28 days per division (pairs table 0x1ab1060), 28 for a
# division of 8, 21 for one of 7. The game's 8/8/7/7 make 98 (1,230 + 98 fits); 32 teams in four divisions of 8 make 112, and
# 1,280 games + 112 run 42 games past the buffer, over the next blocks' sizes and links. Room for 1,350 + 4 * 28.
CALENDAR_ROWS = 1350 + 4 * 28 + 2                       # 1,464 games (two spare)
STAGE_I = (
    (0x2849f0, 0x606393a8, _imm(0x606393a8, CALENDAR_ROWS * 0x1c), "season calendar: room for the preseason of 32 teams"),
    (0x284a18, 0x38a00546, _imm(0x38a00546, CALENDAR_ROWS), "season calendar: clear all of it"),
)
STAGE_I_CAVES = ()

# Stage J, the All-Star game (read in the program, NOT played; docs/notes/all-star.md). The Season makes its two All-Star
# teams (keys 60 / 61) from the team slots in the data words 0x1ab0688 / 0x1ab068c (30, 31: Seattle and Vegas now) and picks
# their players itself at the break (League event 9 -> 0x455430), so the slots' own players are never used. The calendar
# loader (0x3de664) took a row whose home team is at or above the team count as the All-Star game; with 32 teams in 5-bit
# fields no row can say that (stage E made the count 32). The two teams come from EASHL 1 / 2 (owner, 2026-10-13: online
# only) and a team playing itself marks the All-Star game (no calendar of the game's has such a row).
ALL_STAR_SLOTS = (220, 221)                             # EASHL 1 / 2 become the Eastern / Western All-Stars
STAGE_J = (
    (0x1ab0688, 30, ALL_STAR_SLOTS[0], "All-Star game: the Eastern All-Stars from EASHL 1 (data)"),
    (0x1ab068c, 31, ALL_STAR_SLOTS[1], "All-Star game: the Western All-Stars from EASHL 2 (data)"),
)
STAGE_J_CAVES = (
    (0x3de66c, 0x7c1e2000, [
        (0x7c1e1800, "cmpw r30,r3       a team against itself?"),
        (0x41820008, "beq +8            yes: equal, so not below the count: the All-Star game"),
        (0x7c1e2000, "cmpw r30,r4       the game's own instruction: home at or above the count"),
    ], "calendar: a team against itself is the All-Star game"),
)
DATA_WORDS = (0x1ab0688, 0x1ab068c)                     # data, not instructions (tools/audit_patch.py)
# the two places' names and groups, as the game's own All-Star slots 30 / 31 have them (conference group 2 = East, 1 = West;
# the division group is the conference); their jerseys and players stay EASHL's
ALL_STAR_LOOK = {220: ('Eastern All-Stars', 'East', 'EAS', 2), 221: ('Western All-Stars', 'West', 'WES', 1)}
# ... and their art and rink. EASHL's art 255 means "the online club's own crest", which never arrives offline: playing the
# All-Star game hung after loading, on the lineup card (lab round 12, 2026-10-14; arena 30 alone did not help, art 30 / 31
# did). The game's own All-Star slots have art 30 / 31 (Seattle / Vegas share it: the All-Stars show their menu logos, and
# their jerseys once the new Seattle / Vegas jerseys are installed) and play in arena 30 (Nashville's art, the 2015 host)
# with tunnel and spotlight 30 and the audio of their slot.
ALL_STAR_RINK = {220: {'artid': 30, 'arenaid': 30, 'tunnel': 30, 'spotlight': 30, 'audioid': 1378},
                 221: {'artid': 31, 'arenaid': 30, 'tunnel': 30, 'spotlight': 30, 'audioid': 1323}}

# Stage K, the draft (read in the program, NOT played; docs/notes/draft.md). The draft object (made at 0x3c4ad4 for the
# Season and Be a GM) holds the picks (+0x134, count +0x138), round 1's order and later rounds' order (+0x13c / +0x140, team
# numbers in words) and the number of teams (+0x150, 30). 0x228538 numbers the picks into arrays of count x 4 bytes
# indexed by team, so with a count of 30 Seattle (30) and Vegas (31) write past them. The lottery (0x3c4e34) collects the
# 14 worst teams that missed the playoffs into a stack array at r1+0x88 (later rounds' order is copied from it before the
# draw) and draws one with the 2014 odds for 14 (a number below 1,000 against a ladder of limits written in the code,
# 0x3c4ee4-0x3c5090); the winner moves to the front (0x3c5094). With 32 teams 16 miss the playoffs: all 16 are collected and
# drawn among (owner, 2026-10-13) with today's NHL odds (LOTTERY_ODDS; one draw, the winner picks first, as the game does).
# The 16 playoff teams' records sit right after the array at r1+0xc0, so the draw's 15th and 16th go into round 1's order
# at once (cave at 0x3c50d4), round 1 copies only 14 from the stack, and the playoff teams pick 17-32. The fixed 2015
# order tables (0x2724cc, 30 teams) are never read: every draft is the lottery. A Season makes its own picks (0x228050 at
# set-up, 0x2283a4 / 0x228480 each new year: 7 rounds x 30 teams); with 32 they fill leaguedraftpick's 6 x 7 x 32 rows
# (META_ROWS). Be a GM keeps a copy of the order in its own block (30 bytes at +0x3294a, the next bytes are used), so it
# stays at 30; the sim (0xdfe08) read 32 bytes of it and wrote 32 past its own 30 (over the flags at 0x1045a / 0x1045b): it
# reads the 30, and teams 30 / 31 get the sim's default place (15), as every team without one did.
# Today's NHL lottery odds for the 16 teams that miss the playoffs, worst first, in thousandths (since 2021-22; the NHL has
# two draws and a winner moves up at most 10 places, the game has one draw and the winner picks first).
LOTTERY_ODDS = (185, 135, 115, 95, 85, 75, 65, 60, 50, 35, 30, 25, 20, 15, 5, 5)


def _lottery_draw():
    """Our code for the draw at 0x3c4f0c, where r5 is the drawn number below 1,000: r4 = the winner's place among 16 (how
    many of the odds' running totals are at or below r5), then r5 = 0 so the game's `cmpwi r5,250 ; blt` takes the path of
    a drawn place in r4 and skips its own ladder."""
    code = [(_li(4, 0), "li r4,0           the worst team ...")]
    total, end = 0, 1 + 3 * (len(LOTTERY_ODDS) - 1)
    for odds in LOTTERY_ODDS[:-1]:
        total += odds
        at = len(code) + 1
        code += [(0x2c050000 | total, f"cmpwi r5,{total}"),
                 (0x41800000 | (end - at) * 4, "blt               found"),
                 (0x38840001, "addi r4,r4,1      ... or the next")]
    return code + [(_li(5, 0), "li r5,0           found: the game takes r4"),
                   (0x2c0500fa, "cmpwi r5,250      the game's own instruction")]


STAGE_K = (
    (0x3c4084, 0x3880001e, _imm(0x3880001e, 32), "draft: 32 teams (a loaded draft)"),
    (0x3c4b84, 0x3860001e, _imm(0x3860001e, 32), "draft: 32 teams (a new draft)"),
    (0x3c30d0, 0x2c1b001e, _imm(0x2c1b001e, 32), "draft: the owners of a round's 32 picks"),
    (0x3c4408, 0x2c1c00d2, _imm(0x2c1c00d2, 7 * 32), "draft: simulate the rest of 7 x 32 picks"),
    (0x3c4660, 0x2c1d001e, _imm(0x2c1d001e, 32), "draft: prospect lists for 32 teams"),
    (0x3c4e34, 0x3bc0001d, _imm(0x3bc0001d, 31), "draft lottery: start from the last of 32"),
    (0x3c4e98, 0x2c1f000e, _imm(0x2c1f000e, 16), "draft lottery: all 16 teams that missed the playoffs"),
    (0x3c4eb4, 0x3860000e, _imm(0x3860000e, 16), "draft lottery: later rounds' order of all 16"),
    (0x3c5184, 0x2c1e001e, _imm(0x2c1e001e, 32), "draft: playoff teams among 32"),
    (0x3c5a9c, 0x90670038, _imm(0x90670038, 16 * 4), "draft: round 1's playoff teams pick 17-32"),
    (0x3c5ab0, 0x90660038, _imm(0x90660038, 16 * 4), "draft: later rounds' playoff teams pick 17-32"),
    (0x3c5afc, 0x38e0001e, _imm(0x38e0001e, 32), "draft: number the picks 32 to a round"),
    (0x3c5c08, 0x2c06001e, _imm(0x2c06001e, 32), "draft: a team's place among 32"),
    (0x3c4bd4, 0x4bead8f9, _li(3, 0), "draft: always the lottery (the fixed 2015 order has 30 teams)"),
    (0x228050, 0x2c13001e, _imm(0x2c13001e, 32), "Season set-up: draft picks for 32 teams"),
    (0x2283a4, 0x2c1c001e, _imm(0x2c1c001e, 32), "new year: draft picks for 32 teams"),
    (0x228480, 0x2c19001e, _imm(0x2c19001e, 32), "new year: draft picks for 32 teams (second way)"),
    (0x3c5a34, 0xe8e10608, _li(7, 14), "draft: round 1 takes 14 from the lottery's stack (15 and 16 are in already)"),
    (0xdfee0, 0x8103029c, _li(8, 30), "sim: read Be a GM's 30 places of the order, not 32"),
)
STAGE_K_CAVES = (
    (0xdfef0, 0x61270000, [
        (0x8103029c, "lwz r8,0x29c(r3)  r8 = 32 again: teams without a place get the default"),
        (0x61270000, "ori r7,r9,0       the game's own instruction"),
    ], "sim: every one of 32 teams gets a draft place"),
    (0x3c4f0c, 0x2c0500fa, _lottery_draw(), "draft lottery: one draw among 16 with today's odds"),
    (0x3c50d4, 0x93e10088, [
        (0xe8610650, "ld r3,0x650(r1)   the draft"),
        (0x80c3013c, "lwz r6,0x13c(r3)  round 1's order"),
        (0x80e100c0, "lwz r7,0xc0(r1)   the draw's 15th"),
        (0x90e60038, "stw r7,0x38(r6)   picks 15th in round 1"),
        (0x80e100c4, "lwz r7,0xc4(r1)   the draw's 16th"),
        (0x90e6003c, "stw r7,0x3c(r6)   picks 16th"),
        (0x93e10088, "stw r31,0x88(r1)  the game's own instruction: the winner picks first"),
    ], "draft lottery: round 1's picks 15 and 16 before the playoff teams' records"),
)
# Words that are another instruction, not the game's with a new number (tools/audit_patch.py shows both)
OTHER_INSTRUCTIONS = (0x3c4bd4, 0x3c5a34, 0xdfee0, 0x40cb7c, 0x16320c, 0x3721a4, 0x402d24, 0x407960, 0x407964)

# The game's description of its database (db/nhlng-meta.xml, in cacheboot.big on the disc). The game reads a loose copy in
# its own folder (dev_hdd0/game/<id>/USRDIR/db, lab log) and takes the Season and Be a GM tables' rows from it (a Season
# save made in the lab had 32 Be a GM rows). Team fields that hold "no team" (-1) as well as a team up to Vegas (31) need
# 33 values: six bits, not five (a value is stored as value - rangelow). The lab's earlier file raised them to 31 in five
# bits; the rows and ranges are that file's, the bits are new.
# The bits themselves come from the game's database (db/nhlng.db, also in cacheboot.big, also read as a loose file): its
# empty Season / Be a GM tables are the templates, and a Season save copies their field layout whatever the description
# says (lab round 4, 2026-10-13: description at 6 bits, Season save at 5). With five bits Vegas (31) is stored as -1, "no
# team": the Season gave Vegas's 23 players to nobody, Vegas dressed nobody, and simulating its first game crashed at
# 0x3b6630 (rounds 3 and 4). So both files go into the game's folder, with the same bits (fit_db, check_db).
META_FILE = ('db', 'nhlng-meta.xml')
DB_FILE = ('db', 'nhlng.db')
META_ROWS = {'leaguegmdata': 32, 'leaguestaffdata': 32, 'leaguedraftpick': 32 * 42,
             'nhlschedule': schedule.PATCH_ROWS - CALENDAR_STOCK, 'nhlfutureschedule': schedule.PATCH_ROWS - CALENDAR_STOCK,
             'stockteamsalaryextras': 2}
META_TEAMS = (('leaguegamemodesvars', 'team'), ('leaguescoutvisits', 'team'), ('leaguefreeagentdata', 'originalteamid'),
              ('leaguefreeagentdata', 'signedteamid'), ('leaguerookiedata', 'draftteam'),
              ('leaguecontractoffers', 'teamnotification'), ('leaguedraftpick', 'origteamid'), ('leaguedraftpick', 'owner'),
              ('leagueplayerbiotable', 'proteam'), ('leagueplayerbiotable', 'tradeblockteam'),
              ('leagueplayerbiotable', 'draftteam'),
              ('exhibitionplayerbiotable', 'proteam'))    # the roster's own rights (RIGHTS_TABLE, rights_wide)
META_TEAM_HIGH = 31
# the Season's league keys go up to 65 (stage M): leagueteams.ahlaffiliate (-1..62 in six bits) gets seven
META_KEYS = (('leagueteams', 'ahlaffiliate'),)
META_KEY_HIGH = 126
# the Season keeps its human teams as one bit per team of a league (0x2715c8 / 0x2718bc write it, 0x271ae4 reads it back on
# load) in leaguestates.value, 31 bits: Vegas (bit 31, also Henderson, key 63) came back as 0, a reloaded Vegas Season had no
# team ("undefined", Play Next Game greyed; lab round 13, 2026-10-14). Seattle's bit 30 fits. Thirty-two bits keep all 32.
META_MASKS = (('leaguestates', 'value'),)
META_MASK_HIGH = 2 ** 32 - 1
META_HIGH = {**{tf: META_TEAM_HIGH for tf in META_TEAMS}, **{tf: META_KEY_HIGH for tf in META_KEYS},
             **{tf: META_MASK_HIGH for tf in META_MASKS}}

# Stage O, the farm work of Seattle and Vegas (lab round 12, 2026-10-14, read in the program, NOT played). In a Vegas Season the
# computer's Seattle dressed 5 defencemen after two injuries and the game's line picker (0x1528f8) looped for ever. Every other
# NHL team called players up from its farm team (lab saves: 0-5 per team by February), Seattle and Vegas none. The org roster
# brain (one NHL team and its farm team) still asked "key < 30" in three places:
# - 0x1c7750 moves a player to a team; with no target given (-2) the target is the brain's own team when it is an NHL team,
#   else the farm team's parent / nobody, so a call-up by Seattle's or Vegas's brain went nowhere (0x1c7898);
# - 0x1c41f4, which 0x1c7750 calls, treats a new team numbered 30 or more as a farm team (0x1c42f4);
# - at a new season (0x29bcc4) a stepper (constructor 0x22d1b8) ranks the NHL teams into a list of 30 words
#   (values[key] = place, so keys 30 / 31 wrote 8 bytes past the 0x84-byte block, inside the allocator's 0x10 rounding)
#   and runs the brain's season work (0x1cc86c) for each team, which skips keys 30 or more (0x1cc88c). That work reads the
#   team's computer-GM settings (0x38fb94), a table of 30: teams 30 / 31 get team 29's, as before.
STAGE_O = (
    (0x1c7898, 0x2c05001e, _imm(0x2c05001e, 32), "farm work: a call-up by Seattle / Vegas goes to their NHL team"),
    (0x1c42f4, 0x2c06001e, _imm(0x2c06001e, 32), "farm work: Seattle / Vegas are NHL teams when a player joins them"),
    (0x1cc88c, 0x2c1e001e, _imm(0x2c1e001e, 32), "season work: Seattle / Vegas get the new season's roster work"),
    (0x29be68, 0x38600084, _imm(0x38600084, 0xc + 32 * 4), "season work: the team list holds 32"),
    (0x22d1f4, 0x38a00078, _imm(0x38a00078, 32 * 4), "season work: clear the 32 places"),
)
STAGE_O_CAVES = ()

# Stage P, the computer GMs' daily roster work for Seattle and Vegas (lab round 14, 2026-10-14). In a Vegas Be a GM the
# computer traded Seattle's Eberle away on 25 January 2027 (autosaves 13:43 / 13:44): Seattle kept 19 dressed (line place
# pOUV empty, three healthy scratches unused) and the next sim crashed in the line picker (0x151fb4 calls the weighted pick
# 0x30ba78 with an empty list). Every other team had 20 dressed: the league's daily steps fix rosters and lines in loops
# over teams 0-29 that skip 30 / 31. Every table they reach already holds 32 (SalaryCapManager, stage A; list A, stage B;
# the org roster brain, stage O; 0x38fb94 gives teams 30 / 31 team 29's GM settings):
# - 0x281c34 (the daily step 0x288310) and 0x28ac78 run each computer GM (0x1cc678 / 0x1ce248, Be a GM only, 0x3a60e4);
# - 0xf3b8c4 (daily from 0x288310, end of the off-season from 0x29d338) checks every team's roster and lines and rebuilds
#   them (0x1c3130, 0xf3857c, 0x1c96dc, LinesBrain 0x1b9b88); its two list loops push teams and their farm keys
#   (0x279ecc, list A) into growing lists, and the main loop marks a team done in its caller's object (+0x30 + team; the
#   30 bytes end at +0x4e, the objects have room: stack 0x50, 0xec917c's screen object has no field before +0x1024);
# - 0x29c590 (league event 0x1d) re-signs the computer teams' players; 0x29d338 (event 0x19) fills their rosters for the
#   new season and re-lines them.
# Left at 30: League::LeagueManager::mLastYearPlayoffRun (60 words, NHL 0-29 then AHL; 0x298b18, 0x2989f4): Seattle and
# Vegas have no last-year playoff run; 0x276f10 / 0x27712c (GM settings per team at season start).
STAGE_P = tuple((a, old, _imm(old, 32), why) for a, old, why in (
    (0x281ca4, 0x2c1f001e, "daily: the computer GMs of Seattle / Vegas look after their rosters"),
    (0x28ad54, 0x2c1f001e, "the computer GMs of Seattle / Vegas look after their rosters (second place)"),
    (0xf3bb88, 0x2c03001e, "daily roster check: the list of 32 NHL teams"),
    (0xf3bc14, 0x2c1d001e, "daily roster check: the farm teams of 32 NHL teams"),
    (0xf3bc5c, 0x2c03001e, "daily roster check: Seattle / Vegas get full rosters and lines (a trade left Seattle short)"),
    (0x29c91c, 0x2c1c001e, "re-signing: Seattle / Vegas re-sign their players"),
    (0x29d608, 0x2c17001e, "new season: Seattle / Vegas fill their rosters"),
    (0x29d77c, 0x2c1c001e, "new season: Seattle / Vegas set their lines"),
))
STAGE_P_CAVES = ()

# Stage Q, a game-day roster move between a club and its partner (lab round 15, 2026-10-14). In season 2 of a Vegas Be a GM
# the sim crashed on 2 October 2027 (Vegas - Anaheim) in 0x290a50, the game-day step: for each team it builds an org roster
# brain of the partner club (0x1c3130: an NHL team's farm team, a farm team's first parent) and, when it has two parents,
# a second brain at [r1+0xeb28] (else 0). At 0x296768 it looks for a player (Petr Mrazek, Anaheim's, then on San Diego's
# roster, not dressed) in the first brain's list; not there, it took the second brain without asking whether there is one
# (0x2967c8) and crashed reading through 0 (0x1c4154). Every NHL club and 31 of 32 farm teams have one partner (only shared
# farm teams have two), so the lookup in the second brain must not run without one. Its answer is never used (r3 is
# overwritten at 0x2967e0), so its call makes room for the check: no second brain = r31 0 = no move (0x296824 / 0x296864),
# as when the move does not fit.
STAGE_Q = (
    (0x2967d8, 0x63e30000, 0x2c1f0000, "game day: is there a second partner club? (cmpwi r31,0)"),
    (0x2967dc, 0x4bf2d979, 0x41820048, "game day: none, so no roster move (beq 0x296824; the lookup it replaces was unused)"),
)
STAGE_Q_CAVES = ()
OTHER_INSTRUCTIONS += tuple(a for a, *_ in STAGE_Q)

# Stage R, the next season's calendar (lab round 15, 2026-10-14). A new season's games are the roster's nhlfutureschedule
# (byED) and ahlschedule (AJKN) moved to the new year's weekdays, every team taking the games of the team before it in its
# division (0x283800 -> 0x283498, by the years since 2015). That team map is a stack table of 30 words (r1+0xc0); the
# words of teams 30 / 31 lay in the next table (r1+0x138, the games moved to the season's end), which is cleared before
# the map is read: their games went to key 0. Season 2 of a Vegas Be a GM had Anaheim and Calgary without a game, AHL
# Colorado and Ontario too, and "Anaheim" in 144 AHL games, whose game days ran Be a GM's money code for AHL clubs (flags
# past the SalaryCapManager's 32, over the StatsCache: leaving Be a GM crashed freeing 0x01000000). The function's frame
# grows by 0x80 and the map of 32 words moves into the new room (r1+0x790). The roster's byED must hold all 32 teams too
# (calendartest writes the 32-team calendar there).
CAL_FRAME, CAL_MORE = 0x790, 0x80
STAGE_R = (
    (0x283800, 0xf821f871, _ds(0xf821f871, -(CAL_FRAME + CAL_MORE)), "next season's calendar: 0x80 bytes more stack"),
    (0x283808, 0xf80107a0, _ds(0xf80107a0, 0x7a0 + CAL_MORE), "next season's calendar: the return address above it"),
    (0x283840, 0x81210804, _imm(0x81210804, 0x804 + CAL_MORE), "next season's calendar: the caller's 9th word above it"),
    (0x284200, 0xe80107a0, _ds(0xe80107a0, 0x7a0 + CAL_MORE), "next season's calendar: the return address above it"),
    (0x284250, 0x38210790, _imm(0x38210790, CAL_FRAME + CAL_MORE), "next season's calendar: give the bigger frame back"),
    (0x28399c, 0x30a100c0, _imm(0x30a100c0, CAL_FRAME), "next season's calendar: the team map of 32 in the new room"),
    (0x28415c, 0x808400c0, _imm(0x808400c0, CAL_FRAME), "next season's calendar: an away team from the map of 32"),
    (0x284160, 0x806300c0, _imm(0x806300c0, CAL_FRAME), "next season's calendar: a home team from the map of 32"),
)
STAGE_R_CAVES = ()

# Stage S, the roster's calendar room (lab round 19, 2026-10-15). The game gives 35 tables of a roster a fixed room of its own:
# 0x3dd69c reads pairs (table number in the database, rows) from the data at 0x1acc878 and sets each table's room in memory
# (0xdc217c), whatever the roster file, db/nhlng-meta.xml or db/nhlng.db say. nhlschedule (98) and nhlfutureschedule (97)
# get 1,291 rows there: Be a GM and Season copied rows 0-1,290 of an 84-game calendar and the last 54 games (4-10 April)
# were lost (teams ended at 80-82 games). Both get schedule.PATCH_ROWS.
ROOM_WORDS = (0x1acc90c, 0x1acc914)                     # the room of nhlfutureschedule and nhlschedule (data)
STAGE_S = tuple((a, CALENDAR_ROOM, schedule.PATCH_ROWS, f"roster room: {what} holds {schedule.PATCH_ROWS} rows (data)")
                for a, what in zip(ROOM_WORDS, ('nhlfutureschedule', 'nhlschedule')))
STAGE_S_CAVES = ()
DATA_WORDS += ROOM_WORDS

# Stage T, the league's team rankings (lab round 20, 2026-10-15). The StatsCache (0xf674 bytes, made at 0x140b30 by
# 0x140aa8, which the league's tasks call) ranks the teams in 17 team stats: 0x1405f0 asks the league's team stats for each
# (0x3a2818 with the stat from 0x21bf750, row count 0x3a47f0) and writes the teams in blocks of 0x360 with room for 30
# entries of 0x1c (+8), the stat's two flags at +0x350 and the count at +0x364 (in the next block's head). With 31 or 32
# teams the count runs past: the 31st team lies over the flags and the count, and the next block's first entry marks it
# with 1 over the high byte of its team pointer. In Be a GM's second preseason (24 September 2027) 0x1402f8 then read
# team 31 through 0x01aefde0 and crashed (0x1404a8, reading 0x8db30180). Each ranking keeps its first 30 teams, as when
# teams have not played yet (team 23 was missing from that list): the room of 0x360 is read across the game's menus, so
# it does not grow.
RANK_ROOM = 30
STAGE_T = ()
STAGE_T_CAVES = (
    (0x140684, 0x607a0000, [
        (0x2c030000 | RANK_ROOM, f"cmpwi r3,{RANK_ROOM}      more teams than the ranking's room?"),
        (0x40810008, "ble +8"),
        (0x38600000 | RANK_ROOM, f"li r3,{RANK_ROOM}         yes: the first {RANK_ROOM}"),
        (0x607a0000, "ori r26,r3,0      the game's own instruction: the count"),
    ], "team rankings: at most 30 teams in each of the 17 stats"),
)

# Stage U, the keys of a year's draft picks (lab round 22, 2026-10-15). leaguedraftpick holds six years of picks; a pick's
# key (XWot, 11 bits) is (year mod 6) x 210 + its number in the year, made at the Season's set-up (0x227e74, six years) and
# each new year (0x2281d4, the year six on), where the new year's picks take the keys of the year they replace. The 210
# (7 rounds x 30) is built with shifts: m << 5 = 32m, m - 32m = -31m, m + -31m = -30m, -30m << 3 = -240m,
# -30m - -240m = 210m. With 224 picks a year each year ran 14 keys into the next: from the start of Be a GM the keys of
# neighbouring years overlapped (70 keys twice), and at the first new year (June 2027) the new picks also overwrote
# round 1 of teams 0-13 of the next draft and round 7 of teams 18-31 four years on. The next draft (June 2028) had no
# pick for those 14 places (the board showed the NHL shield and one name again and again) and crashed in the memory
# manager when Seattle's turn came (0xc9bc18 writing 0xd9d, from the draft's 0x3c3030). The key becomes (year mod 6) x 224
# + number (0-1,343, room 1,344): two multiplications, r4 left as the game leaves it (-240m; nothing reads it).
PICKS_PER_YEAR = 7 * 32
_PICK_KEY = ((0x78642ea4, 0x1c83ff10, "mulli r4,r3,-240  (was sldi r4,r3,5) r4 as the game leaves it"),
             (0x7c841810, 0x1c630000 | PICKS_PER_YEAR, f"mulli r3,r3,{PICKS_PER_YEAR}  (was subfc) the year's first key"),
             (0x7c632014, NOP, "nop               (was addc)"),
             (0x78641f24, NOP, "nop               (was sldi r4,r3,3)"),
             (0x7c641810, NOP, "nop               (was subfc: m x 210)"))
STAGE_U = tuple((base + 4 * k, old, new, f"draft pick keys {where}: {why}")
                for base, where in ((0x227e74, 'at the Season set-up'), (0x2281d4, 'of a new year'))
                for k, (old, new, why) in enumerate(_PICK_KEY))
STAGE_U_CAVES = ()
OTHER_INSTRUCTIONS += tuple(a for a, _, new, _ in STAGE_U if new != NOP)

# Stage V, the computer's NHL roster count of Seattle and Vegas (lab round 27, 2026-10-15, read in the program). In a Be a GM
# with Anaheim the computer's Vegas fell to 16-17 NHL players by November 2026 while 13 healthy players with its rights sat
# in Henderson; the sim hung in the line picker (runs 8-10). The game-day step called players up (0x2973e4), but every
# roster commit (0x1ca618) reruns the roster planner (0x3ccfd4), which sent them down again. The planner's pool gives each
# player property 0xf, "on an NHL team" (0x48678c: his team key, +0x66, from 0 to 29), and its count (0x48c82c) puts a
# player with 0xf on the NHL roster, the others in the farm; for a team key of 30 or more (in the game's own league a farm
# or European club, which has no farm team) it counts every player as NHL. So Seattle's and Vegas's own NHL players were
# "not on an NHL team" and their whole pool, farm included, counted as NHL roster: the planner saw a full roster and kept
# no call-up. After a plan the SalaryCapManager record (0x3a8a30; its flag read is stage A's) is refreshed for keys below
# 30 only (0x494b84). Not team keys: 0x488b60 / 0x3eb9e8 are case 30 of switches over other numbers.
STAGE_V = tuple((a, old, _imm(old, 32), why) for a, old, why in (
    (0x486cf8, 0x2c1f001e, "roster plan: a player of Seattle / Vegas is on an NHL team"),
    (0x48c8b4, 0x2c03001e, "roster plan: Seattle's / Vegas's farm players count in the farm, not on the NHL roster"),
    (0x494b84, 0x2c03001e, "roster plan: Seattle's / Vegas's money record is brought up to date after a plan"),
))
STAGE_V_CAVES = ()

# Stage W, a player of Seattle's / Vegas's farm team, and Be a Pro with Seattle or Vegas (lab round 28, 2026-10-16). A new
# Be a NHL Pro with Seattle's Catton crashed while it loaded (read through 0 at 0x1c0098 / 0x3b5ef0). The league had put
# him on Seattle's farm team, Coachella Valley (league key 62, stage M), as it does with young players over the NHL roster
# room. The game's "which team is this player on" query (0x220834 mode 0, 0x221124, ten callers; and 0x2211d8) asks the
# league's roster table for a team below 60, the old number of league teams that stage M made 64: key 62 / 63 was not
# found, the pro's team key (+0x34, 0x458b84) was -1, and the lines helper (0x1c0044) found nobody on team -1's list
# (0x3b718c gave -1). Both queries ask below 64 now; the same lookup serves the player pages of a Season too.
# With Edmonton's Dach (on Edmonton's NHL roster) the career loaded and a game was played. Read in the program, for a pro
# of Seattle / Vegas on the NHL roster: the set-up (0x460e3c) takes the team key as an NHL team only below 30, 0x459904
# (0 to 29 is NHL) and the four branches of 0x45b768 (below 30 the NHL's, else the farm league's). Left: loops over 30
# records (0x455c38, 0x459b68, 0x459bcc, 0x4645ec), rank and game-count limits (0x45723c, 0x4636c0, 0x4594d4), switches
# (0x46a7bc). Lab round 35 (2026-10-19): a Seattle pro on Seattle's NHL roster (O'Brien) crashed while "Loading Be A Pro"
# (read at 0x66, 0x1c4814): 0x458c84 fills the pro's teams (+0x1513 + n, n 2 his NHL team, n 1 his farm team) and at
# 0x458ec8 took a team key of 30 or more for a farm club, so Seattle (30) got NHL team 62 and farm team 30, and the set-up
# built Coachella's roster and did not find him there (docs/notes/league-menus.md). Catton (round 28) was on Coachella.
STAGE_W = tuple((a, old, _imm(old, new), why) for a, old, new, why in (
    (0x2209c0, 0x3880003c, 64, "a player's team (0x220834): a team of the league's 64, Coachella Valley / Henderson too"),
    (0x2212d4, 0x3880003c, 64, "a player's team (0x2211d8): a team of the league's 64"),
    (0x460eb8, 0x2c9d001e, 32, "Be a Pro set-up: a pro of Seattle / Vegas is on an NHL team"),
    (0x459904, 0x2c83001d, 31, "Be a Pro: Seattle and Vegas are NHL teams (0 to 31)"),
    (0x45bba4, 0x2c18001e, 32, "Be a Pro: Seattle / Vegas take the NHL's branch (1 of 4)"),
    (0x45bc6c, 0x2c18001e, 32, "Be a Pro: Seattle / Vegas take the NHL's branch (2 of 4)"),
    (0x45bd7c, 0x2c18001e, 32, "Be a Pro: Seattle / Vegas take the NHL's branch (3 of 4)"),
    (0x45be38, 0x2c18001e, 32, "Be a Pro: Seattle / Vegas take the NHL's branch (4 of 4)"),
    (0x458ec8, 0x2c1d001e, 32, "Be a Pro: a pro of Seattle / Vegas has his own team as NHL team, his farm club as farm team"),
))
STAGE_W_CAVES = ()

# Stage X, the salary cap by real season (2026-10-16, read in the program; docs/notes/salary-cap.md). Be a GM's set-up
# (0x3c5fb0, season 0) and each new year (0x3c6740, the new season's number n) take the league's money from a table of
# the game's resources (reader 0x4a74e0): floor and cap through 0x4a7240(obj, row 0 / 1, n) (row 0's base x $100,000 plus
# the yearly rises of rows 1 / 2 x $1,000), the lowest salary and the highest rookie salary through 0x4a73b0(obj, row 3 / 4,
# n) (x $1,000); the most one player may earn is the cap / 5 (0x4a7498). The contract demands (0x31ab98, 0x31acc8) read the
# lowest salary and that maximum. Only the wrappers 0x4a7360 / 0x4a7388 / 0x4a7498 / 0x4a7448 / 0x4a7470 call the two.
# A roster made for the patch holds real 2026-27 dollars (contracts.py), so both answer from CAP_TABLE: the real numbers
# of the agreement (2026-27, 2027-28), the league's estimate for 2028-29, then the last season's (owner, 2026-10-16). At a
# new year the game still lifts cap and floor by as much as the highest team payroll is over the cap (0x3c691c): 0.19's
# table (+$1.5M) gave $105.5M for 2027-28 and the game made it $107.235M (lab round 29).
CAP_ROWS = {0: 'floor', 1: 'cap', 3: 'lowest salary', 4: 'highest rookie salary'}
CAP_TABLE = {                                           # row: dollars in seasons 0, 1, 2, 3 (2026-27 .. 2029-30), then held
    0: (76_900_000, 83_900_000, 94_350_000, 94_350_000),
    1: (104_000_000, 113_500_000, 127_500_000, 127_500_000),
    3: (850_000, 900_000, 950_000, 1_000_000),
    4: (1_025_000, 1_075_000, 1_125_000, 1_175_000),    # the entry-level maximum: the lowest salary + $175,000
}
CAP_SEASONS = 4
FIRST_SEASON = 2026


def cap_of(row, season):
    """What the patched 0x4a7240 / 0x4a73b0 answer for `row` (CAP_ROWS) in season number `season` (0 = 2026-27)."""
    return CAP_TABLE[row][min(max(season, 0), CAP_SEASONS - 1)]


def _cap_cave():
    code = [(0x2c050000, "cmpwi r5,0        the season's number below 0?"),
            (0x40800008, "bge +8"),
            (0x38a00000, "li r5,0           yes: the first"),
            (0x2c050000 | CAP_SEASONS - 1, f"cmpwi r5,{CAP_SEASONS - 1}        past the table?"),
            (0x40810008, "ble +8"),
            (0x38a00000 | CAP_SEASONS - 1, f"li r5,{CAP_SEASONS - 1}           yes: the last season's numbers"),
            (0x5486103a, "slwi r6,r4,2      the key: row x 4 + season"),
            (0x7cc62a14, "add r6,r6,r5")]
    for row, values in CAP_TABLE.items():
        for season, dollars in enumerate(values):
            code += [(0x2c060000 | row * CAP_SEASONS + season,
                      f"cmpwi r6,{row * CAP_SEASONS + season}       {CAP_ROWS[row]}, {FIRST_SEASON + season}-"
                      f"{(FIRST_SEASON + season + 1) % 100:02d}?"),
                     (0x40820010, "bne +16"),
                     (_addis(3, 0, dollars >> 16), f"lis r3,0x{dollars >> 16:x}"),
                     (0x60630000 | dollars & 0xffff, f"ori r3,r3,0x{dollars & 0xffff:x}   ${dollars:,}"),
                     (0x4e800020, "blr")]
    return code + [(0x38600000, "li r3,0           another row: none (the game asks for none)"),
                   (0x4e800020, "blr")]


STAGE_X = (
    (0x4a73b0, 0xf821ff81, 0x48000000 | (0x4a7240 - 0x4a73b0) & 0x03fffffc,
     "the lowest / highest rookie salary (0x4a73b0, was stdu): b 0x4a7240, the same table (rows 3 / 4)"),
)
STAGE_X_CAVES = (
    (0x4a7240, 0xf821ff61, _cap_cave(),
     "floor, cap, lowest and highest rookie salary by season from CAP_TABLE (was stdu: none of the game's function runs)"),
)
OTHER_INSTRUCTIONS += tuple(a for a, *_ in STAGE_X)
LOWEST_SALARY = CAP_TABLE[3][0]

# Stage Y, Coachella Valley and Henderson in the AHL's menus (lab round 35, 2026-10-19, docs/notes/league-menus.md; the
# owner lifted AGENTS rule 2 for these two slots, on rosters for the patch only). Play Now's team lists (0x128348: rows of
# exhibitionteams, +0x90 the team's league, read from the roster's ttOk.league; +0xa0 the table flag, 1 = a created team)
# let a created team into the Custom list only. A roster for the patch gives custom slots 234 / 235 an AHL Pacific club's
# league fields (league_fit): the gate now lists a created team by its league unless that is Custom (13), where it is
# as the game had it (r22 = +0xa0, r29's low byte = the caller wants no created team, r31 = the list's league,
# 0x100(r1) = +0x90). The five name functions (full name, city, nickname, Select Teams lines 1 / 2) name a created team
# "Custom Team N" (from the first switched-off slot); one in a real league is now named the club way, by its art code (CVF /
# HSK: the texts art/loc.py writes with the team names). The Season's lists are the program's (stage L), not these.
STAGE_Y = (
    (0x128408, 0x57a3063e, 0x2c960001, "team list: cmpwi cr1,r22,1 (was clrlwi r3,r29,24) a created team?"),
    (0x12840c, 0x2c960001, 0x40860028, "team list: bne cr1,0x128434 (was cmpwi cr1,r22,1) no: the league check"),
    (0x128410, 0x2c030000, 0x88610100, "team list: lbz r3,0x100(r1) (was cmpwi r3,0) the team's league"),
    (0x128414, 0x41820008, 0x2c03000d, "team list: cmpwi r3,13 (was beq 0x12841c) Custom?"),
    (0x128418, 0x418601ec, 0x4082001c, "team list: bne 0x128434 (was beq cr1,0x128604) a created team in a real league: "
                                       "the league check, as for a club"),
    (0x12841c, 0x2c1f000d, 0x57a3063e, "team list: clrlwi r3,r29,24 (was cmpwi r31,13) a created Custom team"),
    (0x128420, 0x41820014, 0x2c030000, "team list: cmpwi r3,0 (was beq 0x128434) the caller wants none?"),
    (0x128424, 0x2c960001, 0x408201e0, "team list: bne 0x128604 (was cmpwi cr1,r22,1) yes: left out, as before"),
    (0x128428, 0x2c1f0010, 0x4800000c, "team list: b 0x128434 (was cmpwi r31,16) else the league check, as before"),
    (0x12842c, 0x41820008, NOP, "team list: nop (was beq 0x128434)"),
    (0x128430, 0x418601d4, NOP, "team list: nop (was beq cr1,0x128604)"),
)
NAME_SITES = ((0x2a67d8, "full name"), (0x2a69e0, "city"), (0x2a6ba8, "nickname"), (0x2a6d28, "Select Teams line 1"),
              (0x2a6e6c, "Select Teams line 2"))
_NAME_CAVE = [(0x88610110, "lbz r3,0x110(r1)  the game's own: the table flag (1 = a created team)"),
              (0x88810100, "lbz r4,0x100(r1)  the team's league (r4 is set again before it is read)"),
              (_cmpwi(4, 13), "cmpwi r4,13       Custom?"),
              (0x41820008, "beq +8            yes: as the game does"),
              (_li(3, 0), "li r3,0           a created team in a real league: named the club way")]
STAGE_Y_CAVES = tuple((a, 0x88610110, _NAME_CAVE, f"{what}: a created team in a real league by its art code")
                      for a, what in NAME_SITES)
OTHER_INSTRUCTIONS += tuple(a for a, *_ in STAGE_Y)
# Lab round 41 (2026-10-21, docs/notes/lab-round-41.md): the list builder 0x12865c counts the switched-on rows of
# exhibitionteams (ttOk.NYKk = 1) and 0x128348 then walks team ids 0, 1, 2 ... as many as that count, as if the switched-on
# teams came first. A roster from the game's own has custom slots 222-233 switched off, so the walk ended at 223 and never
# reached Coachella Valley / Henderson (234 / 235): neither Roster Management nor Play Now listed them. At the walk's top
# (0x1283bc, r20 = the id, r25 = the step) an id from 222 on moves on to the next switched-on one, asked the way 0x129c04
# asks the database (exhibitionteams where index = id and active = 1); none left: the walk ends (0x128618). Ids below 222
# (every club, and every season list: 64 keys at most) are walked as before.
LIST_SKIP_FROM, LIST_SKIP_END, LIST_END = 222, 252, 0x128618
SKIP_CALLS = {0x3d7770: "the database", 0xdc302c: "a field by its name's hash", 0xdc0ca4: "a table reference",
              0xdc5378: "a query on the table", 0xdc3814: "field = value", 0xdc4418: "and", 0xdc5394: "where",
              0xdc5c48: "run it", 0xdc3244: "drop a field", 0x17dd0: "drop a query part", 0xdc86a0: "rows found",
              0xdc4e84: "drop the result"}
INDEX_HASH, ACTIVE_HASH = 0xb10552ac, 0x0a249a27        # the game's hashes of "index" / "active" (art/loc.key_hash)


def _call(target):
    return [(_addis(12, 0, target >> 16), f"lis r12,0x{target >> 16:x}"),
            (0x618c0000 | target & 0xffff, f"ori r12,r12,0x{target & 0xffff:x}"),
            (0x7d8903a6, "mtctr r12"),
            (0x4e800421, f"bctrl             0x{target:x}: {SKIP_CALLS[target]}")]


def _field(disp, hash_, name):
    return ([(_addi(3, 1, disp), f"addi r3,r1,0x{disp:x}"),
             (_addis(4, 0, hash_ >> 16), f"lis r4,0x{hash_ >> 16:x}"),
             (0x60840000 | hash_ & 0xffff, f"ori r4,r4,0x{hash_ & 0xffff:x}   \"{name}\""),
             (0x78840020, "clrldi r4,r4,32")] + _call(0xdc302c))


def _skip_cave():
    """The words at the list walk's top: (word, what) with the branches still as labels ('b:label' and so on)."""
    code = [(_cmpwi(20, LIST_SKIP_FROM), f"cmpwi r20,{LIST_SKIP_FROM}       a custom slot?"),
            ('blt:done', "blt done          no: as before"),
            (0xf821fec1, "stdu r1,-0x140(r1) room for the query (as 0x129c04's)"),
            'loop',
            (_cmpwi(20, LIST_SKIP_END), f"cmpwi r20,{LIST_SKIP_END}       past the last team?"),
            ('bge:out', "bge out")]
    code += _call(0x3d7770) + [(_stw(3, 0x110, 1), "stw r3,0x110(r1)")]
    code += _field(0x78, INDEX_HASH, 'index')
    code += [(_addi(3, 1, 0x74), "addi r3,r1,0x74"), (_lwz(4, 0x110, 1), "lwz r4,0x110(r1)"),
             (_addi(5, 1, 0x78), "addi r5,r1,0x78")] + _call(0xdc0ca4)
    code += [(0x3c6001a8, "lis r3,0x1a8"), (0x30a3ac9c, "addic r5,r3,-0x5364"),
             (0x80a50070, "lwz r5,0x70(r5)   exhibitionteams"), (0x7ca507b4, "extsw r5,r5"),
             (_addi(3, 1, 0x70), "addi r3,r1,0x70"), (_addi(4, 1, 0x74), "addi r4,r1,0x74")] + _call(0xdc5378)
    code += _field(0x94, INDEX_HASH, 'index')
    code += [(_addi(3, 1, 0x94), "addi r3,r1,0x94"), (_ori(4, 20), "ori r4,r20,0      index = the id")] + _call(0xdc3814)
    code += [(_stw(3, 0x118, 1), "stw r3,0x118(r1)")]
    code += _field(0xb0, ACTIVE_HASH, 'active')
    code += [(_addi(3, 1, 0xb0), "addi r3,r1,0xb0"), (_li(4, 1), "li r4,1           active = 1")] + _call(0xdc3814)
    code += [(_ori(4, 3), "ori r4,r3,0"), (_lwz(3, 0x118, 1), "lwz r3,0x118(r1)")] + _call(0xdc4418)
    code += [(_ori(4, 3), "ori r4,r3,0"), (_addi(3, 1, 0x70), "addi r3,r1,0x70"), (_li(5, 1), "li r5,1")]
    code += _call(0xdc5394)
    code += [(_ori(4, 3), "ori r4,r3,0"), (_addi(3, 1, 0xcc), "addi r3,r1,0xcc")] + _call(0xdc5c48)
    for disp, target in ((0xb0, 0xdc3244), (0x94, 0xdc3244), (0x70, 0x17dd0), (0x74, 0x17dd0), (0x78, 0xdc3244)):
        code += [(_addi(3, 1, disp), f"addi r3,r1,0x{disp:x}")] + _call(target)
    code += [(_addi(3, 1, 0xcc), "addi r3,r1,0xcc")] + _call(0xdc86a0) + [(_stw(3, 0x118, 1), "stw r3,0x118(r1)")]
    code += [(_addi(3, 1, 0xcc), "addi r3,r1,0xcc")] + _call(0xdc4e84)
    code += [(_lwz(3, 0x118, 1), "lwz r3,0x118(r1)"), (_cmpwi(3, 0), "cmpwi r3,0        switched on?"),
             ('bne:found', "bne found         yes: this id"),
             (_addi(20, 20, 1), "addi r20,r20,1    no: the next"),
             ('b:loop', "b loop"),
             'out',
             (_addi(1, 1, 0x140), "addi r1,r1,0x140"),
             (_addis(12, 0, LIST_END >> 16), f"lis r12,0x{LIST_END >> 16:x}"),
             (0x618c0000 | LIST_END & 0xffff, f"ori r12,r12,0x{LIST_END & 0xffff:x}"),
             (0x7d8903a6, "mtctr r12"),
             (0x4e800420, f"bctr              none left: the walk ends (0x{LIST_END:x})"),
             'found',
             (_addi(1, 1, 0x140), "addi r1,r1,0x140"),
             'done',
             (0x2c130000, "cmpwi r19,0       the game's own")]
    at, labels = 0, {}
    for item in code:
        if isinstance(item, str):
            labels[item] = at
        else:
            at += 4
    out, at = [], 0
    ops = {'blt': 0x41800000, 'bge': 0x40800000, 'bne': 0x40820000, 'b': 0x48000000}
    for item in code:
        if isinstance(item, str):
            continue
        word, what = item
        if isinstance(word, str):
            op, label = word.split(':')
            word = ops[op] | (labels[label] - at) & (0x3fffffc if op == 'b' else 0xfffc)
        out.append((word, what))
        at += 4
    return out


STAGE_Y_CAVES += ((0x1283bc, 0x2c130000, _skip_cave(),
                   "team lists: from id 222 on, only switched-on teams (Coachella Valley / Henderson on a roster from "
                   "the game's own)"),)
# The roster's side: ttOk league, leaguegroup, conferencegroup, divisiongroup of Coachella Valley / Henderson. Every custom
# slot of every roster has CUSTOM_GROUPS; an AHL Pacific club (Bakersfield, slot 33) AHL_PACIFIC.
LEAGUE_FIELDS = ('jjMx', 'lBIi', CONFERENCE, DIVISION)
CUSTOM_GROUPS = (13, 48, 48, 48)
AHL_PACIFIC = (1, 7, 8, 13)
WHL_BC = (11, 31, 32, 34)               # a club of the WHL's B.C. Division (Prince George, slot 204)
LEAGUE_SLOTS = {234: AHL_PACIFIC, 235: AHL_PACIFIC, 251: WHL_BC}        # 251: the Vees (owner, 2026-11-02), in_the_roster

# Stage Z, Be a CHL Pro (2026-11-04, docs/notes/chl-pro-key-127.md; lab rounds 44 / 59, a tester on NHL Legacy Native). A
# career's teams get keys 0, 1, 2 ... (0x12d84c), 7 bits, room 128. With 32 NHL + 32 AHL teams a CHL career filled all 128:
# NHL 0-31, AHL 32-63, All-Stars 64-65, the Top Prospects teams 66-67 (slots 214 / 215), the CHL 68-127. Key 127 (the last
# WHL club) is also a 7-bit key field's "no team", and those careers crashed on the first days. The career setup 0x286e00
# adds the Top Prospects teams last (0x285740: their keys go to settings 0x39 / 0x3a); without that call no key is stored,
# 0x1635b4 gives -16 ("none") as in every career the game makes without them, and a CHL career has 126 teams.
STAGE_Z = (
    (0x28715c, 0x4bffe5e5, NOP, "career setup: nop (was bl 0x285740, the Top Prospects teams): a CHL career keeps 126 "
                                "team keys, none of them 127"),
)
STAGE_Z_CAVES = ()

# yearfirstsigned, yearprodebut, yearufa, yearwaivereligible: read against the league's own year, so year_shift leaves
# them (patch 0.4 moved them 11 later; in Be a GM the game then wrote the league year into every debut year). yearufa is
# then refitted from the shifted birth year (contracts.ufa_fit in patch_roster): birth + 27 on the league's own clock
GAME_YEARS = ('TNEo', 'dCED', 'zKKG', 'YgXB')
PICK_TABLE, PICK_YEAR = 'vaHq', 'dnFq'                  # exhibitiondraftpick.year: the teams' own picks, 2015-2020


TEAM_STAGES = (
    ("NHL Legacy 32 teams A - Be a GM tables (test)", STAGE_A, STAGE_A_CAVES,
     "Room for 32 teams in Be a GM's money records and flags. On its own it changes nothing in the game (lab check)."),
    ("NHL Legacy 32 teams B - League lists of 32 (test)", STAGE_B, STAGE_B_CAVES,
     "Room for 32 NHL teams in the Season's league lists. On its own it changes nothing in the game (lab check)."),
    ("NHL Legacy 32 teams C - team numbers (test)", STAGE_C, STAGE_C_CAVES,
     "NHL teams 0-31, the AHL after them. Only with all other 32-team entries."),
    ("NHL Legacy 32 teams L - AHL of 32 (test)", STAGE_L, STAGE_L_CAVES,
     "All 32 AHL clubs in the Season, Coachella Valley and Henderson too, in the 2026-27 divisions. Only with all other "
     "32-team entries and a roster made for them."),
    ("NHL Legacy 32 teams M - 64 league teams (test)", STAGE_M, STAGE_M_CAVES,
     "Room for 32 NHL and 32 AHL teams in the Season; Seattle's farm team is Coachella Valley, Vegas's Henderson. Only "
     "with all other 32-team entries."),
    ("NHL Legacy 32 teams N - Seattle and Vegas in the NHL (test)", STAGE_NHL, STAGE_NHL_CAVES,
     "Seattle and Vegas join the NHL in Season (Pacific), Utah moves to the Central. Only with all other 32-team entries."),
    ("NHL Legacy 32 teams D - Season simulation of 32 (test)", STAGE_D, STAGE_D_CAVES,
     "Room for 32 teams in the Season's simulator (simulating crashed without it). On its own it changes nothing."),
    ("NHL Legacy 32 teams E - Seattle and Vegas home games (test)", STAGE_E, STAGE_E_CAVES,
     "The calendar keeps Seattle's and Vegas's home games (without it they became an empty All-Star game and the sim "
     "hung). Only with all other 32-team entries."),
    ("NHL Legacy 32 teams F - favourite team list of 32 (test)", STAGE_F, STAGE_F_CAVES,
     "Seattle and Vegas in the favourite-team list (Settings, new profile), and in their place by name in the team "
     "pickers. Only with all other 32-team entries."),
    ("NHL Legacy 32 teams G - Be a GM team picker of 32 (test)", STAGE_G, STAGE_G_CAVES,
     "Room for 32 teams in Be a GM's team picker (Be a GM crashed as it opened). On its own it changes nothing."),
    ("NHL Legacy 32 teams H - staff counts of 32 (test)", STAGE_H, STAGE_H_CAVES,
     "Room for 32 teams in the staff counts (a second Be a GM in one session crashed without it). On its own it changes "
     "nothing."),
    ("NHL Legacy 32 teams I - preseason of 32 (test)", STAGE_I, STAGE_I_CAVES,
     "Room for the preseason games of 32 teams in the season's calendar (Be a GM crashed as it loaded without it). On its "
     "own it changes nothing."),
    ("NHL Legacy 32 teams J - All-Star game (test)", STAGE_J, STAGE_J_CAVES,
     "The All-Star game with 32 teams. EASHL 1 and 2 become the Eastern and Western All-Stars and a team playing "
     "itself in the calendar is the All-Star game. Only with all other 32-team entries and a roster made for them."),
    ("NHL Legacy 32 teams K - draft of 32 (test)", STAGE_K, STAGE_K_CAVES,
     "The draft, the lottery and every year's picks for 32 teams in Season and Be a GM. Only with all other 32-team "
     "entries."),
    ("NHL Legacy 32 teams O - Seattle and Vegas farm work (test)", STAGE_O, STAGE_O_CAVES,
     "Seattle and Vegas call players up from their farm teams and get the new season's roster work (without it a "
     "short-handed Seattle hung the sim). Only with all other 32-team entries."),
    ("NHL Legacy 32 teams P - Seattle and Vegas roster upkeep (test)", STAGE_P, STAGE_P_CAVES,
     "The computer looks after Seattle's and Vegas's rosters and lines every day, re-signs their players and fills "
     "their rosters for a new season (without it a trade left Seattle one player short and Be a GM crashed). Only "
     "with all other 32-team entries."),
    ("NHL Legacy 32 teams Q - game-day moves with one partner club (test)", STAGE_Q, STAGE_Q_CAVES,
     "A game-day roster move between a club and its farm team no longer looks for a second parent club that is not "
     "there (without it season 2 of Be a GM crashed on 2 October). Only with all other 32-team entries."),
    ("NHL Legacy 32 teams R - next season's calendar of 32 (test)", STAGE_R, STAGE_R_CAVES,
     "Every team gets its games in the next season's calendar (without it Anaheim and Calgary had none in season 2 and "
     "leaving Be a GM crashed). Only with all other 32-team entries and a roster made for them."),
    ("NHL Legacy 32 teams S - calendar of 84 games (test)", STAGE_S, STAGE_S_CAVES,
     "Room for the whole 2026-27 calendar, 84 games a team, in the game's roster (without it the last week of the season "
     "was lost). Only with all other 32-team entries and a roster made for them."),
    ("NHL Legacy 32 teams T - team rankings of 32 (test)", STAGE_T, STAGE_T_CAVES,
     "The league's team rankings keep 30 teams each, as the game has room for (without it Be a GM crashed in the "
     "second preseason). Only with all other 32-team entries."),
    ("NHL Legacy 32 teams U - draft picks of 32 a year (test)", STAGE_U, STAGE_U_CAVES,
     "Every draft year keeps its own 224 picks (without it the second draft of Be a GM lost 14 first-round picks and "
     "crashed). Only with all other 32-team entries, in a Season or Be a GM started with it."),
    ("NHL Legacy 32 teams V - Seattle and Vegas call-ups (test)", STAGE_V, STAGE_V_CAVES,
     "The computer counts Seattle's and Vegas's farm players in the farm, so it calls players up when their NHL rosters "
     "run short (without it Vegas fell to 16 players and the sim hung). Only with all other 32-team entries."),
    ("NHL Legacy 32 teams W - Be a Pro with Seattle and Vegas (test)", STAGE_W, STAGE_W_CAVES,
     "Players of Coachella Valley and Henderson are found on their team, and a Be a Pro career with Seattle or Vegas "
     "works (without it a Seattle prospect's career crashed as it loaded). Only with all other 32-team entries."),
    ("NHL Legacy 32 teams X - salary cap by season (test)", STAGE_X, STAGE_X_CAVES,
     "Be a GM's real salary cap. 2026-27 $104.0M (floor $76.9M), 2027-28 $113.5M ($83.9M), 2028-29 $127.5M ($94.35M), "
     "then held. The most one player earns is a fifth of the cap, the lowest and the highest rookie salary as agreed "
     "($850,000 / $1,025,000 in 2026-27). Only with a roster made for it, which holds the real contracts."),
    ("NHL Legacy 32 teams Y - Coachella Valley and Henderson in the AHL (test)", STAGE_Y, STAGE_Y_CAVES,
     "Coachella Valley and Henderson in the AHL's team lists (Play Now, Roster Management), with their own names, not "
     "under Custom Teams. Only with a roster made for it and the team names written by the NHL Legacy Roster Updater."),
    ("NHL Legacy 32 teams Z - Be a CHL Pro (test)", STAGE_Z, STAGE_Z_CAVES,
     "A Be a CHL Pro career no longer crashes in its first days. It leaves out the Top Prospects teams, so its teams fit "
     "the room the game has for them. Only with all other 32-team entries."),
)


# The intro (docs/notes/intro-skip.md; the owner's wish, 2026-10-15). Two entries of their own, each its own switch, apart
# from the year and the 32 teams. Lab round 27 (P1 + P3 + P4, two boots): the game went from its loading picture straight to
# Press Start (no language pick, intro video or legal screen), one press reached the main menu (no autosave notice, no online
# boxes), a Play Now game rendered to the opening faceoff, and a Be a GM save loaded. Press Start itself stays: no game
# word presses it (the Flash screen needs the pad that pressed).
INTRO_ENTRY = "NHL Legacy skip the intro"
INTRO = (
    (0x220a64c, 0x01000000, 0x00000000,
     "CBootflow's full-boot byte (data, the three after it are 0): the game's own quick boot, read at init 0x174ac, "
     "0x406efc, 0x407128, 0x40726c: no language pick (the console's language), no intro video, no legal screen"),
    (0xfb2f24, 0x41820024, 0x48000024,
     "FlowBoot::Start: beq -> b, always step 2: no autosave notice (SaveLoad message 12); autosave stays on"),
)
# Separate, so a player can keep the login at boot. The owner played online through the community server with it on
# (2026-10-18): an online mode signs in when it is opened.
LOGIN_ENTRY = "NHL Legacy no online login at boot"
LOGIN = (
    (0x1cd411c, 0x020e9e10, 0x020e9d80,
     "COnlineSession's vtable slot 25 ShouldDoBootFlowLogin (data): the descriptor of li r3,0; blr (0x20410) instead of "
     "li r3,1 (0x34570); Flash then skips startBootLogin"),
)
# The main menu's news panel (owner, 2026-10-22: every text there says gg.puckpeak.com; docs/notes/promo-texts.md). Signed
# out, RequestDynamicMessages (0x7e98e4 -> 0x7e8cd8) builds the offline messages from the text file, so the program's loose
# copy (loc.PROMO) shows; signed in (the community server) it asks the server, whose news are the game's 2014 texts (the owner's screens,
# 2026-10-22: our loose file read, the server's old lines shown). OSDK's vt[0x98] says "signed in"; its beq to the
# signed-out branch becomes b. Ticked with the patch, apart from the 32 teams. Lab (signed out, as always there): boots to
# the main menu, the panel shows the text file's lines (lab round 45).
NEWS_ENTRY = "NHL Legacy Puck Peak news on the main menu"
NEWS = (
    (0x7e8d58, 0x418204d8, 0x480004d8,
     "RequestDynamicMessages: beq -> b, the signed-out branch also when signed in: the offline messages of the game's "
     "text file (Puck Peak's), never the server's"),
)
INTRO_ENTRIES = (
    (INTRO_ENTRY, INTRO, "Starts at Press Start, then one press to the main menu. No language pick (the game takes RPCS3's "
                         "console language), no intro video, no legal screen, no autosave notice. Works on its own."),
    (LOGIN_ENTRY, LOGIN, "No online login and no online boxes when the game starts. Online play still works (an online "
                         "mode signs in when it is opened). Works on its own."),
    (NEWS_ENTRY, NEWS, "The news panel of the main menu shows the texts of the game's text file (Puck Peak's, with "
                       "Photos, logos and team names) also when signed in online, never the server's news. Works on "
                       "its own."),
)
DATA_WORDS += (0x220a64c, 0x1cd411c)
OTHER_INSTRUCTIONS += (0x220a64c, 0xfb2f24, 0x7e8d58)

# Online play through our own server (private/Multiplayer.txt, docs/notes/multiplayer.md; the owner, 2026-10-25). The words are the
# community's "multiplayer patch" (Kaap0, in RPCS3's own patch.yml), the same for the EU and the NA disc: 1.00 skips a
# crash on the online path, the roster check and the tuner check. Update 1.01 has its own addresses (one program for both
# versions), given by that patch; the game's old words there are not known, so its lines say
# no "was". An entry of its own, ticked by "Set up online" (patchinstall.set_online), apart from the 32 teams.
ONLINE_ENTRY = "NHL Legacy online play"
ONLINE_VERSION = '0.1'
ONLINE_NOTES = ("Lets the game sign in and play online through the Puck Peak server. It skips a crash on the online path, the "
                "online roster check and the tuner check. The words are Kaap0's multiplayer patch. Works on its own.")
ONLINE = (
    (0x8bc4bc, 0x4bfd9d1c, 0x4e800020, "online crash fix: blr, the function returns at once"),
    (0x8bc494, 0x4bfd9adc, 0x4e800020, "online crash fix: blr, the function returns at once"),
    (0x104f0bc, 0x4bfd6578, 0x4bfd6524, "online roster check: the branch goes past the check"),
    (0x211df0, 0x4bff8850, 0x4bff8760, "online tuner check: the branch goes past the check"),
)
ONLINE_101 = (
    (0x87b11c, 0x2c030001, "online roster check (update 1.01's own address)"),
    (0x87a010, 0x2c030001, "online tuner check (update 1.01's own address)"),
)

# The online start (docs/plans/glittery-cuddling-wave.md, docs/notes/online-boot-hook.md; the owner, 2026-10-25: Ready takes both
# players to Select Teams without a press). The main menu's script reads IS_AUTO_SELECT_PLAYNOW_ON_BOOT =
# ION_GameSetup.IsSelectPlayNowOnBoot() once at boot (globaldefines.big); retail answers no. The native method is the thunk
# 0x10624f0: it loads an adapter, calls its vtable slot 0x6c (bctrl at 0x1062514), then 0x965424 turns r3 into the script's
# true / false. The bctrl becomes li r3,1: the script is told yes, and the thunk and the shared slot stay as they are. The entry
# is NOT ticked with the others: the program ticks it for one launch of a lobby's game and unticks it (patchinstall).
ONLINE_START_ENTRY = "NHL Legacy online start"
ONLINE_START_VERSION = '0.1'
ONLINE_START_NOTES = ("Takes the game to online play by itself when the Puck Peak program starts it for a lobby. Do not tick it "
                      "yourself, the program switches it on for one start only.")
ONLINE_START = (
    (0x1062514, 0x4e9e0421, 0x38600000,
     "IsSelectPlayNowOnBoot: li r3,0 instead of the bctrl into the adapter's slot 0x6c: the menu script is told no, "
     "so its second boot branch runs (art/onlinestart.py)"),
)
# Update 1.01: the same thunk, moved by 0x1910 (tools/port_patch.py: the 21 words around it are alike, score 1.00)
ONLINE_START_101 = (
    (0x1063e24, 0x4e9e0421, 0x38600000, "IsSelectPlayNowOnBoot at update 1.01's address: li r3,0 instead of the bctrl"),
)

# Update 1.01 (UPDATE_HASH). Its program is 1.00's with a few functions grown: every place the patch names sits 0 to 0x2030
# bytes later and holds the same instruction (tools/port_patch.py found each by its neighbourhood and wrote patch101.py;
# tools/audit_patch.py checks every word against the 1.01 program). The patch's words are the same, apart from what names
# a place: the hooked addresses, the targets of the game's branches the patch writes or keeps, the addresses our code
# calls (CAVE_ADDRESSES, built with lis + ori / addic) and the function descriptor of the login entry (VALUE_ADDRESSES).
CAVE_DATA = (0x1a7ac9c,)                                # data our code reads: the table list (exhibitionteams, as 0x129c04)
CAVE_ADDRESSES = frozenset(SKIP_CALLS) | {LIST_END} | set(CAVE_DATA)
VALUE_ADDRESSES = (0x1cd411c,)                          # data words whose number is an address


def _target(addr, word):
    """Where the relative branch `word` at `addr` goes, or None (not a relative branch)."""
    op = word >> 26
    if op == 18 and not word & 2:
        disp = word & 0x3fffffc
        return addr + (disp - 0x4000000 if disp & 0x2000000 else disp)
    if op == 16 and not word & 2:
        disp = word & 0xfffc
        return addr + (disp - 0x10000 if disp & 0x8000 else disp)
    return None


def at(addr, version='01.00'):
    """The address in the game version `version` of the 1.00 address `addr`."""
    if version == '01.00':
        return addr
    from .patch101 import ADDRESSES
    return ADDRESSES[addr]


def ported_word(addr, word, version='01.00'):
    """The word at the 1.00 address `addr`, `word` there in 1.00, as it is in `version`: a branch goes to the same place
    (moved), a function descriptor is the one at the moved place; everything else is the same word."""
    if version == '01.00' or addr in DATA_WORDS and addr not in VALUE_ADDRESSES:
        return word
    if addr in VALUE_ADDRESSES:
        return at(word, version)
    target = _target(addr, word)
    if target is None:
        return word
    disp = at(target, version) - at(addr, version)
    if word >> 26 == 18:
        assert -0x2000000 <= disp < 0x2000000, hex(addr)
        return word & 0xfc000003 | disp & 0x3fffffc
    assert -0x8000 <= disp < 0x8000, hex(addr)
    return word & 0xffff0003 | disp & 0xfffc


def ported_code(code, version='01.00'):
    """Our code `code` ([(word, what)]) for `version`: each lis + ori / addi / addic pair that builds one of
    CAVE_ADDRESSES builds the moved address; the rest (the game's instruction it replaces, numbers, the branches inside our
    code) stays."""
    out = list(code)
    if version == '01.00':
        return out
    for i in range(len(code) - 1):
        hi, lo = code[i][0], code[i + 1][0]
        if hi >> 26 != 15 or hi >> 16 & 31 or lo >> 26 not in (12, 14, 24):
            continue
        signed = lo >> 26 != 24
        if (lo >> 16 if signed else lo >> 21) & 31 != hi >> 21 & 31:
            continue
        low = lo & 0xffff
        value = ((hi & 0xffff) << 16) + (low - 0x10000 if signed and low & 0x8000 else low) & 0xffffffff
        if value not in CAVE_ADDRESSES:
            continue
        moved = at(value, version)
        top = (moved + 0x8000 if signed else moved) >> 16
        out[i] = (hi & 0xffff0000 | top, f"{code[i][1]}  (1.01: 0x{moved:x})")
        out[i + 1] = (lo & 0xffff0000 | moved & 0xffff, code[i + 1][1])
    return out


def port_addresses():
    """Every 1.00 address the 1.01 patch needs moved: the hooked ones, the branch targets of the words written and
    replaced, the addresses our code builds, the descriptors in the data words (tools/port_patch.py maps them)."""
    found = {a for a, _ in hooks()} | set(CAVE_ADDRESSES)
    for a, old, new, _ in writes():
        if a in VALUE_ADDRESSES:
            found |= {old, new}
        elif a not in DATA_WORDS:
            found |= {t for t in (_target(a, old), _target(a, new)) if t is not None}
    for a, old in hooks():
        if a not in DATA_WORDS and _target(a, old) is not None:
            found.add(_target(a, old))
    return found


def _hooks():
    """hooks() in 1.00."""
    return ([YEAR_HOOK] + [(a, old) for a, old, *_ in YEAR_LABELS]
            + [(a, old) for _, ws, cs, _ in TEAM_STAGES for a, old, *_ in list(ws) + list(cs)]
            + [(a, old) for _, ws, _ in INTRO_ENTRIES for a, old, *_ in ws])


def writes():
    """The plain word changes: [(address, the game's word, our word, why)]."""
    return (list(YEAR_LABELS) + [w for _, ws, _, _ in TEAM_STAGES for w in ws]
            + [w for _, ws, _ in INTRO_ENTRIES for w in ws])


def caves():
    """The patch's own code: [(hooked address, [(word, what it does)])], run in place of the hooked instruction."""
    return [(YEAR_HOOK[0], list(YEAR_CAVE))] + [(a, list(code)) for _, _, cs, _ in TEAM_STAGES for a, _, code, _ in cs]


def year_of(year):
    """What the patched converter makes of `year` (the code in YEAR_CAVE, for the tests)."""
    lo, span = YEAR_WINDOW
    return year + YEARS_LATER if 0 <= year - lo < span else year


def hooks(version='01.00'):
    """Every game instruction the patch replaces in `version`: [(address, the game's word)] (tools/audit_patch.py checks
    them)."""
    return [(at(a, version), ported_word(a, old, version)) for a, old in _hooks()]


def _write_line(a, old, new, why, version):
    return (f"      - [ be32, 0x{at(a, version):08x}, 0x{ported_word(a, new, version):08x} ]   "
            f"# was 0x{ported_word(a, old, version):08x}: {why}")


def entry_lines(title='BLES02153', version='01.00'):
    """The year entry's lines under its PPU hash (indented two spaces)."""
    return (_head(YEAR_ENTRY, PATCH_VERSION, "The game's years 2010-2025 become 11 years later (2015 becomes 2026). Use it "
                  "with a roster made for it (year-test), whose birth years are on the league's own clock, 11 years earlier.",
                  title, version)
            + [_write_line(a, old, new, why, version) for a, old, new, why in YEAR_LABELS]
            + _cave_lines(YEAR_HOOK[0], YEAR_HOOK[1], YEAR_CAVE, version))


def _head(name, version, notes, title, game='01.00'):
    # plain YAML scalars: ': ' would start a map and '#' a comment (RPCS3 then loads no entry of the file)
    assert ': ' not in name + notes and '#' not in name + notes, name
    return ([f"  {name}:",
             "    Games:",
             "      NHL Legacy:"]
            + [f"        {t}: [ {game} ]" for t in ((title,) if isinstance(title, str) else title)]
            + ["    Author: PuckPeak NHL Legacy Rosters",
               f"    Patch Version: {version}",
               f"    Notes: {notes}",
               "    Patch:"])


def _cave_lines(addr, old, code, version='01.00'):
    # RPCS3 writes the be32 lines that follow a calloc line into the new code, one after another, then adds the jump back
    where = at(addr, version)
    return ([f"      - [ calloc, 0x{where:08x}, {len(code)} ]   # the game's 0x{ported_word(addr, old, version):08x} "
             "goes to our code"]
            + [f"      - [ be32, 0x{where:08x}, 0x{word:08x} ]   # {what}" for word, what in ported_code(code, version)])


def team_entry_lines(stage, title='BLES02153', version='01.00'):
    """One 32-team entry's lines (`stage` from TEAM_STAGES): the plain changes first, then each piece of own code."""
    name, ws, cs, notes = stage
    lines = _head(name, TEAMS_VERSION, notes, title, version)
    lines += [_write_line(a, old, new, why, version) for a, old, new, why in ws]
    for a, old, code, _ in cs:
        lines += _cave_lines(a, old, code, version)
    return lines


def intro_entry_lines(entry, title='BLES02153', version='01.00'):
    """One intro entry's lines (`entry` from INTRO_ENTRIES)."""
    name, ws, notes = entry
    return (_head(name, INTRO_VERSION, notes, title, version)
            + [_write_line(a, old, new, why, version) for a, old, new, why in ws])


def online_entry_lines(title='BLES02153', version='01.00'):
    """The online entry's lines: 1.00's four words with the game's own, update 1.01's two as that patch gives them."""
    lines = _head(ONLINE_ENTRY, ONLINE_VERSION, ONLINE_NOTES, title, version)
    if version == '01.00':
        return lines + [f"      - [ be32, 0x{a:08x}, 0x{new:08x} ]   # was 0x{old:08x}: {why}" for a, old, new, why in ONLINE]
    return lines + [f"      - [ be32, 0x{a:08x}, 0x{new:08x} ]   # {why}" for a, new, why in ONLINE_101]


def online_start_lines(title='BLES02153', version='01.00'):
    """The online start entry's lines: the word at 1.00's address, or at update 1.01's."""
    lines = _head(ONLINE_START_ENTRY, ONLINE_START_VERSION, ONLINE_START_NOTES, title, version)
    words = ONLINE_START if version == '01.00' else ONLINE_START_101
    return lines + [f"      - [ be32, 0x{a:08x}, 0x{new:08x} ]   # was 0x{old:08x}: {why}" for a, old, new, why in words]


def hash_of(title, version='01.00'):
    """The PPU hash RPCS3 knows the game version `version` of `title` by (1.01: one program for EU and NA)."""
    return HASHES[title] if version == '01.00' else UPDATE_HASH


def _blocks(titles, versions, lines_of):
    # one block per PPU hash: 1.01's names both versions in each entry's Games (YAML allows a key once)
    blocks = []
    for version in versions:
        groups = {}
        for title in titles:
            groups.setdefault(hash_of(title, version), []).append(title)
        note = ["  # update 1.01: the same patch at 1.01's addresses (the comments name 1.00's)"] if version != '01.00' else []
        for hash_, group in groups.items():
            lines = lines_of(group[0] if len(group) == 1 else tuple(group), version)
            blocks.append(f"PPU-{hash_}:\n" + "\n".join(note + lines) + "\n")
    return "Version: 1.2\n\n" + "\n".join(blocks)


def patch_text(teams=False, titles=tuple(HASHES), versions=('01.00',)):
    """The patch file (RPCS3's patch format 1.2), ready to import into RPCS3 (Manage > Game Patches: drop it on the window):
    for each game version in `titles` (EU, NA) and `versions` under its own PPU hash, the year entry, with `teams` the
    32-team entries, then the intro entries (each ticked on its own, or not)."""
    def lines_of(title, version):
        lines = entry_lines(title, version)
        for stage in TEAM_STAGES if teams else ():
            lines += [""] + team_entry_lines(stage, title, version)
        for entry in INTRO_ENTRIES:
            lines += [""] + intro_entry_lines(entry, title, version)
        return lines
    return _blocks(titles, versions, lines_of)


# What the program installs for players (patchinstall.py): the year entry and every 32-team stage as ONE entry, one switch
# in RPCS3's Game Patches window, the same words as the lab's entries in the same order (tests); the intro entries as they are.
PLAYER_ENTRY = "NHL Legacy 32 teams and the year 2026"
PLAYER_NOTES = ("Seattle and Vegas in Season and Be a GM (32 NHL and 32 AHL teams, 84 games, the All-Star game, the draft "
                "of 32, the real salary cap) and the year 2026. Only with a roster made for it by the NHL Legacy "
                "Roster Updater (it opens no other roster). Season and Be a GM saves made with it need it.")


def player_entry_lines(title='BLES02153', version='01.00'):
    """The players' 32-team entry: the year entry's changes, then every TEAM_STAGES entry's, in that order."""
    lines = _head(PLAYER_ENTRY, TEAMS_VERSION, PLAYER_NOTES, title, version)
    head = len(lines)                   # every entry's head has the same lines; its changes follow
    lines += entry_lines(title, version)[head:]
    for stage in TEAM_STAGES:
        lines += team_entry_lines(stage, title, version)[head:]
    return lines


def player_patch_text(titles=tuple(HASHES), versions=VERSIONS):
    """The patch file the program installs: for each version in `titles` and game version in `versions` under its PPU
    hash, PLAYER_ENTRY, the intro entries and the online entry (patchinstall.py ticks them)."""
    def lines_of(title, version):
        lines = player_entry_lines(title, version)
        for entry in INTRO_ENTRIES:
            lines += [""] + intro_entry_lines(entry, title, version)
        lines += [""] + online_entry_lines(title, version)
        lines += [""] + online_start_lines(title, version)
        return lines
    return _blocks(titles, versions, lines_of)


def year_shift(R, stale):
    """Turn the roster `R` (as this program writes it) into the patched way, in place: birth years as the real year
    - 1911, on the league's own clock (2015 = 2026; records still in the game's way found with donors.real_birth_year when
    `stale`), and the teams' draft picks 11 years later (2026-2031, for Play Now's trade screen; a Season makes its own).
    The contract and debut years (GAME_YEARS) stay: the game reads them against the league's own year too. Draft years
    are real years and stay. Returns how many records changed."""
    P = R.P
    changed = 0
    for prow in range(P.cur_rec):
        before = P.get(prow, 'dnFq')
        born = real_birth_year(P, prow, stale) - 1900 - YEARS_LATER
        P.set(prow, 'dnFq', min(max(born, 0), P.field('dnFq').mask))
        changed += before != P.get(prow, 'dnFq')
    T = R.f[PICK_TABLE]
    for i in range(T.cur_rec):
        T.set(i, PICK_YEAR, min(T.get(i, PICK_YEAR) + YEARS_LATER, T.field(PICK_YEAR).mask))
    return changed


def mend_years(R):
    """Write every record's real birth year (donors.real_birth_year) in this roster family's way (real - 1910), in place:
    the records still in the game's year - 1900 read right from now on. A roster made for the patch is built from mended
    years (pipeline.build), so that updating it again (unshift) starts from what its first update saw. Returns how
    many records changed."""
    P, changed = R.P, 0
    for prow in range(P.cur_rec):
        before = P.get(prow, 'dnFq')
        P.set(prow, 'dnFq', min(max(real_birth_year(P, prow, True) - 1910, 0), P.field('dnFq').mask))
        changed += before != P.get(prow, 'dnFq')
    return changed


def is_patch_roster(R):
    """Was the roster `R` made for the game patch (its save section has the patched game's length, section_fit)?"""
    return R.f.section_size == SECTION_SIZE


def unshift(R):
    """Undo year_shift on the patch roster `R`, in place, so it can be updated again: birth years back to this roster
    family's way (real - 1910; year_shift wrote real - 1911 and had already mended the game's stale records, so
    donors.real_birth_year reads them as they are), the teams' picks 11 years back (shifting twice put them in 2037-2042
    and every new Be a GM crashed, lab round 18). The tables and the section keep the patch's room."""
    P = R.P
    for prow in range(P.cur_rec):
        P.set(prow, 'dnFq', min(P.get(prow, 'dnFq') + YEARS_LATER - 10, P.field('dnFq').mask))
    T = R.f[PICK_TABLE]
    for i in range(T.cur_rec):
        T.set(i, PICK_YEAR, max(T.get(i, PICK_YEAR) - YEARS_LATER, 0))


def _joined(*groups):
    """{slot: fields} of several such dicts, a slot's fields joined (Seattle / Vegas are in two)."""
    out = {}
    for group in groups:
        for slot, fields in group.items():
            out[slot] = out.get(slot, ()) + tuple(f for f in fields if f not in out.get(slot, ()))
    return out


# The team fields patch_roster writes (farm_fit, divisions_fit, all_star_fit, league_fit): {slot: fields}. unpatch_roster
# puts the game's own values back. (Until 2026-10-19 Seattle's / Vegas's farm link replaced their names and divisions
# here, so a turned-back roster kept them: lab round 36.)
PATCHED_TEAM_FIELDS = _joined(
    {n: (CONFERENCE, DIVISION, 'JkmY', 'ITNQ', 'nnsx') for n in TEAMS_2026},
    {n: (AFFILIATE,) for n in NO_FARM},
    {slot: (CONFERENCE, DIVISION) for slot in FARM_SLOTS if slot < 62},
    {slot: ('JkmY', 'ITNQ', 'nnsx', CONFERENCE, DIVISION) + tuple(ALL_STAR_RINK[slot]) for slot in ALL_STAR_LOOK},
    {slot: LEAGUE_FIELDS for slot in LEAGUE_SLOTS},
)


def unpatch_roster(R, ref):
    """Turn the patch roster `R` (already unshift-ed) back into a roster for the unpatched game, in place, with the game's
    own roster `ref` (a Roster: restore.default_slot) giving what the patch replaced: the calendars (nhlschedule,
    favoriteteamschedule, the next seasons', the AHL's) and their room, the save section's length, the team fields of
    PATCHED_TEAM_FIELDS (divisions, Seattle's / Vegas's farm links, the All-Star places), the rights' five bits
    (rights_narrow: Vegas's go). The players, their other rights (the AHL step gives the same ones) and their deals
    (pipeline.build rescales the money) stay."""
    from .restore import copy_calendar
    copy_calendar(R, ref)
    for tag in (FUTURE_TABLE, FARM_TABLE):
        T, D = R.f[tag], ref.f[tag]
        for i in range(T.cur_rec):
            for f in T.fields:
                T.set(i, f, 0)
        T.cur_rec = 0
        for i in range(D.cur_rec):
            T.add_record({f: D.get(i, f) for f in D.fields})
    for tag in CALENDAR_TABLES + (FARM_TABLE, schedule.FAVOURITE):
        if R.f[tag].max_rec > ref.f[tag].max_rec:
            R.f[tag].shrink(ref.f[tag].max_rec)
    for slot, fields in PATCHED_TEAM_FIELDS.items():
        for f in fields:
            R.T.set(slot, f, ref.T.get(slot, f))
    rights_narrow(R)
    R.f.resize(ref.f.section_size)


def unshifted(raw):
    """The roster save `raw` (bytes) as this program reads it: a roster made for the patch unshifted and unleagued, any
    other as it is."""
    from .roster import Roster
    R = Roster(raw)
    if not is_patch_roster(R):
        return raw
    unshift(R)
    unleague(R)
    unart(R)
    return R.f.build()


def check_years(R, season_year):
    """Problems of a roster made for the patch (a list of texts, empty when right): the players' middle age 22 to 32 in
    the season, counted as the game counts it (from the league's own year, season_year - 11, and the stored birth year),
    the teams' picks for the season and the five after it (the birth years are set, not moved, so only these years show
    a roster that was shifted twice: lab round 18 started from a patched roster, its picks were for 2037-2042 and every
    new Be a GM crashed at 0x381c24). Single odd ages are the roster's own (the legends, a few placeholder juniors)."""
    P = R.P
    problems = []
    league_year = season_year - YEARS_LATER
    ages = sorted(league_year - (P.get(prow, 'dnFq') + 1900) for prow in range(P.cur_rec)
                  if P.get(prow, 'NYKk') and P.get(prow, 'RMbQ') and 'ZZ' not in P.get(prow, 'RMbQ'))
    if ages and not 22 <= ages[len(ages) // 2] <= 32:
        problems.append(f"the players' middle age would be {ages[len(ages) // 2]}")
    T = R.f[PICK_TABLE]
    odd = sorted({T.get(i, PICK_YEAR) + 1900 for i in range(T.cur_rec)} - set(range(season_year, season_year + 6)))
    if odd:
        problems.append(f"draft picks of other years than {season_year}-{season_year + 5}: {odd}")
    return problems


def farm_fit(R, games):
    """Make the roster `R` (as this program writes it) fit the patched Season's farm league (stages L and M), in place:
    Seattle and Vegas name no farm club (the patch gives them Coachella Valley and Henderson; the roster cannot name those),
    the AHL clubs in slots 32-61 are filed in their 2026-27 divisions (FARM_DIVISIONS), and the farm calendar (ahlschedule,
    teams by farm place) holds `games`, the AHL's regular season as the data pack has it ([date, home slot, away slot]),
    in date order. Returns the number of games."""
    import datetime
    T, A = R.T, R.f[FARM_TABLE]
    for n in NO_FARM:
        T.set(n, AFFILIATE, 0)
    for division, conference, _name, slots in FARM_DIVISIONS:
        for slot in slots:
            if slot < 62:                               # Coachella's and Henderson's groups are their league's
                T.set(slot, CONFERENCE, conference)
                T.set(slot, DIVISION, division)
    rows = sorted(games, key=lambda g: g[0])               # a stable sort: a day's games stay in the feed's order
    if len(rows) > A.max_rec:
        raise ValueError(f"{len(rows)} farm games do not fit in the farm calendar ({A.max_rec})")
    for i in range(A.cur_rec):                          # the old rows would stay behind the new ones otherwise
        for f in A.fields:
            A.set(i, f, 0)
    A.cur_rec = 0
    for i, (date, home, away) in enumerate(rows):
        d = datetime.date.fromisoformat(date)
        A.add_record({f: 0 for f in A.fields} | {FARM_ROW['index']: i, FARM_ROW['day']: d.day - 1,
                                                  FARM_ROW['month']: d.month - 1, FARM_ROW['home']: FARM_PLACE[home],
                                                  FARM_ROW['away']: FARM_PLACE[away]})
    return len(rows)


def check_farm(R):
    """Problems of a roster made for the patched Season's farm league (texts, empty when right): every NHL team but Seattle
    and Vegas names its own farm club in slots 32-61, Seattle and Vegas none, the AHL clubs in their 2026-27 divisions,
    the farm calendar's places 0-31 in date order, every place with games, nobody twice a day or against himself."""
    T, A = R.T, R.f[FARM_TABLE]
    farm = {n: T.get(n, AFFILIATE) - 1 for n in range(32)}
    problems = [f"NHL slot {n} names farm slot {farm[n]} (the patch gives it {FARM_SLOTS[n]})"
                for n in NO_FARM if farm[n] != -1]
    clubs = [f for n, f in farm.items() if n not in NO_FARM]
    problems += [f"NHL slot {n} has its farm team in slot {f}" for n, f in farm.items()
                 if n not in NO_FARM and not 32 <= f < 62]
    problems += [f"farm slot {f} serves {clubs.count(f)} NHL teams" for f in sorted(set(clubs)) if clubs.count(f) > 1]
    for division, conference, name, slots in FARM_DIVISIONS:
        problems += [f"AHL slot {s} is in group {T.get(s, CONFERENCE)} / {T.get(s, DIVISION)}, not the {name}"
                     for s in slots if s < 62 and (T.get(s, CONFERENCE), T.get(s, DIVISION)) != (conference, division)]
    seen, last, games = set(), (-1, -1), {}
    for i in range(A.cur_rec):
        h, a = A.get(i, FARM_ROW['home']), A.get(i, FARM_ROW['away'])
        month, day = A.get(i, FARM_ROW['month']), A.get(i, FARM_ROW['day'])
        order = ((month - 8) % 12, day)
        if A.get(i, FARM_ROW['index']) != i or order < last or h == a or max(h, a) >= len(FARM_SLOTS):
            problems.append(f"farm calendar row {i}: {h} against {a} on {month + 1}/{day + 1}")
        for t in (h, a):
            if (month, day, t) in seen:
                problems.append(f"farm place {t} plays twice on {month + 1}/{day + 1}")
            seen.add((month, day, t))
            games[t] = games.get(t, 0) + 1
        last = order
    problems += [f"farm place {p} ({FARM_SLOTS[p]}) has no games" for p in range(len(FARM_SLOTS)) if p not in games]
    return problems[:20]


def _farm_of(R):
    """{NHL slot: its farm club's slot} in the patched Season: the roster's own for 0-29, Coachella / Henderson for 30 / 31."""
    return {n: FARM_SLOTS[n] if n in NO_FARM else R.T.get(n, AFFILIATE) - 1 for n in range(32)}


def _kind(P, prow):
    pos = P.get(prow, 'aljv')
    return 'G' if pos == 4 else 'D' if pos == 3 else 'F'


def rights_fit(R, farm_teams, season_year):
    """Make the roster `R` (as this program writes it) give every NHL team of the patched Season its farm club's players,
    in place: the players the data pack marks as on an NHL contract (`farm_teams`: the pack's AHL teams, {'slot',
    'players'}) hold their organisation's rights (the list's `org`; a list without it: the farm club's parent's) and a
    two-way deal, as the AHL step gives them (clubs._rights, _nhl_contract); Vegas's too (six bits: rights_wide). Returns
    the number of players whose rights changed."""
    from .contracts import REAL as REAL_MONEY
    from .leagues.clubs import two_way
    from .matching import norm
    P = R.P
    parent = {f: n for n, f in _farm_of(R).items() if _holds(P, n)}
    changed = 0
    for team in farm_teams:
        nhl = parent.get(team['slot'])
        if nhl is None:
            continue
        signed = {}                     # (last, first initial) -> the NHL slot that holds his rights
        for p in team['players']:
            org = L.API_TO_SLOT.get(p.get('org')) if 'org' in p else nhl if p.get('nhl_contract') else None
            if org is not None and _holds(P, org):
                signed[(norm(p['last']), norm(p['first'])[:1])] = org
        for _i, prow, *_ in R.team_roster(team['slot']):
            org = signed.get((norm(P.get(prow, 'RMbQ')), norm(P.get(prow, 'PedH'))[:1])) if prow is not None else None
            if org is not None and P.get(prow, RIGHTS) != org + 1:
                P.set(prow, RIGHTS, org + 1)
                two_way(P, prow, season_year, REAL_MONEY)
                changed += 1
    # a farm club still short of its NHL team's players (the game's own roster: its 2014 farm players hold nobody's
    # rights, and the data pack's contract players may be up with the NHL team): the youngest of its players who hold
    # nobody's rights sign a two-way deal with that team
    for farm, nhl in sorted(parent.items()):
        held = {k: 0 for k in FARM_DEPTH}
        free = {k: [] for k in FARM_DEPTH}
        for _i, prow, *_ in R.team_roster(farm):
            if prow is None:
                continue
            if P.get(prow, RIGHTS) == nhl + 1 and P.get(prow, 'GDhI') and P.get(prow, 'dhKk'):
                held[_kind(P, prow)] += 1
            elif not P.get(prow, RIGHTS):
                free[_kind(P, prow)].append(prow)
        for k, n in FARM_DEPTH.items():
            for prow in sorted(free[k], key=lambda r: (-P.get(r, 'dnFq'), r))[:max(0, n - held[k])]:
                P.set(prow, RIGHTS, nhl + 1)
                two_way(P, prow, season_year, REAL_MONEY)
                changed += 1
    return changed


def _holds(P, nhl):
    """Can the roster's proteam hold NHL slot `nhl`'s rights (stored as nhl + 1)?"""
    return nhl + 1 < 1 << P.field(RIGHTS).bits


def check_rights(R):
    """Problems of a roster made for the patched Season (texts, empty when right): every NHL team's farm club holds at
    least FARM_DEPTH forwards / defencemen / goalies under that team's rights and a contract, so that a computer GM can
    call one up for a hurt player (Vegas from Henderson too), and the roster's proteam has the six bits the patch's db
    files describe (RIGHTS_BITS)."""
    P = R.P
    if P.field(RIGHTS).bits != RIGHTS_BITS:
        return [f"player rights ({RIGHTS_TABLE}.{RIGHTS}) have {P.field(RIGHTS).bits} bits, the patched game reads "
                f"{RIGHTS_BITS}"]
    problems = []
    for nhl, farm in _farm_of(R).items():
        held = {k: 0 for k in FARM_DEPTH}
        for _i, prow, *_ in R.team_roster(farm):
            if prow is not None and P.get(prow, RIGHTS) == nhl + 1 and P.get(prow, 'GDhI') and P.get(prow, 'dhKk'):
                held[_kind(P, prow)] += 1
        short = [f"{held[k]} {k} (at least {n})" for k, n in FARM_DEPTH.items() if held[k] < n]
        if short:
            problems.append(f"NHL slot {nhl}'s farm club (slot {farm}) holds only " + ", ".join(short) + " of its players")
    return problems[:20]


def rights_wide(R):
    """Give the roster `R` (made for the game patch) six-bit rights (RIGHTS_BITS), in place, so that Vegas (32) fits:
    the fields after proteam move along (tdb.Table.widen; a record has 28 bits to spare). The patch's db files describe
    the same (META_TEAMS). Returns whether it changed."""
    if R.P.field(RIGHTS).bits >= RIGHTS_BITS:
        return False
    R.P.widen(RIGHTS, RIGHTS_BITS)
    return True


def rights_narrow(R, bits=5):
    """Give the roster `R` the unpatched game's five-bit rights again, in place: a player whose rights do not fit
    (Vegas's, 32) holds nobody's, as the AHL step leaves him on a roster for the unpatched game (clubs._rights); his deal
    stays. Returns the number of players who lost rights."""
    P = R.P
    if P.field(RIGHTS).bits <= bits:
        return 0
    lost = 0
    for prow in range(P.cur_rec):
        if P.get(prow, RIGHTS) >= 1 << bits:
            P.set(prow, RIGHTS, 0)
            lost += 1
    P.narrow(RIGHTS, bits)
    return lost


# Every later season's calendar is the 2026-27 one a week later (lab round 27, 2026-10-15). The game's year turns on
# 11 September every season (the year-span league tasks start then), and the preseason starts 17 days before the
# opener (0x284b80, in 0x28470c). The real calendar opens on 29 September, so season 2's preseason started on
# 12 September 2027: its first game day still ran in the old year and was not counted, every team counted 6 of its 7
# preseason games, and the preseason roster routine 0x28b75c never reached its final cut (the commit 0x1ca618 mode 7
# after the second-to-last game). The random preseason rosters stayed all season: stars on the farm. The game's own
# calendar opened on 8 October. A later season keeps the template's weekdays and moves it at most 3 days either way
# (0x283800, 0x283a2c), so a week later opens on 3-9 October and the preseason starts on 16 September or later.
# Season 1 plays nhlschedule with the real dates; a Be a GM starts before its preseason.
FUTURE_DAYS = 7


def future_rows(rows):
    """The calendar rows `rows` ((month, day, home, away), month and day from 0) FUTURE_DAYS later, in the same order.
    The dates are read as the 2026-27 season (no 29 February, so no game moves onto it), or as 2027-28 when a game is
    on 29 February (the game's own 2015-16 calendar)."""
    first = 2027 if any(month == 1 and day == 28 for month, day, *_ in rows) else 2026
    out = []
    for when, home, away in schedule.dated(rows, first):
        when += datetime.timedelta(days=FUTURE_DAYS)
        out.append((when.month - 1, when.day - 1, home, away))
    return out


def future_fit(R):
    """Copy the calendar (nhlschedule, all 32 teams and the All-Star row) FUTURE_DAYS later (future_rows) into
    nhlfutureschedule (FUTURE_TABLE) of the roster `R`, in place: every later season's calendar is made from it
    (stage R), and the game's own one has 30 teams."""
    rows = future_rows(schedule.read(R))
    F = R.f[FUTURE_TABLE]
    if F.max_rec < schedule.PATCH_ROWS:
        F.grow(schedule.PATCH_ROWS)
    if len(rows) > F.max_rec:
        raise ValueError(f"{len(rows)} games do not fit in the next seasons' calendar ({F.max_rec})")
    for i in range(F.cur_rec):                          # the old rows would stay behind the new ones otherwise
        for field in schedule.ROW.values():
            F.set(i, field, 0)
    F.cur_rec = 0
    if F.max_rec > schedule.PATCH_ROWS:                 # a roster the patched game saved itself had room for 1,459
        F.shrink(schedule.PATCH_ROWS)
    for i, (month, day, home, away) in enumerate(rows):
        F.add_record({schedule.ROW['round']: 0, schedule.ROW['status']: 0, schedule.ROW['day']: day,
                      schedule.ROW['month']: month, schedule.ROW['index']: i, schedule.ROW['home']: home,
                      schedule.ROW['away']: away})


def check_future(R):
    """Problems of a roster's next seasons' calendar for the patch (texts, empty when right): nhlfutureschedule holds
    the same games as nhlschedule, row for row, FUTURE_DAYS later (future_rows)."""
    if schedule.read(R, FUTURE_TABLE) != future_rows(schedule.read(R)):
        return [f"the next seasons' calendar (nhlfutureschedule) is not the 32-team calendar {FUTURE_DAYS} days later"]
    F = R.f[FUTURE_TABLE]
    return [f"next seasons' calendar row {i} is numbered {F.get(i, schedule.ROW['index'])}" for i in range(F.cur_rec)
            if F.get(i, schedule.ROW['index']) != i][:5]


def section_fit(R):
    """Give the roster `R`'s save section the length the patched game reads (SECTION_SIZE, stage S), in place."""
    R.f.resize(SECTION_SIZE)


def check_games(R):
    """Problems of a roster's calendar for the patch (texts, empty when right): each of the 32 NHL teams plays
    schedule.PATCH_PER_TEAM games, half of them at home, the calendar tables have the room stage S gives the game
    (CALENDAR_TABLES: schedule.PATCH_ROWS) and the save's section its length (SECTION_SIZE)."""
    problems = [f"schedule table {tag} has room for {R.f[tag].max_rec} rows, not {schedule.PATCH_ROWS}"
                for tag in CALENDAR_TABLES if R.f[tag].max_rec != schedule.PATCH_ROWS]
    if R.f.section_size != SECTION_SIZE:
        problems.append(f"the roster's save section has {R.f.section_size} bytes, not {SECTION_SIZE} "
                        "(the patched game takes it for a damaged save)")
    games, home = {}, {}
    for _m, _d, h, a in schedule.read(R):
        if h != a:
            games[h] = games.get(h, 0) + 1
            games[a] = games.get(a, 0) + 1
            home[h] = home.get(h, 0) + 1
    for team in range(32):
        if games.get(team) != schedule.PATCH_PER_TEAM or home.get(team) != schedule.PATCH_PER_TEAM // 2:
            problems.append(f"team {team} plays {games.get(team, 0)} games, {home.get(team, 0)} at home, "
                            f"not {schedule.PATCH_PER_TEAM}, {schedule.PATCH_PER_TEAM // 2}")
    return problems[:20]


def divisions_fit(R):
    """File Utah, Seattle and Vegas in their 2026-27 divisions (TEAMS_2026) and give them their names (NAMES_2026) in the
    roster `R`, in place."""
    for n, division in TEAMS_2026.items():
        R.T.set(n, DIVISION, division)
        R.T.set(n, CONFERENCE, DIVISIONS[division])
    for n, (full, short, abbr) in NAMES_2026.items():
        R.T.set(n, 'JkmY', full)
        R.T.set(n, 'ITNQ', short)
        R.T.set(n, 'nnsx', abbr)


def league_of(R, slot):
    """The league fields (LEAGUE_FIELDS) of team `slot` in the roster `R`."""
    return tuple(R.T.get(slot, f) for f in LEAGUE_FIELDS)


def in_the_roster(R, slots):
    """`slots` without the Vees' when the roster `R` has someone else there (layout.is_vees)."""
    return [slot for slot in slots if slot != L.VEES or L.is_vees(R.T)]


def league_fit(R):
    """Put Coachella Valley and Henderson in the AHL's Pacific and the Vees in the WHL's B.C. Division (LEAGUE_SLOTS) in the
    roster `R` (stage Y), in place. Returns how many teams changed."""
    changed = 0
    for slot in in_the_roster(R, LEAGUE_SLOTS):
        changed += league_of(R, slot) != LEAGUE_SLOTS[slot]
        for f, value in zip(LEAGUE_FIELDS, LEAGUE_SLOTS[slot]):
            R.T.set(slot, f, value)
    return changed


def unleague(R):
    """Undo league_fit on the roster `R`, in place: Coachella Valley, Henderson and the Vees back in the Custom league, where
    the builder, the names and the pictures expect them (and the unpatched game lists them). Returns how many teams changed."""
    changed = 0
    for slot in in_the_roster(R, LEAGUE_SLOTS):
        if league_of(R, slot) == LEAGUE_SLOTS[slot]:
            for f, value in zip(LEAGUE_FIELDS, CUSTOM_GROUPS):
                R.T.set(slot, f, value)
            changed += 1
    return changed


# --- art ids of their own (0.50.4; lab round 48, docs/notes/lab-round-48.md) -------------------------------------------
CREATED = 'BERR'            # ttOk `table`: 1 = a created team (the game draws it from the create-a-team files)
ROW_ART, ROW_TEAM = 'LQDG', 'gXCm'      # wgjx (stockteamjerseys): teamartid, teamid


def art_rows(R, art):
    """The rows of table wgjx (stockteamjerseys) for art id `art`: [{field: value}], in the table's order."""
    W = R.f['wgjx']
    return [{f: W.get(i, f) for f in W.fields} for i in range(W.cur_rec) if W.get(i, ROW_ART) == art]


ROW_WORD, ROW_DEFAULT, ROW_VARIANT = 'gZuU', 'MSFy', 'TccF'     # wgjx locstring, isdefault, variant
ALTERNATE_WORD = 2                          # locstring of an Alternate version (art/looks.py ALTERNATE)


def _club_rows_missing(R):
    """[(slot, art, row)]: the donor rows art_fit still has to add, in the order it adds them."""
    out = []
    for slot in in_the_roster(R, L.CLUB_ART):
        art = L.CLUB_ART[slot]
        donor, variants = L.CLUB_DONOR[slot]
        have = {row[ROW_VARIANT] for row in art_rows(R, art)}
        out += [(slot, art, row) for row in art_rows(R, donor) if row[ROW_VARIANT] in variants and row[ROW_VARIANT] not in have]
    return out


def make_room(R, need, dropped=None):
    """Free `need` rows of table wgjx (it holds W.max_rec, 749) for art_fit by taking out Alternate rows this program added
    for this season's thirds (art/looks.alternate_rows, 0.92.0). They are the run of Alternate rows (locstring 2, not a
    default) at the very end of the table, each one of a team whose own rows come earlier; the last one added goes first (the
    clubs of the higher slots before the NHL). Needed by a roster an older version filled: 0.92.0 left room for 4 rows
    (Coachella Valley, Henderson), the Vees need 2 more since 0.95.0 (a tester's "wgjx: table full (749)",
    docs/notes/wgjx-full.md). Deterministic. Returns how many rows went; `dropped` (a list) gets their (team slot, art id,
    variant)."""
    W = R.f['wgjx']
    short = need - (W.max_rec - W.cur_rec)
    if short <= 0:
        return 0
    clubs = set(L.CLUB_ART.values())
    end = W.cur_rec
    while end > 0 and W.cur_rec - end < short:
        i = end - 1
        art = W.get(i, ROW_ART)
        if (W.get(i, ROW_WORD) != ALTERNATE_WORD or W.get(i, ROW_DEFAULT) or art in clubs
                or not any(W.get(j, ROW_ART) == art for j in range(i))):
            break
        end = i
    gone = [(W.get(i, ROW_TEAM), W.get(i, ROW_ART), W.get(i, ROW_VARIANT)) for i in range(W.cur_rec - 1, end - 1, -1)]
    for i in range(end, W.cur_rec):
        for f in W.fields:
            W.set(i, f, 0)
    W.cur_rec = end
    if dropped is not None:
        dropped += gone
    return len(gone)


def art_fit(R, dropped=None):
    """Give Coachella Valley, Henderson and the Vees the art ids of their own (layout.CLUB_ART) in the roster `R` for the patched
    game, in place: the created-team flag off and the jersey rows of their donor club (layout.CLUB_DONOR: the donor's rows
    for the versions listed there) under their art id and slot. Their files are art/clubart.py's. When the table has no room
    for those rows, this season's Alternate rows an older update added make it (`make_room`; `dropped` gets them); a roster
    whose own rows leave none still cannot take them (a LayoutError that says so). Returns how many teams changed."""
    W, changed = R.f['wgjx'], 0
    missing = _club_rows_missing(R)
    make_room(R, len(missing), dropped)
    if len(missing) > W.max_rec - W.cur_rec:
        raise L.LayoutError(f"This roster's list of jersey versions is full ({W.cur_rec} of {W.max_rec}), so there is no "
                            "room for Coachella Valley's, Henderson's and the Penticton Vees' jerseys the 32-team game "
                            "needs. Update another roster, or unpatch the game in Game patch and update this one.")
    for slot, art, row in missing:
        W.add_record(dict(row, **{ROW_ART: art, ROW_TEAM: slot}))
        changed += 1
    for slot in in_the_roster(R, L.CLUB_ART):
        art = L.CLUB_ART[slot]
        if R.T.get(slot, 'artid') != art or R.T.get(slot, CREATED) != 0:
            R.T.set(slot, 'artid', art)
            R.T.set(slot, CREATED, 0)
            changed += 1
    return changed


def unart(R):
    """Undo art_fit on the roster `R`, in place: their create-a-team art ids (layout.OWN_ART) and the flag back on, their
    rows out of wgjx (they were added last). Returns how many teams changed."""
    changed = 0
    for slot, art in L.CLUB_ART.items():
        if R.T.get(slot, 'artid') == art:
            R.T.set(slot, 'artid', L.OWN_ART[slot])
            R.T.set(slot, CREATED, 1)
            changed += 1
    W, arts = R.f['wgjx'], set(L.CLUB_ART.values())
    gone = [i for i in range(W.cur_rec) if W.get(i, ROW_ART) in arts]
    if gone:
        tail = [{f: W.get(i, f) for f in W.fields} for i in range(gone[0], W.cur_rec) if i not in gone]
        for i in range(gone[0], W.cur_rec):
            for f in W.fields:
                W.set(i, f, 0)
        W.cur_rec = gone[0]
        for row in tail:
            W.add_record(row)
        changed += 1
    return changed


def check_art_fit(R):
    """Problems of Coachella Valley / Henderson's / the Vees' art ids in a roster for the patch (texts, empty when right):
    their art id, the flag off, and the donor's rows under their art id and slot."""
    out = []
    for slot in in_the_roster(R, L.CLUB_ART):
        art = L.CLUB_ART[slot]
        donor, variants = L.CLUB_DONOR[slot]
        if R.T.get(slot, 'artid') != art or R.T.get(slot, CREATED) != 0:
            out.append(f"team slot {slot} ({R.team_name(slot)}) does not have art id {art} as a club")
        mine = sorted((row['TccF'], tuple(sorted(dict(row, **{ROW_ART: 0, ROW_TEAM: 0}).items())))
                      for row in art_rows(R, art))
        theirs = sorted((row['TccF'], tuple(sorted(dict(row, **{ROW_ART: 0, ROW_TEAM: 0}).items())))
                        for row in art_rows(R, donor) if row['TccF'] in variants)
        if mine != theirs or any(row[ROW_TEAM] != slot for row in art_rows(R, art)):
            out.append(f"team slot {slot} ({R.team_name(slot)}): its jersey rows are not the donor club's")
    return out


def check_league_fit(R):
    """Problems of Coachella Valley / Henderson / the Vees in a roster for the patch (texts, empty when right): in their
    division and switched on."""
    return [f"team slot {slot} ({R.team_name(slot)}) is not in its division" for slot in in_the_roster(R, LEAGUE_SLOTS)
            if league_of(R, slot) != LEAGUE_SLOTS[slot] or not R.T.get(slot, 'NYKk')]


def all_star_fit(R):
    """Name the two All-Star places (ALL_STAR_LOOK), put them in their conferences and in the game's own All-Star rink
    (ALL_STAR_RINK), in the roster `R`, in place."""
    for slot, (full, short, abbr, group) in ALL_STAR_LOOK.items():
        R.T.set(slot, 'JkmY', full)
        R.T.set(slot, 'ITNQ', short)
        R.T.set(slot, 'nnsx', abbr)
        R.T.set(slot, CONFERENCE, group)
        R.T.set(slot, DIVISION, group)
        for field, value in ALL_STAR_RINK[slot].items():
            R.T.set(slot, field, value)


def check_all_star(R):
    """Problems of a roster's All-Star game for the patch (texts, empty when right): the two places named and in their
    conferences, and exactly one row of a team against itself in nhlschedule and favoriteteamschedule, on a day that team
    has no other game."""
    problems = []
    for slot, (full, _short, _abbr, group) in ALL_STAR_LOOK.items():
        if R.T.get(slot, 'JkmY') != full or R.T.get(slot, CONFERENCE) != group or R.T.get(slot, DIVISION) != group:
            problems.append(f"team slot {slot} is not the {full}")
        elif any(R.T.get(slot, field) != value for field, value in ALL_STAR_RINK[slot].items()):
            problems.append(f"the {full} (slot {slot}) are not in the All-Star rink")
    for tag in (schedule.TABLE, schedule.FAVOURITE):
        rows = schedule.read(R, tag)
        own = [r for r in rows if r[2] == r[3]]
        if len(own) != 1:
            problems.append(f"schedule {tag} has {len(own)} All-Star rows, not 1")
            continue
        month, day, team, _ = own[0]
        if any((m, d) == (month, day) and team in (h, a) for m, d, h, a in rows if h != a):
            problems.append(f"schedule {tag}: team {team} plays on the All-Star day")
    return problems


def check_divisions(R):
    """Problems of a roster's NHL groups for the patch (texts, empty when right): each of the 32 NHL slots in a division of its
    conference, 8 teams in each division."""
    T, count = R.T, {}
    problems = []
    for n in range(32):
        division, conference = T.get(n, DIVISION), T.get(n, CONFERENCE)
        if DIVISIONS.get(division) != conference:
            problems.append(f"NHL slot {n} is in group {conference} / {division}, not in a division")
        count[division] = count.get(division, 0) + 1
    problems += [f"NHL slot {n} is not named {full}" for n, (full, short, abbr) in NAMES_2026.items()
                 if (T.get(n, 'JkmY'), T.get(n, 'ITNQ'), T.get(n, 'nnsx')) != (full, short, abbr)]
    return problems + [f"division {d} has {count.get(d, 0)} teams, not 8" for d in DIVISIONS if count.get(d, 0) != 8]


def disc_meta(source):
    """The game's own db/nhlng-meta.xml (bytes) from its disc (`source`: a disc image or the game's folder)."""
    from .art.disc import EbArchive
    return EbArchive.open(source, 'cacheboot.big').read('/'.join(META_FILE))


def _bits(low, high):
    return max(1, (high - low).bit_length())


def _meta_blocks(text):
    """{table name: (start, end) of its <table ...> ... </table> in `text`}."""
    blocks = {}
    for m in re.finditer(r'<table name="([^"]+)"', text):
        blocks[m.group(1)] = (m.start(), text.index('</table>', m.start()))
    return blocks


def _set_attr(tag, name, value):
    """The XML tag `tag` with attribute `name` set to `value` (added at the end when it has none)."""
    if re.search(rf'\b{name}="', tag):
        return re.sub(rf'\b{name}="[^"]*"', f'{name}="{value}"', tag)
    end = len(tag) - (2 if tag.endswith('/>') else 1)
    return tag[:end].rstrip(' ') + f' {name}="{value}"' + tag[end:]


def fit_meta(data):
    """The game's db/nhlng-meta.xml (`data`, bytes, as on the disc) made for the 32-team patch: META_ROWS rows, the
    META_TEAMS fields up to META_TEAM_HIGH and the META_KEYS ones up to META_KEY_HIGH in the bits they need. Everything else stays byte for byte; a file made by this
    comes back unchanged. Raises ValueError when the file is not the one this was made for."""
    text = data.decode('utf-8')
    blocks = _meta_blocks(text)
    edits = []                                            # (start, end, new text)
    for table, rows in META_ROWS.items():
        if table not in blocks:
            raise ValueError(f"the game's database description has no table {table}")
        start = blocks[table][0]
        tag = text[start:text.index('>', start) + 1]
        edits.append((start, start + len(tag), _set_attr(tag, 'maxinsert', rows)))
    for (table, field), high in META_HIGH.items():
        start, end = blocks.get(table, (0, 0))
        m = re.search(rf'<field name="{field}" [^>]*/>', text[start:end])
        if not m:
            raise ValueError(f"the game's database description has no field {table}.{field}")
        tag = m.group(0)
        low = int(re.search(r'rangelow="(-?\d+)"', tag).group(1))
        tag = _set_attr(_set_attr(tag, 'rangehigh', high), 'depth', _bits(low, high))
        edits.append((start + m.start(), start + m.end(), tag))
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    return text.encode('utf-8')


def check_meta(data):
    """Problems of a db/nhlng-meta.xml made by fit_meta (texts, empty when right): every whole-number field's range fits
    its bits (the game stores value - rangelow; a value that does not fit comes back as another), the rows and team
    ranges of the patch are there."""
    text = data.decode('utf-8')
    problems = []
    for tm in re.finditer(r'<table name="([^"]+)"[^>]*>(.*?)</table>', text, re.S):
        for fm in re.finditer(r'<field [^>]*/>', tm.group(2)):
            a = dict(re.findall(r'(\w+)="([^"]*)"', fm.group(0)))
            if a.get('type') == 'FIELDTYPE_INTEGER' and \
                    _bits(int(a['rangelow']), int(a['rangehigh'])) > int(a['depth']):
                problems.append(f"{tm.group(1)}.{a['name']}: {a['rangelow']}..{a['rangehigh']} does not fit in "
                                f"{a['depth']} bits")
    blocks = _meta_blocks(text)
    for table, rows in META_ROWS.items():
        start = blocks.get(table, (0, 0))[0]
        if f'maxinsert="{rows}"' not in text[start:text.index('>', start)]:
            problems.append(f"{table} has not room for {rows} rows")
    for (table, field), high in META_HIGH.items():
        start, end = blocks.get(table, (0, 0))
        if not re.search(rf'<field name="{field}" [^>]*rangehigh="{high}"', text[start:end]):
            problems.append(f"{table}.{field} does not go up to {high}")
    return problems[:20]


def disc_db(source):
    """The game's own database db/nhlng.db (bytes) from its disc (`source`: a disc image or the game's folder)."""
    from . import stock
    return stock.database(source)


def _meta_fields(meta):
    """{(table tag, field tag): depth} of every field in a db/nhlng-meta.xml (bytes)."""
    text = meta.decode('utf-8')
    out = {}
    for tm in re.finditer(r'<table name="[^"]+" shortname="([^"]+)"[^>]*>(.*?)</table>', text, re.S):
        for fm in re.finditer(r'<field [^>]*/>', tm.group(2)):
            a = dict(re.findall(r'(\w+)="([^"]*)"', fm.group(0)))
            out[tm.group(1), a['shortname']] = int(a['depth'])
    return out


def meta_rights(meta):
    """The bits a db/nhlng-meta.xml (bytes) gives the roster's player rights (RIGHTS_TABLE.RIGHTS), or None: patch 0.23's
    files give six, the game's own and older patches' five; the game reads a roster whose rights have other bits as
    damaged."""
    text = meta.decode('utf-8', 'replace')
    table = re.search(rf'<table [^>]*shortname="{RIGHTS_TABLE}"[^>]*>(.*?)</table>', text, re.S)
    field = table and re.search(rf'<field [^>]*shortname="{RIGHTS}"[^>]*depth="(\d+)"', table.group(1))
    return int(field.group(1)) if field else None


def _db(data):
    from .tdb import RosterFile
    f = RosterFile.__new__(RosterFile)
    f._parse_db(data)
    return f


def fit_db(data, meta, roster=None):
    """The game's database (`data`, db/nhlng.db as on the disc) with every field of its tables as wide as the description
    `meta` (made by fit_meta) says: the META_TEAMS fields grow to six bits. A field that grows pushes the ones after it
    along, as the game packs its tables (no gaps), in every record (Table.widen): the Season / Be a GM tables, empty
    templates, and the players' rights (cPbu: RIGHTS_TABLE, as the patch roster has them, rights_wide). The calendar tables (CALENDAR_TABLES) get room for
    schedule.PATCH_ROWS rows (empty ones at the end). With `roster` (the patch's roster, a Roster) the next seasons'
    calendars (NEXT_SEASON_TABLES) become the roster's, with its room. Everything else stays byte for byte;
    a file made by this comes back unchanged. Raises ValueError when the file is not the one this was made for."""
    f, depths = _db(data), _meta_fields(meta)
    for name in f.order:
        T = f[name]
        for fld in sorted(T.fields.values(), key=lambda x: -x.offset):
            if depths.get((name, fld.name), fld.bits) != fld.bits:
                T.widen(fld.name, depths[name, fld.name])
    for tag in CALENDAR_TABLES:
        if f[tag].max_rec < schedule.PATCH_ROWS:
            f[tag].grow(schedule.PATCH_ROWS)
    if roster is not None:
        for tag in NEXT_SEASON_TABLES:
            T, own = roster.f[tag], f[tag]
            if (T.field_defs, T.rec_len) != (own.field_defs, own.rec_len):
                raise ValueError(f"the roster's table {tag} has other fields than the game's")
            if own.max_rec < T.max_rec:
                own.grow(T.max_rec)
            if T.cur_rec > own.max_rec:
                raise ValueError(f"{T.cur_rec} rows of the roster's table {tag} do not fit in the game's ({own.max_rec})")
            used = T.cur_rec * T.rec_len
            own.records[:] = T.records[:used] + bytes(len(own.records) - used)    # no old rows left behind
            own.cur_rec = T.cur_rec
    return f.build_db()


def _same_rows(a, b):
    """Do tables `a` and `b` have the same fields and the same rows?"""
    return (a.field_defs, a.rec_len, a.cur_rec) == (b.field_defs, b.rec_len, b.cur_rec) and \
        a.records[:a.cur_rec * a.rec_len] == b.records[:b.cur_rec * b.rec_len]


def check_db(data, meta, roster=None):
    """Problems of a db/nhlng.db made by fit_db (texts, empty when right): it reads back, every table is packed without gaps
    in its record, and every field has the bits the description `meta` gives it (the Season copies these bits). With
    `roster` (the patch's roster, a Roster) its next seasons' calendars (NEXT_SEASON_TABLES) are the roster's."""
    try:
        f = _db(data)
    except (ValueError, struct.error) as err:
        return [f"the game's database cannot be read back: {err}"]
    depths = _meta_fields(meta)
    problems = []
    for name in f.order:
        T, pos = f[name], 0
        for fld in sorted(T.fields.values(), key=lambda x: x.offset):
            if fld.offset != pos:
                problems.append(f"table {name}: field {fld.name} at bit {fld.offset}, not {pos}")
            pos = fld.offset + fld.bits
            if depths.get((name, fld.name), fld.bits) != fld.bits:
                problems.append(f"table {name}: field {fld.name} has {fld.bits} bits, the description "
                                f"{depths[name, fld.name]}")
        if pos > T.rec_len * 8:
            problems.append(f"table {name}: {pos} bits in a record of {T.rec_len * 8}")
    text = meta.decode('utf-8')
    start = _meta_blocks(text).get('nhlschedule', (0, 0))[0]
    if f'maxinsert="{META_ROWS["nhlschedule"]}"' in text[start:text.index('>', start)]:    # the patch's description
        problems += [f"the game's calendar table {tag} has room for {f[tag].max_rec} rows, not {schedule.PATCH_ROWS}"
                     for tag in CALENDAR_TABLES if f[tag].max_rec != schedule.PATCH_ROWS]
    if roster is not None:
        problems += [f"the game's {name} is not the patch roster's ({f[tag].cur_rec} rows, the roster "
                     f"{roster.f[tag].cur_rec})" for tag, name in NEXT_SEASON_TABLES.items()
                     if not _same_rows(f[tag], roster.f[tag])]
        told = depths.get((RIGHTS_TABLE, RIGHTS))       # the game reads the roster's players as the description says
        has = roster.f[RIGHTS_TABLE].field(RIGHTS).bits if RIGHTS_TABLE in roster.f.order else told
        if told is not None and told != has:
            problems.append(f"the roster's player rights have {has} bits, the game's description {told}")
    return problems[:20]
