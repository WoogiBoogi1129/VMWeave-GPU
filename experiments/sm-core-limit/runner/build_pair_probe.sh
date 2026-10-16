#!/bin/bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../../.." && pwd)
image=${SM_BUILD_IMAGE:-d94699a19c42f78777eb8126bda5f823767801f1c9698d065319bede58dbc7e2}
mkdir -p "$root/.local/sm-pair-20261016"
test -f "$root/.local/thesis-isolation-20261012/artifacts/libflyt_guest.so"
podman run --rm -v "$root:/repo:rw" --entrypoint /bin/sh "$image" -c 'gcc -O2 -DVMWEAVE -I/usr/local/cuda/include /repo/experiments/sm-core-limit/probes/sm_probe.c -L/repo/.local/thesis-isolation-20261012/artifacts -Wl,--no-as-needed -lflyt_guest -o /repo/.local/sm-pair-20261016/sm-pair-probe-guest'
sha256sum "$root/.local/sm-pair-20261016/sm-pair-probe-guest"
