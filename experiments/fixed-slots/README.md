# Fixed-slot GPU Pods inside one VM

This experiment validates the simplified two-slot candidate against real CUDA,
with one-slot regression first. It does not measure throughput or promise
per-Pod GPU memory/compute isolation. Both slots share the outer VM quota.

Published Operator/Plugin releases are not sufficient for two-slot mode. Build
this working tree's Operator and Plugin and package the updated Guest control
files before creating a fresh binding. The Worker, SHM ABI and Guest C library
are unchanged from v0.5.10 / device-plugin-v0.1.2.

## Preparation

Use a dedicated VM and an outer Operator scoped to its namespace. Follow the
existing [VM preparation](../../docs/getting-started/guest-images.md) and
[inner Kubernetes](../nested-k8s-gpu/README.md) procedures. Preserve a persistent
root disk and give the inner node enough resources for its control plane.
Verify all CNI components are ready before evaluating GPU allocation; Helm's
DaemonSet rollout can succeed with zero desired Pods on a tainted node.

1. Install the candidate Guest package while the broker is stopped. Its library
   SHA256 must match the Plugin and workload. Do not replace a live broker.
2. Configure an approved GPUProfile for a HAMi-registered GPU, not merely an idle
   GPU from `nvidia-smi`. This run uses a total 2048 MiB / 25% VM quota.
3. Create an immutable `lifecycle: VM` Channel with `sessions: 1`, start the VM,
   and install the candidate chart with `slotCount: 1`. Confirm node allocatable.
4. Build `workloads/concurrent.c` against the matching Guest library, copy it
   into the published compatible workload image at `/opt/vmweave/bin/concurrent`,
   and set that path as ENTRYPOINT. Record the actual CRI-store image digest.
5. Run the one-slot check below. Halt the VM and wait for Channel `Stopped`,
   detach evidence and backing reclamation. Delete the old Channel and clear
   only its VM binding annotations after proving it has been reclaimed.
6. Create the new Channel with `sessions: 2` and matching Profile approval,
   boot and set chart `slotCount: 2`. Do not edit immutable sessions in place.

Build the numerical probe using the extracted compatible Guest package:

```sh
cc -O2 experiments/fixed-slots/workloads/concurrent.c \
  -L /PATH/TO/GUEST-PACKAGE -lvmweave_guest \
  -Wl,-rpath,/opt/vmweave/lib -o /PRIVATE/BUILD-CONTEXT/concurrent
podman build -f experiments/fixed-slots/workloads/Containerfile \
  --build-arg BASE=COMPATIBLE-WORKLOAD-IMAGE@sha256:DIGEST \
  -t localhost/vmweave-fixed-slots-workload:TEST /PRIVATE/BUILD-CONTEXT
```

The private connection JSON has `sshArgv` (an argument array), `context`, `node`,
`image` (digest reference), `brokerGID`, `outerNamespace`, `channel` and `gpuUUID`.
Do not put keys, kubeconfigs or bootstrap tokens in result directories.

```sh
python3 experiments/fixed-slots/run.py \
  --connection /PRIVATE/connection.json \
  --output /NEW/result-directory \
  --namespace UNIQUE-TEST-NAMESPACE --slots 1
# After the fully reclaimed two-slot binding is ready, repeat with --slots 2.
```

`run.py` creates and UID-checks its own namespace, then deletes it even on
failure. Two-slot mode intentionally SIGKILLs one broker in the dedicated VM;
this requires a fresh VM binding afterward. The runner does not provision or
halt the outer VM, uninstall the Operator, or release the outer GPU reservation.
The administrator must perform that final cleanup after collecting evidence.

## Assertions

- Every SGEMM iteration checks all 16,384 output elements against a known matrix;
  different Pods use different inputs. Overlapping application intervals prove
  concurrent clients, not simultaneous hardware kernel execution.
- Two independent socket mounts and host CUDA processes; no layout, peer socket
  directory or NVIDIA device mounted in an ordinary workload container.
- Additional client on an occupied broker rejected; third Pod remains Pending.
- Plugin restart retains active computation; normal exit permits exact-slot reuse.
  After forced API deletion the test waits for the old CUDA process to be reaped
  before starting the replacement. Immediate replacement is separately recorded
  as a busy rejection; it is not claimed to succeed unconditionally.
- Killing one broker withdraws only that slot; its peer computes successfully.

CPU tests separately cover schema mismatch, stale generation/timestamps, missing
status, malicious paths, invalid allocation requests, independent gRPC health
updates, bootstrap child ownership/reaping and admission constraints.

The final run passed the scoped checks. Immediate replacement after forced API
Pod deletion can receive `busy(46)`; verify retirement first. A killed broker's
host CUDA child remained until VM shutdown and was reclaimed by the normal
binding teardown. See the report for these limits and preserved failed attempts.

```sh
python3 experiments/fixed-slots/analyze.py experiments/fixed-slots/results/20261113/two-reaped
```

[Recorded run](results/20261113/REPORT.md)
