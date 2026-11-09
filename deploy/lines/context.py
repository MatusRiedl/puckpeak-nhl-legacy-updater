"""Make the lines job's build folder as one file to copy to the server (deploy/lines/README.md).

    python deploy/lines/context.py lines.tgz

The archive holds Dockerfile, compose.yml and src/: every Python file of legacy_roster/ (not the window's page, pictures
or the bundled data pack), tools/providers/, tools/lines_job.py, tools/clean_check.py and tools/club_slots.json, as the
working tree has them. Only files git would publish are taken (nothing git ignores, so nothing from private/ or work/),
and the archive is refused when tools/clean_check.py finds a word in one of them. Same files, same bytes.
"""
import io
import os
import subprocess
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, 'deploy', 'lines')
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import clean_check  # noqa: E402

FILES = ('tools/lines_job.py', 'tools/clean_check.py', 'tools/club_slots.json')


def wanted(path):
    if path in FILES:
        return True
    if path.startswith('tools/providers/') and path.endswith('.py'):
        return True
    return path.startswith('legacy_roster/') and path.endswith('.py')


def sources():
    out = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '-z', '--', 'legacy_roster', 'tools'], cwd=ROOT,
                         capture_output=True, check=True).stdout.decode('utf-8')
    return sorted(p for p in out.split('\0') if p and wanted(p) and os.path.isfile(os.path.join(ROOT, p)))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    paths = sources()
    missing = [p for p in FILES if p not in paths]
    if missing:
        sys.exit(f"missing: {', '.join(missing)}")
    members = [(name, os.path.join(HERE, name)) for name in ('Dockerfile', 'compose.yml')]
    members += [(f"src/{p}", os.path.join(ROOT, p)) for p in paths]
    hits = []
    for name, path in members:
        text = clean_check.text_of(path)
        if text is not None:
            hits += clean_check.hits_in(name, text)
    if hits:
        sys.exit("words that must not ship:\n" + "\n".join(hits))
    with tarfile.open(sys.argv[1], 'w:gz', format=tarfile.PAX_FORMAT) as tar:
        for name, path in members:
            with open(path, 'rb') as f:
                data = f.read()
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            tar.addfile(info, io.BytesIO(data))
    print(f"{sys.argv[1]}: {len(members)} files ({len(paths)} from the repository)")


if __name__ == '__main__':
    main()
