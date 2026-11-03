# VMWeave v0.5.6 candidate

This lifecycle candidate is superseded by [v0.5.7](release-v0.5.7.md) before
production deployment. v0.5.7 additionally makes the optional completion receipt
a nullable pointer in the generated Go API, so empty typed status does not emit
an invalid timestamp, and adds serialization/deep-copy regressions. Use v0.5.7
for deployment; do not treat the candidate tag as the final rollout record.
