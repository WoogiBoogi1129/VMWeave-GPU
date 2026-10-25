/* Worker async dispatcher with delayed mock completion: bounded live staging. */
#include "../../runtime/shm/src/async.c"
#include <assert.h>
#include <stdio.h>
static size_t live,peak,waits,copies,last_bytes;
static int enqueue_error,record_error,wait_error;
struct mock_event {int ready;};
cudaError_t cudaHostAlloc(void **p,size_t n,unsigned flags){(void)flags;*p=malloc(n);assert(*p);live+=n;if(live>peak)peak=live;return cudaSuccess;}
cudaError_t cudaFreeHost(void *p){for(int i=0;i<128;i++)if(stages[i].host==p)live-=stages[i].bytes;free(p);return cudaSuccess;}
cudaError_t cudaEventCreateWithFlags(cudaEvent_t *e,unsigned f){(void)f;*e=(cudaEvent_t)calloc(1,sizeof(struct mock_event));assert(*e);return cudaSuccess;}
cudaError_t cudaEventRecord(cudaEvent_t e,cudaStream_t s){(void)e;(void)s;return record_error?cudaErrorUnknown:cudaSuccess;}
cudaError_t cudaEventQuery(cudaEvent_t e){return ((struct mock_event*)e)->ready?cudaSuccess:cudaErrorNotReady;}
cudaError_t cudaEventSynchronize(cudaEvent_t e){waits++;if(wait_error)return cudaErrorUnknown;((struct mock_event*)e)->ready=1;return cudaSuccess;}
cudaError_t cudaEventDestroy(cudaEvent_t e){assert(((struct mock_event*)e)->ready);free(e);return cudaSuccess;}
cudaError_t cudaDeviceSynchronize(void){for(int i=0;i<128;i++)if(stages[i].host)((struct mock_event*)stages[i].done)->ready=1;return cudaSuccess;}
cudaError_t cudaMemcpyAsync(void *d,const void *a,size_t n,enum cudaMemcpyKind k,cudaStream_t st){(void)d;(void)a;(void)k;(void)st;copies++;last_bytes=n;return enqueue_error?cudaErrorUnknown:cudaSuccess;}
int vmweave_cuda_exec_resolve(struct vmweave_cuda_exec *s,struct vmweave_device_ref r,size_t n,void **p){
    (void)s;if(r.handle!=1&&r.handle!=2)return 0;if(r.offset>256*1024*1024||n>256*1024*1024-r.offset)return 0;*p=(void*)(uintptr_t)(0x10000000*r.handle+r.offset);return 1;
}
int main(int argc,char **argv){
    struct vmweave_cuda_session session={0};size_t chunk=VMWEAVE_COPY_CHUNK_BYTES;
    uint8_t *p=calloc(1,chunk+56);assert(p);vmweave_put(p+8,1,4);vmweave_put(p+16,1,8);vmweave_put(p+48,chunk,8);
    struct vmweave_shm_request q={.api_id=VMWEAVE_ASYNC_COPY,.payload_schema=1,.input=p,.input_bytes=56+chunk};
    struct vmweave_shm_response r={0};
    if(argc>1){
        if(!strcmp(argv[1],"enqueue"))enqueue_error=1;
        else if(!strcmp(argv[1],"record"))record_error=1;
        else wait_error=1;
        int rc=0;for(int i=0;i<5&&!rc;i++)rc=vmweave_async_dispatch(&session,&q,&r);
        assert(rc==-1);assert(live>0);puts("PASS: in-flight failure requests process retirement without unsafe free");return 0;
    }
    for(int i=0;i<20;i++){
        assert(!vmweave_async_dispatch(&session,&q,&r)&&!r.transport_status&&!r.api_result);
        assert(staged_bytes==live&&live<=VMWEAVE_ASYNC_STAGING_BYTES);
    }
    assert(waits==16&&peak==VMWEAVE_ASYNC_STAGING_BYTES&&copies==20);
    assert(!vmweave_async_close()&&!live&&!staged_bytes);
    q.input_bytes=56;vmweave_put(p+8,3,4);vmweave_put(p+32,2,8);vmweave_put(p+48,16793604,8);
    assert(!vmweave_async_dispatch(&session,&q,&r)&&!r.transport_status&&!r.api_result&&last_bytes==16793604);
    size_t before=copies;vmweave_put(p+32,1,8);
    assert(!vmweave_async_dispatch(&session,&q,&r)&&r.transport_status==VMWEAVE_SHM_BAD_DESCRIPTOR&&copies==before);
    vmweave_put(p+32,99,8);assert(!vmweave_async_dispatch(&session,&q,&r)&&r.transport_status&&copies==before);
    vmweave_put(p+32,2,8);vmweave_put(p+48,UINT64_MAX,8);assert(!vmweave_async_dispatch(&session,&q,&r)&&r.transport_status&&copies==before);
    free(p);puts("PASS: async byte budget/backpressure, completion cleanup, large D2D, overlap/unknown handle/overflow rejection");
}
