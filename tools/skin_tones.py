"""The skin groups of players (data pack part `skins`): check tools/skin_marks.json.

The game draws a created player with a generic head, and the head is also his skin; a new player used to get a light one.
`tools/skin_marks.json` lists players whose photos show brown or dark skin ("<name, letters only>|<birth year>": group;
`legacy_roster.faces.BUCKETS`). It is made by hand: `private/skin/` nominates photos by colour (a score that is right
about two in three) and the list is what a person saw on contact sheets (docs/notes/skin-tones.md). `tools/build_datapack.py`
copies it into the pack on every build.

    python tools/skin_tones.py            check the file (keys, groups, duplicates) and count
    python tools/skin_tones.py --add "Marc Johnstone" 1996 dark
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from legacy_roster import faces  # noqa: E402
from legacy_roster.matching import norm  # noqa: E402

PATH = os.path.join(HERE, 'skin_marks.json')
GROUPS = ('medium', 'brown', 'dark')


def load():
    with open(PATH, encoding='utf-8') as f:
        return json.load(f)


def problems(marks):
    out = []
    for key, group in marks.items():
        name, _, year = key.rpartition('|')
        if group not in GROUPS or group not in faces.BUCKETS:
            out.append(f"{key}: group {group!r} is not one of {GROUPS}")
        if not year.isdigit() or not 1950 <= int(year) <= 2015:
            out.append(f"{key}: no birth year")
        if name != norm(name) or not name:
            out.append(f"{key}: name must be letters only, lower case")
    return out


def main(argv):
    marks = load()
    if argv[:1] == ['--add'] and len(argv) == 4:
        marks[f"{norm(argv[1])}|{int(argv[2])}"] = argv[3]
        with open(PATH, 'w', encoding='utf-8') as f:
            json.dump(dict(sorted(marks.items())), f, indent=0, sort_keys=True)
    bad = problems(marks)
    for line in bad:
        print(line)
    counts = {g: sum(1 for v in marks.values() if v == g) for g in GROUPS}
    print(f"{len(marks)} players: {counts}")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
