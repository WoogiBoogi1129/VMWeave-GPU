#!/usr/bin/env bash
set -euo pipefail
: "${CUDA_ROOT:?Set CUDA_ROOT to CUDA 12.8 toolkit}"
cd "$(dirname "$0")/../.."
mkdir -p .local/path-optimization-tests
incs=(-Iruntime/shm/include -Iruntime/shm/shm-queue/include
      -Iruntime/shm/shm-contract/include -Iruntime/shm/cuda-dispatch/include
      -I"$CUDA_ROOT/include")
cc -std=gnu11 -O1 -g -ffunction-sections -fdata-sections "${incs[@]}" \
   tests/path_optimization/pinned_pool.c -Wl,--gc-sections -pthread -o .local/path-optimization-tests/pinned_pool
.local/path-optimization-tests/pinned_pool
# P0 tests include the actual candidate wrapper and dispatcher.
for name in guest worker; do
 cc -std=gnu11 -O1 -g -ffunction-sections -fdata-sections "${incs[@]}" \
    "tests/path_optimization/memset/$name.c" -Wl,--gc-sections -pthread -o ".local/path-optimization-tests/memset-$name"
done
.local/path-optimization-tests/memset-guest on
.local/path-optimization-tests/memset-guest off
.local/path-optimization-tests/memset-worker
cc -std=gnu11 -O1 -g -DOLD_WORKER -ffunction-sections -fdata-sections "${incs[@]}" \
   tests/path_optimization/memset/worker.c -Wl,--gc-sections -pthread -o .local/path-optimization-tests/memset-old-worker
.local/path-optimization-tests/memset-old-worker
