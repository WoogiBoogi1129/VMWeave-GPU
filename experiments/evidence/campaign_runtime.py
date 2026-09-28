"""UID-scoped VM/native experiment runner; private preparation stays in .local."""
import concurrent.futures
import hashlib
import json
import shlex
import subprocess
import sys
import time
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NS = 'flyt-evidence'
GPU = 'GPU-7d708c42-8d4a-16d5-0746-474567157aa3'
WORKER = 'localhost/flyt-worker@sha256:a7bae7a184238df59b16cce0233ed6dbc74a135c3b3295b0c97811c2c9e9e47d'
GUEST = 'localhost/flyt-evidence-guest@sha256:47e520785c49e6db93631ef4876dcb40b73b23ffc766327e6b02cdfe3496c052'

def save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2)+'\n')

def call(args, **kw):
    return subprocess.check_output([str(x) for x in args], text=True, timeout=kw.pop('timeout',180), **kw)

def k(args, **kw): return call(['kubectl', *args], **kw)

def get(kind, name):
    s=k(['get',kind,name,'-n',NS,'--ignore-not-found','-o','json'])
    return json.loads(s) if s.strip() else None

def wait(fn, seconds=900):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=fn()
        if value:return value
        time.sleep(1)
    raise TimeoutError(str(fn))

class Run:
    def __init__(self, base, run_id, backend='shm', compute=100, slot='a', **condition):
        self.base=Path(base).resolve();self.art=self.base/'artifacts';self.name=run_id
        self.out=self.base/'runs'/run_id;self.out.mkdir(parents=True,exist_ok=False)
        self.backend=backend;self.compute=compute;self.slot=slot;self.uid=None
        self.manifest={'run_id':run_id,'backend':backend,'compute':compute,'memory_mib':4096,'sessions':1,
            'gpu_uuid':GPU,'slot':slot,'started_utc':time.time(),'conditions':condition,
            'commit':call(['git','rev-parse','HEAD'],cwd=ROOT).strip(),
            'file_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'experiments/evidence/campaign_probe.c',self.art/'campaign-probe-guest',self.art/'campaign-probe-native',self.art/'libflyt_guest.so']}}
        save(self.out/'manifest.json',self.manifest)
    def note(self, stage, **kw):
        row={'run_id':self.name,'event':stage,'utc_seconds':time.time(),**kw}
        print(json.dumps(row),flush=True)
        with (self.out/'host-events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    def prepare(self):
        self.note('PREPARE',backend=self.backend,compute=self.compute)
        if self.backend=='shm':
            images=json.loads((ROOT/'.local/evidence-20260924/images.json').read_text())
            cmd=[sys.executable,ROOT/'scripts/prepare-evidence-vm.py','--name',self.name,
                 '--reuse-pvc','evidence-vm-a-backing' if self.slot=='a' else 'evidence-pair-b-backing',
                 '--public-key',self.art/'guest-key.pub','--guest-image',GUEST,'--compute',self.compute,
                 '--output',self.out/'private-prepare']
            for key in ['control','worker','hook']:cmd += ['--'+key+'-image',images[key]]
            (self.out/'prepare.txt').write_text(call(cmd,cwd=ROOT))
            c=get('flytsharedmemorychannel',self.name+'-channel');self.uid=c['metadata']['uid']
            wait(lambda:get('flytsharedmemorychannel',self.name+'-channel').get('status',{}).get('phase')=='BackingReady')
            k(['patch','vm',self.name,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Always"}}'])
            def vm():
                v=get('vmi',self.name)
                return v if v and v.get('status',{}).get('phase')=='Running' and v['status'].get('interfaces') else None
            v=wait(vm);self.ip=v['status']['interfaces'][0]['ipAddress'];self.vmi_uid=v['metadata']['uid']
            self.ssh=['ssh','-i',str(self.art/'guest-key'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.out/'known-hosts'),'ubuntu@'+self.ip]
            def ready():
                return subprocess.run(self.ssh+['true'],capture_output=True,timeout=8).returncode==0
            wait(ready)
            def bound():
                c=get('flytsharedmemorychannel',self.name+'-channel')
                w=get('pod',self.name+'-channel-worker')
                return c if c.get('status',{}).get('workerPodUID') and w and w.get('status',{}).get('phase')=='Running' else None
            c=wait(bound);save(self.out/'private-channel.json',c)
            bdf=call(self.ssh+["python3 -c \"from pathlib import Path; print(next(p.name for p in Path('/sys/bus/pci/devices').iterdir() if (p/'vendor').read_text().strip()=='0x1af4' and (p/'device').read_text().strip()=='0x1110'))\""]).strip()
            self.bdf=bdf
            call([sys.executable,ROOT/'scripts/export-shm-guest.py','--channel-json',self.out/'private-channel.json','--bdf',bdf,'--slot','0','--output',self.out/'guest-config'])
            call(self.ssh+['mkdir -p /tmp/campaign'])
            scp=['scp','-i',str(self.art/'guest-key'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.out/'known-hosts')]
            files=[self.art/'campaign-probe-guest',self.art/'libflyt_guest.so',self.out/'guest-config/layout.bin',*sorted(self.art.glob('reference-*.bin'))]
            call(scp+[str(p) for p in files]+['ubuntu@'+self.ip+':/tmp/campaign/'])
            worker=get('pod',self.name+'-channel-worker')
            pods=json.loads(k(['get','pods','-n',NS,'-o','json']))['items']
            launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'+self.name+'-'))
            self.worker=worker['metadata']['name'];self.launcher=launcher['metadata']['name']
            cpu='0-7' if self.slot=='a' else '8-15';wcpu='16-19' if self.slot=='a' else '20-23'
            affinity=(ROOT/'experiments/evidence/campaign_affinity.py').read_text()
            def pin(pod,cpus):return k(['exec','-i','-n',NS,'evidence-c28-affinity','--','python3','-',pod['metadata']['uid'],cpus],input=affinity)
            qpin=pin(launcher,cpu);wpin=pin(worker,wcpu)
            (self.out/'cpu-pinning.txt').write_text(qpin+'\n'+wpin)
            clocks=[]
            for _ in range(5):
                t0=time.time();g=float(call(self.ssh+['date +%s.%N']).strip());t1=time.time();clocks.append({'host_before':t0,'guest':g,'host_after':t1,'offset':g-(t0+t1)/2,'uncertainty':(t1-t0)/2})
            best=min(clocks,key=lambda x:x['uncertainty']);self.offset=best['offset'];save(self.out/'clock-map.json',clocks)
            save(self.out/'identity.json',{'channel_uid':self.uid,'gpu_uuid':c['status']['gpuUUID'],'allocation':c['status']['allocation'],'vmi_uid':self.vmi_uid,'worker_uid':worker['metadata']['uid'],'worker':self.worker,'launcher':self.launcher,'launcher_uid':launcher['metadata']['uid'],'gpu_annotation':worker['metadata'].get('annotations',{}).get('hami.io/vgpu-devices-allocated'),'images':c['spec'],'guest_cpu_set':cpu,'worker_cpu_set':wcpu,'numa_memory_policy':'observed; not strict membind'})
        else:
            pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':self.name,'namespace':NS,'labels':{'flyt.dev/campaign':'20260928'},'annotations':{'nvidia.com/use-gpuuuid':GPU}},'spec':{'restartPolicy':'Never','terminationGracePeriodSeconds':1,'activeDeadlineSeconds':1800,'automountServiceAccountToken':False,'runtimeClassName':'nvidia','schedulerName':'hami-scheduler','nodeSelector':{'kubernetes.io/hostname':'gpu-4'},'containers':[{'name':'native','image':WORKER,'command':['sleep','1800'],'resources':{'limits':{'nvidia.com/gpu':1,'nvidia.com/gpumem':4096,'nvidia.com/gpucores':self.compute}},'volumeMounts':[{'name':'artifacts','mountPath':'/evidence'}]}],'volumes':[{'name':'artifacts','hostPath':{'path':str(self.art),'type':'Directory'}}]}}
            created=json.loads(k(['create','-f','-','-o','json'],input=json.dumps(pod)));self.uid=created['metadata']['uid']
            wait(lambda:get('pod',self.name).get('status',{}).get('phase')=='Running')
            actual=get('pod',self.name);save(self.out/'identity.json',{'uid':self.uid,'gpu_uuid':GPU,'annotations':actual['metadata'].get('annotations',{}),'image':WORKER,'cpu_set':'0-7'})
        self.note('PREPARED')
    def execute(self,kind='integer',mode='resident',seconds=2,count=0,iterations=64,seed=2026,start=0,reference='-',output='-'):
        prefix='/tmp/campaign/' if self.backend=='shm' else '/evidence/'
        args=[kind,mode,str(seconds),str(count),str(iterations),str(seed),str(start+(getattr(self,'offset',0) if start else 0)),prefix+reference if reference!='-' else '-',prefix+output if output!='-' else '-']
        if self.backend=='shm':
            command='sudo env FLYT_LAYOUT=/tmp/campaign/layout.bin FLYT_IVSHMEM_BDF='+self.bdf+' FLYT_SLOT=0 LD_LIBRARY_PATH=/tmp/campaign /tmp/campaign/campaign-probe-guest '+shlex.join(args)
            cmd=self.ssh+[command]
        else:
            env=['env']
            if self.backend=='native-hami-disabled':env+=['GPU_CORE_UTILIZATION_POLICY=DISABLE']
            cmd=['kubectl','exec','-n',NS,self.name,'--','taskset','-c','0-7',*env,'/evidence/campaign-probe-native',*args]
        save(self.out/'command.json',{'backend':self.backend,
             'program':prefix+('campaign-probe-guest' if self.backend=='shm' else 'campaign-probe-native'),'args':args})
        self.note('COMMAND',command=command if self.backend=='shm' else shlex.join(cmd))
        with (self.out/'stdout.jsonl').open('w') as out,(self.out/'stderr.txt').open('w') as err:
            p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err,text=True)
            watchdog=threading.Timer(900,p.kill);watchdog.start()
            try:
                for line in p.stdout:
                    out.write(line);out.flush();print(self.name+' '+line.rstrip(),flush=True)
                    if '"WARMUP_START"' in line:
                        uid=get('pod',self.worker)['metadata']['uid'] if self.backend=='shm' else self.uid
                        info=k(['exec','-i','-n',NS,'evidence-c28-affinity','--','python3','-',uid],input=(ROOT/'experiments/evidence/campaign_runtime_info.py').read_text())
                        save(self.out/'runtime-libraries.json',json.loads(info))
                code=p.wait(timeout=900)
            finally:
                watchdog.cancel()
                if p.poll() is None:p.terminate()
        rows=[]
        for line in (self.out/'stdout.jsonl').read_text().splitlines():
            if line.startswith('{'):rows.append(json.loads(line))
        result=next((r for r in reversed(rows) if r.get('event')=='RESULT'),{})
        save(self.out/'metrics.json',{'exit_code':code,'result':result,'execution':'PASS' if code==0 and result else 'FAIL','enforcement':'NOT_EVALUATED'})
        self.note('EXIT',exit_code=code,result=result)
        if code or not result or result['status']!='PASS':raise RuntimeError('Workload failed: '+self.name)
        return result
    def close(self):
        if not self.uid:return
        if self.backend=='shm':
            c=get('flytsharedmemorychannel',self.name+'-channel')
            if c['metadata']['uid']!=self.uid:raise RuntimeError('UID changed')
            k(['patch','flytsharedmemorychannel',self.name+'-channel','-n',NS,'--type=json','-p',json.dumps([{'op':'test','path':'/metadata/uid','value':self.uid},{'op':'add','path':'/spec/drain','value':True}])])
            wait(lambda:get('flytsharedmemorychannel',self.name+'-channel').get('status',{}).get('phase')=='Released')
        else:
            if get('pod',self.name)['metadata']['uid']!=self.uid:raise RuntimeError('UID changed')
            k(['delete','pod',self.name,'-n',NS,'--wait=true','--timeout=60s'])
        save(self.out/'cleanup.json',{'released':True,'utc_seconds':time.time(),'uid':self.uid});self.note('RELEASED')
