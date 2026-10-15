#!/bin/bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../../.." && pwd)
build_dir=${SM_BUILD_DIR:-"$root/.local/sm-core-limit-20261015"}
build_image=${SM_BUILD_IMAGE:-d94699a19c42f78777eb8126bda5f823767801f1c9698d065319bede58dbc7e2}
commit=b216ba1be1b8e21488d1c7370ed3357b3049aad1
mkdir -p "$build_dir/artifacts"
if [[ ! -d "$build_dir/HAMi-core/.git" ]]; then
  git clone https://github.com/Project-HAMi/HAMi-core.git "$build_dir/HAMi-core"
  git -C "$build_dir/HAMi-core" checkout --detach "$commit"
fi
test "$(git -C "$build_dir/HAMi-core" rev-parse HEAD)" = "$commit"
# Reapply only our exact patch; reject unrelated source edits.
if ! git -C "$build_dir/HAMi-core" diff --quiet; then
  for patch in 0002-linear-sm-gain-with-idle-reset.patch 0001-linear-sm-gain.patch; do
    if git -C "$build_dir/HAMi-core" apply --reverse --check "$root/experiments/sm-core-limit/patches/$patch" 2>/dev/null; then
      git -C "$build_dir/HAMi-core" apply --reverse "$root/experiments/sm-core-limit/patches/$patch"
      break
    fi
  done
fi
git -C "$build_dir/HAMi-core" diff --exit-code
for variant in original patched idle-reset; do
  if [[ "$variant" = patched ]]; then
    git -C "$build_dir/HAMi-core" apply "$root/experiments/sm-core-limit/patches/0001-linear-sm-gain.patch"
  elif [[ "$variant" = idle-reset ]]; then
    git -C "$build_dir/HAMi-core" apply --reverse "$root/experiments/sm-core-limit/patches/0001-linear-sm-gain.patch"
    git -C "$build_dir/HAMi-core" apply "$root/experiments/sm-core-limit/patches/0002-linear-sm-gain-with-idle-reset.patch"
  fi
  podman run --rm -v "$build_dir/HAMi-core:/src:rw" --workdir /src --entrypoint /bin/sh "$build_image" -c 'J=8 ./build.sh' > "$build_dir/build-$variant.log" 2>&1
  cp "$build_dir/HAMi-core/build/libvgpu.so" "$build_dir/artifacts/libvgpu-$variant.so.tmp"
  mv "$build_dir/artifacts/libvgpu-$variant.so.tmp" "$build_dir/artifacts/libvgpu-$variant.so"
done
podman run --rm -v "$root:/repo:rw" -v "$build_dir/artifacts:/out:rw" --entrypoint /bin/sh "$build_image" -c 'gcc -O2 -I/usr/local/cuda/include /repo/experiments/sm-core-limit/probes/sm_probe.c -L/usr/local/cuda/lib64/stubs -lcuda -o /out/sm-probe'
podman run --rm -v "$root:/repo:rw" -v "$build_dir/artifacts:/out:rw" --entrypoint /bin/sh "$build_image" -c 'gcc -O2 -I/usr/local/cuda/include /repo/experiments/sm-core-limit/probes/memory_probe.c -L/usr/local/cuda/lib64/stubs -lcuda -o /out/memory-probe
if test -f /repo/.local/thesis-isolation-20261012/artifacts/libflyt_guest.so; then
  gcc -O2 -DVMWEAVE -I/usr/local/cuda/include /repo/experiments/sm-core-limit/probes/sm_probe.c -L/repo/.local/thesis-isolation-20261012/artifacts -Wl,--no-as-needed -lflyt_guest -o /out/sm-probe-guest
fi'
sha256sum "$build_dir"/artifacts/* > "$build_dir/SHA256SUMS"
