FROM localhost/flyt-threeway-build:20261025-gl
RUN apt-get update && apt-get install -y --no-install-recommends libegl-dev && rm -rf /var/lib/apt/lists/*
