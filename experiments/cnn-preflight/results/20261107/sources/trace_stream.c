/* Diagnostic-only interposer: log the call and delegate to the same native
 * library observed in LD_DEBUG. Does NOT implement cuDNN remoting. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <execinfo.h>

int cudnnSetStream(void *handle, void *stream) {
    void *lib = dlopen("libcudnn.so.9", RTLD_NOLOAD | RTLD_LAZY);
    int (*next)(void *, void *) = lib ? (int (*)(void *, void *))dlsym(lib, "cudnnSetStream") : NULL;
    Dl_info info = {0};
    if (next) dladdr((void *)next, &info);
    fprintf(stderr, "CNN_API_ENTER cudnnSetStream target=%s handle_null=%d stream_null=%d\n",
            info.dli_fname ? info.dli_fname : "UNRESOLVED", handle == NULL, stream == NULL);
    void *frames[24]; int count = backtrace(frames, 24); backtrace_symbols_fd(frames, count, 2);
    fflush(stderr);
    if (!next) { fprintf(stderr, "CNN_DIAGNOSTIC_ERROR unresolved native setter\n"); exit(125); }
    int result = next(handle, stream);
    fprintf(stderr, "CNN_API_RETURN cudnnSetStream status=%d\n", result); fflush(stderr);
    dlclose(lib);
    return result;
}
