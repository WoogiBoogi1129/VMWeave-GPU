from common import *
import shlex
INNER='nested-validation'
VM='vw-k8s-worker-01'
EXPECTED_GPU='GPU-7d708c42-8d4a-16d5-0746-474567157aa3'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def iobj(*args):return json.loads(inner(*args,'-o','json'))
def iapply(value):return ssh('cp','sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf apply -f -',input=json.dumps(value))
def ready_nodes():
    nodes=iobj('get','nodes')['items']
    return len(nodes)==2 and all(any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']) for n in nodes)
def observation():
    c=obj('get','sharedmemorychannel',VM,'-n',NS);s=c['status'];worker=s['resourcePrefix']+'-worker'
    code="""import os,json
out=[]
for p in os.listdir('/proc'):
 if p.isdigit():
  try:
   cmd=open('/proc/'+p+'/cmdline','rb').read().replace(bytes([0]),b' ').decode()
   first=cmd.split(' ')[0]
   if first.endswith('shm-session-worker'):out.append({'pid':int(p),'command':cmd})
  except (OSError,UnicodeError):pass
print(json.dumps(out))"""
    procs=json.loads(k('exec','-n',NS,worker,'--','python3','-c',code))
    raw=run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_memory','--format=csv,noheader,nounits'])
    rows=[]
    for line in raw.splitlines():
        cols=[x.strip() for x in line.split(',')]
        if len(cols)!=4:continue
        pid=int(cols[1])
        try:
            cg=pathlib.Path(f'/proc/{pid}/cgroup').read_text()
            if s['workerPodUID'] not in cg and s['workerPodUID'].replace('-','_') not in cg:continue
            status=pathlib.Path(f'/proc/{pid}/status').read_text()
            ids=[int(x) for x in next(x for x in status.splitlines() if x.startswith('NSpid:')).split()[1:]]
            rows.append({'gpu_uuid':cols[0],'host_pid':pid,'namespace_pids':ids,'cgroup':cg,'memory_MiB':cols[3],'child_matches':any(p['pid']==ids[-1] and '--session' in p['command'] for p in procs)})
        except FileNotFoundError:continue
    if any(r['gpu_uuid']!=EXPECTED_GPU for r in rows):raise RuntimeError('unexpected GPU UUID')
    return {'at':now(),'channel_uid':c['metadata']['uid'],'channel_status':s,'worker':worker,'processes':procs,'gpu_processes':rows}
def quiescent(label,timeout=60):
    start=time.monotonic()
    while True:
        o=observation()
        if not o['gpu_processes'] and not any('--session' in p['command'] for p in o['processes']):
            o['elapsed_seconds']=time.monotonic()-start;save('gpu/'+label+'-reclaimed.json',o);return o
        if time.monotonic()-start>timeout:save('gpu/'+label+'-reclaim-failed.json',o);raise RuntimeError('CUDA child not reclaimed')
        time.sleep(1)
def start(name,mode=None,socket=True):
    quiescent(name+'-before')
    image=json.loads((OUT/'inventory/workload-image.json').read_text())
    gid=int(ssh('worker','getent group vmweave').split(':')[2])
    spec={'restartPolicy':'Never','automountServiceAccountToken':False,'nodeSelector':{'kubernetes.io/hostname':VM},'terminationGracePeriodSeconds':10,'securityContext':{'runAsUser':1000,'runAsGroup':gid,'runAsNonRoot':True,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'gpu','image':image['RepoDigests'][0],'imagePullPolicy':'Never','env':[{'name':'VMWEAVE_BROKER_SOCKET','value':'/run/vmweave/gpu.sock'},{'name':'LD_LIBRARY_PATH','value':'/opt/vmweave/lib'}],'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'1','memory':'512Mi'}}}]}
    if mode:spec['containers'][0]['args']=[mode]
    if socket:
        spec['containers'][0]['volumeMounts']=[{'name':'broker','mountPath':'/run/vmweave','readOnly':True}]
        spec['volumes']=[{'name':'broker','hostPath':{'path':'/run/vmweave','type':'Directory'}}]
    job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'namespace':INNER},'spec':{'backoffLimit':0,'activeDeadlineSeconds':360,'template':{'metadata':{'labels':{'test':name}},'spec':spec}}}
    save('gpu/'+name+'-job.json',job)
    if inner('get','job',name,'-n',INNER,'--ignore-not-found','-o','name').strip():raise RuntimeError('refuse duplicate Job '+name)
    iapply(job);began=time.monotonic()
    while time.monotonic()-began<120:
        pods=iobj('get','pods','-n',INNER,'-l','job-name='+name)['items']
        if pods:
            pod=pods[0];pname=pod['metadata']['name']
            if pod.get('status',{}).get('containerStatuses'):
                actual=pod['status']['containerStatuses'][0].get('imageID','')
                if actual and not any(value.removeprefix('sha256:') in actual for value in (image['Id'],image['Digest'])):
                    raise RuntimeError('workload image mismatch '+actual)
            if pod['status']['phase'] in ('Running','Succeeded','Failed'):
                log=inner('logs',pname,'-n',INNER)
                if 'READY_FOR_OBSERVATION' in log or pod['status']['phase'] in ('Succeeded','Failed'):
                    save('gpu/'+name+'-pod-start.json',pod);save('gpu/'+name+'-initial.log',log)
                    save('timings/'+name+'-start.json',{'at':now(),'create_to_observation_seconds':time.monotonic()-began})
                    if 'READY_FOR_OBSERVATION' in log:
                        obs=observation();save('gpu/'+name+'-active.json',obs)
                        if not any(r['child_matches'] for r in obs['gpu_processes']):raise RuntimeError('GPU PID attribution missing')
                    return pname
        time.sleep(1)
    save('gpu/'+name+'-timeout.json',pods);raise RuntimeError('Pod start timed out')
def finish(name,pod,release=True,expect_failure=False,reclaim=True):
    if release:inner('exec',pod,'-n',INNER,'--','touch','/tmp/run')
    began=time.monotonic()
    while time.monotonic()-began<100:
        p=iobj('get','pod',pod,'-n',INNER)
        if p['status']['phase'] in ('Succeeded','Failed'):break
        time.sleep(1)
    else:save('gpu/'+name+'-hung.json',p);raise RuntimeError('GPU workload timed out')
    logs=inner('logs',pod,'-n',INNER)
    save('gpu/'+name+'-final.log',logs);save('gpu/'+name+'-pod-final.json',p)
    failed=p['status']['phase']=='Failed'
    if expect_failure!=failed:raise RuntimeError(name+' unexpected completion: '+p['status']['phase'])
    if release and not expect_failure:
        records=[json.loads(x) for x in logs.splitlines() if x.startswith('{')]
        result=next(x for x in records if x['event']=='RESULT')
        assert result['mismatches']==0 and result['elements']==8388608 and result['kernel_launches']==1
    terminal_observed=time.monotonic()-began
    q=quiescent(name) if reclaim else None
    finished_at=p['status']['containerStatuses'][0]['state']['terminated']['finishedAt']
    reclamation=(datetime.datetime.fromisoformat(q['at'])-datetime.datetime.fromisoformat(finished_at.replace('Z','+00:00'))).total_seconds() if q else None
    save('timings/'+name+'-finish.json',{'at':now(),'release_to_terminal_seconds':terminal_observed,'container_finished_at':finished_at,'exit_to_reclaim_observed_seconds':reclamation})
    if reclaim:assert reclamation<=60,'reclamation exceeded 60 seconds'
    return p
def normal(name):return finish(name,start(name))
def create_namespace():iapply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':INNER}})
if __name__=='__main__':
    import sys
    create_namespace()
    normal(sys.argv[1])
