#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
build_dir="$PWD/.local/performance-20260930/artifacts"
podman run --rm -v "$PWD:/repo:ro" -v "$build_dir:/out" localhost/flyt-build:stage2-20260928 sh -ec '
 cp /opt/flyt/lib/libflyt_guest.so /out/
 gcc -O2 -I/usr/local/cuda/include /repo/experiments/performance/load_probe.c -L/usr/local/cuda/lib64 -L/usr/local/cuda/lib64/stubs -lcudart -lcuda -o /out/load-N
 gcc -O2 -DFLYT_GUEST -I/usr/local/cuda/include /repo/experiments/performance/load_probe.c -L/opt/flyt/lib -Wl,-rpath,\$ORIGIN -lflyt_guest -o /out/load-S
 gcc -O2 -I/usr/local/cuda/include /repo/experiments/performance/overhead_probe.c -L/usr/local/cuda/lib64 -L/usr/local/cuda/lib64/stubs -lcudart -lcuda -o /out/probe-N
 gcc -O2 -DFLYT_GUEST -I/usr/local/cuda/include /repo/experiments/performance/overhead_probe.c -L/opt/flyt/lib -Wl,-rpath,\$ORIGIN -lflyt_guest -o /out/probe-S
 gcc -O2 -DFLYT_TCP -I/usr/local/cuda/include /repo/experiments/performance/overhead_probe.c -L/out -Wl,-rpath,\$ORIGIN -Wl,-rpath-link,/out -Wl,--allow-shlib-undefined -l:cricket-client.so -o /out/probe-T
 cp /repo/experiments/evidence/overhead_work.ptx /out/work.ptx
 /usr/local/cuda/bin/ptxas -arch=sm_120 /out/work.ptx -o /out/work-original.cubin
 '
python3 experiments/evidence/normalize_overhead_cubin.py "$build_dir/work-original.cubin" "$build_dir/work.cubin" --manifest "$build_dir/cubin-normalization.json"
sha256sum "$build_dir"/load-* "$build_dir"/probe-* "$build_dir"/*.so "$build_dir"/work.*
