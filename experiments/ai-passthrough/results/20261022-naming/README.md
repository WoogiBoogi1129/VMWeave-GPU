# v0.5.0 naming migration canary

One existing small/batch-1024/resident training workload; 30 warmup and 200 measured steps per process. Baseline and restored use the previous state-cache implementation with FLYT variables; renamed uses the packaged candidate Guest library and VMWEAVE variables. Cache enabled in all three. The Worker is the same candidate image throughout. This isolates Guest naming compatibility, not the original passthrough performance gap.

| Run | samples/s |
|---|---:|
| Baseline | 18509.166 |
| Renamed | 18598.301 |
| Restored | 18821.568 |

Renamed lies between the baseline runs; this single sequence does not establish statistical equivalence. Loss, gradients and weights at steps 1/10/100 are exactly equal. All 29 prior exported flyt_* Guest symbols remain available. Binary hashes and candidate image digest are in status.json. This is local pre-release validation, not validation of the subsequently published image.

Validation: 81 control tests, 14 deployment tests, Go vet/race tests, strict documentation build, repository checks and GPU-free runtime image regression (including all six layout permission cases) passed. Full local logs and tensors are retained under .local/naming-release-20261022. No historical raw evidence was rewritten.

## Published release and current-system rollout

Final release is **v0.5.1**, adding the canonical `vmweaveRegisterKernelABI` with the previous name as an identical-address alias. v0.5.0 remains immutable and is superseded. [Release lock](../../../../deploy/releases/v0.5.1.json) records all seven image digests, chart digest and source revision.

Operator Helm revision 9 runs chart 0.5.1; DRA Helm revision 4 keeps upstream chart 0.1.1 and uses the released DRA image. The current VM `vmweave-test-a/vmweave-k8s-01` keeps its UID and root PVC. Its idle broker was stopped before installing the verified Guest package. The VM was halted and the previous allocation reclaimed. Because Profile/request/channel references and images are immutable, a new versioned Profile and request were created and the empty stopped channel was recreated. No CRD validation was bypassed. Historical profiles and the prior request remain available.

Published Guest/Worker memory copy and PTX execution passed (1,096 kernel iterations over two seconds). With both cache entries warm, killing the test session's Worker child resulted in error 999, including subsequent context lookup. A fresh process using `FLYT_*` settings and `/opt/flyt` aliases then completed GPU execution. The fault probe's elapsed time includes the controller-side delay before killing the child; it is not fault-notification latency. Live Guest SHA-256 equals the downloaded package. See `live-*.json` and `running-images.json`.

The DRA Driver is Ready and still advertises only GPU-c654d43e-43f8-c28e-77c2-1f17a0cbf46a. This update did not rerun a DRA allocation workload. Classic upstream HAMi 2.10.0 and unrelated application services were not redeployed; the VMWeave HAMi image was published separately. The temporary admin Pod and canary resources were removed.

Rollback uses the saved Helm values/manifests (Operator revision 8; DRA revision 3), the prior immutable Profile/request and old image digests, and Guest backup `/opt/flyt.pre-vmweave` plus the saved service file. Stop the VM and reclaim the allocation before recreating an older channel; do not try to revive a fenced session. Local backups and full logs are retained under `.local/naming-release-20261022`.
