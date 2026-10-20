FROM docker.io/library/golang:1.25@sha256:54b6b88db6fe375c6676625d87d668273f85c6d09153635d0cbba89cba7a207a AS builder
WORKDIR /src
COPY operator/go.mod operator/go.sum ./
RUN go mod download
COPY operator/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /manager ./cmd
FROM gcr.io/distroless/static:nonroot@sha256:516757106de35205efb70b91ba03f6f1298424a0678c603255cf2852a7000087
COPY --from=builder /manager /manager
USER 65532:65532
ENTRYPOINT ["/manager"]
