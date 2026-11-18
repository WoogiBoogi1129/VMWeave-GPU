#include "../../runtime/shm/src/async.c"
#include <assert.h>
#include <stdio.h>
static unsigned launches,fail_at;
CUresult cuLaunchKernel(CUfunction f,unsigned gx,unsigned gy,unsigned gz,unsigned bx,unsigned by,unsigned bz,
                       unsigned shared,CUstream st,void **params,void **extra){
    (void)gy;(void)gz;(void)by;(void)bz;(void)shared;
    assert(f==(CUfunction)(uintptr_t)123&&gx==1&&bx==1&&!st&&!extra);
    assert(*(unsigned*)params[0]==launches);launches++;
    return fail_at&&launches==fail_at?CUDA_ERROR_LAUNCH_FAILED:CUDA_SUCCESS;
}
int vmweave_cuda_exec_resolve(struct vmweave_cuda_exec *s,struct vmweave_device_ref r,size_t n,void **p){(void)s;(void)r;(void)n;(void)p;return 0;}
int main(void){
    struct vmweave_cuda_session s={0};uint8_t input[8+128*76]={0},output[16];
    struct vmweave_shm_request q={.api_id=VMWEAVE_KERNEL_BATCH_CAPS,.payload_schema=1};
    struct vmweave_shm_response r={.output=output,.output_capacity=16};
    assert(!vmweave_async_dispatch(&s,&q,&r)&&!r.transport_status&&r.output_bytes==16&&vmweave_get(output+4,4)==128);
    objects[0]=(struct object){.id=7,.kind=FUNCTION,.pointer=(void*)(uintptr_t)123};
    vmweave_put(input,1,4);vmweave_put(input+4,128,4);
    for(unsigned i=0;i<128;i++){
        uint8_t *p=input+8+i*76;vmweave_put(p,72,4);p+=4;
        vmweave_put(p,7,8);for(unsigned j=0;j<6;j++)vmweave_put(p+16+4*j,1,4);
        vmweave_put(p+44,1,4);vmweave_put(p+52,4,4);vmweave_put(p+56,i,4);
    }
    q.api_id=VMWEAVE_KERNEL_BATCH;q.input=input;q.input_bytes=sizeof(input);
    /* Invalid final record / trailing bytes / counts never execute a prefix. */
    vmweave_put(input+8+127*76+4,999,8);
    assert(!vmweave_async_dispatch(&s,&q,&r)&&r.transport_status&&launches==0);
    vmweave_put(input+8+127*76+4,7,8);
    q.input_bytes--;assert(!vmweave_async_dispatch(&s,&q,&r)&&r.transport_status&&launches==0);q.input_bytes++;
    vmweave_put(input+4,129,4);assert(!vmweave_async_dispatch(&s,&q,&r)&&r.transport_status&&launches==0);vmweave_put(input+4,128,4);
    vmweave_put(input+8+127*76+12,1,8);assert(!vmweave_async_dispatch(&s,&q,&r)&&r.transport_status&&launches==0);vmweave_put(input+8+127*76+12,0,8);
    assert(!vmweave_async_dispatch(&s,&q,&r)&&!r.transport_status&&!r.api_result&&launches==128);
    launches=0;fail_at=3;assert(!vmweave_async_dispatch(&s,&q,&r)&&!r.transport_status&&r.api_result==CUDA_ERROR_LAUNCH_FAILED&&launches==3);
    puts("PASS: capability, bounded wire, whole-packet validation before side effects, order and stop on first CUDA error");return 0;
}
