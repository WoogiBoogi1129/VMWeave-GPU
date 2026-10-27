#!/usr/bin/env bash
set -euo pipefail
# Explicit future validation command. Never invoked by preparation scripts.
cd "$(dirname "$0")/.."
mkdir -p build-tests
incs=(-Isource/runtime/shm/include -Isource/runtime/shm/shm-queue/include
      -Isource/runtime/shm/shm-contract/include -Isource/runtime/shm/cuda-dispatch/include)
flags=(-std=gnu11 -O1 -g -Wall -Wextra -Wno-misleading-indentation -pthread)
cc "${flags[@]}" "${incs[@]}" tests/queue_paths.c source/runtime/shm/shm-queue/src/perf.c -o build-tests/queue_paths
cc "${flags[@]}" "${incs[@]}" tests/session_ipc.c source/runtime/shm/src/session_ipc.c -o build-tests/session_ipc
cc "${flags[@]}" "${incs[@]}" tests/owner.c -o build-tests/owner
build-tests/queue_paths
build-tests/session_ipc
build-tests/session_ipc events
build-tests/owner
python3 -m unittest discover -s tests -p test_broker_paths.py
python3 -m unittest discover -s source/tests/control -p test_bulk_copy.py
python3 -m unittest discover -s source/tests/control -p test_path_direct.py
