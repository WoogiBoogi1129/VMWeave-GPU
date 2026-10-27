#ifndef VMWEAVE_SHM_QUEUE_H
#define VMWEAVE_SHM_QUEUE_H
#include "vmweave_shm_contract.h"
#ifdef __cplusplus
extern "C" {
#endif

/* Local polling result only; never encode this as descriptor transport status. */
#define VMWEAVE_SHM_AGAIN 100
#define VMWEAVE_SHM_MAX_MESSAGE_BYTES (64u * 1024u * 1024u)
enum vmweave_shm_role { VMWEAVE_SHM_GUEST = 1, VMWEAVE_SHM_WORKER = 2 };
struct vmweave_shm_ring_layout { uint64_t offset; uint32_t entries; };
struct vmweave_shm_arena { uint64_t offset, bytes; };
struct vmweave_shm_slot {
    uint8_t session_id[16];
    struct vmweave_shm_ring_layout request_ring, response_ring;
    struct vmweave_shm_arena request_payload, response_payload;
};
/* Authoritative Host-private control-plane data, not read out of Guest memory.
 * All slots are fixed before format/open. No hot addition or same-generation
 * reattachment. Provider validates UID/epoch/binding/mapping ACK externally.
 */
struct vmweave_shm_layout {
    uint8_t allocation_id[16], channel_generation[16];
    uint64_t region_bytes;
    uint32_t session_count;
    struct vmweave_shm_slot slots[VMWEAVE_SHM_MAX_SESSIONS];
};
int vmweave_shm_layout_validate(const struct vmweave_shm_layout *);
/* Destructive initializer for NEW, exclusively owned, unmapped-by-peers backing
 * only. Never call on a live or reused generation. Clears the entire region.
 */
int vmweave_shm_format(void *mapping, size_t bytes, const struct vmweave_shm_layout *);
/* Mapping is caller-owned and must remain mapped until close and peer teardown.
 * x86-64 little-endian coherent normal RAM, 64-byte aligned base, lock-free u64.
 * Both endpoints open before submissions; selected ring counters must be zero.
 * One local owner thread, no concurrent API calls; not a reconnect operation.
 * wait_ms is 1..60000 and used by the Guest receive polling helper only.
 */
int vmweave_shm_open(void *mapping, size_t bytes, const struct vmweave_shm_layout *,
                  uint32_t slot, enum vmweave_shm_role, uint32_t wait_ms,
                  struct vmweave_shm_channel **out);
void vmweave_shm_close(struct vmweave_shm_channel *);
/* Explicit peer failure/timeout signal from future supervisor; local only. */
void vmweave_shm_abort(struct vmweave_shm_channel *);

struct vmweave_shm_part { const void *data; size_t bytes; };
/* Local-only gather; wire format unchanged. At most two private descriptors. */
int vmweave_shm_submit_parts(struct vmweave_shm_channel *,const struct vmweave_shm_request *,const struct vmweave_shm_part *,size_t);

/* Guest submit/receive are declared by vmweave_shm_contract.h. receive's function
 * return is delivery status; response.transport_status is the remote result.
 * try_receive is nonblocking. A too-small output buffer leaves response queued
 * and reports required output_bytes; retry receive with larger capacity, never
 * resubmit the API. Deadline is measured from publication, not from receive.
 */
int vmweave_shm_try_receive(struct vmweave_shm_channel *, uint64_t request_id,
                         struct vmweave_shm_response *);
/* Worker takes one request into allocated private memory; release after execution.
 * No CUDA/API payload interpretation here. Unknown API/schema must be answered
 * UNSUPPORTED_API by the later execution adapter. Response capacity is available
 * before execution so the adapter can preflight output space.
 */
int vmweave_shm_worker_take(struct vmweave_shm_channel *, struct vmweave_shm_request *);
void vmweave_shm_request_release(struct vmweave_shm_request *);
/* Caller owns storage until execution/response completes. Never pass a borrowed
 * request to request_release. Too-small storage does not consume the request. */
int vmweave_shm_worker_take_into(struct vmweave_shm_channel *,struct vmweave_shm_request *,void *,size_t);
void vmweave_shm_request_clear_borrowed(struct vmweave_shm_request *);
size_t vmweave_shm_response_capacity(const struct vmweave_shm_channel *);
int vmweave_shm_worker_respond(struct vmweave_shm_channel *,
                           const struct vmweave_shm_response *);

#ifdef __cplusplus
}
#endif
#endif
