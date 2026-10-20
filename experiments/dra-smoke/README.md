# HAMi DRA integration validation — 2026-10-20

Environment: gpu-4, Kubernetes 1.37.0, CRI-O 1.37.0, NVIDIA RTX PRO 6000 Blackwell
Server Edition. DRA owns only GPU UUID
`GPU-c654d43e-43f8-c28e-77c2-1f17a0cbf46a` (index 2). Classic HAMi excludes that
UUID and continues to advertise GPUs 0, 1 and 3. This separation is retained with
the DRA driver; two independent allocators must not advertise the same GPU.

## Implementation exercised

- Explicit `resource.k8s.io/v1` Claim creation by VMWeave; no compatibility webhook.
- Fixed profile node/UUID and memory/core requests; allocation-result validation.
- The driver is built from upstream commit
  `300224ac789ad40ced1ea2d9b47f6ba4a7cb5c69` plus the repository UUID allowlist patch.
- The final driver includes the published VMWeave patched HAMi-core and atomic
  library installation. Worker library hash is in `results/20261020/worker-library.sha256`.
- Separate namespace-scoped test Operator and a disposable VM with its own disk
  and local shared-memory PV. Existing running VMWeave and AI-service workloads
  were not selected as test workloads.

## Results

- Actual Guest → broker → shared memory → DRA-allocated Worker → GPU memory copy
  and PTX kernel execution: PASS, including consecutive jobs and a VM reboot.
- Reboot generated a fresh allocation, Worker and Claim; final halt removed Claims.
- Operator restart during shutdown preserved cleanup progress.
- Worker deletion produced Unavailable, followed by successful VM halt and Claim
  cleanup (`worker-failure.json`).
- 2GiB memory limit: a 16MiB allocation succeeded and a 3GiB allocation returned
  `CUDA_ERROR_OUT_OF_MEMORY` for both tested compute settings.
- Short native Worker probe: 25 cores produced 1,400.21 launches/s; 100 cores
  produced 10,885.71 launches/s. These establish throttling, **not** calibrated
  25%-of-throughput behavior. Different kernels, longer windows and repeats are
  needed for a performance/accuracy study. No PyTorch training was performed.
- An additional 100-core request while a 50-core allocation existed remained
  unallocated/Pending; there was no silent fallback to classic HAMi.
- Library initializer changed the destination inode while an existing mapping
  retained its old bytes, avoiding truncation of libraries in running consumers.
- Go vet/race tests, classic control tests (57), deployment tests (14), CRD mirror
  checks, server-side schema dry runs, Helm lint/package and strict docs checks.

The initial guest disk cached its first-boot MAC in netplan. A later boot used a
different MAC and stalled networking. The disposable disk was halted and repaired
to match Ethernet interfaces by name; subsequent boots passed. This was a guest
image configuration issue, not a DRA allocation failure.

## Scope and evidence

Small retained result files live in `results/20261020`. Full local audit data,
rendered manifests, pinned images, install logs and test commands are under
`.local/dra-review/` on the validation host. The chart is a development version;
this work does not publish new registry images or a public release.

These tests do not establish recovery from node power loss, multi-node placement,
other Kubernetes/runtime versions, or precise compute-share proportionality.

## Retained environment and cleanup

Final verification also ran on the final Operator image after adding the
missing-Claim replacement guard. Its results are in
`results/20261020/final-operator-smoke-events.json`.

`results/20261020/cleanup.json` records successful removal of the disposable
Operator, VM, Claims, PVCs/PVs and test disk. `vmweave-dra-driver` and DeviceClass
`vmweave-hami-dra` remain ready for reuse. The retained image digest and settings
are in `summary.json` and `retained-driver-values.json` in the same result folder.

The classic HAMi exclusion for GPU 2 remains necessary. Existing VMWeave
Operator/VMs and existing AI services were preserved: the requested clarification
about deleting older resources was not answered during this run. No existing VM
disk or research result was deleted. Cluster-scoped VMWeave CRDs retain the
backward-compatible schema additions, since existing classic installations use
them too.
