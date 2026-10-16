/* Identical driver-API workload for native CUDA and VMWeave guest execution. */
#include <cuda.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#include <unistd.h>
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*) __attribute__((weak));
#ifdef VMWEAVE
extern int cudaFree(void *);
#endif
#define CHECK(x) do { CUresult e=(x); if(e){fprintf(stderr,"%s: %d\n",#x,e);return 1;} } while(0)
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
int main(int argc,char **argv){
 if(argc!=4 && argc!=5)return 2;
 double duration=atof(argv[1]),warmup=atof(argv[2]);int reps=atoi(argv[3]);
 if(duration<=warmup||warmup<0||duration>3600||reps<=0)return 2;
 CHECK(cuInit(0));int count;CHECK(cuDeviceGetCount(&count));if(count!=1)return 3;
 CUdevice dev;CHECK(cuDeviceGet(&dev,0));
#ifdef VMWEAVE
 /* VMWeave owns the Worker context; guests initialize through its runtime API. */
 CHECK(cudaFree(NULL));
#else
 CUcontext ctx;CHECK(cuCtxCreate_v2(&ctx,0,dev));
#endif
 int sm,threads;CHECK(cuDeviceGetAttribute(&sm,CU_DEVICE_ATTRIBUTE_MULTIPROCESSOR_COUNT,dev));
 CHECK(cuDeviceGetAttribute(&threads,CU_DEVICE_ATTRIBUTE_MAX_THREADS_PER_MULTIPROCESSOR,dev));
 CUdeviceptr ptr;CHECK(cuMemAlloc(&ptr,2048*256*4));
 char ptx[4096];snprintf(ptx,sizeof(ptx),
 ".version 7.0\n.target sm_70\n.address_size 64\n"
 ".visible .entry load(.param .u64 ptr) {\n"
 ".reg .u64 %%p,%%off; .reg .u32 %%i,%%t,%%b,%%n; .reg .f32 %%a; .reg .pred %%q;\n"
 "ld.param.u64 %%p,[ptr]; mov.u32 %%t,%%tid.x; mov.u32 %%b,%%ctaid.x; mad.lo.u32 %%i,%%b,256,%%t;\n"
 "cvt.rn.f32.u32 %%a,%%i; mov.u32 %%n,0;\n"
 "loop: fma.rn.f32 %%a,%%a,0f3f800001,0f3a83126f; add.u32 %%n,%%n,1; setp.lt.u32 %%q,%%n,%d; @%%q bra loop;\n"
 "mul.wide.u32 %%off,%%i,4; add.u64 %%p,%%p,%%off; st.global.f32 [%%p],%%a; ret; }\n",reps);
 CUmodule module;CUfunction fn;CHECK(cuModuleLoadData(&module,ptx));CHECK(cuModuleGetFunction(&fn,module,"load"));
 if(flytRegisterKernelABI){unsigned char sizes[]={8},pointers[]={1};if(flytRegisterKernelABI(fn,1,sizes,pointers))return 4;}
 printf("{\"event\":\"ready\",\"pid\":%d,\"sm\":%d,\"threads_per_sm\":%d,\"reps\":%d}\n",getpid(),sm,threads,reps);fflush(stdout);
 /* Optional coordinated wall-clock start; each Guest's measured clock offset
  * is applied by the runner. Initialization completes before this barrier. */
 if(argc==5){
  double target=atof(argv[4]);struct timespec wall;
  for(;;){clock_gettime(CLOCK_REALTIME,&wall);if(wall.tv_sec+wall.tv_nsec/1e9>=target)break;usleep(1000);}
 }
 double start=now(),measure=0,last_report=0;unsigned long launches=0;void *params[]={&ptr};
 while(now()-start<duration){
  CHECK(cuLaunchKernel(fn,2048,1,1,256,1,1,0,NULL,params,NULL));CHECK(cuCtxSynchronize());
  if(measure)launches++;else if(now()-start>=warmup){measure=now();printf("{\"event\":\"measurement_start\",\"elapsed\":%.6f}\n",measure-start);fflush(stdout);}
  if(argc==5 && now()-last_report>=1){last_report=now();printf("{\"event\":\"progress\",\"elapsed\":%.6f,\"launches\":%lu}\n",last_report-start,launches);fflush(stdout);}
 }
 double elapsed=now()-measure;
 float value;CHECK(cuMemcpyDtoH(&value,ptr,sizeof(value)));
 printf("{\"event\":\"result\",\"launches\":%lu,\"seconds\":%.6f,\"launches_per_second\":%.6f,\"sample\":%.6f}\n",launches,elapsed,launches/elapsed,value);
 CHECK(cuModuleUnload(module));CHECK(cuMemFree(ptr));
#ifndef VMWEAVE
 CHECK(cuCtxDestroy(ctx));
#endif
 return 0;
}
