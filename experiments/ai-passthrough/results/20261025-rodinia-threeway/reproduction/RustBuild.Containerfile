FROM localhost/flyt-threeway-build:20261025-full
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup.sh && sh /tmp/rustup.sh -y --profile minimal --default-toolchain 1.90.0 && rm /tmp/rustup.sh
ENV PATH=/root/.cargo/bin:$PATH
