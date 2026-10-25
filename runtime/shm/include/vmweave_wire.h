#ifndef VMWEAVE_WIRE_H
#define VMWEAVE_WIRE_H
#include "vmweave_cuda_exec.h"
#include "vmweave_mapping.h"
/* v1 reply: u32 version, u32 flags (1=large D2D, 2=broker bounded),
 * u64 H2D chunk, u64 D2H chunk. Unknown peers return NotSupported. */
#define VMWEAVE_COPY_LIMITS 0x1014u
#define VMWEAVE_HELLO 1u
#define VMWEAVE_GOODBYE 2u
#define VMWEAVE_HEARTBEAT 3u
static inline uint64_t vmweave_get(const uint8_t *p,unsigned n){uint64_t x=0;for(unsigned i=0;i<n;i++)x|=(uint64_t)p[i]<<(8*i);return x;}
static inline void vmweave_put(uint8_t *p,uint64_t x,unsigned n){for(unsigned i=0;i<n;i++)p[i]=(uint8_t)(x>>(8*i));}
struct vmweave_cuda_session { struct vmweave_cuda_exec *exec; };
#endif
