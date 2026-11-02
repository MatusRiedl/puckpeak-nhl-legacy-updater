"""careersave: a made-up Be a Pro career (no game data) read, changed and built again; with LEGACY_ROSTER_CAREERS (a
folder holding copies of Be a Pro saves, never a real savedata folder) every copy must come back byte for byte."""
import os
import struct
import zlib

import pytest

from legacy_roster import careersave as K
from legacy_roster import tdb
from legacy_roster.tdb import crc32_bzip2
from legacy_roster.verify import career_problems
from tests.test_seasonsave import _table, later, save_bytes, write_save

BIO_INDEX = 4389
RATINGS = [33 + i % 20 for i in range(len(K.RATINGS))]          # raw: 69 ... the game's value - 36


def _chunk(kind, body, version=1):
    return struct.pack('>IIII', kind, version, len(body), crc32_bzip2(body)) + body


def pro_chunk():
    c8 = bytearray(4096)
    c8[0:4], c8[0x19:0x1E], c8[0x32:0x38] = b'Theo', b'Lpro1', b'REGINA'
    struct.pack_into('>HHH', c8, K.AT['year'], 2007 - 11, BIO_INDEX, 0xFFFF)
    c8[K.AT['overall']] = 33
    c8[K.AT['ratings']:K.AT['ratings'] + len(RATINGS)] = bytes(r - 1 for r in RATINGS)    # the career's first values
    c8[K.AT['type']], c8[K.AT['jersey']] = 6, 88
    return bytes(c8)


def career_bytes(tail=b'', spent=(0, 0, 0), first=1):
    """A Be a Pro save's bytes: a small league database with the pro's bio and skater rows, then five chunks; chunk 24
    holds the XP earned (699 / 678 / 623 more than `spent`) and spent. `first`: the version of the first chunk."""
    other = {K.INDEX: 12, K.FIRST: 'Other', K.LAST: 'Player'}
    bio = _table(K.BIO, [(K.FIRST, 200, 1), (K.LAST, 200, 1), (K.INDEX, 13, 0)],
                 [other, {K.INDEX: BIO_INDEX, K.FIRST: 'Theo', K.LAST: 'Lpro1'}], 8)
    fields = [(K.INDEX, 13, 0)] + [(K.TAGS[kind][name], 6, 0) for kind in 'ces' for name in K.RATINGS]
    rows = [{K.INDEX: BIO_INDEX, **{K.TAGS[kind][n]: v for kind in 'ces' for n, v in zip(K.RATINGS, RATINGS)}}]
    skater = _table(K.SKATER, fields, rows, 8)
    raw = bytearray(save_bytes([bio, skater], magic=K.MAGIC))
    earned = [n + s for n, s in zip((699, 678, 623), spent)]
    xp = struct.pack('>11I', *earned, *spent, 0, 0, 0, 0xFFFFFFFF, 0xFFFFFFFF)
    raw += _chunk(2, bytes(range(16)), first) + _chunk(K.PRO_CHUNK, pro_chunk()) + _chunk(20, struct.pack('>I', BIO_INDEX))
    raw += _chunk(K.XP_CHUNK, xp) + _chunk(29, b'\xff' * 20)
    end = len(raw)
    raw += tail
    struct.pack_into('>I', raw, 0x10, zlib.crc32(raw[0x1C:end]))
    return bytes(raw)


def test_a_career_comes_back_byte_for_byte_and_shows_the_pro():
    raw = career_bytes()
    c = K.Career(raw)
    assert c.build() == raw
    p = c.pro
    assert (p.first, p.last, p.birthplace, p.year, p.bio, p.game_id) == ('Theo', 'Lpro1', 'REGINA', 1996, BIO_INDEX, None)
    assert p.overall == 69 and p.type == 6 and p.jersey == 88 and not p.goalie
    assert p.ratings['acceleration'] == 69 and p.ratings['passing'] == RATINGS[14] + 36
    assert p.xp == {'offense': 699, 'defense': 678, 'athletic': 623}
    assert c.bio_row() == 1 and c.skater_row() == 0


def test_a_career_of_update_1_01_is_read_too():
    """Its chunk 2 has version 2: the Native port's first career was called damaged (lab round 59)."""
    raw = career_bytes(first=2)
    c = K.Career(raw)
    assert c.build() == raw and len(c.chunks) == 5 and c.pro.xp['offense'] == 699
    c.set_xp({'offense': 5000})
    new = c.build()
    assert K.Career(new).pro.xp['offense'] == 5000 and career_problems(raw, new, ['xp']) == []


def test_old_bytes_after_the_last_chunk_stay_and_the_header_crc_stops_before_them():
    raw = career_bytes(tail=b'\x5a' * 2000)
    c = K.Career(raw)
    assert c.build() == raw and c.tail == b'\x5a' * 2000
    assert struct.unpack_from('>I', raw, 0x10)[0] != zlib.crc32(raw[0x1C:])       # tdb's own rule would be wrong here


def test_xp_and_name_change_only_their_bytes():
    raw = career_bytes()
    c = K.Career(raw)
    c.set_xp({'offense': 1699})
    c.set_name(first='Teo')
    new = c.build()
    assert len(new) == len(raw)
    back = K.Career(new)
    assert back.pro.xp == {'offense': 1699, 'defense': 678, 'athletic': 623}
    assert back.pro.name == 'Teo Lpro1' and back.pro.ratings == c.pro.ratings
    bio = back.db.tables[K.BIO]
    assert bio.get(1, K.FIRST) == 'Teo' and bio.get(0, K.FIRST) == 'Other'
    assert [ch.body for ch in back.chunks if ch.kind not in (K.PRO_CHUNK, K.XP_CHUNK)] == \
        [ch.body for ch in K.Career(raw).chunks if ch.kind not in (K.PRO_CHUNK, K.XP_CHUNK)]


def test_the_career_check_lets_through_only_the_edits_made():
    raw = career_bytes()
    assert career_problems(raw, raw) == []
    c = K.Career(raw)
    c.set_xp({'athletic': 5000})
    xp = c.build()
    assert career_problems(raw, xp, ['xp'], sizes=[len(raw)]) == []
    assert any('part 24' in p for p in career_problems(raw, xp))
    c.set_name(last='Nowak')
    both = c.build()
    assert career_problems(raw, both, ['xp', 'name']) == []
    named = career_problems(raw, both, ['xp'])
    assert any('part 8' in p for p in named) and any('row 1' in p for p in named)
    assert career_problems(raw, both, ['xp', 'name'], sizes=[len(raw) - 9])           # files of another size
    c = K.Career(raw)
    c.chunk(2)[3] ^= 1                                          # a part no edit touches
    assert any('part 2' in p for p in career_problems(raw, c.build(), ['xp', 'name']))
    c = K.Career(raw)
    c.db.tables[K.BIO].set(0, K.LAST, 'Someone')                # another player's row
    assert any('row 0' in p for p in career_problems(raw, c.build(), ['name']))
    assert career_problems(raw, raw[:-1] + b'\0')               # the last chunk damaged
    assert career_problems(raw, raw, ['looks'])                  # not an edit careersave knows


def test_xp_to_spend_is_earned_minus_spent_and_a_change_raises_the_earned():
    raw = career_bytes(spent=(685, 595, 315))
    c = K.Career(raw)
    assert c.pro.xp == {'offense': 699, 'defense': 678, 'athletic': 623}
    assert c.pro.earned['offense'] == 1384 and c.pro.spent['athletic'] == 315
    c.set_xp({'offense': 1199})
    new = c.build()
    words = struct.unpack_from('>6I', K.Career(new).chunk(K.XP_CHUNK))
    assert words == (685 + 1199, 678 + 595, 623 + 315, 685, 595, 315)          # the spent words stay
    assert K.Career(new).pro.xp['offense'] == 1199
    assert career_problems(raw, new, ['xp']) == []


def test_ratings_are_the_databases_and_a_change_writes_only_the_pros_c_ratings():
    raw = career_bytes()
    c = K.Career(raw)
    assert c.pro.ratings['passing'] == RATINGS[14] + 36                         # not chunk 8's (one lower)
    c.set_ratings({'passing': 95, 'speed': 40})
    new = c.build()
    back = K.Career(new)
    assert back.pro.ratings['passing'] == 95 and back.pro.ratings['speed'] == 40
    assert bytes(back.chunk(K.PRO_CHUNK)) == bytes(K.Career(raw).chunk(K.PRO_CHUNK))       # chunk 8 as it was
    t = back.db.tables[K.SKATER]
    assert t.get(0, K.TAGS['e']['passing']) == RATINGS[14]                      # e_ / s_ keep the first values
    assert career_problems(raw, new, ['ratings']) == []
    assert any('row 0' in p for p in career_problems(raw, new, ['xp']))
    for bad in (39, 100):
        with pytest.raises(K.CareerError):
            K.Career(raw).set_ratings({'passing': bad})
    with pytest.raises(K.CareerError):
        K.Career(raw).set_ratings({'blocker': 80})
    c = K.Career(raw)
    c.db.tables[K.SKATER].set(0, K.TAGS['c']['speed'], 38 - 36)                 # a value the window never types
    assert any('speed is 38' in p for p in career_problems(raw, c.build(), ['ratings']))


def test_the_load_list_label_follows_a_last_name_the_game_made_it_from(tmp_path):
    raw = career_bytes()
    made = K.Save(write_save(str(tmp_path), 'BLES021530502', raw, "O'BRIEN3"))
    own = K.Save(write_save(str(tmp_path), 'BLES021530503', raw, 'MY CAREER'))
    assert K.sub_title('BLES021530500', 'Di Nicola') == 'DI NICOLA1'
    assert K.renamed_label(made, "O'Brien", 'Nowak') == 'NOWAK3'
    assert K.renamed_label(made, "O'Brien", "O'Brien") is None and K.renamed_label(own, 'Lpro1', 'Nowak') is None


@pytest.mark.parametrize('pools, first', [({'offense': -1}, None), ({'defense': K.MAX_XP + 1}, None),
                                          ({}, ''), ({}, 'X' * K.NAME_SIZE), ({}, 'Žluťoučký')])
def test_impossible_changes_are_refused(pools, first):
    c = K.Career(career_bytes())
    with pytest.raises(K.CareerError):
        c.set_xp(pools)
        c.set_name(first=first)


def test_damaged_or_other_saves_are_refused():
    raw = bytearray(career_bytes())
    with pytest.raises(K.CareerError):
        K.Career(b'PS3SeasonFile'.ljust(16, b'\0') + bytes(raw[16:]))
    raw[-5] ^= 1                                                # inside the last chunk: its CRC no longer fits
    with pytest.raises(K.CareerError):
        K.Career(bytes(raw))


def test_pieces_keep_the_files_split():
    raw = career_bytes()
    assert b''.join(K.pieces(raw)) == raw and K.pieces(raw, [len(raw)]) == [raw]
    assert K.pieces(raw, [9, len(raw) - 9]) == [raw[:9], raw[9:]]
    with pytest.raises(K.CareerError):
        K.pieces(raw, [len(raw) - 1])


def test_finds_only_be_a_pro_careers_and_waits_for_the_game_to_finish(tmp_path):
    raw = career_bytes()
    a = write_save(str(tmp_path), 'BLES021530500', raw, 'LPRO11', chunk=K.PIECE, when=1_700_000_000)
    b = write_save(str(tmp_path), 'BLUS315400503', raw, 'LPRO14', chunk=K.PIECE, when=1_700_000_500)
    write_save(str(tmp_path), 'BLES021531000', raw, 'SEASON1')                     # not a Be a Pro folder
    write_save(str(tmp_path), 'BLES021530501', b'PS3SeasonFile'.ljust(64, b'\0'), 'X')  # not a Be a Pro file
    assert [s.folder for s in K.find(str(tmp_path))] == ['BLUS315400503', 'BLES021530500']
    assert [s.folder for s in K.find(str(tmp_path), ['BLES02153'])] == ['BLES021530500']
    with pytest.raises(K.CareerError):
        K.read(a, now=1_700_000_002)                                                # written 2 s ago
    c = K.read(b, now=later(b))
    assert c.pro.last == 'Lpro1' and c.pieces == [len(raw)]
    assert b''.join(K.pieces(c.build(), c.pieces)) == raw


def _copies(root):
    for here, _dirs, files in os.walk(root):
        if 'DATA0000' in files:
            with open(os.path.join(here, 'DATA0000'), 'rb') as f:
                if f.read(16).rstrip(b'\0') == K.MAGIC:
                    yield here


def test_every_copy_of_a_real_career_comes_back_byte_for_byte():
    root = os.environ.get('LEGACY_ROSTER_CAREERS')
    if not root or not os.path.isdir(root):
        pytest.skip("no copies of Be a Pro saves (set LEGACY_ROSTER_CAREERS)")
    folders = list(_copies(root))
    assert folders
    for folder in folders:
        parts = []
        for p in K.data_files(folder):
            with open(p, 'rb') as f:
                parts.append(f.read())
        raw = b''.join(parts)
        c = K.Career(raw)
        assert c.build() == raw, os.path.basename(folder)
        c.set_xp({'offense': c.pro.xp['offense'] + 500})
        c.set_name(last=c.pro.last[:20] + 'x')
        kinds = ['xp', 'name']
        if not c.pro.goalie:
            c.set_ratings({'passing': min(K.HIGHEST, c.pro.ratings['passing'] + 5)})
            kinds.append('ratings')
        new = c.build()
        assert K.pieces(new, [len(p) for p in parts])
        back = K.Career(new)
        assert back.pro.xp['offense'] == c.pro.xp['offense'] and back.pro.last == c.pro.last
        assert back.pro.ratings == c.pro.ratings
        assert back.bio_row() is not None and back.db.tables[K.BIO].get(back.bio_row(), K.LAST) == c.pro.last
        problems = tdb.check_chain(new[:back.end])          # the database's own checksums (0x10 stops at the chunks)
        assert not [p for p in problems if '0x10' not in p], (os.path.basename(folder), problems)
        assert career_problems(raw, new, kinds, [len(p) for p in parts]) == [], os.path.basename(folder)


def _career_folder(tmp_path, raw, when=1_700_000_000):
    saves = tmp_path / 'savedata'
    saves.mkdir(exist_ok=True)
    path = write_save(str(saves), 'BLES021530502', raw, 'LPRO13', chunk=1024, when=when)
    with open(os.path.join(path, 'ICON0.PNG'), 'wb') as f:
        f.write(b'png')
    os.utime(os.path.join(path, 'ICON0.PNG'), (when, when))
    return str(saves), path


def _files(path):
    return {n: open(os.path.join(path, n), 'rb').read() for n in sorted(os.listdir(path))}


def test_a_career_is_saved_after_a_backup_of_the_whole_folder(tmp_path, monkeypatch):
    from legacy_roster import savedata
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    raw = career_bytes()
    saves, path = _career_folder(tmp_path, raw)
    before = _files(path)
    c = K.Career(raw)
    c.set_xp({'offense': 900})
    new = c.build()
    backups = str(tmp_path / 'backups')
    backup = savedata.update_career(saves, 'BLES021530502', new, raw, backups, now=later(path))
    assert _files(backup) == before                                            # every file, PARAM.SFO and the icon too
    after = _files(path)
    assert b''.join(after[n] for n in sorted(after) if n.startswith('DATA')) == new
    assert [len(after[n]) for n in sorted(after) if n.startswith('DATA')] == \
        [len(before[n]) for n in sorted(before) if n.startswith('DATA')]
    assert after['PARAM.SFO'] == before['PARAM.SFO'] and after['ICON0.PNG'] == before['ICON0.PNG']
    changed = [n for n in after if after[n] != before[n]]
    assert changed and all(n.startswith('DATA') for n in changed)
    assert not [n for n in os.listdir(tmp_path) if n.startswith('.roster-updater')]
    assert savedata.update_career(saves, 'BLES021530502', new, new, backups, now=later(path)) is None   # nothing new
    named = savedata.update_career(saves, 'BLES021530502', new, new, backups, now=later(path), label='NOWAK3')
    assert K.Save(path).name == 'NOWAK3' and _files(path)['DATA0000'] == after['DATA0000']
    assert _files(named)['PARAM.SFO'] == before['PARAM.SFO']                    # the label as it was, in the backup
    for n in range(savedata.KEEP_BACKUPS + 2):                                  # only the newest 10 are kept
        os.makedirs(os.path.join(backups, f'BLES021530502_20260101-0000{n:02d}'))
    savedata._prune_backups(backups, 'BLES021530502')
    assert len(os.listdir(backups)) == savedata.KEEP_BACKUPS and os.path.isdir(backup)


@pytest.mark.parametrize('case', ['running', 'settling', 'changed', 'split', 'roster', 'outside'])
def test_a_career_is_not_touched_when_it_should_not_be(tmp_path, monkeypatch, case):
    from legacy_roster import savedata
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: 'rpcs3.exe' if case == 'running' else None)
    raw = career_bytes()
    saves, path = _career_folder(tmp_path, raw)
    c = K.Career(raw)
    c.set_xp({'offense': 900})
    new, expected, now, folder = c.build(), raw, later(path), 'BLES021530502'
    if case == 'settling':
        now = os.path.getmtime(os.path.join(path, 'DATA0000')) + 2
    elif case == 'changed':
        expected = new
    elif case == 'split':
        new += b'\0' * 2000
    elif case == 'roster':
        folder = 'BLES021530202'
        os.rename(path, os.path.join(saves, folder))
        path = os.path.join(saves, folder)
    elif case == 'outside':
        saves = str(tmp_path)
        folder = os.path.join('savedata', 'BLES021530502')
    before = _files(path)
    with pytest.raises(savedata.InPlaceError):
        savedata.update_career(saves, folder, new, expected, str(tmp_path / 'backups'), now=now)
    assert _files(path) == before and not os.path.exists(tmp_path / 'backups')


def test_a_failed_move_puts_the_career_back(tmp_path, monkeypatch):
    from legacy_roster import savedata
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    raw = career_bytes()
    saves, path = _career_folder(tmp_path, raw)
    before = _files(path)
    c = K.Career(raw)
    c.set_name(first='Jaromir')                                 # changes the database (all files) and chunk 8
    c.set_xp({'defense': 1})
    new = c.build()
    real, calls = os.replace, []

    def flaky(a, b):
        calls.append(b)
        if len(calls) == 2:
            raise OSError("disk full")
        real(a, b)
    monkeypatch.setattr(savedata.os, 'replace', flaky)
    with pytest.raises(savedata.InPlaceError, match="old one is still there"):
        savedata.update_career(saves, 'BLES021530502', new, raw, str(tmp_path / 'backups'), now=later(path))
    assert len(calls) == 2 and _files(path) == before
