FROM ghcr.io/woogiboogi1129/vmweave-worker@sha256:efb17db71fbf9e1b497fce5cdd60e7a121d5e5d25d470bfda44cc38b34f926ca
COPY vmweave-shm-worker vmweave-shm-session-worker /opt/vmweave/bin/
ENV VMWEAVE_LIBRARY_TRACE=1
