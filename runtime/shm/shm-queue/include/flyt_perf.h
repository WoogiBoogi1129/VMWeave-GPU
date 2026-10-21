/* Deprecated source compatibility; use vmweave_perf.h. */
#ifndef VMWEAVE_LEGACY_FLYT_PERF_H
#define VMWEAVE_LEGACY_FLYT_PERF_H
#include "vmweave_perf.h"
#ifndef FLYT_PERF_DISPATCH
#define FLYT_PERF_DISPATCH VMWEAVE_PERF_DISPATCH
#endif
#ifndef FLYT_PERF_EXCHANGE
#define FLYT_PERF_EXCHANGE VMWEAVE_PERF_EXCHANGE
#endif
#ifndef FLYT_PERF_RECEIVE
#define FLYT_PERF_RECEIVE VMWEAVE_PERF_RECEIVE
#endif
#ifndef FLYT_PERF_RESPOND
#define FLYT_PERF_RESPOND VMWEAVE_PERF_RESPOND
#endif
#ifndef FLYT_PERF_STAGES
#define FLYT_PERF_STAGES VMWEAVE_PERF_STAGES
#endif
#ifndef FLYT_PERF_SUBMIT
#define FLYT_PERF_SUBMIT VMWEAVE_PERF_SUBMIT
#endif
#ifndef FLYT_PERF_TAKE
#define FLYT_PERF_TAKE VMWEAVE_PERF_TAKE
#endif
#ifndef flyt_copy_optimized
#define flyt_copy_optimized vmweave_copy_optimized
#endif
#ifndef flyt_perf_add
#define flyt_perf_add vmweave_perf_add
#endif
#ifndef flyt_perf_dump
#define flyt_perf_dump vmweave_perf_dump
#endif
#ifndef flyt_perf_enabled
#define flyt_perf_enabled vmweave_perf_enabled
#endif
#ifndef flyt_perf_now
#define flyt_perf_now vmweave_perf_now
#endif
#ifndef flyt_perf_stage
#define flyt_perf_stage vmweave_perf_stage
#endif
#ifndef flyt_wait
#define flyt_wait vmweave_wait
#endif
#ifndef flyt_wait_pause
#define flyt_wait_pause vmweave_wait_pause
#endif
#endif
