/* Identical native/SHM workload. All reported work completes cuCtxSynchronize.
 * argv: kind mode seconds count iterations seed start_epoch reference output
 * kind: fma|integer; mode: resident|transfer. count>0 selects fixed work.
 * Reference/output '-' disables that file; integer always checks all elements.
 */
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#define ELEMENTS (2048*256)
#define BYTES (ELEMENTS*4)
#define CHECK(x) do {int err=(int)(x);if(err){fprintf(stderr,"%s: CUDA %d\n",#x,err);return 10;}}while(0)
#ifdef FLYT_GUEST
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
#endif
static double clk(clockid_t c){struct timespec t;clock_gettime(c,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void event(const char *name,unsigned long n,double elapsed){
 printf("{\"event\":\"%s\",\"utc_seconds\":%.9f,\"monotonic_seconds\":%.9f,\"completed\":%lu,\"elapsed_seconds\":%.9f}\n",name,clk(CLOCK_REALTIME),clk(CLOCK_MONOTONIC),n,elapsed);fflush(stdout);
}
int main(int argc,char **argv){
 if(argc!=10)return 2;
 int fp=!strcmp(argv[1],"fma"),transfer=!strcmp(argv[2],"transfer");
 double seconds=atof(argv[3]),scheduled=atof(argv[7]);unsigned long count=strtoul(argv[4],0,10);
 unsigned iterations=strtoul(argv[5],0,10),seed=strtoul(argv[6],0,10);
 if((!fp&&strcmp(argv[1],"integer"))||(!transfer&&strcmp(argv[2],"resident"))||seconds<0||seconds>600||iterations<1||iterations>1048576)return 2;
 uint32_t *src=malloc(BYTES),*got=malloc(BYTES),*ref=malloc(BYTES);if(!src||!got||!ref)return 3;
 for(unsigned i=0;i<ELEMENTS;i++){if(fp)((float*)src)[i]=(float)(i%257+seed%17);else src[i]=i+seed;}
 char ptx[4096];snprintf(ptx,sizeof(ptx),
 ".version 7.0\n.target sm_70\n.address_size 64\n"
 ".visible .entry work(.param .u64 src,.param .u64 dst,.param .u32 reps){\n"
 ".reg .u64 %%s,%%d,%%off; .reg .u32 %%i,%%t,%%b,%%n,%%reps,%%r; .reg .f32 %%a; .reg .pred %%q;\n"
 "ld.param.u64 %%s,[src];ld.param.u64 %%d,[dst];ld.param.u32 %%reps,[reps];"
 "mov.u32 %%t,%%tid.x;mov.u32 %%b,%%ctaid.x;mad.lo.u32 %%i,%%b,256,%%t;"
 "mul.wide.u32 %%off,%%i,4;add.u64 %%s,%%s,%%off;add.u64 %%d,%%d,%%off;mov.u32 %%n,0;\n"
 "%s\nloop: %s add.u32 %%n,%%n,1;setp.lt.u32 %%q,%%n,%%reps;@%%q bra loop;\n%s ret;}\n",
 fp?"ld.global.f32 %a,[%s];":"ld.global.u32 %r,[%s];",
 fp?"fma.rn.f32 %a,%a,0f3f800001,0f3a83126f;":"add.u32 %r,%r,19;",
 fp?"st.global.f32 [%d],%a;":"st.global.u32 [%d],%r;");
 int devices=0;CHECK(cudaGetDeviceCount(&devices));if(devices!=1)return 4;
 void *input=0,*output=0;CHECK(cudaMalloc(&input,BYTES));CHECK(cudaMalloc(&output,BYTES));
 CHECK(cudaMemcpy(input,src,BYTES,cudaMemcpyHostToDevice));
 CUmodule module;CUfunction func;CHECK(cuModuleLoadData(&module,ptx));CHECK(cuModuleGetFunction(&func,module,"work"));
#ifdef FLYT_GUEST
 const unsigned char sizes[]={8,8,4},pointers[]={1,1,0};CHECK(flytRegisterKernelABI(func,3,sizes,pointers));
#endif
 CUdeviceptr in=(CUdeviceptr)(uintptr_t)input,out=(CUdeviceptr)(uintptr_t)output;void *params[]={&in,&out,&iterations};
 event("WARMUP_START",0,0);double warm=clk(CLOCK_MONOTONIC);unsigned long nw=0;
 do{CHECK(cuLaunchKernel(func,2048,1,1,256,1,1,0,NULL,params,NULL));CHECK(cuCtxSynchronize());nw++;}while(clk(CLOCK_MONOTONIC)-warm<10||nw<50);
 event("WARMUP_END",nw,clk(CLOCK_MONOTONIC)-warm);
 while(clk(CLOCK_REALTIME)<scheduled)usleep(10000);
 double start=clk(CLOCK_MONOTONIC),last=start;unsigned long n=0;event("MEASUREMENT_START",0,0);
 do{
  if(transfer)CHECK(cudaMemcpy(input,src,BYTES,cudaMemcpyHostToDevice));
  CHECK(cuLaunchKernel(func,2048,1,1,256,1,1,0,NULL,params,NULL));CHECK(cuCtxSynchronize());
  if(transfer)CHECK(cudaMemcpy(got,output,BYTES,cudaMemcpyDeviceToHost));
  n++;double now=clk(CLOCK_MONOTONIC);
  if(now-last>=0.2){event("PROGRESS",n,now-start);last=now;}
 }while(count?n<count:clk(CLOCK_MONOTONIC)-start<seconds);
 double elapsed=clk(CLOCK_MONOTONIC)-start;event("MEASUREMENT_END",n,elapsed);
 CHECK(cudaMemcpy(got,output,BYTES,cudaMemcpyDeviceToHost));
 unsigned mismatches=0,nonfinite=0;double max_abs=0,max_rel=0;int checked=0;
 if(!fp){checked=1;for(unsigned i=0;i<ELEMENTS;i++)if(got[i]!=(uint32_t)(src[i]+19u*iterations))mismatches++;}
 else if(strcmp(argv[8],"-")){
  FILE*f=fopen(argv[8],"rb");if(!f||fread(ref,1,BYTES,f)!=BYTES)return 5;fclose(f);checked=1;
  for(unsigned i=0;i<ELEMENTS;i++){double a=((float*)got)[i],r=((float*)ref)[i];if(!isfinite(a)||!isfinite(r)){nonfinite++;continue;}double d=fabs(a-r);if(d>max_abs)max_abs=d;if(r&&d/fabs(r)>max_rel)max_rel=d/fabs(r);if(d>1e-6+1e-4*fabs(r))mismatches++;}
 }
 if(strcmp(argv[9],"-")){FILE*f=fopen(argv[9],"wb");if(!f||fwrite(got,1,BYTES,f)!=BYTES)return 6;fclose(f);}
 CHECK(cuModuleUnload(module));CHECK(cudaFree(input));CHECK(cudaFree(output));
 printf("{\"event\":\"RESULT\",\"status\":\"%s\",\"kind\":\"%s\",\"mode\":\"%s\",\"seed\":%u,\"iterations\":%u,\"completed\":%lu,\"elapsed_seconds\":%.9f,\"throughput\":%.9f,\"checked_elements\":%u,\"mismatches\":%u,\"nonfinite\":%u,\"max_absolute_error\":%.9g,\"max_relative_error\":%.9g,\"reference_generation\":%s,\"utc_seconds\":%.9f}\n",mismatches||nonfinite?"FAIL":"PASS",argv[1],argv[2],seed,iterations,n,elapsed,n/elapsed,checked?ELEMENTS:0,mismatches,nonfinite,max_abs,max_rel,checked?"false":"true",clk(CLOCK_REALTIME));fflush(stdout);
 free(src);free(got);free(ref);return mismatches||nonfinite?1:0;
}
