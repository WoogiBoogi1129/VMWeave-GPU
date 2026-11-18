# Experimental bounded kernel submission

This patch is an opt-in experiment for the registered, typed `cuLaunchKernel`
path. It is disabled by default. It does not implement general CUDA interception,
CUDA Graphs, multi-stream batching, or Lupine's full custom RPC protocol.

Set `VMWEAVE_KERNEL_BATCH=1` in a broker client's environment. The Worker must
advertise v1 capability (`0x2034`). An explicitly unsupported old Worker keeps
the original synchronous path. Ambiguous failures never trigger replay.

Default-stream launches copy their encoded arguments into one process-local
queue. A packet contains at most 128 launches and 203,272 bytes. The caller
flushes at capacity; another remote CUDA operation flushes before proceeding.
The direct H2D path also flushes. A helper thread targets a flush 200 microseconds
after the first queued launch, so an application that stops making CUDA calls
does not leave work indefinitely buffered. Scheduling and transport delay can
exceed that target. The queue and transport share the existing Guest mutex;
there is only one packet in flight. This is bounded batching, not an unbounded
or fully pipelined asynchronous transport.

The Worker validates the whole packet before executing any launch. It preserves
packet order and stops at the first CUDA error. A failed packet makes this
client session terminal; a completed prefix is never replayed. Driver errors
can therefore surface at a later launch or synchronization call. A new client
connection is required after failure. Forked children cannot reuse the queue.
Ordinary process exit flushes pending work when the existing Guest lock can be
acquired; abrupt process death uses the existing broker session retirement.

Compatibility limits matter: launch-time errors may be delayed; unsupported
stream and packed-kernel paths remain synchronous; there is no general
application-performance or full CUDA-conformance claim. Keep the option off in
shared production workloads until application-level coverage is completed.

Host tests are integrated into `scripts/test-shm-training.sh`. They exercise
argument lifetime, bounded packets, ordering boundaries, timed progress, old
peers, fork rejection, malformed packets, partial failure and no replay.
`kernel_batch_gpu.c` additionally exercises actual GPU ordering and results,
error propagation, and a deliberately killed client in an isolated session.

The comparison must use the same new Guest and Worker binaries with the option
off and on. Release-vs-rebuilt results cannot isolate the effect of batching.
Measure completion after final synchronization, not just local enqueue time.
