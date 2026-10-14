#!/bin/sh
# Run as root in the VM, with the guest-artifacts directory as the argument.
set -eu
artifacts=${1:?usage: install_guest_broker.sh ARTIFACT_DIRECTORY}
getent group vmweave >/dev/null || groupadd --system vmweave
install -d /opt/flyt/lib /opt/flyt/control
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
