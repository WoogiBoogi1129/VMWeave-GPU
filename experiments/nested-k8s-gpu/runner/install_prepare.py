from common import *
import concurrent.futures,difflib,hashlib,re
if (PRIVATE/'preparation.complete').exists():
    raise SystemExit('Guest preparation already completed; refusing key rotation or broker replacement.')
INSTALL=EXP/'installation'
src=ROOT.parent/'Kubernetes_Installer_2026'
save('inventory/installer-source.txt',run(['git','rev-parse','HEAD'],cwd=src)+run(['git','status','--short'],cwd=src))
for role,file in [('cp','k8s-setup.sh'),('worker','k8s-worker-setup.sh')]:
    original=(src/file).read_text();s=original
    s=s.replace('https://pkgs.k8s.io/addons:/cri-o:/stable:/','https://download.opensuse.org/repositories/isv:/cri-o:/stable:/')
    s=s.replace('install -y --no-install-recommends cri-o kubelet kubeadm kubectl','install -y --no-install-recommends cri-o=1.35.10-1.1 kubelet=1.35.9-1.1 kubeadm=1.35.9-1.1 kubectl=1.35.9-1.1')
    s=s.replace('kubeadm init --pod-network-cidr="${CIDR}" --cri-socket=unix:///var/run/crio/crio.sock','kubeadm init --config=/home/ubuntu/nested/init.yaml --skip-token-print')
    if role=='cp':
        s=s.replace('  MAX_RETRIES=30','  local i\n  MAX_RETRIES=30')
        s=re.sub(r'step_install_helm\(\) \{.*?\n\}', 'step_install_helm() {\n  install -m 0755 /home/ubuntu/nested/helm /usr/local/bin/helm\n  helm version --short\n}',s,flags=re.S)
        start=s.index('  CILIUM_CLI_VERSION=$(curl')
        end=s.index('  echo " > Cilium CNI',start)
        s=s[:start]+'  install -m 0755 /home/ubuntu/nested/cilium /usr/local/bin/cilium\n'+s[end:]
        s=s.replace('--helm-set ipam.mode=kubernetes','--helm-values /home/ubuntu/nested/cilium-values.yaml')
    else:
        s=re.sub(r'  JOIN_CMD=\(.*?  "\$\{JOIN_CMD\[@\]\}"', '  kubeadm join --config=/home/ubuntu/nested/join.yaml',s,flags=re.S)
        # Config file replaces interactive token collection; secret stays mode 0600.
        s=s.replace('  collect_join_info\n','  : # join.yaml supplies protected discovery credentials\n')
    (INSTALL/file).write_text(s)
    (INSTALL/(file+'.patch')).write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile=file,tofile=file+'.experiment')))
    run(['bash','-n',INSTALL/file])
    save('inventory/'+file+'.sha256',hashlib.sha256(original.encode()).hexdigest()+' original\n'+hashlib.sha256(s.encode()).hexdigest()+' patched\n')
def prepare(role):
    for _ in range(60):
        try: ssh(role,'true',stderr=subprocess.DEVNULL);break
        except subprocess.CalledProcessError:time.sleep(3)
    else: raise RuntimeError(role+' SSH timeout')
    ssh(role,'mkdir -p /home/ubuntu/nested')
    file='k8s-setup.sh' if role=='cp' else 'k8s-worker-setup.sh'
    scp(role,INSTALL/file,'/home/ubuntu/nested/')
    save('inventory/'+role+'-guest-before.txt',ssh(role,'hostname; cat /etc/machine-id; sudo cat /sys/class/dmi/id/product_uuid; uname -a; cat /etc/os-release; df -h /; ip -4 address; test ! -e /etc/kubernetes/admin.conf; test ! -e /var/lib/etcd'))
    for step in ('system-prep','apt-repos','install-packages'):
        marker=PRIVATE/(role+'-'+step+'.done')
        if marker.exists(): continue
        print(role,step,'START',flush=True)
        cmd=f'cd /home/ubuntu/nested && sudo env DEBIAN_FRONTEND=noninteractive KUBERNETES_VERSION=v1.35 CILIUM_VERSION=1.20.2 CIDR=10.246.0.0/16 bash {file} --step {step}'
        log=OUT/f'raw/{role}-{step}.log'
        if log.exists(): log.rename(log.with_name(log.name+'.attempt-'+str(time.time_ns())))
        with log.open('w') as f:
            subprocess.run(['python3',str(EXP/'runner/common.py'),role,cmd],stdout=f,stderr=subprocess.STDOUT,check=True)
        marker.touch()
        print(role,step,'DONE',flush=True)
    cmd='''sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y wireguard-tools gcc libc6-dev podman jq
sudo install -d /etc/crio/crio.conf.d /etc/systemd/system/kubelet.service.d
printf '[crio.runtime]\ncgroup_manager = "systemd"\n' | sudo tee /etc/crio/crio.conf.d/99-kubernetes.conf
printf '[Unit]\nAfter=wg-quick@wg0.service\nWants=wg-quick@wg0.service\n' | sudo tee /etc/systemd/system/kubelet.service.d/20-wireguard.conf
sudo systemctl daemon-reload
sudo systemctl restart crio
sudo systemctl enable kubelet
sudo sh -c 'umask 077; wg genkey > /etc/wireguard/private.key; wg pubkey < /etc/wireguard/private.key > /etc/wireguard/public.key'
dpkg-query -W cri-o kubelet kubeadm kubectl
'''
    save('raw/'+role+'-extra-packages.log',ssh(role,cmd,stderr=subprocess.STDOUT))
with concurrent.futures.ThreadPoolExecutor(2) as pool:
    list(pool.map(prepare,['cp','worker']))
pubs={r:ssh(r,'sudo cat /etc/wireguard/public.key').strip() for r in ('cp','worker')}
for role,ip,peer in [('cp','10.245.0.10','worker'),('worker','10.245.0.11','cp')]:
    peerip='10.245.0.11' if peer=='worker' else '10.245.0.10'
    endpoint=obj('get','svc','vw-k8s-'+peer+'-01','-n',NS)['spec']['clusterIP']
    # Private key is read only within the guest, never included in evidence.
    config=f'[Interface]\nAddress = {ip}/24\nListenPort = 51820\nMTU = 1220\nPrivateKey = PRIVATE_PLACEHOLDER\n\n[Peer]\nPublicKey = {pubs[peer]}\nAllowedIPs = {peerip}/32\nEndpoint = {endpoint}:51820\nPersistentKeepalive = 25\n'
    (INSTALL/(role+'-wg0.redacted.conf')).write_text(config)
    import shlex
    ssh(role,'sudo python3 -c '+shlex.quote('import pathlib; p=pathlib.Path("/etc/wireguard/wg0.conf");p.write_text('+repr(config)+'.replace("PRIVATE_PLACEHOLDER",pathlib.Path("/etc/wireguard/private.key").read_text().strip()));p.chmod(0o600)'))
    ssh(role,'sudo systemctl enable --now wg-quick@wg0')
for role,peerip in [('cp','10.245.0.11'),('worker','10.245.0.10')]:
    save('cluster/'+role+'-wireguard.txt',ssh(role,f'ip -4 address show wg0; ping -c 2 {peerip}; ping -M do -s 1192 -c 1 {peerip}; sudo wg show'))
scp('cp','/usr/local/bin/helm','/home/ubuntu/nested/')
scp('cp','/usr/local/bin/cilium','/home/ubuntu/nested/')
save('inventory/tools.sha256',run(['sha256sum','/usr/local/bin/helm','/usr/local/bin/cilium']))
scp('worker',ROOT/'.local/v055-release-20261027/published-guest','/home/ubuntu/nested/')
save('raw/broker-install.log',ssh('worker','sudo sh /home/ubuntu/nested/published-guest/install_guest_broker.sh /home/ubuntu/nested/published-guest && sudo usermod -aG vmweave ubuntu && getent group vmweave'))
print('PREPARATION COMPLETE',flush=True)
(PRIVATE/'preparation.complete').touch()
