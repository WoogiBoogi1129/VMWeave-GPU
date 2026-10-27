FROM localhost/vmweave-worker:path-candidate-20261027
COPY compute-sanitizer /opt/compute-sanitizer
RUN mv /opt/vmweave/bin/vmweave-shm-session-worker /opt/vmweave/bin/vmweave-shm-session-worker-real
COPY sanitized-worker /opt/vmweave/bin/vmweave-shm-session-worker
