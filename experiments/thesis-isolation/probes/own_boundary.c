/* Own-allocation positive control only; no target address is accepted as input. */
#include <cuda.h>
#include <cuda_runtime_api.h>
#include "flyt_guest.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
static const char ptx[]=".version 7.0\n.target sm_70\n.address_size 64\n"
".visible .entry wr(.param .u64 p,.param .u32 v){.reg .u64 %p;.reg .u32 %v;ld.param.u64 %p,[p];ld.param.u32 %v,[v];st.global.u32 [%p],%v;ret;}\n"
".visible .entry rd(.param .u64 p,.param .u64 o){.reg .u64 %p,%o;.reg .u32 %v;ld.param.u64 %p,[p];ld.param.u64 %o,[o];ld.global.u32 %v,[%p];st.global.u32 [%o],%v;ret;}\n";
int main(int argc,char **argv){
 setvbuf(stdout,NULL,_IOLBF,0);unsigned seed=argc>1?strtoul(argv[1],NULL,0):123;
 unsigned expected[1024],observed[1024];for(unsigned i=0;i<1024;i++)expected[i]=seed+i*2654435761u;
 void *mem=NULL,*out=NULL;CUmodule mod;CUfunction rd,wr;int e;
 #define CHECK(x) do{if((e=(x))){printf("{\"event\":\"init_error\",\"code\":%d}\n",e);return 1;}}while(0)
 CHECK(cudaMalloc(&mem,sizeof(expected)));CHECK(cudaMalloc(&out,4096));CHECK(cudaMemcpy(mem,expected,sizeof(expected),cudaMemcpyHostToDevice));
 CHECK(cuModuleLoadData(&mod,ptx));CHECK(cuModuleGetFunction(&rd,mod,"rd"));CHECK(cuModuleGetFunction(&wr,mod,"wr"));
 unsigned char rs[]={8,8},rp[]={1,1},ws[]={8,4},wp[]={1,0};CHECK(flytRegisterKernelABI(rd,2,rs,rp));CHECK(flytRegisterKernelABI(wr,2,ws,wp));
 struct flyt_device_ref ref,oref;CHECK(flyt_guest_ref(mem,sizeof(expected),&ref));CHECK(flyt_guest_ref(out,4096,&oref));
 printf("{\"event\":\"ready\",\"address\":%llu,\"handle\":%llu,\"bytes\":4096,\"output_address\":%llu,\"output_handle\":%llu,\"seed\":%u}\n",(unsigned long long)(uintptr_t)mem,(unsigned long long)ref.handle,(unsigned long long)(uintptr_t)out,(unsigned long long)oref.handle,seed);
 char op[32];unsigned sequence=0;
 while(fgets(op,sizeof(op),stdin)){
  op[strcspn(op,"\n")]=0;if(!strcmp(op,"quit"))break;
  fprintf(stderr,"BOUNDARY_COMMAND {\"sequence\":%u,\"op\":\"%s\",\"stage\":\"begin\"}\n",++sequence,op);
  if(!strcmp(op,"read")||!strcmp(op,"write")){
   int read=!strcmp(op,"read");unsigned sentinel=0xa5a5a5a5u,value=0xdeadbeefu,result=sentinel;
   int prep=read?cudaMemcpy(out,&sentinel,4,cudaMemcpyHostToDevice):0;
   CUdeviceptr p=(uintptr_t)mem,o=(uintptr_t)out;void *args[]={&p,read?(void*)&o:(void*)&value};
   int launch=prep?prep:(int)cuLaunchKernel(read?rd:wr,1,1,1,1,1,1,0,0,args,NULL);
   int sync=launch?-1:(int)cudaDeviceSynchronize();int copy=sync?-1:(int)cudaMemcpy(&result,read?out:mem,4,cudaMemcpyDeviceToHost);
   if(!read&&!launch&&!sync&&!copy)expected[0]=value;
   printf("{\"event\":\"access\",\"op\":\"%s\",\"sequence\":%u,\"prep\":%d,\"launch\":%d,\"sync\":%d,\"copy\":%d,\"observed\":%u,\"expected\":%u}\n",op,sequence,prep,launch,sync,copy,result,expected[0]);
  }else if(!strcmp(op,"check")){
   e=cudaMemcpy(observed,mem,sizeof(observed),cudaMemcpyDeviceToHost);unsigned mismatch=0;if(!e)for(int i=0;i<1024;i++)mismatch+=expected[i]!=observed[i];
   printf("{\"event\":\"check\",\"code\":%d,\"mismatches\":%u}\n",e,mismatch);
  }else{fprintf(stderr,"unsupported command\n");return 2;}
  fprintf(stderr,"BOUNDARY_COMMAND {\"sequence\":%u,\"op\":\"%s\",\"stage\":\"end\"}\n",sequence,op);
  printf("{\"event\":\"done\",\"op\":\"%s\"}\n",op);
 }
 cudaFree(out);cudaFree(mem);return 0;
}
