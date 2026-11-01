"""The lobby client of online play (private/Multiplayer.txt sections 4 D3/D6 and 5 Phase 1): the app's side of the server's small HTTPS API.
Standard library only. One request per call, no retries (the tab polls every 2 s). The lobbies live in the server's memory; the
ranks are worked out from the match reports the games send (0.90.0, docs/notes/online-match-reports.md).

The API (the server is Overtime, Overtime.Lobby/LobbyApi.cs; tests/fake_lobby.py answers the same):

    POST   <API>/lobby              {name, crc, patch, version, rpcs3, is_public, roster_name} -> a lobby (the caller is its host;
                                    is_public lists it for everybody, roster_name is shown in the list)
    GET    <API>/lobbies            -> [{code, host, roster_name, patch, version, roster_size, age_seconds, members, max}]: the public
                                    lobbies waiting for a friend (open, the host alone, his roster sent), newest first
    POST   <API>/lobby/<code>/join  {name, crc, patch, version, rpcs3}  -> the lobby (the caller is its guest)
    GET    <API>/lobby/<code>?name=  -> the lobby
    POST   <API>/lobby/<code>/ready {name, ready}                -> the lobby
    POST   <API>/lobby/<code>/leave {name}                       -> {}
    POST   <API>/lobby/<code>/me    {name, crc, patch, version, rpcs3}  -> the lobby (a member's roster / patch changed; his Ready goes)
    PUT    <API>/lobby/<code>/roster?name=  gzip bytes           -> the lobby (the host sends his roster)
    GET    <API>/lobby/<code>/roster?name=                       -> the host's roster (gzip bytes)
    POST   <API>/lobby/<code>/say   {name, text}                 -> the lobby (0.90: its `chat` gets the line)
    GET    <API>/board                                           -> {players, ranked, highlights, recent, tiers, placement, updated}
    GET    <API>/board/player?name=                              -> a player's card (404 unknown; a hidden one only to himself)
    GET    <API>/history?name=&limit=                            -> his matches, newest first
    POST   <API>/board/hide     {name, hidden}                   -> {name, hidden} (showing again needs his own token)

    a lobby = {code, state: open | starting | playing | expired, reason: why it cannot start (a text) or None,
               members: [{name, role: host | guest, roster_ok, patch_ok, ready, progress, patch, version, rpcs3}],
               roster: {crc, size} of the host's uploaded roster, or None, chat: [{seq, name, text, at}] (0.90 servers)}
    The host is the reference: a guest is roster_ok with the host's roster CRC and patch_ok with the host's patch. patch is the
    patch version ("0.26") or "none"; a host's expired lobby (he left) says state "expired".
    rpcs3 = the member's RPCS3 build number as text, '' when unknown: shown to the friend, never a gate. The game (version, "EU 01.00": the
    region and the game version) must be the host's, or the lobby says so and nobody can start; a member without the game patch (patch "none") cannot be Ready.
    progress = in_game | signed_in | hosting | browsing | joined | playing | gone (the server's view of that member)

The identity is the RPCN name the app reports (trust, as the community servers do), but acting for a member needs his secret: create
and join answer with a `token`, which this module keeps (never in the lobby it returns) and sends as the header X-Lobby-Token with
every later request for that lobby and name; a request without it is answered 403 not_member. An error answers with the HTTP status
4xx and {error, message}; LobbyError carries both. A server from before 0.90 answers the ranks and chat routes 404 with no body
(code http404): `missing` says so, and the tab then hides what needs them. D3 / D6 say who pairs: the host presses Create Game Session in the game,
the guest Browse then Join; the server shows the guest only the host's session.
"""
import gzip
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import zlib

from . import datasource

API_URL = "https://legacy.puckpeak.com/api"      # LEGACY_ROSTER_ONLINE_URL names another one (tests, a lab server)
TIMEOUT = 8
ROSTER_TIMEOUT = 90                              # a roster is about 1 MB gzipped
LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"             # a code is six of these (no I and O, no digits to mix up)
MAX_ROSTER = 48 * 1024 * 1024                    # a roster save is a few MB unpacked; more than this is not one (a friend's gzip bomb)
STATES = ('open', 'starting', 'playing', 'expired')


class LobbyError(Exception):
    """The server answered no: `code` is its short word (full, unknown, closed, mismatch ...), the message is for the player."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Unreachable(LobbyError):
    """The server could not be reached (no internet, the server down): the lobby may still be there."""

    def __init__(self, message="Puck Peak's online server is not reachable right now."):
        super().__init__('unreachable', message)


def api_url():
    url = os.environ.get('LEGACY_ROSTER_ONLINE_URL') or API_URL
    return url.rstrip('/')


def clean_code(text):
    """The lobby code in `text` as typed (spaces, dashes and small letters allowed), or None when it is not six letters of LETTERS."""
    code = ''.join(c for c in (text or '').upper() if c.isalnum())
    return code if len(code) == 6 and all(c in LETTERS for c in code) else None


_tokens = {}            # (code, name in lower case) -> the secret the server gave that member; only in memory


def _key(code, name):
    return (str(code).upper(), str(name).lower())


def _own_token(name):
    """Any token this app holds for `name` (in any lobby): proof to the ranks routes that the caller is that player."""
    return next((t for (code, who), t in _tokens.items() if who == str(name).lower() and t), None)


def missing(err):
    """Does `err` mean the server lacks the route (a server from before 0.90) or cannot be reached? Then the part is just not there."""
    return isinstance(err, Unreachable) or getattr(err, 'code', None) in ('http404', 'http405', 'http501')


def _request(method, path, data=None, content_type='application/json', timeout=TIMEOUT, token=None):
    headers = {'Content-Type': content_type, 'User-Agent': 'PuckPeakLegacyUpdater'}
    if token:
        headers['X-Lobby-Token'] = token
    req = urllib.request.Request(api_url() + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=datasource.tls_context()) as r:
            return r.read()
    except urllib.error.HTTPError as err:
        try:
            said = json.loads(err.read())
        except ValueError:
            said = {}
        raise LobbyError(said.get('error') or f'http{err.code}', said.get('message') or f"The server said {err.code}.") from err
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise Unreachable() from err


def _call(method, path, body=None, member=None, token=None):
    """`member` = (code, name) when the request is that member's: his token goes with it; a token the server hands out is kept."""
    data = None if body is None else json.dumps(body).encode()
    try:
        found = json.loads(_request(method, path, data, token=_tokens.get(_key(*member)) if member else token) or b'{}')
    except ValueError as err:
        raise Unreachable() from err
    except LobbyError as err:
        if member and err.code in ('unknown', 'not_member'):
            _tokens.pop(_key(*member), None)
        raise
    if isinstance(found, dict) and 'token' in found:
        token = found.pop('token')
        if token and member and found.get('code'):
            _tokens[_key(found['code'], member[1])] = token
    return found


def _who(name, crc, patch, version, rpcs3=''):
    """`rpcs3`: the build number of the caller's RPCS3 as text ('' when not known); the friend is told, nothing is gated."""
    return {'name': name, 'crc': crc, 'patch': patch, 'version': version, 'rpcs3': str(rpcs3 or '')}


def create(name, crc, patch, version, public=True, roster_name='', rpcs3=''):
    """Open a lobby; the caller is its host. Returns the lobby (its code to share). A public one is in everybody's list."""
    body = _who(name, crc, patch, version, rpcs3)
    body.update({'is_public': bool(public), 'roster_name': roster_name or ''})
    return _call('POST', '/lobby', body, member=('', name))


def lobbies():
    """The public lobbies waiting for a friend (see the API above)."""
    found = _call('GET', '/lobbies')
    return found if isinstance(found, list) else []


def join(code, name, crc, patch, version, rpcs3=''):
    return _call('POST', f'/lobby/{code}/join', _who(name, crc, patch, version, rpcs3), member=(code, name))


def status(code, name):
    return _call('GET', f'/lobby/{code}?name={urllib.parse.quote(name)}', member=(code, name))


def ready(code, name, on):
    return _call('POST', f'/lobby/{code}/ready', {'name': name, 'ready': bool(on)}, member=(code, name))


def leave(code, name):
    try:
        return _call('POST', f'/lobby/{code}/leave', {'name': name}, member=(code, name))
    finally:
        _tokens.pop(_key(code, name), None)


def update_me(code, name, crc, patch, version, rpcs3=''):
    """The caller's roster or patch changed (he copied the host's roster, or patched): the lobby, with his Ready mark taken back."""
    return _call('POST', f'/lobby/{code}/me', _who(name, crc, patch, version, rpcs3), member=(code, name))


def put_roster(code, name, data):
    """The host sends his roster (`data`: a SYS-DATA file); it travels gzipped. Returns the lobby."""
    packed = gzip.compress(data, 6, mtime=0)
    try:
        return json.loads(_request('PUT', f'/lobby/{code}/roster?name={urllib.parse.quote(name)}', packed,
                                   'application/octet-stream', ROSTER_TIMEOUT, _tokens.get(_key(code, name))) or b'{}')
    except ValueError as err:
        raise Unreachable() from err


def get_roster(code, name):
    """The host's roster as a SYS-DATA file (the friend takes it)."""
    packed = _request('GET', f'/lobby/{code}/roster?name={urllib.parse.quote(name)}', None, timeout=ROSTER_TIMEOUT,
                      token=_tokens.get(_key(code, name)))
    try:
        unpacker = zlib.decompressobj(16 + zlib.MAX_WBITS)
        data = unpacker.decompress(packed, MAX_ROSTER + 1)
        if len(data) > MAX_ROSTER or unpacker.unconsumed_tail or not unpacker.eof:
            raise ValueError("too big or cut off")
        return data
    except (zlib.error, ValueError) as err:
        raise LobbyError('bad_roster', "The roster did not arrive correctly. Try again.") from err


def say(code, name, text):
    """One chat line to the lobby. Returns the lobby (its `chat`); slow_down when the last line was a moment ago."""
    return _call('POST', f'/lobby/{code}/say', {'name': name, 'text': text}, member=(code, name))


def board():
    """The public leaderboard (see the API above)."""
    found = _call('GET', '/board')
    return found if isinstance(found, dict) else {}


def card(name):
    """`name`'s rank card (rating, tier, record, next tier); LobbyError 'unknown' when he has no rated game yet (or hid himself
    and this app holds no token of his)."""
    return _call('GET', f'/board/player?name={urllib.parse.quote(name)}', token=_own_token(name))


def history(name, limit=20):
    """`name`'s matches, newest first: [{id, at, status, why, opponent, team, opp_team, for, against, result, delta, waiting}]."""
    found = _call('GET', f'/history?name={urllib.parse.quote(name)}&limit={int(limit)}', token=_own_token(name))
    return found if isinstance(found, list) else []


def match(mid):
    """One match's box score: {id, at, status, why, sides: [{name, team, score, home, stats: {tag: number}}]}, home first; the stats
    are the game's versus stats (CPRT) as each player's game reported them. LobbyError 'unknown' for an id the server lacks."""
    found = _call('GET', f'/match?id={urllib.parse.quote(str(mid), safe="")}')
    return found if isinstance(found, dict) else {}


def hide(name, hidden):
    """Take `name` off the public board (anyone may), or put him back (only with his own token: be in a lobby)."""
    return _call('POST', '/board/hide', {'name': name, 'hidden': bool(hidden)}, token=_own_token(name))
