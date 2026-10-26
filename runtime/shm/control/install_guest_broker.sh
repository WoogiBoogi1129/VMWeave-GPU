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
install -d /opt/vmweave/lib /opt/vmweave/control /opt/vmweave/bin /etc/vmweave
# Preserve explicit operator configuration across upgrades; new installs stay off.
if [ ! -e /etc/vmweave/guest-broker.env ]; then
    printf 'VMWEAVE_BULK_COPY=0\n' > /etc/vmweave/guest-broker.env
    chmod 0644 /etc/vmweave/guest-broker.env
fi
install -m 0755 "$artifacts/guest-gpu-smoke" /opt/vmweave/bin/guest-gpu-smoke
install -m 0644 "$artifacts/source-revision.txt" /opt/vmweave/source-revision.txt
install -m 0644 "$artifacts/libvmweave_guest.so" /opt/vmweave/lib/libvmweave_guest.so.new
mv -f /opt/vmweave/lib/libvmweave_guest.so.new /opt/vmweave/lib/libvmweave_guest.so
ln -sfn libvmweave_guest.so /opt/vmweave/lib/libcuda.so.1
ln -sfn libvmweave_guest.so /opt/vmweave/lib/libflyt_guest.so
for file in vmweave_env.py guest_broker.py guest_bootstrap.py; do
    install -m 0644 "$artifacts/$file" "/opt/vmweave/control/$file"
done
install -m 0644 "$artifacts/vmweave-guest-broker.service" /etc/systemd/system/
# Existing /opt/flyt directories are migrated only while the broker is stopped.
if [ -d /opt/flyt ] && [ ! -L /opt/flyt ]; then
    test ! -e /opt/flyt.pre-vmweave || { echo "Existing migration backup; inspect before retry" >&2; exit 1; }
    mv /opt/flyt /opt/flyt.pre-vmweave
fi
ln -sfn vmweave /opt/flyt
systemctl daemon-reload
# The new transport must start on a fresh VM boot; never reopen live SHM rings.
systemctl enable vmweave-guest-broker.service
printf 'Broker installed for next boot. Add authorized users to group vmweave.\n'
