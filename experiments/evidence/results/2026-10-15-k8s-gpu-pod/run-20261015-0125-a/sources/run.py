#!/usr/bin/env python3
"""Bounded, single-Pod GPU execution experiment; no VM restart or fault injection."""
import argparse,datetime,fcntl,hashlib,json,os,pathlib,shlex,subprocess,sys,time
from zoneinfo import ZoneInfo
REPO=pathlib.Path(__file__).resolve().parents[2]
NS='vmweave-test-a'; VM='vmweave-k8s-01'; INNER='vmweave-gpu-validation'; POD='vmweave-gpu-pod-check'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def append(path,data):
 with path.open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX);f.write(json.dumps(data,ensure_ascii=False)+'\n')
def save(path,data):path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
class Run:
 def __init__(self,root):
  self.root=pathlib.Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
  self.cfg=json.loads((REPO/'.local/k8s-gpu-pod-20261015/connection.json').read_text())
 def call(self,args,guest=False,input=None,check=True,show=False):
  command=shlex.join(args);argv=args
  if guest:
   argv=['ssh','-i',self.cfg['key'],'-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+self.cfg['known_hosts'],'ubuntu@'+self.cfg['ip'],command]
  if show:print(('[Guest] ' if guest else '[Host] ')+'$ '+command,flush=True)
  started=now();p=subprocess.run(argv,input=input,text=True,capture_output=True,timeout=35,cwd=REPO)
  append(self.root/'commands.jsonl',{'started':started,'finished':now(),'location':'Guest' if guest else 'Host','command':command,'stdin':input,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
  if show:
   print(p.stdout,end='',flush=True)
   if p.stderr:print(p.stderr,end='',file=sys.stderr,flush=True)
  if check and p.returncode:raise RuntimeError(f'{command}: {p.returncode}: {p.stderr}')
  return p
 def outer(self,kind,name=None):return json.loads(self.call(['kubectl','get',kind,*([name] if name else []),'-n',NS,'-o','json']).stdout)
 def inner(self,kind,name=None,check=True):
  p=self.call(['sudo','kubectl','get',kind,*([name] if name else []),'-n',INNER,'-o','json'],guest=True,check=check)
  return json.loads(p.stdout) if p.returncode==0 else None
 def gpu(self,label,show=False):
  c=self.outer('sharedmemorychannel',VM);worker=c['status']['resourcePrefix']+'-worker';uuid=c['status']['gpuUUID']
  code="import os,json;out=[]\nfor s in os.listdir('/proc'):\n if s.isdigit():\n  try:\n   v=open('/proc/'+s+'/cmdline','rb').read().replace(bytes([0]),b' ').decode()\n   if v.startswith('/opt/flyt/bin/flyt-shm-session-worker') or v.startswith('flyt-shm-session-worker --session'):out.append({'pid':int(s),'command':v})\n  except (OSError,UnicodeError):pass\nprint(json.dumps(out))"
  worker_procs=json.loads(self.call(['kubectl','exec','-n',NS,worker,'--','python3','-c',code]).stdout)
  raw=self.call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_memory','--format=csv,noheader,nounits']).stdout
  rows=[]
  for line in raw.splitlines():
   cols=[v.strip() for v in line.split(',')]
   if len(cols)!=4 or cols[0]!=uuid:continue
   pid=int(cols[1]);row={'gpu_uuid':uuid,'host_pid':pid,'process':cols[2],'used_memory_mib':cols[3]}
   try:
    status=pathlib.Path(f'/proc/{pid}/status').read_text();cg=pathlib.Path(f'/proc/{pid}/cgroup').read_text()
    nsids=[int(x) for x in next(x for x in status.splitlines() if x.startswith('NSpid:')).split()[1:]]
    row.update(namespace_pids=nsids,cgroup=cg,worker_uid_matches=c['status']['workerPodUID'].replace('-','_') in cg or c['status']['workerPodUID'] in cg)
    row['cuda_child_matches']=row['worker_uid_matches'] and any(x['pid']==nsids[-1] and '--session' in x['command'] for x in worker_procs)
   except (OSError,StopIteration) as e:row['mapping_error']=str(e)
   rows.append(row)
  data={'at':now(),'worker':worker,'worker_uid':c['status']['workerPodUID'],'channel_uid':c['metadata']['uid'],'gpu_uuid':uuid,'worker_processes':worker_procs,'gpu_processes':rows}
  (self.root/'worker').mkdir(exist_ok=True);save(self.root/'worker'/f'{label}.json',data)
  if show:
   print('[Host] Live Worker / GPU process observation (nvidia-smi + /proc NSpid/cgroup)',flush=True)
   print(json.dumps(data,indent=2),flush=True)
  return data
 def header(self,stage):
  print('RUN:',self.root.name,' STAGE:',stage,flush=True)
  print('CAPTURE TIME:',datetime.datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),flush=True)
  print('HOST namespace:',NS,' VM:',VM,' GUEST namespace:',INNER,' POD:',POD,flush=True)
 def view(self,stage):
  self.header(stage)
  if stage=='S01':
   self.call(['kubectl','get','vm',VM,'-n',NS],show=True)
   self.call(['kubectl','get','sharedmemorychannel',VM,'-n',NS],show=True)
   c=self.outer('sharedmemorychannel',VM);self.call(['kubectl','get','pod',c['status']['resourcePrefix']+'-worker','-n',NS],show=True)
   self.call(['sudo','kubectl','get','nodes'],guest=True,show=True)
   self.call(['systemctl','is-active','vmweave-guest-broker'],guest=True,show=True)
  elif stage=='S02':
   spec=json.loads((self.root/'pod.yaml').read_text());container=spec['spec']['containers'][0]
   print('Actual submitted Pod configuration:',flush=True)
   print(json.dumps({'image':container['image'],'securityContext':spec['spec']['securityContext'],'containerSecurity':container['securityContext'],'volumes':spec['spec']['volumes'],'environment':container['env']},indent=2),flush=True)
   self.call(['sudo','kubectl','create','-f','-'],guest=True,input=json.dumps(spec),show=True)
   self.call(['sudo','kubectl','get','pod',POD,'-n',INNER,'-o','wide'],guest=True,show=True)
  elif stage in ['S03','S05','S06']:
   self.call(['sudo','kubectl','get','pod',POD,'-n',INNER,'-o','wide'],guest=True,show=True)
   self.call(['sudo','kubectl','logs',POD,'-n',INNER,'--tail=16','--timestamps'],guest=True,show=True,check=stage!='S06')
   p=self.inner('pod',POD);save(self.root/f'pod-{stage}.json',p)
   print('Container status:',json.dumps(p['status'].get('containerStatuses',[])),flush=True)
  elif stage=='S04':self.gpu('live-S04',show=True)
  elif stage=='S07':
   self.call(['sudo','kubectl','delete','pod',POD,'-n',INNER,'--wait=true','--timeout=25s'],guest=True,show=True)
   self.call(['sudo','kubectl','get','pods','-n',INNER],guest=True,show=True)
   self.call(['kubectl','get','vm',VM,'-n',NS],show=True)
   self.call(['kubectl','get','sharedmemorychannel',VM,'-n',NS],show=True)
   self.call(['sudo','kubectl','get','nodes'],guest=True,show=True)
  else:raise ValueError(stage)
 def capture(self,stage):
  command=shlex.join([sys.executable,str(pathlib.Path(__file__).resolve()),'view',str(self.root),stage])
  env={**os.environ,'NODE_PATH':str(REPO/'.local/evidence-20260924/tools/node_modules')}
  p=subprocess.run(['node',str(REPO/'experiments/k8s-gpu-pod/capture_live.cjs'),str(self.root),stage,command],cwd=REPO,env=env,text=True,capture_output=True,timeout=65)
  (self.root/f'capture-{stage}.txt').write_text(p.stdout+p.stderr)
  if p.returncode:raise RuntimeError('capture '+stage+': '+p.stdout+p.stderr)
 def prepare(self):
  c=self.outer('sharedmemorychannel',VM);v=self.outer('vm',VM);w=self.outer('pod',c['status']['resourcePrefix']+'-worker')
  assert c['status']['phase']=='Ready' and v['status']['ready'] and w['status']['phase']=='Running'
  self.call(['systemctl','is-active','vmweave-guest-broker'],guest=True)
  gid=int(self.call(['getent','group','vmweave'],guest=True).stdout.split(':')[2])
  nodes=json.loads(self.call(['sudo','kubectl','get','nodes','-o','json'],guest=True).stdout)
  assert all(any(x['type']=='Ready' and x['status']=='True' for x in n['status']['conditions']) for n in nodes['items'])
  system=json.loads(self.call(['sudo','kubectl','get','pods','-n','kube-system','-o','json'],guest=True).stdout)
  assert all(any(x['type']=='Ready' and x['status']=='True' for x in p['status'].get('conditions',[])) for p in system['items'])
  self.call(['sudo','kubectl','exec','-n','vmweave-validation','client','--','nslookup','kubernetes.default.svc.cluster.local'],guest=True)
  self.call(['sudo','kubectl','exec','-n','vmweave-validation','client','--','wget','-qO-','http://web'],guest=True)
  self.call(['test','-S','/run/vmweave/gpu.sock'],guest=True)
  self.call(['stat','-c','%U %G %a %n','/run/vmweave','/run/vmweave/gpu.sock'],guest=True)
  before=self.gpu('before');assert not any('--session' in x['command'] for x in before['worker_processes'])
  ns={'apiVersion':'v1','kind':'Namespace','metadata':{'name':INNER}}
  self.call(['sudo','kubectl','apply','-f','-'],guest=True,input=json.dumps(ns))
  self.call(['sudo','kubectl','get','pod',POD,'-n',INNER,'--ignore-not-found','-o','name'],guest=True)
  image=self.cfg['image']
  spec={'apiVersion':'v1','kind':'Pod','metadata':{'name':POD,'namespace':INNER,'labels':{'experiment':'vmweave-gpu-pod-check','run-id':self.root.name}},'spec':{'restartPolicy':'Never','activeDeadlineSeconds':300,'automountServiceAccountToken':False,'securityContext':{'runAsUser':1000,'runAsGroup':gid,'runAsNonRoot':True,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'gpu','image':image,'imagePullPolicy':'Never','env':[{'name':'FLYT_BROKER_SOCKET','value':'/run/vmweave/gpu.sock'},{'name':'LD_LIBRARY_PATH','value':'/opt/flyt/lib'}],'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},'resources':{'requests':{'cpu':'100m','memory':'64Mi'},'limits':{'cpu':'1','memory':'256Mi'}},'volumeMounts':[{'name':'broker','mountPath':'/run/vmweave','readOnly':True}]}],'volumes':[{'name':'broker','hostPath':{'path':'/run/vmweave','type':'Directory'}}]}}
  save(self.root/'pod.yaml',spec) # JSON is a YAML subset; preserve exact submitted object.
  env={'run_id':self.root.name,'started':now(),'source_commit':self.call(['git','rev-parse','HEAD']).stdout.strip(),'image':image,'gid':gid,'vm':{'name':VM,'uid':v['metadata']['uid'],'resources':v['spec']['template']['spec']['domain'].get('resources')},'channel':{'uid':c['metadata']['uid'],'status':c['status']},'worker':{'name':w['metadata']['name'],'uid':w['metadata']['uid'],'image':w['spec']['containers'][0]['image']},'nodes':nodes,'system_pods':system,'clocks':{}}
  for guest in [False,True]:env['clocks']['guest' if guest else 'host']={'time':self.call(['date','--iso-8601=seconds'],guest=guest).stdout.strip(),'ntp':self.call(['timedatectl','show','-p','NTPSynchronized'],guest=guest).stdout.strip()}
  env['artifact_hashes']={name:hashlib.sha256((REPO/'.local/k8s-gpu-pod-20261015'/name).read_bytes()).hexdigest() for name in ['gpu-pod-check','libflyt_guest.so','pod-image.oci']}
  save(self.root/'environment.json',env);save(self.root/'channel-before.json',{'uid':c['metadata']['uid'],'status':c['status']})
 def monitor(self):
  deadline=time.monotonic()+320;index=0
  while time.monotonic()<deadline:
   p=self.inner('pod',POD,check=False)
   if p:
    append(self.root/'pod-states.jsonl',{'observed_at':now(),'pod':p})
    logs=self.call(['sudo','kubectl','logs',POD,'-n',INNER,'--timestamps'],guest=True,check=False)
    if logs.returncode==0:(self.root/'container.log').write_text(logs.stdout)
    if p['status']['phase'] in ['Succeeded','Failed']:return
    if p['status']['phase']=='Running':
     try:self.gpu('sample-'+str(index))
     except Exception as e:append(self.root/'observation-errors.jsonl',{'at':now(),'error':str(e)})
   index+=1;time.sleep(1)
  raise RuntimeError('monitor deadline exceeded')
 def execute(self):
  self.prepare();self.capture('S01')
  monitor=subprocess.Popen([sys.executable,__file__,'monitor',str(self.root)],cwd=REPO,stdout=open(self.root/'monitor.txt','w'),stderr=subprocess.STDOUT)
  try:
   self.capture('S02')
   deadline=time.monotonic()+150
   while time.monotonic()<deadline:
    if (self.root/'container.log').exists() and 'GPU_KERNEL_SYNCHRONIZED' in (self.root/'container.log').read_text():break
    p=self.inner('pod',POD)
    if p['status']['phase']=='Failed':raise RuntimeError('GPU Pod failed before GPU execution')
    time.sleep(1)
   else:raise RuntimeError('GPU start deadline exceeded')
   self.capture('S03');self.capture('S04')
   deadline=time.monotonic()+150
   while time.monotonic()<deadline:
    p=self.inner('pod',POD)
    if p['status']['phase'] in ['Succeeded','Failed']:break
    time.sleep(1)
   save(self.root/'pod-final.json',p)
   self.capture('S05')
   monitor.wait(timeout=15)
   events=self.inner('events');save(self.root/'events.json',events)
   c=self.outer('sharedmemorychannel',VM);worker=c['status']['resourcePrefix']+'-worker'
   (self.root/'worker'/'container.txt').write_text(self.call(['kubectl','logs','-n',NS,worker,'--since-time',json.loads((self.root/'environment.json').read_text())['started']]).stdout)
   status=p['status']['containerStatuses'][0];logs=(self.root/'container.log').read_text()
   assert p['status']['phase']=='Succeeded' and status['state']['terminated']['exitCode']==0 and status['restartCount']==0
   assert all(x in logs for x in ['GPU_ACCESS_OK','GPU_MEMORY_ALLOCATED_32MIB','GPU_KERNEL_SYNCHRONIZED','DEVICE_TO_HOST_OK','GPU_RESOURCES_RELEASED','"status":"PASS"'])
   gpu=json.loads((self.root/'worker'/'live-S04.json').read_text());assert any(x.get('cuda_child_matches') for x in gpu['gpu_processes']), 'GPU process attribution missing'
   self.capture('S07')
   after=self.outer('sharedmemorychannel',VM);save(self.root/'channel-after.json',{'uid':after['metadata']['uid'],'status':after['status']})
   assert after['status']['phase']=='Ready'
   result={'status':'PASS','finished':now(),'pod_uid':p['metadata']['uid'],'pod_phase':p['status']['phase'],'image_id':status['imageID'],'exit_code':0,'restarts':0,'gpu_process_attribution':True,'cleanup':'experiment Pod deleted; existing VM/Kubernetes/channel retained','scope':'single nonprivileged GPU Pod creation, execution and completion; no accuracy, lifecycle, concurrency or recovery experiment'}
   save(self.root/'result.json',result)
  except Exception as e:
   save(self.root/'result.json',{'status':'FAIL','at':now(),'error':str(e)})
   try:self.capture('S06');save(self.root/'events.json',self.inner('events'))
   except Exception as capture_error:append(self.root/'observation-errors.jsonl',{'at':now(),'error':str(capture_error)})
   raise
  finally:
   if monitor.poll() is None:monitor.terminate();monitor.wait(timeout=10)
   captures=[]
   for f in sorted((self.root/'terminal').glob('*/capture.json')):
    item=json.loads(f.read_text());item['source']='terminal/'+f.parent.name+'/screen.txt';captures.append(item)
   (self.root/'screenshots').mkdir(exist_ok=True);save(self.root/'screenshots'/'index.json',captures)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['run','view','monitor']);parser.add_argument('root');parser.add_argument('stage',nargs='?');a=parser.parse_args();r=Run(a.root)
 if a.action=='run':r.execute()
 elif a.action=='view':r.view(a.stage)
 else:r.monitor()
