#!/bin/sh
# HAMi's postStart hook. Publish a new inode before the upstream initializer:
# truncating a library already mapped by running Workers can crash them.
set -eu
dest=${1:?Usage: vgpu-init.sh destination-directory}
dest=${dest%/}
test -n "$dest"
source=/k8s-vgpu/lib/nvidia/libvgpu.so.v2.10.0
mkdir -p "$dest"
temporary=$(mktemp "$dest/.vmweave-libvgpu.XXXXXX")
trap 'rm -f "$temporary"' EXIT HUP INT TERM
cp "$source" "$temporary"
chmod 755 "$temporary"
cmp "$source" "$temporary"
mv -f "$temporary" "$dest/libvgpu.so.v2.10.0"
trap - EXIT HUP INT TERM
exec /k8s-vgpu/bin/vgpu-init.upstream.sh "$dest"
