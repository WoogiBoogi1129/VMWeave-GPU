FROM localhost/vmweave-worker:system-comparison-20261001
COPY bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker
ENV HD_METRICS=1 HD_VARIANT=original
