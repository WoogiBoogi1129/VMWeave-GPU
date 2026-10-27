#include "../../runtime/shm/src/async.c"
#include <assert.h>
#include <stdio.h>
static unsigned allocations,frees,creates,destroys;static int complete;
static int fail_alloc,fail_create,fail_query;
cudaError_t cudaHostAlloc(void **p,size_t n,unsigned flags){(void)flags;if(fail_alloc)return cudaErrorMemoryAllocation;*p=malloc(n);if(!*p)return cudaErrorMemoryAllocation;++allocations;return cudaSuccess;}
cudaError_t cudaFreeHost(void *p){free(p);++frees;return cudaSuccess;}
cudaError_t cudaEventCreateWithFlags(cudaEvent_t *p,unsigned flags){(void)flags;if(fail_create)return cudaErrorMemoryAllocation;*p=(cudaEvent_t)malloc(1);++creates;return *p?cudaSuccess:cudaErrorMemoryAllocation;}
cudaError_t cudaEventDestroy(cudaEvent_t e){free(e);++destroys;return cudaSuccess;}
cudaError_t cudaEventQuery(cudaEvent_t e){(void)e;if(fail_query)return cudaErrorUnknown;return complete?cudaSuccess:cudaErrorNotReady;}
cudaError_t cudaEventSynchronize(cudaEvent_t e){(void)e;complete=1;return cudaSuccess;}
int main(void){
 setenv("VMWEAVE_PINNED_POOL","1",1);assert(pooled());int a,b;assert(!pool_acquire(4097,&a));assert(stages[a].bytes==8192&&allocations==1);
 stages[a].active=1;staged_bytes+=stages[a].bytes;assert(!vmweave_async_reap()&&stages[a].active);
 assert(!pool_acquire(4097,&b)&&a!=b&&allocations==2);
 complete=1;assert(!vmweave_async_reap()&&!stages[a].active&&!staged_bytes&&!frees);
 assert(!pool_acquire(4097,&b)&&allocations==2);
 assert(pool_acquire(VMWEAVE_ASYNC_STAGING_BYTES+1,&b)==cudaErrorMemoryAllocation);
 fail_alloc=1;size_t before=pool_bytes;assert(pool_acquire(16384,&b)==cudaErrorMemoryAllocation&&pool_bytes==before);fail_alloc=0;
 fail_create=1;unsigned freed=frees;assert(pool_acquire(16384,&b)==cudaErrorMemoryAllocation&&pool_bytes==before&&frees==freed+1);fail_create=0;
 stages[a].active=1;staged_bytes+=stages[a].bytes;fail_query=1;
 assert(vmweave_async_reap()==-1&&stages[a].active&&frees==freed+1);fail_query=0;
 assert(!vmweave_async_reap()&&!staged_bytes);
 /* A whole-budget request must evict only completed small allocations. */
 assert(!pool_acquire(VMWEAVE_ASYNC_STAGING_BYTES,&b)&&pool_bytes==VMWEAVE_ASYNC_STAGING_BYTES);
 for(int i=0;i<128;i++)if(stages[i].host){assert(!stages[i].active);assert(!cudaEventDestroy(stages[i].done));assert(!cudaFreeHost(stages[i].host));}
 assert(allocations==frees&&creates==destroys);puts("PASS completed-only reuse, size class, live storage exclusion, cap, eviction, allocation/event/query failure");
}
