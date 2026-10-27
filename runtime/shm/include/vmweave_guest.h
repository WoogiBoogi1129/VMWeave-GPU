#ifndef VMWEAVE_GUEST_H
#define VMWEAVE_GUEST_H
#include <pthread.h>
#include "vmweave_wire.h"
extern pthread_mutex_t vmweave_guest_lock;
int vmweave_broker_direct_enabled(void);
int vmweave_broker_copy_direct(const void *,const void *,size_t,size_t *);
int vmweave_guest_record_error(int error);
int vmweave_guest_exchange_parts(uint32_t,const void *,size_t,const void *,size_t,void *,size_t,size_t *);
/* Caller serializes these with vmweave_guest_lock. No RPC fallback. */
int vmweave_guest_exchange(uint32_t api,const void *input,size_t bytes,void *output,size_t capacity,size_t *received);
int vmweave_guest_ref(const void *pointer,size_t bytes,struct vmweave_device_ref *out);
int vmweave_guest_copy(void *dst,const void *src,size_t bytes,int kind,uint64_t stream,int async);
int vmweave_guest_transport_limits(size_t *request,size_t *response);
#endif
