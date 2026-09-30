.PHONY: build test generate manifests check vet
build:
	CGO_ENABLED=0 go build -trimpath -o bin/manager ./cmd

test:
	go test -race ./api/... ./internal/... ./cmd/...

vet:
	go vet ./api/... ./internal/... ./cmd/...

generate:
	python3 hack/generate-types.py
	gofmt -w api/v1alpha1
	go run sigs.k8s.io/controller-tools/cmd/controller-gen@v0.18.0 object paths=./api/...

# The initial API schemas preserve the audited CEL/default constraints verbatim.
# Do not replace them with less restrictive inferred schemas during this migration.
manifests:
	python3 hack/check-crds.py

check: manifests vet test
