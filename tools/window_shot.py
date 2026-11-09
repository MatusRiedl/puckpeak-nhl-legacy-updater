"""Show the updater window in a given state and save a picture of it: for checking the window after a change,
and for the README. It never touches a real RPCS3: it builds a pretend RPCS3 folder in a temporary folder
from the base roster (the same one the tests use) and keeps the program's settings, caches and reports there.

    python tools\\window_shot.py <state> <out.png> [options]

states (the tab they show in brackets):
    none       RPCS3 not set yet [Setup]
    setup      RPCS3 found, a roster selected [Setup]
    ready      RPCS3 found, a roster selected [Update]
    patch      the Game patch tab, not patched [Game patch]
    updating   an update in progress (made-up progress messages)
    done       runs a real offline update into the pretend folder, then shows the result
    details    done, with the details drawer open
    failed     a made-up failure
    delete     the question before a roster save goes to the Recycle Bin (its Delete button pressed)
    export     Setup with "Export files to a folder" ticked and a roster file picked (also export-ready)
    export-done  the files made, the "Your files are ready" window open
    roster     the Roster tab on the base roster, Edmonton (or --team <slot>) and its first player picked (also: editor)
    equipment  the Roster tab's "Equipment" window for the first Edmonton player (pictures need --disc)
    jerseys    the Jerseys & ice tab for Edmonton or --team <slot> (pictures need --disc) (also: uniforms)
    lines      the Lines tab for Edmonton (SHOT_TAB=pp|pk|ot|so|letters: another part), a place picked
    strategy   the Strategy tab for Edmonton, two values changed (also: strategies)
    face       the Roster tab's "Face of a player" window, SHOT_FACE (default "mc") typed (head pictures need --disc)
    calendar   the Calendar tab for Edmonton (SHOT_DAY=YYYY-MM-DD: that day opened; SHOT_MODE=league: all games)
    office     the Front office tab for Edmonton
    contract   the Front office's contract window for its first player, the cap hit raised by $1M
    prospects  the Draft & Pro tab: next year's draft with three made-up prospects, the second on the card
    prospects-pro  the Draft & Pro tab: My pro, made and on the card
    prospects-make  the Draft & Pro tab's "Make a class..." window over the three prospects
    prospects-class  the Draft & Pro tab: a random class of 32 (number 2027), its first player on the card
    prospects-import  the Draft & Pro tab: that class saved as a file and put into the draft after, with the report
    prospects-career  the Draft & Pro tab's Be a Pro careers: copies from LEGACY_ROSTER_CAREERS (folders of Be a Pro
               saves) in the pretend RPCS3, the first opened, 250 more Offense XP and Passing + 3 not saved
    online     the Play online tab, not set up yet (online-lobby: a lobby, its host alone; online-ready: two players Ready;
               online-ingame: the game started, a guest; online-failed: it could not sign in; online-mismatch: a guest without the host's game patch;
               online-you: set up, with a rank and matches; online-chat: a lobby of two chatting; online-board: the leaderboard; online-stats: My stats; online-box: a box score;
               online-result: the result window after a match); made-up facts, no network
    patched    the Game patch tab: the EU game patched with an older patch (Patch again, Unpatch), a roster tagged "32 teams"

The pretend RPCS3 has the base roster, an earlier update of it, and a copy saved for the NA version, so the
EU / NA tags and "Save for" show.

How the picture is made: the program's own controllers (legacy_roster/app/) are driven into the state, what
they would push to the page is written to a file, and Microsoft Edge (headless, nothing shows on the screen)
draws the page from web/ with it. So the picture is the same on every PC, at any scaling, without a window.

options:
    --scale F           the screen's scaling: 1 (100 %), 1.5 (150 %), 2 (200 %); default 1
    --screen-lines N    pretend the screen is N lines tall (default 1080; 768 = small laptop); the window takes the
                        size main.py gives it there (taskbar 48 lines, 16:9, 1366 wide up to 800 lines)
    --size WxH          the page's size in the window's units instead of the one --screen-lines gives (940x640: the
                        smallest window)
    --tab ID            show another tab than the state's own (setup, update, patch, roster, lines, strategy,
                        jerseys, calendar, office, prospects)
    --show-path TEXT    path shown in Setup, so a public picture does not show a real user name
    --all               switch on every league before a done/details update
    --disc PATH         your own game disc image (read only): the editor's card then shows the players' pictures
    --saves             step 1 points at a copied folder of roster saves instead of RPCS3
    --live              open the real window (pywebview) and let it paint itself into the picture (PrintWindow;
                        Windows, needs .venv: pywebview, Pillow); --scale has no effect there
    --browser           open the page in your web browser instead of saving a picture (for design work; the
                        buttons do nothing there). Ctrl+C stops it; `out` is not used.
"""
import argparse
import ctypes
import datetime
import functools
import http.server
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
BASE = os.environ.get('LEGACY_ROSTER_BASE') or os.path.join(ROOT, 'work', 'backup', 'BLES021530202')
WEB = os.path.join(ROOT, 'legacy_roster', 'web')
STATES = ('none', 'setup', 'ready', 'patch', 'updating', 'done', 'details', 'failed', 'delete', 'roster', 'editor', 'jerseys',
          'uniforms', 'equipment', 'export', 'export-ready', 'export-done', 'patched', 'full', 'lines', 'strategy', 'strategies', 'face',
          'calendar', 'office', 'contract', 'downloading', 'misfit', 'prospects', 'prospects-pro', 'prospects-look',
          'prospects-make', 'prospects-class', 'prospects-import', 'prospects-career', 'online', 'online-lobby',
          'online-ready', 'online-ingame', 'online-failed', 'online-mismatch', 'online-list', 'online-you', 'online-chat',
          'online-board', 'online-result', 'online-stats', 'online-box', 'export-roster', 'heads-up')
TEAM_STATES = {'roster': 'roster', 'editor': 'roster', 'equipment': 'roster', 'face': 'roster', 'jerseys': 'jerseys',
               'uniforms': 'jerseys', 'lines': 'lines', 'strategy': 'strategy', 'strategies': 'strategy',
               'calendar': 'calendar', 'office': 'office', 'contract': 'office', 'prospects': 'prospects',
               'prospects-pro': 'prospects', 'prospects-look': 'prospects', 'prospects-make': 'prospects', 'prospects-class': 'prospects',
               'prospects-import': 'prospects', 'prospects-career': 'prospects', 'export-roster': 'roster',
               'heads-up': 'roster'}
# made-up players for the Draft & Pro pictures (no real person's name)
SHOT_PROSPECTS = (('Aron', 'Halvik', 'C', 'SWE', 1), ('Jonah', 'Vale', 'D', 'CAN', 3), ('Marek', 'Doubrava', 'LW', 'CZE', 5))
SCREEN_LINES, TASKBAR = 1080, 48    # the screen pretended (in the window's units) and its taskbar
FRAME = (16, 39)                # what the frame and title bar take of it at 100 %
FIXTURE = '__fixture.json'


def pretend_rpcs3(folder, disc=None, full=False):
    """An RPCS3 folder with the base roster, one earlier update of it and a copy for the NA version
    (`disc`: a game disc image both versions are said to be on; `full`: 11 EU rosters, one more than the
    game lists)."""
    from legacy_roster import savedata
    sd = os.path.join(folder, 'rpcs3', 'dev_hdd0', 'home', '00000001', 'savedata')
    shutil.copytree(BASE, os.path.join(sd, os.path.basename(BASE)))
    exe = os.path.join(folder, 'rpcs3', 'rpcs3.exe')
    open(exe, 'wb').close()
    base = savedata.list_rosters(sd)[0]
    with open(base.sys_data, 'rb') as f:
        data = f.read()
    savedata.install(sd, base, data, savedata.default_name(datetime.datetime.now() - datetime.timedelta(days=1)))
    savedata.install(sd, base, data, "Community roster NA", title_id='BLUS31540')
    for n in range(3, 11) if full else ():
        shutil.copytree(base.path, os.path.join(sd, f"{base.title_id}02{n:02d}"))
    if disc:
        os.makedirs(os.path.join(folder, 'rpcs3', 'config'))
        with open(os.path.join(folder, 'rpcs3', 'config', 'games.yml'), 'w', encoding='utf-8') as f:
            f.write(''.join(f'{t}: "{os.path.abspath(disc)}"\n' for t in savedata.GAMES))
    return exe


def pretend_native(folder):
    """An install of NHL Legacy Native with the base roster saved for the game (--native: every state on the port)."""
    from legacy_roster import savedata
    root = os.path.join(folder, 'NHL Legacy Native')
    for sub in ('game/PS3_GAME', 'data/update/USRDIR'):
        os.makedirs(os.path.join(root, sub))
    open(os.path.join(root, 'NHLLauncher.exe'), 'wb').close()
    head = bytearray(0x200)                                     # the build the game patch was made for: the two numbers savedata.exe_id reads
    head[:2], head[0x80:0x84] = b'MZ', b'PE\0\0'
    struct.pack_into('<I', head, 0x3c, 0x80)
    struct.pack_into('<II', head, 0x88, min(savedata.NATIVE_PATCHED)[0], 0)
    struct.pack_into('<I', head, 0xd0, min(savedata.NATIVE_PATCHED)[1])
    with open(os.path.join(root, 'NHLLegacy.exe'), 'wb') as f:
        f.write(head)
    open(os.path.join(root, 'data', 'eboot.elf'), 'wb').close()
    with open(os.path.join(root, 'nhl_settings.ini'), 'w', encoding='utf-8') as f:
        f.write('[paths]\ndisc = game\nuser = user\n[launcher]\n')
    sd = os.path.join(root, 'user', 'gamedata', 'dev_hdd0', 'home', '00000001', 'savedata')
    shutil.copytree(BASE, os.path.join(sd, os.path.basename(BASE).replace('BLES02153', 'BLUS31540')))
    return os.path.join(root, 'NHLLauncher.exe')


def capture(hwnd, out):
    """The window (its handle) as it paints itself, cropped to its visible frame."""
    from PIL import Image
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    for fn in (user32.GetWindowDC, gdi32.CreateCompatibleDC, gdi32.CreateCompatibleBitmap, gdi32.SelectObject):
        fn.restype = wintypes.HANDLE
    user32.GetWindowDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HANDLE]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.UINT]
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HANDLE]
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    gdi32.GetDIBits.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                ctypes.c_void_p, wintypes.UINT]
    gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi32.DeleteDC.argtypes = [wintypes.HANDLE]
    hwnd = wintypes.HWND(hwnd)
    whole, visible = wintypes.RECT(), wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(whole))
    # the window rectangle also counts the invisible resize border; DWM knows the visible frame
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(visible), ctypes.sizeof(visible))
    w, h = whole.right - whole.left, whole.bottom - whole.top
    wdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(wdc)
    bmp = gdi32.CreateCompatibleBitmap(wdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    painted = user32.PrintWindow(hwnd, mdc, 2)                  # PW_RENDERFULLCONTENT
    header = (ctypes.c_uint32 * 10)(40, w, (-h) & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)    # top-down, 32 bit
    bits = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, bits, header, 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, wdc)
    if not painted:
        raise RuntimeError("the window could not be painted into a picture")
    img = Image.frombuffer('RGB', (w, h), bits, 'raw', 'BGRX', 0, 1)
    img = img.crop((visible.left - whole.left, visible.top - whole.top,
                    visible.right - whole.left, visible.bottom - whole.top))
    img.save(out)
    return img.size



def wait(condition, seconds=600):
    end = time.time() + seconds
    while time.time() < end and not condition():
        time.sleep(0.1)


def drive(args, c, work):
    """Bring the controllers into the state asked for. Says which tab shows and whether the details are open."""
    from legacy_roster import gamepatch, layout as L
    upd, ed, uni = c['update'], c['editor'], c['uniforms']
    wait(lambda: not upd.scanning, 60)
    state, tab, details = args.state, 'update', False
    if state in ('none', 'setup'):
        tab = 'setup'
        if state == 'setup':
            upd.select(os.path.basename(BASE))
    elif state.startswith('online'):
        tab = 'online'
        make_online(c, state)
    elif state == 'patch':
        tab = 'patch'
        upd.select(os.path.basename(BASE))
    elif state == 'updating':
        upd._begin(None)
        for msg in ('Starting from "ROSTER2526" (BLES021530202)', 'NHL rosters: ANA (1/32)', 'NHL rosters: TOR (28/32)'):
            upd.say(msg)
    elif state in ('done', 'details'):
        if args.all:
            for key in upd.steps:
                upd.steps[key] = True
        if not args.disc:                   # the pretend RPCS3 has no game to make pictures from
            upd.photos = False
            for part in upd.art_on:         # team names too: they need the game's own files
                upd.art_on[part] = False
        upd.select(os.path.basename(BASE))
        upd.start()
        wait(lambda: upd.busy, 10)
        wait(lambda: not upd.busy and not upd.scanning)
        details = state == 'details'
    elif state in TEAM_STATES:
        tab = TEAM_STATES[state]
        if state == 'export-roster':        # an export from a roster file: the team tabs show the file
            upd.set_export_only(True)
            wait(lambda: not upd.scanning)
            upd.use_export_file(os.path.join(BASE, 'SYS-DATA'))
        else:
            upd.select(os.path.basename(BASE))
        ed.show_tab('roster')               # the team tabs read the roster picked in Setup
        wait(lambda: ed.view is not None and not ed.busy and ed.after_busy is None)
        team = args.team if args.team is not None else L.API_TO_SLOT['EDM']
        ed.set_league("Free agents" if team == 'FA' else ed.snap.team_league[team])
        ed.pick_team(team)
        rows = ed.snapshot()['rows']
        ed.pick_player(next((r for r in rows if r['pos'] == 'G'), rows[0])['id'] if os.environ.get('SHOT_GOALIE') else rows[0]['id'])
        wait(lambda: not (ed.picture or {}).get('loading'), 60)
        ed.show_tab(tab)                    # its follower follows the team
        if tab == 'jerseys':
            wait(lambda: (uni.snapshot() or {}).get('loaded'), 120)
            if uni.team_kit is None:            # a custom team's form has the game's pictures once it is loaded
                wanted = len(uni.versions) + 1 if uni.pictures is not None and args.disc else 0
                wait(lambda: len(uni.thumbs) >= wanted, 120)
        if state == 'heads-up':         # free editing: a goalie moved off the team, the gold line under the list
            goalie = next(r for r in ed.snapshot()['rows'] if r['pos'] == 'G')
            ed.pick_player(goalie['id'])
            other = next(t for t in ed.snap.teams_in('NHL') if t != team)
            ed.apply(dict(ed.snapshot()['card']['values'], team=str(other)))
            wait(lambda: not ed.busy and ed.after_busy is None)
        if state == 'equipment':
            ed.equipment.open()
            wait(lambda: ed.equipment.loaded, 120)
        if state == 'lines':
            ed.lines.set_tab(os.environ.get('SHOT_TAB') or 'even')
            ed.lines.pick_slot({'pp': 'pp1c', 'pk': 'pk4_1c', 'ot': 'ot_1c', 'so': 's1'}.get(ed.lines.tab, 'l2lw'))
        if state == 'face':             # the Face of a player window, a search typed (the heads' pictures need --disc)
            ed.face_open()
            wait(lambda: (ed.modal or {}).get('pics') != 'loading', 120)
            ed.face_search(os.environ.get('SHOT_FACE') or 'mc')
        if tab == 'strategy':
            ed.strategy.set('oz_forecheck', 1)
            ed.strategy.set('forward1_bias2', 8)
        if tab == 'calendar':
            if os.environ.get('SHOT_MODE'):
                c['calendar'].mode(os.environ['SHOT_MODE'])
            if os.environ.get('SHOT_DAY'):
                c['calendar'].day(os.environ['SHOT_DAY'])
        if tab == 'prospects':
            make_prospects(c, state)
        if state == 'contract':         # the first player of the organisation's list, $1M more
            office = c['office']
            first = next(r for g in office.snapshot()['groups'] for r in g['rows'])
            ed.contract_open(first['key'])
            deal = office.contract_snapshot()['draft']
            office.contract_change('cap', deal['cap'] + 1_000_000)
    elif state in ('export', 'export-ready', 'export-done'):     # "Export files to a folder": the files go into the temp folder
        os.chdir(work)
        upd.set_export_only(True)
        upd.use_export_file(os.path.join(BASE, 'SYS-DATA'))
        tab = 'setup'
        if state == 'export-done':                  # the made files and the "Your files are ready" window
            tab = 'update'
            upd.start()
            wait(lambda: upd.busy, 10)
            wait(lambda: not upd.busy)
            wait(lambda: upd.dialog is not None, 10)
    elif state == 'patched':        # the EU game patched with an older patch, a roster made for it
        tab = 'patch'
        upd.select(os.path.basename(BASE))
        upd.patch_state = {'BLES02153': {'patched': True, 'version': '0.17', 'intro': True, 'login': False}}
        upd.patch_rosters = {os.path.basename(BASE)}
        upd.changed()
    elif state == 'misfit':         # the EU game just patched, the roster picked is a normal one: the question
        tab = 'setup'
        upd.select(os.path.basename(BASE))
        upd.patch_state = {'BLES02153': {'patched': True, 'version': gamepatch.TEAMS_VERSION, 'intro': True, 'login': False}}
        upd.patch_rosters = set()
        upd.versions = ['BLES02153']
        upd._ask_fit()
        upd.changed()
    elif state == 'downloading':    # the pictures of "Photos, logos and team names" coming in, Update pressed
        upd.select(os.path.basename(BASE))
        upd.fetch, upd.fetch_at, upd.fetch_size = 'running', 0.41, 157_000_000
        upd.waiting, upd.busy = False, True
        upd._fetch_progress(0.42)
    elif state == 'full':           # 11 EU rosters: the count is red, one row is not in the game, no new roster
        upd.select(os.path.basename(BASE))
        upd.save_mode = 'new'
        upd.changed()
    elif state == 'delete':
        tab = 'setup'
        upd.ask_delete(next(s.folder for s in upd.slots if s.tool_made))
    elif state == 'failed':
        upd.status = ("Nothing was saved.", 'bad')
        upd.show_result(False, "The new roster failed the safety checks, so nothing was saved",
                        ["Anaheim Ducks dresses 19 players (4 C, 4 LW, 3 RW, 6 D, 2 G); the game needs 20 with 2 G "
                         "and at least 6 D", "Your existing rosters are untouched."], [("Show details", 'details')])
    return args.tab or tab, details


SHOT_LOOK = {'shape': 9, 'tone': 6, 'hair': 2, 'hair_colour': 3, 'facial_hair': 0, 'facial_hair_colour': 3,
             'eyebrow': 1, 'eyebrow_colour': 3, 'eyes': 4, 'black_eye': 0, 'scars': 1, 'freckles': 0}


def make_prospects(c, state):
    """Three made-up prospects for next year's draft on CHL clubs (the second on the card); 'prospects-pro': also My
    pro, on Edmonton, with a created look, on the card; 'prospects-look': the Look window over him (the game's pictures
    need --disc); 'prospects-make': the maker's window over them; 'prospects-class' / 'prospects-import': a random class
    instead (and its file put into the draft after)."""
    from legacy_roster import draftclass
    from legacy_roster import layout as L
    ed, pr = c['editor'], c['prospects']
    year = ed.snap.season_year + 1
    if state == 'prospects-career':
        return make_career(c)

    def calm():
        with ed.lock:                       # `busy` goes off just before the result is taken in, under the lock
            return not ed.busy and ed.after_busy is None

    settle = lambda: wait(lambda: calm() and (time.sleep(0.05) or calm()), 300)
    if state in ('prospects-class', 'prospects-import'):
        pr.show(year)
        pr.make_open()
        pr.make_set('count', 32)
        pr.make_set('seed', 2027)
        pr.make()
        settle()
        if state == 'prospects-import':     # another player's class of the same year (number 99), one club unknown
            snap = ed.snap
            names = [(p.first, p.last, p.country) for p in snap.by_who.values() if not any(t in L.NHL_ALL for t in p.teams)]
            taken = [p.name for p in snap.by_who.values()]
            made = draftclass.make(year, 24, names, pr._draft_clubs(snap), seed=99, taken=taken)
            players = [{'card': pl['card'], 'prospect': pl['prospect'],
                        'club': {'league': snap.team_league[pl['club']], 'name': snap.team_name(pl['club'])}} for pl in made]
            players[0]['club'] = {'league': 'OHL', 'name': 'Lakeshore Herons'}
            pr.step(1)
            pr.import_text(draftclass.class_file("Shared class", year, players), 'shared_class.json')
            settle()
        pr.pick(pr.snapshot()['rows'][0]['key'])
        settle()
        return
    clubs = (min(L.OHL), min(L.QMJHL), min(L.WHL))

    def made(first, last, pos, country, team, birth, ovr, look=None):
        typed = {'first': first, 'last': last, 'num': str(10 + len(ed.edits)), 'pos': pos, 'shoots': 'L',
                 'birth': birth, 'country': country, 'height': '185', 'weight': '84', 'team': team, 'ovr': str(ovr),
                 'ratings': {}, 'look': look}
        assert ed.apply(typed) == 'applied', ed.status
        settle()

    pr.show(year)
    for (first, last, pos, country, tier), team in zip(SHOT_PROSPECTS, clubs):
        pr.add()
        pr.set('tier', tier)
        made(first, last, pos, country, team, f"{year - 18}-0{tier}-12", 62 - 4 * tier)
    if state in ('prospects-pro', 'prospects-look'):
        pr.show('pro')
        pr.add()
        made('Theo', 'Brannick', 'C', 'CAN', L.API_TO_SLOT['EDM'], f"{year - 20}-05-01", 64, look=SHOT_LOOK)
        if state == 'prospects-look':
            ed.look_open(ed.snapshot()['card']['values']['look'])
            wait(lambda: (ed.modal or {}).get('pics') != 'loading', 120)
    else:
        pr.pick(next(r['key'] for r in pr.snapshot()['rows'] if r['name'].endswith('Vale')))
    if state == 'prospects-make':
        pr.make_open()
        pr.make_set('seed', 2027)


def make_online(c, state):
    """The Play online tab with made-up facts, no network: 'online' not set up yet, 'online-lobby' a lobby with its host
    alone, 'online-ready' two players Ready, 'online-ingame' the game started (a guest), 'online-failed' it could not sign in."""
    upd, on = c['update'], c['online']
    upd.select(os.path.basename(BASE))
    wait(lambda: not upd.scanning, 60)
    on.account, on.checked, on.server = 'GuestPlayer', True, True
    on.title = (upd.versions or ['BLES02153'])[0]
    on.build = 20402
    if state != 'online':
        on.state = {'patched': True, 'online': True, 'version': '0.26', 'game': '01.00'}
    else:
        on.state = {'patched': False, 'online': False, 'version': None, 'game': '01.00'}
    if state != 'online':
        on.roster = {'name': 'Puck Peak Online 2026-10-25', 'folder': 'BLES021530299', 'crc': 'a1b2c3d4'}
    me = {'name': 'GuestPlayer', 'role': 'host', 'roster_ok': True, 'patch_ok': True, 'ready': False, 'progress': 'in_game',
          'patch': '0.26', 'version': 'EU 01.00'}
    friend = {'name': 'Friend_77', 'role': 'guest', 'roster_ok': True, 'patch_ok': True, 'ready': False, 'progress': 'signed_in',
              'patch': '0.26', 'version': 'EU 01.00'}
    mine = {'crc': 'a1b2c3d4', 'size': 1048576}
    if state == 'online-list':
        on.public = True
        on.open_lobbies = [
            {'code': 'KDMQRS', 'host': 'Friend_77', 'roster_name': 'Community 2026-27 (updated)', 'patch': '0.26', 'version': 'EU 01.00',
             'roster_size': 1048576, 'age_seconds': 40, 'members': 1, 'max': 2},
            {'code': 'TWXYZA', 'host': 'PuckHunter', 'roster_name': 'Puck Peak Online', 'patch': '0.25', 'version': 'EU 01.00',
             'roster_size': 1048576, 'age_seconds': 600, 'members': 1, 'max': 2},
            {'code': 'BCDFGH', 'host': 'EUplayer', 'roster_name': 'My roster', 'patch': '0.26', 'version': 'NA 01.01',
             'roster_size': 1048576, 'age_seconds': 3000, 'members': 1, 'max': 2}]
    elif state == 'online-lobby':
        on.brought = 'Community 2026-27 (updated)'
        on.lobby, on.code = {'code': 'KDMQRS', 'state': 'open', 'reason': None, 'members': [me], 'roster': mine}, 'KDMQRS'
    elif state == 'online-mismatch':
        me.update(role='guest', patch='0.25', patch_ok=False)
        friend.update(role='host', progress='hosting')
        on.state['version'] = '0.25'
        on.lobby = {'code': 'KDMQRS', 'state': 'open', 'reason': 'Friend_77 has game patch 0.26, GuestPlayer has game patch 0.25. '
                    'Both need the same: update the program.', 'members': [friend, me], 'roster': mine}
        on.code = 'KDMQRS'
    elif state == 'online-ready':
        me['ready'] = friend['ready'] = True
        friend['rpcs3'] = '20402'
        on.lobby, on.code = {'code': 'KDMQRS', 'state': 'starting', 'reason': None, 'members': [me, friend], 'roster': mine}, 'KDMQRS'
    elif state in ('online-ingame', 'online-failed'):
        me.update(role='guest', progress='browsing', ready=True)
        friend.update(role='host', progress='hosting', ready=True)
        on.lobby, on.code = {'code': 'KDMQRS', 'state': 'playing', 'reason': None, 'members': [friend, me], 'roster': mine}, 'KDMQRS'
        on.launched = 'KDMQRS'
        on.log = {'name': 'GuestPlayer', 'bound': True, 'signaling': state == 'online-ingame', 'refused': None, 'fatal': False,
                  'old': False}
    if state in ('online-you', 'online-chat', 'online-board', 'online-result', 'online-stats', 'online-box'):
        shot_ranks(on, state)
        if state == 'online-chat':
            me['ready'] = True
            on.lobby, on.code = {'code': 'KDMQRS', 'state': 'open', 'reason': None, 'members': [me, friend], 'roster': mine,
                                 'chat': [{'seq': 1, 'name': 'Friend_77', 'text': 'Ready when you are', 'at': 0},
                                          {'seq': 2, 'name': 'GuestPlayer', 'text': 'One sec', 'at': 0},
                                          {'seq': 3, 'name': 'Friend_77', 'text': 'Rematch after this?', 'at': 0}]}, 'KDMQRS'
    on.changed()


def shot_ranks(on, state):
    """Made-up ranks for the online-you / -chat / -board / -result pictures."""
    on.ranks_on = True
    on.card = {'name': 'GuestPlayer', 'rating': 1137, 'tier': 'Pro', 'placing': 0, 'rank': 4, 'of': 23, 'w': 9, 'l': 5,
               'streak': 2, 'peak': 1150, 'delta7': 21, 'form': 'WWLWWLWWWL', 'gf': 41, 'ga': 30,
               'curve': [[k, r] for k, r in enumerate((1000, 1016, 1031, 1015, 1032, 1050, 1066, 1049, 1067, 1084, 1101, 1086, 1104,
                                                        1120, 1150, 1133, 1119, 1137))],
               'opponents': [{'name': 'Friend_77', 'w': 4, 'l': 2}, {'name': 'PuckHunter', 'w': 2, 'l': 1},
                             {'name': 'EUplayer', 'w': 1, 'l': 1}],
               'teams': [{'name': 'Montreal Canadiens', 'w': 5, 'l': 3}, {'name': 'Edmonton Oilers', 'w': 3, 'l': 1}],
               'next_tier': 'Top 6', 'next_at': 1200, 'hidden': False}
    games = [('Friend_77', 'MTL', 'TOR', 4, 2, 'W', 18, 'confirmed'), ('PuckHunter', 'EDM', 'CGY', 3, 2, 'W', 15, 'confirmed'),
             ('Friend_77', 'MTL', 'BOS', 1, 3, 'L', -17, 'confirmed'), ('EUplayer', 'DET', 'CHI', 2, 2, None, None, 'waiting'),
             ('Hidden player', 'NYR', 'NJD', 5, 1, 'W', 22, 'forfeit')]
    on.history = [{'id': f'B1/{9 - k}', 'at': 0, 'status': st, 'why': None, 'opponent': o, 'team': t, 'opp_team': u, 'for': f,
                   'against': a, 'result': res, 'delta': d, 'waiting': st == 'waiting'}
                  for k, (o, t, u, f, a, res, d, st) in enumerate(games)]
    names = [('IceKing', 1288, 'Top 6'), ('Friend_77', 1201, 'Top 6'), ('Hidden player', 1164, 'Pro'), ('GuestPlayer', 1137, 'Pro'),
             ('PuckHunter', 1102, 'Pro'), ('EUplayer', 1040, 'Rookie'), ('SlapShot', 1012, 'Rookie'), ('Netminder9', 988, 'Minor League')]
    on.board = {'players': [{'rank': k + 1, 'name': n, 'rating': r, 'tier': t, 'placing': 0, 'games': 10 + k, 'w': 8 - k // 2,
                             'l': 3 + k // 2, 'streak': 1, 'peak': r, 'last': None, 'delta7': 0} for k, (n, r, t) in enumerate(names)],
                'ranked': 23, 'highlights': [{'kind': 'climber', 'title': 'Climber of the week', 'name': 'IceKing', 'value': '+64'},
                                             {'kind': 'streak', 'title': 'Hot streak', 'name': 'Friend_77', 'value': 'W4'}],
                'recent': [], 'tiers': [{'name': 'Minor League', 'min': 0}, {'name': 'Rookie', 'min': 1000},
                                        {'name': 'Pro', 'min': 1100}, {'name': 'Top 6', 'min': 1200}],
                'placement': 5, 'updated': 0}
    on.ranks_tab = {'online-board': 'board', 'online-stats': 'stats', 'online-box': 'box'}.get(state, 'mine')
    on.boxes = {'B1/9': ('confirmed', {'id': 'B1/9', 'at': 0, 'status': 'confirmed', 'why': None, 'sides': [
        {'name': 'GuestPlayer', 'team': 'Montreal Canadiens', 'score': 4, 'home': True,
         'stats': {'SHTS': 31, 'HITS': 14, 'FO': 27, 'PIMS': 4, 'PPG': 1, 'PPO': 3, 'SHG': 0, 'PSSC': 188, 'PSSA': 231, 'TOA': 512,
                   'BS': 6, 'BAG': 1, 'BAO': 2}},
        {'name': 'Friend_77', 'team': 'Toronto Maple Leafs', 'score': 2, 'home': False,
         'stats': {'SHTS': 24, 'HITS': 19, 'FO': 22, 'PIMS': 8, 'PPG': 0, 'PPO': 2, 'SHG': 0, 'PSSC': 160, 'PSSA': 214, 'TOA': 431,
                   'BS': 9, 'BAG': 0, 'BAO': 1}}]})}
    on.box_id = 'B1/9'
    if state == 'online-result':
        on.result = on.history[0]


def make_career(c):
    """Up to three Be a Pro career copies (LEGACY_ROSTER_CAREERS) into the pretend RPCS3, the careers in view, the first
    opened, 250 more Offense XP and Passing + 3 typed."""
    from legacy_roster import careersave
    source = os.environ.get('LEGACY_ROSTER_CAREERS')
    folders = []
    for here, dirs, files in os.walk(source or ''):
        if 'DATA0000' in files and 'PARAM.SFO' in files:
            folders.append(here)
    if not folders:
        raise SystemExit("prospects-career needs LEGACY_ROSTER_CAREERS: a folder holding copies of Be a Pro saves")
    sd = c['update'].rpcs3.savedata
    for n, folder in enumerate(sorted(folders)[:3]):
        shutil.copytree(folder, os.path.join(sd, f'BLES021530{500 + n}'))
    car, pr = c['career'], c['prospects']
    pr.show('careers')
    car.open(car.saves[0].folder)
    wait(lambda: not car.busy, 120)
    car.set('offense', car.career.pro.xp['offense'] + 250)
    if car.career.pro.ratings:
        car.set('passing', min(careersave.HIGHEST, car.career.pro.ratings['passing'] + 3))


def controllers():
    from legacy_roster.app.calendar import CalendarController
    from legacy_roster.app.career import CareerController
    from legacy_roster.app.editor import EditorController
    from legacy_roster.app.equipment import EquipmentController
    from legacy_roster.app.lines import LinesController
    from legacy_roster.app.office import OfficeController
    from legacy_roster.app.online import OnlineController
    from legacy_roster.app.prospects import ProspectsController
    from legacy_roster.app.season import SeasonSource
    from legacy_roster.app.strategy import StrategyController
    from legacy_roster.app.uniforms import UniformsController
    from legacy_roster.app.update import UpdateController
    from legacy_roster.window.host import WebHost
    host = WebHost()                        # without a window: it only collects what would be pushed
    upd = UpdateController(host)
    ed = EditorController(host, upd)
    uni = UniformsController(host, ed)
    eq = EquipmentController(host, ed)
    ln, st = LinesController(host, ed), StrategyController(host, ed)
    season = SeasonSource(ed)
    cal, office = CalendarController(host, ed, season), OfficeController(host, ed, season)
    car = CareerController(host, ed)
    pr = ProspectsController(host, ed, car)
    online = OnlineController(host, upd, autopoll=False)
    ed.follow_with('online', online)
    for name, snapshot in (('lines', ln.snapshot), ('strategy', st.snapshot), ('update', upd.snapshot), ('editor', ed.snapshot),
                           ('picture', ed.picture_view), ('face_pics', ed.face_pics_view), ('look_pics', ed.look_pics_view),
                           ('uniforms', uni.snapshot), ('thumbs', uni.thumbs_view),
                           ('equipment', eq.snapshot), ('equip_pics', eq.pics_view), ('rail', ed.rail_view),
                           ('calendar', cal.snapshot), ('office', office.snapshot), ('contract', office.contract_snapshot),
                           ('prospects', pr.snapshot), ('career', car.snapshot), ('online', online.snapshot)):
        host.register(name, snapshot)
    upd.start_up()
    return host, {'host': host, 'update': upd, 'editor': ed, 'uniforms': uni, 'calendar': cal, 'office': office,
                  'prospects': pr, 'career': car, 'online': online}


# a state whose rows are below the fold: the list of steps scrolled to its end once the page is drawn
SCROLL_STEPS = ("<script>setInterval(() => { const step = document.querySelector('.step'); const list = step && "
                "step.closest('.scroll'); if (list) list.scrollTop = list.scrollHeight; }, 200);</script>")
# SHOT_SCROLL=1: an in-page window scrolled to its end (the lower part of a long window)
SCROLL_MODAL = ("<script>setInterval(() => { const body = document.querySelector('.modal .m-body'); "
                "if (body) body.scrollTop = body.scrollHeight; }, 200);</script>")
# SHOT_OPEN=1: the Photos and logos row opened (its parts shown)
OPEN_GROUP = ("<script>const opened = setInterval(() => { const a = document.querySelector('.step .arrow:not(.open)'); "
              "if (a) { a.click(); clearInterval(opened); } }, 200);</script>")


def serve(message, extra=''):
    """The page and the fixture on a local web server (ES modules do not load from file://): its address. `extra`:
    more for the page's head (SCROLL_STEPS)."""
    data = json.dumps(message)
    with open(os.path.join(WEB, 'index.html'), encoding='utf-8') as f:
        page = f.read()
    # the state goes into the page itself, so it is there before the first picture is drawn
    shot = page.replace('<head>', '<head>\n<script>window.__FIXTURE__ = ' + data.replace('</', '<\\/') + ';</script>' + extra, 1)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split('?')[0]
            if path in ('/' + FIXTURE, '/shot.html'):
                body = (data if path.endswith('.json') else shot).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json' if path.endswith('.json') else 'text/html')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=WEB))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def browser_program():
    for path in (os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
                 os.path.join(os.environ.get('ProgramFiles', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
                 '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                 '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'):
        if os.path.exists(path):
            return path
    for name in ('msedge', 'microsoft-edge', 'google-chrome', 'chromium', 'chromium-browser'):
        if shutil.which(name):
            return shutil.which(name)
    sys.exit("no Microsoft Edge or Chrome found to draw the page (or use --live)")


def window_size(lines):
    """The window's size with its frame (main.fit) on a screen `lines` tall."""
    from legacy_roster.window.main import fit
    width = 1366 if lines <= 800 else round(lines * 16 / 9)
    return fit((0, 0, width, lines - TASKBAR))[:2]


def headless(url, out, args, work):
    if args.size:
        size = tuple(int(x) for x in args.size.lower().split('x'))
    else:
        window = window_size(args.screen_lines or SCREEN_LINES)
        size = (window[0] - FRAME[0], window[1] - FRAME[1])
    out = os.path.abspath(out)
    if os.path.exists(out):
        os.remove(out)
    subprocess.run([browser_program(), '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
                    f'--user-data-dir={os.path.join(work, "browser")}', f'--force-device-scale-factor={args.scale}',
                    f'--window-size={size[0]},{size[1]}', '--virtual-time-budget=10000', f'--screenshot={out}', url],
                   check=False, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not os.path.exists(out):
        sys.exit("the browser made no picture")
    return size


def live(args, work):
    """The real window, painted into the picture by itself."""
    from legacy_roster.window import main as window_main

    def after(window, c):
        window.events.loaded.wait(30)
        time.sleep(2)
        tab, details = drive(args, c, work)
        window.run_js("window.dispatchEvent(new CustomEvent('lr-tab', { detail: '%s' }))" % tab)
        if details:
            c['host'].send('details', {'open': True})
        time.sleep(2.5)
        print(args.state, args.out, capture(window.native.Handle.ToInt64(), args.out))
        window.destroy()
    window_main.main([], after=after)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('state', choices=STATES)
    ap.add_argument('out')
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--screen-lines', type=int)
    ap.add_argument('--size', help="the page's size, WxH (940x640: the smallest window)")
    ap.add_argument('--tab', choices=('setup', 'update', 'patch', 'roster', 'lines', 'strategy', 'jerseys', 'calendar', 'office',
                                      'prospects'))
    ap.add_argument('--show-path')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--disc')
    ap.add_argument('--team', type=lambda v: v if v == 'FA' else int(v),
                    help="the editor's team slot (default Edmonton; 36 Charlotte, 135 Canada; FA the free agents)")
    ap.add_argument('--saves', action='store_true')
    ap.add_argument('--native', action='store_true', help="on a pretend NHL Legacy Native, with a pretend RPCS3 to switch to")
    ap.add_argument('--live', action='store_true')
    ap.add_argument('--browser', action='store_true')
    args = ap.parse_args()
    if not os.path.exists(os.path.join(BASE, 'SYS-DATA')):
        sys.exit("no base roster save: set LEGACY_ROSTER_BASE to a roster save folder (see docs/DEVELOPING.md)")

    work = tempfile.mkdtemp(prefix='window-shot-')
    os.environ['LOCALAPPDATA'] = os.environ['XDG_DATA_HOME'] = work    # settings, caches and reports stay here
    here = os.getcwd()
    try:
        from legacy_roster import __version__, pipeline, savedata
        from legacy_roster.app import settings as S
        from legacy_roster.app import texts as X
        exe = pretend_rpcs3(work, args.disc, full=args.state == 'full')
        if args.saves:                                # the saves copied out of RPCS3: no RPCS3 above them
            copied = os.path.join(work, 'copied saves')
            shutil.copytree(os.path.join(os.path.dirname(exe), 'dev_hdd0', 'home', '00000001', 'savedata'), copied)
            exe = copied
        hosts = {}
        if args.native:
            hosts = {'hosts': {'rpcs3': exe}}
            exe = pretend_native(work)
        S.load = lambda: {} if args.state == 'none' else {'rpcs3': exe, **hosts}
        S.save = lambda values: None
        savedata.running_rpcs3 = lambda: None         # a running RPCS3 on this PC must not be picked up
        savedata.default_rpcs3 = lambda: None         # nor one in its usual place
        real_update = pipeline.update
        pipeline.update = lambda *a, **k: real_update(*a, **{**k, 'offline': True})
        if args.live:
            live(args, work)
            return
        host, c = controllers()
        upd = c['update']
        if args.native:
            chosen = upd.select
            upd.select = lambda folder: chosen(folder.replace('BLES02153', 'BLUS31540'))
        tab, details = drive(args, c, work)
        time.sleep(0.3)
        message = host.first()
        message['meta'] = {'version': __version__, 'tagline': X.TAGLINE, 'site_label': X.SITE_LABEL}
        if args.show_path:
            if (message['slices'].get('update', {}).get('rpcs3') or {}).get('path'):
                message['slices']['update']['rpcs3']['path'] = args.show_path
            # the temporary folder and the home folder name the user: a public picture shows made-up ones
            text = json.dumps(message)
            for real, shown in ((work, r'C:\Users\Player\AppData\Local'), (os.path.expanduser('~'), r'C:\Users\Player')):
                text = text.replace(json.dumps(real)[1:-1], json.dumps(shown)[1:-1])
            message = json.loads(text)
        server, url = serve(message, (SCROLL_MODAL if os.environ.get('SHOT_SCROLL') else '') +
                            (OPEN_GROUP if os.environ.get('SHOT_OPEN') else ''))
        query = f'&tab={tab}' + ('&details' if details else '')
        if args.browser:
            import webbrowser
            url += f"index.html?fixture={FIXTURE}" + query
            webbrowser.open(url)
            print("The page is open in your browser at", url, "- Ctrl+C stops.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return
        size = headless(url + "shot.html?still" + query, args.out, args, work)
        server.shutdown()
        print(f"{args.state}: {args.out} {size[0]}x{size[1]} at {args.scale:g}x, {len(upd.slots)} rosters")
    finally:
        os.chdir(here)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
