"""Every roster a tester sent that the program once refused or got wrong (0.95.1, owner: "this is a reoccurring theme").

The rosters are other people's work and never in git: one folder per roster with its SYS-DATA in
private/tester_rosters/ (README.txt there), or in the folder LEGACY_ROSTER_TESTERS names. Without any the tests skip.
Each roster gets a full update from the bundled data pack (offline, so it is reproducible), the game patch's step too
when the roster was made for the patched game, as the program does on a patched RPCS3. It must pass every safety check,
and an update of the result must change nothing (rule 4)."""
import os

import pytest

from legacy_roster import datasource, gamepatch, pipeline, schedule
from legacy_roster.roster import Roster

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.environ.get('LEGACY_ROSTER_TESTERS') or os.path.join(ROOT, 'private', 'tester_rosters')


def _rosters():
    if not os.path.isdir(FOLDER):
        return []
    return sorted(name for name in os.listdir(FOLDER) if os.path.isfile(os.path.join(FOLDER, name, 'SYS-DATA')))


def _update(raw, pack):
    """What the program does with this roster: (roster bytes, problems, the build)."""
    patched = gamepatch.is_patch_roster(Roster(raw))
    steps = pipeline.steps_for(pack)
    data = datasource.gather(Roster(raw), set(steps), pack, offline=True)
    if patched:
        data.calendar = schedule.ALL_PATCH
    res = pipeline.build(raw, data, steps, game_patch=patched)
    if not res.ok:
        return res.data, res.problems, res
    if patched:
        out, problems, _ = pipeline.patch_roster(res, raw, pack, data.season_year)
        return out, problems, res
    return res.data, [], res


@pytest.mark.parametrize('name', _rosters() or [pytest.param(None, marks=pytest.mark.skip(
    reason="no tester rosters (private/tester_rosters or LEGACY_ROSTER_TESTERS)"))])
def test_a_tester_roster_is_updated_and_a_second_update_changes_nothing(name, pack):
    with open(os.path.join(FOLDER, name, 'SYS-DATA'), 'rb') as f:
        raw = f.read()
    first, problems, res = _update(raw, pack)
    assert problems == [], problems[:10]
    assert res.ok, res.problems[:10]
    again, problems, _ = _update(first, pack)
    assert problems == [], problems[:10]
    assert again == first
