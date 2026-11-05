# VMWeave guest Kubernetes device plugin

Optional node integration, installed by the administrator of Kubernetes **inside**
a VMWeave guest. It advertises `vmweave.io/gpu: 1`: exclusive access to the VM's
existing quota, not a physical GPU or a new allocation from the outer cluster.
One CUDA client per allocated container is supported. HAMi nesting, multiple
concurrent GPU clients and direct-Guest/Pod arbitration are outside v0.1.

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

## Contract v1

- One stable device ID `vmweave-slot-0`. The boot/allocation/generation describe
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
- Status JSON is atomically replaced at `/run/vmweave-device-plugin/status.json`.
  Its parent/file must be owned by root and not group/world writable. Symlink
  files, unsupported schema/protocol, stale/future timestamps, wrong boot,
  invalid allocation/generation, library mismatch and wrong socket GID/mode
  fail closed. `maxClients` must equal 1.
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
