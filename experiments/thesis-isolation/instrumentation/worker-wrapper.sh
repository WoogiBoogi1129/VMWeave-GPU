#!/bin/sh
# Preserve existing HAMi preload; add a forwarding-only context observer.
export LD_PRELOAD="${LD_PRELOAD:+$LD_PRELOAD:}/opt/flyt/lib/context-observer.so"
exec /opt/flyt/bin/flyt-shm-worker.original "$@"
