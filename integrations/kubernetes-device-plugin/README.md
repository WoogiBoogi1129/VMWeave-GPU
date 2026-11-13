# VMWeave guest Kubernetes device plugin

Optional node integration, installed by the administrator of Kubernetes **inside**
a VMWeave guest. Each `vmweave.io/gpu: 1` allocation grants one broker slot.
The source supports one or two fixed slots sharing the VM's existing GPU quota.
Each allocated container supports one CUDA client. Physical GPUs, additional
VRAM, per-Pod memory/compute guarantees, HAMi nesting and direct-Guest/Pod
arbitration are outside this contract.

The published v0.1.2 release remains single-slot. Two slots require the matching
candidate Operator, Guest control package and Plugin from this working tree;
setting a chart value alone cannot upgrade released binaries.

[Installation and limits](../../docs/guides/kubernetes-device-plugin.md)

## Development

```sh
cd integrations/kubernetes-device-plugin
go test -race ./...
go vet ./...
go build -o /tmp/vmweave-device-plugin ./cmd
```

The tests use temporary Unix sockets and a mock kubelet. They cover actual gRPC
registration, ListAndWatch transitions, kubelet socket replacement, duplicate
plugin exclusion, invalid Allocate requests and untrusted/stale discovery. They
never connect to a real broker or open a CUDA session.

## Fixed-slot contract

- Stable device IDs `vmweave-slot-0` (and `vmweave-slot-1` in two-slot mode).
  The boot/allocation/generation describe
  the runtime binding, not additional devices. A new binding is not restoration
  of an old CUDA context; applications must restart after VM/runtime replacement.
- Register the server only after listening. Re-register on kubelet or plugin
  socket replacement. An advisory file lock excludes a second instance.
- Allocate checks discovery again and returns the broker directory read-only
  at `/run/vmweave`, plus `VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock`.
  No GPU device file, BAR, SHM backing, native driver or credential is injected.
- Allocate is repeatable and does not reserve/open a CUDA session. Kubelet owns
  container allocation bookkeeping; broker connections own CUDA session cleanup.
- Busy is not Unhealthy. A direct VM client is outside kubelet accounting and
  can contend with a scheduled Pod. Initial operation requires no concurrent
  direct GPU client; this is an operating condition, not an isolation guarantee.
- Single-slot mode retains schema v1 at `/run/vmweave-device-plugin/status.json`.
  Two-slot mode uses one schema v2 record per
  `/run/vmweave-device-plugin/slots/{0,1}/status.json`, with `slotIndex`,
  `slotCount: 2` and `sessionID`. The Plugin checks these and allocation/generation
  against the root-owned boot layout; it does not infer capacity from file count.
  Records are replaced atomically.
  Its parent/file must be owned by root and not group/world writable. Symlink
  files, unsupported schema/protocol, stale/future timestamps, wrong boot,
  invalid allocation/generation, library mismatch and wrong socket GID/mode
  fail closed. `maxClients` must equal 1 per broker. Each slot has independent
  health; loss of one record does not withdraw the other device.
- Set Channel `spec.sessions: 2`, an approving Profile with `maxClients >= 2`,
  and chart `slotCount: 2` (CLI `--slot-count=2`). The Guest reads the actual
  boot layout and starts separate broker processes with distinct `VMWEAVE_SLOT`.
  There is no session-manager CRD/database or dynamic resize. Session IDs and
  client epochs retain their existing lifetime semantics.
- Two-slot Allocate mounts only `/run/vmweave/slots/i` at `/run/vmweave`.
  Several container requests are accepted, each requesting exactly one distinct
  device. A container requesting two slots or duplicate device IDs is rejected.
- Forced Pod deletion does not confirm process termination. An immediately
  scheduled replacement can receive `busy(46)` while the old client is alive.
  Verify actual client/CUDA-child retirement before reuse, or retry a fresh
  application execution. Busy remains healthy and never permits duplicate access.
- A dead broker is not restarted on consumed SHM rings. Its peer continues;
  restoring the dead slot requires a fresh VM binding. Its host CUDA child and
  memory may remain reserved until VM shutdown reclaims the binding. Normal client exit
  reclaims its CUDA child and permits reuse without restarting the broker.
- `observedAt` and `transportObservedAt` are Unix seconds on the same guest.
  Both expire after 10 seconds (future tolerance 1 second). A long/stalled CUDA
  request can temporarily make new allocations unhealthy; existing execution
  is not killed. Clock rollback beyond tolerance also fails closed.
- `activeClient` is diagnostic. The publisher never opens CUDA sessions. Native
  owner mode only publishes observed progress; legacy mode takes the existing
  session lock for idle HEARTBEAT, never when a client owns it.
- Health means recent broker/SHM progress plus compatible artifacts, not a
  prediction that every CUDA operation or the physical GPU will succeed.
- Plugin has no Kubernetes API client, outer-cluster credentials or RBAC. Root
  filesystem permissions are needed for kubelet sockets; the chart drops all
  capabilities, requests no privileged mode and mounts only three directories.
- `doctor` uses the same checks without connecting to broker or kubelet. Do not
  use its failure as a broker liveness restart policy; a new runtime may be needed.

Broker status additions are backward compatible for direct users. Existing
brokers without discovery are deliberately not advertised by this plugin.
