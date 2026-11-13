"""Is a newer version of the program out? Look at the project's newest GitHub release; if it is newer, offer to
swap the exe for it. Standard library only. Nothing here touches a roster or a save.

Only the Windows exe replaces itself. Everything else (a Mac, Linux, the command line, running from source)
is told that a new version exists and given the release page."""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

from .. import __version__, datasource, savedata

REPO = "MatusRiedl/nhl-legacy-pc-online-blueline"
# a test (or a fork) can point the check at its own JSON, a release made like GitHub's
RELEASE_URL = os.environ.get('LEGACY_ROSTER_RELEASE_URL') or f"https://api.github.com/repos/{REPO}/releases/latest"
EXE_ASSET = 'BluelineLegacy.exe'                # the name since 0.98.0 (owner, 2026-11-13)
PREV_EXE_ASSET = 'PuckPeakLegacyUpdater.exe'     # 0.80.1 to 0.97.1: their check looks only for it (and the one below), so the
                                                 # release carries the exe under this name too (packaging/build.ps1)
OLD_EXE_ASSET = 'NHLLegacyRosterUpdater.exe'     # the name until 0.80.0; 0.80.1's release carries the exe under both
SUMS_ASSET = 'SHA256SUMS.txt'
CHUNK = 256 * 1024


class Release:
    def __init__(self, version, tag, notes, page, exe_url=None, size=0, digest=None):
        self.version, self.tag, self.notes, self.page = version, tag, notes, page
        self.exe_url, self.size, self.digest = exe_url, size, digest

    @property
    def text(self):
        return '.'.join(str(n) for n in self.version)

    def can_install(self):
        return bool(self.exe_url and self.digest)


def parse_version(text):
    """'v0.11.0' or '0.11' -> (0, 11, 0); None when it is not a version."""
    m = re.match(r'^\s*v?(\d+)\.(\d+)(?:\.(\d+))?\s*$', text or '')
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def _digest_of(asset):
    value = (asset or {}).get('digest') or ''
    return value.split(':', 1)[1].lower() if value.startswith('sha256:') else None


def _digest_from_sums(text, name):
    for line in (text or '').splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip('*') == name and re.fullmatch(r'[0-9a-fA-F]{64}', parts[0]):
            return parts[0].lower()
    return None


def from_json(data, fetch_text=None):
    """A Release from GitHub's 'latest release' answer; None for a draft, a prerelease or nonsense."""
    if not isinstance(data, dict) or data.get('draft') or data.get('prerelease'):
        return None
    version = parse_version(data.get('tag_name'))
    if version is None:
        return None
    assets = {a.get('name'): a for a in data.get('assets') or [] if isinstance(a, dict)}
    name = next((n for n in (EXE_ASSET, PREV_EXE_ASSET) if n in assets), OLD_EXE_ASSET)
    exe = assets.get(name)
    digest = _digest_of(exe)
    if exe and not digest and SUMS_ASSET in assets and fetch_text:
        try:
            digest = _digest_from_sums(fetch_text(assets[SUMS_ASSET].get('browser_download_url')), name)
        except Exception:
            digest = None
    return Release(version, data['tag_name'], (data.get('body') or '').strip(), data.get('html_url') or f"https://github.com/{REPO}/releases",
                   exe.get('browser_download_url') if exe else None, int((exe or {}).get('size') or 0), digest)


answered = False    # did GitHub answer the last look? (Setup's "Up to date" tick only then, 0.98.1)


def latest(current=__version__, fetch_json=None, fetch_text=None):
    """The newest release when it is newer than `current`, else None (also when GitHub cannot be reached)."""
    global answered
    answered = False
    fetch_json = fetch_json or datasource.http_json
    fetch_text = fetch_text or (lambda url: datasource.http_get(url, timeout=20, retries=1).decode('utf-8', 'replace'))
    try:
        release = from_json(fetch_json(RELEASE_URL), fetch_text)
    except Exception:           # offline, rate limited, not published yet: say nothing
        return None
    answered = True
    have = parse_version(current)
    return release if release and have and release.version > have else None


def due(settings):
    """Look at this start? At every start unless the player switched it off (owner, 0.50.3: before, at most every 12
    hours, so a version released the same day was not offered)."""
    return settings.get('check_updates', True) is not False


# --- replacing the exe ------------------------------------------------------------------------------
def running_exe():
    """The path of the exe that runs, or None when this is not the Windows exe (source, Mac, Linux)."""
    return os.path.abspath(sys.executable) if savedata.WINDOWS and getattr(sys, 'frozen', False) else None


def can_replace(exe=None):
    exe = exe or running_exe()
    if not exe or not os.path.isfile(exe):
        return False
    folder = os.path.dirname(exe)
    probe = os.path.join(folder, '.write-test')
    try:
        with open(probe, 'wb'):
            pass
        os.remove(probe)
        return True
    except OSError:
        return False


def clean_leftovers(exe=None):
    """Remove the old exe and a half-finished download left by an earlier update. Versions 0.10.0-0.10.2 could not
    close their window after an update; that copy (the `.old` exe, only ever downloading) is ended first."""
    exe = exe or running_exe()
    if not exe:
        return
    try:
        savedata.end_process_of(exe + '.old')
    except Exception:
        pass
    for suffix in ('.old', '.new'):
        try:
            os.remove(exe + suffix)
        except OSError:
            pass


def download(release, target, progress=None):
    """Download the release's exe to `target`; delete it and raise ValueError if it is not the file that was published."""
    req = urllib.request.Request(release.exe_url, headers={'User-Agent': 'Mozilla/5.0 (NHLLegacyRosterUpdater)'})
    sha = hashlib.sha256()
    got = 0
    try:
        with urllib.request.urlopen(req, timeout=60, context=datasource.tls_context()) as r, open(target, 'wb') as out:
            total = int(r.headers.get('Content-Length') or release.size or 0)
            while True:
                block = r.read(CHUNK)
                if not block:
                    break
                out.write(block)
                sha.update(block)
                got += len(block)
                if progress and total:
                    progress(min(1.0, got / total))
        if sha.hexdigest() != release.digest:
            raise ValueError("The downloaded file is not the one that was published, so it was not used.")
    except BaseException:
        try:
            os.remove(target)
        except OSError:
            pass
        raise


def swap(new_path, exe):
    """Put the downloaded exe in place of the running one (Windows lets a running exe be renamed)."""
    old = exe + '.old'
    try:
        os.remove(old)
    except OSError:
        pass
    os.replace(exe, old)
    try:
        os.replace(new_path, exe)
    except OSError:
        os.replace(old, exe)        # put the working one back
        raise


def restart(exe):
    """Start the (new) exe the way a double-click would, free of this program's unpacked folder."""
    flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    savedata.launch([exe], close_fds=True, creationflags=flags, cwd=os.path.dirname(exe))


def install(release, progress=None):
    """Download, check and swap in the new exe, then start it. Returns when the new one runs: the caller quits."""
    exe = running_exe()
    if not exe or not release.can_install() or not can_replace(exe):
        raise RuntimeError("This copy cannot replace itself.")
    new = exe + '.new'
    download(release, new, progress)
    swap(new, exe)
    restart(exe)
