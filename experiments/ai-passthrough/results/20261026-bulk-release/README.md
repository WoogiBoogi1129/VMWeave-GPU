# v0.5.4 bulk-copy release qualification

Two fresh GPU VMs, OFF/ON then ON/OFF, each with one warmup and five
measured copies per size/direction. These follow-up samples check correctness
and possible regression; they are not a new matched Flyt performance campaign.
All 72 synchronous/asynchronous large-copy correctness cases passed.
Small-copy and D2D variability remains; default-off is retained. In particular,
1 MiB minus one byte H2D was slower in both sessions (10.22%, 14.3%). This
operation does not negotiate or use bulk memory, so these samples alone do not
establish a bulk-path cause. No universal no-regression claim is made.

The feature remains explicit opt-in in both the application and Broker.
Production validation and published image/chart digests are recorded in
`deploy/releases/v0.5.4.json` after deployment.

In-flight fault injection paused the isolated Worker child before submitting a
16 MiB copy, then killed that Worker or the Guest Broker. Both cases returned
999 for the pending and subsequent copy (1.30 s and 1.36 s respectively).
The real-socket unit test separately verifies no retry occurs. The first fault
setup attempt used the wrong process-name filter and was cleaned up before
retrying; its log is preserved. No production fault injection was performed.

CPU control tests: 106 tests, 105 passed and one skipped. Deployment tests: 16
passed. Runtime image ABI/copy regressions, documentation and chart lint passed.
The default chart intentionally needs deployment values; lint used captured
production values. Validation image revision was `v054-validation`; published
artifacts are qualified separately against the final source commit.

## Published and deployed

Release `v0.5.4`, source `678c8e7f065b922562098b4c97955cbbbc0436bb`, is
published and deployed. Production Helm revision is 12. All nine package files
(excluding revision/checksum metadata) match the locally qualified candidate.
The public chart installed successfully in an isolated namespace. The published
GPU canary passed smoke and 18 copy cases at 50%/2048 MiB.

Production Guest/Broker, Operator, Helper, Hook and Worker are updated. GPU
smoke, cache/math API checks, 18 enabled-bulk copy cases, and NW/LU reference
hashes passed. VM/PVC identities, 50%/2048 MiB quota, HAMi and DRA are preserved.
All test Pods and the isolated chart namespaces were removed.

The release default remains OFF. On the production VM only, Broker configuration
is ON and `/etc/profile.d/vmweave-bulk-copy.sh` exports the flag for new login
sessions. Existing shells, sudo commands and service workloads need explicit
`VMWEAVE_BULK_COPY=1`; this flag does not itself set CUDA library/preload paths.
The running Broker environment and a new login shell were verified.

Rollback uses the captured v0.5.3 Guest/Broker package, previous environment/profile,
Helm revision 11 and previous binding references, with a fresh VM binding.
Backups remain local; private VM identities/configuration are not published.
Image/chart digests and workflow links are in `deploy/releases/v0.5.4.json`.
