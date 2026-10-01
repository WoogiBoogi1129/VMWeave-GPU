FROM localhost/flyt-worker:stage2-20260928
COPY runtime/shm/control /opt/flyt/control
ENV FLYT_TRACE_REQUESTS=0 GPU_CORE_UTILIZATION_POLICY=FORCE VMWEAVE_API_GROUP=vmweave.io
