/* Deprecated source compatibility; use vmweave_guest.h. */
#ifndef VMWEAVE_LEGACY_FLYT_GUEST_H
#define VMWEAVE_LEGACY_FLYT_GUEST_H
#include "flyt_wire.h"
#include "vmweave_guest.h"
#ifndef flyt_device_ref
#define flyt_device_ref vmweave_device_ref
#endif
#ifndef flyt_guest_exchange
#define flyt_guest_exchange vmweave_guest_exchange
#endif
#ifndef flyt_guest_lock
#define flyt_guest_lock vmweave_guest_lock
#endif
#ifndef flyt_guest_ref
#define flyt_guest_ref vmweave_guest_ref
#endif
#ifndef flyt_wire
#define flyt_wire vmweave_wire
#endif
#endif
