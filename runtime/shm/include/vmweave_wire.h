#ifndef VMWEAVE_WIRE_H
#define VMWEAVE_WIRE_H
#include "vmweave_cuda_exec.h"
#include "vmweave_mapping.h"
#define VMWEAVE_HELLO 1u
#define VMWEAVE_GOODBYE 2u
#define VMWEAVE_HEARTBEAT 3u
static inline uint64_t vmweave_get(const uint8_t *p,unsigned n){uint64_t x=0;for(unsigned i=0;i<n;i++)x|=(uint64_t)p[i]<<(8*i);return x;}
static inline void vmweave_put(uint8_t *p,uint64_t x,unsigned n){for(unsigned i=0;i<n;i++)p[i]=(uint8_t)(x>>(8*i));}
struct vmweave_cuda_session { struct vmweave_cuda_exec *exec; };
#endif
