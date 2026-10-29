#define _POSIX_C_SOURCE 200809L
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

/* Same public CUDA/cuBLAS ABI subset for direct Guest and container runs. */
extern int cudaMalloc(void **, size_t), cudaFree(void *);
extern int cudaMemcpy(void *, const void *, size_t, int), cudaDeviceSynchronize(void);
extern int cublasCreate_v2(void **), cublasDestroy_v2(void *);
extern int cublasSetMathMode(void *, int), cublasGetMathMode(void *, int *);
extern int cublasSgemm_v2(void *, int, int, int, int, int, const float *,
                        const float *, int, const float *, int, const float *, float *, int);
#define CHECK(x) do { int rc=(x); if(rc){fprintf(stderr,"API_ERROR %s %d\n",#x,rc);exit(2);} } while(0)
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static float value(uint32_t i,uint32_t seed){uint32_t x=i+seed;x=(x^(x>>16))*0x7feb352dU;x=(x^(x>>15))*0x846ca68bU;x^=x>>16;return ((int)(x&255)-128)/128.0f;}
static void validate(const float *out,int n,const char *phase){
    size_t nn=(size_t)n*n;double worst=0;unsigned bad=0;
    for(size_t i=0;i<nn;i++)if(!isfinite(out[i]))bad++;
    for(unsigned i=0;i<32;i++){
        size_t idx=((uint64_t)i*104729+17)%nn;int row=idx%n,col=idx/n;double ref=0;
        for(int k=0;k<n;k++)ref+=(double)value(row+(uint32_t)k*n,20261029)*value(k+(uint32_t)col*n,20261030);
        double err=fabs((double)out[idx]-ref);if(err>worst)worst=err;
        if(err>1e-4+2e-4*fabs(ref))bad++;
    }
    printf("{\"event\":\"correctness\",\"phase\":\"%s\",\"finite_elements\":%zu,\"fp64_reference_samples\":32,\"max_abs_error\":%.9g,\"failures\":%u}\n",phase,nn,worst,bad);
    if(bad)exit(3);
}
int main(int argc,char **argv){
    setvbuf(stdout,NULL,_IOLBF,0);
    if(argc!=5){fprintf(stderr,"usage: sgemm N seconds barrier-or-dash label\n");return 1;}
    int n=atoi(argv[1]);double duration=atof(argv[2]);if((n!=1024&&n!=4096)||duration<1||duration>30)return 1;
    size_t bytes=(size_t)n*n*sizeof(float);float *a=malloc(bytes),*b=malloc(bytes),*c=malloc(bytes);
    if(!a||!b||!c)return 1;
    for(size_t i=0;i<(size_t)n*n;i++){a[i]=value(i,20261029);b[i]=value(i,20261030);}
    float *da,*db,*dc;void *handle;int mode=-1;float alpha=1,beta=0;
    CHECK(cudaMalloc((void**)&da,bytes));CHECK(cudaMalloc((void**)&db,bytes));CHECK(cudaMalloc((void**)&dc,bytes));
    CHECK(cublasCreate_v2(&handle));CHECK(cublasSetMathMode(handle,2));CHECK(cublasGetMathMode(handle,&mode));if(mode!=2)return 4;
    CHECK(cudaMemcpy(da,a,bytes,1));CHECK(cudaMemcpy(db,b,bytes,1));
    printf("{\"event\":\"ready\",\"label\":\"%s\",\"n\":%d,\"uid\":%u,\"gid\":%u,\"matrix_bytes\":%zu,\"math_mode\":%d,\"cpu_fallback\":false}\n",argv[4],n,getuid(),getgid(),bytes,mode);
    if(argv[3][0]!='-'){double start=now();while(access(argv[3],F_OK)){if(now()-start>90)return 5;struct timespec t={0,100000000};nanosleep(&t,NULL);}}
    double warm_start=now();unsigned warm=0;
    do{CHECK(cublasSgemm_v2(handle,0,0,n,n,n,&alpha,da,n,db,n,&beta,dc,n));CHECK(cudaDeviceSynchronize());warm++;}while(warm<3||now()-warm_start<2);
    printf("{\"event\":\"warmup\",\"gemms\":%u,\"seconds\":%.9f}\n",warm,now()-warm_start);
    CHECK(cudaMemcpy(c,dc,bytes,2));validate(c,n,"warmup");
    for(int phase=0;phase<2;phase++){
        const char *name=phase?"transfer_inclusive":"resident_compute";
        printf("{\"event\":\"measurement_start\",\"phase\":\"%s\",\"unix_seconds\":%lld}\n",name,(long long)time(NULL));
        uint64_t count=0;double start=now();
        do{
            if(phase){CHECK(cudaMemcpy(da,a,bytes,1));CHECK(cudaMemcpy(db,b,bytes,1));}
            CHECK(cublasSgemm_v2(handle,0,0,n,n,n,&alpha,da,n,db,n,&beta,dc,n));CHECK(cudaDeviceSynchronize());
            if(phase)CHECK(cudaMemcpy(c,dc,bytes,2));
            count++;
        }while(now()-start<duration||count<3);
        double elapsed=now()-start;
        printf("{\"event\":\"result\",\"label\":\"%s\",\"n\":%d,\"phase\":\"%s\",\"completed_gemms\":%llu,\"seconds\":%.9f,\"gemms_per_second\":%.9f,\"gflops\":%.9f,\"ms_per_gemm\":%.9f,\"transfer_bytes_per_gemm\":%zu}\n",argv[4],n,name,(unsigned long long)count,elapsed,count/elapsed,2.0*n*n*n*count/elapsed/1e9,elapsed*1000/count,phase?3*bytes:0);
        if(!phase){CHECK(cudaMemcpy(c,dc,bytes,2));}
        validate(c,n,name);
    }
    CHECK(cublasDestroy_v2(handle));CHECK(cudaFree(da));CHECK(cudaFree(db));CHECK(cudaFree(dc));free(a);free(b);free(c);
    puts("{\"event\":\"PASS\"}");return 0;
}
