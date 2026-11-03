# v0.5.7 lifecycle validation

The source adds VMI-scoped termination handling for single-allocation channels,
identity-bound completion receipts and finalization independent of runtime drain.
Persistent VM stop/restart behavior is retained. v0.5.6 was a superseded candidate;
v0.5.7 also corrects optional-receipt serialization in the generated Go API.

- `operator-check.log`: CRD copy checks, Go vet and race-enabled API/engine tests.
- `control-tests.log`: Python control tests, including terminal watch evidence.
- `deployment-tests.log`: chart/install/package tests.

The deployment record is `../../v0.5.7.json`. It distinguishes public package
verification, isolated Kubernetes API fixtures, and readiness/preservation checks
on the existing cluster. API fixtures seed synthetic lifecycle status in a
private test namespace: they do **not** demonstrate physical GPU detach or a new
end-to-end VM boot/stop experiment. No new comparative performance claim is made.

All production runtime VMs and Workers are preserved during this control-plane
update. Only controller/webhook Deployments and the additive Channel CRD schema
are updated. The existing legacy Released channels without receipts and the
unresolved Draining channel remain preserved. Partial backing-deletion recovery
and the post-reclaim/pre-status-write crash window are outside this change.
