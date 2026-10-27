#!/usr/bin/env bash
set -euo pipefail
: "${CUDA_ROOT:?Set CUDA_ROOT to CUDA 12.8 toolkit}"
cd "$(dirname "$0")/.."
mkdir -p build-tests
incs=(-Isource/runtime/shm/include -Isource/runtime/shm/shm-queue/include
      -Isource/runtime/shm/shm-contract/include -Isource/runtime/shm/cuda-dispatch/include
      -I"$CUDA_ROOT/include")
cc -std=gnu11 -O1 -g -ffunction-sections -fdata-sections "${incs[@]}" \
   tests/pinned_pool.c -Wl,--gc-sections -pthread -o build-tests/pinned_pool
build-tests/pinned_pool
# P0 tests include the actual candidate wrapper and dispatcher.
for name in guest worker; do
 cc -std=gnu11 -O1 -g -ffunction-sections -fdata-sections "${incs[@]}" \
    "tests/memset/$name.c" -Wl,--gc-sections -pthread -o "build-tests/memset-$name"
done
build-tests/memset-guest on
build-tests/memset-guest off
build-tests/memset-worker
cc -std=gnu11 -O1 -g -DOLD_WORKER -ffunction-sections -fdata-sections "${incs[@]}" \
   tests/memset/worker.c -Wl,--gc-sections -pthread -o build-tests/memset-old-worker
build-tests/memset-old-worker
