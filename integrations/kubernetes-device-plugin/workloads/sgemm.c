/* Supported ABI correctness smoke, not a performance benchmark. */
#include <stdio.h>
#include <stddef.h>
#include <math.h>
#include <stdlib.h>
#include <unistd.h>
extern int cudaMalloc(void **,size_t),cudaFree(void *),cudaMemcpy(void *,const void *,size_t,int),cudaDeviceSynchronize(void);
extern int cublasCreate_v2(void **),cublasDestroy_v2(void *);
extern int cublasSgemm_v2(void *,int,int,int,int,int,const float *,const float *,int,const float *,int,const float *,float *,int);
#define CHECK(x) do{int rc=(x);if(rc){fprintf(stderr,"%s: %d\n",#x,rc);return 1;}}while(0)
int main(int argc,char **argv){
 int idle=0;if(argc>2)return 3;if(argc==2){char *end;long n=strtol(argv[1],&end,10);if(*end||n<0||n>60)return 3;idle=(int)n;}
 float a[]={1,2,3,4},b[]={5,6,7,8},out[4]={0},expected[]={23,34,31,46};
 float *da,*db,*dc,alpha=1,beta=0;void *handle;
 CHECK(cudaMalloc((void**)&da,sizeof(a)));CHECK(cudaMalloc((void**)&db,sizeof(b)));CHECK(cudaMalloc((void**)&dc,sizeof(out)));
 if(idle)sleep((unsigned)idle);
 CHECK(cudaMemcpy(da,a,sizeof(a),1));CHECK(cudaMemcpy(db,b,sizeof(b),1));CHECK(cublasCreate_v2(&handle));
 CHECK(cublasSgemm_v2(handle,0,0,2,2,2,&alpha,da,2,db,2,&beta,dc,2));CHECK(cudaDeviceSynchronize());CHECK(cudaMemcpy(out,dc,sizeof(out),2));
 for(int i=0;i<4;i++)if(fabsf(out[i]-expected[i])>0.0001f)return 2;
 CHECK(cublasDestroy_v2(handle));CHECK(cudaFree(da));CHECK(cudaFree(db));CHECK(cudaFree(dc));
 puts("{\"status\":\"PASS\",\"scope\":\"SGEMM 2x2 full result validation\"}");return 0;
}
