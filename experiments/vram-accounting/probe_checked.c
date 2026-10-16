/* Validate full-buffer checker on deliberately corrupted, owned scratch data. */
#define main allocation_main
#include "probe.c"
#undef main
int main(void){
 setvbuf(stdout,0,_IOLBF,0);int count=0,e=cudaGetDeviceCount(&count);void *m=0,*p=0;size_t n=2097155;
 if(!e)e=cuModuleLoadData(&m,ptx);if(!e)e=cuModuleGetFunction(&fn,m,"verify");unsigned char z[]={8,8},refs[]={1,0};if(!e)e=flytRegisterKernelABI(fn,2,z,refs);
 if(!e)e=cudaMalloc(&p,n);if(!e)e=cudaMemset(p,0x5a,n);if(!e)e=cudaDeviceSynchronize();if(e)return 10;
 int good=check(p,n);unsigned zero=0;unsigned char tail=0;
 e=cudaMemcpy((char*)p+1048576,&zero,4,1);int middle=check(p,n);
 e|=cudaMemset(p,0x5a,n);e|=cudaDeviceSynchronize();e|=cudaMemcpy((char*)p+n-1,&tail,1,1);int end=check(p,n);
 e|=cudaMemset(p,0x5a,n);e|=cudaDeviceSynchronize();e|=cudaMemcpy(p,&zero,4,1);int head=check(p,n);
 e|=cudaMemset(p,0x5a,n);e|=cudaDeviceSynchronize();int restored=check(p,n);e|=cudaFree(p);
 int bad=e||good||middle!=-12||end!=-13||head!=-11||restored;
 printf("{\"op\":\"selftest\",\"rc\":%d,\"info_rc\":0,\"verify_rc\":0,\"good\":%d,\"middle\":%d,\"tail\":%d,\"head\":%d,\"restored\":%d}\n",bad,good,middle,end,head,restored);
 if(bad)return 11;return allocation_main();
}
