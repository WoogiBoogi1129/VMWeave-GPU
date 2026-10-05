#define _POSIX_C_SOURCE 200809L
#include "flyt_mapping.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void snapshot(void *dst,const void *src,size_t n){uint64_t *d=dst;const volatile uint64_t *s=src;for(size_t i=0;i<n/8;i++)d[i]=s[i];}
int main(int argc,char **argv){
 if(argc!=3)return 2;struct flyt_shm_layout l;struct flyt_mapping m={0};
 if(flyt_layout_read(argv[1],&l)||flyt_map_guest(argv[2],&l,&m))return 3;
 size_t max=16777216;if(l.slots[0].request_payload.bytes<max)return 4;
 unsigned char *bar=(unsigned char*)m.address+l.slots[0].request_payload.offset,*a=malloc(max),*b=malloc(max);
 if(!a||!b)return 5;for(size_t i=0;i<max;i++)a[i]=(unsigned char)(i*13+7);memset(b,0,max);
 for(size_t n=4194304;n<=max;n+=4194304){
  for(int mode=0;mode<4;mode++){
   memcpy(bar,a,n);double sum=0,min=1e9,max_t=0;unsigned count=0;double start=now();
   do{__asm__ __volatile__(""::"r"(b),"r"(bar):"memory");double t=now();switch(mode){case 0:memcpy(b,a,n);break;case 1:memcpy(bar,a,n);break;case 2:memcpy(b,bar,n);break;case 3:snapshot(b,bar,n);break;}__asm__ __volatile__(""::"r"(b),"r"(bar):"memory");double dt=now()-t;
    if(count>=20){sum+=dt;if(dt<min)min=dt;if(dt>max_t)max_t=dt;}count++;
   }while(now()-start<2||count<100);
   if(memcmp(a,mode==1?bar:b,n))return 6;
   printf("{\"bytes\":%zu,\"mode\":%d,\"count\":%u,\"mean_ms\":%.9f,\"min_ms\":%.9f,\"max_ms\":%.9f,\"verified\":true}\n",n,mode,count-20,sum/(count-20)*1000,min*1000,max_t*1000);fflush(stdout);
  }
 }
 free(a);free(b);flyt_unmap(&m);return 0;
}
