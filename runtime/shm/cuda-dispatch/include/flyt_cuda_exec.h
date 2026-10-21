/* Deprecated source compatibility; use vmweave_cuda_exec.h. */
#ifndef VMWEAVE_LEGACY_FLYT_CUDA_EXEC_H
#define VMWEAVE_LEGACY_FLYT_CUDA_EXEC_H
#include "flyt_shm_contract.h"
#include "vmweave_cuda_exec.h"
#ifndef FLYT_COPY_DTOD
#define FLYT_COPY_DTOD VMWEAVE_COPY_DTOD
#endif
#ifndef FLYT_COPY_DTOH
#define FLYT_COPY_DTOH VMWEAVE_COPY_DTOH
#endif
#ifndef FLYT_COPY_HTOD
#define FLYT_COPY_HTOD VMWEAVE_COPY_HTOD
#endif
#ifndef FLYT_EXEC_MAX_ALLOCATIONS
#define FLYT_EXEC_MAX_ALLOCATIONS VMWEAVE_EXEC_MAX_ALLOCATIONS
#endif
#ifndef FLYT_EXEC_MAX_COPY_BYTES
#define FLYT_EXEC_MAX_COPY_BYTES VMWEAVE_EXEC_MAX_COPY_BYTES
#endif
#ifndef flyt_copy_direction
#define flyt_copy_direction vmweave_copy_direction
#endif
#ifndef flyt_cuda_backend
#define flyt_cuda_backend vmweave_cuda_backend
#endif
#ifndef flyt_cuda_call
#define flyt_cuda_call vmweave_cuda_call
#endif
#ifndef flyt_cuda_exec
#define flyt_cuda_exec vmweave_cuda_exec
#endif
#ifndef flyt_cuda_exec_call
#define flyt_cuda_exec_call vmweave_cuda_exec_call
#endif
#ifndef flyt_cuda_exec_check
#define flyt_cuda_exec_check vmweave_cuda_exec_check
#endif
#ifndef flyt_cuda_exec_create
#define flyt_cuda_exec_create vmweave_cuda_exec_create
#endif
#ifndef flyt_cuda_exec_destroy
#define flyt_cuda_exec_destroy vmweave_cuda_exec_destroy
#endif
#ifndef flyt_cuda_exec_resolve
#define flyt_cuda_exec_resolve vmweave_cuda_exec_resolve
#endif
#ifndef flyt_cuda_result
#define flyt_cuda_result vmweave_cuda_result
#endif
#ifndef flyt_cuda_result_release
#define flyt_cuda_result_release vmweave_cuda_result_release
#endif
#ifndef flyt_cuda_runtime
#define flyt_cuda_runtime vmweave_cuda_runtime
#endif
#ifndef flyt_cuda_runtime_backend
#define flyt_cuda_runtime_backend vmweave_cuda_runtime_backend
#endif
#ifndef flyt_cuda_runtime_close
#define flyt_cuda_runtime_close vmweave_cuda_runtime_close
#endif
#ifndef flyt_cuda_runtime_open
#define flyt_cuda_runtime_open vmweave_cuda_runtime_open
#endif
#ifndef flyt_device_ref
#define flyt_device_ref vmweave_device_ref
#endif
#ifndef flyt_shm_contract
#define flyt_shm_contract vmweave_shm_contract
#endif
#endif
