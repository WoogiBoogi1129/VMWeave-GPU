#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

/* Observation only: pause after the first successful allocation, before warmup.
 * RTLD_NEXT resolves to the unchanged VMWeave Guest library. Later allocations
 * only forward through the same cached function pointer in Guest and Pod.
 */
int cudaMalloc(void **ptr,size_t bytes){
    static int (*next)(void **,size_t);static int observed;
    if(!next){*(void **)(&next)=dlsym(RTLD_NEXT,"cudaMalloc");if(!next)_exit(90);}
    int rc=next(ptr,bytes);
    if(!rc&&!observed++){
        const char *path=getenv("EXPERIMENT_BARRIER");if(!path)_exit(91);
        puts("{\"event\":\"ready\",\"workload\":\"rodinia\"}");fflush(stdout);
        for(int i=0;access(path,F_OK);i++){if(i>=900)_exit(92);struct timespec t={0,100000000};nanosleep(&t,NULL);}
    }
    return rc;
}
