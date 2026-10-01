#!/usr/bin/env bash
# Host-only regression checks; CUDA headers/libraries are needed, a GPU is not.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
build=${1:?Usage: test-shm-training.sh /absolute/path/to/shm-cmake-build}
cuda_root=${CUDA_PATH:-/usr/local/cuda}
cd "$repo"
includes=(-Iruntime/shm/include -Iruntime/shm/cuda-dispatch/include
  -Iruntime/shm/shm-queue/include -Iruntime/shm/shm-contract/include
  -I"$cuda_root/include")
cc -O2 "${includes[@]}" tests/integration/guest_pointer_refs.c \
  "$build/libflyt_mapping.a" "$build/queue/libflyt_shm_queue.a" \
  -lpthread -o "$build/guest-pointer-refs-test"
"$build/guest-pointer-refs-test"
cc -O2 "${includes[@]}" tests/integration/kernel_wire_validation.c \
  -L"$cuda_root/lib64" -Wl,-rpath,"$cuda_root/lib64" \
  -L"$cuda_root/lib64/stubs" -lcudart -lcuda -o "$build/kernel-wire-test"
"$build/kernel-wire-test"
cc -O2 "${includes[@]}" tests/integration/memory_info_dispatch.c \
  "$build/libflyt_dispatch.a" "$build/queue/libflyt_shm_queue.a" -lpthread -o "$build/memory-info-test"
"$build/memory-info-test"
cc -O2 "${includes[@]}" tests/integration/allocation_oom_recovery.c \
  "$build/exec/libflyt_cuda_exec.a" -lpthread -o "$build/oom-recovery-test"
"$build/oom-recovery-test"
"$build/oom-recovery-test" fatal
cc -O2 "${includes[@]}" tests/integration/private_copy_buffers.c \
  "$build/exec/libflyt_cuda_exec.a" -lpthread -o "$build/private-copy-test"
"$build/private-copy-test"
"$build/private-copy-test" fatal
cc -O2 -Wall -Wextra -Werror "${includes[@]}" tests/integration/queue_payload_bounds.c \
  runtime/shm/shm-queue/src/perf.c -lpthread -o "$build/queue-payload-test"
FLYT_COPY_MODE=legacy "$build/queue-payload-test"
FLYT_COPY_MODE=optimized FLYT_WAIT_MODE=bounded "$build/queue-payload-test"
FLYT_GUEST_LIBRARY="$build/libflyt_guest.so" python3 tests/integration/layout_permissions.py -q
