"""The update check: versions, GitHub's answer, the checksum, the swap of the exe."""
import hashlib
import http.server
import threading

import pytest

from legacy_roster.app import selfupdate as U


def release_json(tag='v0.11.0', digest=None, **extra):
    asset = {'name': U.EXE_ASSET, 'browser_download_url': 'http://x/exe', 'size': 3}
    if digest:
        asset['digest'] = 'sha256:' + digest
    data = {'tag_name': tag, 'html_url': 'http://x/page', 'body': '# New\n- a thing', 'assets': [asset]}
    data.update(extra)
    return data


def test_parse_version():
    assert U.parse_version('v0.11.0') == (0, 11, 0)
    assert U.parse_version('0.10') == (0, 10, 0)
    assert U.parse_version('v0.9.2-beta') is None
    assert U.parse_version(None) is None
    assert U.parse_version('0.10.0') < U.parse_version('0.11.0') < U.parse_version('0.100.0')


def test_latest_only_when_newer():
    assert U.latest('0.10.0', lambda url: release_json('v0.11.0')).text == '0.11.0'
    assert U.latest('0.11.0', lambda url: release_json('v0.11.0')) is None
    assert U.latest('0.12.0', lambda url: release_json('v0.11.0')) is None


def test_latest_ignores_drafts_prereleases_and_errors():
    assert U.latest('0.10.0', lambda url: release_json(prerelease=True)) is None
    assert U.latest('0.10.0', lambda url: release_json(draft=True)) is None

    def offline(url):
        raise OSError("no connection")
    assert U.latest('0.10.0', offline) is None
    assert U.latest('0.10.0', lambda url: ['not', 'a', 'release']) is None


def test_digest_from_the_asset_or_the_sums_file():
    digest = 'ab' * 32
    assert U.from_json(release_json(digest=digest)).digest == digest
    assert U.from_json(release_json(digest=digest)).can_install()
    plain = release_json()
    assert not U.from_json(plain).can_install()
    plain['assets'].append({'name': U.SUMS_ASSET, 'browser_download_url': 'http://x/sums'})
    sums = f"{digest}  {U.EXE_ASSET}\n"
    assert U.from_json(plain, lambda url: sums).digest == digest
    assert U.from_json(plain, lambda url: "nonsense").digest is None


def test_the_new_exe_name_first_and_the_old_one_still_works():
    """0.80.1 renamed the exe; its release carries both names (old copies look for theirs), later ones may not."""
    old, new = 'aa' * 32, 'bb' * 32
    both = release_json(digest=new)
    both['assets'].append({'name': U.OLD_EXE_ASSET, 'browser_download_url': 'http://x/old', 'size': 3,
                           'digest': 'sha256:' + old})
    assert U.from_json(both).exe_url == 'http://x/exe' and U.from_json(both).digest == new
    only_old = release_json(digest=old)
    only_old['assets'][0]['name'] = U.OLD_EXE_ASSET
    assert U.from_json(only_old).can_install()


def test_blueline_takes_its_own_name_then_the_puck_peak_name():
    """0.98.0 named the exe BluelineLegacy.exe; its release also carries PuckPeakLegacyUpdater.exe for 0.80.1 to 0.97.1."""
    both = release_json(digest='bb' * 32)
    both['assets'].append({'name': U.PREV_EXE_ASSET, 'browser_download_url': 'http://x/prev', 'size': 3,
                           'digest': 'sha256:' + 'cc' * 32})
    assert U.EXE_ASSET == 'BluelineLegacy.exe' and U.from_json(both).exe_url == 'http://x/exe'
    only_prev = release_json(digest='cc' * 32)
    only_prev['assets'][0]['name'] = U.PREV_EXE_ASSET
    assert U.from_json(only_prev).exe_url == 'http://x/exe' and U.from_json(only_prev).can_install()


def test_due_at_every_start_and_not_when_switched_off():
    assert U.due({}) and U.due({'check_updates': True})
    assert U.due({'update_checked': 10 ** 12})          # a look a moment ago (0.50.2 and older waited 12 hours)
    assert not U.due({'check_updates': False})


@pytest.fixture
def server(tmp_path):
    body = b'new program'
    served = {'body': body}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Length', str(len(served['body'])))
            self.end_headers()
            self.wfile.write(served['body'])

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/exe", served
    httpd.shutdown()


def test_download_checks_the_checksum(server, tmp_path):
    url, served = server
    good = U.Release((0, 11, 0), 'v0.11.0', '', 'p', url, 0, hashlib.sha256(served['body']).hexdigest())
    seen = []
    target = tmp_path / 'x.new'
    U.download(good, str(target), seen.append)
    assert target.read_bytes() == b'new program' and seen and seen[-1] == 1.0

    bad = U.Release((0, 11, 0), 'v0.11.0', '', 'p', url, 0, '0' * 64)
    other = tmp_path / 'y.new'
    with pytest.raises(ValueError):
        U.download(bad, str(other))
    assert not other.exists()          # a file that is not the published one is not kept


def test_swap_replaces_and_keeps_the_old_one(tmp_path):
    exe, new = tmp_path / 'app.exe', tmp_path / 'app.exe.new'
    exe.write_bytes(b'old')
    new.write_bytes(b'new')
    U.swap(str(new), str(exe))
    assert exe.read_bytes() == b'new' and (tmp_path / 'app.exe.old').read_bytes() == b'old'
    U.clean_leftovers(str(exe))
    assert not (tmp_path / 'app.exe.old').exists()


def test_swap_puts_the_old_exe_back_when_the_new_one_is_missing(tmp_path):
    exe = tmp_path / 'app.exe'
    exe.write_bytes(b'old')
    with pytest.raises(OSError):
        U.swap(str(tmp_path / 'missing.new'), str(exe))
    assert exe.read_bytes() == b'old'


def test_a_source_run_cannot_replace_itself():
    assert U.running_exe() is None
    with pytest.raises(RuntimeError):
        U.install(U.Release((9, 0, 0), 'v9', '', 'p', 'http://x', 1, 'a' * 64))
