from infra import *
import profiles
def idle():
 x=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 assert GPU not in x,('GPU1 already has compute processes',x)

def start(mode,label):
 assert mode=='V'
 idle();s={'mode':mode,'label':label,'namespace':VNS}
 s.update(vm_start(NAME+'-shm',VNS));s['namespace']=VNS
 ch=wait(lambda:x if (x:=get('sharedmemorychannel',NAME+'-shm',VNS)).get('status',{}).get('phase')=='Ready' else None,240)
 pods=json.loads(k('get','pods','-n',VNS,'-o','json'))['items'];p=next(p for p in pods if p['metadata']['uid']==ch['status']['workerPodUID'])
 s.update(server=p['metadata']['name'],server_uid=p['metadata']['uid']);s['server_pinning']=pin(s['server_uid'],list(range(12,16)))
 wait(lambda:S.run(s['ssh']+['sudo test -S /run/vmweave/gpu.sock'],capture_output=True).returncode==0,180)
 save(O/'evidence'/(label+'-channel.json'),ch)
 (O/'evidence'/(label+'-broker.txt')).write_text(remote(s,'cat /etc/vmweave/guest-broker.env; sudo systemctl status vmweave-guest-broker --no-pager; ls -l /dev/nvidia* 2>/dev/null || true'))
 s['mode']=mode;s['label']=label
 if mode=='V':
  s['profile']=profiles.ACTIVE; profiles.audit(s)
 actual=k('exec','-n',s['namespace'],s['server'],'--','nvidia-smi','--query-gpu=uuid,memory.total','--format=csv,noheader')
 assert [line.split(',')[0].strip() for line in actual.splitlines() if line.startswith('GPU-')]==[GPU],actual
 save(O/'evidence'/(label+'-pod.json'),get('pod',s['server'],s['namespace']))
 if mode!='V':save(O/'evidence'/(label+'-claim.json'),get('resourceclaim',s['server']))
 else:save(O/'evidence'/(label+'-claim.json'),get('resourceclaim',ch['status']['claimName'],VNS))
 if mode!='N':
  copy(s,[B/'artifacts'/mode/'probe'],'/opt/comm/artifacts/'+mode+'/')
  copy(s,[B/'artifacts/sequence.cubin',B/'artifacts/sequence.ptx'],'/opt/comm/artifacts/')
  s['clocks']=[]
  for _ in range(5):
   a=time.time_ns();g=int(remote(s,'date +%s%N').strip());b=time.time_ns();s['clocks'].append({'host_before_ns':a,'guest_ns':g,'host_after_ns':b})
  s['guest_info']=remote(s,'cat /etc/os-release; uname -r; ip -brief link; lspci -nn; test ! -e /dev/nvidia0')
 import base64
 (O/'evidence'/(label+'-layout.bin')).write_bytes(base64.b64decode(remote(s,'sudo base64 -w0 /run/vmweave/layout.bin')))
 (O/'evidence'/(label+'-client-sha256.txt')).write_text(remote(s,'sha256sum /opt/comm/artifacts/V/probe /opt/comm/artifacts/V/libvmweave_guest.so /opt/vmweave/lib/libvmweave_guest.so'))
 save(B/'active.json',s)
 save(O/'evidence'/(label+'-session.json'),{k:v for k,v in s.items() if k not in ['ssh','scp']})
 return s

def command(s,order,pilot=False):
 mode=s['mode'];label=s['label'];out='/work/'+label if mode=='N' else '/tmp/comm/'+label
 if mode=='N':
  k('exec','-n',NS,s['server'],'--','mkdir','-p',out)
  return ['kubectl','exec','-n',NS,s['server'],'--','taskset','-c','8-11','env','LD_LIBRARY_PATH=/work/N:/usr/local/cuda/lib64','/work/N/probe','/work/sequence.ptx',out,','.join(map(str,order)),'30','0' if pilot else '10','1' if pilot else '0']
 remote(s,'mkdir -p '+out)
 env={'LD_LIBRARY_PATH':'/opt/comm/artifacts/'+mode}
 if mode=='V':env.update(VMWEAVE_BROKER_SOCKET='/run/vmweave/gpu.sock',**profiles.application())
 if mode=='F':env.update(SM_CORE='188')
 if mode=='L':env.update(LUPINE_SERVER=s['server_ip']+':14833')
 return s['ssh']+[shlex.join(['sudo','timeout','-k','15','1800','env','-u','LD_PRELOAD',*[k+'='+v for k,v in env.items()],'/opt/comm/artifacts/'+mode+'/probe','/opt/comm/artifacts/sequence.'+('cubin' if mode=='F' else 'ptx'),out,','.join(map(str,order)),'30','0' if pilot else '10','1' if pilot else '0'])]

def close(s):
 profiles.prepare_next(s)
 vm_stop(s['name'],s['namespace'])
 idle();save(O/'evidence'/(s['label']+'-released.json'),{'utc':time.time(),'gpu_idle':True,'session_closed':True});(B/'active.json').unlink(missing_ok=True)
