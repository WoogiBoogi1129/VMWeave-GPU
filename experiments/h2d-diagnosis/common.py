"""Current-operator campaign helpers. Commands and actual outputs are audited."""
import json, os, shlex, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '.local/h2d-diagnosis-20261005'
OUT = ROOT / 'experiments/evidence/results/2026-10-05-h2d-diagnosis'
NS = 'vmweave-test-a'
GPU = 'GPU-7d708c42-8d4a-16d5-0746-474567157aa3'
GUEST = 'localhost/flyt-evidence-guest@sha256:47e520785c49e6db93631ef4876dcb40b73b23ffc766327e6b02cdfe3496c052'
ADMIN = 'localhost/vmweave-worker@sha256:8566144a77681353b49211d8ae5a2ab71c6f082b7f4dd22e76eb8dcd386670e7'
HELPER = 'hd-admin'

def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def redact(text):
    secrets_file=BASE/"redaction-values.json"
    if secrets_file.exists():
        for value in json.loads(secrets_file.read_text()):text=text.replace(value,"[REDACTED]")
    for file in [BASE/'grafana-auth.json',BASE/'legacy-auth.json']:
        if file.exists():
            value=json.loads(file.read_text()).get('password','')
            if value:text=text.replace(value,'[REDACTED]')
    return text

def call(args, *, input=None, timeout=180, private=False, check=True):
    args = list(map(str, args)); started = time.time()
    result = subprocess.run(args, input=input, text=True, capture_output=True, timeout=timeout, env={**os.environ,"TMPDIR":"/dev/shm/hd-build-tmp"})
    if not private and not any(x in ('secret','secrets') for x in args):
        OUT.mkdir(parents=True, exist_ok=True)
        with (OUT/'commands.jsonl').open('a') as f:
            f.write(redact(json.dumps({'utc':started,'command':args,'stdin':input,
                'stdout':result.stdout,'stderr':result.stderr,'exit_code':result.returncode,
                'duration_s':time.time()-started}, ensure_ascii=False))+'\n')
    if check and result.returncode:
        raise RuntimeError(redact(shlex.join(args)+': '+result.stderr[-2000:]))
    return result.stdout if private else redact(result.stdout)

def k(*args, **kw): return call(['kubectl',*args],**kw)
def get(kind, name, ns=NS):
    s=k('get',kind,name,'-n',ns,'--ignore-not-found','-o','json')
    return json.loads(s) if s.strip() else None
def create(obj, private=False):
    return json.loads(k('create','-f','-','-o','json',input=json.dumps(obj),private=private))
def wait(fn, seconds=300):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=fn()
        if value:return value
        time.sleep(2)
    raise TimeoutError(str(fn))
def admin(args, **kw):
    args=list(args)
    if args[:3]==['chroot','/host','podman']:args=args[:2]+['env','TMPDIR=/dev/shm/hd-build-tmp']+args[2:]
    return k('exec','-n',NS,HELPER,'--',*args,**kw)

def ensure_admin():
    if not get('pod',HELPER):
        create({'apiVersion':'v1','kind':'Pod','metadata':{'name':HELPER,'namespace':NS,'labels':{'vmweave.io/campaign':'h2d-diagnosis-20261005'}},
          'spec':{'nodeName':'gpu-4','hostPID':True,'restartPolicy':'Never','automountServiceAccountToken':False,
          'containers':[{'name':'admin','image':ADMIN,'command':['sleep','43200'],
          'securityContext':{'privileged':True,'runAsUser':0},'volumeMounts':[{'name':'host','mountPath':'/host'}]}],
          'volumes':[{'name':'host','hostPath':{'path':'/','type':'Directory'}}]}})
    wait(lambda:get('pod',HELPER).get('status',{}).get('phase')=='Running')

if __name__=='__main__':
    ensure_admin()
    for name,args in [('nodes',['get','nodes','-o','wide']),('pods',['get','pods','-A','-o','wide'])]:
        (OUT/(name+'-before.txt')).write_text(k(*args))
    (OUT/'gpu-before.txt').write_text(call(['nvidia-smi','-q']))
    (OUT/'host-images.txt').write_text(admin(['chroot','/host','podman','images','--format','{{.Repository}}:{{.Tag}} {{.Digest}}']))
    save(OUT/'source-start.json',{'commit':call(['git','-C',ROOT,'rev-parse','HEAD']).strip(),
         'status':call(['git','-C',ROOT,'status','--short']),'started_utc':time.time()})
