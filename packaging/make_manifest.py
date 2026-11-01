"""Write legacy_roster/web/manifest.txt: every file of the page, one path per line (build.ps1 / build.sh run it before
PyInstaller). window/main.missing_files checks them at start, so an antivirus or cleaner that removed a style or script
file from the exe's unpacked folder is told to the player instead of leaving a blue or black window."""
import os
import sys

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'legacy_roster', 'web')
NAME = 'manifest.txt'


def listing(web=WEB):
    found = []
    for folder, dirs, files in os.walk(web):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        for name in sorted(files):
            if name != NAME and not name.endswith(('.pyc', '.map')):
                found.append(os.path.relpath(os.path.join(folder, name), web).replace(os.sep, '/'))
    return sorted(found)


def write(web=WEB):
    names = listing(web)
    with open(os.path.join(web, NAME), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(names) + '\n')
    return names


if __name__ == '__main__':
    print(f"{len(write())} files of the page listed in {NAME}")
    sys.exit(0)
