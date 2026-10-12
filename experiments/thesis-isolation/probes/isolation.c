/* Interactive, one process/slot. No product changes. JSON lines are raw evidence. */
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
".visible .entry read_value(.param .u64 p,.param .u64 out){.reg .u64 %p,%o;.reg .u32 %v;ld.param.u64 %p,[p];ld.param.u64 %o,[out];ld.global.u32 %v,[%p];st.global.u32 [%o],%v;ret;}\n";
static unsigned expected[1024],observed[1024];static void *mem;static CUfunction wr,rd;
static int check(void){int e=cudaMemcpy(observed,mem,sizeof(observed),cudaMemcpyDeviceToHost);if(e)return e;return memcmp(expected,observed,sizeof(expected))?-1:0;}
static int step(void){int before=check();if(before)return before;CUdeviceptr p=(uintptr_t)mem;unsigned v=expected[0];void *a[]={&p,&v};int e=cuLaunchKernel(wr,1,1,1,1,1,1,0,0,a,0);if(!e)e=cudaDeviceSynchronize();if(!e)e=check();return e;}
int main(int argc,char **argv){
 setvbuf(stdout,0,_IOLBF,0);unsigned seed=argc>1?strtoul(argv[1],0,0):1012;int e;CUmodule mod;
 for(unsigned i=0;i<1024;i++)expected[i]=seed+i*2654435761u;
 if((e=cudaMalloc(&mem,sizeof(expected)))||(e=cudaMemcpy(mem,expected,sizeof(expected),cudaMemcpyHostToDevice))||(e=cuModuleLoadData(&mod,ptx))||(e=cuModuleGetFunction(&wr,mod,"write_value"))||(e=cuModuleGetFunction(&rd,mod,"read_value"))){printf("{\"event\":\"init_error\",\"code\":%d}\n",e);return 1;}
 unsigned char ws[]={8,4},wp[]={0,0},rs[]={8,8},rp[]={0,1};
 /* First arg is intentionally scalar: raw device VA tests bypass Guest pointer lookup. */
 if((e=flytRegisterKernelABI(wr,2,ws,wp))||(e=flytRegisterKernelABI(rd,2,rs,rp))||(e=step())){printf("{\"event\":\"init_error\",\"code\":%d}\n",e);return 1;}
 struct flyt_device_ref ref;flyt_guest_ref(mem,sizeof(expected),&ref);
 printf("{\"event\":\"ready\",\"address\":%llu,\"handle\":%llu,\"seed\":%u}\n",(unsigned long long)(uintptr_t)mem,(unsigned long long)ref.handle,seed);
 char line[256],op[32];unsigned long long value;double seconds;
 while(fgets(line,sizeof(line),stdin)){
  op[0]=0;sscanf(line,"%31s",op);
  if(!strcmp(op,"observe")){
   seconds=0;sscanf(line,"%*s %lf",&seconds);double start=now();unsigned long n=0;
   do{double t=now();e=step();printf("{\"event\":\"request\",\"id\":%lu,\"start\":%.9f,\"latency_s\":%.9f,\"code\":%d}\n",n++,t,now()-t,e);if(e)break;}while(now()-start<seconds);
  }else if(!strcmp(op,"oom")){
   value=0;sscanf(line,"%*s %llu",&value);void *buffers[1024]={0};unsigned n=0;size_t sum=sizeof(expected),f=0,total=0;const size_t chunk=16*1024*1024;cudaMemGetInfo(&f,&total);
   printf("{\"event\":\"quota\",\"free\":%zu,\"total\":%zu}\n",f,total);
   while(n<1024&&sum<=value+chunk){e=cudaMalloc(&buffers[n],chunk);if(!e){sum+=chunk;n++;e=cudaMemset(buffers[n-1],0x5a,chunk);if(!e)e=cudaDeviceSynchronize();}printf("{\"event\":\"allocation\",\"sum\":%zu,\"bytes\":%zu,\"code\":%d}\n",sum,chunk,e);if(e)break;}
   int allocation_error=e;for(unsigned i=0;i<n;i++){int z=cudaFree(buffers[i]);printf("{\"event\":\"free\",\"index\":%u,\"code\":%d}\n",i,z);}
   void *small=0;int re=cudaMalloc(&small,4096);if(!re)re=cudaFree(small);if(!re)re=step();printf("{\"event\":\"recovery\",\"oom_code\":%d,\"code\":%d,\"same_process\":true}\n",allocation_error,re);
  }else if(!strcmp(op,"rawread")||!strcmp(op,"rawwrite")){
   value=0;sscanf(line,"%*s %llu",&value);unsigned char in[52]={0};size_t got=0;unsigned result=0;int write=!strcmp(op,"rawwrite");flyt_put(in,write?1:2,4);flyt_put(in+(write?8:24),value,8);flyt_put(in+40,4,8);flyt_put(in+48,0xdeadbeef,4);
   pthread_mutex_lock(&flyt_guest_lock);e=flyt_guest_exchange(FLYT_API_RUNTIME_MEMCPY,in,write?52:48,write?NULL:&result,write?0:4,&got);pthread_mutex_unlock(&flyt_guest_lock);
   printf("{\"event\":\"access\",\"path\":\"%s\",\"target_handle\":%llu,\"code\":%d,\"observed\":%u,\"output_bytes\":%zu}\n",op,value,e,result,got);
  }else if(!strcmp(op,"read")||!strcmp(op,"write")||!strcmp(op,"fault")){
   value=0;sscanf(line,"%*s %llu",&value);CUdeviceptr target=value,out=(uintptr_t)mem;unsigned v=0xdeadbeef;void *a[]={&target,!strcmp(op,"read")?(void*)&out:(void*)&v};int launch=cuLaunchKernel(!strcmp(op,"read")?rd:wr,1,1,1,1,1,1,0,0,a,0);int sync=cudaDeviceSynchronize();unsigned result=0;int copy=cudaMemcpy(&result,mem,4,cudaMemcpyDeviceToHost);
   printf("{\"event\":\"access\",\"path\":\"%s\",\"target_address\":%llu,\"launch\":%d,\"sync\":%d,\"copy\":%d,\"observed\":%u}\n",op,value,launch,sync,copy,result);
  }else if(!strcmp(op,"check")){e=check();printf("{\"event\":\"check\",\"code\":%d}\n",e);
  }else if(!strcmp(op,"quit"))break;
  printf("{\"event\":\"done\",\"op\":\"%s\"}\n",op);
 }
 cudaFree(mem);return 0;
}
