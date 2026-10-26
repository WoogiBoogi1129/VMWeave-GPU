from pathlib import Path
import shutil,re
R=Path.cwd(); B=R/'.local/rodinia-steady-20261026'; O=R/'experiments/ai-passthrough/results/20261026-rodinia-steady'
S=O/'src';shutil.copytree(B/'rodinia_3.1/cuda',S,dirs_exist_ok=True)
for p in list(S.rglob('*')):
 if p.is_file() and p.suffix not in ('.cu','.c','.h','.cpp') and p.name not in ('run','README'):p.unlink()
header=r'''#pragma once
#include <cuda_runtime.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
static double exp_start,exp_elapsed;
static int exp_iteration;
static double exp_now(){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void exp_check(cudaError_t e){if(e!=cudaSuccess){fprintf(stderr,"CUDA error %d: %s\n",(int)e,cudaGetErrorString(e));exit(2);}}
static void exp_begin(){exp_check(cudaDeviceSynchronize());exp_start=exp_now();}
static void exp_end(){exp_check(cudaGetLastError());exp_check(cudaDeviceSynchronize());exp_elapsed+=exp_now()-exp_start;}
static void exp_dump(const void*p,size_t n){char name[80];snprintf(name,sizeof(name),"output-%02d.bin",exp_iteration);FILE*f=fopen(name,"wb");if(!f||fwrite(p,1,n,f)!=n)exit(3);fclose(f);}
'''
(S/'experiment.h').write_text(header)
wrapper=r'''
int main(int argc,char**argv){int count=getenv("EXPERIMENT_REPEATS")?atoi(getenv("EXPERIMENT_REPEATS")):2;
 if(count<1||count>10)return 4;
 double init=exp_now();exp_check(cudaFree(0));exp_check(cudaDeviceSynchronize());
 fprintf(stderr,"EXPERIMENT_INIT %.9f\n",exp_now()-init);
 for(exp_iteration=0;exp_iteration<count+2;exp_iteration++){
 optind=0;exp_elapsed=0;int rc=experiment_main(argc,argv);if(rc)return rc;
 printf("EXPERIMENT_SAMPLE {\"iteration\":%d,\"warmup\":%s,\"seconds\":%.9f}\n",exp_iteration,exp_iteration<2?"true":"false",exp_elapsed);fflush(stdout);
 }return 0;}
'''
for rel in ['nw/needle.cu','lud/cuda/lud.cu','srad/srad_v2/srad.cu','streamcluster/streamcluster_cuda_cpu.cpp']:
 p=S/rel;s=p.read_text();s=re.sub(r'\bmain\s*\(', 'experiment_main(',s,count=1)
 if rel.startswith('nw'):
  s=s.replace('cudaMalloc((void**)& referrence_cuda','exp_begin();\n cudaMalloc((void**)& referrence_cuda',1)
  marker='cudaMemcpy(output_itemsets, matrix_cuda, sizeof(int) * size, cudaMemcpyDeviceToHost);'
  assert marker in s;s=s.replace(marker,marker+'\nexp_end();exp_dump(output_itemsets,sizeof(int)*size);')
 elif rel.startswith('lud'):
  s=s.replace('cudaMalloc((void**)&d_m','exp_begin();\n cudaMalloc((void**)&d_m',1)
  marker='/* end of timing point */';s=s.replace(marker,'exp_end();exp_dump(m,matrix_dim*matrix_dim*sizeof(float));\n'+marker)
 elif rel.startswith('srad'):
  # Generate deterministic CPU input before timing GPU allocations.
  start=s.index('\tprintf("Randomizing');end=s.index('\tprintf("Start the SRAD',start)
  prep=s[start:end];s=s[:start]+s[end:];i=s.index('\t//Allocate device memory');s=s[:i]+prep+'\nexp_begin();\n'+s[i:]
  s=s.replace('cudaThreadSynchronize();','exp_end();exp_dump(J,sizeof(float)*size_I);')
 else:
  s=s.replace('  streamCluster(stream,','  exp_begin();\n  streamCluster(stream,',1)
  s=s.replace('  outcenterIDs( &centers, centerIDs, outfile);','  exp_end();\n  outcenterIDs( &centers, centerIDs, outfile);\n  free(switch_membership);free(is_center);free(center_table);\n  free(points.p);free(centers.p);free(block);free(centerBlock);free(centerIDs);')
  s=s.replace('size_t numRead  = stream->read(block, dim, chunksize );','exp_end();\n    size_t numRead  = stream->read(block, dim, chunksize );\n    exp_begin();')
  s=s.replace('  delete stream;','  delete stream;delete[] outfilename;delete[] infilename;')
 p.write_text('#include "experiment.h"\n'+s+wrapper)
p=S/'lud/common/common.c';p.write_text(p.read_text().replace('srand(time(NULL))','srand(7)'))
p=S/'streamcluster/streamcluster_cuda.cu';p.write_text(p.read_text().replace('void freeDevMem()\n{','void freeDevMem()\n{\n iter=0;'))
shutil.copy2(B/'rodinia_3.1/LICENSE',O/'RODINIA-LICENSE')
