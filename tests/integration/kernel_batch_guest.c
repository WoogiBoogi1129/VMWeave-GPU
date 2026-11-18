/* Actual public Guest entry points, mock broker: no GPU required. */
#include "../../runtime/shm/src/guest.c"
#include "../../runtime/shm/src/guest_async.c"
#include <assert.h>
#include <sys/wait.h>
static unsigned calls,launched,caps,fail_batch,old_peer;
static uint32_t expected;
void vmweave_broker_close(void){}
int vmweave_broker_direct_enabled(void){return 1;}
int vmweave_broker_copy_direct(const void *h,const void *p,size_t n,size_t *got){
    (void)h;(void)p;(void)n;assert(!kernel_batch.count);*got=0;return 0;
}
static void record(const uint8_t *p,size_t n){
    assert(n==72&&vmweave_get(p,8)==7&&vmweave_get(p+44,4)==1);
    assert(vmweave_get(p+56,4)==expected++);launched++;
}
int vmweave_broker_exchange(uint32_t api,const void *input,size_t n,void *output,size_t cap,size_t *got){
    const uint8_t *p=input;*got=0;
    if(api==VMWEAVE_KERNEL_BATCH_CAPS){
        caps++;if(old_peer)return 801;assert(!n&&cap==16);
        vmweave_put(output,1,4);vmweave_put((uint8_t*)output+4,VMWEAVE_KERNEL_BATCH_MAX,4);
        vmweave_put((uint8_t*)output+8,VMWEAVE_KERNEL_BATCH_BYTES,4);vmweave_put((uint8_t*)output+12,1,4);*got=16;return 0;
    }
    if(api==VMWEAVE_KERNEL_BATCH){
        calls++;if(fail_batch)return 719;
        assert(vmweave_get(p,4)==1);size_t pos=8;unsigned count=(unsigned)vmweave_get(p+4,4);
        assert(count&&count<=128);
        for(unsigned i=0;i<count;i++){size_t bytes=(size_t)vmweave_get(p+pos,4);pos+=4;assert(bytes<=n-pos);record(p+pos,bytes);pos+=bytes;}
        assert(pos==n);return 0;
    }
    if(api==VMWEAVE_KERNEL_LAUNCH){record(p,n);return 0;}
    assert(!kernel_batch.count); /* barriers must flush first */
    if(api==VMWEAVE_COPY_LIMITS){assert(cap==24);vmweave_put(output,1,4);vmweave_put((uint8_t*)output+4,3,4);
        vmweave_put((uint8_t*)output+8,VMWEAVE_COPY_CHUNK_BYTES,8);vmweave_put((uint8_t*)output+16,VMWEAVE_COPY_CHUNK_BYTES,8);*got=24;return 0;}
    assert(api==VMWEAVE_API_RUNTIME_DEVICE_SYNCHRONIZE||api==VMWEAVE_API_RUNTIME_FREE||api==VMWEAVE_STREAM_SYNC||api==VMWEAVE_MODULE_UNLOAD);
    return 0;
}
static int launch(uint32_t value,CUstream st){void *params[]={&value};return cuLaunchKernel((CUfunction)(uintptr_t)7,1,1,1,1,1,1,0,st,params,NULL);}
int main(int argc,char **argv){
    setenv("VMWEAVE_BROKER_SOCKET","mock",1);
    setenv("VMWEAVE_KERNEL_BATCH",argc>1&&!strcmp(argv[1],"off")?"0":"1",1);
    old_peer=argc>1&&!strcmp(argv[1],"old");
    uint8_t sizes[]={4},pointers[]={0};assert(!vmweaveRegisterKernelABI((CUfunction)(uintptr_t)7,1,sizes,pointers));
    for(unsigned i=0;i<1000;i++)assert(!launch(i,0));
    assert(!cudaDeviceSynchronize()&&launched==1000);
    if(old_peer||!strcmp(getenv("VMWEAVE_KERNEL_BATCH"),"0")){
        assert(!calls&&caps==old_peer);puts("PASS: opt-out / unsupported peer preserves synchronous path");return 0;
    }
    assert(caps==1&&calls<1000);
    /* Nondefault stream, copy, free, stream sync and unload are boundaries. */
    assert(!launch(1000,0)&&!launch(1001,(CUstream)(uintptr_t)9)&&launched==1002);
    allocations[0]=(typeof(allocations[0])){.base=(void*)0x10000000,.bytes=2*1024*1024,.mapped=2*1024*1024,.handle=3};allocation_span=1;
    char *host=malloc(2*1024*1024);assert(host);
    assert(!launch(1002,0)&&!cudaMemcpy(allocations[0].base,host,2*1024*1024,cudaMemcpyHostToDevice)&&launched==1003);free(host);memset(allocations,0,sizeof(allocations));allocation_span=0;
    assert(!launch(1003,0)&&!cudaFree(NULL)&&launched==1004);
    assert(!launch(1004,0)&&!cudaStreamSynchronize(0)&&launched==1005);
    assert(!launch(1005,0)&&!cuModuleUnload((CUmodule)(uintptr_t)1)&&launched==1006);
    /* Progress without another CUDA call; tolerate host scheduling up to 2 s. */
    assert(!launch(1006,0));unsigned complete=0;
    for(unsigned i=0;i<2000&&!complete;i++){usleep(1000);pthread_mutex_lock(&vmweave_guest_lock);complete=launched==1007;pthread_mutex_unlock(&vmweave_guest_lock);}
    assert(complete);
    pid_t child=fork();assert(child>=0);if(!child)_exit(launch(1007,0)==999?0:1);
    int status;assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&!WEXITSTATUS(status));
    /* Error is sticky, never replay a partially executed packet. */
    pthread_mutex_lock(&vmweave_guest_lock);fail_batch=1;pthread_mutex_unlock(&vmweave_guest_lock);
    int e=launch(1007,0);assert(!e||e==719);assert(cudaDeviceSynchronize()==719);
    pthread_mutex_lock(&vmweave_guest_lock);unsigned saved=calls;pthread_mutex_unlock(&vmweave_guest_lock);
    assert(launch(1008,0)==719&&cudaDeviceSynchronize()==719&&calls==saved);
    puts("PASS: bounded batching, argument snapshots, order, boundaries, timed progress, fork rejection, sticky errors and no replay");
    return 0;
}
