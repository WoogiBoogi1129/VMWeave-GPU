#include "vmweave_torch.h"
#include <cuda_runtime_api.h>
#include <cuda.h>
#include <string.h>
int vmweave_async_stream(uint64_t,void **);

int vmweave_torch_dispatch(struct vmweave_cuda_session *s,const struct vmweave_shm_request *q,struct vmweave_shm_response *r) {
    const uint8_t *p=q->input;size_t n=q->input_bytes,at=0;
    r->output_bytes=0;r->api_result=0;r->transport_status=VMWEAVE_SHM_OK;r->result_domain=VMWEAVE_RESULT_CUDA_RUNTIME;
    if(q->payload_schema!=1)goto unsupported;
    switch(q->api_id) {
    case VMWEAVE_PRIMARY_CONTEXT_STATE: {
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;
        if(n||r->output_capacity<8||!r->output)goto invalid;unsigned flags=0;int active=0;
        r->api_result=cuDevicePrimaryCtxGetState(0,&flags,&active);
        if(!r->api_result){vmweave_put(r->output,flags,4);vmweave_put(r->output+4,(uint32_t)active,4);r->output_bytes=8;}break;
    }
    case VMWEAVE_DEVICE_PROPERTIES: {
        if(n!=4||vmweave_get(p,4)!=12080||r->output_capacity<VMWEAVE_PROPERTY_CAPACITY||!r->output)goto invalid;
        struct cudaDeviceProp prop={0};
        r->api_result=cudaGetDeviceProperties(&prop,0);if(r->api_result)break;
        /* These native host capabilities cannot cross the VM channel. */
        prop.managedMemory=0;prop.concurrentManagedAccess=0;prop.pageableMemoryAccess=0;
        prop.canMapHostMemory=0;prop.canUseHostPointerForRegisteredMem=0;
        prop.pageableMemoryAccessUsesHostPageTables=0;prop.directManagedMemAccessFromHost=0;
        prop.hostRegisterSupported=0;prop.memoryPoolsSupported=0;prop.ipcEventSupported=0;
#define VMWEAVE_PROP_NUMBER(field,width) vmweave_put(r->output+at,prop.field,width);at+=width;
#define VMWEAVE_PROP_BYTES(field,bytes) memcpy(r->output+at,prop.field,bytes);at+=bytes;
#include "vmweave_properties.inc"
#undef VMWEAVE_PROP_NUMBER
#undef VMWEAVE_PROP_BYTES
        r->output_bytes=at;break;
    }
    case VMWEAVE_DEVICE_ATTRIBUTE: {
        if(n!=4||r->output_capacity<4||!r->output)goto invalid;int value=0;
        enum cudaDeviceAttr attr=(enum cudaDeviceAttr)vmweave_get(p,4);
        r->api_result=cudaDeviceGetAttribute(&value,attr,0);
        if(attr==cudaDevAttrManagedMemory||attr==cudaDevAttrConcurrentManagedAccess||
           attr==cudaDevAttrPageableMemoryAccess||attr==cudaDevAttrCanMapHostMemory||
           attr==cudaDevAttrCanUseHostPointerForRegisteredMem||attr==cudaDevAttrHostRegisterSupported||
           attr==cudaDevAttrMemoryPoolsSupported||attr==cudaDevAttrIpcEventSupport) value=0;
        if(!r->api_result){vmweave_put(r->output,(uint32_t)value,4);r->output_bytes=4;}break;
    }
    case VMWEAVE_CUDA_VERSION: {
        if(n!=4||vmweave_get(p,4)>1||r->output_capacity<4||!r->output)goto invalid;int value=0;
        r->api_result=vmweave_get(p,4)?cudaDriverGetVersion(&value):cudaRuntimeGetVersion(&value);
        if(!r->api_result){vmweave_put(r->output,(uint32_t)value,4);r->output_bytes=4;}break;
    }
    case VMWEAVE_ALLOCATION_ADDRESS: {
        if(n!=8||r->output_capacity<8||!r->output)goto invalid;
        void *address=NULL;struct vmweave_device_ref ref={vmweave_get(p,8),0};
        if(!vmweave_cuda_exec_resolve(s->exec,ref,0,&address))goto invalid;
        /* Explicit device-VA token for opt-in mirror mode, never a CPU address
         * dereferenced by the receiver. Legacy handle-only APIs are unchanged. */
        vmweave_put(r->output,(uintptr_t)address,8);r->output_bytes=8;break;
    }
    case VMWEAVE_MEMSET_NATIVE: {
        if(!p||n!=40||vmweave_get(p+24,8)||vmweave_get(p+36,4))goto invalid;
        uint64_t bytes=vmweave_get(p+16,8);void *address=NULL;
        struct vmweave_device_ref ref={vmweave_get(p,8),vmweave_get(p+8,8)};
        if(bytes>SIZE_MAX||!vmweave_cuda_exec_resolve(s->exec,ref,(size_t)bytes,&address))goto invalid;
        r->api_result=cudaMemset(address,(int)(int32_t)vmweave_get(p+32,4),(size_t)bytes);
        break;
    }
    case VMWEAVE_MEMSET: {
        if(n!=40||vmweave_get(p+36,4))goto invalid;
        struct vmweave_device_ref ref={vmweave_get(p,8),vmweave_get(p+8,8)};
        size_t bytes=(size_t)vmweave_get(p+16,8);void *address=NULL,*stream=NULL;
        if(!vmweave_cuda_exec_resolve(s->exec,ref,bytes,&address)||!vmweave_async_stream(vmweave_get(p+24,8),&stream))goto invalid;
        r->api_result=cudaMemsetAsync(address,(int)vmweave_get(p+32,4),bytes,(cudaStream_t)stream);break;
    }
    case VMWEAVE_PRIORITY_RANGE: {
        if(n||r->output_capacity<8||!r->output)goto invalid;int least=0,greatest=0;
        r->api_result=cudaDeviceGetStreamPriorityRange(&least,&greatest);
        if(!r->api_result){vmweave_put(r->output,(uint32_t)least,4);vmweave_put(r->output+4,(uint32_t)greatest,4);r->output_bytes=8;}break;
    }
    default:goto unsupported;
    }
    return 0;
invalid:r->transport_status=VMWEAVE_SHM_BAD_DESCRIPTOR;goto error;
unsupported:r->transport_status=VMWEAVE_SHM_UNSUPPORTED_API;
error:r->result_domain=0;r->api_result=0;r->output_bytes=0;return 0;
}

/* Legacy binary ABI: same implementation and address, no second state. */
extern __typeof__(vmweave_torch_dispatch) flyt_torch_dispatch __attribute__((alias("vmweave_torch_dispatch")));
