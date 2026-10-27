#!/usr/bin/env bash
set -euo pipefail
# Explicit future validation command. Never invoked by preparation scripts.
cd "$(dirname "$0")/../.."
mkdir -p .local/path-optimization-tests
incs=(-Iruntime/shm/include -Iruntime/shm/shm-queue/include
      -Iruntime/shm/shm-contract/include -Iruntime/shm/cuda-dispatch/include)
flags=(-std=gnu11 -O1 -g -Wall -Wextra -Wno-misleading-indentation -pthread)
cc "${flags[@]}" "${incs[@]}" tests/path_optimization/queue_paths.c runtime/shm/shm-queue/src/perf.c -o .local/path-optimization-tests/queue_paths
cc "${flags[@]}" "${incs[@]}" tests/path_optimization/session_ipc.c runtime/shm/src/session_ipc.c -o .local/path-optimization-tests/session_ipc
cc "${flags[@]}" "${incs[@]}" tests/path_optimization/owner.c -o .local/path-optimization-tests/owner
.local/path-optimization-tests/queue_paths
.local/path-optimization-tests/session_ipc
.local/path-optimization-tests/session_ipc events
.local/path-optimization-tests/owner
python3 -m unittest discover -s tests/path_optimization -p test_broker_paths.py
python3 -m unittest discover -s tests/control -p test_bulk_copy.py
python3 -m unittest discover -s tests/control -p test_path_direct.py

cc "${flags[@]}" "${incs[@]}" tests/path_optimization/session_ipc_failures.c -o .local/path-optimization-tests/session_ipc_failures
.local/path-optimization-tests/session_ipc_failures
