"""Words the published program must not carry: names of other games and of their makers.

    python tools/clean_check.py            check; prints file:line for every hit, exit 1 when there is one
    python tools/clean_check.py --quiet    only the count
    python tools/clean_check.py --server   only what goes on the program's server (the data pack, the picture packs)

Checks every file git would publish (tracked and new, not ignored), the data pack inside the program (unpacked), and the
picture packs that are published on the program's server (private/packs: index.json and member names). build.ps1 runs
it before a build; tests/test_clean.py runs it with the tests. The words are put together from pieces so that this file
does not hold them itself.
"""
import argparse
import gzip
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, 'private', 'packs')
DATA_PACK = os.path.join(ROOT, 'legacy_roster', 'data', 'datapack.json.gz')

_M = 'E' + 'A'
_G = 'nh' + 'l'
WORDS = re.compile('|'.join([
    r'\b' + _M + r'\b',                                     # the maker, as a word (also "<maker>'s")
    r'(?i:(?<![a-z0-9])' + _M + r'(?=_))',                  # ... as a name part: <maker>_ratings
    r'(?i:_' + _M + r'(?![a-z0-9]))',                       # ... rate_<maker>
    r'(?i:' + 'electronic' + r'\s+' + 'arts' + r')',
    r'(?i:' + _G + r'[ _-]?2[67](?![0-9]))',                # the newer games by number
    r'(?i:' + _G + 'ratings' + r')',                        # the site that lists the maker's ratings
    r'(?i:\bp' + 's5' + r'\b)', r'(?i:play' + r'station\s*5)',
    r'\bPP' + r'SA\d{5}', r'\bapp' + r'0\b',                # the newer console's title ids and dump folder
    r'(?i:zam' + 'boni)',                                   # the community server (our own is called Overtime)
]))


def published_files():
    """Files git would publish: tracked ones and new ones that no ignore rule covers."""
    out = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT, capture_output=True,
                         check=True).stdout
    return sorted(p for p in out.decode('utf-8').split('\0') if p and os.path.isfile(os.path.join(ROOT, p)))


def text_of(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if b'\0' in raw[:8192]:
        return None                                         # a picture, a font, a packed file
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return None


def hits_in(name, text):
    for n, line in enumerate(text.splitlines(), 1):
        for m in WORDS.finditer(line):
            yield f"{name}:{n}: {m.group(0)!r} in {line.strip()[:140]}"


def pack_hits(text, name='datapack.json.gz'):
    """The hits in a data pack's JSON text (one entry per line, so a hit names its place); tools/lines_job.py runs it
    before the server's pack is replaced."""
    return list(hits_in(name, text.replace('{"', '\n{"').replace(', "', ',\n"')))


def check(files=True):
    """Every hit as a 'where: what' line. `files` False: the data pack and the picture packs only."""
    found = []
    for rel in published_files() if files else ():
        if rel.endswith('.gz'):
            continue
        text = text_of(os.path.join(ROOT, rel))
        if text is not None:
            found += hits_in(rel, text)
    if os.path.isfile(DATA_PACK):
        with gzip.open(DATA_PACK, 'rt', encoding='utf-8') as f:
            found += pack_hits(f.read())
    if os.path.isdir(PACKS):
        for name in sorted(os.listdir(PACKS)):
            if not name.endswith('.zip'):
                continue
            with zipfile.ZipFile(os.path.join(PACKS, name)) as z:
                found += hits_in(f"{name} (member names)", '\n'.join(z.namelist()))
                if 'index.json' in z.namelist():
                    found += hits_in(f"{name}/index.json", z.read('index.json').decode('utf-8').replace(', "', ',\n"'))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--server', action='store_true', help="only the data pack and the picture packs")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors='backslashreplace')
    found = check(files=not args.server)
    if not args.quiet:
        for line in found:
            print(line)
    print(f"{len(found)} hit(s)")
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
