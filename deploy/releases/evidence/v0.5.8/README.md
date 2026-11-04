# v0.5.8 reclamation validation

The implementation persists recovery intent and file inventory in an API
ConfigMap independent of the helper Pod. It removes the journal and dedicated
credentials after saving completion, before channel deletion or Stopped reset.
The release record is `../../v0.5.8.json`.

- `operator-check.log`, `control-tests.log`, `deployment-tests.log`: local checks.
- `api-filesystem-canary.json`: five scenarios using the **published OCI manager**,
  real Kubernetes API, local PV/PVC and helper Pods. Fault Pods exit at explicit
  checkpoints. Detach evidence is synthetic; test backing files do not represent
  an actual GPU mapping. No VM boot or node reboot test is claimed.
- `published-binary-verified.json`: source revision, image/chart digests and manager
  hash; published chart compared with source.
- `rbac-verification.json`, `controller-rbac-verification.json`: real authorization
  checks, including controller creation of the named-journal helper Role.
- `*-chart-diff.json`: preserved live Helm values change only ConfigMap permissions
  before the intended image digest replacement.
- `post-rollout-result.json`: both admission webhooks, active runtime preservation,
  unchanged unresolved Draining allocation and absence of leftover journals.
- `legacy-reviewed-proofs.json`, `legacy-cleanup-result.json`: one-time historical
  cleanup of three Released channels and six owned attachments. Exact-generation
  detach proofs, absent old VMI/Worker/backing and a different active VM binding
  were checked. Deletes/finalizer updates used UID/resourceVersion preconditions;
  no synthetic completion receipt was written. Shared VM/PV/PVC were retained.
  This manual migration is **not** the normal new-journal recovery path.
- `workflows.json`: all ten source main/tag workflows succeeded.

Published runtime images are listed for reproducibility; existing live Worker,
helper, Hook, HAMi and DRA references were retained during this controller update.
Physical GPU detach, application SLA, node reboot and storage-loss recovery are
outside these checks. Unused historical GPURequest objects were not removed.
