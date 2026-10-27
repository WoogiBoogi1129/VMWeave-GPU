#ifndef VMWEAVE_SESSION_IPC_H
#define VMWEAVE_SESSION_IPC_H
#include <stddef.h>
#include <stdint.h>
/* Private host IPC only. Never expose this memfd to the VM. */
#define VMWEAVE_IPC_ARENA_BYTES (2u*(16u*1024u*1024u+4096u))
#define VMWEAVE_IPC_HALF (VMWEAVE_IPC_ARENA_BYTES/2u)
struct vmweave_ipc { unsigned char *arena; int fd,request_event,response_event; uint64_t sequence; };
#define VMWEAVE_IPC_INIT { .fd=-1, .request_event=-1, .response_event=-1 }
int vmweave_ipc_enable_events(struct vmweave_ipc *);
int vmweave_ipc_request_wait_fd(const struct vmweave_ipc *,int);
int vmweave_ipc_create(struct vmweave_ipc *);
int vmweave_ipc_map(struct vmweave_ipc *,int);
void vmweave_ipc_close(struct vmweave_ipc *);
int vmweave_ipc_handshake(int,int);
int vmweave_ipc_call(struct vmweave_ipc *,int,uint32_t,const void *,size_t,void *,size_t,uint32_t *,uint32_t *,uint32_t *,size_t *);
/* child receive returns 0 on success; failure terminates the session. */
int vmweave_ipc_receive(struct vmweave_ipc *,int,void *,size_t,uint32_t *,const void **,size_t *,void **,size_t *,unsigned *);
int vmweave_ipc_reply(struct vmweave_ipc *,int,unsigned,uint32_t,uint32_t,uint32_t,const void *,size_t);
#endif
