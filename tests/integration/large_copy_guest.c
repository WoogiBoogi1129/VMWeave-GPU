/* Real Guest entry points, fake broker/Worker: no GPU or device memory access. */
#include "../../runtime/shm/src/guest.c"
#include "../../runtime/shm/src/guest_async.c"
#include <assert.h>
static size_t remote_bytes,limit=VMWEAVE_COPY_CHUNK_BYTES,calls,fail_at,short_at;
static unsigned char *remote[2];
static int legacy;
static uint64_t expected_stream;
void vmweave_broker_close(void){}
int vmweave_broker_exchange(uint32_t api,const void *input,size_t n,void *output,size_t cap,size_t *got){
    *got=0;
    if(api==VMWEAVE_API_RUNTIME_MALLOC){static uint64_t handle=10;vmweave_put(output,handle++,8);*got=8;return 0;}
    if(api==VMWEAVE_API_RUNTIME_FREE)return 0;
    if(api==VMWEAVE_COPY_LIMITS){
        if(legacy)return 801;
        assert(!n&&cap==24);uint8_t *p=output;
        vmweave_put(p,1,4);vmweave_put(p+4,3,4);vmweave_put(p+8,limit,8);vmweave_put(p+16,limit,8);*got=24;return 0;
    }
    assert(api==VMWEAVE_API_RUNTIME_MEMCPY||api==VMWEAVE_ASYNC_COPY);
    ++calls;if(fail_at==calls)return 999;
    const uint8_t *p=input;size_t header=48;
    if(api==VMWEAVE_ASYNC_COPY){assert(vmweave_get(p,8)==expected_stream);p+=8;header=56;}
    unsigned k=vmweave_get(p,4);size_t bytes=vmweave_get(p+40,8);
    uint64_t dh=vmweave_get(p+8,8),sh=vmweave_get(p+24,8);
    size_t d=vmweave_get(p+16,8),s=vmweave_get(p+32,8);
    assert(k==3||bytes<=limit);assert(n==header+(k==1?bytes:0));assert(cap==(k==2?bytes:0));
    if(k!=2)assert(dh>=1&&dh<=2&&d<=remote_bytes&&bytes<=remote_bytes-d);
    if(k!=1)assert(sh>=1&&sh<=2&&s<=remote_bytes&&bytes<=remote_bytes-s);
    if(k==1)memcpy(remote[dh-1]+d,(const uint8_t*)input+header,bytes);
    else if(k==2){if(bytes)memcpy(output,remote[sh-1]+s,bytes);*got=bytes;}
    else memcpy(remote[dh-1]+d,remote[sh-1]+s,bytes);
    if(short_at==calls)*got=1;
    return 0;
}
static void reset(void){calls=fail_at=short_at=0;copy_limits_known=copy_large=0;legacy=0;}
int main(void){
    setenv("VMWEAVE_BROKER_SOCKET","mock",1);
    remote_bytes=2*VMWEAVE_COPY_CHUNK_BYTES+4096;
    unsigned char *host=malloc(remote_bytes),*out=malloc(remote_bytes);assert(host&&out);
    for(size_t i=0;i<remote_bytes;i++)host[i]=(unsigned char)(i*31+i/257);
    for(int i=0;i<2;i++){
        remote[i]=calloc(1,remote_bytes);assert(remote[i]);
        allocations[i].base=mmap(NULL,remote_bytes,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(allocations[i].base!=MAP_FAILED);
        allocations[i].bytes=allocations[i].mapped=remote_bytes;allocations[i].handle=i+1;
    }
    allocation_span=2;
    unsigned char *a=allocations[0].base,*b=allocations[1].base;
    size_t lengths[]={0,1,VMWEAVE_COPY_CHUNK_BYTES-1,VMWEAVE_COPY_CHUNK_BYTES,VMWEAVE_COPY_CHUNK_BYTES+1,16793604,2*VMWEAVE_COPY_CHUNK_BYTES,2*VMWEAVE_COPY_CHUNK_BYTES+1};
    for(int async=0;async<2;async++)for(unsigned j=0;j<sizeof(lengths)/sizeof(*lengths);j++){
        size_t n=lengths[j];reset();expected_stream=73;
        int e=async?cudaMemcpyAsync(a+17,host,n,cudaMemcpyDefault,(cudaStream_t)73):cudaMemcpy(a+17,host,n,cudaMemcpyDefault);
        assert(!e&&calls==(n?(n+limit-1)/limit:1));assert(!memcmp(remote[0]+17,host,n));
        calls=0;
        e=async?cudaMemcpyAsync(b+23,a+17,n,cudaMemcpyDeviceToDevice,(cudaStream_t)73):cudaMemcpy(b+23,a+17,n,cudaMemcpyDeviceToDevice);
        assert(!e&&calls==1);
        calls=0;memset(out,0,n);
        e=async?cudaMemcpyAsync(out,b+23,n,cudaMemcpyDeviceToHost,(cudaStream_t)73):cudaMemcpy(out,b+23,n,cudaMemcpyDeviceToHost);
        assert(!e&&!memcmp(out,host,n)&&calls==(n?(n+limit-1)/limit:1));
    }
    reset();assert(!cuMemcpyHtoD_v2((uintptr_t)a,host,16793604));assert(!cuMemcpyDtoD_v2((uintptr_t)b,(uintptr_t)a,16793604));
    assert(!cuMemcpyDtoH_v2(out,(uintptr_t)b,16793604)&&!memcmp(out,host,16793604));
    reset();expected_stream=91;
    assert(!cuMemcpyHtoDAsync_v2((uintptr_t)a,host,16793604,(CUstream)91));
    assert(!cuMemcpyDtoDAsync_v2((uintptr_t)b,(uintptr_t)a,16793604,(CUstream)91));
    assert(!cuMemcpyDtoHAsync_v2(out,(uintptr_t)b,16793604,(CUstream)91)&&!memcmp(out,host,16793604));
    reset();assert(cudaMemcpy(a+remote_bytes-1,host,2,cudaMemcpyDefault)==cudaErrorInvalidValue&&calls==0);
    assert(cudaMemcpy(a+remote_bytes-1,b,2,cudaMemcpyDeviceToDevice)==cudaErrorInvalidValue&&calls==0);
    assert(cudaMemcpy(a+1,a,VMWEAVE_COPY_CHUNK_BYTES+1,cudaMemcpyDeviceToDevice)==cudaErrorInvalidValue&&calls==0);
    assert(cudaMemcpy(out,(void*)(UINTPTR_MAX-8),16,cudaMemcpyHostToDevice)==cudaErrorInvalidValue&&calls==0);
    assert(!cudaMemcpy(out,host,remote_bytes,cudaMemcpyHostToHost)&&calls==0&&!memcmp(out,host,remote_bytes));
    reset();fail_at=2;memset(remote[0],0,remote_bytes);
    assert(cudaMemcpy(a,host,remote_bytes,cudaMemcpyHostToDevice)==cudaErrorUnknown&&calls==2);
    assert(!memcmp(remote[0],host,limit)&&remote[0][limit]==0);
    reset();short_at=1;assert(cudaMemcpy(a,host,remote_bytes,cudaMemcpyHostToDevice)==cudaErrorUnknown&&calls==1);
    reset();legacy=1;assert(cudaMemcpy(a,host,16793604,cudaMemcpyHostToDevice)==cudaErrorNotSupported&&calls==0);
    assert(!cudaMemcpy(a,host,32,cudaMemcpyHostToDevice)&&calls==1);
    reset();limit=4096;assert(!cudaMemcpy(a,host,16793604,cudaMemcpyHostToDevice)&&calls==(16793604+4095)/4096);
    assert(!memcmp(remote[0],host,16793604));
    for(int i=0;i<2;i++){munmap(allocations[i].base,remote_bytes);free(remote[i]);}memset(allocations,0,sizeof(allocations));allocation_span=0;
    void *x,*y,*z,*reuse;
    assert(!cudaMalloc(&x,4096)&&!cudaMalloc(&y,4096)&&!cudaMalloc(&z,4096)&&allocation_span==3);
    assert(device_address(z)&&!device_address(host));
    assert(!cudaFree(x)&&allocation_span==3);
    assert(!cudaMalloc(&reuse,4096)&&allocation_span==3&&device_address(reuse));
    assert(!cudaFree(z)&&allocation_span==2);
    assert(!cudaFree(y)&&allocation_span==1);
    assert(!cudaFree(reuse)&&!allocation_span&&!device_address(reuse));
    free(host);free(out);free(copy_buffer);copy_buffer=NULL;
    puts("PASS: large sync/async copies, Default, offsets, all directions, Driver wrappers, preflight bounds/overlap/overflow, partial failure, short replies, old peers, small arenas");
}
