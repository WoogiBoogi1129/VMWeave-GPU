from pathlib import Path
import shutil,re
R=Path.cwd();B=R/'.local/rodinia-threeway-20261025';dst=B/'timed-src';shutil.copytree(R/'experiments/ai-passthrough/results/20261023-large-copy/rodinia-instrumented',dst)
header=r'''#include <time.h>
#include <stdio.h>
static double experiment_preinit_time, experiment_main_time, experiment_gpu_time;
static double experiment_now(){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void experiment_preinit(){experiment_preinit_time=experiment_now();}
__attribute__((section(".preinit_array"),used)) static void (*experiment_preinit_entry)(void)=experiment_preinit;
static void experiment_finish(){double end=experiment_now();FILE *f=fopen("timing.json","w");if(!f)return;fprintf(f,"{\"startup_seconds\":%.9f,\"gpu_phase_seconds\":%.9f,\"seconds\":%.9f}\n",experiment_main_time-experiment_preinit_time,end-experiment_gpu_time,experiment_main_time-experiment_preinit_time+end-experiment_gpu_time);fclose(f);}
'''
for rel in ['nw/needle.cu','lud/cuda/lud.cu']:
 p=dst/rel;s=p.read_text();s,n=re.subn(r'(main\s*\([^)]*\)\s*\{)',r'\1\n experiment_main_time=experiment_now();',s,count=1);assert n==1,rel
 i=s.index('CHECK_COPY(cudaMalloc(');s=s[:i]+'experiment_gpu_time=experiment_now();\n '+s[i:]
 s=s.replace('CHECK_COPY(cudaDeviceSynchronize());','CHECK_COPY(cudaDeviceSynchronize());\n experiment_finish();',1);p.write_text(header+s)
