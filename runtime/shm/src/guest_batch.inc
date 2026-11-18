/* Included by guest.c: one queue per CUDA client, under vmweave_guest_lock.
 * Explicit opt-in only. CUDA driver launch errors can be delayed to a later
 * call; after a failed batch this session is terminal and is never replayed.
 * A timer provides progress even when the application stops calling CUDA.
 * The 200 us deadline is a scheduling target, not a real-time guarantee. */
static struct {
    int known,enabled,error,thread_started,stop;
    pid_t pid;
    unsigned count;
    size_t used;
    uint64_t packets,submitted;
    uint8_t data[VMWEAVE_KERNEL_BATCH_BYTES];
    pthread_t thread;
    pthread_cond_t changed;
    struct timespec deadline;
} kernel_batch;

static int kernel_batch_flush(void){
    if(!kernel_batch.enabled)return 0;
    if(kernel_batch.pid!=getpid()||broken)return 999;
    if(kernel_batch.error)return kernel_batch.error;
    if(!kernel_batch.count)return 0;
    vmweave_put(kernel_batch.data,1,4);
    vmweave_put(kernel_batch.data+4,kernel_batch.count,4);
    size_t got=0;
    kernel_batch.packets++;kernel_batch.submitted+=kernel_batch.count;
    int e=vmweave_guest_exchange(VMWEAVE_KERNEL_BATCH,kernel_batch.data,kernel_batch.used,NULL,0,&got);
    /* Clear even on failure: an acknowledged prefix may already be running. */
    kernel_batch.count=0;kernel_batch.used=8;
    if(!e&&got)e=999;
    if(e)kernel_batch.error=e;
    return e;
}
static void *kernel_batch_main(void *unused){
    (void)unused;pthread_mutex_lock(&vmweave_guest_lock);
    while(!kernel_batch.stop){
        while(!kernel_batch.count&&!kernel_batch.stop)
            pthread_cond_wait(&kernel_batch.changed,&vmweave_guest_lock);
        if(kernel_batch.stop)break;
        int e=pthread_cond_timedwait(&kernel_batch.changed,&vmweave_guest_lock,&kernel_batch.deadline);
        if(e==ETIMEDOUT)kernel_batch_flush();
        else if(e){kernel_batch.error=999;kernel_batch.count=0;}
    }
    pthread_mutex_unlock(&vmweave_guest_lock);return NULL;
}
static int kernel_batch_init(void){
    if(kernel_batch.known)return kernel_batch.error;
    kernel_batch.known=1;
    const char *v=vmweave_getenv("VMWEAVE_KERNEL_BATCH");
    if(!v||strcmp(v,"1"))return 0;
    /* This first version is restricted to broker clients with a fresh session. */
    if(!vmweave_getenv("VMWEAVE_BROKER_SOCKET"))return kernel_batch.error=801;
    uint8_t out[16];size_t got=0;
    int e=vmweave_guest_exchange(VMWEAVE_KERNEL_BATCH_CAPS,NULL,0,out,sizeof(out),&got);
    if(e==801)return 0; /* Old peer: preserve the original synchronous path. */
    if(e)return kernel_batch.error=e;
    if(got!=16||vmweave_get(out,4)!=1||vmweave_get(out+4,4)!=VMWEAVE_KERNEL_BATCH_MAX||
       vmweave_get(out+8,4)!=VMWEAVE_KERNEL_BATCH_BYTES||vmweave_get(out+12,4)!=1)
        return kernel_batch.error=801;
    pthread_condattr_t attr;
    if(pthread_condattr_init(&attr))return kernel_batch.error=999;
    e=pthread_condattr_setclock(&attr,CLOCK_MONOTONIC);
    if(!e)e=pthread_cond_init(&kernel_batch.changed,&attr);
    pthread_condattr_destroy(&attr);if(e)return kernel_batch.error=999;
    kernel_batch.pid=getpid();kernel_batch.used=8;kernel_batch.enabled=1;
    if(pthread_create(&kernel_batch.thread,NULL,kernel_batch_main,NULL)){
        kernel_batch.enabled=0;return kernel_batch.error=999;
    }
    kernel_batch.thread_started=1;
    fprintf(stderr,"vmweave kernel-batch v1 enabled max=128 flush_target_us=200\n");return 0;
}
int vmweave_guest_kernel_submit(const void *input,size_t bytes){
    if(!input||bytes<48||bytes>VMWEAVE_KERNEL_RECORD_MAX)return 1;
    const uint8_t *p=input;
    int e=kernel_batch_init();if(e)return e;
    if(!kernel_batch.enabled||vmweave_get(p+8,8)){
        size_t got=0;return vmweave_guest_exchange(VMWEAVE_KERNEL_LAUNCH,input,bytes,NULL,0,&got);
    }
    if(kernel_batch.pid!=getpid()||broken)return 999;
    if(kernel_batch.error)return kernel_batch.error;
    if(!kernel_batch.count){
        clock_gettime(CLOCK_MONOTONIC,&kernel_batch.deadline);
        kernel_batch.deadline.tv_nsec+=200000;
        if(kernel_batch.deadline.tv_nsec>=1000000000){kernel_batch.deadline.tv_sec++;kernel_batch.deadline.tv_nsec-=1000000000;}
    }
    vmweave_put(kernel_batch.data+kernel_batch.used,bytes,4);
    memcpy(kernel_batch.data+kernel_batch.used+4,input,bytes); /* owns caller args */
    kernel_batch.used+=4+bytes;kernel_batch.count++;
    /* One wake per newly nonempty queue. Waking the timer for every launch
     * creates avoidable mutex contention in the very burst we are batching. */
    if(kernel_batch.count==1)pthread_cond_signal(&kernel_batch.changed);
    return kernel_batch.count==VMWEAVE_KERNEL_BATCH_MAX?kernel_batch_flush():0;
}
static void kernel_batch_shutdown(void){
    if(!kernel_batch.thread_started||kernel_batch.pid!=getpid())return;
    if(pthread_mutex_trylock(&vmweave_guest_lock))return;
    kernel_batch_flush();kernel_batch.stop=1;pthread_cond_signal(&kernel_batch.changed);
    pthread_mutex_unlock(&vmweave_guest_lock);pthread_join(kernel_batch.thread,NULL);
    kernel_batch.thread_started=0;pthread_cond_destroy(&kernel_batch.changed);
    fprintf(stderr,"vmweave kernel-batch packets=%llu submitted=%llu terminal_error=%d\n",
        (unsigned long long)kernel_batch.packets,(unsigned long long)kernel_batch.submitted,kernel_batch.error);
}
