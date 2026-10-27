# VMWeave path optimization in v0.5.5

The v0.5.5 runtime combines native memset, direct Guest bulk input, reusable Broker/Worker buffers,
gather submission, a host-only parent/child arena, a same-thread native transport owner,
host eventfd notifications, and a bounded async H2D pinned/event pool.
Metadata validation, single outstanding request, CUDA-session process isolation and failure fencing remain.
There is no multi-request pipeline, early D2H return or cross-VM eventfd notification.

## Configuration

Binary defaults remain opt-in. The published v0.5.5 Worker image sets
`VMWEAVE_WORKER_REUSE=1`, `VMWEAVE_SESSION_ARENA=1`, `VMWEAVE_SESSION_EVENTFD=1`,
and `VMWEAVE_PINNED_POOL=1`, matching the tested combined Worker configuration.
An explicit container environment can override image defaults; eventfd requires the session arena.

Before a fresh VM binding, set these lines in `/etc/vmweave/guest-broker.env`:

```ini
VMWEAVE_BULK_COPY=1
VMWEAVE_BROKER_REUSE=1
VMWEAVE_BROKER_GATHER=1
VMWEAVE_BROKER_OWNER=1
```

Applications must receive these variables (including explicit Pod/service environments for non-login workloads):

```sh
export VMWEAVE_BULK_COPY=1
export VMWEAVE_BULK_DIRECT=1
export VMWEAVE_NATIVE_MEMSET=1
```

Use the matching v0.5.5 Guest library, Broker and Worker. The installer preserves existing environment files;
Helm does not replace files inside an existing Guest. Never restart a Broker against live SHM rings or
replace a library while a client owns a CUDA session. Apply package/configuration updates while the
Broker is stopped, halt the VM, wait for channel Stopped, rebind the approved image set, then boot a new VMI.
The release rollout configures login environments; Kubernetes Pods and standalone services need explicit variables.
State/math caches and wait profiles are not changed by this rollout. Spin remains 0us and sleep 50us.

## Evidence and limits

Fifteen actual VMs (five per condition) provided 150 timed workload samples. The combined candidate reduced
execution time by 34.3% versus the same candidate with new options disabled (existing bulk enabled).
It took 10.0% longer than Flyt SHM overall; SRAD took 1.88 times as long. The release does not claim Flyt superiority.
The user explicitly authorized replacing the prior VMWeave after reviewing these results.

Actual-VM data correctness, CUDA-child failure/recovery and VM generation recreation passed. GPU Compute
Sanitizer did not reach Worker readiness and is not a passed qualification. Full syscall failure coverage,
long-running concurrency and individual-feature performance attribution remain outside the completed tests.

[Measured comparison](https://github.com/WoogiBoogi1129/VMWeave-GPU/blob/main/experiments/ai-passthrough/results/20261027-path-optimization-vm/REPORT.md)
contains the fixed protocol, raw results, confidence intervals and remaining work.
The release preserves v0.5.4's fatal bulk-error fencing and environment-preserving installer on top of the frozen candidate.

## Rollback

With no active clients, stop the Broker and restore the captured previous Guest/Broker package and environment.
Halt the VM and wait for channel Stopped before restoring the previous approved Profile/Request/channel image
references and saved Helm revision, then boot a fresh VMI. Preserve the VM and root/SHM PVC identities.
Do not mix an old Worker with an enabled native-memset Guest. Disabling only an application option is not a
complete rollback of the combined Broker/Worker configuration.
