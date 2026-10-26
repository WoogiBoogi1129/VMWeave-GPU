// Diagnostic-only API wall-time counters. No caching or behavior changes.
#include <cuda_runtime_api.h>
#include <dlfcn.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <atomic>
static std::atomic<unsigned long long> counts[12], wall[12], nonzero[12];
static const char *names[]={"cudaMalloc","cudaFree","cudaMemcpy","cudaLaunchKernel","cudaDeviceSynchronize","cudaEventCreate","cudaEventDestroy","cudaEventRecord","cudaEventSynchronize","cudaEventElapsedTime","cudaGetLastError","cudaEventCreateWithFlags"};
static unsigned long long now(){timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (unsigned long long)t.tv_sec*1000000000+t.tv_nsec;}
static thread_local int depth;
static std::atomic<unsigned long long> copy_bytes[5];
#define WRAP(ID,NAME,ARGS,CALL) extern "C" cudaError_t NAME ARGS {using Fn=cudaError_t (*)ARGS;static auto fn=(Fn)dlsym(RTLD_NEXT,#NAME);if(!fn){fprintf(stderr,"PROFILE unresolved %s\n",#NAME);exit(90);}bool top=depth++==0;auto profile_begin_ns=top?now():0;auto rc=fn CALL;--depth;if(top){counts[ID]++;wall[ID]+=now()-profile_begin_ns;if(rc!=cudaSuccess)nonzero[ID]++;}return rc;}
WRAP(0,cudaMalloc,(void **p,size_t n),(p,n))
WRAP(1,cudaFree,(void *p),(p))
extern "C" cudaError_t cudaMemcpy(void*d,const void*s,size_t n,cudaMemcpyKind k){using Fn=cudaError_t(*)(void*,const void*,size_t,cudaMemcpyKind);static auto fn=(Fn)dlsym(RTLD_NEXT,"cudaMemcpy");if(!fn)exit(90);bool top=depth++==0;auto t=top?now():0;auto rc=fn(d,s,n,k);--depth;if(top){counts[2]++;wall[2]+=now()-t;if(rc!=cudaSuccess)nonzero[2]++;if((unsigned)k<5)copy_bytes[k]+=n;}return rc;}
WRAP(3,cudaLaunchKernel,(const void*f,dim3 g,dim3 b,void**a,size_t n,cudaStream_t s),(f,g,b,a,n,s))
WRAP(4,cudaDeviceSynchronize,(void),())
WRAP(5,cudaEventCreate,(cudaEvent_t *e),(e))
WRAP(6,cudaEventDestroy,(cudaEvent_t e),(e))
WRAP(7,cudaEventRecord,(cudaEvent_t e,cudaStream_t s),(e,s))
WRAP(8,cudaEventSynchronize,(cudaEvent_t e),(e))
WRAP(9,cudaEventElapsedTime,(float*t,cudaEvent_t a,cudaEvent_t b),(t,a,b))
WRAP(10,cudaGetLastError,(void),())
WRAP(11,cudaEventCreateWithFlags,(cudaEvent_t *e,unsigned f),(e,f))
__attribute__((destructor)) static void output(){FILE*f=fopen("api-profile.json","w");if(!f)return;fprintf(f,"{\"scope\":\"whole process including initialization and warmups; top-level wrapped APIs only; wall time includes waiting, not pure GPU kernel time\",\"apis\":{");for(int i=0;i<12;i++)fprintf(f,"%s\"%s\":{\"calls\":%llu,\"wall_ns\":%llu,\"nonzero_returns\":%llu}",i?",":"",names[i],counts[i].load(),wall[i].load(),nonzero[i].load());fprintf(f,"},\"memcpy_requested_bytes_by_kind\":[%llu,%llu,%llu,%llu,%llu]}\n",copy_bytes[0].load(),copy_bytes[1].load(),copy_bytes[2].load(),copy_bytes[3].load(),copy_bytes[4].load());fclose(f);}
