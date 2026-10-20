# HAMi DRA packaging

VMWeave's DRA path uses `Project-HAMi/k8s-dra-driver` commit
`300224ac789ad40ced1ea2d9b47f6ba4a7cb5c69` (chart 0.1.1). The image builds that
source; the pinned upstream v0.1.0 image supplies only the runtime filesystem.
The build must set both HAMi and NVIDIA version linker variables: the feature
registry otherwise panics at startup.

`images/hami-dra/Containerfile` copies the patched HAMi-core from the published
VMWeave v0.3.0 HAMi image. It does not use the upstream unpatched library.
`install-core.sh` publishes new inodes before invoking the upstream initializer,
so running consumers keep their existing mappings during a driver restart.

`patches/0001-gpu-allowlist.patch` restricts GPU discovery with the comma-separated
`VMWEAVE_DRA_GPU_UUIDS` variable. An empty value retains upstream discovery of all
GPUs. Set a nonempty allowlist on a shared node and exclude the same UUIDs from
other allocators. Unknown UUIDs yield no matching devices, not fallback GPUs.
This filter is an allocation boundary, not a security sandbox for the privileged
node plugin.

Use a dedicated `driver.hostHookPath`, such as `/var/lib/vmweave-hami-dra`, to
separate the library and claim cache from classic HAMi. The consumer container
still sees `/usr/local/vgpu/libvgpu.so`. Do not remove this directory while claims
are in use. Driver removal and application cleanup are separate operations.

The `hami-dra-image` workflow builds and runs the GPU-free image verification on
relevant changes, and publishes only for release tags. Verify locally with
`python3 tests/hami-dra/test_image.py --engine podman --image YOUR_IMAGE`.
