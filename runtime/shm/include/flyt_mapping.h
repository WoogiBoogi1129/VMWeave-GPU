/* Deprecated source compatibility; use vmweave_mapping.h. */
#ifndef VMWEAVE_LEGACY_FLYT_MAPPING_H
#define VMWEAVE_LEGACY_FLYT_MAPPING_H
#include "flyt_shm_queue.h"
#include "vmweave_mapping.h"
#ifndef flyt_layout_read
#define flyt_layout_read vmweave_layout_read
#endif
#ifndef flyt_map_file
#define flyt_map_file vmweave_map_file
#endif
#ifndef flyt_map_guest
#define flyt_map_guest vmweave_map_guest
#endif
#ifndef flyt_mapping
#define flyt_mapping vmweave_mapping
#endif
#ifndef flyt_shm_layout
#define flyt_shm_layout vmweave_shm_layout
#endif
#ifndef flyt_shm_queue
#define flyt_shm_queue vmweave_shm_queue
#endif
#ifndef flyt_unmap
#define flyt_unmap vmweave_unmap
#endif
#endif
