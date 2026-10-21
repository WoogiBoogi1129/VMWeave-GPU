#ifndef VMWEAVE_SHM_CONTRACT_H
#define VMWEAVE_SHM_CONTRACT_H

/* Stage 10-01 declarations only. Not wired into the runtime; NOT_RUN.
 * Wire records are byte arrays with explicit little-endian encoding. Never
 * memcpy a native C struct, pointer, size_t, enum or atomic object onto the wire.
 */
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define VMWEAVE_SHM_ABI_MAJOR 1u
#define VMWEAVE_SHM_ABI_MINOR 0u
#define VMWEAVE_SHM_DESCRIPTOR_BYTES 128u
#define VMWEAVE_SHM_CACHE_LINE_BYTES 64u
#define VMWEAVE_SHM_MAX_SESSIONS 32u
#define VMWEAVE_SHM_MAX_RING_ENTRIES 65536u
#define VMWEAVE_SHM_INVALID_HANDLE UINT64_C(0)

/* Request and response use the same fixed record. All reserved bytes are zero.
 * Flags are zero in ABI 1.0. API payload schemas define IN/OUT and async behavior.
 */
enum vmweave_shm_descriptor_offset {
    VMWEAVE_D_MAGIC = 0,            /* 8 bytes: ASCII FLYTSHM1 */
    VMWEAVE_D_MAJOR = 8,            /* u16 */
    VMWEAVE_D_MINOR = 10,           /* u16 */
    VMWEAVE_D_KIND = 12,            /* u16: request=1, response=2 */
    VMWEAVE_D_FLAGS = 14,           /* u16 */
    VMWEAVE_D_CHANNEL_GENERATION = 16, /* 16 random bytes, not a counter */
    VMWEAVE_D_SESSION_ID = 32,      /* 16 random bytes */
    VMWEAVE_D_REQUEST_ID = 48,      /* u64, starts at 1; never reused in session */
    VMWEAVE_D_API_ID = 56,          /* u32 */
    VMWEAVE_D_PAYLOAD_SCHEMA = 60,  /* u32 */
    VMWEAVE_D_PAYLOAD_OFFSET = 64,  /* u64 from session payload arena base */
    VMWEAVE_D_PAYLOAD_LENGTH = 72,  /* u64 */
    VMWEAVE_D_TRANSPORT_STATUS = 80,/* u32, zero in request */
    VMWEAVE_D_RESULT_DOMAIN = 84,   /* u32: none/runtime/driver/library */
    VMWEAVE_D_API_RESULT = 88,      /* u32 raw API return bits; NOT an errno */
    VMWEAVE_D_COMPLETION = 92,      /* u32: 0=request, 1=API return */
    VMWEAVE_D_RESERVED = 96        /* 32 zero bytes */
};

enum vmweave_shm_status {
    VMWEAVE_SHM_OK = 0,
    VMWEAVE_SHM_UNSUPPORTED_API = 1,
    VMWEAVE_SHM_BAD_VERSION = 2,
    VMWEAVE_SHM_BAD_DESCRIPTOR = 3,
    VMWEAVE_SHM_STALE_IDENTITY = 4,
    VMWEAVE_SHM_QUEUE_FULL = 5,     /* Local submit failure: request NOT published. */
    VMWEAVE_SHM_CHANNEL_CLOSED = 6,
    VMWEAVE_SHM_EXECUTION_UNKNOWN = 7, /* No automatic retry. */
    VMWEAVE_SHM_INTERNAL_ERROR = 8
};
enum vmweave_shm_result_domain {
    VMWEAVE_RESULT_NONE = 0, VMWEAVE_RESULT_CUDA_RUNTIME = 1,
    VMWEAVE_RESULT_CUDA_DRIVER = 2, VMWEAVE_RESULT_LIBRARY = 3
};

/* API ID allocation is provisional but IDs are never repurposed within major 1.
 * Listing an API here does not implement it. Stage 10-06 defines payload schemas.
 */
enum vmweave_shm_api_id {
    VMWEAVE_API_RUNTIME_GET_DEVICE_COUNT = 0x1001,
    VMWEAVE_API_RUNTIME_GET_DEVICE = 0x1002,
    VMWEAVE_API_RUNTIME_SET_DEVICE = 0x1003,
    VMWEAVE_API_RUNTIME_MALLOC = 0x1010,
    VMWEAVE_API_RUNTIME_FREE = 0x1011,
    VMWEAVE_API_RUNTIME_MEMCPY = 0x1012,
    VMWEAVE_API_RUNTIME_MEM_GET_INFO = 0x1013,
    VMWEAVE_API_RUNTIME_DEVICE_SYNCHRONIZE = 0x1020
};

/* Host-local decoded objects, never mapped as wire structs. */
struct vmweave_shm_identity {
    uint8_t channel_generation[16];
    uint8_t session_id[16];
};
struct vmweave_shm_request {
    struct vmweave_shm_identity identity;
    uint64_t request_id;
    uint32_t api_id;
    uint32_t payload_schema;
    const uint8_t *input;
    size_t input_bytes;
};
struct vmweave_shm_response {
    uint32_t transport_status;
    uint32_t result_domain;
    uint32_t api_result;
    uint8_t *output;
    size_t output_capacity;
    size_t output_bytes;
};
struct vmweave_cuda_session;
struct vmweave_shm_channel;

/* Implemented in later branches. No RPC fallback is permitted. The dispatcher
 * snapshots and validates input before CUDA execution; output belongs to caller.
 */
int vmweave_cuda_dispatch(struct vmweave_cuda_session *session,
                      const struct vmweave_shm_request *request,
                      struct vmweave_shm_response *response);
int vmweave_shm_submit(struct vmweave_shm_channel *channel,
                    const struct vmweave_shm_request *request);
int vmweave_shm_receive(struct vmweave_shm_channel *channel, uint64_t request_id,
                     struct vmweave_shm_response *response);

#ifdef __cplusplus
}
#endif
#endif
