"""Heads that fit (0.96.0): a created player's generic head is also his skin, and every new player used to get a light one
(Marc Johnstone, Japan's team). The data pack's part `skins` (the players whose photos show brown or dark skin) and
`faces.COUNTRY_SKIN` choose the group; `Donors.fit_skins` repairs players already on a lighter head."""
from legacy_roster import datasource, faces, pipeline
from legacy_roster import layout as L
from legacy_roster.builder import Builder, Data
from legacy_roster.donors import GENERIC_HEAD, real_birth_year
from legacy_roster.matching import norm
from legacy_roster.roster import Roster


def _builder(base_bytes, skins=None):
    R = Roster(base_bytes)
    return R, Builder(R, Data(season_year=2026, skins=skins))


def _generic_light(R, b, skip=()):
    """A record on a generic head of the light group, with a real team and a name."""
    P = R.P
    for i in range(P.cur_rec):
        if (P.get(i, 'DaPp') >= GENERIC_HEAD and faces.BUCKET_OF.get(P.get(i, 'QDTK')) == 'light' and i not in skip
                and R.entries_by_pid.get(P.get(i, 'zIBw')) and not faces.is_reserved(P, i) and P.get(i, 'RMbQ')
                and 'ZZ' not in P.get(i, 'RMbQ')):
            return i
    raise LookupError('no light generic head')


def _mark(R, b, i, group):
    P = R.P
    return {norm(f"{P.get(i, 'PedH')} {P.get(i, 'RMbQ')}"): [(real_birth_year(P, i, b.stale_years), group)]}


def test_the_pack_part_is_read_and_a_bad_one_is_not():
    part = {'format': datasource.SKINS_FORMAT, 'players': {'marcjohnstone|1996': 'dark', 'anna|1990': 'purple', 'x|y': 'brown'}}
    assert datasource.skins_part({'skins': part}) == {'marcjohnstone': [(1996, 'dark')]}
    assert datasource.skins_part({'skins': dict(part, format=99)}) is None
    assert datasource.skins_part({}) is None


def test_a_new_player_with_a_dark_photo_gets_a_dark_head(base_bytes):
    R, b = _builder(base_bytes, {'marcjohnstone': [(1996, 'dark')]})
    row = b.take_record(0, "Marc Johnstone")
    b.donors.reset_identity(row, "Marc Johnstone", L.NAT_CODE['CAN'], 1996)
    assert faces.BUCKET_OF[R.P.get(row, 'QDTK')] == 'dark'
    assert (R.P.get(row, 'DaPp'), R.P.get(row, 'QDTK')) in b.donors.group_heads['dark']
    first = (R.P.get(row, 'DaPp'), R.P.get(row, 'QDTK'), R.P.get(row, 'jfuZ'))
    b.donors.reset_identity(row, "Marc Johnstone", L.NAT_CODE['CAN'], 1997)      # a year off still is him
    assert (R.P.get(row, 'DaPp'), R.P.get(row, 'QDTK'), R.P.get(row, 'jfuZ')) == first


def test_a_player_the_pack_does_not_know_keeps_the_usual_head_and_a_japanese_one_gets_a_medium_one(base_bytes):
    R, b = _builder(base_bytes, {'marcjohnstone': [(1996, 'dark')]})
    row = b.take_record(0, "Somebody Else")
    b.donors.reset_identity(row, "Somebody Else", L.NAT_CODE['CAN'], 1996)
    assert (R.P.get(row, 'DaPp'), R.P.get(row, 'QDTK')) in b.donors.generic_heads
    b.donors.reset_identity(row, "Somebody Else", L.NAT_CODE['JPN'], 1996)
    assert faces.BUCKET_OF[R.P.get(row, 'QDTK')] == 'medium'
    b.donors.reset_identity(row, "Marc Johnstone", L.NAT_CODE['JPN'], 1996)      # the photo beats the country
    assert faces.BUCKET_OF[R.P.get(row, 'QDTK')] == 'dark'


def test_a_player_on_a_light_head_is_fitted_once(base_bytes):
    R0 = Roster(base_bytes)
    R, b = _builder(base_bytes)
    row = _generic_light(R0, b)
    japanese = b.donors.fit_skins()         # the country's players (Japan's team) are fitted first
    assert japanese
    b.data.skins = _mark(R, b, row, 'brown')
    was = (R.P.get(row, 'DaPp'), R.P.get(row, 'QDTK'))
    before = R.f.build()
    assert b.donors.fit_skins() == 1
    now = (R.P.get(row, 'DaPp'), R.P.get(row, 'QDTK'))
    assert now != was and faces.BUCKET_OF[now[1]] == 'brown' and now[0] >= GENERIC_HEAD and now in b.donors.group_heads['brown']
    after = R.f.build()
    assert b.donors.fit_skins() == 0 and R.f.build() == after != before


def test_scanned_heads_created_records_and_darker_heads_are_left_alone(base_bytes):
    R, b = _builder(base_bytes)
    P = R.P
    scanned = next(i for i in range(P.cur_rec) if P.get(i, 'DaPp') < GENERIC_HEAD and P.get(i, 'RMbQ') and 'ZZ' not in P.get(i, 'RMbQ')
                   and R.entries_by_pid.get(P.get(i, 'zIBw')) and faces.BUCKET_OF.get(P.get(i, 'QDTK')) == 'light')
    reserved = next(i for i in range(P.cur_rec) if faces.is_reserved(P, i))
    P.set(reserved, 'DaPp', GENERIC_HEAD)
    P.set(reserved, 'QDTK', 1)
    skins = {}
    for i in (scanned, reserved):
        skins.update(_mark(R, b, i, 'dark'))
    darker = next(i for i in range(P.cur_rec) if P.get(i, 'DaPp') >= GENERIC_HEAD and faces.BUCKET_OF.get(P.get(i, 'QDTK')) == 'dark'
                  and not faces.is_reserved(P, i) and P.get(i, 'RMbQ'))
    skins.update(_mark(R, b, darker, 'brown'))          # already darker than the photo says: not lightened
    b.data.skins = skins
    keep = {i: (P.get(i, 'DaPp'), P.get(i, 'QDTK')) for i in (scanned, reserved, darker)}
    b.donors.fit_skins()
    assert {i: (P.get(i, 'DaPp'), P.get(i, 'QDTK')) for i in keep} == keep


def test_an_update_with_the_part_fits_heads_and_gives_the_same_roster_twice(base_bytes, data):
    R0 = Roster(base_bytes)
    _, b = _builder(base_bytes)
    row = _generic_light(R0, b)
    key = norm(f"{R0.P.get(row, 'PedH')} {R0.P.get(row, 'RMbQ')}")
    data.skins = _mark(R0, b, row, 'dark')
    try:
        first = pipeline.build(base_bytes, data)
        assert not first.problems
        assert any('fits their photo' in str(r[2]) for r in first.log)
        R = Roster(first.data)
        assert any(faces.BUCKET_OF.get(R.P.get(i, 'QDTK')) == 'dark' and norm(f"{R.P.get(i, 'PedH')} {R.P.get(i, 'RMbQ')}") == key
                   for i in range(R.P.cur_rec))
        assert pipeline.build(first.data, data).data == first.data
    finally:
        data.skins = None
