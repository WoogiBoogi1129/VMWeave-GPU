> **역사 자료:** 정리 이전 문서입니다. 현재 안내는 [VMWeave-GPU 문서](https://WoogiBoogi1129.github.io/VMWeave-GPU/)를 따르세요. 아래의 명령·상태·환경은 작성 당시 기준이며, 상대 문서 링크는 보존 커밋으로 연결합니다.

# Managed Kubernetes deployment

The legacy `deploy/templates` path reproduces the original experiment. New
runtime work lives under `deploy/kustomize` and uses prebuilt images instead of
passing binaries through a builder PVC.

## Shared-cluster safety boundary

- Only namespaces whose name begins with `flyt-` and which carry
  `app.kubernetes.io/part-of=flyt` may be mutated by managed scripts.
- GPU selection is an explicit UUID allow-list.
- Rendering fails when an approved GPU, or one of its MIG children, is already
  represented by an allocated DRA claim.
- The checked-in GPU overlay is inert: its selector is `false` and replicas are
  zero until locally rendered.
- The managed apply script rejects cluster-scoped and non-Flyt objects.

## Workflow

1. Build and publish the `cluster-manager` and `gpu-cell` targets from
   `images/flyt/Containerfile`.
2. Put image digests and approved GPU UUIDs in ignored `config.env`.
3. Create a dedicated labeled namespace.
4. Run `make validate-managed`.
5. Create the two runtime Secrets with `scripts/create-managed-secrets.sh`.
6. Apply with `scripts/apply-managed.sh`.

The current phase deliberately does not create or modify KubeVirt VMs. Guest
session reconciliation must move from direct MongoDB writes to the managed
session API before VM automation is enabled.
