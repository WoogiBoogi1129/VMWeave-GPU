#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

extern int cudaMalloc(void **, size_t), cudaFree(void *);
extern int cudaMemcpy(void *, const void *, size_t, int), cudaDeviceSynchronize(void);
#define CHECK(x) do {int e=(x);if(e){fprintf(stderr,"API_ERROR %s %d\n",#x,e);exit(2);}} while(0)
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char **argv){
    if(argc!=2)return 1;
    setvbuf(stdout,NULL,_IOLBF,0);
    const size_t sizes[]={4096,1048576,16777216,67108864},max=67108864;
    unsigned char *src=malloc(max),*out=malloc(max);void *dev=NULL;
    if(!src||!out)return 1;
    for(size_t i=0;i<max;i++)src[i]=(unsigned char)(i*31+i/257);
    memset(out,0,max);CHECK(cudaMalloc(&dev,max));CHECK(cudaDeviceSynchronize());
    puts("{\"event\":\"ready\",\"workload\":\"copy\",\"host_memory\":\"pageable\"}");
    double wait=now();while(access(argv[1],F_OK)){if(now()-wait>90)return 5;struct timespec t={0,100000000};nanosleep(&t,NULL);}
    for(int si=0;si<4;si++)for(int kind=1;kind<=2;kind++){
        size_t bytes=sizes[si];void *dst=kind==1?dev:out;const void *from=kind==1?(const void*)src:dev;
        CHECK(cudaMemcpy(dev,src,bytes,1));CHECK(cudaDeviceSynchronize());
        for(int w=0;w<3;w++){CHECK(cudaMemcpy(dst,from,bytes,kind));CHECK(cudaDeviceSynchronize());}
        double ret[20000],done[20000];int n=0;double start=now();
        do {
            double t=now();CHECK(cudaMemcpy(dst,from,bytes,kind));double r=now();
            CHECK(cudaDeviceSynchronize());double d=now();ret[n]=r-t;done[n]=d-t;n++;
        }while((now()-start<2.0||n<20)&&n<20000);
        double elapsed=now()-start;if(elapsed<2.0)return 6;
        if(kind==1){CHECK(cudaMemcpy(out,dev,bytes,2));CHECK(cudaDeviceSynchronize());}
        int correct=memcmp(src,out,bytes)==0;
        printf("{\"event\":\"copy_result\",\"direction\":\"%s\",\"bytes\":%zu,\"count\":%d,\"seconds\":%.9f,\"GB_per_second\":%.9f,\"correct\":%s,\"api_return_seconds\":[",kind==1?"H2D":"D2H",bytes,n,elapsed,(double)bytes*n/elapsed/1e9,correct?"true":"false");
        for(int i=0;i<n;i++){printf("%s%.9f",i?",":"",ret[i]);}
        printf("],\"completion_seconds\":[");
        for(int i=0;i<n;i++){printf("%s%.9f",i?",":"",done[i]);}
        puts("]}");
        if(!correct)return 3;
    }
    CHECK(cudaFree(dev));free(src);free(out);puts("{\"event\":\"PASS\"}");return 0;
}
