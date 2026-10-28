from common import *
if (OUT/'inventory/workload-image.json').exists():
    raise SystemExit('Pinned workload image already recorded; refusing to replace this run artifact.')
ssh('worker','mkdir -p /home/ubuntu/nested/workload')
for f in ('correctness.c','Containerfile'):scp('worker',EXP/'workloads'/f,'/home/ubuntu/nested/workload/')
cmd='''set -eu
cd /home/ubuntu/nested/workload
cp /opt/vmweave/lib/libvmweave_guest.so .
gcc -std=c11 -O2 -Wall -Wextra -Werror correctness.c -L. -lvmweave_guest -o correctness
sudo podman build --pull=false -t localhost/nested-gpu:20261028 -f Containerfile .
sudo podman image inspect localhost/nested-gpu:20261028 --format '{{.Id}}'
sha256sum correctness libvmweave_guest.so
'''
try:save('raw/workload-build.log',ssh('worker',cmd,stderr=subprocess.STDOUT))
except subprocess.CalledProcessError as e:save('raw/workload-build-failed.log',e.output);raise RuntimeError('build failed')
image=json.loads(ssh('worker','sudo podman image inspect localhost/nested-gpu:20261028'))[0]
save('inventory/workload-image.json',image)
print('WORKLOAD BUILT '+image['Id'],flush=True)
