FROM localhost/flyt-threeway-build:20261025-egl
RUN apt-get update && apt-get install -y --no-install-recommends libvdpau-dev && rm -rf /var/lib/apt/lists/*
