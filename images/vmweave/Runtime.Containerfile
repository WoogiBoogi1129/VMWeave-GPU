ARG CUDA_DEVEL_IMAGE=docker.io/nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04@sha256:ad6d59a3bbf3e82c1c849c9ac09cfc2a3e0bbb8655042fd899be6681b3fe2a85
ARG CUDA_RUNTIME_IMAGE=docker.io/nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04@sha256:17e2934e1fa96152b14f78078bfbafd0f00f391df995dc6c641a720fce1202bb
FROM ${CUDA_DEVEL_IMAGE} AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake && rm -rf /var/lib/apt/lists/*
COPY runtime/shm /src/runtime/shm
RUN cmake -S /src/runtime/shm -B /build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/flyt \
    && cmake --build /build --parallel 2 && cmake --install /build

COPY experiments/evidence/guest_gpu_smoke.c /src/guest_gpu_smoke.c
RUN cc -O2 -I/usr/local/cuda/include /src/guest_gpu_smoke.c -L/opt/flyt/lib \
    -Wl,-rpath,'$ORIGIN' -lflyt_guest -o /opt/flyt/lib/guest-gpu-smoke

FROM ${CUDA_RUNTIME_IMAGE} AS worker
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates tini && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/flyt/bin /opt/flyt/bin
COPY runtime/shm/control /opt/flyt/control
ENV FLYT_RESOURCE_BACKEND=hami VMWEAVE_API_GROUP=vmweave.io
ENTRYPOINT ["/usr/bin/tini","--","python3","/opt/flyt/control/supervisor.py"]

FROM docker.io/library/ubuntu:22.04@sha256:3b06811b2afd352be909dd088a004166d665dc76d38b13eada33522a9d915c6f AS guest-artifacts
COPY --from=build /opt/flyt/lib/libflyt_guest.so /opt/flyt/lib/guest-gpu-smoke /opt/flyt/guest/
RUN ln -s libflyt_guest.so /opt/flyt/guest/libcuda.so.1
COPY runtime/shm/control/guest_broker.py runtime/shm/control/guest_bootstrap.py runtime/shm/control/vmweave-guest-broker.service runtime/shm/control/install_guest_broker.sh /opt/flyt/guest/
# Link applications explicitly to this artifact or preload it into supported apps.
# No native CUDA, ONC RPC, libtirpc, rpcbind or Manager binary is copied here.

ARG SOURCE_REVISION=unknown
RUN printf "%s\n" "$SOURCE_REVISION" > /opt/flyt/guest/source-revision.txt \
    && cd /opt/flyt/guest && sha256sum libflyt_guest.so guest-gpu-smoke guest_broker.py guest_bootstrap.py vmweave-guest-broker.service install_guest_broker.sh source-revision.txt > SHA256SUMS
