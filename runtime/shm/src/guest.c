#define _GNU_SOURCE
#include "vmweave_env.h"
#include "vmweave_guest.h"
#include "vmweave_async.h"
#include "vmweave_torch.h"
#include "vmweave_trace.h"
#include "vmweave_perf.h"
/* Protected by vmweave_guest_lock; one synchronous copy owns this private buffer. */
static unsigned char *copy_buffer;
static size_t copy_capacity;
#include <cuda_runtime_api.h>
#include <cuda.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdatomic.h>
#include <time.h>
#include <errno.h>
#include <stdio.h>

pthread_mutex_t vmweave_guest_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t io_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t io_cond=PTHREAD_COND_INITIALIZER;
static pthread_t io_thread;
static int started,initialized,work,finished;
static size_t transport_request_bytes,transport_response_bytes;
static atomic_int broken;
static pid_t owner_pid;
static uint8_t trace_allocation[16]; /* Written and read only by the I/O thread. */
static struct {uint32_t api;const void *input;size_t bytes;void *output;size_t capacity,received;int result;} job;
static struct {void *base;size_t bytes,mapped;uint64_t handle;} allocations[4096];
/* One past the last live slot; protected by vmweave_guest_lock. */
static unsigned allocation_span;
static _Thread_local cudaError_t last_error;
int vmweave_guest_mirror_enabled(void){const char *v=vmweave_getenv("VMWEAVE_MIRROR_DEVICE_VA");return v&&!strcmp(v,"1");}
static void before_fork(void){pthread_mutex_lock(&vmweave_guest_lock);pthread_mutex_lock(&io_lock);}
static void after_fork(void){pthread_mutex_unlock(&io_lock);pthread_mutex_unlock(&vmweave_guest_lock);}
static void child_fork(void){broken=1;after_fork();}
__attribute__((constructor)) static void setup_fork(void){
    pthread_condattr_t attr;pthread_condattr_init(&attr);pthread_condattr_setclock(&attr,CLOCK_MONOTONIC);
    pthread_cond_init(&io_cond,&attr);pthread_condattr_destroy(&attr);pthread_atfork(before_fork,after_fork,child_fork);
}

static int exchange(struct vmweave_shm_channel *c,struct vmweave_shm_identity identity,uint64_t *id,
                    uint32_t api,const void *in,size_t n,void *out,size_t cap,size_t *got){
    struct vmweave_shm_request q={.identity=identity,.request_id=*id,.api_id=api,.payload_schema=1,.input=in,.input_bytes=n};
    struct vmweave_shm_response r={.output=out,.output_capacity=cap};
    if(vmweave_shm_submit(c,&q)){broken=1;return 999;}
    vmweave_trace("guest","submit",trace_allocation,&q,NULL);
    if(vmweave_shm_receive(c,*id,&r)){broken=1;return 999;}
    vmweave_trace("guest","receive",trace_allocation,&q,&r);
    ++*id;*got=r.output_bytes;
    if(r.transport_status){
        fprintf(stderr,"vmweave rejected api=0x%x transport_status=%u\n",api,r.transport_status);
        if(r.transport_status==VMWEAVE_SHM_UNSUPPORTED_API)return 801;broken=1;return 999;}
    if(r.result_domain!=VMWEAVE_RESULT_CUDA_RUNTIME&&r.result_domain!=VMWEAVE_RESULT_CUDA_DRIVER&&r.result_domain!=VMWEAVE_RESULT_LIBRARY&&api>VMWEAVE_HEARTBEAT){broken=1;return 999;}
    return (int)r.api_result;
}
static void *io_main(void *unused){
    (void)unused;struct vmweave_shm_layout l;struct vmweave_mapping m={0};struct vmweave_shm_channel *c=NULL;
    struct vmweave_shm_identity identity;uint64_t id=1;size_t got=0;unsigned long slot=0;char *end;
    const char *path=vmweave_getenv("VMWEAVE_LAYOUT"),*bdf=vmweave_getenv("VMWEAVE_IVSHMEM_BDF"),*slotenv=vmweave_getenv("VMWEAVE_SLOT");
    if(slotenv){slot=strtoul(slotenv,&end,10);if(*end||slot>=32)broken=1;}
    if(!path||!bdf||broken||vmweave_layout_read(path,&l)||slot>=l.session_count||vmweave_map_guest(bdf,&l,&m)||
       vmweave_shm_open(m.address,m.bytes,&l,(uint32_t)slot,VMWEAVE_SHM_GUEST,30000,&c))broken=1;
    if(!broken){
        transport_request_bytes=l.slots[slot].request_payload.bytes;
        if(transport_request_bytes>VMWEAVE_SHM_MAX_MESSAGE_BYTES)transport_request_bytes=VMWEAVE_SHM_MAX_MESSAGE_BYTES;
        transport_response_bytes=vmweave_shm_response_capacity(c);
        memcpy(trace_allocation,l.allocation_id,16);memcpy(identity.channel_generation,l.channel_generation,16);memcpy(identity.session_id,l.slots[slot].session_id,16);
        if(exchange(c,identity,&id,VMWEAVE_HELLO,NULL,0,NULL,0,&got))broken=1;}
    pthread_mutex_lock(&io_lock);initialized=1;pthread_cond_broadcast(&io_cond);
    while(!broken){
        while(!work&&!broken){
            struct timespec deadline;clock_gettime(CLOCK_MONOTONIC,&deadline);deadline.tv_sec+=2;
            int wait=pthread_cond_timedwait(&io_cond,&io_lock,&deadline);
            if(wait==ETIMEDOUT&&!work){
                pthread_mutex_unlock(&io_lock);size_t ignored;
                if(exchange(c,identity,&id,VMWEAVE_HEARTBEAT,NULL,0,NULL,0,&ignored))broken=1;
                pthread_mutex_lock(&io_lock);
            }else if(wait&&wait!=ETIMEDOUT)broken=1;
        }
        if(broken)break;
        pthread_mutex_unlock(&io_lock);
        job.result=exchange(c,identity,&id,job.api,job.input,job.bytes,job.output,job.capacity,&job.received);
        pthread_mutex_lock(&io_lock);work=0;finished=1;pthread_cond_broadcast(&io_cond);
        if(job.api==VMWEAVE_GOODBYE)broken=1;
    }
    pthread_cond_broadcast(&io_cond);pthread_mutex_unlock(&io_lock);vmweave_shm_close(c);vmweave_unmap(&m);return NULL;
}
extern int vmweave_broker_exchange(uint32_t,const void*,size_t,void*,size_t,size_t*);
extern void vmweave_broker_close(void);
int vmweave_guest_exchange(uint32_t api,const void *input,size_t bytes,void *output,size_t capacity,size_t *received){
    if(vmweave_getenv("VMWEAVE_BROKER_SOCKET")){size_t ignored;return vmweave_broker_exchange(api,input,bytes,output,capacity,received?received:&ignored);}
    if(owner_pid&&owner_pid!=getpid())return 999;
    uint64_t measured=vmweave_perf_enabled()?vmweave_perf_now():0;
    pthread_mutex_lock(&io_lock);
    if(!started){owner_pid=getpid();started=1;if(pthread_create(&io_thread,NULL,io_main,NULL)){broken=1;initialized=1;}}
    while(!initialized)pthread_cond_wait(&io_cond,&io_lock);
    if(broken){pthread_mutex_unlock(&io_lock);return 999;}
    job.api=api;job.input=input;job.bytes=bytes;job.output=output;job.capacity=capacity;job.received=0;
    finished=0;work=1;pthread_cond_broadcast(&io_cond);
    while(!finished&&!broken)pthread_cond_wait(&io_cond,&io_lock);
    int result=finished?job.result:999;if(received)*received=job.received;
    pthread_mutex_unlock(&io_lock);
    if(vmweave_getenv("VMWEAVE_TRACE_CALLS"))fprintf(stderr,"vmweave api=0x%x bytes=%zu result=%d\n",api,bytes,result);
    vmweave_perf_add(VMWEAVE_PERF_EXCHANGE,measured,bytes);
    return result;
}
__attribute__((destructor)) static void shutdown_guest(void){
    if(vmweave_getenv("VMWEAVE_BROKER_SOCKET")){vmweave_broker_close();return;}
    if(!started||owner_pid!=getpid()||pthread_mutex_trylock(&vmweave_guest_lock))return;
    size_t ignored;if(!broken)vmweave_guest_exchange(VMWEAVE_GOODBYE,NULL,0,NULL,0,&ignored);
    free(copy_buffer);copy_buffer=NULL;copy_capacity=0;
    pthread_mutex_unlock(&vmweave_guest_lock);if(initialized)pthread_join(io_thread,NULL);
    vmweave_perf_dump("guest-caller");
}
int vmweave_guest_ref(const void *p,size_t n,struct vmweave_device_ref *r){
    uintptr_t v=(uintptr_t)p;
    for(unsigned i=0;i<4096;i++)if(allocations[i].base){uintptr_t b=(uintptr_t)allocations[i].base;
        if(v>=b&&v-b<allocations[i].bytes&&n<=allocations[i].bytes-(v-b)){r->handle=allocations[i].handle;r->offset=v-b;return 0;}}
    /* Prefer a live allocation's base over a preceding allocation's one-past
     * address. Adjacent mirrored CUDA allocations make this case common. */
    if(!n)for(unsigned i=0;i<4096;i++)if(allocations[i].base&&v-(uintptr_t)allocations[i].base==allocations[i].bytes){
        r->handle=allocations[i].handle;r->offset=allocations[i].bytes;return 0;}
    return 1;
}
static cudaError_t finish(int e){last_error=(cudaError_t)e;return last_error;}
static void *reserve_device_va(uint64_t address,size_t bytes){
    if(!address||(address&4095)||!bytes||(bytes&4095)||address>UINTPTR_MAX-bytes)return MAP_FAILED;
    void *wanted=(void *)(uintptr_t)address;
    void *p=mmap(wanted,bytes,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
    /* Old kernels can ignore an unknown flag. Never accept another address. */
    if(p!=MAP_FAILED&&p!=wanted){munmap(p,bytes);return MAP_FAILED;}
    return p;
}
cudaError_t cudaMemGetInfo(size_t *free_bytes,size_t *total_bytes){
    if(!free_bytes||!total_bytes)return finish(cudaErrorInvalidValue);
    *free_bytes=0;*total_bytes=0;uint8_t out[16];size_t got=0;
    pthread_mutex_lock(&vmweave_guest_lock);
    int e=vmweave_guest_exchange(VMWEAVE_API_RUNTIME_MEM_GET_INFO,NULL,0,out,sizeof(out),&got);
    if(!e){
        if(got!=16||!vmweave_get(out+8,8)||vmweave_get(out,8)>vmweave_get(out+8,8))e=cudaErrorUnknown;
        else{*free_bytes=(size_t)vmweave_get(out,8);*total_bytes=(size_t)vmweave_get(out+8,8);}
    }
    pthread_mutex_unlock(&vmweave_guest_lock);return finish(e);
}
cudaError_t cudaMalloc(void **out,size_t n){
    if(!out)return finish(1);*out=NULL;pthread_mutex_lock(&vmweave_guest_lock);unsigned i;
    for(i=0;i<4096&&allocations[i].base;i++);int e=2;uint8_t in[8],result[8];size_t got=0;
    if(i==4096||n>SIZE_MAX-4095)goto done;
    size_t requested=n;
    if(vmweave_guest_mirror_enabled()&&n)requested=(n+4095)&~(size_t)4095;
    vmweave_put(in,requested,8);e=vmweave_guest_exchange(VMWEAVE_API_RUNTIME_MALLOC,in,8,result,8,&got);
    if(e)goto done;if(got!=8){e=999;goto done;}uint64_t handle=vmweave_get(result,8);if(!n&&!handle)goto done;
    size_t mapped=(n+4095)&~(size_t)4095;if(!mapped){e=999;goto done;}
    void *wanted=NULL;int flags=MAP_PRIVATE|MAP_ANONYMOUS;
    if(vmweave_guest_mirror_enabled()){
        vmweave_put(in,handle,8);e=vmweave_guest_exchange(VMWEAVE_ALLOCATION_ADDRESS,in,8,result,8,&got);
        if(!e&&(got!=8||!vmweave_get(result,8)||(vmweave_get(result,8)&4095)))e=801;
        if(e){vmweave_guest_exchange(VMWEAVE_API_RUNTIME_FREE,in,8,NULL,0,&got);goto done;}
        wanted=(void *)(uintptr_t)vmweave_get(result,8);flags|=MAP_FIXED_NOREPLACE;
    }
    void *p=wanted?reserve_device_va((uintptr_t)wanted,mapped):mmap(NULL,mapped,PROT_NONE,flags,-1,0);
    if(p==MAP_FAILED){vmweave_put(in,handle,8);vmweave_guest_exchange(VMWEAVE_API_RUNTIME_FREE,in,8,NULL,0,&got);e=2;goto done;}
    allocations[i].base=p;allocations[i].bytes=n;allocations[i].mapped=mapped;allocations[i].handle=handle;if(i>=allocation_span)allocation_span=i+1;*out=p;
done:pthread_mutex_unlock(&vmweave_guest_lock);return finish(e);
}
cudaError_t cudaFree(void *p){
    pthread_mutex_lock(&vmweave_guest_lock);unsigned i;uint64_t handle=0;int e=0;size_t got;uint8_t in[8];
    for(i=0;i<4096;i++)if(allocations[i].base==p&&p){handle=allocations[i].handle;break;}
    if(p&&!handle)e=1;
    else{vmweave_put(in,handle,8);e=vmweave_guest_exchange(VMWEAVE_API_RUNTIME_FREE,in,8,NULL,0,&got);
        if(!e&&p){munmap(p,allocations[i].mapped);memset(&allocations[i],0,sizeof(allocations[i]));
            while(allocation_span&&!allocations[allocation_span-1].base)--allocation_span;}}
    pthread_mutex_unlock(&vmweave_guest_lock);return finish(e);
}
/* Called after transport initialization. Broker uses this to account for the
 * actual slot arenas and its session envelope, not a guessed global maximum. */
int vmweave_guest_transport_limits(size_t *request,size_t *response){
    if(!request||!response)return 1;
    pthread_mutex_lock(&io_lock);
    int e=!initialized||broken||!transport_request_bytes||!transport_response_bytes;
    if(!e){*request=transport_request_bytes;*response=transport_response_bytes;}
    pthread_mutex_unlock(&io_lock);return e?999:0;
}
static int copy_limits_known;
static size_t copy_h2d_limit,copy_d2h_limit;
static int copy_large;
static int copy_limits(void){
    if(copy_limits_known)return 0;
    uint8_t out[24];size_t got=0;
    int e=vmweave_guest_exchange(VMWEAVE_COPY_LIMITS,NULL,0,out,sizeof(out),&got);
    if(e==801){ /* Old peers retain their existing small-copy protocol. */
        copy_h2d_limit=copy_d2h_limit=VMWEAVE_COPY_CHUNK_BYTES;
    }else{
        if(e)return e;
        if(got!=24||vmweave_get(out,4)!=1)return 801;
        unsigned flags=(unsigned)vmweave_get(out+4,4);
        uint64_t h=vmweave_get(out+8,8),d=vmweave_get(out+16,8);
        if(!h||!d||h>VMWEAVE_COPY_CHUNK_BYTES||d>VMWEAVE_COPY_CHUNK_BYTES)return 801;
        copy_h2d_limit=(size_t)h;copy_d2h_limit=(size_t)d;
        copy_large=(flags&1)&&(!vmweave_getenv("VMWEAVE_BROKER_SOCKET")||(flags&2));
    }
    if(!vmweave_getenv("VMWEAVE_BROKER_SOCKET")){
        size_t request,response;e=vmweave_guest_transport_limits(&request,&response);if(e)return e;
        if(request<=56||!response)return 801;
        if(copy_h2d_limit>request-56)copy_h2d_limit=request-56;
        if(copy_d2h_limit>response)copy_d2h_limit=response;
    }
    copy_limits_known=1;return 0;
}
/* Serialized by the public entry points. Validate the WHOLE operation before
 * sending chunk one. An error after a successful chunk is not rolled back. */
static int device_address(const void *pointer){
    uintptr_t p=(uintptr_t)pointer;
    for(unsigned i=0;i<allocation_span;i++)if(allocations[i].base){
        uintptr_t b=(uintptr_t)allocations[i].base;
        if(p>=b&&(p-b<allocations[i].mapped||p-b==allocations[i].bytes))return 1;
    }
    return 0;
}
int vmweave_guest_copy(void *dst,const void *src,size_t n,int kind,uint64_t stream,int async){
    struct vmweave_device_ref d={0},s={0};
    if(n&&(!dst||!src||n>UINTPTR_MAX-(uintptr_t)dst||n>UINTPTR_MAX-(uintptr_t)src))return 1;
    int dh=device_address(dst),sh=device_address(src);
    if(kind==cudaMemcpyDefault)kind=dh?(sh?cudaMemcpyDeviceToDevice:cudaMemcpyHostToDevice):(sh?cudaMemcpyDeviceToHost:cudaMemcpyHostToHost);
    if(kind==cudaMemcpyHostToHost){if(dh||sh)return 1;if(n)memmove(dst,src,n);return 0;}
    if(kind<cudaMemcpyHostToDevice||kind>cudaMemcpyDeviceToDevice)return 1;
    if(kind!=cudaMemcpyDeviceToHost&&vmweave_guest_ref(dst,n,&d))return 1;
    if(kind!=cudaMemcpyHostToDevice&&vmweave_guest_ref(src,n,&s))return 1;
    if((kind==cudaMemcpyHostToDevice&&sh)||(kind==cudaMemcpyDeviceToHost&&dh))return 1;
    if(kind==cudaMemcpyDeviceToDevice&&n&&d.handle==s.handle&&
       (d.offset>=s.offset?d.offset-s.offset:s.offset-d.offset)<n)return 1;
    int e=copy_limits();if(e)return e;
    if(n>VMWEAVE_COPY_CHUNK_BYTES&&!copy_large)return 801;
    size_t limit=kind==cudaMemcpyHostToDevice?copy_h2d_limit:copy_d2h_limit;
    if(kind==cudaMemcpyDeviceToDevice)limit=n;
    size_t chunk=n<limit?n:limit,header=async?56:48;
    size_t capacity=header+(kind==cudaMemcpyHostToDevice?chunk:0);
    int optimized=vmweave_copy_optimized();uint8_t *in;
    if(optimized){
        if(capacity>copy_capacity){void *p=realloc(copy_buffer,capacity);if(!p)return 2;copy_buffer=p;copy_capacity=capacity;}
        in=copy_buffer;
    }else{in=malloc(capacity);if(!in)return 2;}
    size_t offset=0;
    do{
        size_t bytes=n-offset;if(bytes>limit)bytes=limit;
        memset(in,0,header);uint8_t *p=in;
        if(async){vmweave_put(in,stream,8);p+=8;}
        vmweave_put(p,kind==cudaMemcpyHostToDevice?1:kind==cudaMemcpyDeviceToHost?2:3,4);
        vmweave_put(p+8,d.handle,8);vmweave_put(p+16,d.handle?d.offset+offset:0,8);
        vmweave_put(p+24,s.handle,8);vmweave_put(p+32,s.handle?s.offset+offset:0,8);vmweave_put(p+40,bytes,8);
        if(kind==cudaMemcpyHostToDevice&&bytes)memcpy(in+header,(const uint8_t*)src+offset,bytes);
        size_t got=0;void *output=kind==cudaMemcpyDeviceToHost&&bytes?(uint8_t*)dst+offset:NULL;
        e=vmweave_guest_exchange(async?VMWEAVE_ASYNC_COPY:VMWEAVE_API_RUNTIME_MEMCPY,in,
            header+(kind==cudaMemcpyHostToDevice?bytes:0),output,kind==cudaMemcpyDeviceToHost?bytes:0,&got);
        if(!e&&got!=(kind==cudaMemcpyDeviceToHost?bytes:0))e=999;
        if(e)break;
        offset+=bytes;
    }while(offset<n);
    if(!optimized)free(in);return e;
}
cudaError_t cudaMemcpy(void *dst,const void *src,size_t n,enum cudaMemcpyKind kind){
    pthread_mutex_lock(&vmweave_guest_lock);
    int e=vmweave_guest_copy(dst,src,n,kind,0,0);
    pthread_mutex_unlock(&vmweave_guest_lock);return finish(e);
}
static cudaError_t scalar(uint32_t api,int *out,int input){
    uint8_t in[4],result[4];size_t got;vmweave_put(in,(uint32_t)input,4);
    pthread_mutex_lock(&vmweave_guest_lock);int e=vmweave_guest_exchange(api,api==VMWEAVE_API_RUNTIME_SET_DEVICE?in:NULL,api==VMWEAVE_API_RUNTIME_SET_DEVICE?4:0,result,4,&got);
    if(!e&&out){if(got!=4)e=999;else *out=(int)vmweave_get(result,4);}pthread_mutex_unlock(&vmweave_guest_lock);return finish(e);
}
cudaError_t cudaGetDeviceCount(int *n){return n?scalar(VMWEAVE_API_RUNTIME_GET_DEVICE_COUNT,n,0):finish(1);}
cudaError_t cudaGetDevice(int *n){return n?scalar(VMWEAVE_API_RUNTIME_GET_DEVICE,n,0):finish(1);}
cudaError_t cudaSetDevice(int n){return scalar(VMWEAVE_API_RUNTIME_SET_DEVICE,NULL,n);}
cudaError_t cudaDeviceSynchronize(void){return scalar(VMWEAVE_API_RUNTIME_DEVICE_SYNCHRONIZE,NULL,0);}
cudaError_t cudaGetLastError(void){cudaError_t e=last_error;last_error=cudaSuccess;return e;}
cudaError_t cudaPeekAtLastError(void){return last_error;}
static CUresult driver(cudaError_t e){return e==cudaSuccess?CUDA_SUCCESS:e==cudaErrorInvalidValue?CUDA_ERROR_INVALID_VALUE:e==cudaErrorMemoryAllocation?CUDA_ERROR_OUT_OF_MEMORY:e==cudaErrorNotSupported?CUDA_ERROR_NOT_SUPPORTED:CUDA_ERROR_UNKNOWN;}
CUresult cuInit(unsigned flags){int n;if(flags)return CUDA_ERROR_INVALID_VALUE;return driver(cudaGetDeviceCount(&n));}
CUresult cuDeviceGetCount(int *n){return driver(cudaGetDeviceCount(n));}
CUresult cuDeviceGet(CUdevice *d,int ordinal){if(!d||ordinal)return CUDA_ERROR_INVALID_DEVICE;int n;CUresult e=driver(cudaGetDeviceCount(&n));if(e==CUDA_SUCCESS)*d=0;return e;}
CUresult cuMemAlloc_v2(CUdeviceptr *p,size_t n){if(!p)return CUDA_ERROR_INVALID_VALUE;void *v=NULL;cudaError_t e=cudaMalloc(&v,n);*p=(CUdeviceptr)(uintptr_t)v;return driver(e);}
CUresult cuMemFree_v2(CUdeviceptr p){return driver(cudaFree((void *)(uintptr_t)p));}
CUresult cuMemcpyHtoD_v2(CUdeviceptr d,const void *s,size_t n){return driver(cudaMemcpy((void *)(uintptr_t)d,s,n,cudaMemcpyHostToDevice));}
CUresult cuMemcpyDtoH_v2(void *d,CUdeviceptr s,size_t n){return driver(cudaMemcpy(d,(void *)(uintptr_t)s,n,cudaMemcpyDeviceToHost));}
CUresult cuMemcpyDtoD_v2(CUdeviceptr d,CUdeviceptr s,size_t n){return driver(cudaMemcpy((void *)(uintptr_t)d,(void *)(uintptr_t)s,n,cudaMemcpyDeviceToDevice));}
CUresult cuCtxSynchronize(void){return driver(cudaDeviceSynchronize());}
CUresult cuMemGetInfo_v2(size_t *free_bytes,size_t *total_bytes){return driver(cudaMemGetInfo(free_bytes,total_bytes));}

/* Legacy binary ABI: same implementation and address, no second state. */
extern __typeof__(vmweave_guest_exchange) flyt_guest_exchange __attribute__((alias("vmweave_guest_exchange")));
extern __typeof__(vmweave_guest_lock) flyt_guest_lock __attribute__((alias("vmweave_guest_lock")));
extern __typeof__(vmweave_guest_mirror_enabled) flyt_guest_mirror_enabled __attribute__((alias("vmweave_guest_mirror_enabled")));
extern __typeof__(vmweave_guest_ref) flyt_guest_ref __attribute__((alias("vmweave_guest_ref")));
