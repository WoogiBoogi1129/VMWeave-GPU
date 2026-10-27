FROM localhost/vmweave-worker:v053-candidate-1025
COPY vmweave-shm-session-worker vmweave-shm-worker /opt/vmweave/bin/
ENV VMWEAVE_PERSISTENT=1
