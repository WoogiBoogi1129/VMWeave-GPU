ARG CUDA_DEVEL_IMAGE=docker.io/nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04@sha256:ad6d59a3bbf3e82c1c849c9ac09cfc2a3e0bbb8655042fd899be6681b3fe2a85
ARG CUDA_RUNTIME_IMAGE=docker.io/nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04@sha256:17e2934e1fa96152b14f78078bfbafd0f00f391df995dc6c641a720fce1202bb
FROM ${CUDA_DEVEL_IMAGE} AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake python3 && rm -rf /var/lib/apt/lists/*
COPY runtime/shm /src/runtime/shm
RUN cmake -S /src/runtime/shm -B /build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/vmweave \
    && cmake --build /build --parallel 2 && cmake --install /build

COPY tests/integration /src/tests/integration
COPY scripts/test-shm-training.sh /src/scripts/test-shm-training.sh
RUN mkdir -p /tmp/vmweave-test-stubs \
    && ln -s /usr/local/cuda/lib64/stubs/libcuda.so /tmp/vmweave-test-stubs/libcuda.so.1 \
    && LD_LIBRARY_PATH=/tmp/vmweave-test-stubs:/usr/local/cuda/lib64 bash /src/scripts/test-shm-training.sh /build \
    && rm -rf /tmp/vmweave-test-stubs

COPY experiments/evidence/guest_gpu_smoke.c /src/guest_gpu_smoke.c
RUN cc -O2 -I/usr/local/cuda/include /src/guest_gpu_smoke.c -L/opt/vmweave/lib \
    -Wl,-rpath,'$ORIGIN' -lvmweave_guest -o /opt/vmweave/lib/guest-gpu-smoke

FROM ${CUDA_RUNTIME_IMAGE} AS worker
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates tini && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/vmweave/bin /opt/vmweave/bin
COPY runtime/shm/control /opt/vmweave/control
RUN ln -s vmweave /opt/flyt
ENV VMWEAVE_API_GROUP=vmweave.io
ENTRYPOINT ["/usr/bin/tini","--","python3","/opt/vmweave/control/supervisor.py"]

FROM docker.io/library/ubuntu:22.04@sha256:3b06811b2afd352be909dd088a004166d665dc76d38b13eada33522a9d915c6f AS guest-artifacts
COPY --from=build /opt/vmweave/lib/libvmweave_guest.so /opt/vmweave/lib/guest-gpu-smoke /opt/vmweave/guest/
RUN ln -s vmweave /opt/flyt && ln -s libvmweave_guest.so /opt/vmweave/guest/libflyt_guest.so && ln -s libvmweave_guest.so /opt/vmweave/guest/libcuda.so.1
COPY runtime/shm/control/vmweave_env.py runtime/shm/control/guest_broker.py runtime/shm/control/guest_bootstrap.py runtime/shm/control/vmweave-guest-broker.service runtime/shm/control/install_guest_broker.sh /opt/vmweave/guest/
# Link applications explicitly to this artifact or preload it into supported apps.
# No native CUDA, ONC RPC, libtirpc, rpcbind or Manager binary is copied here.

ARG SOURCE_REVISION=unknown
RUN printf "%s\n" "$SOURCE_REVISION" > /opt/vmweave/guest/source-revision.txt \
    && cd /opt/vmweave/guest && sha256sum libvmweave_guest.so libflyt_guest.so vmweave_env.py guest-gpu-smoke guest_broker.py guest_bootstrap.py vmweave-guest-broker.service install_guest_broker.sh source-revision.txt > SHA256SUMS
