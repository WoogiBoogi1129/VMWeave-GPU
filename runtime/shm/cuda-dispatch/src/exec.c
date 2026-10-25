#include "vmweave_cuda_exec.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>

struct allocation { uint64_t id; void *pointer; size_t bytes; };
/* A process is never reused for a different client, even after destruction. */
static atomic_flag session_created = ATOMIC_FLAG_INIT;
struct vmweave_cuda_exec {
    struct vmweave_cuda_backend backend;
    void *context;
    pthread_t owner;
    int closing;
    uint32_t fatal_error;
    uint64_t next_handle;
    struct allocation allocations[VMWEAVE_EXEC_MAX_ALLOCATIONS];
};

static int status(struct vmweave_cuda_result *r, uint32_t code)
{
    r->status = code;
    if (code != VMWEAVE_SHM_OK) {
        r->result_domain = VMWEAVE_RESULT_NONE;
        r->api_result = 0;
    }
    return (int)code;
}

int vmweave_cuda_exec_check(struct vmweave_cuda_exec *s)
{
    if (!s || !pthread_equal(s->owner, pthread_self())) return VMWEAVE_SHM_BAD_DESCRIPTOR;
    return s->closing ? VMWEAVE_SHM_CHANNEL_CLOSED : VMWEAVE_SHM_OK;
}

int vmweave_cuda_exec_create(const struct vmweave_cuda_backend *b, void *context,
                          struct vmweave_cuda_exec **out)
{
    struct vmweave_cuda_exec *s;
    if (!out) return VMWEAVE_SHM_BAD_DESCRIPTOR;
    *out = NULL;
    if (!b || !b->get_count || !b->get_device || !b->set_device ||
        !b->allocate || !b->release || !b->copy || !b->synchronize)
        return VMWEAVE_SHM_BAD_DESCRIPTOR;
    s = calloc(1, sizeof(*s));
    if (!s) return VMWEAVE_SHM_INTERNAL_ERROR;
    if (atomic_flag_test_and_set(&session_created)) {
        free(s);
        return VMWEAVE_SHM_CHANNEL_CLOSED;
    }
    s->backend = *b;
    s->context = context;
    s->owner = pthread_self();
    s->next_handle = 1;
    *out = s;
    return VMWEAVE_SHM_OK;
}

static struct allocation *lookup(struct vmweave_cuda_exec *s, uint64_t id)
{
    size_t i;
    if (!id) return NULL;
    for (i = 0; i < VMWEAVE_EXEC_MAX_ALLOCATIONS; ++i)
        if (s->allocations[i].id == id) return &s->allocations[i];
    return NULL;
}

static int resolve(struct vmweave_cuda_exec *s, struct vmweave_device_ref ref,
                   size_t bytes, void **pointer)
{
    struct allocation *a = lookup(s, ref.handle);
    if (!a || ref.offset > a->bytes || bytes > a->bytes - (size_t)ref.offset)
        return 0;
    *pointer = (unsigned char *)a->pointer + (size_t)ref.offset;
    return 1;
}

static int copy_call(struct vmweave_cuda_exec *s, const struct vmweave_cuda_call *c,
                     struct vmweave_cuda_result *r)
{
    void *dst = NULL, *src = NULL, *host = NULL;
    uint64_t n = c->args.copy.bytes;
    uint32_t kind = c->args.copy.direction;
    if (n > SIZE_MAX || (kind != VMWEAVE_COPY_DTOD && n > VMWEAVE_COPY_CHUNK_BYTES) ||
        kind < VMWEAVE_COPY_HTOD || kind > VMWEAVE_COPY_DTOD)
        return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    if (kind != VMWEAVE_COPY_DTOH && !resolve(s, c->args.copy.dst, (size_t)n, &dst))
        return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    if (kind != VMWEAVE_COPY_HTOD && !resolve(s, c->args.copy.src, (size_t)n, &src))
        return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    if (kind == VMWEAVE_COPY_HTOD) {
        if (c->args.copy.host_input_bytes != n || (n && !c->args.copy.host_input))
            return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    } else if (c->args.copy.host_input_bytes || c->args.copy.host_input) {
        return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    }
    if(c->args.copy.borrow_input && kind!=VMWEAVE_COPY_HTOD)
        return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    if(c->args.copy.host_output || c->args.copy.host_output_bytes){
        if(kind!=VMWEAVE_COPY_DTOH || !c->args.copy.host_output || c->args.copy.host_output_bytes<n)
            return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    }
    /* Reject overlapping device ranges before CUDA. */
    if (kind == VMWEAVE_COPY_DTOD && n &&
        c->args.copy.dst.handle == c->args.copy.src.handle) {
        uint64_t a = c->args.copy.dst.offset, b = c->args.copy.src.offset;
        if ((a >= b ? a - b : b - a) < n)
            return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    }
    if (!n) return status(r, VMWEAVE_SHM_OK);
    if(kind==VMWEAVE_COPY_HTOD && c->args.copy.borrow_input){
        src=(void *)c->args.copy.host_input;
    }else if(kind==VMWEAVE_COPY_DTOH && c->args.copy.host_output){
        dst=c->args.copy.host_output;
    }else if (kind != VMWEAVE_COPY_DTOD) {
        host = malloc((size_t)n);
        if (!host) return status(r, VMWEAVE_SHM_INTERNAL_ERROR);
        if (kind == VMWEAVE_COPY_HTOD) {
            memcpy(host, c->args.copy.host_input, (size_t)n);
            src = host;
        } else dst = host;
    }
    r->api_result = s->backend.copy(s->context, dst, src, (size_t)n, kind);
    if (r->api_result) {
        s->closing = 1;
        s->fatal_error = r->api_result;
    }
    if (!r->api_result && kind == VMWEAVE_COPY_DTOH) {
        r->data = dst;
        r->data_bytes = (size_t)n;
        r->data_borrowed = c->args.copy.host_output != NULL;
    } else free(host);
    return status(r, VMWEAVE_SHM_OK);
}

int vmweave_cuda_exec_resolve(struct vmweave_cuda_exec *s, struct vmweave_device_ref r,size_t n,void **out)
{
    if(!s||!out||s->closing||!pthread_equal(s->owner,pthread_self()))return 0;
    return resolve(s,r,n,out);
}

int vmweave_cuda_exec_call(struct vmweave_cuda_exec *s, const struct vmweave_cuda_call *c,
                        struct vmweave_cuda_result *r)
{
    struct allocation *a;
    size_t i;
    if (!r) return VMWEAVE_SHM_BAD_DESCRIPTOR;
    memset(r, 0, sizeof(*r));
    if (!s || !c) return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    if (!pthread_equal(s->owner, pthread_self()))
        return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
    if (s->closing) return status(r, VMWEAVE_SHM_CHANNEL_CLOSED);
    r->result_domain = VMWEAVE_RESULT_CUDA_RUNTIME;
    switch (c->api_id) {
    case VMWEAVE_API_RUNTIME_GET_DEVICE_COUNT:
        r->api_result = s->backend.get_count(s->context, &r->device);
        break;
    case VMWEAVE_API_RUNTIME_GET_DEVICE:
        r->api_result = s->backend.get_device(s->context, &r->device);
        break;
    case VMWEAVE_API_RUNTIME_SET_DEVICE:
        r->api_result = s->backend.set_device(s->context, c->args.device);
        break;
    case VMWEAVE_API_RUNTIME_MALLOC:
        if (c->args.allocation_bytes > SIZE_MAX)
            return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
        for (i = 0; i < VMWEAVE_EXEC_MAX_ALLOCATIONS; ++i)
            if (!s->allocations[i].id) break;
        /* Reserve bookkeeping capacity BEFORE any allocation side effect. */
        if (i == VMWEAVE_EXEC_MAX_ALLOCATIONS || s->next_handle == UINT64_MAX)
            return status(r, VMWEAVE_SHM_INTERNAL_ERROR);
        a = &s->allocations[i];
        r->api_result = s->backend.allocate(s->context, &a->pointer,
                                             (size_t)c->args.allocation_bytes);
        if (!r->api_result) {
            if (!c->args.allocation_bytes && !a->pointer) break;
            if (!a->pointer) {
                s->closing = 1;
                return status(r, VMWEAVE_SHM_INTERNAL_ERROR);
            }
            a->bytes = (size_t)c->args.allocation_bytes;
            a->id = s->next_handle++;
            r->handle = a->id;
        } else {
            a->pointer = NULL;
            /* CUDA Runtime error 2 is an ordinary allocation rejection (also
             * used by HAMi quota enforcement), not a poisoned CUDA context.
             * Keep existing allocations usable for free and a smaller retry.
             * All other allocation failures retain the conservative shutdown.
             */
            if (r->api_result != 2) {
                s->closing = 1;
                s->fatal_error = r->api_result;
            }
        }
        break;
    case VMWEAVE_API_RUNTIME_FREE:
        if (!c->args.free_handle) {
            r->api_result = s->backend.release(s->context, NULL);
            if (r->api_result) {
                s->closing = 1;
                s->fatal_error = r->api_result;
            }
            break;
        }
        a = lookup(s, c->args.free_handle);
        if (!a) return status(r, VMWEAVE_SHM_BAD_DESCRIPTOR);
        r->api_result = s->backend.release(s->context, a->pointer);
        if (!r->api_result) memset(a, 0, sizeof(*a));
        else {
            s->closing = 1;
            s->fatal_error = r->api_result;
        }
        break;
    case VMWEAVE_API_RUNTIME_MEMCPY:
        return copy_call(s, c, r);
    case VMWEAVE_API_RUNTIME_DEVICE_SYNCHRONIZE:
        r->api_result = s->backend.synchronize(s->context);
        if (r->api_result) {
            s->closing = 1;
            s->fatal_error = r->api_result;
        }
        break;
    default:
        return status(r, VMWEAVE_SHM_UNSUPPORTED_API);
    }
    if (r->api_result) r->device = 0;
    return status(r, VMWEAVE_SHM_OK);
}

void vmweave_cuda_result_release(struct vmweave_cuda_result *r)
{
    if (!r) return;
    if(!r->data_borrowed)free(r->data);
    memset(r, 0, sizeof(*r));
}

int vmweave_cuda_exec_destroy(struct vmweave_cuda_exec **session, uint32_t *cuda_error)
{
    struct vmweave_cuda_exec *s;
    size_t i;
    if (!session || !cuda_error) return VMWEAVE_SHM_BAD_DESCRIPTOR;
    *cuda_error = 0;
    if (!*session) return VMWEAVE_SHM_OK;
    s = *session;
    if (!pthread_equal(s->owner, pthread_self())) return VMWEAVE_SHM_BAD_DESCRIPTOR;
    s->closing = 1;
    if (s->fatal_error) {
        *cuda_error = s->fatal_error;
        return VMWEAVE_SHM_INTERNAL_ERROR;
    }
    *cuda_error = s->backend.synchronize(s->context);
    if (*cuda_error) {
        s->fatal_error = *cuda_error;
        return VMWEAVE_SHM_INTERNAL_ERROR;
    }
    for (i = 0; i < VMWEAVE_EXEC_MAX_ALLOCATIONS; ++i) {
        if (!s->allocations[i].id) continue;
        *cuda_error = s->backend.release(s->context, s->allocations[i].pointer);
        if (*cuda_error) {
            s->fatal_error = *cuda_error;
            return VMWEAVE_SHM_INTERNAL_ERROR;
        }
        memset(&s->allocations[i], 0, sizeof(s->allocations[i]));
    }
    free(s);
    *session = NULL;
    return VMWEAVE_SHM_OK;
}

/* Legacy binary ABI: same implementation and address, no second state. */
extern __typeof__(vmweave_cuda_exec_call) flyt_cuda_exec_call __attribute__((alias("vmweave_cuda_exec_call")));
extern __typeof__(vmweave_cuda_exec_check) flyt_cuda_exec_check __attribute__((alias("vmweave_cuda_exec_check")));
extern __typeof__(vmweave_cuda_exec_create) flyt_cuda_exec_create __attribute__((alias("vmweave_cuda_exec_create")));
extern __typeof__(vmweave_cuda_exec_destroy) flyt_cuda_exec_destroy __attribute__((alias("vmweave_cuda_exec_destroy")));
extern __typeof__(vmweave_cuda_exec_resolve) flyt_cuda_exec_resolve __attribute__((alias("vmweave_cuda_exec_resolve")));
extern __typeof__(vmweave_cuda_result_release) flyt_cuda_result_release __attribute__((alias("vmweave_cuda_result_release")));
