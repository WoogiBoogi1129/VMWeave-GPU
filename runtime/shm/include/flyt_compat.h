/* Deprecated source compatibility; use vmweave_compat.h. */
#ifndef VMWEAVE_LEGACY_FLYT_COMPAT_H
#define VMWEAVE_LEGACY_FLYT_COMPAT_H
#include "flyt_async.h"
#include "vmweave_compat.h"
#ifndef FLYT_BLAS_CREATE
#define FLYT_BLAS_CREATE VMWEAVE_BLAS_CREATE
#endif
#ifndef FLYT_BLAS_DESTROY
#define FLYT_BLAS_DESTROY VMWEAVE_BLAS_DESTROY
#endif
#ifndef FLYT_BLAS_MATH_GET
#define FLYT_BLAS_MATH_GET VMWEAVE_BLAS_MATH_GET
#endif
#ifndef FLYT_BLAS_MATH_SET
#define FLYT_BLAS_MATH_SET VMWEAVE_BLAS_MATH_SET
#endif
#ifndef FLYT_BLAS_POINTER_GET
#define FLYT_BLAS_POINTER_GET VMWEAVE_BLAS_POINTER_GET
#endif
#ifndef FLYT_BLAS_POINTER_SET
#define FLYT_BLAS_POINTER_SET VMWEAVE_BLAS_POINTER_SET
#endif
#ifndef FLYT_BLAS_SGEMM
#define FLYT_BLAS_SGEMM VMWEAVE_BLAS_SGEMM
#endif
#ifndef FLYT_BLAS_STREAM
#define FLYT_BLAS_STREAM VMWEAVE_BLAS_STREAM
#endif
#ifndef FLYT_BLAS_WORKSPACE
#define FLYT_BLAS_WORKSPACE VMWEAVE_BLAS_WORKSPACE
#endif
#ifndef FLYT_DNN_CREATE
#define FLYT_DNN_CREATE VMWEAVE_DNN_CREATE
#endif
#ifndef FLYT_DNN_DESTROY
#define FLYT_DNN_DESTROY VMWEAVE_DNN_DESTROY
#endif
#ifndef FLYT_DNN_VERSION
#define FLYT_DNN_VERSION VMWEAVE_DNN_VERSION
#endif
#ifndef FLYT_GRAPH_CREATE
#define FLYT_GRAPH_CREATE VMWEAVE_GRAPH_CREATE
#endif
#ifndef FLYT_GRAPH_DESTROY
#define FLYT_GRAPH_DESTROY VMWEAVE_GRAPH_DESTROY
#endif
#ifndef FLYT_GRAPH_EMPTY_NODE
#define FLYT_GRAPH_EMPTY_NODE VMWEAVE_GRAPH_EMPTY_NODE
#endif
#ifndef FLYT_GRAPH_EXEC_DESTROY
#define FLYT_GRAPH_EXEC_DESTROY VMWEAVE_GRAPH_EXEC_DESTROY
#endif
#ifndef FLYT_GRAPH_INSTANTIATE
#define FLYT_GRAPH_INSTANTIATE VMWEAVE_GRAPH_INSTANTIATE
#endif
#ifndef FLYT_GRAPH_LAUNCH
#define FLYT_GRAPH_LAUNCH VMWEAVE_GRAPH_LAUNCH
#endif
#ifndef flyt_async
#define flyt_async vmweave_async
#endif
#ifndef flyt_async_stream
#define flyt_async_stream vmweave_async_stream
#endif
#ifndef flyt_compat_close
#define flyt_compat_close vmweave_compat_close
#endif
#ifndef flyt_compat_dispatch
#define flyt_compat_dispatch vmweave_compat_dispatch
#endif
#ifndef flyt_cuda_session
#define flyt_cuda_session vmweave_cuda_session
#endif
#ifndef flyt_shm_request
#define flyt_shm_request vmweave_shm_request
#endif
#ifndef flyt_shm_response
#define flyt_shm_response vmweave_shm_response
#endif
#endif
