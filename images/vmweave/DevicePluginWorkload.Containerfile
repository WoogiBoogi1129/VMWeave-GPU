ARG GUEST_IMAGE
FROM ${GUEST_IMAGE} AS guest
FROM docker.io/library/ubuntu:22.04@sha256:3b06811b2afd352be909dd088a004166d665dc76d38b13eada33522a9d915c6f AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY --from=guest /opt/vmweave/guest /guest
COPY integrations/kubernetes-device-plugin/workloads/sgemm.c /sgemm.c
RUN cc -O2 -Wall -Wextra -Werror /sgemm.c -L/guest -lvmweave_guest -Wl,-rpath,/opt/vmweave/lib -o /sgemm
FROM docker.io/library/ubuntu:22.04@sha256:3b06811b2afd352be909dd088a004166d665dc76d38b13eada33522a9d915c6f
COPY --from=guest /opt/vmweave/guest/libvmweave_guest.so /opt/vmweave/lib/libvmweave_guest.so
COPY --from=guest /opt/vmweave/guest/guest-gpu-smoke /opt/vmweave/bin/guest-gpu-smoke
COPY --from=build /sgemm /opt/vmweave/bin/sgemm
ENV LD_LIBRARY_PATH=/opt/vmweave/lib
USER 1000:1000
ENTRYPOINT ["/opt/vmweave/bin/guest-gpu-smoke"]
