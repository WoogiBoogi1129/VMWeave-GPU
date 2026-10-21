# v0.5.0 naming migration canary

One existing small/batch-1024/resident training workload; 30 warmup and 200 measured steps per process. Baseline and restored use the previous state-cache implementation with FLYT variables; renamed uses the packaged candidate Guest library and VMWEAVE variables. Cache enabled in all three. The Worker is the same candidate image throughout. This isolates Guest naming compatibility, not the original passthrough performance gap.

| Run | samples/s |
|---|---:|
| Baseline | 18509.166 |
| Renamed | 18598.301 |
| Restored | 18821.568 |

Renamed lies between the baseline runs; this single sequence does not establish statistical equivalence. Loss, gradients and weights at steps 1/10/100 are exactly equal. All 29 prior exported flyt_* Guest symbols remain available. Binary hashes and candidate image digest are in status.json. This is local pre-release validation, not validation of the subsequently published image.

Validation: 81 control tests, 14 deployment tests, Go vet/race tests, strict documentation build, repository checks and GPU-free runtime image regression (including all six layout permission cases) passed. Full local logs and tensors are retained under .local/naming-release-20261022. No historical raw evidence was rewritten.
