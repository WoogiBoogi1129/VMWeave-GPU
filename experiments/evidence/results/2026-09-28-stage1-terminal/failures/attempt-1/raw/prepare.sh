#!/bin/bash
set -euo pipefail
python3 scripts/prepare-evidence-vm.py --name "$VM" \
  --reuse-pvc evidence-vm-a-backing --public-key "$DEMO/artifacts/guest-key.pub" \
  --memory-mib 4096 --compute 50 --sessions 1 \
  --guest-image "$GUEST_IMAGE" --worker-image "$WORKER_IMAGE" \
  --control-image "$CONTROL_IMAGE" --hook-image "$HOOK_IMAGE" \
  --output "$DEMO/private-prepare"
