#!/bin/bash
set -euo pipefail
hostname
date -u +%FT%TZ
cd /tmp/campaign
sudo env FLYT_LAYOUT=/tmp/campaign/layout.bin \
  FLYT_IVSHMEM_BDF=0000:00:1e.0 FLYT_SLOT=0 LD_LIBRARY_PATH=/tmp/campaign \
  ./campaign-probe-guest integer resident 45 0 64 2030 0 - -
