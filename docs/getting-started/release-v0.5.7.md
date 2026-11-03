# VMWeave v0.5.7: VMI-scoped Allocation cleanup

This Operator release separates runtime drain from finalizing an already completed
channel. It preserves the existing persistent `lifecycle: VM` contract.

- A bound `Allocation` channel observes the **recorded VMI UID** ending, including
  deletion, terminal status and replacement by another UID. This starts drain;
  an absent VMI or Pod is never treated as detach evidence.
- After both detach proofs, successful backing reclamation and any DRA Claim
  release, the controller records `status.completion` for that exact channel,
  VM/PVC identity, allocation and generation. A newly completed Allocation
  channel is then deleted with background propagation.
- Finalizing a completed channel never drains again or creates a new reclaim
  Pod. A receipt is independent of the old helper Pod's continued existence.
- A VM stop in `lifecycle: VM` still reclaims runtime resources, clears runtime
  identity and retains the same channel as `Stopped` for the next boot.
- Explicit drain/delete only halts a VM when its current channel binding and
  execution generation match. A replacement VMI is not stopped.

When a completed binding still belongs to a Halted VM and no VMI remains, only
that binding's annotations and matching hook annotation are removed. Other VM
configuration is retained. An `Always` VM's stale single-allocation binding is
kept to prevent silently restarting without GPU access. For automatic repeated
boots use `lifecycle: VM`; a one-shot VM must be halted and explicitly rebound
before another allocation. No restart-policy change is inferred from VMI death.

## Upgrade and limits

Apply the new SharedMemoryChannel CRD **before** upgrading the controller;
Helm does not upgrade CRDs in the chart's `crds/` directory. All existing fields
and lifecycle defaults are retained. The new status field is additive.

Historical Released channels without a matching completion receipt remain
preserved. If deletion is requested, they report
`ReleasedCompletionEvidenceRequired` in controller logs and keep their
finalizer. They must not be converted by copying status or removing finalizers
without independent verification. Existing incomplete Draining allocations
remain blocked. This release does not add unstarted-Worker evidence recovery,
partial-filesystem-deletion recovery, or a legacy receipt migration command.

The record is written only after reclamation succeeds. A crash between backing
removal and recording completion is still a separate recovery limitation; this
release does not claim fully crash-idempotent filesystem reclamation.

Clients that poll for a long-lived Released CR must migrate to a watch started
before drain. `scripts/operator/lifecycle_wait.py`, the evidence smoke tool and
the shared thesis-isolation runner capture the terminal object before automatic
GC. Archived experiment audits that require Released objects to remain in the
cluster describe the old release and are not the new cleanup contract.

Rollback to an older operator is not transparent for pending deletions:
older code ignores the receipt and can re-enter the unsafe drain path. Stop new
cleanup requests, finish or inventory pending operations, preserve the additive
schema and evidence, then assess a controller rollback. Do not downgrade CRDs
or force finalizers as a routine rollback step.

## Verification

Regression tests cover deletion after helper Pod GC, VM rebinding, replaced
VMI UIDs, completion identity mismatch, missing detach evidence, automatic
Allocation deletion and persistent VM stop/restart behavior. Publication and
live rollout evidence is recorded separately in `deploy/releases/v0.5.7.json`.

## Deployment result

Published and deployed on 2026-11-04 (KST). Central Helm release `vmweave` is
revision 14 and the separate `nested` release is revision 3, both chart 0.5.7.
Both Controller/Webhook pairs run the published Operator digest. The additive
CRD was applied before rollout; management scope, TLS and runtime images were
retained. Three existing VMIs and two active channel generations were preserved.

[Deployment record](https://github.com/WoogiBoogi1129/VMWeave-GPU/blob/main/deploy/releases/v0.5.7.json) and
[validation evidence](https://github.com/WoogiBoogi1129/VMWeave-GPU/blob/main/deploy/releases/evidence/v0.5.7/README.md) distinguish
synthetic API tests from production readiness checks. v0.5.6 was a superseded
candidate and was not deployed to these production releases.
