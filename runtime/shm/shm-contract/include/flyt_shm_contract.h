/* Deprecated source compatibility; use vmweave_shm_contract.h. */
#ifndef VMWEAVE_LEGACY_FLYT_SHM_CONTRACT_H
#define VMWEAVE_LEGACY_FLYT_SHM_CONTRACT_H
#include "vmweave_shm_contract.h"
#ifndef FLYT_API_RUNTIME_DEVICE_SYNCHRONIZE
#define FLYT_API_RUNTIME_DEVICE_SYNCHRONIZE VMWEAVE_API_RUNTIME_DEVICE_SYNCHRONIZE
#endif
#ifndef FLYT_API_RUNTIME_FREE
#define FLYT_API_RUNTIME_FREE VMWEAVE_API_RUNTIME_FREE
#endif
#ifndef FLYT_API_RUNTIME_GET_DEVICE
#define FLYT_API_RUNTIME_GET_DEVICE VMWEAVE_API_RUNTIME_GET_DEVICE
#endif
#ifndef FLYT_API_RUNTIME_GET_DEVICE_COUNT
#define FLYT_API_RUNTIME_GET_DEVICE_COUNT VMWEAVE_API_RUNTIME_GET_DEVICE_COUNT
#endif
#ifndef FLYT_API_RUNTIME_MALLOC
#define FLYT_API_RUNTIME_MALLOC VMWEAVE_API_RUNTIME_MALLOC
#endif
#ifndef FLYT_API_RUNTIME_MEMCPY
#define FLYT_API_RUNTIME_MEMCPY VMWEAVE_API_RUNTIME_MEMCPY
#endif
#ifndef FLYT_API_RUNTIME_MEM_GET_INFO
#define FLYT_API_RUNTIME_MEM_GET_INFO VMWEAVE_API_RUNTIME_MEM_GET_INFO
#endif
#ifndef FLYT_API_RUNTIME_SET_DEVICE
#define FLYT_API_RUNTIME_SET_DEVICE VMWEAVE_API_RUNTIME_SET_DEVICE
#endif
#ifndef FLYT_D_API_ID
#define FLYT_D_API_ID VMWEAVE_D_API_ID
#endif
#ifndef FLYT_D_API_RESULT
#define FLYT_D_API_RESULT VMWEAVE_D_API_RESULT
#endif
#ifndef FLYT_D_CHANNEL_GENERATION
#define FLYT_D_CHANNEL_GENERATION VMWEAVE_D_CHANNEL_GENERATION
#endif
#ifndef FLYT_D_COMPLETION
#define FLYT_D_COMPLETION VMWEAVE_D_COMPLETION
#endif
#ifndef FLYT_D_FLAGS
#define FLYT_D_FLAGS VMWEAVE_D_FLAGS
#endif
#ifndef FLYT_D_KIND
#define FLYT_D_KIND VMWEAVE_D_KIND
#endif
#ifndef FLYT_D_MAGIC
#define FLYT_D_MAGIC VMWEAVE_D_MAGIC
#endif
#ifndef FLYT_D_MAJOR
#define FLYT_D_MAJOR VMWEAVE_D_MAJOR
#endif
#ifndef FLYT_D_MINOR
#define FLYT_D_MINOR VMWEAVE_D_MINOR
#endif
#ifndef FLYT_D_PAYLOAD_LENGTH
#define FLYT_D_PAYLOAD_LENGTH VMWEAVE_D_PAYLOAD_LENGTH
#endif
#ifndef FLYT_D_PAYLOAD_OFFSET
#define FLYT_D_PAYLOAD_OFFSET VMWEAVE_D_PAYLOAD_OFFSET
#endif
#ifndef FLYT_D_PAYLOAD_SCHEMA
#define FLYT_D_PAYLOAD_SCHEMA VMWEAVE_D_PAYLOAD_SCHEMA
#endif
#ifndef FLYT_D_REQUEST_ID
#define FLYT_D_REQUEST_ID VMWEAVE_D_REQUEST_ID
#endif
#ifndef FLYT_D_RESERVED
#define FLYT_D_RESERVED VMWEAVE_D_RESERVED
#endif
#ifndef FLYT_D_RESULT_DOMAIN
#define FLYT_D_RESULT_DOMAIN VMWEAVE_D_RESULT_DOMAIN
#endif
#ifndef FLYT_D_SESSION_ID
#define FLYT_D_SESSION_ID VMWEAVE_D_SESSION_ID
#endif
#ifndef FLYT_D_TRANSPORT_STATUS
#define FLYT_D_TRANSPORT_STATUS VMWEAVE_D_TRANSPORT_STATUS
#endif
#ifndef FLYT_RESULT_CUDA_DRIVER
#define FLYT_RESULT_CUDA_DRIVER VMWEAVE_RESULT_CUDA_DRIVER
#endif
#ifndef FLYT_RESULT_CUDA_RUNTIME
#define FLYT_RESULT_CUDA_RUNTIME VMWEAVE_RESULT_CUDA_RUNTIME
#endif
#ifndef FLYT_RESULT_LIBRARY
#define FLYT_RESULT_LIBRARY VMWEAVE_RESULT_LIBRARY
#endif
#ifndef FLYT_RESULT_NONE
#define FLYT_RESULT_NONE VMWEAVE_RESULT_NONE
#endif
#ifndef FLYT_SHM_ABI_MAJOR
#define FLYT_SHM_ABI_MAJOR VMWEAVE_SHM_ABI_MAJOR
#endif
#ifndef FLYT_SHM_ABI_MINOR
#define FLYT_SHM_ABI_MINOR VMWEAVE_SHM_ABI_MINOR
#endif
#ifndef FLYT_SHM_BAD_DESCRIPTOR
#define FLYT_SHM_BAD_DESCRIPTOR VMWEAVE_SHM_BAD_DESCRIPTOR
#endif
#ifndef FLYT_SHM_BAD_VERSION
#define FLYT_SHM_BAD_VERSION VMWEAVE_SHM_BAD_VERSION
#endif
#ifndef FLYT_SHM_CACHE_LINE_BYTES
#define FLYT_SHM_CACHE_LINE_BYTES VMWEAVE_SHM_CACHE_LINE_BYTES
#endif
#ifndef FLYT_SHM_CHANNEL_CLOSED
#define FLYT_SHM_CHANNEL_CLOSED VMWEAVE_SHM_CHANNEL_CLOSED
#endif
#ifndef FLYT_SHM_DESCRIPTOR_BYTES
#define FLYT_SHM_DESCRIPTOR_BYTES VMWEAVE_SHM_DESCRIPTOR_BYTES
#endif
#ifndef FLYT_SHM_EXECUTION_UNKNOWN
#define FLYT_SHM_EXECUTION_UNKNOWN VMWEAVE_SHM_EXECUTION_UNKNOWN
#endif
#ifndef FLYT_SHM_INTERNAL_ERROR
#define FLYT_SHM_INTERNAL_ERROR VMWEAVE_SHM_INTERNAL_ERROR
#endif
#ifndef FLYT_SHM_INVALID_HANDLE
#define FLYT_SHM_INVALID_HANDLE VMWEAVE_SHM_INVALID_HANDLE
#endif
#ifndef FLYT_SHM_MAX_RING_ENTRIES
#define FLYT_SHM_MAX_RING_ENTRIES VMWEAVE_SHM_MAX_RING_ENTRIES
#endif
#ifndef FLYT_SHM_MAX_SESSIONS
#define FLYT_SHM_MAX_SESSIONS VMWEAVE_SHM_MAX_SESSIONS
#endif
#ifndef FLYT_SHM_OK
#define FLYT_SHM_OK VMWEAVE_SHM_OK
#endif
#ifndef FLYT_SHM_QUEUE_FULL
#define FLYT_SHM_QUEUE_FULL VMWEAVE_SHM_QUEUE_FULL
#endif
#ifndef FLYT_SHM_STALE_IDENTITY
#define FLYT_SHM_STALE_IDENTITY VMWEAVE_SHM_STALE_IDENTITY
#endif
#ifndef FLYT_SHM_UNSUPPORTED_API
#define FLYT_SHM_UNSUPPORTED_API VMWEAVE_SHM_UNSUPPORTED_API
#endif
#ifndef flyt_cuda_dispatch
#define flyt_cuda_dispatch vmweave_cuda_dispatch
#endif
#ifndef flyt_cuda_session
#define flyt_cuda_session vmweave_cuda_session
#endif
#ifndef flyt_shm_api_id
#define flyt_shm_api_id vmweave_shm_api_id
#endif
#ifndef flyt_shm_channel
#define flyt_shm_channel vmweave_shm_channel
#endif
#ifndef flyt_shm_descriptor_offset
#define flyt_shm_descriptor_offset vmweave_shm_descriptor_offset
#endif
#ifndef flyt_shm_identity
#define flyt_shm_identity vmweave_shm_identity
#endif
#ifndef flyt_shm_receive
#define flyt_shm_receive vmweave_shm_receive
#endif
#ifndef flyt_shm_request
#define flyt_shm_request vmweave_shm_request
#endif
#ifndef flyt_shm_response
#define flyt_shm_response vmweave_shm_response
#endif
#ifndef flyt_shm_result_domain
#define flyt_shm_result_domain vmweave_shm_result_domain
#endif
#ifndef flyt_shm_status
#define flyt_shm_status vmweave_shm_status
#endif
#ifndef flyt_shm_submit
#define flyt_shm_submit vmweave_shm_submit
#endif
#endif
