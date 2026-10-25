#include "vmweave_wire.h"
#include <cuda_runtime_api.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

int vmweave_cuda_dispatch(struct vmweave_cuda_session *,const struct vmweave_shm_request *,struct vmweave_shm_response *);
static int calls,state;static size_t free_value=123,total_value=456;static cudaError_t error_value=cudaSuccess;
int vmweave_cuda_exec_check(struct vmweave_cuda_exec *s){(void)s;return state;}
cudaError_t cudaMemGetInfo(size_t *free_bytes,size_t *total_bytes){calls++;*free_bytes=free_value;*total_bytes=total_value;return error_value;}
int vmweave_cuda_exec_call(struct vmweave_cuda_exec *e,const struct vmweave_cuda_call *c,struct vmweave_cuda_result *r){(void)e;(void)c;(void)r;abort();}
void vmweave_cuda_result_release(struct vmweave_cuda_result *r){(void)r;abort();}
int main(void){
    struct vmweave_cuda_session session={.exec=(struct vmweave_cuda_exec *)1};
    struct vmweave_shm_request q={.api_id=VMWEAVE_API_RUNTIME_MEM_GET_INFO,.payload_schema=1};
    uint8_t output[24];struct vmweave_shm_response r={.output=output,.output_capacity=16};
    assert(!vmweave_cuda_dispatch(&session,&q,&r));assert(calls==1&&r.output_bytes==16&&!r.api_result);
    assert(vmweave_get(output,8)==123&&vmweave_get(output+8,8)==456);
    r.output_capacity=15;assert(!vmweave_cuda_dispatch(&session,&q,&r));assert(calls==1&&r.transport_status==VMWEAVE_SHM_BAD_DESCRIPTOR);
    r.output_capacity=16;q.input_bytes=1;assert(!vmweave_cuda_dispatch(&session,&q,&r));assert(calls==1&&r.transport_status==VMWEAVE_SHM_BAD_DESCRIPTOR);
    q.input_bytes=0;error_value=cudaErrorMemoryAllocation;assert(!vmweave_cuda_dispatch(&session,&q,&r));assert(r.api_result==cudaErrorMemoryAllocation&&r.output_bytes==0);
    error_value=cudaSuccess;free_value=457;assert(!vmweave_cuda_dispatch(&session,&q,&r));assert(r.api_result==cudaErrorUnknown&&r.output_bytes==0);
    int previous=calls;state=VMWEAVE_SHM_CHANNEL_CLOSED;
    assert(!vmweave_cuda_dispatch(&session,&q,&r));assert(calls==previous&&r.transport_status==VMWEAVE_SHM_CHANNEL_CLOSED);
    state=VMWEAVE_SHM_BAD_DESCRIPTOR;
    assert(!vmweave_cuda_dispatch(&session,&q,&r));assert(calls==previous&&r.transport_status==VMWEAVE_SHM_BAD_DESCRIPTOR);
    state=0;q.api_id=VMWEAVE_COPY_LIMITS;r.output_capacity=24;
    assert(!vmweave_cuda_dispatch(&session,&q,&r)&&!r.transport_status&&r.output_bytes==24);
    assert(vmweave_get(output,4)==1&&vmweave_get(output+4,4)==1&&vmweave_get(output+8,8)==VMWEAVE_COPY_CHUNK_BYTES&&vmweave_get(output+16,8)==VMWEAVE_COPY_CHUNK_BYTES);
    r.output_capacity=23;assert(!vmweave_cuda_dispatch(&session,&q,&r)&&r.transport_status==VMWEAVE_SHM_BAD_DESCRIPTOR);
    r.output_capacity=24;state=VMWEAVE_SHM_CHANNEL_CLOSED;
    assert(!vmweave_cuda_dispatch(&session,&q,&r)&&r.transport_status==VMWEAVE_SHM_CHANNEL_CLOSED);
    puts("PASS: memory-info encoding, bounds, CUDA errors, inconsistent observations and closed/wrong-thread guards");
    return 0;
}
