#ifndef VMWEAVE_OWNER_H
#define VMWEAVE_OWNER_H
#include <stdint.h>
#include <stddef.h>
struct vmweave_owner;
int vmweave_owner_open(struct vmweave_owner **);
int vmweave_owner_exchange(struct vmweave_owner *,uint32_t,const void *,size_t,const void *,size_t,void *,size_t,size_t *);
int vmweave_owner_limits(struct vmweave_owner *,size_t *,size_t *);
int vmweave_owner_close(struct vmweave_owner *);
#endif
