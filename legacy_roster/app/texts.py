"""What the window says to players, and the small helpers that word it."""
import datetime

from .. import savedata

SITE = "https://www.puckpeak.com"
SITE_LABEL = "www.puckpeak.com"
DISCORD = "https://gg.puckpeak.com"        # the Puck Peak Discord (a redirect)
KOFI = "https://ko-fi.com/iksperial"       # tips for the development (the button below the Discord one)
TAGLINE = "NHL & hockey analytics like never before"
HOW_TO_LOAD = "In the game: Customize > Save/Load/Delete > Load > Rosters, pick it, then save the roster once so it stays active."
HOW_TO_LOAD_IN_PLACE = ("In the game: start it. If this is not the roster in use, Customize > Save/Load/Delete > Load > Rosters, pick it, "
                        "then save the roster once.")
HOW_TO_USE_EXPORT = ("Copy SYS-DATA into one of your roster save folders in place of the file with that name (keep a copy of "
                     "the old one), then in the game: Customize > Save/Load/Delete > Load > Rosters, pick it, and save the roster once.")
NO_NAME = "(a roster file has no name)"
BIN_NAME = "Recycle Bin" if savedata.WINDOWS else "Trash"
DISC_NOTE = "From your game disc: the 2014-15 players, brought up to today"
SAVE_NOTE = ("Updating this roster makes a backup first. Saving as a new roster leaves existing saves untouched. "
             "RPCS3 must be closed for in-place updates.")
EXPORT_SAVE_NOTE = ("Everything is made into a new folder (named by the date and time) and nothing in RPCS3 is changed. "
                    "A short text in it says where each part goes.")
EXPORT_PICK = ("Pick a roster of your RPCS3 below, or a roster file (the SYS-DATA of the community roster you downloaded). "
               "The files are made into a new folder.")
GAME_ROSTER_FILE = ("that is the game's own roster as it comes on the disc. Pick \"New from EU disc\" (or NA) in the list "
                    "above instead: the export then makes an updated roster from it")
EXPORT_RPCS3 = ("Optional here: pick RPCS3 to start from your own rosters and to skip roster names you already use. "
                "Nothing in it is changed.")
EXPORT_GAME = "Pick your copy of the game (the .iso or its folder): the pictures, the game patch and the game's own roster need it."
EXPORT_PATCH_ON = "The export holds the game patch: a roster for 32 teams, the patch's files, and what to tick in RPCS3."
EXPORT_PATCH_OFF = "Not in the export: it holds a roster for the game as it is. Tick the box to add the game patch."
EXPORT_PATCH_NOTE = ("RPCS3's own patch list is not changed: the instructions in the export say which patches to tick "
                     "(Manage > Game Patches). Needs your copy of the game.")
EXPORT_WHY = ("Restore, \"Update this roster\", Play online and the Be a Pro and Season saves are off while you export: they "
              "change RPCS3 itself. Switch off \"Export files to a folder\" in Setup to use them.")
ROOM_NOTE = "The game shows at most 10 rosters per version. Keep 10 or fewer."
ROOM_FULL_SHORT = "Full: the game shows only 10. Delete a roster you no longer play, or pick \"Update this roster\"."
ROOM_FULL = savedata.FULL_TEXT
HIDDEN_IN_GAME = ("The game does not show this roster: it lists only 10. Delete a roster you no longer play, "
                  "and this one shows again.")
PHOTOS_HINT ="RPCS3 must be closed. The game's own pictures are kept and can be put back."
PHOTOS_TITLE = "Photos and logos"
PHOTOS_SIZE = 105 * 1000 * 1000       # what the row says before the program knows the real size
PHOTOS_RUNNING = "Downloading automatically... {pct} %"
PHOTOS_READY = "Downloaded automatically. Ready."
PHOTOS_RETRY = "Not downloaded yet. It tries again automatically."
PHOTOS_OFF = "Off: nothing is downloaded."
PROGRAM = "rpcs3.exe" if savedata.WINDOWS else "the RPCS3 program"       # what the player is asked to pick, in his system's word
PHOTOS_NEEDS_RPCS3 = f"Needs RPCS3: pick {PROGRAM} in step 1."
PHOTOS_EXPORT = "Pick your copy of the game in Setup first: the pictures are made from it."
PHOTOS_WAITING = "Waiting for the download... {pct} %"
PHOTOS_SHORT = "Some pictures could not be downloaded; the next update tries again."
PACK_TITLES = {'photos': "player photos and team logos", 'looks': "this season's jerseys", 'ice': "the new centre ice",
               'arenas': "NHL arenas", 'masks': "team goalie masks"}   # packs.NAMES
PICTURE_NOT_SERVED = "Not available for download yet: nothing to install. The program looks again at its next start."


def pictures_short(names):
    """The result's line for the packs (packs.NAMES) an update had to go without."""
    return ("Not downloaded, so not installed: " + ", ".join(PACK_TITLES.get(n, n) for n in names)
            + ". The next update tries again.")


# 0.76.0: the picture rows after "Photos and logos" (settings key -> title, what it does, about how many bytes it downloads)
PICTURE_ROWS = {
    'photos': ("Player photos and team logos", "The pictures of the players and the logos of the teams.",
               PHOTOS_SIZE),
    'names': ("Team names", "Team names and short codes in Select Teams and on the scoreboard, and the main menu texts. "
                            "RPCS3 must be closed.", 0),
    'looks': ("This season's jerseys and centre ice", "New jerseys, pants and socks for the teams, and new centre-ice "
                                                      "logos: 30 NHL teams with the arenas' current names.", 55 * 1000 * 1000),
    'arenas': ("NHL arenas", "New boards and banners in the NHL arenas.", 13 * 1000 * 1000),
    'team_masks': ("Team goalie masks", "The goalie masks of the teams.", 3 * 1000 * 1000),
}
PICTURE_SIZES = {pack: PICTURE_ROWS[key][2] for pack, key in (('photos', 'photos'), ('looks', 'looks'), ('arenas', 'arenas'),
                                                                      ('masks', 'team_masks'))}
PICTURE_SIZES['ice'] = 6 * 1000 * 1000      # the new centre ice, downloaded with this season's (0.80.0); about how big, before the server says
PICTURE_NAMES_OFF = "Off: the game keeps its own team names."
NAMES_TIP = "Writes the team names of the roster you picked now. Your rosters and your graphics are not touched."
NAMES_DONE = "Team names are in. Your graphics were not touched."
PICTURE_NO_DOWNLOAD = "Nothing to download."
SAVED_DESPITE = ("The roster is saved: you can load it in the game. The details of what went wrong are in {log}; "
                 "send that file with a bug report.")
SAVED_SOME_FAILED = "Something after the save went wrong."
LOOKS_MISSING = "This season's jerseys come with the switch \"This season's jerseys and centre ice\" (Update tab)."
EDITS_HINT = "Kept on this PC, so the next download does not undo them."
PATCH_TITLE = "32 teams and the year 2026 (game patch)"
PATCH_SUB = "Seattle and Vegas in Season and Be a GM: 32 NHL and 32 AHL teams, 84 games. New."
NOT_PATCHED = "Not patched: updates make rosters for the game as it is."
PATCHED_NOTE = "every update makes a roster for it"
PATCH_NEEDS_RPCS3 = f"The game patch needs RPCS3: pick {PROGRAM} in step 1."
PATCH_NATIVE = "The game patch is for RPCS3. NHL Legacy Native cannot take it, so its Season and Be a GM stay at 30 teams."
NATIVE_NOTE = ("NHL Legacy Native: updates, pictures, team names and the editors all work here. It has no game patch and no "
               "online play, so Season and Be a GM have 30 teams, and Coachella Valley, Henderson and the Vees are Custom teams.")
ONLINE_NATIVE = "Online play needs RPCS3: NHL Legacy Native has no online. Pick RPCS3 in Setup to play online."


def linux_pick(folders):
    """The question that opens the RPCS3 picker on Linux: the program (an AppImage or the rpcs3 binary) is best, the folder
    is enough to find the saves and to patch, but then the program cannot start RPCS3 for you (the Flatpak starts anyway)."""
    return ["Pick the RPCS3 program (the rpcs3 file or its AppImage): the program then finds your saves and can start RPCS3.",
            "Or pick RPCS3's folder (" + ", ".join(folders) + "). With the Flatpak, pick that folder."]
PATCH_NEEDS_GAME = "RPCS3 does not list the game yet: start it once from RPCS3's game list."
PATCH_ASK = ["This patches the game in RPCS3 (every version you have) for 32 teams and the year 2026.",
             "While it is patched, every update makes a roster for the patched game. The patched game shows other "
             "rosters as damaged: update one of them first.",
             "Season and Be a GM saves you start with the patch need it to go on.",
             "Unpatch (in step 2) puts the game back as it was. RPCS3 must be closed for both."]
UNPATCH_ASK = ["This takes the game patch out of RPCS3: the game is as it was.",
               "Rosters made for the patch, and Season and Be a GM saves started with it, do not open without it. "
               "Update a roster made for the patch, and it is made for the game as it is again. "
               "Your rosters and saves are not changed now."]
MISFIT_PATCHED = "The patched game cannot load this roster (it says \"damaged\"). Update it to make it a 32-team roster."
MISFIT_UNPATCHED = "Made for the game patch: the game without it cannot load this roster. Update it to turn it back."
MISFIT_VERSION = ("Made for another version of the game patch: the patched game cannot load this roster (it says "
                  "\"damaged\"). Update it to make it fit.")
MISFIT_STALE = ("Your game has update 1.01, and the game patch in RPCS3 is from before this program knew it. Press "
                "Patch again in Game patch.")
FIT_NO_STEP = "Switch on at least one thing to update, then press Update roster."
UNPATCHED = "Done: the game patch is out. Rosters marked \"32 teams\" do not open now: update one, and it is made for the game as it is."
NO_LOGIN_TIP = "No sign-in boxes when the game starts. Online modes still sign in when you open them."
PATCH_INFO_TITLE = "What the game patch does"
PATCH_INFO = [
    ("In the game", [
        "The year is 2026: the calendar, the seasons and the dates start in 2026-27, not 2015.",
        "Season, Be a GM and Be a Pro have all 32 NHL teams: Seattle and Vegas can be picked, played and simulated. "
        "Utah plays in the Central, Seattle and Vegas in the Pacific.",
        "The real 2026-27 calendar: 84 games per team. The seasons after it get a 32-team calendar too.",
        "The farm league has 32 AHL clubs in their 2026-27 divisions, with Coachella Valley (Seattle) and Henderson "
        "(Vegas). Call-ups and send-downs work for every team. Both clubs are also in Play Now's AHL list (their names "
        "come with the Team names switch).",
        "The playoffs, the trade deadline, the off-season, the All-Star game and the draft with the lottery work "
        "with 32 teams (7 rounds, 224 picks a year).",
        "Salary cap in real money: $104.0M in 2026-27 (floor $76.9M), $113.5M in 2027-28, $127.5M in 2028-29, "
        "then held. Contracts show the seasons as 26-27, 27-28 ...",
        "The computer runs Seattle and Vegas like every other team (call-ups, line-ups, re-signing), so a Season or "
        "Be a GM plays on season after season.",
        "The news panel of the main menu shows Puck Peak's news, also when you play online (they come with Photos, "
        "logos and team names).",
    ]),
    ("The two switches", [
        "Skip the intro: the game goes straight to the main menu. No language pick, intro videos, legal screen, "
        "autosave notice or Press Start. Autosave stays on.",
        "No pop ups at start: no online sign-in boxes when the game starts. Online modes still sign in when you "
        "open them.",
    ]),
    ("What it changes on your PC", [
        "A patch file in RPCS3's patches folder, and the patch's ticks in RPCS3's patch settings. RPCS3 applies it each "
        "time the game starts. The game's own files and your disc are never changed.",
        "Two small database files in the game's folder in RPCS3, made from your own game disc.",
        "Every version of the game you have (EU and NA). A file that was there before is kept and put back by Unpatch.",
        "Your rosters and saves are not changed when you patch.",
    ]),
    ("Rosters and saves", [
        "While the game is patched, every update makes a roster for it (marked \"32 teams\"). The patched game shows "
        "other rosters as damaged: update one of them first.",
        "Start a new Season, Be a GM or Be a Pro after patching. Saves started with the patch need it to go on.",
        "Online play still works.",
    ]),
    ("Unpatch", [
        "Unpatch takes it all out: the game is as it was. Rosters marked \"32 teams\" and saves started with the patch "
        "do not open without it. Update such a roster, and it is made for the game as it is again.",
        "RPCS3 must be closed to patch or unpatch.",
    ]),
]


def patched_status(where):
    return f"Done: the {where} game is patched. Now update a roster (Update tab) and start a new Season or Be a GM."


def fit_ask(name, why):
    """The question after Patch / Unpatch when the roster picked no longer fits the game (`why`: a MISFIT_ text)."""
    if why == MISFIT_VERSION:
        return [f"\"{name}\" was made for another version of the game patch. The patched game cannot load it and says "
                "it is damaged.", "Update it now and it fits the patch you have. A backup is made first."]
    if why == MISFIT_PATCHED:
        return [f"\"{name}\" was made for the game without the patch. The patched game cannot load it and says it is "
                "damaged.", "Update it now and it becomes a 32-team roster for the patched game. A backup is made first."]
    return [f"\"{name}\" was made for the patched game. The game without the patch cannot load it.",
            "Update it now and it is made for the game as it is again. A backup is made first."]


def patch_state(state, old=(), missing=()):
    """'Patched: EU and NA (intro skipped)' from patchinstall.state, or None when nothing is patched. `old`: patched
    versions with an older patch; `missing`: versions RPCS3 has that are not patched."""
    on = [t for t, st in state.items() if st.get('patched') or st.get('stale')]
    if not on:
        return None
    from .. import savedata
    extra = [what for what, key in (("intro skipped", 'intro'), ("no pop-ups at start", 'login'))
             if any(state[t].get(key) for t in on)]
    text = f"Patched: {' and '.join(savedata.region(t) for t in on)}" + (f" ({', '.join(extra)})" if extra else "")
    if not old and not missing:
        return f"{text}: {PATCHED_NOTE}."
    if old:
        text += ". A newer patch is in this program: press Patch again."
    elif missing:
        text += f". Your {' and '.join(savedata.region(t) for t in missing)} game is not patched."
    return text


SCHEDULE_NOTE = "The real games and dates for Season mode (30 teams; the game still calls the year 2015)"
NHL_NOTE = "Today's rosters from NHL.com"
MISSING_FILES = ("Some of this program's files are missing from the system's temporary folder. An antivirus "
                 "or a cleaning program may have removed them.\n\n"
                 "Close this message and start the program again. If it keeps happening, "
                 "allow PuckPeakLegacyUpdater in your antivirus.")


def friendly_date(when, now=None):
    now = now or datetime.datetime.now()
    days = (now.date() - when.date()).days
    if days == 0:
        return f"today {when:%H:%M}"
    if days == 1:
        return f"yesterday {when:%H:%M}"
    return f"{when.day} {when:%b %Y}"


def short_reason(problem):
    if 'custom copies' in problem:
        return "Cannot be used: its teams are laid out differently from the community roster."
    return "Cannot be used: " + problem.split('. ')[0].rstrip('.') + "."


def dated(source):
    return f"{source['label']}, data from {source['date']}" if source else "No data available"


def rpcs3_note(rpcs3, slots):
    """What step 1 says under the path once RPCS3 is found: only what the player needs to act on.
    (The count of rosters found is gone: the list shows them.) None when there is nothing to say."""
    saves = [s for s in slots if not getattr(s, 'disc', False)]
    if rpcs3 is not None and rpcs3.plain:
        n = len(saves)
        return (f"Found {n} roster{'s' if n != 1 else ''} of NHL Legacy in this folder. Without RPCS3 the new roster "
                "is saved next to them; photos and the game's own roster need RPCS3.")
    if rpcs3 is not None and rpcs3.native:
        return None if saves else ("No roster is saved yet. Start from the game's own roster (listed below): it is made "
                                   "from your game and brought up to today.")
    if not saves and not slots:
        return ("No roster is saved in RPCS3 yet, and RPCS3 does not say where your game is. Pick the game "
                "(its .iso file or its folder): the program then starts from the game's own roster, made from "
                "your game disc and brought up to today.")
    if not saves:
        return ("No roster is saved in RPCS3 yet. Start from the game's own roster (listed below): it is "
                "made from your game disc and brought up to today.")
    return None


def photos_will(size=None):
    """The Photos row before its pictures are on this PC: 'Downloaded automatically (about 160 MB)'."""
    size = size or PHOTOS_SIZE
    if size < 1e7:
        return "Downloaded automatically (under 10 MB)"
    return f"Downloaded automatically (about {round(size / 1e7) * 10} MB)"
