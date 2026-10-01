FROM localhost/vmweave-worker:performance-20260930
COPY bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker
ENV FLYT_WAIT_MODE=legacy FLYT_COPY_MODE=legacy FLYT_METRICS=1
