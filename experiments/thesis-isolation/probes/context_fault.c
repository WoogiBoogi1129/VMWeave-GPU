/* E3: single null-address store in the test process CUDA context; no target VM address. */
#define _POSIX_C_SOURCE 200809L
#include <cuda.h>
#include <cuda_runtime_api.h>
#include "flyt_guest.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static const char ptx[]=".version 7.0\n.target sm_70\n.address_size 64\n"
".visible .entry write_value(.param .u64 p,.param .u32 v){.reg .u64 %p;.reg .u32 %v;ld.param.u64 %p,[p];ld.param.u32 %v,[v];st.global.u32 [%p],%v;ret;}\n"
".visible .entry read_value(.param .u64 p,.param .u64 out){.reg .u64 %p,%o;.reg .u32 %v;ld.param.u64 %p,[p];ld.param.u64 %o,[out];ld.global.u32 %v,[%p];st.global.u32 [%o],%v;ret;}\n"
".visible .entry null_store(){.reg .u64 %p;.reg .u32 %v;mov.u64 %p,0;mov.u32 %v,1;st.volatile.global.u32 [%p],%v;ret;}\n";
static unsigned expected[1024],observed[1024];static void *mem;static CUfunction wr,rd;
static int check(void){int e=cudaMemcpy(observed,mem,sizeof(observed),cudaMemcpyDeviceToHost);if(e)return e;return memcmp(expected,observed,sizeof(expected))?-1:0;}
static int step(void){int before=check();if(before)return before;CUdeviceptr p=(uintptr_t)mem;unsigned v=expected[0];void *a[]={&p,&v};int e=cuLaunchKernel(wr,1,1,1,1,1,1,0,0,a,0);if(!e)e=cudaDeviceSynchronize();if(!e)e=check();return e;}
int main(int argc,char **argv){
 setvbuf(stdout,0,_IOLBF,0);unsigned seed=argc>1?strtoul(argv[1],0,0):1012;int e;CUmodule mod;
 for(unsigned i=0;i<1024;i++)expected[i]=seed+i*2654435761u;
 if((e=cudaMalloc(&mem,sizeof(expected)))||(e=cudaMemcpy(mem,expected,sizeof(expected),cudaMemcpyHostToDevice))||(e=cuModuleLoadData(&mod,ptx))||(e=cuModuleGetFunction(&wr,mod,"write_value"))||(e=cuModuleGetFunction(&rd,mod,"read_value"))){printf("{\"event\":\"init_error\",\"code\":%d}\n",e);return 1;}
 unsigned char ws[]={8,4},wp[]={1,0},rs[]={8,8},rp[]={1,1};
 /* Both device addresses use the existing pointer validation path. */
 if((e=flytRegisterKernelABI(wr,2,ws,wp))||(e=flytRegisterKernelABI(rd,2,rs,rp))||(e=step())){printf("{\"event\":\"init_error\",\"code\":%d}\n",e);return 1;}
 struct flyt_device_ref ref;flyt_guest_ref(mem,sizeof(expected),&ref);
 printf("{\"event\":\"ready\",\"address\":%llu,\"handle\":%llu,\"seed\":%u}\n",(unsigned long long)(uintptr_t)mem,(unsigned long long)ref.handle,seed);
 char line[256],op[32];unsigned long long value;double seconds;
 while(fgets(line,sizeof(line),stdin)){
  op[0]=0;sscanf(line,"%31s",op);
  if(!strcmp(op,"observe")){
   seconds=0;sscanf(line,"%*s %lf",&seconds);double start=now();unsigned long n=0;
   do{double t=now();e=step();printf("{\"event\":\"request\",\"id\":%lu,\"start\":%.9f,\"latency_s\":%.9f,\"code\":%d}\n",n++,t,now()-t,e);if(e)break;}while(now()-start<seconds);
  }else if(!strcmp(op,"fault")){
   CUfunction fn;int load=cuModuleGetFunction(&fn,mod,"null_store");
   int abi=load?load:flytRegisterKernelABI(fn,0,NULL,NULL);
   printf("{\"event\":\"fault_start\"}\n");
   int launch=abi?abi:cuLaunchKernel(fn,1,1,1,1,1,1,0,0,NULL,NULL);
   int sync=cudaDeviceSynchronize();
   printf("{\"event\":\"fault\",\"load\":%d,\"abi\":%d,\"launch\":%d,\"sync\":%d}\n",load,abi,launch,sync);
  }else if(!strcmp(op,"quit"))break;
  else {printf("{\"event\":\"unsupported\"}\n");return 2;}
  printf("{\"event\":\"done\",\"op\":\"%s\"}\n",op);
 }
 return 0;
}
