#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
extern int cudaGetDeviceCount(int*),cudaMalloc(void**,size_t),cudaFree(void*),cudaMemset(void*,int,size_t),cudaMemcpy(void*,const void*,size_t,int),cudaDeviceSynchronize(void),cudaMemGetInfo(size_t*,size_t*);
extern int cuModuleLoadData(void**,const void*),cuModuleGetFunction(void**,void*,const char*),cuLaunchKernel(void*,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,void*,void**,void**),flytRegisterKernelABI(void*,unsigned,const unsigned char*,const unsigned char*);
static void *ptr[3000],*fn;static size_t sizes[3000];static unsigned used;static size_t live;
static const char ptx[]=".version 7.0\n.target sm_70\n.address_size 64\n.visible .entry verify(.param .u64 buf,.param .u64 count){.reg .pred %p; .reg .b32 %r<8>; .reg .b64 %d<8>; ld.param.u64 %d0,[buf];ld.param.u64 %d1,[count];mov.u32 %r0,%tid.x;mov.u32 %r1,%ctaid.x;mad.lo.u32 %r2,%r1,256,%r0;add.u32 %r2,%r2,1;cvt.u64.u32 %d2,%r2;LOOP: setp.ge.u64 %p,%d2,%d1;@%p bra END;mul.lo.u64 %d3,%d2,4;add.u64 %d4,%d0,%d3;ld.global.u32 %r3,[%d4];setp.eq.u32 %p,%r3,1515870810;@%p bra NEXT;atom.global.add.u32 %r4,[%d0],1;NEXT:add.u64 %d2,%d2,65536;bra LOOP;END:ret;}\n";
static void emit(const char *op,int rc,size_t n,int verify){size_t f=0,t=0;int info=cudaMemGetInfo(&f,&t);struct timespec ts;clock_gettime(CLOCK_REALTIME,&ts);printf("{\"op\":\"%s\",\"rc\":%d,\"bytes\":%zu,\"live_requested\":%zu,\"count\":%u,\"free\":%zu,\"total\":%zu,\"info_rc\":%d,\"verify_rc\":%d,\"guest_utc\":%.9f}\n",op,rc,n,live,used,f,t,info,verify,ts.tv_sec+ts.tv_nsec/1e9);}
static int check(void *p,size_t n){int e;unsigned head=0,zero=0,wrong=0;if(n<4){unsigned char b[4];e=cudaMemcpy(b,p,n,2);for(size_t j=0;!e&&j<n;j++)if(b[j]!=0x5a)e=-10;return e;}if((e=cudaMemcpy(&head,p,4,2)))return e;if(head!=0x5a5a5a5a)return -11;if((e=cudaMemcpy(p,&zero,4,1)))return e;uint64_t a=(uintptr_t)p,c=n/4;void *args[]={&a,&c};e=cuLaunchKernel(fn,256,1,1,256,1,1,0,0,args,0);if(!e)e=cudaDeviceSynchronize();if(!e)e=cudaMemcpy(&wrong,p,4,2);if(!e&&wrong)e=-12;if(!e&&n%4){unsigned char b[4];e=cudaMemcpy(b,(char*)p+n-n%4,n%4,2);for(size_t j=0;!e&&j<n%4;j++)if(b[j]!=0x5a)e=-13;}int restore=cudaMemcpy(p,&head,4,1);return e?e:restore;}
int main(void){setvbuf(stdout,0,_IOLBF,0);int count=0,e=cudaGetDeviceCount(&count);emit("init",e,0,0);if(e||count!=1)return 2;char line[128],op[32];size_t n;unsigned repeat;
while(fgets(line,sizeof(line),stdin)){n=0;repeat=1;sscanf(line,"%31s %zu %u",op,&n,&repeat);e=0;int v=0;
if(!strcmp(op,"load")){void *m=0;e=cuModuleLoadData(&m,ptx);if(!e)e=cuModuleGetFunction(&fn,m,"verify");unsigned char z[]={8,8},p[]={1,0};if(!e)e=flytRegisterKernelABI(fn,2,z,p);}
else if(!strcmp(op,"alloc")){for(unsigned j=0;j<repeat;j++){if(used>=3000){e=-90;break;}e=cudaMalloc(&ptr[used],n);if(e)break;sizes[used]=n;live+=n;used++;e=cudaMemset(ptr[used-1],0x5a,n);if(!e)e=cudaDeviceSynchronize();if(!e&&fn)v=check(ptr[used-1],n);if(e||v)break;}}
else if(!strcmp(op,"check")){if(!fn)e=-91;else for(unsigned j=0;j<used&&!v;j++)if(ptr[j])v=check(ptr[j],sizes[j]);}
else if(!strcmp(op,"free")){if(n>=used||!ptr[n])e=-92;else{e=cudaFree(ptr[n]);if(!e){live-=sizes[n];ptr[n]=0;}}}
else if(!strcmp(op,"clear")){for(unsigned j=0;j<used;j++)if(ptr[j]){int q=cudaFree(ptr[j]);if(q)e=q;else{live-=sizes[j];ptr[j]=0;}}if(!e)used=0;}
else if(!strcmp(op,"quit")){emit(op,0,0,0);return 0;}
else if(strcmp(op,"info"))e=-93;
emit(op,e,n,v);
}return 0;}
