/* Common sequential CUDA workload. Build N, T (FLYT_TCP), S (FLYT_GUEST).
 * Timing: CLOCK_MONOTONIC; sample arrays preallocated, CSV written afterwards.
 * A real progress counter is printed once per second inside the timed loop.
 * argv: mode bytes seconds warmup_seconds sample_prefix module_file
 * module: identical source PTX; T uses offline ptxas cubin for legacy ELF parser.
 */
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#define CHECK(x) do{int e=(int)(x);if(e){fprintf(stderr,"CUDA_FAILURE %s=%d\n",#x,e);exit(10);}}while(0)
#ifdef FLYT_GUEST
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
#endif
static double clock_s(clockid_t c){struct timespec t;clock_gettime(c,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void event(const char *e,double t,unsigned long n){printf("{\"event\":\"%s\",\"utc\":%.9f,\"monotonic\":%.9f,\"elapsed\":%.9f,\"completed\":%lu}\n",e,clock_s(CLOCK_REALTIME),clock_s(CLOCK_MONOTONIC),t,n);fflush(stdout);}
/* Keep the CUDA session alive only after all windows, until collection finishes. */
static void collection_barrier(void){
 const char *release=getenv("HD_COLLECT_BARRIER");if(!release||!*release)return;
 event("ARTIFACTS_READY",0,0);double start=clock_s(CLOCK_MONOTONIC);
 while(access(release,F_OK)){if(clock_s(CLOCK_MONOTONIC)-start>180){fprintf(stderr,"collection barrier timeout\n");_Exit(11);}struct timespec pause={0,10000000};nanosleep(&pause,NULL);}
}
static int barrier_registered;
static double hc,hs,dc,ds; static int mode;static size_t bytes;static void *di,*do_;static uint32_t *src,*dst;static CUfunction fn;static unsigned reps;static void *args[3];
static void operation(double *a,double *b){
 double t=clock_s(CLOCK_MONOTONIC),u;
 if(mode==0){size_t f,z;CHECK(cudaMemGetInfo(&f,&z));u=clock_s(CLOCK_MONOTONIC);*a=u-t;*b=0;return;}
 if(mode==2||mode==5){CHECK(cudaMemcpy(di,src,bytes,cudaMemcpyHostToDevice));double v=clock_s(CLOCK_MONOTONIC);CHECK(cudaDeviceSynchronize());u=clock_s(CLOCK_MONOTONIC);hc=v-t;hs=u-v;dc=ds=0;if(mode==2){CHECK(cudaMemcpy(dst,di,bytes,cudaMemcpyDeviceToHost));v=clock_s(CLOCK_MONOTONIC);CHECK(cudaDeviceSynchronize());double w=clock_s(CLOCK_MONOTONIC);dc=v-u;ds=w-v;}*b=dc+ds;*a=u-t;return;}
 if(mode==4)CHECK(cudaMemcpy(di,src,bytes,cudaMemcpyHostToDevice));
 CHECK(cuLaunchKernel(fn,bytes/4/256,1,1,256,1,1,0,NULL,args,NULL));u=clock_s(CLOCK_MONOTONIC);
 CHECK(cudaDeviceSynchronize());if(mode==4)CHECK(cudaMemcpy(dst,do_,bytes,cudaMemcpyDeviceToHost));
 *a=u-t;*b=clock_s(CLOCK_MONOTONIC)-t;
}
static int measure(int argc,char **argv){
 if(argc!=7)return 2;
 if(!barrier_registered){if(atexit(collection_barrier))return 3;barrier_registered=1;}
 mode=!strcmp(argv[1],"query")?0:(!strcmp(argv[1],"kernel")||!strcmp(argv[1],"longkernel"))?1:!strcmp(argv[1],"h2d")?5:!strcmp(argv[1],"copy")?2:!strcmp(argv[1],"resident")?3:!strcmp(argv[1],"transfer")?4:-1;
 bytes=strtoul(argv[2],0,10);double duration=atof(argv[3]),warm=atof(argv[4]);
 if(mode<0||bytes<4096||bytes>16777216||bytes%1024||duration<=0||duration>120||warm<0)return 2;
 const size_t capacity=2000000;double *first=calloc(capacity,sizeof(double)),*second=calloc(capacity,sizeof(double));
 double *parts=calloc(capacity*4,sizeof(double));if(!first||!second||!parts)return 3;
 src=malloc(bytes);dst=malloc(bytes);if(!src||!dst)return 3;
 for(size_t i=0;i<bytes/4;i++)src[i]=(uint32_t)(i+2026);
 int count=0;CHECK(cudaGetDeviceCount(&count));if(count!=1)return 4;
 CHECK(cudaSetDevice(0));CHECK(cudaMalloc(&di,bytes));CHECK(cudaMalloc(&do_,bytes));CHECK(cudaMemcpy(di,src,bytes,cudaMemcpyHostToDevice));
 CUmodule module=0;reps=mode==1?(!strcmp(argv[1],"longkernel")?1048576:1):64;
 if(mode==1||(mode==3||mode==4)){
 FILE*f=fopen(argv[6],"rb");if(!f)return 5;fseek(f,0,SEEK_END);long len=ftell(f);rewind(f);char*code=calloc(len+1,1);if(fread(code,1,len,f)!=(size_t)len)return 5;fclose(f);
 CHECK(cuModuleLoadData(&module,code));CHECK(cuModuleGetFunction(&fn,module,"work"));free(code);
#ifdef FLYT_GUEST
 const unsigned char sizes[]={8,8,4},ptrs[]={1,1,0};CHECK(flytRegisterKernelABI(fn,3,sizes,ptrs));
#endif
 }
 CUdeviceptr in=(CUdeviceptr)(uintptr_t)di,out=(CUdeviceptr)(uintptr_t)do_;args[0]=&in;args[1]=&out;args[2]=&reps;
 size_t free_bytes,total_bytes;CHECK(cudaMemGetInfo(&free_bytes,&total_bytes));
 printf("{\"event\":\"CONDITION\",\"mode\":\"%s\",\"bytes\":%zu,\"duration_s\":%g,\"warmup_min_s\":%g,\"iterations\":%u,\"free_bytes\":%zu,\"total_bytes\":%zu}\n",argv[1],bytes,duration,warm,reps,free_bytes,total_bytes);
 event("WARMUP_START",0,0);double t=clock_s(CLOCK_MONOTONIC),a,b;unsigned long n=0;
 do{operation(&a,&b);n++;}while(clock_s(CLOCK_MONOTONIC)-t<warm||n<50);
 event("WARMUP_END",clock_s(CLOCK_MONOTONIC)-t,n);
 event("MEASUREMENT_START",0,0);t=clock_s(CLOCK_MONOTONIC);n=0;double tick=t;
 do{if(n==capacity){fprintf(stderr,"sample capacity exceeded\n");return 6;}operation(first+n,second+n);parts[4*n]=hc;parts[4*n+1]=hs;parts[4*n+2]=dc;parts[4*n+3]=ds;n++;double current=clock_s(CLOCK_MONOTONIC);if(current-tick>=1){event("TICK",current-t,n);tick=current;}}while(clock_s(CLOCK_MONOTONIC)-t<duration);
 double elapsed=clock_s(CLOCK_MONOTONIC)-t;event("MEASUREMENT_END",elapsed,n);
 CHECK(cudaMemcpy(dst,mode==1||(mode==3||mode==4)?do_:di,bytes,cudaMemcpyDeviceToHost));unsigned long bad=0;
 for(size_t i=0;i<bytes/4;i++)if(dst[i]!=(uint32_t)(src[i]+((mode==1||(mode==3||mode==4))?19*reps:0)))bad++;
 char path[1024];snprintf(path,sizeof(path),"%s.csv",argv[5]);FILE*f=fopen(path,"w");if(!f)return 7;
 fprintf(f,"sample,first_seconds,second_seconds,h2d_copy_s,h2d_sync_s,d2h_copy_s,d2h_sync_s\n");for(unsigned long i=0;i<n;i++)fprintf(f,"%lu,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f\n",i,first[i],second[i],parts[4*i],parts[4*i+1],parts[4*i+2],parts[4*i+3]);fclose(f);
 snprintf(path,sizeof(path),"%s.output.bin",argv[5]);f=fopen(path,"wb");if(!f||fwrite(dst,1,bytes,f)!=bytes)return 7;fclose(f);
 printf("{\"event\":\"RESULT\",\"status\":\"%s\",\"mode\":\"%s\",\"bytes\":%zu,\"completed\":%lu,\"elapsed_s\":%.9f,\"operations_per_s\":%.9f,\"checked_elements\":%zu,\"mismatches\":%lu}\n",bad?"FAIL":"PASS",argv[1],bytes,n,elapsed,n/elapsed,bytes/4,bad);fflush(stdout);
 if(module)CHECK(cuModuleUnload(module));CHECK(cudaFree(di));CHECK(cudaFree(do_));free(parts);free(first);free(second);free(src);free(dst);return bad?8:0;
}

int main(int argc,char **argv){
#ifdef FLYT_TCP
 extern int connection_is_local,shm_enabled,socktype;
 printf("{\"event\":\"TRANSPORT\",\"socktype\":%d,\"connection_is_local\":%d,\"shm_enabled\":%d}\n",socktype,connection_is_local,shm_enabled);fflush(stdout);
 if(socktype!=1||connection_is_local!=0)return 9;
#endif
 if(argc==7 && !strcmp(argv[1],"sweep")){
 const char *sizes[]={"4194304","8388608","12582912","16777216"};
 for(int j=0;j<4;j++){char prefix[1024];snprintf(prefix,sizeof(prefix),"%s-copy-%s",argv[5],sizes[j]);char *args[]={argv[0],"copy",(char*)sizes[j],argv[3],argv[4],prefix,argv[6]};int code=measure(7,args);if(code)return code;}return 0;}
 if((argc==8||argc==9) && !strcmp(argv[1],"batch")){
  const char *modes[]={"query","kernel","longkernel","copy","copy","copy","copy","copy"};
  const char *sizes[]={"1048576","1048576","1048576","4096","65536","1048576","4194304","16777216"};
  int shift=atoi(argv[7]);for(int j=0;j<8;j++){int i=(j+shift)%8;if(argc==9&&!(atoi(argv[8])&(1<<i)))continue;char prefix[1024];snprintf(prefix,sizeof(prefix),"%s-%s-%s",argv[5],modes[i],sizes[i]);
   char *args[]={argv[0],(char*)modes[i],(char*)sizes[i],argv[2],argv[4],prefix,argv[6]};
   int code=measure(7,args);if(code)return code;
  }return 0;
 }return measure(argc,argv);
}
