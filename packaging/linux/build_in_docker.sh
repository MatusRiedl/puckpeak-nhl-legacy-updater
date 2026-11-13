#!/usr/bin/env bash
# Build the Linux program and check it on three systems, in Docker boxes, on any Linux machine with Docker (MAINTAINING.md
# "The Linux program"). Every image and container is named legacy-linux-*; nothing else on the machine is touched. Each
# box gets at most 2 cores and 2 GB of memory, no ports and no folders of the machine.
#   bash build_in_docker.sh <source.tgz> <out folder>
# <source.tgz>: the files git would publish, packed (git ls-files); <out folder> receives
# BluelineLegacy-<version>-linux.tar.gz and a picture of the window per system (window-<system>.png).
# Fails when the build fails or the new window does not open on one of the systems (packaging/linux_check.sh).
set -euo pipefail
src=$(readlink -f "$1")
out=$(readlink -f "$2")
mkdir -p "$out"
here=$(mktemp -d)
tar xzf "$src" -C "$here" packaging/linux packaging/linux_check.sh
limits=(--cpus=2 --memory=2g --memory-swap=2g)

docker build -q -t legacy-linux-build "$here/packaging/linux" >/dev/null
docker rm -f legacy-linux-builder >/dev/null 2>&1 || true
docker create --name legacy-linux-builder "${limits[@]}" legacy-linux-build bash -c \
    "cd /src && tar xzf /tmp/src.tgz && git init -q && git add -A && bash packaging/build.sh \
     && mkdir -p /tmp/out && cp dist/*-linux.tar.gz /tmp/out/" >/dev/null
docker cp "$src" legacy-linux-builder:/tmp/src.tgz
docker start -a legacy-linux-builder | tail -5
docker cp legacy-linux-builder:/tmp/out "$here/out"
docker rm -f legacy-linux-builder >/dev/null
archive=$(ls "$here"/out/*-linux.tar.gz)
cp "$archive" "$out/"
echo "built $(basename "$archive") ($(du -h "$archive" | cut -f1))"

status=0
for system in ubuntu fedora arch; do
    docker build -q -t "legacy-linux-check:$system" -f "$here/packaging/linux/check/$system.Dockerfile" \
        "$here/packaging/linux/check" >/dev/null
    docker rm -f legacy-linux-check >/dev/null 2>&1 || true
    docker create --name legacy-linux-check "${limits[@]}" "legacy-linux-check:$system" \
        bash /tmp/linux_check.sh /tmp/app.tgz /tmp/window.png >/dev/null
    docker cp "$here/packaging/linux_check.sh" legacy-linux-check:/tmp/linux_check.sh
    docker cp "$archive" legacy-linux-check:/tmp/app.tgz
    echo "=== $system"
    docker start -a legacy-linux-check || status=1
    docker cp legacy-linux-check:/tmp/window.png "$out/window-$system.png" 2>/dev/null || true
    docker rm -f legacy-linux-check >/dev/null
done
rm -rf "$here"
exit $status
