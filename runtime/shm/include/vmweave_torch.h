#ifndef VMWEAVE_TORCH_H
#define VMWEAVE_TORCH_H
#include "vmweave_wire.h"
/* Additive schema-1 extension. CUDA 12.8 / little-endian 64-bit guests only. */
enum {
    VMWEAVE_DEVICE_PROPERTIES=0x2100, VMWEAVE_DEVICE_ATTRIBUTE, VMWEAVE_CUDA_VERSION,
    VMWEAVE_ALLOCATION_ADDRESS, VMWEAVE_MEMSET, VMWEAVE_PRIORITY_RANGE,
    VMWEAVE_STREAM_PRIORITY_CREATE, VMWEAVE_PRIMARY_CONTEXT_STATE,
    VMWEAVE_MODULE_BEGIN=0x2040, VMWEAVE_MODULE_CHUNK, VMWEAVE_MODULE_COMMIT,
    VMWEAVE_FUNCTION_LAYOUT, VMWEAVE_KERNEL_PACKED,
    VMWEAVE_MEMSET_NATIVE=0x2108
};
#define VMWEAVE_MAX_MODULE_BYTES (512u*1024u*1024u)
#define VMWEAVE_MAX_PARAMETER_BYTES 32764u
#define VMWEAVE_PROPERTY_CAPACITY 2048u
int vmweave_torch_dispatch(struct vmweave_cuda_session *,const struct vmweave_shm_request *,struct vmweave_shm_response *);
int vmweave_guest_mirror_enabled(void);
#endif
