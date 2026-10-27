/* Test-only PCI BAR substitute. Load ONLY into the isolated test Broker. */
#define _GNU_SOURCE
#include "vmweave_mapping.h"
#include <fcntl.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
int vmweave_map_guest(const char *bdf, const struct vmweave_shm_layout *l,
                      struct vmweave_mapping *m) {
    (void)bdf;
    const char *path=getenv("VMWEAVE_TEST_CHANNEL");
    if (!path) return -1;
    int fd=open(path,O_RDWR|O_CLOEXEC|O_NOFOLLOW);struct stat st;
    if(fd<0)return -1;
    if(fstat(fd,&st)||!S_ISREG(st.st_mode)||(uint64_t)st.st_size!=l->region_bytes){close(fd);return -1;}
    void *p=mmap(NULL,l->region_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if(p==MAP_FAILED){close(fd);return -1;}
    *m=(struct vmweave_mapping){.address=p,.bytes=l->region_bytes,.fd=fd};return 0;
}
