# VMWeave v0.5.8: durable, temporary reclamation evidence

This release closes the interruption window between backing-file removal and
`status.completion`. A controller-created ConfigMap stores an authorized
reclamation journal independently of the helper Pod. It is temporary: completion
is saved on the channel, then the writer Pod, dedicated RBAC/ServiceAccount and
journal are deleted before channel finalization or persistent `Stopped` reset.

## Protocol and trust

1. Verify current-generation guest/worker detach acknowledgements, their holder
   UIDs, roles and node; wait for Worker deletion and any provisioner exit.
2. Save a journal containing the channel/VM/VMI/Worker/PVC identities, allocation,
   execution generation, backend/Claim identity and detach evidence. Persist its
   exact UID and authorization in `status.reclamation`. Only a subsequent read
   may launch the helper.
3. The helper validates the complete allocation and `ready.json`, then saves its
   directory inode and file inventory as `Prepared` in the Kubernetes API **before
   the first unlink**. Conflicting updates and API errors stop further work.
4. On retry, only a matching authorization and journal may explain missing files.
   Surviving entries must match the saved inventory. Unknown contents, symlinks,
   hardlinks, replacements and missing allocations without a prepared journal
   fail closed. After unlink/rmdir and fsync, save journal state `Complete`.
5. The controller accepts this durable result even if the helper Pod disappeared,
   waits for DRA Claim release where applicable, and saves `status.completion`.
6. Delete the writer Pod and its scoped credentials, then the journal. Confirm
   absence before releasing the channel finalizer or resetting runtime identity.
   Cleanup failure retains the receipt/finalizer and retries only cleanup.

The journal is an API ConfigMap rather than a file in the shared PVC: existing
Workers and helpers share a filesystem UID/GID, so a file there would not provide
an independent write boundary. The helper's dedicated Role permits only `get`
and `update` of its one named ConfigMap. Worker permissions are unchanged and do
not grant journal or channel-status writes. Controller authorization is checked
against the journal UID and its exact authorization string. Cluster administrators
and users able to mutate controller-owned resources remain trusted; this is not
a security boundary against cluster-admin or arbitrary same-volume writers.

The controller embeds the Python helper and passes it to `python3 -c`. Existing
immutable helper-image references therefore receive the new recovery logic
without replacing active Worker/Guest images. Python 3 with stdlib SSL and normal
in-cluster service-account API connectivity are required. The standalone legacy
`runtime/shm/control/reclaim.py` is not this protocol and is no longer launched by
the Go operator.

## Upgrade and limits

Apply the additive `status.reclamation` SharedMemoryChannel CRD schema before the
controller upgrade; Helm does not update existing CRDs from `crds/`. Upgrade the
chart as well: the controller needs namespace-scoped ConfigMap management
permissions. Existing namespaces, TLS settings and runtime images can be retained.

Supported recovery covers helper/controller process or Pod interruption, partial
unlink and API failures with the backing filesystem and API state retained. Node
reboot, disk/node loss and administrative force-removal of journals/finalizers
are not claimed. A missing or replaced journal before completion blocks recovery.
Normal operation retains no long-lived journal and creates no extra PV/PVC or CRD.

Legacy `Released` objects without receipts are never automatically converted
from their phase or backing absence. Independently verified historical cleanup
must preserve an external audit and use exact UID/resourceVersion conditions.
A legacy in-progress `*-reclaim` Pod blocks automatic new-protocol adoption with
`LegacyReclamationRequiresVerification`; do not run old/new reclaimers together.
Unstarted-Worker detach recovery remains a separate change.

Do not roll back to an older controller with pending `status.reclamation`
operations: older code can ignore the journal and invoke the legacy reclaimer.
Inventory and finish pending operations before considering a rollback; preserve
the additive schema and evidence. Do not clear finalizers to resolve an ordinary
recovery failure.

## Verification

- Race-enabled Go tests cover independent journal completion, status-write failure,
  exact identity binding, stale detach rejection, DRA release ordering, failed
  helper retry, cleanup failures and persistent runtime reset.
- Python tests inject interruption at every deletion boundary and failures before
  or after each API commit; malformed, replaced and unsafe entries fail closed.
- `tests/integration/reclamation_api_canary.py` uses a real Kubernetes API, local
  PV/PVC and least-privilege helper Pods. It interrupts helpers after partial
  deletion, directory removal and completion, starts the controller, and checks
  recovery and removal of journals/credentials. Detach statuses are synthetic;
  this is not a physical GPU detach or VM boot benchmark.
- Deployment evidence and checks against the published OCI binary/chart are
  recorded in `deploy/releases/v0.5.8.json` after rollout.
