ARG WORKER_BASE
FROM ${WORKER_BASE}
RUN mv /opt/flyt/bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker.original && mv /opt/flyt/bin/flyt-shm-session-worker /opt/flyt/bin/flyt-shm-session-worker.original
COPY runner/worker-gate.sh /opt/flyt/bin/flyt-shm-worker
COPY runner/worker-gate.sh /opt/flyt/bin/flyt-shm-session-worker
RUN chmod 755 /opt/flyt/bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-session-worker
