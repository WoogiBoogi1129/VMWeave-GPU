/* Deprecated source compatibility; use vmweave_async.h. */
#ifndef VMWEAVE_LEGACY_FLYT_ASYNC_H
#define VMWEAVE_LEGACY_FLYT_ASYNC_H
#include "flyt_wire.h"
#include "vmweave_async.h"
#ifndef FLYT_ASYNC_COPY
#define FLYT_ASYNC_COPY VMWEAVE_ASYNC_COPY
#endif
#ifndef FLYT_EVENT_CREATE
#define FLYT_EVENT_CREATE VMWEAVE_EVENT_CREATE
#endif
#ifndef FLYT_EVENT_DESTROY
#define FLYT_EVENT_DESTROY VMWEAVE_EVENT_DESTROY
#endif
#ifndef FLYT_EVENT_QUERY
#define FLYT_EVENT_QUERY VMWEAVE_EVENT_QUERY
#endif
#ifndef FLYT_EVENT_RECORD
#define FLYT_EVENT_RECORD VMWEAVE_EVENT_RECORD
#endif
#ifndef FLYT_EVENT_SYNC
#define FLYT_EVENT_SYNC VMWEAVE_EVENT_SYNC
#endif
#ifndef FLYT_FUNCTION_GET
#define FLYT_FUNCTION_GET VMWEAVE_FUNCTION_GET
#endif
#ifndef FLYT_KERNEL_LAUNCH
#define FLYT_KERNEL_LAUNCH VMWEAVE_KERNEL_LAUNCH
#endif
#ifndef FLYT_MODULE_LOAD
#define FLYT_MODULE_LOAD VMWEAVE_MODULE_LOAD
#endif
#ifndef FLYT_MODULE_UNLOAD
#define FLYT_MODULE_UNLOAD VMWEAVE_MODULE_UNLOAD
#endif
#ifndef FLYT_STREAM_CREATE
#define FLYT_STREAM_CREATE VMWEAVE_STREAM_CREATE
#endif
#ifndef FLYT_STREAM_DESTROY
#define FLYT_STREAM_DESTROY VMWEAVE_STREAM_DESTROY
#endif
#ifndef FLYT_STREAM_QUERY
#define FLYT_STREAM_QUERY VMWEAVE_STREAM_QUERY
#endif
#ifndef FLYT_STREAM_SYNC
#define FLYT_STREAM_SYNC VMWEAVE_STREAM_SYNC
#endif
#ifndef flyt_async_close
#define flyt_async_close vmweave_async_close
#endif
#ifndef flyt_async_dispatch
#define flyt_async_dispatch vmweave_async_dispatch
#endif
#ifndef flyt_async_reap
#define flyt_async_reap vmweave_async_reap
#endif
#ifndef flyt_cuda_session
#define flyt_cuda_session vmweave_cuda_session
#endif
#ifndef flyt_shm_request
#define flyt_shm_request vmweave_shm_request
#endif
#ifndef flyt_shm_response
#define flyt_shm_response vmweave_shm_response
#endif
#ifndef flyt_wire
#define flyt_wire vmweave_wire
#endif
#endif
