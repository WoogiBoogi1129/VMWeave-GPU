#pragma once
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
