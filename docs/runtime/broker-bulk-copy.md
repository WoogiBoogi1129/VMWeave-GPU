# Opt-in Guest–Broker bulk copy

This opt-in path removes bulk H2D/D2H bytes from the Guest-local Unix socket.
It does not map BAR memory into applications, change the Worker protocol,
remove CUDA synchronization, or provide zero-copy GPU transfers.

Enable `VMWEAVE_BULK_COPY=1` in both the application and Broker environments.
Default is disabled. The experimental threshold is 1 MiB per synchronous copy
chunk; the maximum remains 16 MiB and existing transport negotiation may reduce
it. Small copies, D2D and asynchronous operations use the existing path.
Threshold is fixed before the pilot, not tuned against Rodinia results.

## Protocol and ownership

Broker controls 0x7ff2 (OPEN) and 0x7ff3 (COPY) are local-only. OPEN has zero
input/output capacity. Success returns the usual 16-byte response and exactly
one SCM_RIGHTS FD. The version-1 arena is a 32 MiB memfd: first 16 MiB H2D,
second 16 MiB D2H. Its size is sealed against growth/shrink and further seals.
The Guest validates file size, type, seals and FD count and receives the FD with CLOEXEC before mapping.
An explicit unsupported response uses the old copy path; malformed/ambiguous
negotiation fails the session. An in-flight copy is never retried as fallback.

COPY sends the ordinary 48-byte synchronous-copy descriptor on the socket;
only payload lives in the arena. The Broker validates direction, length and
response capacity, adds its own epoch/API envelope, and takes a private H2D
snapshot before submission. D2H transport output goes directly into the second
arena region. The reply reports produced bytes; it carries no payload bytes.
Routing metadata is never read from mutable shared memory. A client can mutate
its own payload, as with an application data race, but cannot change validated
handles, offsets, lengths, epoch or opcode through the arena.

The existing Guest exchange mutex serializes use. The response is the buffer
reuse boundary. The Broker retains exclusive session ownership and existing
Worker validation. Disconnect closes the Worker session and Broker mapping;
future clients get fresh, zeroed memfds. A disconnected client may retain its
old mapping but that memory is never reused for another session. Child-process
use is rejected by the existing inherited-process fence.

Memory cost: 32 MiB virtual arena per active session plus the existing private
request buffers; committed pages depend on use. No per-copy FD passing occurs.
The first pilot intentionally retains the Guest request-buffer copy and the
Broker's private H2D snapshot. Claims of eliminating all intermediate copies
would be incorrect.

## Validation and rollout

`python3 -m unittest discover -s tests/control -p test_bulk_copy.py` compiles the
actual C client and checks Unix FD passing, 1 MiB/16 MiB boundaries, fallback,
size seals, invalid metadata and unnegotiated operations against a mock Worker.
This is not GPU performance evidence. Existing cache/session tests remain required.

GPU qualification must use a separate VM with the candidate library and Broker,
checking large/chunked and asynchronous copies and unchanged Rodinia outputs.
Compare feature off/on in alternating order; profile socket bytes separately
from timed runs. Existing Flyt measurements provide context, not a matched new
three-way experiment. Promotion requires independent sessions and no correctness,
isolation or small-copy regression. Do not replace an active production Broker.
Rollback is disabling the feature for new application sessions; a deployed
Broker/library replacement requires the ordinary stopped-VM lifecycle.

## Installation and updates

The standard installer creates `/etc/vmweave/guest-broker.env` with
`VMWEAVE_BULK_COPY=0` on a new installation and preserves it on upgrades.
The systemd service reads this file. Set it to `VMWEAVE_BULK_COPY=1` before
a fresh VM binding and also export that variable for the application.
Do not restart the Broker against live transport rings to apply configuration.
Helm does not update the library or this configuration inside an existing VM.
Keep the Guest library and Broker from the same guest-artifacts package.
Disable the application flag for subsequent sessions to return to the old path.
A package rollback requires the stopped-VM lifecycle and the previous matched
Guest/Broker package; preserve the environment file and previous Helm values.

The compact matched experiment is recorded under
`experiments/ai-passthrough/results/20261026-bulk-short`. It shows workload
improvements, but does not establish universal absence of small-copy regression.
