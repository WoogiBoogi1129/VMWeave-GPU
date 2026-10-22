# Broker-mode device/context state cache

The feature is **off by default**. Set `VMWEAVE_STATE_CACHE=1` in the application
process to opt in. This does not select the diagnostic
`VMWEAVE_DIAG_STATE_CACHE` preload shim. No legacy network RPC transport is
introduced: cache misses use the existing Unix-socket broker and SHM Worker path.

## Scope and semantics

`vmweave_broker_exchange` is the common path after the CUDA wrappers. Calls through
global symbols, a specific-library `dlsym`, and `cuGetProcAddress` reach it.
The first version caches only device zero (`0x1002`) and an active primary context
(`0x2107`) with no request payload. The broker verifies that the session exposes
exactly one CUDA device. Inactive context responses are never cached. The current
proxy's synthetic context model is unchanged; this is not an implementation of
native CUDA's full per-thread current-context semantics. Direct SHM clients do
not use this cache.

The cache is scoped to one process and one broker connection/epoch. Argument
validation, owner PID, sticky session failure, and connection checks precede
hits. `cudaSetDevice` invalidates both entries before forwarding. An observed API
error invalidates both entries; error 999 or a transport/protocol failure fences
the connection. Closing the session also fences it. A forked child cannot use the
parent's connection, including when the inherited broker mutex was locked.
There is no same-process reconnect; start a fresh process for a new session.
Unsupported reset/release/context APIs are not newly enabled by this feature.
Future state-changing APIs must add invalidation before they are supported.

A cached value describes logical device/context state, **not an instantaneous
remote liveness check**. The broker checks Worker child liveness every 10 ms when
idle and between requests. If the epoch/child is invalid it shuts down the local
socket; the next client check fails instead of returning a cache hit. This check
uses the session child's socket, does not invoke CUDA and preserves the existing
child isolation and cleanup model.

The client also has a 50 ms lease, using a monotonic clock. After expiration it
must synchronously revalidate the epoch before using cached data. This prevents
an unresponsive broker from allowing unbounded cached successes. The existing
socket I/O timeout is 30 seconds; a blocked health request can therefore wait for
that timeout before reporting an error. The interval and lease are **not hard
real-time notification guarantees**: scheduling and transport delays exist, and a
Worker may die immediately after a successful check. A CUDA failure which has not
yet caused child exit or an error response is not detectable merely from socket
liveness. Applications requiring remote verification on every query must leave
this feature disabled. Known faults never become successful cache hits.

## Wire compatibility

Existing framing is unchanged. All integers follow the existing little-endian
wire format (current target: x86-64).

| Control | Request | Success response |
|---|---|---|
| Worker `VMWEAVE_SESSION_STATUS` (7) | 16-byte epoch | Same 16-byte epoch, if active child socket is live |
| Broker `VMWEAVE_BROKER_CACHE_OPEN` (0x7ff0) | Empty; capacity 24 | u32 version=1, u32 flags=1 (single-device/liveness support), 16-byte epoch |
| Broker `VMWEAVE_BROKER_CACHE_STATUS` (0x7ff1) | Empty; capacity 16 | Same epoch after Worker status check |

Broker controls use the API number range so an old broker forwards them to an
old Worker's unsupported-API handler without interpreting them as transport
controls. A new broker with an old Worker returns unsupported (801) for cache
negotiation. Without successful version/capability/epoch negotiation the client
continues ordinary calls without caching. Malformed successful capability data
also leaves caching disabled; malformed transport framing is a terminal error.
An old client does not negotiate and receives the original broker behavior.

No asynchronous response frames are added to the application byte stream.
Worker-death notification uses socket shutdown, avoiding races with normal reply
framing. The single owning broker thread performs status checks and calls in
order. CLOSE remains responsible for killing/reaping the session child.

## Verification and counters

```bash
python3 tests/control/test_guest_broker.py
python3 tests/control/test_state_cache.py
VMWEAVE_TEST_GUEST_LIBRARY=/absolute/path/libvmweave_guest.so python3 tests/control/test_state_cache.py
```

The last form adds actual CUDA symbol/function-pointer entry-path coverage, using
a fake remote Worker and no GPU. Other cases cover default-off, old broker,
old Worker, multiple devices, inactive-to-active state, setters, API errors,
fork, concurrent queries/close, Worker/broker death, changed epoch, expired lease,
invalid arguments, fresh flags, and malformed negotiation.

`vmweave_broker_cache_stats(uint64_t out[6])` returns cumulative process counters:
enabled, device hits, primary-context hits, broker wire requests, synchronous
lease renewals, invalidations. Take before/after snapshots; there is no reset.
Wire requests include negotiation and synchronous health controls. Broker's
periodic Worker status checks must be counted separately. These counters are
observability aids, not a stable CUDA API.

## Build, canary and rollback

Build using the existing `runtime/shm` CMake project and CUDA build environment.
Deploy matching Guest, broker Python source and session Worker to an isolated
canary. Keep the base artifacts and SHA-256 values. The validation runner is
`experiments/ai-passthrough/runner/state_cache_validation.py`; it is environment
specific, uses an existing CUDA/VM fixture and a preloaded Worker image, and must
be reviewed for resource names, registered idle GPU and image digest before use.
It performs one small/batch-1024/resident workload, 30 warmup steps and 200 measured
steps, correctness checkpoints, an off/on/restored comparison and a targeted
Worker-child kill followed by a fresh session. It does not run a workload sweep.

First rollback: unset `VMWEAVE_STATE_CACHE` (or set it to 0) and start a new process.
For full rollback, restore the pinned Guest library, broker source and Worker
image together and create a new session. Do not try to revive a fenced client.
BLAS setter elimination, asynchronous submission and broker replacement are not
part of this change.

## Optional BLAS math-mode setter cache

`VMWEAVE_BLAS_MATH_CACHE=1` additionally skips a repeated successful
`cublasSetMathMode` on the same handle. It is **off by default**, requires
`VMWEAVE_STATE_CACHE=1`, and is effective only after the existing broker/Worker
single-device epoch/health negotiation succeeds. Legacy peers and direct SHM
clients keep forwarding setters. No protocol, stream, workspace, GEMM, or kernel
submission behavior is changed.

The common broker exchange owns a bounded 64-entry table under its existing
mutex. Each entry stores the 8-byte wire handle and last successful 4-byte mode.
Only an exact 12-byte setter request with a successful empty response is recorded.
A new mode goes to the Worker; a full table forwards unrecorded handles every
time, while existing handles can still update. Errors are never installed.
All BLAS create/destroy requests conservatively clear the entire table. Device
changes, any observed API error, connection failure, epoch mismatch, and close
also clear it. Forked children fail before acquiring the inherited mutex.
There is no same-process reconnect; a new process starts with an empty table.

The current Worker changes math mode only in `VMWEAVE_BLAS_MATH_SET`; handle
creation/destruction is also intercepted. A future API that mutates or replaces
BLAS state must add invalidation before enabling it. Sharing opaque handles with
another broker session is unsupported; handles belong to the session child.

A hit occurs only after the existing health checks. The 50 ms lease is **not an
instantaneous remote liveness guarantee**. Native errors that would only be
observed by repeating a remote setter may be observed by a subsequent forwarded
operation instead. Applications requiring every setter to consult native cuBLAS
must leave this option disabled. Known session faults never return cached success.

`vmweave_broker_math_cache_stats(uint64_t out[5])` exports cumulative process
counters: effective enabled flag, hits, eligible forwarded misses, invalidation
operations, and successful setters not recorded because the table was full.
Invalidations count clearing operations even if the table was already empty.
The existing six-element state-cache statistics ABI is unchanged. Stats are
serialized by the same mutex and return zeroes in a forked child. The new option
has no legacy FLYT alias because it did not exist before this implementation.

Disable `VMWEAVE_BLAS_MATH_CACHE` (unset or `0`) and restart the application to
restore forwarding. Environment options are read once when the process connects;
changing its environment after negotiation does not change behavior. No Worker
image or Helm setting is needed for this application-process option.

Validation: `python3 tests/control/test_math_cache.py`; set
`VMWEAVE_TEST_GUEST_LIBRARY` to the full Guest library to include entry-point and
`dlsym` checks. Also run `tests/control/test_state_cache.py` against the same ELF.
