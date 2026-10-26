# VMWeave v0.5.4

This release adds opt-in shared memory for synchronous Guest–Broker H2D/D2H
copy payloads. Copies of at least 1 MiB use a session-private sealed memfd;
individual chunks remain bounded to 16 MiB. Small copies, asynchronous copies
and D2D retain the existing path. This is not end-to-end zero-copy.

Both the application and Broker must set `VMWEAVE_BULK_COPY=1`. The installer
creates `/etc/vmweave/guest-broker.env` with the feature disabled and preserves
existing settings on upgrade. The systemd service reads that file. Do not
restart a Broker on live SHM rings: apply package/configuration changes before
a fresh VM binding. The Guest library and Broker must come from the same
published guest-artifacts image; a Helm upgrade alone does not update an
existing VM's filesystem.

A malformed negotiation, interrupted copy or fatal Worker error fences the
client session. An uncertain copy is never retried. Only an explicit unsupported
capability reply permits falling back during negotiation. Buffer ownership and
Worker handle, epoch and range validation remain in place.

The matched compact experiment reduced mean workload completion time by
29.15% (NW), 16.69% (LU), and 55.05% (SRAD) relative to the same candidate with
the feature disabled. StreamCluster's single measured sample decreased 8.59%.
Flyt remained faster. These are specific workload results, not universal
throughput or regression guarantees. See the
[experiment report](https://github.com/WoogiBoogi1129/VMWeave-GPU/blob/main/experiments/ai-passthrough/results/20261026-bulk-short/REPORT.txt)
and [protocol and configuration](../runtime/broker-bulk-copy.md).

For rollback, disable the application flag for new sessions. To roll back the
installed package, stop applications, restore the captured matching Guest/Broker
package and previous Helm configuration using the stopped-VM lifecycle, then
verify the new binding before resuming work. Keep VM and PVC identities and GPU
quota unchanged. HAMi and DRA do not require changes for this feature.

## Deployment record

The release was published and deployed on 2026-10-26 (KST), Helm revision 12.
Public-package equality, isolated chart installation, the 50%/2048 MiB GPU
canary, and production copy/kernel/output checks passed. The production VM
enables the feature in the Broker and new login sessions; sudo commands and
service workloads must set the application flag explicitly. Release defaults
remain disabled. See the [digest and validation record](https://github.com/WoogiBoogi1129/VMWeave-GPU/blob/main/deploy/releases/v0.5.4.json).
