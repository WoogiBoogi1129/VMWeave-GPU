import datetime,json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/nested-k8s-gpu'
OUT=EXP/'results/20261028-minimal'
PRIVATE=ROOT/'.local/nested-k8s-20261028'
NS='vmweave-nested-k8s'
SYSTEM='vmweave-nested-system'
CTX='kubernetes-admin@kubernetes'
def run(args,**kw):
    return subprocess.check_output([str(x) for x in args],text=True,**kw)
def k(*args,**kw): return run(['kubectl','--context',CTX,*args],**kw)
def obj(*args): return json.loads(k(*args,'-o','json'))
def save(name,data):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(data if isinstance(data,str) else json.dumps(data,indent=2)+'\n')
def apply(data): return k('apply','-f','-',input=json.dumps(data))
def ssh(role,command,**kw):
    name='vw-k8s-'+('cp' if role=='cp' else 'worker')+'-01'
    ip=obj('get','service',name,'-n',NS)['spec']['clusterIP']
    return run(['ssh','-i',PRIVATE/'id_ed25519','-o','StrictHostKeyChecking=accept-new','-o',f'UserKnownHostsFile={PRIVATE}/known_hosts','-o','ConnectTimeout=8',f'ubuntu@{ip}',command],**kw)
def scp(role,source,target):
    name='vw-k8s-'+('cp' if role=='cp' else 'worker')+'-01'
    ip=obj('get','service',name,'-n',NS)['spec']['clusterIP']
    return run(['scp','-r','-i',PRIVATE/'id_ed25519','-o','StrictHostKeyChecking=accept-new','-o',f'UserKnownHostsFile={PRIVATE}/known_hosts',source,f'ubuntu@{ip}:{target}'])
def inner(*args):
    import shlex
    return ssh('cp','sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf '+shlex.join(args))
if __name__=='__main__':
    import sys
    try: print(ssh(sys.argv[1],sys.argv[2],stderr=subprocess.STDOUT))
    except subprocess.CalledProcessError as e:
        print(e.output);sys.exit(e.returncode)
