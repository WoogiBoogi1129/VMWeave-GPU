FROM golang:1.25 AS builder
WORKDIR /src
COPY operator/go.mod operator/go.sum ./
RUN go mod download
COPY operator/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /manager ./cmd
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /manager /manager
USER 65532:65532
ENTRYPOINT ["/manager"]
