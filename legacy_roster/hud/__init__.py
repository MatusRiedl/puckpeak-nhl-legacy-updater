"""Over the game: partner chat lines and the post-match card drawn over RPCS3's game window (Play online).

    ov = Hud(find_rect)      # find_rect() -> (left, top, right, bottom) of the game window, or None for the main screen
    ov.start()
    ov.chat('Partner', 'gg')
    ov.result({...})             # see anim.Result
    ov.stop()

A separate click-through, never-activated, top-most layered window per widget (see native.py), so the controller and the
keyboard keep going to the game. Windows only; `available()` says whether it can run here. All drawing is on one thread.
Ported from the owner's NHL 19 project (overtime_roster/hud), in Puck Peak's colours. A layered window does not show over
exclusive fullscreen, so the online launch asks RPCS3 for borderless fullscreen (onlinecfg.borderless_config).
"""
import os
import queue
import re
import sys
import threading
import time

from . import anim

FPS = 60
TARGET_FPS = 70             # present on every Nth compositor frame, N = round(refresh / 70): never off the vsync grid
CTRL_SHIFT = 0x2 | 0x4
PHRASE_KEYS = tuple(0x70 + i for i in range(6))      # Ctrl+Shift+F1 .. F6, live only while the game window exists


def available():
    return sys.platform == 'win32'


def emulator_rect():
    """(left, top, right, bottom) in pixels of RPCS3's game window or NHL Legacy Native's, None when there is none. RPCS3 shows
    the game in a window of its own beside its main window ("RPCS3 0.0.38-..."); started with --no-gui (the online launch) only
    the game window is there. Its title is RPCS3's game title line ("FPS: 60.00 | Vulkan | ... | NHL Legacy Edition [BLES02153]").
    The port has the one window."""
    if not available():
        return None
    import ctypes
    from ctypes import wintypes as wt
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.SetProcessDPIAware()
    kernel32.OpenProcess.restype = wt.HANDLE
    kernel32.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
    kernel32.QueryFullProcessImageNameW.argtypes = (wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD))
    kernel32.CloseHandle.argtypes = (wt.HANDLE,)
    names = {}

    def image(pid):
        if pid not in names:
            h = kernel32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
            name = ''
            if h:
                buf, size = ctypes.create_unicode_buffer(520), wt.DWORD(520)
                if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    name = os.path.basename(buf.value).lower()
                kernel32.CloseHandle(h)
            names[pid] = name
        return names[pid]
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            program = image(pid.value)
            if program in ('rpcs3.exe', 'nhllegacy.exe'):
                title = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, title, 512)
                r, corner = wt.RECT(), wt.POINT(0, 0)          # the picture only: no title bar or border when windowed
                user32.GetClientRect(hwnd, ctypes.byref(r))
                user32.ClientToScreen(hwnd, ctypes.byref(corner))
                area = (r.right - r.left) * (r.bottom - r.top)
                if (program == 'nhllegacy.exe' or is_game_title(title.value)) and area > 640 * 360:
                    found.append((area, (corner.x, corner.y, corner.x + r.right, corner.y + r.bottom)))
        return True
    user32.EnumWindows(each, 0)
    return max(found)[1] if found else None


def is_game_title(title):
    """Is a window of rpcs3.exe titled `title` its game window? Not the main window ("RPCS3 0.0.38-...") nor one of its
    dialogs (Settings, Log, ...): the game window names the serial or shows the FPS."""
    return bool(re.search(r'\[(BLES|BLUS)\d{5}\]|FPS:', title or ''))


def screen_rect():
    import ctypes
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


class Hud:
    def __init__(self, find_rect=None, clock=time.monotonic, on_hotkey=None, hotkeys=()):
        self.find_rect = find_rect or screen_rect
        self.on_hotkey, self.hotkeys = on_hotkey, tuple(hotkeys)     # on_hotkey(index) runs on the HUD thread
        self.keys_on = False
        self.keys_taken = set()                         # phrase numbers whose hotkey another program holds
        self.clock = clock
        self.q = queue.Queue()
        self.thread = None
        self.error = None
        self.frames = 0

    # ---- thread-safe calls
    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, name='overlay', daemon=True)
        self.thread.start()

    def stop(self):
        self.q.put(('stop',))
        if self.thread:
            self.thread.join(5)

    def ping(self):
        """Make sure the HUD thread runs (the hotkeys live on it)."""
        self.start()

    def chat(self, who, text, hold=6.0):
        self.q.put(('chat', who, text, hold))

    def result(self, data, hold=9.0):
        self.q.put(('result', data, hold))

    # ---- HUD thread
    def _keys(self, native, want):
        """The quick-phrase hotkeys exist only while the game window does (so they never get in the way on the desktop)."""
        if want == self.keys_on or not self.hotkeys:
            return
        self.keys_on = want
        for i, vk in enumerate(self.hotkeys):
            if want:
                if not native.register_hotkey(i, CTRL_SHIFT, vk):
                    self.keys_taken.add(i)             # another program holds it: that phrase has no key this game
            else:
                native.unregister_hotkey(i)
        if not want:
            self.keys_taken.clear()

    def _run(self):
        try:
            self._loop()
        except Exception as e:                         # the overlay must never take the app down
            self.error = repr(e)

    def _loop(self):
        from . import cards, native
        rect = self.find_rect() or screen_rect()
        s = max(0.5, (rect[3] - rect[1]) / 1080.0)       # fixed for the run: the surfaces are sized once
        chat = anim.Chat()
        res = None
        chat_surf = native.Surface(*cards.chat_size(s))
        card_surf = native.Surface(*cards.card_size(s))
        last_rect = 0
        native.timer_resolution(True)
        every = max(1, round(native.refresh_hz() / TARGET_FPS))
        try:
            while True:
                now = self.clock()
                for ident in native.pump():
                    if self.on_hotkey and ident < len(self.hotkeys):
                        self.on_hotkey(ident)
                try:
                    while True:
                        cmd = self.q.get_nowait()
                        if cmd[0] == 'stop':
                            return
                        if cmd[0] == 'chat':
                            chat.add(cmd[1], cmd[2], now, cmd[3])
                        elif cmd[0] == 'result':
                            res = anim.Result(cmd[1], now, cmd[2])
                except queue.Empty:
                    pass
                if now - last_rect > 1.0:              # follow the game window; none (the game closed) hides everything
                    last_rect = now
                    rect = self.find_rect()
                self._keys(native, rect is not None)
                if rect is None:
                    chat_surf.hide()
                    card_surf.hide()
                    time.sleep(0.25)
                    rect = self.find_rect()
                    continue
                left, top, right, bottom = rect
                lines = chat.tick(now)
                if lines:
                    cards.draw_chat(chat_surf.gfx, lines, now, s)
                    chat_surf.present(left + 24 * s, bottom - chat_surf.h - 130 * s)
                else:
                    chat_surf.hide()
                if res and res.done(now):
                    res = None
                if res:
                    cards.draw_result(card_surf.gfx, res, now, s)
                    card_surf.present((left + right - card_surf.w) / 2, top + (bottom - top) * .42 - card_surf.h / 2,
                                      255 * res.alpha(now))
                else:
                    card_surf.hide()
                self.frames += 1
                if lines or res:
                    for _ in range(every):
                        native.vsync(1.0 / FPS)
                else:
                    time.sleep(0.05)
        finally:
            native.timer_resolution(False)
            self._keys(native, False)
            chat_surf.close()
            card_surf.close()
