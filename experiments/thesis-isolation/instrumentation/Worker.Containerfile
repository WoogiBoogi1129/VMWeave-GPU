FROM localhost/vmweave-worker:boundary-base-20261014
COPY install/bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker.original
COPY context-observer.so /opt/flyt/lib/context-observer.so
COPY worker-wrapper.sh /opt/flyt/bin/flyt-shm-worker
RUN chmod 755 /opt/flyt/bin/flyt-shm-worker
ENV FLYT_TRACE_REQUESTS=1
