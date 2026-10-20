#!/bin/sh
# Run as root in the VM, with the guest-artifacts directory as the argument.
set -eu
artifacts=${1:?usage: install_guest_broker.sh ARTIFACT_DIRECTORY}
if systemctl is-active --quiet vmweave-guest-broker.service; then
    echo 'Halt the VM and install on its offline disk/image, or install before the next fresh GPU binding; active broker must not be replaced.' >&2
    exit 1
fi
for command in python3 install systemctl groupadd sha256sum; do command -v "$command" >/dev/null; done
(cd "$artifacts" && sha256sum -c SHA256SUMS)
getent group vmweave >/dev/null || groupadd --system vmweave
install -d /opt/flyt/lib /opt/flyt/control /opt/flyt/bin
install -m 0755 "$artifacts/guest-gpu-smoke" /opt/flyt/bin/guest-gpu-smoke
install -m 0644 "$artifacts/source-revision.txt" /opt/flyt/source-revision.txt
install -m 0644 "$artifacts/libflyt_guest.so" /opt/flyt/lib/libflyt_guest.so.new
mv -f /opt/flyt/lib/libflyt_guest.so.new /opt/flyt/lib/libflyt_guest.so
ln -sfn libflyt_guest.so /opt/flyt/lib/libcuda.so.1
for file in guest_broker.py guest_bootstrap.py; do
    install -m 0644 "$artifacts/$file" "/opt/flyt/control/$file"
done
install -m 0644 "$artifacts/vmweave-guest-broker.service" /etc/systemd/system/
systemctl daemon-reload
# The new transport must start on a fresh VM boot; never reopen live SHM rings.
systemctl enable vmweave-guest-broker.service
printf 'Broker installed for next boot. Add authorized users to group vmweave.\n'
