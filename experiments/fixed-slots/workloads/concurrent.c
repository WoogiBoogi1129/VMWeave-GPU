/* Full matrix validation and a controlled lifetime; not a throughput benchmark. */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <time.h>
#include <unistd.h>
extern int cudaMalloc(void **,size_t),cudaFree(void *),cudaMemcpy(void *,const void *,size_t,int),cudaDeviceSynchronize(void);
extern int cublasCreate_v2(void **),cublasDestroy_v2(void *);
extern int cublasSgemm_v2(void *,int,int,int,int,int,const float *,const float *,int,const float *,int,const float *,float *,int);
#define CHECK(x) do{int rc=(x);if(rc){fprintf(stderr,"%s: %d\n",#x,rc);return 1;}}while(0)
static double now(void){struct timespec t;clock_gettime(CLOCK_REALTIME,&t);return t.tv_sec+t.tv_nsec/1e9;}
int main(int argc,char **argv){
 if(argc!=4)return 3;int seed=atoi(argv[1]),seconds=atoi(argv[2]);double start=strtod(argv[3],NULL);
 if(seed<1||seed>100||seconds<1||seconds>300)return 3;
 const int n=128;size_t count=(size_t)n*n,bytes=count*sizeof(float);
 float *a=malloc(bytes),*b=calloc(count,sizeof(float)),*out=malloc(bytes);if(!a||!b||!out)return 4;
 for(size_t i=0;i<count;i++)a[i]=(float)(seed+(i%17));for(int i=0;i<n;i++)b[i*n+i]=1;
 float *da,*db,*dc,alpha=1,beta=0;void *handle;
 CHECK(cudaMalloc((void**)&da,bytes));CHECK(cudaMalloc((void**)&db,bytes));CHECK(cudaMalloc((void**)&dc,bytes));
 CHECK(cudaMemcpy(da,a,bytes,1));CHECK(cudaMemcpy(db,b,bytes,1));CHECK(cublasCreate_v2(&handle));
 setbuf(stdout,NULL);printf("{\"event\":\"ready\",\"seed\":%d,\"time\":%.6f}\n",seed,now());
 struct timespec nap={.tv_nsec=100000000};while(now()<start)nanosleep(&nap,NULL);
 double first=now(),end=first+seconds;unsigned loops=0;
 while(now()<end && access("/tmp/stop",F_OK)!=0){
  CHECK(cublasSgemm_v2(handle,0,0,n,n,n,&alpha,da,n,db,n,&beta,dc,n));CHECK(cudaDeviceSynchronize());CHECK(cudaMemcpy(out,dc,bytes,2));
  for(size_t i=0;i<count;i++)if(out[i]!=a[i]){fprintf(stderr,"mismatch seed=%d index=%zu got=%f expected=%f\n",seed,i,out[i],a[i]);return 2;}
  ++loops;if(loops%10==0)printf("{\"event\":\"progress\",\"seed\":%d,\"loops\":%u,\"time\":%.6f}\n",seed,loops,now());
  nanosleep(&nap,NULL);
 }
 CHECK(cublasDestroy_v2(handle));CHECK(cudaFree(da));CHECK(cudaFree(db));CHECK(cudaFree(dc));
 printf("{\"event\":\"pass\",\"seed\":%d,\"loops\":%u,\"elementsPerLoop\":%zu,\"start\":%.6f,\"end\":%.6f}\n",seed,loops,count,first,now());
 free(a);free(b);free(out);return loops?0:5;
}
