from common import *
import re,shlex
def step(role,name):
    filename='k8s-setup.sh' if role=='cp' else 'k8s-worker-setup.sh'
    marker=PRIVATE/(role+'-'+name+'.done')
    if marker.exists():return
    print(role,name,'START',flush=True)
    command=f'cd /home/ubuntu/nested && sudo env KUBERNETES_VERSION=v1.35 CILIUM_VERSION=1.20.2 CIDR=10.246.0.0/16 bash {filename} --step {name}'
    try: output=ssh(role,command,stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        save(f'raw/{role}-{name}-failed-{time.time_ns()}.log',re.sub(r'\b[a-z0-9]{6}\.[a-z0-9]{16}\b','<REDACTED_TOKEN>',e.output));raise RuntimeError(name+' failed; inspect log')
    save(f'raw/{role}-{name}.log',re.sub(r'\b[a-z0-9]{6}\.[a-z0-9]{16}\b','<REDACTED_TOKEN>',output))
    marker.touch();print(role,name,'DONE',flush=True)
scp('cp',EXP/'manifests/init.yaml','/home/ubuntu/nested/')
scp('cp',EXP/'manifests/cilium-values.yaml','/home/ubuntu/nested/')
step('cp','init-cluster');step('cp','kubeconfig');step('cp','install-helm')
if not (PRIVATE/'worker-join-cluster.done').exists():
    join=ssh('cp','sudo kubeadm token create --ttl 2h --print-join-command').split()
    token=join[join.index('--token')+1];ca=join[join.index('--discovery-token-ca-cert-hash')+1]
    config=f'''apiVersion: kubeadm.k8s.io/v1beta4
kind: JoinConfiguration
discovery:
  bootstrapToken:
    apiServerEndpoint: 10.245.0.10:6443
    token: {token}
    caCertHashes: ["{ca}"]
nodeRegistration:
  name: vw-k8s-worker-01
  criSocket: unix:///var/run/crio/crio.sock
  kubeletExtraArgs:
    - name: node-ip
      value: 10.245.0.11
'''
    p=PRIVATE/'join.yaml';p.write_text(config);p.chmod(0o600)
    scp('worker',p,'/home/ubuntu/nested/join.yaml');ssh('worker','chmod 600 /home/ubuntu/nested/join.yaml')
    (EXP/'manifests/join.redacted.yaml').write_text(config.replace(token,'<GENERATE_AT_EXECUTION>'))
step('worker','join-cluster');step('cp','install-cilium')
if not (PRIVATE/'coredns-cilium.done').exists():
    # Cilium operator normally recreates unmanaged DNS Pods automatically.
    dns=json.loads(inner('get','pods','-n','kube-system','-l','k8s-app=kube-dns','-o','json'))
    if any(not p['status'].get('podIP','').startswith('10.246.') for p in dns['items']):
        inner('rollout','restart','deployment/coredns','-n','kube-system')
    inner('rollout','status','deployment/coredns','-n','kube-system','--timeout=180s')
    (PRIVATE/'coredns-cilium.done').touch()
save('cluster/nodes-initial.json',json.loads(inner('get','nodes','-o','json')))
save('cluster/pods-initial.json',json.loads(inner('get','pods','-A','-o','json')))
save('cluster/cilium-values.txt',ssh('cp','sudo helm --kubeconfig /etc/kubernetes/admin.conf get values cilium -n kube-system -a'))
print('CLUSTER INSTALL COMPLETE',flush=True)
