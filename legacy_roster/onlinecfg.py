"""Online play from the app (private/Multiplayer.txt, docs/notes/multiplayer.md): the pieces that need neither the server nor a
running RPCS3, standard library only. The player's own RPCS3 files are only read:

    account(rpcs3)                  the RPCN name in config/rpcn.yml (never the password or the token)
    net_config(text, address)       a config.yml with the Net block set for our server, every other line as it was
    write_config(rpcs3, title, ip)  that config as the app's own file (online/config_<TITLE>.yml in the program's folder)
    launch_args(rpcs3, title, cfg)  rpcs3.exe (AppImage, flatpak run ...) --no-gui --config <cfg> <game>
    log_state(text)                 what RPCS3's log says about the online sign-in
    read_shared(path)               RPCS3's log, which RPCS3 keeps open
    rpcs3_build(rpcs3)              the build number of the RPCS3 that wrote the log (None: not known yet)
    roster_crc(data)                the CRC in a roster save's header (the official online roster is told by it)
"""
import os
import re
import struct

from . import datasource, savedata, tdb

HOST = 'gosredirector.ea.com'        # the address the game asks for; RPCS3's IP swap list sends it to our server
NET = {                              # the Net block's keys the app sets; every other key stays as the player has it
    'Internet enabled': 'Connected',
    'PSN status': 'RPCN',
    'UPNP Enabled': 'true',
}
SWAP = 'IP swap list'
MIN_RPCS3 = 20393                    # the oldest RPCS3 build the online lab played with (lab 1); older ones are told to update
MATHS_KEY, MATHS = 'SPU XFloat Accuracy', 'Accurate'     # every online config (maths_config)
MATHS_WORD = 'exact'                  # part of the lobby's patch word: an older app's games would drift away from these


def account(rpcs3):
    """The RPCN name (NPID) in RPCS3's rpcn.yml (config/ on Windows, next to its data on Linux and Mac), or None (no file,
    no account yet). Only that line is read."""
    for path in (os.path.join(rpcs3.folder, 'config', 'rpcn.yml'), os.path.join(rpcs3.folder, 'rpcn.yml')):
        try:
            with open(path, encoding='utf-8-sig', errors='replace') as f:
                for line in f:
                    key, sep, value = line.rstrip('\r\n').partition(':')
                    if sep and key.strip() == 'NPID':
                        return value.strip().strip('"\'') or None
        except OSError:
            continue
    return None


def good_name(name):
    """Is `name` a name a player of NHL Legacy Native can go online with (the rules of an RPCN name)?"""
    return bool(re.fullmatch(r'[A-Za-z0-9_-]{3,16}', name or ''))


def port_launch(host, address, name, roster=None, by_itself=False):
    """(arguments, environment) that start NHL Legacy Native for a lobby. Our patch file reads NHL_PUCKPEAK_*: the game server,
    the save folder of the roster to load at boot, and `by_itself` = go to the lobby's search with no key. The rest is the port's
    own: real sockets (with no PSN server to ask, so nothing is listening at that address), the name, the quick boot."""
    env = savedata.clean_environment()
    env.update(NHL_PUCKPEAK_ONLINE=address, PS3_NET_ONLINE='1', PSNR_SERVER='127.0.0.1:9', PS3_NP_ONLINE_ID=name, NHL_SKIP_INTRO='1')
    if roster:
        env['NHL_PUCKPEAK_ROSTER'] = os.path.basename(roster)
    if by_itself:
        env['NHL_PUCKPEAK_START'] = '1'
    return [host.exe, '--username', name], env


def base_config(rpcs3, title):
    """The text of the config RPCS3 would boot `title` with: its custom config when there is one, else config.yml ('' when
    there is neither)."""
    for path in (os.path.join(rpcs3.folder, 'config', 'custom_configs', f'config_{title}.yml'),
                 os.path.join(rpcs3.folder, 'custom_configs', f'config_{title}.yml'),
                 os.path.join(rpcs3.folder, 'config', 'config.yml'), os.path.join(rpcs3.folder, 'config.yml')):
        try:
            with open(path, encoding='utf-8-sig', errors='replace', newline='') as f:
                return f.read()
        except OSError:
            continue
    return ''


def _swaps(value, address):
    """The IP swap list `value` with HOST sent to `address`, other pairs kept (RPCS3 joins pairs with &&)."""
    pairs = [p.strip() for p in value.strip().strip('"\'').split('&&') if p.strip()]
    pairs = [p for p in pairs if p.partition('=')[0].strip().lower() != HOST]
    return ' && '.join(pairs + [f'{HOST}={address}'])


def net_config(text, address):
    """`text` (a config.yml) with its Net block set to play online on our server at `address`: Internet enabled, RPCN,
    UPnP on, HOST swapped for `address` (the player's other swaps stay). Every other line is as it was, line endings
    included; a missing Net block or key is added."""
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.rstrip() == 'Net:'), None)
    if start is None:
        lines += ['Net:'] + [f'  {k}: {v}' for k, v in NET.items()] + [f'  {SWAP}: {_swaps("", address)}']
        return newline.join(lines) + newline
    end = start + 1
    while end < len(lines) and (lines[end].startswith((' ', '\t')) or not lines[end].strip()):
        end += 1
    seen = set()
    for i in range(start + 1, end):
        key, sep, value = lines[i].strip().partition(':')
        if not sep:
            continue
        if key in NET:
            lines[i] = f'  {key}: {NET[key]}'
            seen.add(key)
        elif key == SWAP:
            lines[i] = f'  {SWAP}: {_swaps(value, address)}'
            seen.add(key)
    add = [f'  {k}: {v}' for k, v in NET.items() if k not in seen]
    if SWAP not in seen:
        add.append(f'  {SWAP}: {_swaps("", address)}')
    while end > start + 1 and not lines[end - 1].strip():       # new keys go after the block's last key
        end -= 1
    lines[end:end] = add
    return newline.join(lines) + (newline if text.endswith('\n') or not text else '')


def blit_config(text):
    """`text` (a config.yml) with "Disable Blit Engine Upscaling" ticked when the resolution scale is not 100 %: RPCS3 has a
    bug that makes matches load forever at another scale unless it is on (lab 2026-10-26: NA at 300 % stalled with the box off
    and loaded in 45 s with it on; the community says the same). At 100 % or with no scale named, nothing changes."""
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.rstrip() == 'Video:'), None)
    if start is None:
        return text
    end = start + 1
    while end < len(lines) and (lines[end].startswith((' ', '\t')) or not lines[end].strip()):
        end += 1
    scale = blit = None
    for i in range(start + 1, end):
        key, sep, value = lines[i].partition(':')
        if sep and key == '  Resolution Scale':
            scale = i
        elif sep and key == '  Disable Blit Engine Upscaling':
            blit = i
    if scale is None or lines[scale].partition(':')[2].strip().strip('"\'') == '100':
        return text
    if blit is None:
        lines.insert(scale + 1, '  Disable Blit Engine Upscaling: true')
    else:
        lines[blit] = '  Disable Blit Engine Upscaling: true'
    return newline.join(lines) + (newline if text.endswith('\n') else '')


def maths_config(text):
    """`text` (a config.yml) with the SPU's floats at Accurate. At Approximate RPCS3 swaps the game's 1 / x and square root recipes
    for exact sums, the two answers differ by a rounding step, and a match against NHL Legacy Native or a player on another
    setting drifts apart in the skeletons, then the puck (lab 2026-11-03: lost after 8 s; at Accurate it stays in step,
    docs/notes/native-patch.md). Everybody online uses this config, so one setting holds for every pair."""
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.rstrip() == 'Core:'), None)
    if start is None:
        return f'Core:{newline}  {MATHS_KEY}: {MATHS}{newline}' + text
    end = start + 1
    while end < len(lines) and (lines[end].startswith((' ', '\t')) or not lines[end].strip()):
        if lines[end].partition(':')[0] == '  ' + MATHS_KEY:
            lines[end] = f'  {MATHS_KEY}: {MATHS}'
            break
        end += 1
    else:
        lines.insert(start + 1, f'  {MATHS_KEY}: {MATHS}')
    return newline.join(lines) + (newline if text.endswith('\n') else '')


def borderless_config(text):

    """`text` (a config.yml) with Vulkan's "Exclusive Fullscreen Mode" set to Disable (RPCS3's "Prefer borderless"): the
    overlay over the game (legacy_roster/hud, a layered window) does not show over exclusive fullscreen. Only that line of the
    Vulkan block changes; a config without the block is left as it is (RPCS3 then uses its own default)."""
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines()
    vulkan = next((i for i, line in enumerate(lines) if line.rstrip() == '  Vulkan:'), None)
    if vulkan is None:
        return text
    for i in range(vulkan + 1, len(lines)):
        if not lines[i].startswith('    '):
            break
        if lines[i].partition(':')[0] == '    Exclusive Fullscreen Mode':
            lines[i] = '    Exclusive Fullscreen Mode: Disable'
            return newline.join(lines) + (newline if text.endswith('\n') else '')
    return text


def config_dir(rpcs3):
    """Where the app's own config goes: the program's folder, except for the Flatpak RPCS3, which cannot see it: there it goes
    into the Flatpak's own folder (the same path inside and outside the sandbox)."""
    if rpcs3.flatpak:
        where = os.path.join(rpcs3.folder, 'online')
        os.makedirs(where, exist_ok=True)
        return where
    return datasource.app_dir('online')


def log_path(rpcs3, posix=os.name != 'nt'):
    """RPCS3's log: log/RPCS3.log in its folder (Windows, a portable copy), else in the cache folder of the system (Linux
    ~/.cache/rpcs3, the Flatpak's own cache, a Mac's ~/Library/Caches/rpcs3). The newest of the files there is, else the first."""
    home = os.path.expanduser('~')
    cache = os.environ.get('XDG_CACHE_HOME') or os.path.join(home, '.cache')
    places = [os.path.join(rpcs3.folder, 'log', 'RPCS3.log')]
    if posix:
        flatpak_cache = os.path.join(home, '.var', 'app', 'net.rpcs3.RPCS3', 'cache', 'rpcs3', 'RPCS3.log')
        places += ([flatpak_cache, os.path.join(cache, 'rpcs3', 'RPCS3.log')] if rpcs3.flatpak
                   else [os.path.join(cache, 'rpcs3', 'RPCS3.log'), os.path.join(home, 'Library', 'Caches', 'rpcs3', 'RPCS3.log'),
                         flatpak_cache])
    there = [p for p in places if os.path.isfile(p)]
    return max(there, key=os.path.getmtime) if there else places[0]


def write_config(rpcs3, title, address, borderless=False):
    """Write the app's own config for booting `title` online (the player's config for the game with the Net block set) to
    online/config_<TITLE>.yml in the program's folder. Returns its path. The player's own files are not touched.
    `borderless`: fullscreen as a borderless window (the overlay over the game, borderless_config)."""
    path = os.path.join(config_dir(rpcs3), f'config_{title}.yml')
    text = maths_config(blit_config(net_config(base_config(rpcs3, title), address)))
    if borderless:
        text = borderless_config(text)
    with open(path + '.tmp', 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    os.replace(path + '.tmp', path)
    return path


def launch_args(rpcs3, title, config, fullscreen=False):
    """The command line that boots `title` from RPCS3 with the app's config `config`, or None when RPCS3 or the game is not
    found. The game is the disc RPCS3 lists (RPCS3 itself runs update 1.01 when it is installed)."""
    disc = rpcs3.game_disc(title)
    command = rpcs3.command()
    if not command or not disc:
        return None
    return command + ['--no-gui'] + (['--fullscreen'] if fullscreen else []) + ['--config', config, disc]


def read_shared(path, limit=None):
    """The text of `path` (RPCS3.log) read with full sharing: RPCS3 keeps it open and a plain open fails on Windows.
    `limit`: stop after about that many bytes (the start of the log is enough for the version line)."""
    return read_shared_bytes(path, limit=limit).decode('utf-8', 'replace')


def read_shared_bytes(path, start=0, limit=None):
    """The bytes of `path` from `start` on, read as read_shared does."""
    if os.name != 'nt':
        with open(path, 'rb') as f:
            f.seek(start)
            return f.read(limit)
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
    k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                             wintypes.LPVOID]
    k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
    handle = k32.CreateFileW(path, 0x80000000, 7, None, 3, 0x80, None)
    if handle in (None, wintypes.HANDLE(-1).value):
        raise OSError(ctypes.get_last_error(), 'cannot open ' + path)
    try:
        if start and not k32.SetFilePointerEx(handle, start, None, 0):
            raise OSError(ctypes.get_last_error(), 'cannot read ' + path)
        out, buf, got = [], ctypes.create_string_buffer(1 << 20), wintypes.DWORD()
        while k32.ReadFile(handle, buf, len(buf), ctypes.byref(got), None) and got.value:
            out.append(buf.raw[:got.value])
            if limit is not None and sum(map(len, out)) >= limit:
                break
    finally:
        k32.CloseHandle(handle)
    return b''.join(out)


_BUILD = re.compile(r'RPCS3 v\d+\.\d+\.\d+-(\d+)-')


def rpcs3_build(rpcs3):
    """The build number of the RPCS3 that wrote `log/RPCS3.log` ('RPCS3 v0.0.43-20402-d00d8023 Alpha' -> 20402), or None: no
    log yet, or rpcs3.exe is newer than the log (RPCS3 was updated and has not been started since)."""
    path = log_path(rpcs3)
    try:
        if rpcs3.exe and os.path.isfile(rpcs3.exe) and os.path.getmtime(rpcs3.exe) > os.path.getmtime(path):
            return None
        found = _BUILD.search(read_shared(path, 4096))
    except OSError:
        return None
    return int(found.group(1)) if found else None


_LOGGED_IN = re.compile(r'rpcn: You are now logged in RPCN\((?P<name>[^|)]+?)\s*\|')
_SIGNALING = 'Failed to get a reply from RPCN signaling'
_PROTOCOL = re.compile(r'rpcn: Server returned protocol version: (\d+), expected: (\d+)')
_REFUSED = re.compile(r'rpcn: (?:Failed to connect|Login error|Authentication failed|Invalid credentials|'
                      r'Failed to (?:login|authenticate))|rpcn: .*(?:Wrong|Invalid) (?:password|token)', re.I)


def log_state(text):
    """What RPCS3's log (from this boot: after the newest 'RPCS3 v' start line) says about the online sign-in:
    {'name': the RPCN name signed in, None if not (any more), 'bound': the game's UDP port 3658 was taken,
     'signaling': False when RPCN's UDP check got no reply (the game then says it is not signed in to the online servers),
     'refused': the line that says the sign-in failed, else None, 'fatal': RPCS3 stopped with a fatal error,
     'old': this RPCS3 is older than the RPCN server (its protocol number is lower than the server's)}."""
    return log_fold(None, text)


def log_fold(state, text):
    """log_state of a log read in pieces: `state` from the pieces before (None at the start), `text` the next whole lines.
    A start line in `text` begins the state anew."""
    marks = [m.start() for m in re.finditer(r'RPCS3 v\d', text)]
    if marks or state is None:
        text = text[marks[-1]:] if marks else text
        state = {'name': None, 'bound': False, 'signaling': True, 'refused': None, 'fatal': False, 'old': False}
    else:
        state = dict(state)
    for line in text.splitlines():
        found = _LOGGED_IN.search(line)
        if found:
            state['name'], state['refused'] = found.group('name').strip(), None
        elif _PROTOCOL.search(line):
            have = _PROTOCOL.search(line)
            state['old'] = int(have.group(2)) < int(have.group(1))
        elif 'rpcn: Disconnected' in line:
            state['name'] = None
        elif 'P2P port' in line and 'was bound' in line:
            state['bound'] = True
        elif _SIGNALING in line:
            state['signaling'] = False
        elif _REFUSED.search(line):
            state['refused'] = line.split('rpcn:', 1)[-1].strip()
        elif 'Fatal Error' in line or 'RPCS3: Fatal' in line:
            state['fatal'] = True
    return state


class LogTail:
    """RPCS3.log read a piece at a time: each look reads only what was added since the last one (the log grows to many MB while
    the game runs). A log that got shorter is a new one (RPCS3 started again): read from its start."""

    def __init__(self, path):
        self.path, self.pos, self.rest, self.state = path, 0, b'', None

    def read(self):
        size = os.path.getsize(self.path)
        if size < self.pos:
            self.pos, self.rest, self.state = 0, b'', None
        if size == self.pos and self.state is not None:
            return self.state
        new = read_shared_bytes(self.path, self.pos)
        self.pos += len(new)
        data = self.rest + new
        cut = data.rfind(b'\n') + 1                     # a line still being written waits for its end
        self.rest = data[cut:]
        self.state = log_fold(self.state, data[:cut].decode('utf-8', 'replace'))
        return self.state


def roster_check(data):
    """The friend's roster save `data` is read as a roster before it is put in the game folder (the CRC fits, the tables parse,
    the team table is no bigger than the game's). Returns its CRC; raises ValueError for anything else."""
    crc = roster_crc(data)
    from . import roster as roster_module
    try:
        parsed = roster_module.Roster(data)
        if parsed.T.cur_rec > 252:
            raise ValueError("too many teams")
    except (ValueError, KeyError, IndexError, struct.error, AttributeError, OverflowError) as err:
        raise ValueError(f"not a roster save ({err})") from err
    return crc


def roster_crc(data):
    """The CRC in the header of the roster save `data` (SYS-DATA bytes) as eight hex digits; the official online roster is
    told by it. Raises ValueError for something that is not a roster save."""
    if len(data) < 0x30:
        raise ValueError("file too short to be a save")
    size, stored = struct.unpack_from('>II', data, 0x24)
    if tdb.crc32_bzip2(data[0x2C:0x2C + size]) != stored:
        raise ValueError("section CRC mismatch -- not a supported save")
    return f'{stored:08x}'
