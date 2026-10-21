#ifndef VMWEAVE_ASYNC_H
#define VMWEAVE_ASYNC_H
#include "vmweave_wire.h"
enum {
 VMWEAVE_STREAM_CREATE=0x2001,VMWEAVE_STREAM_DESTROY,VMWEAVE_STREAM_SYNC,VMWEAVE_STREAM_QUERY,
 VMWEAVE_EVENT_CREATE=0x2010,VMWEAVE_EVENT_DESTROY,VMWEAVE_EVENT_RECORD,VMWEAVE_EVENT_SYNC,VMWEAVE_EVENT_QUERY,
 VMWEAVE_ASYNC_COPY=0x2020,VMWEAVE_MODULE_LOAD=0x2030,VMWEAVE_MODULE_UNLOAD,VMWEAVE_FUNCTION_GET,VMWEAVE_KERNEL_LAUNCH
};
int vmweave_async_dispatch(struct vmweave_cuda_session *,const struct vmweave_shm_request *,struct vmweave_shm_response *);
int vmweave_async_reap(void);
int vmweave_async_close(void);
#endif
