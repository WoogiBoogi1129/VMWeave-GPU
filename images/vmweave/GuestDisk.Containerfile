# Supply an offline, prepared QCOW2 OS disk as disk.qcow2.
FROM scratch
COPY --chown=107:107 --chmod=0440 disk.qcow2 /disk/disk.qcow2
