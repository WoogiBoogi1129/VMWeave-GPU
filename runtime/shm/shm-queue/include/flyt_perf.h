#ifndef FLYT_PERF_H
#define FLYT_PERF_H
#include <stdint.h>
#include <stddef.h>
/* Local policy/telemetry only: no wire or CUDA semantic changes. */
enum flyt_perf_stage { FLYT_PERF_SUBMIT, FLYT_PERF_TAKE, FLYT_PERF_RESPOND,
    FLYT_PERF_RECEIVE, FLYT_PERF_DISPATCH, FLYT_PERF_EXCHANGE, FLYT_PERF_STAGES };
struct flyt_wait { uint64_t started; unsigned sleeps; };
int flyt_perf_enabled(void);
int flyt_copy_optimized(void);
uint64_t flyt_perf_now(void);
void flyt_perf_add(enum flyt_perf_stage, uint64_t started, size_t bytes);
void flyt_perf_dump(const char *role);
/* Bounded active spin, then short sleeps with idle backoff. EINTR is a wakeup. */
int flyt_wait_pause(struct flyt_wait *);
#endif
