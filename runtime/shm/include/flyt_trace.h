/* Deprecated source compatibility; use vmweave_trace.h. */
#ifndef VMWEAVE_LEGACY_FLYT_TRACE_H
#define VMWEAVE_LEGACY_FLYT_TRACE_H
#include "flyt_wire.h"
#include "vmweave_trace.h"
#ifndef FLYT_API_RUNTIME_FREE
#define FLYT_API_RUNTIME_FREE VMWEAVE_API_RUNTIME_FREE
#endif
#ifndef FLYT_API_RUNTIME_MALLOC
#define FLYT_API_RUNTIME_MALLOC VMWEAVE_API_RUNTIME_MALLOC
#endif
#ifndef FLYT_API_RUNTIME_MEMCPY
#define FLYT_API_RUNTIME_MEMCPY VMWEAVE_API_RUNTIME_MEMCPY
#endif
#ifndef FLYT_TRACE
#define FLYT_TRACE VMWEAVE_TRACE
#endif
#ifndef FLYT_TRACE_REQUESTS
#define FLYT_TRACE_REQUESTS VMWEAVE_TRACE_REQUESTS
#endif
#ifndef flyt_get
#define flyt_get vmweave_get
#endif
#ifndef flyt_shm_request
#define flyt_shm_request vmweave_shm_request
#endif
#ifndef flyt_shm_response
#define flyt_shm_response vmweave_shm_response
#endif
#ifndef flyt_trace
#define flyt_trace vmweave_trace
#endif
#ifndef flyt_wire
#define flyt_wire vmweave_wire
#endif
#endif
