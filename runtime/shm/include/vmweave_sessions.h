#ifndef VMWEAVE_SESSIONS_H
#define VMWEAVE_SESSIONS_H
/* v2 application sessions over a single-owner v1 transport. Never reset rings. */
#define VMWEAVE_SESSION_OPEN 4u
#define VMWEAVE_SESSION_CLOSE 5u
#define VMWEAVE_SESSION_CALL 6u
/* Epoch-checked child liveness; no CUDA calls or state changes. */
#define VMWEAVE_SESSION_STATUS 7u
/* Broker controls use the API range so legacy brokers return unsupported. */
#define VMWEAVE_BROKER_CACHE_OPEN 0x7ff0u
#define VMWEAVE_BROKER_CACHE_STATUS 0x7ff1u
#define VMWEAVE_BROKER_CACHE_VERSION 1u
#define VMWEAVE_SESSION_ENVELOPE 24u
#define VMWEAVE_SESSION_MAX_BYTES (16u*1024u*1024u+4096u)
#endif
