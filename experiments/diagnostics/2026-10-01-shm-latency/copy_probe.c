/* Isolated normal-RAM copy diagnostic; not an IVSHMEM BAR measurement. */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
__attribute__((noinline)) static void snapshot(void *dst,const void *src,size_t n){
 unsigned char *d=dst;const volatile unsigned char *s=src;for(size_t i=0;i<n;i++)d[i]=s[i];
}
__attribute__((noinline)) static void bulk(void *dst,const void *src,size_t n){memcpy(dst,src,n);}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char **argv){
 if(argc!=3)return 1;
 size_t n=strtoul(argv[2],NULL,10);if(n>16777216||!n)return 1;
 void (*copy)(void*,const void*,size_t)=!strcmp(argv[1],"snapshot")?snapshot:bulk;
 unsigned char *src=malloc(n),*dst=malloc(n);if(!src||!dst)return 2;memset(src,0x5a,n);memset(dst,0,n);
 for(int i=0;i<20;i++)copy(dst,src,n);
 double t=now();unsigned count=0;do{copy(dst,src,n);count++;}while(now()-t<.3);double elapsed=now()-t;
 if(memcmp(src,dst,n))return 3;
 printf("{\"method\":\"%s\",\"bytes\":%zu,\"count\":%u,\"mean_us\":%.6f,\"gib_s\":%.6f,\"validation\":\"PASS\"}\n",argv[1],n,count,elapsed/count*1e6,n*(double)count/elapsed/1073741824.);
 free(src);free(dst);return 0;
}
