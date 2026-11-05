/* Test-only transport adapter: a private file replaces the VM PCI BAR.
 * Do not install in a guest or use as production GPU access configuration. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>
int vmweave_map_guest(const char *bdf, const void *layout, void *mapping) {
    (void)bdf;
    const char *path = getenv("VMWEAVE_TEST_BACKING");
    int (*map_file)(const char *, const void *, void *) = dlsym(RTLD_NEXT, "vmweave_map_file");
    return path && map_file ? map_file(path, layout, mapping) : -1;
}
