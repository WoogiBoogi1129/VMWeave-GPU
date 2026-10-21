/* Deprecated source compatibility; use vmweave_torch.h. */
#ifndef VMWEAVE_LEGACY_FLYT_TORCH_H
#define VMWEAVE_LEGACY_FLYT_TORCH_H
#include "flyt_wire.h"
#include "vmweave_torch.h"
#ifndef FLYT_ALLOCATION_ADDRESS
#define FLYT_ALLOCATION_ADDRESS VMWEAVE_ALLOCATION_ADDRESS
#endif
#ifndef FLYT_CUDA_VERSION
#define FLYT_CUDA_VERSION VMWEAVE_CUDA_VERSION
#endif
#ifndef FLYT_DEVICE_ATTRIBUTE
#define FLYT_DEVICE_ATTRIBUTE VMWEAVE_DEVICE_ATTRIBUTE
#endif
#ifndef FLYT_DEVICE_PROPERTIES
#define FLYT_DEVICE_PROPERTIES VMWEAVE_DEVICE_PROPERTIES
#endif
#ifndef FLYT_FUNCTION_LAYOUT
#define FLYT_FUNCTION_LAYOUT VMWEAVE_FUNCTION_LAYOUT
#endif
#ifndef FLYT_KERNEL_PACKED
#define FLYT_KERNEL_PACKED VMWEAVE_KERNEL_PACKED
#endif
#ifndef FLYT_MAX_MODULE_BYTES
#define FLYT_MAX_MODULE_BYTES VMWEAVE_MAX_MODULE_BYTES
#endif
#ifndef FLYT_MAX_PARAMETER_BYTES
#define FLYT_MAX_PARAMETER_BYTES VMWEAVE_MAX_PARAMETER_BYTES
#endif
#ifndef FLYT_MEMSET
#define FLYT_MEMSET VMWEAVE_MEMSET
#endif
#ifndef FLYT_MODULE_BEGIN
#define FLYT_MODULE_BEGIN VMWEAVE_MODULE_BEGIN
#endif
#ifndef FLYT_MODULE_CHUNK
#define FLYT_MODULE_CHUNK VMWEAVE_MODULE_CHUNK
#endif
#ifndef FLYT_MODULE_COMMIT
#define FLYT_MODULE_COMMIT VMWEAVE_MODULE_COMMIT
#endif
#ifndef FLYT_PRIMARY_CONTEXT_STATE
#define FLYT_PRIMARY_CONTEXT_STATE VMWEAVE_PRIMARY_CONTEXT_STATE
#endif
#ifndef FLYT_PRIORITY_RANGE
#define FLYT_PRIORITY_RANGE VMWEAVE_PRIORITY_RANGE
#endif
#ifndef FLYT_PROPERTY_CAPACITY
#define FLYT_PROPERTY_CAPACITY VMWEAVE_PROPERTY_CAPACITY
#endif
#ifndef FLYT_STREAM_PRIORITY_CREATE
#define FLYT_STREAM_PRIORITY_CREATE VMWEAVE_STREAM_PRIORITY_CREATE
#endif
#ifndef flyt_cuda_session
#define flyt_cuda_session vmweave_cuda_session
#endif
#ifndef flyt_guest_mirror_enabled
#define flyt_guest_mirror_enabled vmweave_guest_mirror_enabled
#endif
#ifndef flyt_shm_request
#define flyt_shm_request vmweave_shm_request
#endif
#ifndef flyt_shm_response
#define flyt_shm_response vmweave_shm_response
#endif
#ifndef flyt_torch_dispatch
#define flyt_torch_dispatch vmweave_torch_dispatch
#endif
#ifndef flyt_wire
#define flyt_wire vmweave_wire
#endif
#endif
