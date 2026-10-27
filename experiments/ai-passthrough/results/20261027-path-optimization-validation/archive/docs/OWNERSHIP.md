# Interfaces, ownership and lifecycle

All candidates are unbuilt/unexecuted. These are contracts to verify, not results.

| Path | Storage owner | Reader | Reuse boundary | Failure action |
|---|---|---|---|---|
| P1 application source | application, Guest lock serializes wrapper | Guest copy | payload copied into bulk arena; wrapper still waits for reply | no replay |
| Guest/Broker bulk arena | Broker-created per connection | application/Broker | successful or error reply after backend request returns; failed sessions discarded | unmap local view; never assign old mapping to new session |
| P2 Broker scratch | Transport under session lock | ctypes/I/O owner | synchronous exchange returns | clear session references on close |
| P2 Worker take_into | Worker parent | parent and socket sender | response published, then next request | clear borrowed request; caller frees allocation once |
| P3 split request descriptors | Broker private header and I/O job | transport owner thread | exchange returns | pointers remain live through terminal return |
| P3 SHM payload | existing channel | Worker private snapshot | existing request/response credit | abort channel; never resubmit |
| P4 host arena upload | parent fills data; child installs private socket header | CUDA child | synchronous copy API returns, reply received | kill/reap child before destroying parent arena |
| P4 host arena download | CUDA child | parent | parent copies validated produced bytes to VM response | never return bytes on error |
| P5 owner context | creating OS thread/process | same thread only | explicit close | sticky failure, subsequent calls rejected |
| P6 eventfds | parent creates, child inherits per session | each endpoint consumes its own event | exactly one notification per socket packet | count mismatch/timeout/EOF fails session |
| P7 pinned pool | CUDA session process | GPU copy engine | completion event succeeds | enqueue/record/query errors terminate execution; do not reuse |

## APIs

- P1 `vmweave_broker_copy_direct`: descriptor plus source data; shared
  `exchange_impl` preserves PID fence, connection/health checks, locking,
  invalidation and error handling. Unsupported capability can materialize a
  legacy request before any CUDA operation. No fallback after a sent operation.
- P2 `worker_take_into` is distinct from allocating `worker_take`. Its request
  must be cleared with `request_clear_borrowed`, never `request_release`.
- P3 `submit_parts` takes at most two bounded segments, sums lengths before copy,
  and publishes only after both are copied. It retains the original wire layout.
  `guest_exchange_parts` synchronously owns both caller buffers through return.
- P4 host IPC uses a 64-byte little-endian private socket descriptor, protocol
  version 1. Header fields are magic/version/mode/api/sequence/input length/output
  capacity/transport/domain/result/reserved/produced bytes. Three modes: inline,
  synchronous H2D arena, synchronous D2H arena. The two arena halves have fixed
  offsets; no arbitrary pointer or offset is accepted from a peer. Handshake must
  complete before CUDA requests. Unknown versions fail; there is no in-flight
  downgrade. Parent execs the same executable for the child.
- P5 owner context is an additive C API, separate from the legacy Guest I/O-thread
  interface. Python still handles the existing socket protocol in this first
  candidate; all C transport calls occur in the single owner/serving thread.
  Only connection admission runs in another thread. Heartbeats and partial-packet
  deadlines remain active. This is not a full Python-to-C Broker rewrite.

## Lock/order rules

Application public Guest lock precedes Broker lock. New Broker entry points call
one common implementation and never recursively call public exchange under its
lock. P3 keeps the existing transport I/O-thread locking; P5 uses an independent
context with owner-thread checks and cannot share its channel with that thread.
The Broker session lock protects scratch, epoch and arena lifecycle.

## Notification ordering

P6 notifies after writing the 64-byte socket header and after any arena upload
has been filled. Inline payload follows notification, so a large socket write
cannot deadlock waiting for a receiver that is waiting for notification. Replies
follow the same rule. Eventfd counts are drained and must equal one because only
one request is outstanding. Socket HUP/ERR and bounded deadlines terminate waits.
Acquire/release fences bracket arena publication/consumption. No eventfd crosses
the VM boundary. A syscall notification may cost more than socket polling; it is
an experimental alternative, not a claimed speedup.

## Memory costs and limits

P2 Worker scratch reserves up to 64 MiB per Worker slot when enabled. P4 arena
reserves two halves of 16 MiB + 4096 bytes per CUDA session and still retains the
Worker private snapshot. P7 retains completed pinned blocks within the existing
async staging budget and 128 slots; size classes are powers of two from 4 KiB.
Eviction frees only completed slots. Capacity (not transfer size) is accounted
for pooled allocations. Whole-process exit remains the fatal-error cleanup path.

## Compatibility

Existing VM wire/opcodes are unchanged except additive P0 opcode 0x2108.
P1 uses the existing bulk protocol. P3 resolves its local C symbol before any
request; missing symbol selects existing staging. P5 requires matching owner
symbols and fails at initialization rather than silently mixing ownership modes.
P4/P6 are internal same-binary parent/child opt-ins. Async/D2D payload transport
continues on the inline socket path. Flags are frozen at process initialization or
first use; change only in a fresh process/session.
