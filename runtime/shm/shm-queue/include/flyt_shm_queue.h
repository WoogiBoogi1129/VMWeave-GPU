/* Deprecated source compatibility; use vmweave_shm_queue.h. */
#ifndef VMWEAVE_LEGACY_FLYT_SHM_QUEUE_H
#define VMWEAVE_LEGACY_FLYT_SHM_QUEUE_H
#include "flyt_shm_contract.h"
#include "vmweave_shm_queue.h"
#ifndef FLYT_SHM_AGAIN
#define FLYT_SHM_AGAIN VMWEAVE_SHM_AGAIN
#endif
#ifndef FLYT_SHM_GUEST
#define FLYT_SHM_GUEST VMWEAVE_SHM_GUEST
#endif
#ifndef FLYT_SHM_MAX_MESSAGE_BYTES
#define FLYT_SHM_MAX_MESSAGE_BYTES VMWEAVE_SHM_MAX_MESSAGE_BYTES
#endif
#ifndef FLYT_SHM_MAX_SESSIONS
#define FLYT_SHM_MAX_SESSIONS VMWEAVE_SHM_MAX_SESSIONS
#endif
#ifndef FLYT_SHM_WORKER
#define FLYT_SHM_WORKER VMWEAVE_SHM_WORKER
#endif
#ifndef flyt_shm_abort
#define flyt_shm_abort vmweave_shm_abort
#endif
#ifndef flyt_shm_arena
#define flyt_shm_arena vmweave_shm_arena
#endif
#ifndef flyt_shm_channel
#define flyt_shm_channel vmweave_shm_channel
#endif
#ifndef flyt_shm_close
#define flyt_shm_close vmweave_shm_close
#endif
#ifndef flyt_shm_contract
#define flyt_shm_contract vmweave_shm_contract
#endif
#ifndef flyt_shm_format
#define flyt_shm_format vmweave_shm_format
#endif
#ifndef flyt_shm_layout
#define flyt_shm_layout vmweave_shm_layout
#endif
#ifndef flyt_shm_layout_validate
#define flyt_shm_layout_validate vmweave_shm_layout_validate
#endif
#ifndef flyt_shm_open
#define flyt_shm_open vmweave_shm_open
#endif
#ifndef flyt_shm_request
#define flyt_shm_request vmweave_shm_request
#endif
#ifndef flyt_shm_request_release
#define flyt_shm_request_release vmweave_shm_request_release
#endif
#ifndef flyt_shm_response
#define flyt_shm_response vmweave_shm_response
#endif
#ifndef flyt_shm_response_capacity
#define flyt_shm_response_capacity vmweave_shm_response_capacity
#endif
#ifndef flyt_shm_ring_layout
#define flyt_shm_ring_layout vmweave_shm_ring_layout
#endif
#ifndef flyt_shm_role
#define flyt_shm_role vmweave_shm_role
#endif
#ifndef flyt_shm_slot
#define flyt_shm_slot vmweave_shm_slot
#endif
#ifndef flyt_shm_try_receive
#define flyt_shm_try_receive vmweave_shm_try_receive
#endif
#ifndef flyt_shm_worker_respond
#define flyt_shm_worker_respond vmweave_shm_worker_respond
#endif
#ifndef flyt_shm_worker_take
#define flyt_shm_worker_take vmweave_shm_worker_take
#endif
#endif
