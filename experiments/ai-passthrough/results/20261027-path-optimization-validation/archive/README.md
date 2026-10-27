# VMWeave path optimization candidate

Prepared and validated 2026-10-27 (KST). Build, CPU/mock regression, CPU sanitizers
and host-file-backed SHM with real GPU correctness checks have been executed.
See [validation results](validation/REPORT.md) for fixes, evidence and exact scope.
Actual VM/PCI BAR integration, performance qualification and deployment remain pending.

`source/runtime/shm` is an isolated candidate. The original repository's relevant
product files were checked against the earlier baseline hashes and left unchanged.
The prior P0 candidate is preserved in its own directory. `baseline/` here includes
that unbuilt P0 candidate and the existing uncommitted bulk-copy implementation.

| Stage | Prepared implementation | Enable in a fresh process |
|---|---|---|
| P0 | native memset opcode, retained legacy path | application: VMWEAVE_NATIVE_MEMSET=1 |
| P1 | source→bulk arena, common Broker fencing and fallback | application: VMWEAVE_BULK_DIRECT=1 plus existing BULK_COPY=1 |
| P2a | bounded Broker scratch, logical sizes | Broker: VMWEAVE_BROKER_REUSE=1 |
| P2b | caller-owned Worker snapshot API | Worker parent: VMWEAVE_WORKER_REUSE=1 |
| P3 | two-segment submit/exchange and Broker gather | Broker: VMWEAVE_BROKER_GATHER=1 plus BULK_COPY=1 |
| P4 | session-only host memfd payload; versioned control messages | Worker parent: VMWEAVE_SESSION_ARENA=1 |
| P5 | native owner context on Broker serving thread | Broker: VMWEAVE_BROKER_OWNER=1 |
| P6a | bounded wait-profile matrix using existing options | see matrix.json; no default changes |
| P6b | optional host-only eventfd notifications | Worker parent: VMWEAVE_SESSION_EVENTFD=1, requires SESSION_ARENA=1 |
| P7a | bounded completed-buffer/event pool | CUDA child: VMWEAVE_PINNED_POOL=1 |

All new options default OFF. Existing `VMWEAVE_BULK_COPY=1` must be set on both
application and Broker for bulk paths. Wait profiles apply to the endpoints that
actually own the SHM queue. No live environment was modified.

## Deliberate implementation boundaries

- P5 keeps the existing Python socket protocol and adds a direct C transport
  owner. It removes the per-request C I/O-thread handoff, not all Python work.
  This narrows the migration while preserving epoch/cache/Broker behavior.
- P4 retains a Worker private snapshot and copies payload into the host arena;
  it removes socket payload transfer, not all intermediate copies.
- P7b multi-outstanding pipeline, asynchronous D2H early return and cross-VM
  interrupt wiring remain outside the approved first candidate scope, as in the
  full plan. They are not implemented or silently represented as completed.
- Executed tests and remaining qualification gaps are recorded in
  `validation/REPORT.md`; `VALIDATION-HANDOFF.md` retains the broader checklist.

## Artifacts

- `patches/`: ordered additive patches. P0 is archival relative to the earlier
  original runtime. Apply P1 onward to **this package's baseline/**, which already
  includes P0. Applying P0 twice is incorrect.
- `baseline.json`: exact starting snapshot and provenance.
- `candidate-manifest.json`: candidate source/test hashes.
- `preparation/static-review.json`: text-only review, patch replay and original
  file preservation; this is not C semantic verification.
- `tests/`: real-source mock/CPU tests and explicit execution scripts.
- `source/tests/`: baseline tests copied for later regression plus direct-copy
  integration tests. They are not auto-executed by preparation.
- `docs/OWNERSHIP.md`: memory, FD, thread, protocol and failure contracts.
- `docs/VALIDATION-HANDOFF.md`: ordered deferred validation and known gaps.
- `preparation/matrix.json`: original fixed feature/wait matrix. Its NOT_RUN status
  refers to the planned performance campaign; correctness results are in `validation/`.

`preparation/` records the original pre-execution checks. `validation/` records
subsequent execution, including the original failure logs and validation fixes.
P10 follows P9; do not sort patch filenames lexicographically (P10 would precede P2).
