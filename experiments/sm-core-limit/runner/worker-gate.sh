#!/bin/sh
# Canary only: the runner installs a read-only bind mount in this Pod's mount
# namespace and verifies its SHA before releasing this gate. No host file edit.
set -eu
until test -f /tmp/sm-core-ready; do sleep 0.2; done
export GPU_CORE_UTILIZATION_POLICY=FORCE
export LIBCUDA_LOG_LEVEL=3
exec /opt/flyt/bin/flyt-shm-worker.original "$@"
