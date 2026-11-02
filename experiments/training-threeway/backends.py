from lab import *
import transition
VMNS='vmweave-test-a'
APPENV={'VMWEAVE_BULK_COPY':'1','VMWEAVE_BULK_DIRECT':'1','VMWEAVE_NATIVE_MEMSET':'1',
        'VMWEAVE_STATE_CACHE':'1','VMWEAVE_MATH_CACHE':'1','VMWEAVE_MIRROR_DEVICE_VA':'1',
        'VMWEAVE_TRACE_REQUESTS':'0','VMWEAVE_BROKER_SOCKET':'/run/vmweave/gpu.sock'}
def flyt_pod():
 mounts=[{'name':'shm','mountPath':'/flyt-channel'}]
 volumes=[{'name':'shm','persistentVolumeClaim':{'claimName':'flyt-shm'}}]
 for name,path,target in [('cuda','/usr/lib/x86_64-linux-gnu/libcuda.so.580.173.02','/usr/local/cuda/lib64/stubs/libcuda.so.1'),('nvml','/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.580.173.02','/usr/local/cuda/lib64/stubs/libnvidia-ml.so.1')]:
  mounts.append({'name':name,'mountPath':target,'readOnly':True});volumes.append({'name':name,'hostPath':{'path':path,'type':'File'}})
 for name,path in [('mps','/run/flyt-mps'),('mps-log','/tmp/flyt-mps-log')]:
  mounts.append({'name':name,'mountPath':path});volumes.append({'name':name,'emptyDir':{}})
 volumes.append({'name':'mongo','emptyDir':{}})
 p={'apiVersion':'v1','kind':'Pod','metadata':{'name':'flyt-server','namespace':NS,'labels':{'experiment':'training-threeway-20261102'},'annotations':{'nvidia.com/use-gpuuuid':GPU}},'spec':{'hostPID':True,'schedulerName':'hami-scheduler','runtimeClassName':'nvidia','nodeSelector':{'kubernetes.io/hostname':'gpu-4'},'automountServiceAccountToken':False,'restartPolicy':'Never','terminationGracePeriodSeconds':15,'containers':[{'name':'server','image':'localhost/flyt-threeway-server@sha256:3ab91091aad3fed7000e305d02fa89b4d61bc36c6d653aa05db1358929709f09','imagePullPolicy':'Never','command':['sleep','43200'],'securityContext':{'runAsUser':0},'resources':{'limits':{'nvidia.com/gpu':1,'nvidia.com/gpumem':8192,'nvidia.com/gpucores':100}},'volumeMounts':mounts},{'name':'mongo','image':'docker.io/library/mongo@sha256:c53852c00c23ca9f23fc39690350ffa9a80e3642fe8f96879726d8da0abe80a7','command':['mongod','--bind_ip','127.0.0.1','--port','28025','--dbpath','/data/db'],'volumeMounts':[{'name':'mongo','mountPath':'/data/db'}]}],'volumes':volumes}}
 save(O/'inventory'/'flyt-server-spec.json',p);create(p)

def idle():
 text=S.check_output(['nvidia-smi','-i',GPU,'--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
 assert not text,('GPU0 has a compute client',text)

def open_mode(mode,label):
 name='tt-'+mode+'-1102';ns=VMNS if mode=='vmweave' else NS
 idle()
 if mode=='passthrough':transition.transition('vfio-pci')
 s=start(name,ns);s.update(mode=mode,label=label)
 if mode=='flyt':
  state=json.loads((B/'flyt-state.json').read_text());state.update(s);save(B/'flyt-state.json',state)
  flyt_pod()
  with (B/('flyt-stack-'+label+'.log')).open('w') as out:S.run(['python3',str(R/'experiments/training-threeway/flyt_stack.py')],stdout=out,stderr=S.STDOUT,check=True,timeout=360)
  s['worker']='flyt-server';pin(s,'flyt-server')
 elif mode=='vmweave':
  ch=wait(lambda:x if (x:=get('sharedmemorychannel',name,ns)).get('status',{}).get('phase')=='Ready' else None)
  pods=json.loads(k('get','pods','-n',ns,'-o','json'))['items']
  p=next(p for p in pods if p['metadata']['uid']==ch['status']['workerPodUID'])
  s['worker']=p['metadata']['name'];pin(s,s['worker'])
  wait(lambda:S.run(s['ssh']+['sudo test -S /run/vmweave/gpu.sock'],capture_output=True).returncode==0)
  save(O/'inventory'/(label+'-vmweave-worker.json'),p)
  save(O/'inventory'/(label+'-channel.json'),ch)
 else:
  pin(s)
  remote(s,'sudo modprobe nvidia; sudo modprobe nvidia_uvm')
  code="import os,stat;from pathlib import Path;d={a[1]:int(a[0]) for l in Path('/proc/devices').read_text().splitlines() if len(a:=l.split())==2 and a[0].isdigit()};[(os.mknod(p,stat.S_IFCHR|0o666,os.makedev(ma,mi)) if not Path(p).exists() else None) for p,ma,mi in [('/dev/nvidia0',195,0),('/dev/nvidiactl',195,255),('/dev/nvidia-uvm',d['nvidia-uvm'],0)]]"
  remote(s,'sudo python3 -c '+shlex.quote(code))
  actual=remote(s,'sudo env LD_LIBRARY_PATH=/opt/flyt-evidence/driver /opt/flyt-evidence/driver/nvidia-smi --query-gpu=uuid --format=csv,noheader').strip();assert actual==GPU,actual
 remote(s,'mkdir -p /tmp/training')
 copy(s,[R/'experiments/training-threeway/bench.py'],'/tmp/training/')
 save(B/'active.json',s)
 save(O/'inventory'/(label+'-'+mode+'-session.json'),{k:v for k,v in s.items() if k not in ['ssh','scp']})
 library_hashes=remote(s,'sha256sum /opt/flyt-cuda-libs/libcudart.so.12 /opt/flyt-cuda-libs/libcublas.so.12')
 (O/'inventory'/(label+'-'+mode+'-cuda-libraries.txt')).write_text(library_hashes)
 if mode in ['vmweave','flyt']:
  args=['exec','-n',ns,s['worker']]
  if mode=='flyt':args+=['-c','server']
  native_hashes=k(*args,'--','sh','-c','sha256sum /usr/local/cuda/lib64/libcudart.so.12 /usr/local/cuda/lib64/libcublas.so.12')
  assert [l.split()[0] for l in native_hashes.splitlines()]==[l.split()[0] for l in library_hashes.splitlines()]
  (O/'inventory'/(label+'-'+mode+'-backend-cuda-libraries.txt')).write_text(native_hashes)
 env_info=remote(s,'uname -r; sha256sum /tmp/training/bench.py; env LD_LIBRARY_PATH=/opt/flyt-cuda-libs:/opt/flyt-evidence/driver /opt/torch-venv/bin/python -c '+shlex.quote('import torch; print(torch.__version__, torch.version.cuda)'))
 (O/'inventory'/(label+'-'+mode+'-environment.txt')).write_text(env_info)
 return s

def close_mode(s):
 mode=s['mode']
 stop(s['name'],s['namespace'])
 if mode=='vmweave':wait(lambda:get('sharedmemorychannel',s['name'],s['namespace']).get('status',{}).get('phase')=='Stopped')
 elif mode=='flyt':
  k('delete','pod','flyt-server','-n',NS,'--wait=true','--timeout=90s')
 elif mode=='passthrough':transition.transition('nvidia')
 idle();save(O/'inventory'/(s['label']+'-'+mode+'-stopped.json'),{'utc':time.time(),'GPU0_idle':True})
 (B/'active.json').unlink(missing_ok=True)

def command(s,args,timeout=600):
 env=['env','-u','LD_PRELOAD','-u','LD_LIBRARY_PATH']
 if s['mode']=='vmweave':env += [k+'='+v for k,v in APPENV.items()]+['LD_PRELOAD=/opt/vmweave/lib/libvmweave_guest.so','LD_LIBRARY_PATH=/opt/vmweave/lib:/opt/flyt-cuda-libs']
 elif s['mode']=='flyt':env += ['LD_LIBRARY_PATH=/tmp/flyt-test:/opt/flyt-cuda-libs']
 else:env += ['LD_LIBRARY_PATH=/opt/flyt-evidence/driver:/opt/flyt-cuda-libs']
 return s['ssh']+[shlex.join(['sudo','timeout','-s','TERM','-k','10',str(timeout),*env,'/opt/torch-venv/bin/python','-u','/tmp/training/bench.py',*map(str,args)])]


def recover_start(mode):
 """Recover only the fixed test names after startup fails before returning a session."""
 name='tt-'+mode+'-1102';ns=VMNS if mode=='vmweave' else NS
 if get('vm',name,ns):stop(name,ns)
 if mode=='flyt' and get('pod','flyt-server'):
  k('delete','pod','flyt-server','-n',NS,'--wait=true','--timeout=90s')
 if mode=='vmweave':wait(lambda:get('sharedmemorychannel',name,ns).get('status',{}).get('phase')=='Stopped')
 if mode=='passthrough' and Path('/sys/bus/pci/devices/0000:40:00.0/driver').resolve().name=='vfio-pci':transition.transition('nvidia')
 (B/'active.json').unlink(missing_ok=True)
