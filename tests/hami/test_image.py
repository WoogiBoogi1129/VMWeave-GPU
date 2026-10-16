"""Exercise the release image's real postStart installer without host mounts/GPU."""
import argparse
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--engine', default='podman')
p.add_argument('--image', required=True)
a = p.parse_args()
script = r'''
set -eu
src=/k8s-vgpu/lib/nvidia/libvgpu.so.v2.10.0
expected=$(cut -d ' ' -f 1 /opt/vmweave/hami/libvgpu.sha256)
test "$(sha256sum "$src" | cut -d ' ' -f 1)" = "$expected"
test -s /opt/vmweave/hami/sm-limit.patch
dest=$(mktemp -d)
trap 'rm -rf "$dest"' EXIT
printf 'old-library' > "$dest/libvgpu.so.v2.10.0"
# Keep the old inode open, as a running process's mapping would.
exec 9< "$dest/libvgpu.so.v2.10.0"
/k8s-vgpu/bin/vgpu-init.sh "$dest/"
test "$(cat <&9)" = old-library
cmp "$src" "$dest/libvgpu.so.v2.10.0"
/k8s-vgpu/bin/vgpu-init.sh "$dest/"
cmp "$src" "$dest/libvgpu.so.v2.10.0"
test -s "$dest/ld.so.preload"
echo "PASS: image SHA, installation, repeat installation, existing inode preserved"
'''
subprocess.run([a.engine, 'run', '--rm', '--network=none', '--entrypoint',
                '/bin/sh', a.image, '-c', script], check=True)
