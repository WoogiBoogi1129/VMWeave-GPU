#ifdef OLD_WORKER
#include "../fixtures/pre_native_torch.c"
#else
#include "../../../runtime/shm/src/torch.c"
#endif
#include <assert.h>
#include <stdio.h>
static unsigned native_calls,async_calls;static cudaError_t injected;static unsigned char memory[256];
int vmweave_cuda_exec_resolve(struct vmweave_cuda_exec *s,struct vmweave_device_ref ref,size_t n,void **out){
    (void)s;if(ref.handle!=7||ref.offset>256||n>256-ref.offset)return 0;*out=memory+ref.offset;return 1;
}
int vmweave_async_stream(uint64_t id,void **out){if(id!=0&&id!=9)return 0;*out=(void*)(uintptr_t)id;return 1;}
cudaError_t cudaMemset(void *p,int v,size_t n){++native_calls;if(!injected)memset(p,v,n);return injected;}
cudaError_t cudaMemsetAsync(void *p,int v,size_t n,cudaStream_t st){(void)p;(void)v;(void)n;assert(st==(cudaStream_t)9);++async_calls;return cudaSuccess;}
CUresult cuDevicePrimaryCtxGetState(CUdevice d,unsigned *f,int *a){(void)d;(void)f;(void)a;return CUDA_SUCCESS;}
cudaError_t cudaGetDeviceProperties(struct cudaDeviceProp *p,int d){(void)p;(void)d;return cudaSuccess;}
cudaError_t cudaDeviceGetAttribute(int *p,enum cudaDeviceAttr a,int d){(void)p;(void)a;(void)d;return cudaSuccess;}
cudaError_t cudaDriverGetVersion(int *p){(void)p;return cudaSuccess;}
cudaError_t cudaRuntimeGetVersion(int *p){(void)p;return cudaSuccess;}
cudaError_t cudaDeviceGetStreamPriorityRange(int *a,int *b){(void)a;(void)b;return cudaSuccess;}
int main(void){
    _Static_assert(VMWEAVE_MEMSET==0x2104,"existing ABI");
    _Static_assert(VMWEAVE_PRIMARY_CONTEXT_STATE==0x2107,"existing ABI");
    struct vmweave_cuda_session s={0};uint8_t p[40]={0};
    struct vmweave_shm_request q={.api_id=VMWEAVE_MEMSET_NATIVE,.payload_schema=1,.input=p,.input_bytes=40};
    struct vmweave_shm_response r={0};memset(memory,0xcc,sizeof(memory));
    vmweave_put(p,7,8);vmweave_put(p+8,3,8);vmweave_put(p+16,250,8);vmweave_put(p+32,UINT32_MAX,4);
#ifdef OLD_WORKER
    assert(!vmweave_torch_dispatch(&s,&q,&r)&&r.transport_status==VMWEAVE_SHM_UNSUPPORTED_API&&!native_calls&&!async_calls);
    puts("PASS old worker: new opcode rejected without CUDA side effects");return 0;
#endif
    assert(!vmweave_torch_dispatch(&s,&q,&r)&&!r.transport_status&&!r.api_result&&!r.output_bytes&&native_calls==1);
    assert(memory[2]==0xcc&&memory[3]==255&&memory[252]==255&&memory[253]==0xcc);
    unsigned offsets[]={0,8,16,24,36};
    for(unsigned i=0;i<5;i++){uint8_t old[40];memcpy(old,p,40);vmweave_put(p+offsets[i],999,i==4?4:8);
        assert(!vmweave_torch_dispatch(&s,&q,&r)&&r.transport_status==VMWEAVE_SHM_BAD_DESCRIPTOR&&native_calls==1);memcpy(p,old,40);}
    q.input_bytes=39;assert(!vmweave_torch_dispatch(&s,&q,&r)&&r.transport_status&&native_calls==1);q.input_bytes=40;
    q.input=NULL;assert(!vmweave_torch_dispatch(&s,&q,&r)&&r.transport_status&&native_calls==1);q.input=p;
    q.payload_schema=2;assert(!vmweave_torch_dispatch(&s,&q,&r)&&r.transport_status==VMWEAVE_SHM_UNSUPPORTED_API&&native_calls==1);q.payload_schema=1;
    injected=cudaErrorInvalidValue;assert(!vmweave_torch_dispatch(&s,&q,&r)&&!r.transport_status&&r.api_result==injected&&native_calls==2);
    q.api_id=VMWEAVE_MEMSET;vmweave_put(p+24,9,8);
    assert(!vmweave_torch_dispatch(&s,&q,&r)&&!r.transport_status&&async_calls==1&&native_calls==2);
    puts("PASS worker: native dispatch, canaries, bounds/schema/stream, errors, old async ABI");
}
