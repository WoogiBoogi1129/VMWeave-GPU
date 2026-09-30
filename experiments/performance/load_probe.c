/* Identical integer PTX work for direct CUDA and VMWeave. Complete output check.
 * args: seconds warmup reps count start_utc prefix module
 * count>0 adds a fixed-work window after the time window. */
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#define CHECK(x) do{int e=(int)(x);if(e){fprintf(stderr,"CUDA_FAILURE %s=%d\n",#x,e);exit(10);}}while(0)
#ifdef FLYT_GUEST
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
#endif
static double clk(clockid_t c){struct timespec t;clock_gettime(c,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void emit(const char*event,const char*phase,double elapsed,unsigned long count){
 printf("{\"event\":\"%s\",\"phase\":\"%s\",\"utc\":%.9f,\"elapsed\":%.9f,\"completed\":%lu}\n",event,phase,clk(CLOCK_REALTIME),elapsed,count);fflush(stdout);
}
int main(int argc,char**argv){
 if(argc!=8)return 2;
 double seconds=atof(argv[1]),warmup=atof(argv[2]),start=atof(argv[5]);unsigned reps=strtoul(argv[3],0,10);unsigned long fixed=strtoul(argv[4],0,10);
 if(seconds<=0||seconds>600||warmup<0||warmup>120||!reps)return 2;
 const size_t bytes=2097152,capacity=2000000;
 double *ends=calloc(capacity,sizeof(double)),*lat=calloc(capacity,sizeof(double));
 uint32_t *src=malloc(bytes),*dst=malloc(bytes);if(!ends||!lat||!src||!dst)return 3;
 for(size_t i=0;i<bytes/4;i++)src[i]=(uint32_t)(i+2026);
 int devices;CHECK(cudaGetDeviceCount(&devices));if(devices!=1)return 4;
 CHECK(cudaSetDevice(0));void *di,*do_;CHECK(cudaMalloc(&di,bytes));CHECK(cudaMalloc(&do_,bytes));CHECK(cudaMemcpy(di,src,bytes,cudaMemcpyHostToDevice));
 FILE*f=fopen(argv[7],"rb");if(!f)return 5;fseek(f,0,SEEK_END);long length=ftell(f);rewind(f);char*code=calloc(length+1,1);if(fread(code,1,length,f)!=(size_t)length)return 5;fclose(f);
 CUmodule module;CUfunction fn;CHECK(cuModuleLoadData(&module,code));CHECK(cuModuleGetFunction(&fn,module,"work"));free(code);
#ifdef FLYT_GUEST
 const unsigned char sizes[]={8,8,4},ptrs[]={1,1,0};CHECK(flytRegisterKernelABI(fn,3,sizes,ptrs));
#endif
 CUdeviceptr in=(CUdeviceptr)(uintptr_t)di,out=(CUdeviceptr)(uintptr_t)do_;void*args[]={&in,&out,&reps};
 emit("WARMUP_START","warmup",0,0);double t=clk(CLOCK_MONOTONIC);unsigned long n=0;
 do{CHECK(cuLaunchKernel(fn,bytes/1024,1,1,256,1,1,0,NULL,args,NULL));CHECK(cudaDeviceSynchronize());n++;}while(clk(CLOCK_MONOTONIC)-t<warmup||n<10);
 emit("WARMUP_END","warmup",clk(CLOCK_MONOTONIC)-t,n);
 if(start>0){emit("WAIT_START","waiting",0,0);while(clk(CLOCK_REALTIME)<start)usleep(1000);}
 for(int window=0;window<(fixed?2:1);window++){
  const char*phase=window?"fixed":"timed";n=0;emit("MEASUREMENT_START",phase,0,0);double utc=clk(CLOCK_REALTIME);t=clk(CLOCK_MONOTONIC);double tick=t;
  do{
   if(n>=capacity)return 6;
   double a=clk(CLOCK_MONOTONIC);CHECK(cuLaunchKernel(fn,bytes/1024,1,1,256,1,1,0,NULL,args,NULL));CHECK(cudaDeviceSynchronize());double b=clk(CLOCK_MONOTONIC);
   lat[n]=b-a;ends[n]=b-t;n++;
   if(b-tick>=1){printf("{\"event\":\"TICK\",\"phase\":\"%s\",\"utc\":%.9f,\"elapsed\":%.9f,\"completed\":%lu,\"last_latency_s\":%.9f}\n",phase,clk(CLOCK_REALTIME),b-t,n,b-a);fflush(stdout);tick=b;}
  }while(window?n<fixed:clk(CLOCK_MONOTONIC)-t<seconds);
  double elapsed=clk(CLOCK_MONOTONIC)-t;emit("MEASUREMENT_END",phase,elapsed,n);
  CHECK(cudaMemcpy(dst,do_,bytes,cudaMemcpyDeviceToHost));unsigned long bad=0;
  for(size_t i=0;i<bytes/4;i++)if(dst[i]!=(uint32_t)(src[i]+19u*reps))bad++;
  char path[1024];snprintf(path,sizeof(path),"%s-%s.csv",argv[6],phase);f=fopen(path,"w");if(!f)return 7;
  fprintf(f,"sample,end_elapsed_s,latency_s\n");for(unsigned long i=0;i<n;i++)fprintf(f,"%lu,%.9f,%.9f\n",i,ends[i],lat[i]);fclose(f);
  printf("{\"event\":\"RESULT\",\"status\":\"%s\",\"phase\":\"%s\",\"utc_start\":%.9f,\"reps\":%u,\"bytes\":%zu,\"completed\":%lu,\"elapsed_s\":%.9f,\"operations_per_s\":%.9f,\"checked_elements\":%zu,\"mismatches\":%lu}\n",bad?"FAIL":"PASS",phase,utc,reps,bytes,n,elapsed,n/elapsed,bytes/4,bad);fflush(stdout);
  if(bad)return 8;
 }
 CHECK(cuModuleUnload(module));CHECK(cudaFree(di));CHECK(cudaFree(do_));return 0;
}
