#include <time.h>
#include <stdio.h>
static double experiment_preinit_time, experiment_main_time, experiment_gpu_time;
static double experiment_now(){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void experiment_preinit(){experiment_preinit_time=experiment_now();}
__attribute__((section(".preinit_array"),used)) static void (*experiment_preinit_entry)(void)=experiment_preinit;
static void experiment_finish(){double end=experiment_now();FILE *f=fopen("timing.json","w");if(!f)return;fprintf(f,"{\"startup_seconds\":%.9f,\"gpu_phase_seconds\":%.9f,\"seconds\":%.9f}\n",experiment_main_time-experiment_preinit_time,end-experiment_gpu_time,experiment_main_time-experiment_preinit_time+end-experiment_gpu_time);fclose(f);}
#include <cuda_runtime.h>

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

#define CHECK_COPY(x) do { cudaError_t e=(x); if(e!=cudaSuccess){fprintf(stderr,"CUDA failure %d at %d\n",(int)e,__LINE__);exit(2);} } while(0)
#define LIMIT -999
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "needle.h"
#include <cuda.h>
#include <sys/time.h>

// includes, kernels
#include "needle_kernel.cu"

////////////////////////////////////////////////////////////////////////////////
// declaration, forward
void runTest( int argc, char** argv);


int blosum62[24][24] = {
{ 4, -1, -2, -2,  0, -1, -1,  0, -2, -1, -1, -1, -1, -2, -1,  1,  0, -3, -2,  0, -2, -1,  0, -4},
{-1,  5,  0, -2, -3,  1,  0, -2,  0, -3, -2,  2, -1, -3, -2, -1, -1, -3, -2, -3, -1,  0, -1, -4},
{-2,  0,  6,  1, -3,  0,  0,  0,  1, -3, -3,  0, -2, -3, -2,  1,  0, -4, -2, -3,  3,  0, -1, -4},
{-2, -2,  1,  6, -3,  0,  2, -1, -1, -3, -4, -1, -3, -3, -1,  0, -1, -4, -3, -3,  4,  1, -1, -4},
{ 0, -3, -3, -3,  9, -3, -4, -3, -3, -1, -1, -3, -1, -2, -3, -1, -1, -2, -2, -1, -3, -3, -2, -4},
{-1,  1,  0,  0, -3,  5,  2, -2,  0, -3, -2,  1,  0, -3, -1,  0, -1, -2, -1, -2,  0,  3, -1, -4},
{-1,  0,  0,  2, -4,  2,  5, -2,  0, -3, -3,  1, -2, -3, -1,  0, -1, -3, -2, -2,  1,  4, -1, -4},
{ 0, -2,  0, -1, -3, -2, -2,  6, -2, -4, -4, -2, -3, -3, -2,  0, -2, -2, -3, -3, -1, -2, -1, -4},
{-2,  0,  1, -1, -3,  0,  0, -2,  8, -3, -3, -1, -2, -1, -2, -1, -2, -2,  2, -3,  0,  0, -1, -4},
{-1, -3, -3, -3, -1, -3, -3, -4, -3,  4,  2, -3,  1,  0, -3, -2, -1, -3, -1,  3, -3, -3, -1, -4},
{-1, -2, -3, -4, -1, -2, -3, -4, -3,  2,  4, -2,  2,  0, -3, -2, -1, -2, -1,  1, -4, -3, -1, -4},
{-1,  2,  0, -1, -3,  1,  1, -2, -1, -3, -2,  5, -1, -3, -1,  0, -1, -3, -2, -2,  0,  1, -1, -4},
{-1, -1, -2, -3, -1,  0, -2, -3, -2,  1,  2, -1,  5,  0, -2, -1, -1, -1, -1,  1, -3, -1, -1, -4},
{-2, -3, -3, -3, -2, -3, -3, -3, -1,  0,  0, -3,  0,  6, -4, -2, -2,  1,  3, -1, -3, -3, -1, -4},
{-1, -2, -2, -1, -3, -1, -1, -2, -2, -3, -3, -1, -2, -4,  7, -1, -1, -4, -3, -2, -2, -1, -2, -4},
{ 1, -1,  1,  0, -1,  0,  0,  0, -1, -2, -2,  0, -1, -2, -1,  4,  1, -3, -2, -2,  0,  0,  0, -4},
{ 0, -1,  0, -1, -1, -1, -1, -2, -2, -1, -1, -1, -1, -2, -1,  1,  5, -2, -2,  0, -1, -1,  0, -4},
{-3, -3, -4, -4, -2, -2, -3, -2, -2, -3, -2, -3, -1,  1, -4, -3, -2, 11,  2, -3, -4, -3, -2, -4},
{-2, -2, -2, -3, -2, -1, -2, -3,  2, -1, -1, -2, -1,  3, -3, -2, -2,  2,  7, -1, -3, -2, -1, -4},
{ 0, -3, -3, -3, -1, -2, -2, -3, -3,  3,  1, -2,  1, -1, -2, -2,  0, -3, -1,  4, -3, -2, -1, -4},
{-2, -1,  3,  4, -3,  0,  1, -1,  0, -3, -4,  0, -3, -3, -2,  0, -1, -4, -3, -3,  4,  1, -1, -4},
{-1,  0,  0,  1, -3,  3,  4, -2,  0, -3, -3,  1, -1, -3, -1,  0, -1, -3, -2, -2,  1,  4, -1, -4},
{ 0, -1, -1, -1, -2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -2,  0,  0, -2, -1, -1, -1, -1, -1, -4},
{-4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4, -4,  1}
};

double gettime() {
  struct timeval t;
  gettimeofday(&t,NULL);
  return t.tv_sec+t.tv_usec*1e-6;
}

////////////////////////////////////////////////////////////////////////////////
// Program main
////////////////////////////////////////////////////////////////////////////////
int
main( int argc, char** argv) 
{
 experiment_main_time=experiment_now();

  printf("WG size of kernel = %d \n", BLOCK_SIZE);

    runTest( argc, argv);

    return EXIT_SUCCESS;
}

void usage(int argc, char **argv)
{
	fprintf(stderr, "Usage: %s <max_rows/max_cols> <penalty> \n", argv[0]);
	fprintf(stderr, "\t<dimension>  - x and y dimensions\n");
	fprintf(stderr, "\t<penalty> - penalty(positive integer)\n");
	exit(1);
}

void runTest( int argc, char** argv) 
{
    int max_rows, max_cols, penalty;
    int *input_itemsets, *output_itemsets, *referrence;
	int *matrix_cuda,  *referrence_cuda;
	int size;
	
    
    // the lengths of the two sequences should be able to divided by 16.
	// And at current stage  max_rows needs to equal max_cols
	if (argc == 3)
	{
		max_rows = atoi(argv[1]);
		max_cols = atoi(argv[1]);
		penalty = atoi(argv[2]);
	}
    else{
	usage(argc, argv);
    }
	
	if(atoi(argv[1])%16!=0){
	fprintf(stderr,"The dimension values must be a multiple of 16\n");
	exit(1);
	}
	

	max_rows = max_rows + 1;
	max_cols = max_cols + 1;
	referrence = (int *)malloc( max_rows * max_cols * sizeof(int) );
    input_itemsets = (int *)malloc( max_rows * max_cols * sizeof(int) );
	output_itemsets = (int *)malloc( max_rows * max_cols * sizeof(int) );
	

	if (!input_itemsets)
		fprintf(stderr, "error: can not allocate memory");

    srand ( 7 );
	
	
    for (int i = 0 ; i < max_cols; i++){
		for (int j = 0 ; j < max_rows; j++){
			input_itemsets[i*max_cols+j] = 0;
		}
	}
	
	printf("Start Needleman-Wunsch\n");
	
	for( int i=1; i< max_rows ; i++){    //please define your own sequence. 
       input_itemsets[i*max_cols] = rand() % 10 + 1;
	}
    for( int j=1; j< max_cols ; j++){    //please define your own sequence.
       input_itemsets[j] = rand() % 10 + 1;
	}


	for (int i = 1 ; i < max_cols; i++){
		for (int j = 1 ; j < max_rows; j++){
		referrence[i*max_cols+j] = blosum62[input_itemsets[i*max_cols]][input_itemsets[j]];
		}
	}

    for( int i = 1; i< max_rows ; i++)
       input_itemsets[i*max_cols] = -i * penalty;
	for( int j = 1; j< max_cols ; j++)
       input_itemsets[j] = -j * penalty;


    size = max_cols * max_rows;
	experiment_gpu_time=experiment_now();
 CHECK_COPY(cudaMalloc((void**)& referrence_cuda, sizeof(int)*size));
	CHECK_COPY(cudaMalloc((void**)& matrix_cuda, sizeof(int)*size));
	
	CHECK_COPY(cudaMemcpy(referrence_cuda, referrence, sizeof(int) * size, cudaMemcpyHostToDevice));
	CHECK_COPY(cudaMemcpy(matrix_cuda, input_itemsets, sizeof(int) * size, cudaMemcpyHostToDevice));

    dim3 dimGrid;
	dim3 dimBlock(BLOCK_SIZE, 1);
	int block_width = ( max_cols - 1 )/BLOCK_SIZE;

	printf("Processing top-left matrix\n");
	//process top-left matrix
	for( int i = 1 ; i <= block_width ; i++){
		dimGrid.x = i;
		dimGrid.y = 1;
		needle_cuda_shared_1<<<dimGrid, dimBlock>>>(referrence_cuda, matrix_cuda
		                                      ,max_cols, penalty, i, block_width); 
	}
	printf("Processing bottom-right matrix\n");
    //process bottom-right matrix
	for( int i = block_width - 1  ; i >= 1 ; i--){
		dimGrid.x = i;
		dimGrid.y = 1;
		needle_cuda_shared_2<<<dimGrid, dimBlock>>>(referrence_cuda, matrix_cuda
		                                      ,max_cols, penalty, i, block_width); 
	}


    CHECK_COPY(diag_barrier());
 CHECK_COPY(cudaMemcpy(output_itemsets, matrix_cuda, sizeof(int) * size, cudaMemcpyDeviceToHost));
    CHECK_COPY(cudaDeviceSynchronize());
 experiment_finish();
 diag_write();
    for(int i=1;i<max_rows;i++)for(int j=1;j<max_cols;j++){
        int diagonal=input_itemsets[(i-1)*max_cols+j-1]+referrence[i*max_cols+j];
        int top=input_itemsets[(i-1)*max_cols+j]-penalty;
        int left=input_itemsets[i*max_cols+j-1]-penalty;
        input_itemsets[i*max_cols+j]=diagonal>top?(diagonal>left?diagonal:left):(top>left?top:left);
    }
    if(memcmp(input_itemsets,output_itemsets,sizeof(int)*size)){fprintf(stderr,"NW CPU reference mismatch\n");exit(3);}
    FILE *full=fopen("full-output.bin","wb");if(!full||fwrite(output_itemsets,sizeof(int),size,full)!=(size_t)size)exit(4);fclose(full);
    printf("NW CPU reference PASS, bytes=%zu\n",sizeof(int)*(size_t)size);

	
//#define TRACEBACK
#ifdef TRACEBACK
	
	FILE *fpo = fopen("result.txt","w");
	fprintf(fpo, "print traceback value GPU:\n");
    
	for (int i = max_rows - 2,  j = max_rows - 2; i>=0, j>=0;){
		int nw, n, w, traceback;
		if ( i == max_rows - 2 && j == max_rows - 2 )
			fprintf(fpo, "%d ", output_itemsets[ i * max_cols + j]); //print the first element
		if ( i == 0 && j == 0 )
           break;
		if ( i > 0 && j > 0 ){
			nw = output_itemsets[(i - 1) * max_cols + j - 1];
		    w  = output_itemsets[ i * max_cols + j - 1 ];
            n  = output_itemsets[(i - 1) * max_cols + j];
		}
		else if ( i == 0 ){
		    nw = n = LIMIT;
		    w  = output_itemsets[ i * max_cols + j - 1 ];
		}
		else if ( j == 0 ){
		    nw = w = LIMIT;
            n  = output_itemsets[(i - 1) * max_cols + j];
		}
		else{
		}

		//traceback = maximum(nw, w, n);
		int new_nw, new_w, new_n;
		new_nw = nw + referrence[i * max_cols + j];
		new_w = w - penalty;
		new_n = n - penalty;
		
		traceback = maximum(new_nw, new_w, new_n);
		if(traceback == new_nw)
			traceback = nw;
		if(traceback == new_w)
			traceback = w;
		if(traceback == new_n)
            traceback = n;
			
		fprintf(fpo, "%d ", traceback);

		if(traceback == nw )
		{i--; j--; continue;}

        else if(traceback == w )
		{j--; continue;}

        else if(traceback == n )
		{i--; continue;}

		else
		;
	}
	
	fclose(fpo);

#endif

	CHECK_COPY(cudaFree(referrence_cuda));
	CHECK_COPY(cudaFree(matrix_cuda));

	free(referrence);
	free(input_itemsets);
	free(output_itemsets);
	
}

