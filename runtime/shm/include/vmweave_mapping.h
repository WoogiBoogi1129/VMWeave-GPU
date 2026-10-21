#ifndef VMWEAVE_MAPPING_H
#define VMWEAVE_MAPPING_H
#include "vmweave_shm_queue.h"
struct vmweave_mapping { void *address; size_t bytes; int fd; };
/* layout.bin is a private provisioning artifact, never a native struct dump. */
int vmweave_layout_read(const char *path, struct vmweave_shm_layout *out);
int vmweave_map_file(const char *path, const struct vmweave_shm_layout *, struct vmweave_mapping *);
/* Explicit BDF only: no PCI scanning, driver binding, reset or enable writes. */
int vmweave_map_guest(const char *bdf, const struct vmweave_shm_layout *, struct vmweave_mapping *);
void vmweave_unmap(struct vmweave_mapping *);
#endif
