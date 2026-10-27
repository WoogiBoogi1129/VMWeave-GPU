# Validation handoff

No commands in this document were executed during the initial preparation.
The user subsequently authorized validation after the Flyt campaign ended.
See [executed validation](../validation/REPORT.md) for current results and remaining
coverage. This document preserves the original broader qualification checklist.

## Before any execution

Confirm the existing campaign is finished AND its test resources are reclaimed.
Record source hashes, GPU identity/reservation, CPU/NUMA placement, quota,
CUDA/compiler versions, loaded libraries and all option values. Do not reuse
active VM/backend/MPS resources or overwrite production artifacts.

## Build and CPU tests

```sh
bash tests/run_cpu.sh
CUDA_ROOT=/path/to/cuda-12.8 bash tests/run_cuda_mock.sh
cmake -S source/runtime/shm -B build -DCUDAToolkit_ROOT=/path/to/cuda-12.8
cmake --build build --parallel 2
```

Full build requires the baseline cuDNN/cuBLAS dependencies. Run the relevant
baseline broker/cache/session/large-copy/naming tests under `source/tests` after
reviewing their environment requirements. Some integration tests use real GPU or
VM fixtures: do not execute all copied tests blindly. Rebuild CPU queue/IPC tests
with ASan/UBSan and complete leak/FD/timeout cases before GPU qualification.

Prepared executable tests:

- queue_paths.c: actual queue gather, overflow, too-small take, borrowed ownership,
  private snapshot, legacy allocation/release and receive-only retry.
- session_ipc.c: actual host IPC with fork/socketpair/memfd and optional eventfds,
  H2D/D2H payload, handshake, sequence progression and normal descriptor cleanup.
- owner.c: actual C owner with mocked mapping/queue, thread affinity, capacity,
  unsupported API, sticky failure and close.
- pinned_pool.c: actual pool acquisition/reap with mocked CUDA allocation/events,
  size classes, in-flight exclusion, completion reuse and memory cap.
- test_broker_paths.py: actual Python Broker scratch/gather, logical lengths,
  output prefix, invalid metadata and mmap reference lifetime.
- test_bulk_copy.py (baseline copy) and test_path_direct.py: real compiled C client
  with mock Broker and FD passing; direct entry, capability fallback and boundary
  coverage. This does not yet prove the full Guest wrapper's large-copy behavior.
- tests/memset: the previously prepared P0 real wrapper/dispatcher mocks.

The prepared tests have now run; see the report for outcomes and added cases.
The broader failure/concurrency qualification checklist is retained below;
executed cases are identified in the report. Qualification
must cover the following; do not infer coverage from successful normal roundtrips:

1. P1 full Guest chunked copy (16 MiB±1 and final short chunk), PID/fork fence,
   cached and noncached failure paths, short I/O, allocation failure before send.
2. P2 take/respond repeated across epochs, early cleanup and all capacity edges;
   Broker allocation failure and disconnect while an exported mmap view exists.
3. P3 missing-symbol fallback, stopped I/O owner, invalid segment pointers/lengths
   that are within the supported API contract; no response-buffer reuse early.
4. P4 corrupt version/sequence/mode/length, partial header/payload, child exit at
   each protocol state, retained old mapping, mapping/FD/exec allocation failures.
5. P5 differential Python legacy vs direct-owner Broker with identical request
   streams, busy admission, idle heartbeat, partial packet timeout, cache lease,
   EOF/CLOSE, owner-thread/PID misuse, cleanup while another connection is queued.
6. P6 notification-before-wait and after-wait, extra/missing event count, peer
   death without notify, interrupted waits and deadline expiry. Test without
   eventfds as a separate comparator, not an implicit fallback.
7. P7 pool eviction/exhaustion across streams, event/query/record/allocation
   failures, pinned memory accounting and session destruction with pending DMA.

## GPU qualification and measurements

Follow the parent plan's correctness tests before timing. Verify final results
and canaries after explicit completion, plus async stream/event order and session
isolation. Validate P0 last-error behavior against native CUDA separately.

Use `preparation/matrix.json` as the fixed candidate matrix; it contains the
baseline plus one-feature and cumulative combinations, not measured results.
Use separate fresh sessions per condition, at least five independent repetitions,
fixed balanced order, and exclude recorded warmup. Report caller-return and
completion-inclusive latency separately. Collect all Guest/Broker/Worker CPU and
memory, and perform detailed tracing in separate runs. Flyt comparisons require
new matched Flyt measurements. No expected improvement percentage is assumed.

Promote individual patches only after compile/link, regression, GPU correctness,
resource cleanup and performance review. New options remain OFF by default.
Rollback starts a new session with the option disabled or the baseline artifacts;
never rewrite a live session's libraries, mappings or layout.
