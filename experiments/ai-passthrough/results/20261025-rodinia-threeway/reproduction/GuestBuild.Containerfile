FROM localhost/flyt-threeway-build:20261025
RUN apt-get update && apt-get install -y --no-install-recommends libgl-dev && rm -rf /var/lib/apt/lists/*
