from pathlib import Path
import shutil
B=Path('.local/rodinia-threeway-20261025');dst=B/'diagnostic-src';shutil.copytree(B/'timed-src',dst,dirs_exist_ok=True)
wrapper=r'''
static double diag_alloc=0,diag_h2d=0,diag_d2h=0,diag_sync=0,diag_compute_wait=0;
static unsigned diag_alloc_n=0,diag_h2d_n=0,diag_d2h_n=0,diag_sync_n=0;
static cudaError_t diag_malloc(void **p,size_t n){double t=experiment_now();cudaError_t e=cudaMalloc(p,n);diag_alloc+=experiment_now()-t;diag_alloc_n++;return e;}
static cudaError_t diag_copy(void *d,const void *s,size_t n,cudaMemcpyKind k){double t=experiment_now();cudaError_t e=cudaMemcpy(d,s,n,k);double elapsed=experiment_now()-t;if(k==cudaMemcpyHostToDevice){diag_h2d+=elapsed;diag_h2d_n++;}else if(k==cudaMemcpyDeviceToHost){diag_d2h+=elapsed;diag_d2h_n++;}return e;}
static cudaError_t diag_synchronize(){double t=experiment_now();cudaError_t e=cudaDeviceSynchronize();diag_sync+=experiment_now()-t;diag_sync_n++;return e;}
static cudaError_t diag_barrier(){double t=experiment_now();cudaError_t e=cudaDeviceSynchronize();diag_compute_wait+=experiment_now()-t;return e;}
static void diag_write(){FILE *f=fopen("diagnostic.json","w");if(!f)return;fprintf(f,"{\"allocation_and_lazy_initialization_seconds\":%.9f,\"h2d_seconds\":%.9f,\"d2h_after_compute_seconds\":%.9f,\"final_sync_seconds\":%.9f,\"compute_barrier_seconds\":%.9f,\"allocation_calls\":%u,\"h2d_calls\":%u,\"d2h_calls\":%u,\"sync_calls\":%u}\n",diag_alloc,diag_h2d,diag_d2h,diag_sync,diag_compute_wait,diag_alloc_n,diag_h2d_n,diag_d2h_n,diag_sync_n);fclose(f);}
#define cudaMalloc diag_malloc
#define cudaMemcpy diag_copy
#define cudaDeviceSynchronize diag_synchronize
'''
for rel in ['nw/needle.cu','lud/cuda/lud.cu']:
 p=dst/rel;s=p.read_text().replace('#include <cuda_runtime.h>','#include <cuda_runtime.h>\n'+wrapper).replace('experiment_finish();','experiment_finish();\n diag_write();');s=s.replace('CHECK_COPY(cudaMemcpy(output_itemsets,','CHECK_COPY(diag_barrier());\n CHECK_COPY(cudaMemcpy(output_itemsets,').replace('CHECK_COPY(cudaMemcpy(m, d_m,','CHECK_COPY(diag_barrier());\n CHECK_COPY(cudaMemcpy(m, d_m,');p.write_text(s)
