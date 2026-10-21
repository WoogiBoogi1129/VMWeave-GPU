#ifndef VMWEAVE_PERF_H
#define VMWEAVE_PERF_H
#include <stdint.h>
#include <stddef.h>
/* Local policy/telemetry only: no wire or CUDA semantic changes. */
enum vmweave_perf_stage { VMWEAVE_PERF_SUBMIT, VMWEAVE_PERF_TAKE, VMWEAVE_PERF_RESPOND,
    VMWEAVE_PERF_RECEIVE, VMWEAVE_PERF_DISPATCH, VMWEAVE_PERF_EXCHANGE, VMWEAVE_PERF_STAGES };
struct vmweave_wait { uint64_t started; unsigned sleeps; };
int vmweave_perf_enabled(void);
int vmweave_copy_optimized(void);
uint64_t vmweave_perf_now(void);
void vmweave_perf_add(enum vmweave_perf_stage, uint64_t started, size_t bytes);
void vmweave_perf_dump(const char *role);
/* Bounded active spin, then short sleeps with idle backoff. EINTR is a wakeup. */
int vmweave_wait_pause(struct vmweave_wait *);
#endif
