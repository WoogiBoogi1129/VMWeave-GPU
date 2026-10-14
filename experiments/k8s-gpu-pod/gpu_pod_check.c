#define _POSIX_C_SOURCE 200809L
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
#define CHECK(call) do { int rc=(int)(call); if(rc){fprintf(stderr,"{\"event\":\"CUDA_ERROR\",\"api\":\"%s\",\"code\":%d}\n",#call,rc);return 1;} } while(0)
static void event(const char *name){
 struct timespec t;clock_gettime(CLOCK_REALTIME,&t);
 printf("{\"event\":\"%s\",\"unix_seconds\":%lld.%09ld}\n",name,(long long)t.tv_sec,t.tv_nsec);
}
static const char ptx[]=".version 7.0\n.target sm_70\n.address_size 64\n"
 ".visible .entry write_value(.param .u64 ptr, .param .u32 value) {\n"
 ".reg .u64 %rd; .reg .u32 %r;\nld.param.u64 %rd, [ptr]; ld.param.u32 %r, [value];\n"
 "st.global.u32 [%rd], %r; ret; }\n";
int main(void){
 setvbuf(stdout,NULL,_IOLBF,0);event("START");
 printf("{\"event\":\"IDENTITY\",\"uid\":%u,\"gid\":%u,\"pid\":%u,\"cpu_fallback\":false}\n",getuid(),getgid(),getpid());
 int count=0;CHECK(cudaGetDeviceCount(&count));if(count!=1){fprintf(stderr,"expected one GPU; got %d\n",count);return 2;}event("GPU_ACCESS_OK");
 void *memory=NULL;CHECK(cudaMalloc(&memory,32*1024*1024));event("GPU_MEMORY_ALLOCATED_32MIB");
 unsigned input=23,output=0;CHECK(cudaMemcpy(memory,&input,sizeof(input),cudaMemcpyHostToDevice));event("HOST_TO_DEVICE_OK");
 CUmodule module;CUfunction function;CHECK(cuModuleLoadData(&module,ptx));CHECK(cuModuleGetFunction(&function,module,"write_value"));
 const unsigned char sizes[]={8,4},pointers[]={1,0};CHECK(flytRegisterKernelABI(function,2,sizes,pointers));
 CUdeviceptr ptr=(CUdeviceptr)(uintptr_t)memory;void *params[]={&ptr,&input};
 struct timespec start,now,pause={0,10000000};clock_gettime(CLOCK_MONOTONIC,&start);
 double elapsed=0,next=5;unsigned iterations=0;
 do{
  CHECK(cuLaunchKernel(function,1,1,1,1,1,1,0,NULL,params,NULL));CHECK(cuCtxSynchronize());
  if(!iterations){event("GPU_KERNEL_SYNCHRONIZED");}
  iterations++;
  nanosleep(&pause,NULL);clock_gettime(CLOCK_MONOTONIC,&now);
  elapsed=(now.tv_sec-start.tv_sec)+(now.tv_nsec-start.tv_nsec)/1e9;
  if(elapsed>=next){printf("{\"event\":\"GPU_WORK_IN_PROGRESS\",\"elapsed_seconds\":%.3f,\"iterations\":%u}\n",elapsed,iterations);next+=5;}
 }while(elapsed<30);
 CHECK(cudaMemcpy(&output,memory,sizeof(output),cudaMemcpyDeviceToHost));event("DEVICE_TO_HOST_OK");
 /* Successful API execution only: no CPU reference or numerical accuracy test. */
 CHECK(cuModuleUnload(module));CHECK(cudaFree(memory));event("GPU_RESOURCES_RELEASED");
 printf("{\"event\":\"COMPLETE\",\"status\":\"PASS\",\"elapsed_seconds\":%.3f,\"iterations\":%u,\"numerical_accuracy_test\":false}\n",elapsed,iterations);
 return 0;
}
