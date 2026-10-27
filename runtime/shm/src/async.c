#include "vmweave_async.h"
#include "vmweave_torch.h"
#include <cuda_runtime_api.h>
#include <cuda.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

enum {STREAM=1,EVENT,MODULE,FUNCTION,UPLOAD};
struct object {uint64_t id,parent;int kind;void *pointer;size_t bytes,received;};
static struct object objects[4096];static uint64_t next=1;
static size_t upload_bytes;
struct stage {void *host;cudaEvent_t done;size_t bytes;int active;};
static pthread_once_t pool_once=PTHREAD_ONCE_INIT;static int pool_enabled;static size_t pool_bytes;
static void pool_configure(void){const char *v=getenv("VMWEAVE_PINNED_POOL");pool_enabled=v&&!strcmp(v,"1");}
static int pooled(void){pthread_once(&pool_once,pool_configure);return pool_enabled;}
static size_t staged_bytes;static struct stage stages[128];
static struct object *find(uint64_t id,int kind){for(int i=0;i<4096;i++)if(objects[i].id==id&&id&&objects[i].kind==kind)return &objects[i];return NULL;}
static struct object *reserve(void){if(next==UINT64_MAX)return NULL;for(int i=0;i<4096;i++)if(!objects[i].id)return &objects[i];return NULL;}
static int stream(uint64_t id,cudaStream_t *out){struct object *o;if(!id){*out=0;return 1;}o=find(id,STREAM);if(!o)return 0;*out=(cudaStream_t)o->pointer;return 1;}
int vmweave_async_stream(uint64_t id,void **out){cudaStream_t s;if(!stream(id,&s))return 0;*out=s;return 1;}
int vmweave_async_reap(void){
    for(int i=0;i<128;i++)if(stages[i].host&&stages[i].active){
        cudaError_t e=cudaEventQuery(stages[i].done);
        if(e==cudaErrorNotReady)continue;if(e!=cudaSuccess)return -1;
        if(!pooled()){
            if(cudaEventDestroy(stages[i].done)!=cudaSuccess||cudaFreeHost(stages[i].host)!=cudaSuccess)return -1;
        }
        staged_bytes-=stages[i].bytes;
        if(pooled())stages[i].active=0;else memset(&stages[i],0,sizeof(stages[i]));
    }return 0;
}
/* Return -1 only for a session-fatal completion/cleanup failure. */
static int pool_acquire(size_t bytes,int *slot){
    size_t capacity=4096;
    while(capacity<bytes){if(capacity>VMWEAVE_ASYNC_STAGING_BYTES/2)return cudaErrorMemoryAllocation;capacity*=2;}
    if(capacity>VMWEAVE_ASYNC_STAGING_BYTES)return cudaErrorMemoryAllocation;
    for(;;){
        if(vmweave_async_reap())return -1;
        int best=-1,empty=-1,pending=-1;
        for(int i=0;i<128;i++){
            if(!stages[i].host){if(empty<0)empty=i;continue;}
            if(stages[i].active){if(pending<0)pending=i;continue;}
            if(stages[i].bytes>=capacity&&(best<0||stages[i].bytes<stages[best].bytes))best=i;
        }
        if(best>=0){*slot=best;return 0;}
        /* Evict completed slots only; live DMA storage must never be freed. */
        for(int i=0;i<128&&(empty<0||capacity>VMWEAVE_ASYNC_STAGING_BYTES-pool_bytes);i++){
            if(stages[i].host&&!stages[i].active){
                if(cudaEventDestroy(stages[i].done)!=cudaSuccess||cudaFreeHost(stages[i].host)!=cudaSuccess)return -1;
                pool_bytes-=stages[i].bytes;memset(&stages[i],0,sizeof(stages[i]));if(empty<0)empty=i;
            }
        }
        if(empty>=0&&capacity<=VMWEAVE_ASYNC_STAGING_BYTES-pool_bytes){
            void *host=NULL;cudaEvent_t event=NULL;
            cudaError_t e=cudaHostAlloc(&host,capacity,cudaHostAllocDefault);if(e)return e;
            e=cudaEventCreateWithFlags(&event,cudaEventDisableTiming);
            if(e){if(cudaFreeHost(host)!=cudaSuccess)return -1;return e;}
            stages[empty]=(struct stage){.host=host,.done=event,.bytes=capacity};pool_bytes+=capacity;*slot=empty;return 0;
        }
        if(pending<0||cudaEventSynchronize(stages[pending].done)!=cudaSuccess)return -1;
    }
}
int vmweave_async_dispatch(struct vmweave_cuda_session *s,const struct vmweave_shm_request *q,struct vmweave_shm_response *r){
    const uint8_t *p=q->input;size_t n=q->input_bytes;struct object *o=NULL;cudaStream_t st=0;uint64_t id=0;
    r->output_bytes=0;r->api_result=0;r->result_domain=VMWEAVE_RESULT_CUDA_RUNTIME;r->transport_status=0;
    if(q->payload_schema!=1)goto unsupported;
    switch(q->api_id){
    case VMWEAVE_STREAM_PRIORITY_CREATE: {
        if(n!=8||r->output_capacity<8||!r->output)goto invalid;o=reserve();if(!o)goto internal;
        cudaStream_t v=NULL;r->api_result=cudaStreamCreateWithPriority(&v,(unsigned)vmweave_get(p,4),(int)vmweave_get(p+4,4));
        if(!r->api_result){o->pointer=v;o->kind=STREAM;o->id=next++;vmweave_put(r->output,o->id,8);r->output_bytes=8;}break;
    }
    case VMWEAVE_MODULE_BEGIN: {
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;
        if(n!=8||vmweave_get(p,8)<16||vmweave_get(p,8)>VMWEAVE_MAX_MODULE_BYTES||r->output_capacity<8||!r->output)goto invalid;
        size_t bytes=(size_t)vmweave_get(p,8);if(bytes>VMWEAVE_MAX_MODULE_BYTES-upload_bytes){r->api_result=CUDA_ERROR_OUT_OF_MEMORY;break;}
        o=reserve();if(!o)goto internal;void *data=malloc(bytes);
        if(!data){r->api_result=CUDA_ERROR_OUT_OF_MEMORY;break;}
        o->id=next++;o->kind=UPLOAD;o->pointer=data;o->bytes=bytes;o->received=0;upload_bytes+=bytes;
        vmweave_put(r->output,o->id,8);r->output_bytes=8;break;
    }
    case VMWEAVE_MODULE_CHUNK: {
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;
        if(n<=16||n>65536+16||(o=find(vmweave_get(p,8),UPLOAD))==NULL||vmweave_get(p+8,8)!=o->received||n-16>o->bytes-o->received)goto invalid;
        memcpy((uint8_t*)o->pointer+o->received,p+16,n-16);o->received+=n-16;break;
    }
    case VMWEAVE_MODULE_COMMIT: {
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;
        if(n!=8||(o=find(vmweave_get(p,8),UPLOAD))==NULL||o->received!=o->bytes||r->output_capacity<8||!r->output)goto invalid;
        const uint8_t *data=o->pointer;
        if(vmweave_get(data,4)!=0xba55ed50||vmweave_get(data+6,2)<16||vmweave_get(data+6,2)>o->bytes||
           vmweave_get(data+8,8)!=o->bytes-vmweave_get(data+6,2))goto invalid;
        CUmodule module=NULL;r->api_result=cuModuleLoadData(&module,data);
        upload_bytes-=o->bytes;free(o->pointer);o->pointer=NULL;
        if(!r->api_result){o->pointer=module;o->kind=MODULE;vmweave_put(r->output,o->id,8);r->output_bytes=8;}
        else memset(o,0,sizeof(*o));break;
    }
    case VMWEAVE_FUNCTION_LAYOUT: {
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;
        if(n!=8||(o=find(vmweave_get(p,8),FUNCTION))==NULL||r->output_capacity<8+64*4||!r->output)goto invalid;
        unsigned count=0;size_t offset,size;
        for(;count<64;count++){
            CUresult e=cuFuncGetParamInfo((CUfunction)o->pointer,count,&offset,&size);
            if(e==CUDA_ERROR_INVALID_VALUE)break;
            if(e){r->api_result=e;break;}
            if(!size||size>VMWEAVE_MAX_PARAMETER_BYTES||offset>VMWEAVE_MAX_PARAMETER_BYTES-size){r->api_result=CUDA_ERROR_NOT_SUPPORTED;break;}
            vmweave_put(r->output+8+4*count,size,4);
        }
        if(count==64){CUresult e=cuFuncGetParamInfo((CUfunction)o->pointer,count,&offset,&size);if(e!=CUDA_ERROR_INVALID_VALUE)r->api_result=CUDA_ERROR_NOT_SUPPORTED;}
        if(!r->api_result){vmweave_put(r->output,count,4);vmweave_put(r->output+4,0,4);r->output_bytes=8+4*count;}break;
    }
    case VMWEAVE_KERNEL_PACKED: {
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;
        if(n<48||n>48+VMWEAVE_MAX_PARAMETER_BYTES||(o=find(vmweave_get(p,8),FUNCTION))==NULL||!stream(vmweave_get(p+8,8),&st))goto invalid;
        unsigned count=(unsigned)vmweave_get(p+44,4);if(count>64)goto invalid;
        void *params[64];size_t pos=48,used=0;unsigned char values[VMWEAVE_MAX_PARAMETER_BYTES+1024];
        for(unsigned i=0;i<count;i++){
            if(n-pos<4)goto invalid;size_t bytes=(size_t)vmweave_get(p+pos,4),offset=0,expected=0;pos+=4;
            if(!bytes||bytes>n-pos||cuFuncGetParamInfo((CUfunction)o->pointer,i,&offset,&expected)!=CUDA_SUCCESS||bytes!=expected)goto invalid;
            used=(used+15)&~(size_t)15;if(bytes>sizeof(values)-used)goto invalid;
            memcpy(values+used,p+pos,bytes);params[i]=values+used;used+=bytes;pos+=bytes;
        }
        size_t offset=0,size=0;
        if(pos!=n||cuFuncGetParamInfo((CUfunction)o->pointer,count,&offset,&size)!=CUDA_ERROR_INVALID_VALUE)goto invalid;
        r->api_result=cuLaunchKernel((CUfunction)o->pointer,(unsigned)vmweave_get(p+16,4),(unsigned)vmweave_get(p+20,4),(unsigned)vmweave_get(p+24,4),
            (unsigned)vmweave_get(p+28,4),(unsigned)vmweave_get(p+32,4),(unsigned)vmweave_get(p+36,4),(unsigned)vmweave_get(p+40,4),(CUstream)st,params,NULL);break;
    }
    case VMWEAVE_STREAM_CREATE:case VMWEAVE_EVENT_CREATE:
        if(n!=4||r->output_capacity<8||!r->output)goto invalid;o=reserve();if(!o)goto internal;
        if(q->api_id==VMWEAVE_STREAM_CREATE){cudaStream_t v=NULL;r->api_result=cudaStreamCreateWithFlags(&v,(unsigned)vmweave_get(p,4));o->pointer=v;o->kind=STREAM;}
        else{cudaEvent_t v=NULL;r->api_result=cudaEventCreateWithFlags(&v,(unsigned)vmweave_get(p,4));o->pointer=v;o->kind=EVENT;}
        if(!r->api_result){o->id=next++;vmweave_put(r->output,o->id,8);r->output_bytes=8;}break;
    case VMWEAVE_STREAM_DESTROY:case VMWEAVE_STREAM_SYNC:case VMWEAVE_STREAM_QUERY:
        if(n!=8||!stream(vmweave_get(p,8),&st))goto invalid;
        if(q->api_id==VMWEAVE_STREAM_SYNC)r->api_result=cudaStreamSynchronize(st);
        else if(q->api_id==VMWEAVE_STREAM_QUERY)r->api_result=cudaStreamQuery(st);
        else{if(!st)goto invalid;o=find(vmweave_get(p,8),STREAM);r->api_result=cudaStreamDestroy(st);if(!r->api_result)memset(o,0,sizeof(*o));}break;
    case VMWEAVE_EVENT_DESTROY:case VMWEAVE_EVENT_SYNC:case VMWEAVE_EVENT_QUERY:case VMWEAVE_EVENT_RECORD:
        if(n!=(q->api_id==VMWEAVE_EVENT_RECORD?16:8)||(o=find(vmweave_get(p,8),EVENT))==NULL)goto invalid;
        if(q->api_id==VMWEAVE_EVENT_RECORD){if(!stream(vmweave_get(p+8,8),&st))goto invalid;r->api_result=cudaEventRecord((cudaEvent_t)o->pointer,st);}
        else if(q->api_id==VMWEAVE_EVENT_SYNC)r->api_result=cudaEventSynchronize((cudaEvent_t)o->pointer);
        else if(q->api_id==VMWEAVE_EVENT_QUERY)r->api_result=cudaEventQuery((cudaEvent_t)o->pointer);
        else{r->api_result=cudaEventDestroy((cudaEvent_t)o->pointer);if(!r->api_result)memset(o,0,sizeof(*o));}break;
    case VMWEAVE_ASYNC_COPY:{
        if(n<56||vmweave_get(p+12,4)||!stream(vmweave_get(p,8),&st))goto invalid;
        unsigned k=(unsigned)vmweave_get(p+8,4);uint64_t bytes=vmweave_get(p+48,8);void *dst=NULL,*src=NULL;
        struct vmweave_device_ref d={vmweave_get(p+16,8),vmweave_get(p+24,8)},a={vmweave_get(p+32,8),vmweave_get(p+40,8)};
        if(k<1||k>3||bytes>SIZE_MAX||(k!=3&&bytes>VMWEAVE_COPY_CHUNK_BYTES)||n!=56+(k==1?(size_t)bytes:0))goto invalid;
        if(k!=2&&!vmweave_cuda_exec_resolve(s->exec,d,(size_t)bytes,&dst))goto invalid;
        if(k!=1&&!vmweave_cuda_exec_resolve(s->exec,a,(size_t)bytes,&src))goto invalid;
        if(k==3&&bytes&&d.handle==a.handle&&(d.offset>=a.offset?d.offset-a.offset:a.offset-d.offset)<bytes)goto invalid;
        if(k==2&&(bytes>r->output_capacity||(bytes&&!r->output)))goto invalid;
        if(!bytes)break;
        if(k==1){
            int i=-1;void *host=NULL;cudaEvent_t event=NULL;size_t capacity=(size_t)bytes;
            if(pooled()){
                int result=pool_acquire((size_t)bytes,&i);if(result<0)return -1;
                r->api_result=(uint32_t)result;if(result)break;
                host=stages[i].host;event=stages[i].done;capacity=stages[i].bytes;
            }else{
                for(;;){
                    if(vmweave_async_reap())return -1;
                    for(i=0;i<128&&stages[i].host;i++);
                    if(i<128&&bytes<=VMWEAVE_ASYNC_STAGING_BYTES-staged_bytes)break;
                    int pending;for(pending=0;pending<128&&!stages[pending].host;pending++);
                    if(pending==128||cudaEventSynchronize(stages[pending].done)!=cudaSuccess)return -1;
                }
                r->api_result=cudaHostAlloc(&host,capacity,cudaHostAllocDefault);if(r->api_result)break;
                r->api_result=cudaEventCreateWithFlags(&event,cudaEventDisableTiming);
                if(r->api_result){if(cudaFreeHost(host)!=cudaSuccess)return -1;break;}
            }
            memcpy(host,p+56,(size_t)bytes);
            /* Track ownership before enqueue; failed enqueue/record terminates
             * the CUDA process without reusing possibly in-flight memory. */
            stages[i]=(struct stage){.host=host,.done=event,.bytes=capacity,.active=1};staged_bytes+=capacity;
            r->api_result=cudaMemcpyAsync(dst,host,(size_t)bytes,cudaMemcpyHostToDevice,st);
            if(!r->api_result)r->api_result=cudaEventRecord(event,st);
            if(r->api_result)return -1;
        }else if(k==2){
            /* Conservative completion: this initial DtoH path blocks until stream
             * work completes and bytes can be returned, never returns stale data. */
            r->api_result=cudaStreamSynchronize(st);
            if(!r->api_result)r->api_result=cudaMemcpy(r->output,src,(size_t)bytes,cudaMemcpyDeviceToHost);
            if(!r->api_result)r->output_bytes=(size_t)bytes;
        }else r->api_result=cudaMemcpyAsync(dst,src,(size_t)bytes,cudaMemcpyDeviceToDevice,st);
        break;}
    case VMWEAVE_MODULE_LOAD:{
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;
        if(!n||n>VMWEAVE_PTX_MAX_BYTES||p[n-1]||memchr(p,0,n-1)||r->output_capacity<8||!r->output)goto invalid;
        o=reserve();if(!o)goto internal;CUmodule m=NULL;r->api_result=cuModuleLoadData(&m,p);
        if(!r->api_result){o->kind=MODULE;o->pointer=m;o->id=next++;vmweave_put(r->output,o->id,8);r->output_bytes=8;}break;}
    case VMWEAVE_MODULE_UNLOAD:
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;if(n!=8||(o=find(vmweave_get(p,8),MODULE))==NULL)goto invalid;
        r->api_result=cuCtxSynchronize();if(!r->api_result)r->api_result=cuModuleUnload((CUmodule)o->pointer);
        if(!r->api_result){id=o->id;memset(o,0,sizeof(*o));for(int i=0;i<4096;i++)if(objects[i].parent==id)memset(&objects[i],0,sizeof(objects[i]));}break;
    case VMWEAVE_FUNCTION_GET:{
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;if(n<10||n>4104||p[n-1]||memchr(p+8,0,n-9)||r->output_capacity<8||!r->output)goto invalid;
        struct object *m=find(vmweave_get(p,8),MODULE);if(!m)goto invalid;o=reserve();if(!o)goto internal;
        CUfunction f=NULL;r->api_result=cuModuleGetFunction(&f,(CUmodule)m->pointer,(const char *)p+8);
        if(!r->api_result){o->id=next++;o->kind=FUNCTION;o->parent=m->id;o->pointer=f;vmweave_put(r->output,o->id,8);r->output_bytes=8;}break;}
    case VMWEAVE_KERNEL_LAUNCH:{
        r->result_domain=VMWEAVE_RESULT_CUDA_DRIVER;if(n<48||(o=find(vmweave_get(p,8),FUNCTION))==NULL||!stream(vmweave_get(p+8,8),&st))goto invalid;
        uint32_t count=(uint32_t)vmweave_get(p+44,4);if(count>64)goto invalid;
        void *params[64];unsigned char values[64][16];size_t pos=48;
        for(unsigned i=0;i<count;i++){
            if(n-pos<24)goto invalid;unsigned type=(unsigned)vmweave_get(p+pos,4),size=(unsigned)vmweave_get(p+pos+4,4);
            if(!size||size>16)goto invalid;
            if(type==1){void *address;struct vmweave_device_ref a={vmweave_get(p+pos+8,8),vmweave_get(p+pos+16,8)};
                if(size!=8||!vmweave_cuda_exec_resolve(s->exec,a,0,&address))goto invalid;memcpy(values[i],&address,8);}
            else if(type==0)memcpy(values[i],p+pos+8,size);else goto invalid;
            params[i]=values[i];pos+=24;
        }
        if(pos!=n)goto invalid;
        r->api_result=cuLaunchKernel((CUfunction)o->pointer,(unsigned)vmweave_get(p+16,4),(unsigned)vmweave_get(p+20,4),(unsigned)vmweave_get(p+24,4),
            (unsigned)vmweave_get(p+28,4),(unsigned)vmweave_get(p+32,4),(unsigned)vmweave_get(p+36,4),(unsigned)vmweave_get(p+40,4),(CUstream)st,params,NULL);break;}
    default:goto unsupported;
    }
    return 0;
invalid:r->transport_status=VMWEAVE_SHM_BAD_DESCRIPTOR;goto error;
unsupported:r->transport_status=VMWEAVE_SHM_UNSUPPORTED_API;goto error;
internal:r->transport_status=VMWEAVE_SHM_INTERNAL_ERROR;
error:r->result_domain=0;r->api_result=0;r->output_bytes=0;return 0;
}
int vmweave_async_close(void){
    if(cudaDeviceSynchronize()!=cudaSuccess)return -1;
    if(vmweave_async_reap())return -1;
    for(int i=0;i<128;i++)if(stages[i].host){
        if(stages[i].active||cudaEventDestroy(stages[i].done)!=cudaSuccess||cudaFreeHost(stages[i].host)!=cudaSuccess)return -1;
        pool_bytes-=stages[i].bytes;memset(&stages[i],0,sizeof(stages[i]));
    }
    for(int i=0;i<4096;i++)if(objects[i].id){int e=0;
        if(objects[i].kind==STREAM)e=cudaStreamDestroy((cudaStream_t)objects[i].pointer);
        if(objects[i].kind==EVENT)e=cudaEventDestroy((cudaEvent_t)objects[i].pointer);
        if(objects[i].kind==MODULE)e=cuModuleUnload((CUmodule)objects[i].pointer);
        if(objects[i].kind==UPLOAD){upload_bytes-=objects[i].bytes;free(objects[i].pointer);}
        if(e)return -1;memset(&objects[i],0,sizeof(objects[i]));}
    return 0;
}

/* Legacy binary ABI: same implementation and address, no second state. */
extern __typeof__(vmweave_async_close) flyt_async_close __attribute__((alias("vmweave_async_close")));
extern __typeof__(vmweave_async_dispatch) flyt_async_dispatch __attribute__((alias("vmweave_async_dispatch")));
extern __typeof__(vmweave_async_reap) flyt_async_reap __attribute__((alias("vmweave_async_reap")));
extern __typeof__(vmweave_async_stream) flyt_async_stream __attribute__((alias("vmweave_async_stream")));
