# SHM latency controls and telemetry

This first implementation keeps protocol v1, one in-flight request, request IDs,
timeouts, and synchronous CUDA semantics. Both endpoints must be configured to
evaluate a wait-policy change. No doorbell, cross-VM futex, CUDA Graph, pinned
memory, or transparent asynchronous return is introduced.

| Environment | Values | Meaning |
|---|---|---|
| `FLYT_WAIT_MODE` | `legacy`, `bounded` | Existing 1ms sleep, or bounded polling followed by short sleeps |
| `FLYT_SPIN_US` | 0–1000 | Initial active polling budget per wait episode; 0 disables active polling |
| `FLYT_SLEEP_US` | 1–1000 | Short sleep request, default 50µs; actual OS sleep can be longer |
| `FLYT_COPY_MODE` | `legacy`, `optimized` | Independent switch for private buffer reuse and payload-copy changes |
| `FLYT_METRICS` | `0`, `1` | Per-thread accumulated stage timing, emitted to stderr on close |

After 10ms without work the bounded wait requests 1ms sleeps. Idle workloads do
not reserve a spinning CPU. This also means the first request following idle may
still encounter the long sleep. Policy is initialized once per process; start
fresh processes to change it. An invalid numeric setting uses its fallback.

Optimized H2D reuses the Guest staging allocation and passes the validated
Worker-private snapshot directly to the synchronous copy backend. Optimized D2H
uses the Worker's preallocated private response buffer, avoiding an intermediate
allocation/copy. The execution API explicitly records borrowed ownership; it
never frees a caller-owned buffer. Backend copy must release dependence on host
buffers before returning. Async CUDA paths do not use this borrowing shortcut.

Payload snapshots use aligned, bounded volatile 64-bit loads with byte prefixes
and tails on the supported x86 memory mapping. No load extends beyond the
validated payload. Descriptor/header snapshots remain byte-based. The copied
payload is private before decoding. Neither this nor the old byte loop provides
an atomic snapshot of a concurrently changing entire payload; the same private
validation and peer-misbehavior checks still apply. This path is not GPU zero-copy.

Telemetry contains `submit`, `take`, `respond`, `receive`, `dispatch`, `exchange`
counts/durations/bytes and sleep/poll counters. `receive` includes waiting;
`exchange` includes Guest I/O handoff. These stages overlap and must not be summed
as independent end-to-end costs. Totals include startup, warmup and shutdown;
measurement-window latency/CPU comes from the benchmark CSVs and cgroup samples.
Telemetry is thread-local: closing a channel dumps its owner thread; the Guest
destructor dumps the exiting caller thread. It is not an aggregate of arbitrary
application threads. It is disabled unless explicitly requested.

The reproducible four-way VM campaign is in
[experiments/shm-first-bundle](../../experiments/shm-first-bundle/README.md).
