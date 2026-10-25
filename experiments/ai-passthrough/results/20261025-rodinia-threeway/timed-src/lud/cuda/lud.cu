#include <time.h>
#include <stdio.h>
static double experiment_preinit_time, experiment_main_time, experiment_gpu_time;
static double experiment_now(){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void experiment_preinit(){experiment_preinit_time=experiment_now();}
__attribute__((section(".preinit_array"),used)) static void (*experiment_preinit_entry)(void)=experiment_preinit;
static void experiment_finish(){double end=experiment_now();FILE *f=fopen("timing.json","w");if(!f)return;fprintf(f,"{\"startup_seconds\":%.9f,\"gpu_phase_seconds\":%.9f,\"seconds\":%.9f}\n",experiment_main_time-experiment_preinit_time,end-experiment_gpu_time,experiment_main_time-experiment_preinit_time+end-experiment_gpu_time);fclose(f);}
#include <cuda_runtime.h>
#define CHECK_COPY(x) do { cudaError_t e=(x); if(e!=cudaSuccess){fprintf(stderr,"CUDA failure %d at %d\n",(int)e,__LINE__);exit(2);} } while(0)
/*
 * =====================================================================================
 *
 *       Filename:  lud.cu
 *
 *    Description:  The main wrapper for the suite
 *
 *        Version:  1.0
 *        Created:  10/22/2009 08:40:34 PM
 *       Revision:  none
 *       Compiler:  gcc
 *
 *         Author:  Liang Wang (lw2aw), lw2aw@virginia.edu
 *        Company:  CS@UVa
 *
 * =====================================================================================
 */

#include <cuda.h>
#include <stdio.h>
#include <unistd.h>
#include <getopt.h>
#include <stdlib.h>
#include <assert.h>

#include "common.h"

#ifdef RD_WG_SIZE_0_0
        #define BLOCK_SIZE RD_WG_SIZE_0_0
#elif defined(RD_WG_SIZE_0)
        #define BLOCK_SIZE RD_WG_SIZE_0
#elif defined(RD_WG_SIZE)
        #define BLOCK_SIZE RD_WG_SIZE
#else
        #define BLOCK_SIZE 16
#endif

static int do_verify = 0;

static struct option long_options[] = {
  /* name, has_arg, flag, val */
  {"input", 1, NULL, 'i'},
  {"size", 1, NULL, 's'},
  {"verify", 0, NULL, 'v'},
  {0,0,0,0}
};

extern void
lud_cuda(float *d_m, int matrix_dim);


int
main ( int argc, char *argv[] )
{
 experiment_main_time=experiment_now();
  printf("WG size of kernel = %d X %d\n", BLOCK_SIZE, BLOCK_SIZE);

  int matrix_dim = 32; /* default matrix_dim */
  int opt, option_index=0;
  func_ret_t ret;
  const char *input_file = NULL;
  float *m, *d_m, *mm;
  stopwatch sw;

  while ((opt = getopt_long(argc, argv, "::vs:i:", 
                            long_options, &option_index)) != -1 ) {
    switch(opt){
    case 'i':
      input_file = optarg;
      break;
    case 'v':
      do_verify = 1;
      break;
    case 's':
      matrix_dim = atoi(optarg);
      printf("Generate input matrix internally, size =%d\n", matrix_dim);
      // fprintf(stderr, "Currently not supported, use -i instead\n");
      // fprintf(stderr, "Usage: %s [-v] [-s matrix_size|-i input_file]\n", argv[0]);
      // exit(EXIT_FAILURE);
      break;
    case '?':
      fprintf(stderr, "invalid option\n");
      break;
    case ':':
      fprintf(stderr, "missing argument\n");
      break;
    default:
      fprintf(stderr, "Usage: %s [-v] [-s matrix_size|-i input_file]\n",
	      argv[0]);
      exit(EXIT_FAILURE);
    }
  }
  
  if ( (optind < argc) || (optind == 1)) {
    fprintf(stderr, "Usage: %s [-v] [-s matrix_size|-i input_file]\n", argv[0]);
    exit(EXIT_FAILURE);
  }

  if (input_file) {
    printf("Reading matrix from file %s\n", input_file);
    ret = create_matrix_from_file(&m, input_file, &matrix_dim);
    if (ret != RET_SUCCESS) {
      m = NULL;
      fprintf(stderr, "error create matrix from file %s\n", input_file);
      exit(EXIT_FAILURE);
    }
  } 
  else if (matrix_dim) {
    printf("Creating matrix internally size=%d\n", matrix_dim);
    ret = create_matrix(&m, matrix_dim);
    if (ret != RET_SUCCESS) {
      m = NULL;
      fprintf(stderr, "error create matrix internally size=%d\n", matrix_dim);
      exit(EXIT_FAILURE);
    }
  }


  else {
    printf("No input file specified!\n");
    exit(EXIT_FAILURE);
  }

  if (do_verify){
    printf("Before LUD\n");
    // print_matrix(m, matrix_dim);
    matrix_duplicate(m, &mm, matrix_dim);
  }

  experiment_gpu_time=experiment_now();
 CHECK_COPY(cudaMalloc((void**)&d_m, 
             matrix_dim*matrix_dim*sizeof(float)));

  /* beginning of timing point */
  stopwatch_start(&sw);
  CHECK_COPY(cudaMemcpy(d_m, m, matrix_dim*matrix_dim*sizeof(float), 
	     cudaMemcpyHostToDevice));

  lud_cuda(d_m, matrix_dim);

  CHECK_COPY(cudaMemcpy(m, d_m, matrix_dim*matrix_dim*sizeof(float), 
	     cudaMemcpyDeviceToHost));

  CHECK_COPY(cudaDeviceSynchronize());
 experiment_finish();
  FILE *full=fopen("full-output.bin","wb");size_t count=(size_t)matrix_dim*matrix_dim;
  if(!full||fwrite(m,sizeof(float),count,full)!=count)exit(4);fclose(full);
  /* end of timing point */
  stopwatch_stop(&sw);
  printf("Time consumed(ms): %lf\n", 1000*get_interval_by_sec(&sw));

  CHECK_COPY(cudaFree(d_m));


  if (do_verify){
    printf("After LUD\n");
    // print_matrix(m, matrix_dim);
    printf(">>>Verify<<<<\n");
    lud_verify(mm, m, matrix_dim); 
    free(mm);
  }

  free(m);

  return EXIT_SUCCESS;
}				/* ----------  end of function main  ---------- */
