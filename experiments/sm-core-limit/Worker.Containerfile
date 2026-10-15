ARG WORKER_BASE
FROM ${WORKER_BASE}
RUN mv /opt/flyt/bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker.original
COPY runner/worker-gate.sh /opt/flyt/bin/flyt-shm-worker
RUN chmod 755 /opt/flyt/bin/flyt-shm-worker
