/* Stage 2 functionality demonstration. Pauses are for live capture, not timing.
 * Reuses the validated integer PTX add.u32(...,19) operation; applies it to every
 * uint32_t in a single 1 MiB allocation. No PyTorch or native CUDA in the Guest.
 */
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#define ELEMENTS 262144u
#define BYTES (ELEMENTS*4u)
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
static double timestamp(void){struct timespec t;clock_gettime(CLOCK_REALTIME,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void step(const char *name,int result){
    printf("{\"event\":\"STEP\",\"operation\":\"%s\",\"api_result\":%d,\"utc_seconds\":%.9f}\n",name,result,timestamp());fflush(stdout);
}
#define CHECK(name,x) do{int e=(int)(x);step(name,e);if(e)return 10;}while(0)
static int write_array(const char *name,const uint32_t *p){FILE *f=fopen(name,"wb");if(!f)return 1;int bad=fwrite(p,1,BYTES,f)!=BYTES;return fclose(f)||bad;}
static const char ptx[]=
    ".version 7.0\n.target sm_70\n.address_size 64\n"
    ".visible .entry add19(.param .u64 ptr){\n"
    ".reg .u64 %p,%off; .reg .u32 %i,%t,%b,%r;\n"
    "ld.param.u64 %p,[ptr];mov.u32 %t,%tid.x;mov.u32 %b,%ctaid.x;"
    "mad.lo.u32 %i,%b,256,%t;mul.wide.u32 %off,%i,4;add.u64 %p,%p,%off;"
    "ld.global.u32 %r,[%p];add.u32 %r,%r,19;st.global.u32 [%p],%r;ret;}\n";
int main(int argc,char **argv){
    if(argc!=2)return 2;unsigned seed=(unsigned)strtoul(argv[1],NULL,10);
    uint32_t *input=malloc(BYTES),*reference=malloc(BYTES),*output=malloc(BYTES);
    if(!input||!reference||!output)return 3;
    for(unsigned i=0;i<ELEMENTS;i++){input[i]=seed+i;reference[i]=input[i]+19u;}
    if(write_array("stage2-input.bin",input)||write_array("stage2-reference.bin",reference))return 4;
    printf("{\"event\":\"CONDITIONS\",\"seed\":%u,\"bytes\":%u,\"elements\":%u,\"blocks\":1024,\"threads\":256,\"kernel_addend\":19,\"trace\":true,\"timing_experiment\":false}\n",seed,BYTES,ELEMENTS);fflush(stdout);
    int count=0;CHECK("cudaGetDeviceCount",cudaGetDeviceCount(&count));if(count!=1)return 5;
    void *memory=NULL;CHECK("cudaMalloc_1MiB",cudaMalloc(&memory,BYTES));sleep(4);
    CHECK("cudaMemcpy_H2D_1MiB",cudaMemcpy(memory,input,BYTES,cudaMemcpyHostToDevice));sleep(4);
    CUmodule module;CUfunction function;
    CHECK("cuModuleLoadData",cuModuleLoadData(&module,ptx));
    CHECK("cuModuleGetFunction",cuModuleGetFunction(&function,module,"add19"));
    const unsigned char sizes[]={8},pointers[]={1};
    CHECK("flytRegisterKernelABI",flytRegisterKernelABI(function,1,sizes,pointers));
    CUdeviceptr ptr=(CUdeviceptr)(uintptr_t)memory;void *params[]={&ptr};
    CHECK("cuLaunchKernel_1024x256",cuLaunchKernel(function,1024,1,1,256,1,1,0,NULL,params,NULL));
    CHECK("cudaDeviceSynchronize",cudaDeviceSynchronize());sleep(4);
    CHECK("cudaMemcpy_D2H_1MiB",cudaMemcpy(output,memory,BYTES,cudaMemcpyDeviceToHost));
    unsigned mismatches=0;for(unsigned i=0;i<ELEMENTS;i++)if(output[i]!=reference[i])mismatches++;
    if(write_array("stage2-output.bin",output))return 4;
    printf("{\"event\":\"ACCURACY\",\"checked_elements\":%u,\"checked_bytes\":%u,\"mismatches\":%u,\"criterion\":\"exact uint32 equality\"}\n",ELEMENTS,BYTES,mismatches);fflush(stdout);sleep(4);
    CHECK("cuModuleUnload",cuModuleUnload(module));CHECK("cudaFree",cudaFree(memory));
    printf("{\"event\":\"RESULT\",\"status\":\"%s\",\"checked_elements\":%u,\"checked_bytes\":%u,\"mismatches\":%u,\"utc_seconds\":%.9f}\n",mismatches?"FAIL":"PASS",ELEMENTS,BYTES,mismatches,timestamp());fflush(stdout);
    free(input);free(reference);free(output);return mismatches?1:0;
}
