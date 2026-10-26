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
