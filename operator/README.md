# VMWeave Operator

Operator SDK v1.42.3 / controller-runtime Go project. The supported deployment is
`charts/vmweave-operator`; see [installation](../docs/getting-started/install.md).
Controller and webhook run centrally, with explicit namespaced caches and RoleBindings.

Run `make check` for schema consistency, vet and race tests. Run `make build` for the
manager binary. `images/vmweave/Operator.Containerfile` builds its container.

The initial migration preserves the audited OpenAPI/CEL schemas in `config/crd/bases`.
`hack/generate-types.py` generates typed Go API objects and scheme registration from these schemas; `make generate`
regenerates the types and DeepCopy methods. The chart ships identical schema copies.
This deliberately differs from inferring weaker schemas from Go types during migration.
OLM bundles and the SDK's example scaffolding are not part of the supported install path.
