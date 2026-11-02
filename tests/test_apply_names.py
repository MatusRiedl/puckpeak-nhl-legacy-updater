"""Apply names: the picked roster's team names into the game, with no roster saved and no picture looked at
(pipeline.apply_names, the Team names row's button, `cli names apply`)."""
import copy
import os

import pytest

from legacy_roster import datasource, gamepatch, native, pipeline, savedata, schedule
from legacy_roster.art import install, loc, menus, portraits
from legacy_roster.art.photopack import PhotoPack
from legacy_roster.roster import Roster

from .test_native import fake_native
from .test_promo import TextDisc, own_texts


@pytest.fixture
def game(tmp_path, monkeypatch):
    """A pretend RPCS3 that has the game, its text files made up."""
    monkeypatch.setattr(datasource, 'data_home', lambda: str(tmp_path / 'appdata'))
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: None)
    monkeypatch.setattr(install, 'Disc', lambda path: TextDisc({lang: own_texts(lang) for lang in loc.LANGUAGES}))
    monkeypatch.setattr(menus, 'menu_files', lambda disc, mode: {menus.REL: b'MENU'})
    monkeypatch.setattr(PhotoPack, 'open', lambda: pytest.fail("Apply names read the picture pack"))
    rpcs3 = savedata.Rpcs3(str(tmp_path / 'rpcs3' / 'rpcs3.exe'), str(tmp_path / 'rpcs3' / 'savedata'), '00000001',
                           games={'BLES02153': str(tmp_path / 'game.iso')})
    rpcs3.game_folder = lambda title: str(tmp_path / 'rpcs3' / 'dev_hdd0' / 'game' / title / 'USRDIR')
    rpcs3.game_disc = lambda title: str(tmp_path / 'game.iso')
    yield rpcs3
    install.use_host(None)


def written(folder):
    return sorted(os.path.relpath(os.path.join(where, name), folder).replace('\\', '/')
                  for where, _dirs, files in os.walk(folder) for name in files)


def test_the_names_are_the_ones_an_update_of_that_roster_writes(base_bytes, data, tmp_path, monkeypatch):
    monkeypatch.setattr(datasource, 'data_home', lambda: str(tmp_path / 'appdata'))
    result = pipeline.build(base_bytes, data, art_registry=portraits.Registry())
    assert pipeline.names_of(result.data) == result.art[2]


def test_a_roster_for_the_patched_game_gives_the_same_names(base_bytes, data, pack):
    patch = copy.copy(data)
    patch.schedule, patch.leagues, patch.calendar = pack['schedule'], {'ahl': pack['leagues']['ahl']}, schedule.ALL_PATCH
    res = pipeline.build(base_bytes, patch, list(pipeline.CORE_STEPS) + [pipeline.SCHEDULE, 'ahl'], game_patch=True)
    out, problems, _ = pipeline.patch_roster(res, base_bytes, pack, patch.season_year)
    assert problems == [] and gamepatch.is_patch_roster(Roster(out))
    assert pipeline.names_of(out) == pipeline.names_of(res.data)


def test_the_players_own_team_names_come_along(built):
    names = pipeline.names_of(built.data, {'0': {'full': 'Orange County Ducks', 'city': 'Orange County', 'abbr': 'OCD'}})
    assert ('ANA', 'Orange County Ducks', 'Orange County', 'Ducks', 'OCD') in names['teams']


def test_only_names_and_the_menu_go_in(built, game):
    assert pipeline.apply_names(game, built.data, 'BLES02153') > 100
    assert written(game.game_folder('BLES02153')) == sorted(
        [f"fe/loc/nhl_{lang}.db" for lang in loc.LANGUAGES] + ['/'.join(menus.REL)])


def test_a_second_press_writes_nothing(built, game):
    pipeline.apply_names(game, built.data, 'BLES02153')
    said = []
    pipeline.apply_names(game, built.data, 'BLES02153', say=said.append)
    assert not any('written' in line for line in said)


def test_nothing_goes_in_while_the_game_runs(built, game, monkeypatch):
    monkeypatch.setattr(savedata, 'running_rpcs3', lambda: r'D:\game\NHLLegacy.exe')
    with pytest.raises(install.ArtError, match='Close NHL Legacy first'):
        pipeline.apply_names(game, built.data, 'BLES02153')
    assert not os.path.exists(game.game_folder('BLES02153'))


def test_on_the_port_they_go_into_our_mod_and_the_launcher_joins_it(built, game, tmp_path, monkeypatch):
    port = savedata.find_rpcs3(str(fake_native(tmp_path / 'Native')))
    install.use_host(port)
    calls = []
    monkeypatch.setattr(native, 'compose', lambda host, say=print: calls.append(host) or True)
    pipeline.apply_names(port, built.data, 'BLES02153')         # a copied EU roster: the port has one version
    assert calls == [port]
    assert f"fe/loc/nhl_{loc.LANGUAGES[0]}.db" in written(port.game_folder('BLUS31540'))
    assert not os.path.exists(tmp_path / 'Native' / 'data' / 'hdd0')
