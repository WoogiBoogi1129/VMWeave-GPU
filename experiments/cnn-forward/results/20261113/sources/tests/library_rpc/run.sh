#!/bin/bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
build=${1:?Usage: run.sh build-directory}
cd "$repo"
python3 scripts/codegen/library_rpc.py --check
cc -O2 -Iruntime/shm/include -Iruntime/shm/cuda-dispatch/include -Iruntime/shm/shm-queue/include -Iruntime/shm/shm-contract/include -I/usr/local/cuda/include tests/library_rpc/validation.c runtime/shm/src/library.c -L/usr/local/cuda/lib64 -Wl,-rpath,/usr/local/cuda/lib64 -lcudnn -lcublasLt -o "$build/library-wire-test"
"$build/library-wire-test"
cc -O2 -Iruntime/shm/include -Iruntime/shm/cuda-dispatch/include -Iruntime/shm/shm-queue/include -Iruntime/shm/shm-contract/include -I/usr/local/cuda/include tests/library_rpc/guest_validation.c runtime/shm/src/guest_library.c -lpthread -o "$build/library-guest-test"
"$build/library-guest-test"
cc -O2 -Iruntime/shm/include -Iruntime/shm/cuda-dispatch/include -Iruntime/shm/shm-queue/include -Iruntime/shm/shm-contract/include -I/usr/local/cuda/include tests/library_rpc/conv_validation.c runtime/shm/src/library.c -L/usr/local/cuda/lib64 -Wl,-rpath,/usr/local/cuda/lib64 -lcudnn -lcublasLt -o "$build/library-conv-test"
"$build/library-conv-test"
cc -O2 -Iruntime/shm/include -Iruntime/shm/cuda-dispatch/include -Iruntime/shm/shm-queue/include -Iruntime/shm/shm-contract/include -I/usr/local/cuda/include tests/library_rpc/conv_guest_validation.c runtime/shm/src/guest_library.c -lpthread -o "$build/library-conv-guest-test"
"$build/library-conv-guest-test"
