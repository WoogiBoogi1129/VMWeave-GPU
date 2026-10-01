FROM localhost/vmweave-worker:performance-20260930
COPY bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker
ENV FLYT_METRICS=1
