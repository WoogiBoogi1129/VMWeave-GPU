FROM localhost/flyt-threeway-build:20261025-full
RUN apt-get update && apt-get install -y --no-install-recommends rpcbind && rm -rf /var/lib/apt/lists/*
COPY runtime /opt/flyt-test
ENV PATH=/opt/flyt-test:$PATH
