#include "vmweave_cuda_exec.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
static const void *expected_input;static void *expected_output;static unsigned copies;static int inject;
static uint32_t count(void*c,int32_t*v){(void)c;*v=1;return 0;}
static uint32_t device(void*c,int32_t*v){(void)c;*v=0;return 0;}
static uint32_t set(void*c,int32_t v){(void)c;return v?1:0;}
static uint32_t alloc(void*c,void**p,size_t n){(void)c;*p=malloc(n);return *p?0:2;}
static uint32_t release(void*c,void*p){(void)c;free(p);return 0;}
static uint32_t copy(void*c,void*d,const void*s,size_t n,uint32_t k){
 (void)c;copies++;if(k==VMWEAVE_COPY_HTOD)assert(s==expected_input);if(k==VMWEAVE_COPY_DTOH)assert(d==expected_output);
 if(inject)return 700;
 memcpy(d,s,n);return 0;
}
static uint32_t sync_gpu(void*c){(void)c;return 0;}
int main(int argc,char**argv){
 (void)argv;struct vmweave_cuda_backend b={count,device,set,alloc,release,copy,sync_gpu};struct vmweave_cuda_exec*s=NULL;
 struct vmweave_cuda_result r;assert(!vmweave_cuda_exec_create(&b,NULL,&s));
 struct vmweave_cuda_call c={.api_id=VMWEAVE_API_RUNTIME_MALLOC,.args.allocation_bytes=64};assert(!vmweave_cuda_exec_call(s,&c,&r));uint64_t h=r.handle;vmweave_cuda_result_release(&r);
 unsigned char input[64],output[66];for(unsigned i=0;i<64;i++)input[i]=(unsigned char)(i*13);memset(output,0xcc,sizeof(output));
 c=(struct vmweave_cuda_call){.api_id=VMWEAVE_API_RUNTIME_MEMCPY,.args.copy={.direction=VMWEAVE_COPY_HTOD,.dst={h,0},.bytes=64,.host_input=input,.host_input_bytes=64,.borrow_input=1}};
 expected_input=input;assert(!vmweave_cuda_exec_call(s,&c,&r)&&!r.api_result);vmweave_cuda_result_release(&r);
 c=(struct vmweave_cuda_call){.api_id=VMWEAVE_API_RUNTIME_MEMCPY,.args.copy={.direction=VMWEAVE_COPY_DTOH,.src={h,0},.bytes=64,.host_output=output+1,.host_output_bytes=63}};
 assert(vmweave_cuda_exec_call(s,&c,&r)==VMWEAVE_SHM_BAD_DESCRIPTOR&&copies==1);vmweave_cuda_result_release(&r);
 c.args.copy.host_output_bytes=64;expected_output=output+1;inject=argc>1;
 assert(!vmweave_cuda_exec_call(s,&c,&r));
 if(inject){
  assert(r.api_result==700&&!r.data);vmweave_cuda_result_release(&r);
  assert(vmweave_cuda_exec_check(s)==VMWEAVE_SHM_CHANNEL_CLOSED);
  uint32_t fatal=0;assert(vmweave_cuda_exec_destroy(&s,&fatal)==VMWEAVE_SHM_INTERNAL_ERROR&&fatal==700&&s);
  puts("PASS: borrowed output failure poisons context without freeing caller buffer");
  return 0; /* Existing fatal-context contract: supervisor process exit owns cleanup. */
 }
 assert(!r.api_result&&r.data_borrowed&&r.data==output+1&&r.data_bytes==64);vmweave_cuda_result_release(&r);
 assert(!memcmp(input,output+1,64)&&output[0]==0xcc&&output[65]==0xcc);
 uint32_t e;assert(!vmweave_cuda_exec_destroy(&s,&e));puts("PASS: private input/output borrowing, capacity preflight, ownership and bounds");
}
