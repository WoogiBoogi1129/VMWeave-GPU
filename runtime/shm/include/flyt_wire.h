/* Deprecated source compatibility; use vmweave_wire.h. */
#ifndef VMWEAVE_LEGACY_FLYT_WIRE_H
#define VMWEAVE_LEGACY_FLYT_WIRE_H
#include "flyt_cuda_exec.h"
#include "flyt_mapping.h"
#include "vmweave_wire.h"
#ifndef FLYT_GOODBYE
#define FLYT_GOODBYE VMWEAVE_GOODBYE
#endif
#ifndef FLYT_HEARTBEAT
#define FLYT_HEARTBEAT VMWEAVE_HEARTBEAT
#endif
#ifndef FLYT_HELLO
#define FLYT_HELLO VMWEAVE_HELLO
#endif
#ifndef flyt_cuda_exec
#define flyt_cuda_exec vmweave_cuda_exec
#endif
#ifndef flyt_cuda_session
#define flyt_cuda_session vmweave_cuda_session
#endif
#ifndef flyt_get
#define flyt_get vmweave_get
#endif
#ifndef flyt_mapping
#define flyt_mapping vmweave_mapping
#endif
#ifndef flyt_put
#define flyt_put vmweave_put
#endif
#endif
