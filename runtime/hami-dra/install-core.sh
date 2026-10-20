#!/bin/bash
# Replace library inodes atomically so restarting the driver cannot truncate
# libraries already mapped by existing claim consumers.
set -eu
dest=${1:?destination directory required}
mkdir -p "$dest"
for name in libvgpu.so ld.so.preload; do
    source="/usr/local/lib/hami/$name"
    temporary=$(mktemp "$dest/.vmweave-$name.XXXXXX")
    trap 'rm -f "$temporary"' EXIT
    cp "$source" "$temporary"
    chmod 755 "$temporary"
    cmp "$source" "$temporary"
    mv -f "$temporary" "$dest/$name"
    trap - EXIT
done
exec /usr/bin/vgpu-init.upstream.sh "$dest"
