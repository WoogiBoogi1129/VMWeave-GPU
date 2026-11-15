# Operator consolidation — 2026-11-15

Live cluster: `gpu-4`. Unchanged runtime/operator source:
`f6c6ab7acc28fc91d409110a7539a0d22b759ce2`, release v0.5.11, chart 0.5.11.
The chart archive SHA256 was verified against the published release record:
`162ae5a01e329e8b5c529353864b6c0547fec0f56bd234705c9212032d11572c`.

See the [deployment record](../../operator-consolidation-20261115.json) and
[procedure and limitations](../../../../docs/guides/operator-consolidation.md).

- `01`–`07` files record the sequential Helm maintenance, handoff and removal.
- Before/after workload snapshots retain identities, finalizers, ownership, spec hashes and relevant runtime status for all 47 objects. Raw manifests and full values remain in private `.local/operator-consolidation-20261115/` backups. Spec hashes use UTF-8 JSON with sorted keys and compact separators. Container device-health list order is not a restart; the private full comparison normalized that list by resource name.
- Admission checks use server dry-run. The old Controller's Attachment status request was rejected by the new webhook before its RBAC was removed.
- Metrics were captured after 48 actual reconciles; errors, panics and timeouts were zero.
- The GPU test submitted one `vmweave.io/gpu: 1` Pod inside `dp-dev-20261105`. Its pinned published workload image passed SGEMM 2×2 full-result validation. The temporary guest namespace was removed.
- The final deployment record also checks absence of the old Helm release, namespace, ClusterRoles, ClusterRoleBindings, RoleBindings and webhook registration. The namespace inventory excludes Events and was taken after Helm uninstall, before namespace removal.
- TLS CA bundle is replaced by its SHA256 (of its encoded string); private TLS keys and Kubernetes credentials are not included.
- Existing three `Draining / AwaitingDetachEvidence` channels remain unresolved. No new VM creation or two-slot GPU regression was run in this consolidation.

Recheck the saved evidence without cluster access:

```sh
python3 deploy/deployments/evidence/operator-consolidation-20261115/validate.py
```

`artifacts.json` hashes every file in this bundle except itself. This bundle records an operational topology change; it does not replace or modify historical v0.5.11 release evidence.
