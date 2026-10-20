# HAMi DRA backend

VMWeave supports an opt-in `hami-dra` GPUProfile backend. Omitted `backend` retains
classic HAMi. This implementation directly creates ResourceClaims; a converting
webhook is not required. The initial scope is one NVIDIA GPU on the profile's
fixed node and UUID. VM, Worker and local backing PV must share that node.

## Prerequisites

Use the pinned driver/chart source described in `runtime/hami-dra/README.md`.
The deployment was exercised on Kubernetes 1.37.0 and CRI-O 1.37.0. Other versions
need their own validation; the upstream minimum is not a VMWeave support matrix.
DRA Consumable Capacity, CDI, KubeVirt and the usual VMWeave prerequisites are
required. API discovery alone cannot verify host runtime configuration.

On a shared node, reserve disjoint GPU UUIDs for classic HAMi and DRA. The driver
has a UUID allowlist patch, and classic HAMi's `filterdevices.uuid` excludes those
UUIDs. Existing consumers must finish before transferring ownership. Never
advertise an in-use GPU through a second independent allocator.

## Build and install the driver

Build `images/hami-dra/Containerfile` from the repository root and distribute the
result to the target node/registry. No DRA image release is implied by this source
change. Use an immutable tag or a digest supported by your image distribution.

Fetch upstream commit `300224ac789ad40ced1ea2d9b47f6ba4a7cb5c69` from
`https://github.com/Project-HAMi/k8s-dra-driver.git`. Its chart is at
`chart/hami-dra-driver`. Copy and fill `deploy/hami-dra/values.example.json` with
the node, allowed GPU UUIDs, image and host driver/runtime paths. Keep the
extended-resource DeviceClass disabled: this deployment uses explicit Claims.

```sh
helm upgrade --install vmweave-dra /path/to/pinned-driver/chart/hami-dra-driver \
  --namespace vmweave-dra-driver --create-namespace -f driver-values.json
kubectl apply -f deploy/hami-dra/deviceclass.json
```

Install the VMWeave chart using the portable installation procedure and an
Operator built from this change. Helm does not upgrade CRDs automatically: apply
the matching canonical CRDs before upgrading the Operator. Existing classic
profiles keep their default behavior. Create a new profile for a new backend;
backend and DeviceClass are immutable.

Add these fields to an otherwise normal approved GPUProfile:

```yaml
backend: hami-dra
draDeviceClass: vmweave-hami-dra
schedulerName: default-scheduler
hamiNamespace: vmweave-dra-driver
```

The profile still needs `nodeName`, `gpuUUID`, limits, and a digest-pinned Worker
image. Use the runtimeClass supported by your target runtime. Keep the existing
GPURequest interface (`count: 1`, memory, compute).

```sh
python3 scripts/operator/preflight.py \
  --namespace YOUR_WORKLOAD_NAMESPACE --node YOUR_GPU_NODE \
  --backend hami-dra --device-class vmweave-hami-dra --gpu-uuid YOUR_GPU_UUID \
  --output preflight.json
```

## Lifecycle and diagnostics

The Operator creates a generation-owned Claim, then a consuming Worker so the
scheduler can allocate the claim. It verifies Claim identity, driver, consumed
capacity, node and the published device UUID before reporting readiness. The
Worker also checks its actual CUDA UUID, memory ceiling and loaded HAMi library.
The execution backend remains HAMi-core even though the allocation API is DRA.

Inspect channel `status.backend`, `claimName`, `claimUID`, and the referenced
Claim's allocation and `reservedFor` entries. Controller logs distinguish
`DRAAllocationPending`, `DRAWorkerScheduling`, and `DRAClaimReleasePending`.
A missing class or device prevents a new allocation. A missing API or RBAC access
is an operational error and never silently falls back to classic HAMi.

On shutdown, existing detach/backing reclamation checks remain in force. The
Worker must disappear and the Claim must be deleted before the channel becomes
Released/Reclaimed. A persistent VM's next boot gets a new allocation and Claim.
Do not remove finalizers to force a cleanup through an unresolved node failure.

For clusters without direct host-to-Pod routing, GPU smoke accepts
`--virtctl /path/to/virtctl` to tunnel SSH through KubeVirt. Test guest networking
across reboots: dynamic MAC addresses must not conflict with cached netplan
configuration.

## Cleanup

Halt test VMs and wait for channels to reach Stopped/Released and Claims to be
removed. Delete the test channel/request/profile/VM, then uninstall only the test
VMWeave Operator release. Retain PVCs/disks unless explicitly disposable.
Keep the separate HAMi DRA driver release, DeviceClass, node image and dedicated
host hook directory for reuse. Keep the classic-HAMi exclusion for its GPUs.
