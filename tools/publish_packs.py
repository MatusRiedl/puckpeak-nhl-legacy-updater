"""Put the picture packs and the data pack on the program's file server (legacy_roster/packs.py, datasource.FILES_URL).

    python tools/publish_packs.py <ssh-host>:<folder>              every pack in private/packs (photos, looks, arenas, ice, masks) + the data pack
    python tools/publish_packs.py <ssh-host>:<folder> --only arenas,ice   only these packs (the others stay as the server lists them)
    python tools/publish_packs.py <ssh-host>:<folder> --dry-run    only say what would be sent

Writes manifest.json (packs.FORMAT; per pack: file, size, sha256, built), copies each zip under a name of its own
(<name>-<sha12>.zip: a player halfway through a download keeps the old file), then the data pack, then the manifest
last (as manifest.json.tmp, renamed on the server), so a manifest never names a file that is not there yet. The packs
the new and the previous manifest name stay; older ones are removed. The server's daily lines job (tools/lines_job.py)
rewrites the data pack there: each team's lines the server's pack has newer than this one's are kept, written into the
local pack first (lines_job.take_newer), so a publish never sends older lines. Needs ssh and scp (OpenSSH). Refuses when
tools/clean_check.py --server finds a word that must not ship. Host and folder are given on the command line only: they never
go into a committed file.
"""
import argparse
import gzip
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from legacy_roster import datasource, packs  # noqa: E402
import clean_check  # noqa: E402
import lines_job  # noqa: E402

PACKS = os.path.join(ROOT, 'private', 'packs')


def digest(path):
    sha = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            sha.update(block)
    return sha.hexdigest()


def built(path):
    """The date the pack's index.json gives (both packs have one)."""
    with zipfile.ZipFile(path) as z:
        return str(json.loads(z.read('index.json')).get('built', ''))


def entries(folder, only=None):
    """The packs to publish: `only` (all must exist) or every pack of packs.NAMES that is in the folder."""
    out = {}
    for name in only or packs.NAMES:
        path = os.path.join(folder, f"{name}.zip")
        if not os.path.isfile(path):
            if only:
                sys.exit(f"{path} is missing")
            continue
        sha = digest(path)
        out[name] = {'file': f"{name}-{sha[:12]}.zip", 'size': os.path.getsize(path), 'sha256': sha,
                     'built': built(path), 'local': path}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('target', help="<ssh-host>:<folder> on the server")
    ap.add_argument('--packs', default=PACKS, help="the folder with the pack zips (default private/packs)")
    ap.add_argument('--only', help="comma separated pack names; the other packs stay as the server's manifest lists them")
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if ':' not in args.target:
        sys.exit("give the target as <ssh-host>:<folder>")
    host, folder = args.target.split(':', 1)
    folder = folder.rstrip('/')

    if subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'clean_check.py'), '--server']).returncode:
        sys.exit("tools/clean_check.py --server found words that must not ship: nothing was sent")
    pack = datasource.read_pack(datasource.BUNDLED_PACK)
    if pack.get('format') != datasource.PACK_FORMAT:
        sys.exit(f"the data pack is format {pack.get('format')}, the program reads {datasource.PACK_FORMAT}")
    only = [n.strip() for n in args.only.split(',') if n.strip()] if args.only else None
    unknown = [n for n in only or [] if n not in packs.NAMES]
    if unknown:
        sys.exit(f"not a pack: {', '.join(unknown)} (packs: {', '.join(packs.NAMES)})")
    listed = entries(args.packs, only)
    if not listed:
        sys.exit(f"no pack zip in {args.packs}")

    def ssh(command, check=True):
        return subprocess.run(['ssh', host, command], capture_output=True, text=True, check=check)

    def scp(local, remote):
        subprocess.run(['scp', '-q', local, f"{host}:{remote}"], check=True)

    q = shlex.quote
    # the server's daily lines job (tools/lines_job.py) may have newer lines than this pack: keep them
    live = subprocess.run(['ssh', host, f"cat {q(folder + '/datapack.json.gz')}"], capture_output=True, check=False)
    try:
        server_pack = json.loads(gzip.decompress(live.stdout)) if live.returncode == 0 and live.stdout else None
    except (OSError, ValueError):
        server_pack = None
    if server_pack:
        merged, taken = lines_job.take_newer(pack, server_pack)
        if taken:
            hits = clean_check.pack_hits(json.dumps(merged, ensure_ascii=False))
            if hits:
                sys.exit("the server's newer lines hold words that must not ship: nothing was sent\n" + "\n".join(hits))
            print(f"lines: kept the server's newer lines of {len(taken)} teams ({', '.join(t.split(':')[1] for t in taken[:12])}"
                  f"{' ...' if len(taken) > 12 else ''})")
            if not args.dry_run:
                with open(datasource.BUNDLED_PACK, 'wb') as f:      # the local pack becomes what goes out
                    f.write(datasource.pack_bytes(merged))
    old = ssh(f"cat {q(folder + '/manifest.json')}", check=False)
    try:
        before = json.loads(old.stdout).get('packs', {}) if old.returncode == 0 else {}
    except ValueError:
        before = {}
    have = set(ssh(f"ls -1 {q(folder)}", check=False).stdout.split())
    kept = {n: e for n, e in before.items() if n not in listed and n in packs.NAMES and isinstance(e, dict)}
    manifest = {'format': packs.FORMAT, 'packs': {**kept, **{n: {k: v for k, v in e.items() if k != 'local'}
                                                              for n, e in listed.items()}}}
    for name, e in listed.items():
        state = "already there" if e['file'] in have else f"to send ({e['size'] / 1e6:.1f} MB)"
        print(f"{name}: {e['file']}, built {e['built']}, {state}")
    if args.dry_run:
        print(json.dumps(manifest, indent=1))
        return

    ssh(f"mkdir -p {q(folder)}")
    for name, e in listed.items():
        if e['file'] not in have:
            scp(e['local'], f"{folder}/{e['file']}.part")
            ssh(f"mv {q(folder + '/' + e['file'] + '.part')} {q(folder + '/' + e['file'])}")
    scp(datasource.BUNDLED_PACK, f"{folder}/datapack.json.gz.tmp")
    ssh(f"mv {q(folder + '/datapack.json.gz.tmp')} {q(folder + '/datapack.json.gz')}")
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    try:
        scp(f.name, f"{folder}/manifest.json.tmp")
    finally:
        os.remove(f.name)
    ssh(f"mv {q(folder + '/manifest.json.tmp')} {q(folder + '/manifest.json')}")

    keep = {e['file'] for e in manifest['packs'].values()} | {e.get('file') for e in before.values() if isinstance(e, dict)}
    gone = sorted(n for n in have if n.endswith('.zip') and n not in keep)
    if gone:
        ssh(f"cd {q(folder)} && rm -f -- " + ' '.join(q(n) for n in gone))
    ssh(f"chmod 644 {q(folder)}/*")
    print(f"published: {', '.join(e['file'] for e in listed.values())}, datapack.json.gz, manifest.json"
          + (f"; removed {', '.join(gone)}" if gone else ""))


if __name__ == '__main__':
    main()
