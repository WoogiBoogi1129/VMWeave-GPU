#include "vmweave_wire.h"
#include "vmweave_perf.h"
#include <string.h>
#include <cuda_runtime_api.h>
int vmweave_cuda_dispatch(struct vmweave_cuda_session *s,const struct vmweave_shm_request *q,struct vmweave_shm_response *r){
    struct vmweave_cuda_call c={0};struct vmweave_cuda_result result={0};size_t need=0;int rc;
    if(!s||!q||!r)return VMWEAVE_SHM_BAD_DESCRIPTOR;
    r->output_bytes=0;r->transport_status=0;r->result_domain=0;r->api_result=0;
    if(q->payload_schema!=1){r->transport_status=VMWEAVE_SHM_UNSUPPORTED_API;return 0;}
    c.api_id=q->api_id;
    if(c.api_id==VMWEAVE_COPY_LIMITS){
        if(!s->exec||q->input_bytes||r->output_capacity<24||!r->output)goto invalid;
        int state=vmweave_cuda_exec_check(s->exec);
        if(state){r->transport_status=(uint32_t)state;return 0;}
        vmweave_put(r->output,1,4);vmweave_put(r->output+4,1,4);
        vmweave_put(r->output+8,VMWEAVE_COPY_CHUNK_BYTES,8);
        vmweave_put(r->output+16,VMWEAVE_COPY_CHUNK_BYTES,8);
        r->output_bytes=24;r->result_domain=VMWEAVE_RESULT_CUDA_RUNTIME;return 0;
    }
    if(c.api_id==VMWEAVE_API_RUNTIME_MEM_GET_INFO){
        if(!s->exec||q->input_bytes||r->output_capacity<16||!r->output)goto invalid;
        int state=vmweave_cuda_exec_check(s->exec);
        if(state){r->transport_status=(uint32_t)state;return 0;}
        size_t free_bytes=0,total_bytes=0;
        r->result_domain=VMWEAVE_RESULT_CUDA_RUNTIME;
        r->api_result=(uint32_t)cudaMemGetInfo(&free_bytes,&total_bytes);
        if(!r->api_result){
            if(!total_bytes||free_bytes>total_bytes){r->api_result=cudaErrorUnknown;return 0;}
            vmweave_put(r->output,free_bytes,8);vmweave_put(r->output+8,total_bytes,8);r->output_bytes=16;
        }
        return 0;
    }
    switch(c.api_id){
    case VMWEAVE_API_RUNTIME_GET_DEVICE_COUNT:case VMWEAVE_API_RUNTIME_GET_DEVICE:
        if(q->input_bytes)goto invalid;need=4;break;
    case VMWEAVE_API_RUNTIME_SET_DEVICE:
        if(q->input_bytes!=4)goto invalid;c.args.device=(int32_t)vmweave_get(q->input,4);break;
    case VMWEAVE_API_RUNTIME_MALLOC:
        if(q->input_bytes!=8)goto invalid;c.args.allocation_bytes=vmweave_get(q->input,8);need=8;break;
    case VMWEAVE_API_RUNTIME_FREE:
        if(q->input_bytes!=8)goto invalid;c.args.free_handle=vmweave_get(q->input,8);break;
    case VMWEAVE_API_RUNTIME_DEVICE_SYNCHRONIZE:if(q->input_bytes)goto invalid;break;
    case VMWEAVE_API_RUNTIME_MEMCPY:{
        if(q->input_bytes<48||vmweave_get(q->input+4,4))goto invalid;
        uint64_t n=vmweave_get(q->input+40,8);uint32_t k=(uint32_t)vmweave_get(q->input,4);
        if(n>SIZE_MAX||(k!=3&&n>VMWEAVE_COPY_CHUNK_BYTES)||k<1||k>3)goto invalid;
        if(q->input_bytes!=48+(k==VMWEAVE_COPY_HTOD?(size_t)n:0))goto invalid;
        c.args.copy.direction=k;c.args.copy.dst.handle=vmweave_get(q->input+8,8);c.args.copy.dst.offset=vmweave_get(q->input+16,8);
        c.args.copy.src.handle=vmweave_get(q->input+24,8);c.args.copy.src.offset=vmweave_get(q->input+32,8);c.args.copy.bytes=n;
        if(k==VMWEAVE_COPY_HTOD){c.args.copy.host_input=q->input+48;c.args.copy.host_input_bytes=(size_t)n;}
        if(k==VMWEAVE_COPY_DTOH)need=(size_t)n;break;}
    default:r->transport_status=VMWEAVE_SHM_UNSUPPORTED_API;return 0;
    }
    /* Reserve caller's response space BEFORE any CUDA side effect. */
    if(need>r->output_capacity||(need&&!r->output))goto invalid;
    if(c.api_id==VMWEAVE_API_RUNTIME_MEMCPY && vmweave_copy_optimized()){
        if(c.args.copy.direction==VMWEAVE_COPY_HTOD)c.args.copy.borrow_input=1;
        if(c.args.copy.direction==VMWEAVE_COPY_DTOH){c.args.copy.host_output=r->output;c.args.copy.host_output_bytes=r->output_capacity;}
    }
    rc=vmweave_cuda_exec_call(s->exec,&c,&result);
    r->transport_status=(uint32_t)rc;r->result_domain=result.result_domain;r->api_result=result.api_result;
    if(!rc&&!result.api_result){
        if(c.api_id==VMWEAVE_API_RUNTIME_MALLOC)vmweave_put(r->output,result.handle,8);
        else if(c.api_id==VMWEAVE_API_RUNTIME_GET_DEVICE_COUNT||c.api_id==VMWEAVE_API_RUNTIME_GET_DEVICE)vmweave_put(r->output,(uint32_t)result.device,4);
        else if(result.data_bytes && result.data!=r->output){memcpy(r->output,result.data,result.data_bytes);}
        r->output_bytes=need;
    }
    vmweave_cuda_result_release(&result);return 0;
invalid:r->transport_status=VMWEAVE_SHM_BAD_DESCRIPTOR;return 0;
}

/* Legacy binary ABI: same implementation and address, no second state. */
extern __typeof__(vmweave_cuda_dispatch) flyt_cuda_dispatch __attribute__((alias("vmweave_cuda_dispatch")));
