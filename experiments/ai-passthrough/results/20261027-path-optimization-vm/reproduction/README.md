# Executed campaign scripts

These are the scripts used from the repository root on the experiment host.
They reference the isolated candidate build and local guest packages under
`.local/path-optimization-20261027`; binary hashes and image digests are in the parent directory.

The fixed formal protocol predates measurements. Supplementary qualification hooks were added
without changing the formal measurement branch; see `../formal-harness-scope-check.json`.
`analyze.py` and `plot.py` regenerate derived outputs from the preserved raw JSON.

Do not rerun the infrastructure scripts against the original output/resource names: outputs are
exclusive-create and belong to this completed campaign. A new run needs new output paths and
experiment resource names, and must recheck the test GPU, CPU placement and current production state.
No private SSH key or runtime Mongo password is included here.

Root layout permission check used a rootless Podman container with UID 0, network disabled,
NVIDIA_VISIBLE_DEVICES=void, read-only candidate mount at /work, and
VMWEAVE_GUEST_LIBRARY=/work/build/libvmweave_guest.so. The command was
`python3 /work/source/tests/integration/layout_permissions.py -v` in the candidate Worker image.
