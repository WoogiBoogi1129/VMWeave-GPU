FROM localhost/vmweave-worker:v053-candidate-1025
COPY vmweave-shm-session-worker vmweave-shm-worker /opt/vmweave/bin/
ENV VMWEAVE_PERSISTENT=1 VMWEAVE_WORKER_REUSE=1 VMWEAVE_SESSION_ARENA=1 VMWEAVE_SESSION_EVENTFD=1 VMWEAVE_PINNED_POOL=1
