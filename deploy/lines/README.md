# The lines job on the file server

`tools/lines_job.py` in a small container of its own, beside the file server that serves the data pack. Every day at
10:00 UTC it fetches the NHL teams' lines (announced + last games) and the Extraliga clubs' newest match line-ups, lays
them into the published `datapack.json.gz` and replaces it, but only when every guard passes (owner, 2026-11-09; AGENTS.md
rule 6). Both games read that file, so players get the new lines at their next Update, with no release. What it does and
why: docs/notes/lines-job.md.

Host names, addresses and the server's folders never go into this repository. Below, `<pack folder>` is the folder whose
`files/` the file server serves.

## Layout on the server

```
<pack folder>/files/              the file server's files (manifest.json, the packs, datapack.json.gz)
<pack folder>/files/datapack.json.gz.prev   the pack before the job's last write (not served)
<pack folder>/lines/              this folder: Dockerfile, compose.yml, src/ (made by context.py)
<pack folder>/lines/archive/      the last 8 published packs and status.json (the last run's result)
```

The container has no port and is not on the web network. It mounts `../files` (the folder: a file mount would keep the
old file after the job renames the new one over it) and `./archive`, runs as user 10001 with a read-only file system,
0.25 CPU, 256 MB, 64 processes. A run makes a few hundred small requests in 3 to 5 minutes; serving is not touched.

## Deploy (owner's go first; suggest a snapshot)

1. On the PC, from the reviewed commit with a clean tree: `python deploy/lines/context.py lines.tgz`. It takes only files
   git would publish and refuses a file with a word `tools/clean_check.py` finds.
2. Copy `lines.tgz` to the server and unpack it into `<pack folder>/lines/` (remove the old `src/` first, so a deleted
   file does not stay).
3. In `<pack folder>/lines/`:
   ```
   mkdir -p archive
   chown 10001:10001 archive ../files          # the folders only, not their files
   docker pull python:3.13-slim                # note the digest it prints
   BASE=python:3.13-slim@sha256:<digest> docker compose build
   docker compose run --rm lines once --pack /files/datapack.json.gz --dry-run
   ```
   The dry run fetches and checks and writes nothing; it ends with "dry run: every guard passed" or names what failed.
4. `docker compose up -d`, then `docker logs nhl-legacy-lines` says "next run <date> 10:00 UTC".
5. The first real run, at once: `docker compose run --rm lines once --pack /files/datapack.json.gz --archive /archive`.
6. Check: `archive/status.json` says `published`; the pack downloads from the file server's address with the new
   `generated`, `format` 2 and the same `season`; `datapack.json.gz.prev` answers 404 there; the other packs and the
   manifest answer 200; both games' post-change checks.

## Update the code

Steps 1 and 2 again, then `BASE=python:3.13-slim@sha256:<digest> docker compose up -d --build`.

## Roll back a bad pack

```
cp ../files/datapack.json.gz.prev ../files/datapack.json.gz.back && mv ../files/datapack.json.gz.back ../files/datapack.json.gz
```

or the same with a pack from `archive/`. Stop the job first (below) if its next run would write the same thing again. A
maintainer's `tools/publish_packs.py` also replaces the pack; it keeps every team's lines the server has newer than its
own, so it never sends older lines.

## Stop, remove

- Stop: `docker compose down` in `<pack folder>/lines/`. The pack stays as last published; players keep those lines.
- Remove: `docker compose down`, `docker image rm nhl-legacy-lines`, then delete `<pack folder>/lines/`.
