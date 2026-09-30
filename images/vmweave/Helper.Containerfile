# Compatibility helper; control plane is the Go Operator.
FROM docker.io/library/python:3.11-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84
ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/WoogiBoogi1129/VMWeave-GPU" org.opencontainers.image.revision=$VCS_REF
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VMWEAVE_API_GROUP=vmweave.io
WORKDIR /opt/flyt/control
COPY runtime/shm/control/ /opt/flyt/control/
USER 65532:65532
ENTRYPOINT ["python3", "/opt/flyt/control/provision.py"]
CMD []
