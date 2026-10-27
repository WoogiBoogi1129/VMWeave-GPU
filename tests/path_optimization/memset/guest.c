/* Compile the real wrapper, dropping unrelated APIs at link time. */
#include "../../../runtime/shm/src/guest_torch.c"
#include <assert.h>
pthread_mutex_t vmweave_guest_lock=PTHREAD_MUTEX_INITIALIZER;
static unsigned calls,syncs;static uint32_t seen;static int error;static size_t reply;
static int recorded;
int vmweave_guest_record_error(int e){recorded=e;return e;}
int vmweave_guest_ref(const void *p,size_t n,struct vmweave_device_ref *r){
    if(p!=(void*)4096||n>256)return 1;r->handle=7;r->offset=3;return 0;
}
int vmweave_guest_exchange(uint32_t api,const void *p,size_t n,void *out,size_t cap,size_t *got){
    const uint8_t *b=p;++calls;seen=api;
    assert(n==40&&!out&&!cap&&vmweave_get(b,8)==7&&vmweave_get(b+8,8)==3);
    assert(vmweave_get(b+32,4)==UINT32_MAX&&!vmweave_get(b+36,4));
    if(api==VMWEAVE_MEMSET_NATIVE)assert(!vmweave_get(b+24,8));
    *got=reply;return error;
}
cudaError_t cudaDeviceSynchronize(void){++syncs;return cudaSuccess;}
int main(int argc,char **argv){
    assert(argc==2);int on=!strcmp(argv[1],"on");setenv("VMWEAVE_NATIVE_MEMSET",on?"1":"0",1);
    assert(cudaMemset((void*)4096,-1,256)==0&&calls==1&&syncs==(unsigned)!on);
    assert(seen==(on?VMWEAVE_MEMSET_NATIVE:VMWEAVE_MEMSET));
    setenv("VMWEAVE_NATIVE_MEMSET",on?"0":"1",1); /* read once */
    calls=syncs=0;assert(cudaMemset((void*)4096,-1,0)==0&&calls==1&&syncs==(unsigned)!on);
    calls=syncs=0;assert(cudaMemset(NULL,-1,4)==cudaErrorInvalidValue&&!calls&&!syncs);
    assert(cudaMemset((void*)4096,-1,257)==cudaErrorInvalidValue&&!calls);
    int errors[]={801,999,700};
    for(unsigned i=0;i<3;i++){calls=syncs=0;error=errors[i];
        assert((int)cudaMemset((void*)4096,-1,4)==error&&calls==1&&!syncs);if(on)assert(recorded==error);}
    error=0;calls=syncs=0;
    assert(cudaMemsetAsync((void*)4096,-1,4,(cudaStream_t)9)==0&&calls==1&&seen==VMWEAVE_MEMSET&&!syncs);
    if(on){reply=1;calls=0;assert(cudaMemset((void*)4096,-1,4)==cudaErrorUnknown&&calls==1);}
    puts("PASS guest: routing, frozen option, bounds, errors/no replay, async unchanged, response length");
}
