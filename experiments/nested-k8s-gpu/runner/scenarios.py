from gpu import *
import sys
def identity(role):
    name='vw-k8s-'+role+'-01'
    v=obj('get','vmi',name,'-n',NS)
    return {'at':now(),'vmi_uid':v['metadata']['uid'],'vmi_status':v['status'],'node':iobj('get','node',name),'cluster_uid':iobj('get','ns','kube-system')['metadata']['uid'],'disk_markers':ssh(role,'cat /etc/machine-id; sudo sha256sum /etc/kubernetes/pki/ca.crt; cat /home/ubuntu/nested/persistent-marker'),'channel':obj('get','sharedmemorychannel',VM,'-n',NS)['status']}
def recreate(role,label):
    name='vw-k8s-'+role+'-01'
    before=identity(role);save('lifecycle/'+label+'-before.json',before)
    began=time.monotonic();save('timings/'+label+'-recovery-start.json',{'at':now()})
    k('patch','vm',name,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Halted"}}')
    k('wait','--for=delete','vmi/'+name,'-n',NS,'--timeout=180s')
    if role=='worker':
        for _ in range(60):
            stop=obj('get','sharedmemorychannel',VM,'-n',NS)
            if stop.get('status',{}).get('phase')=='Stopped':break
            time.sleep(2)
        else:save('lifecycle/'+label+'-detach-failed.json',stop);raise RuntimeError('Channel did not reach Stopped')
        save('lifecycle/'+label+'-halted-channel.json',stop)
    else:
        try:ssh('worker','curl --max-time 5 -skf https://10.245.0.10:6443/readyz',stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:save('lifecycle/'+label+'-api-unavailable.log',e.output+'\nexit='+str(e.returncode))
        else:raise RuntimeError('CP API unexpectedly available while halted')
    k('patch','vm',name,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Always"}}')
    while time.monotonic()-began<500:
        try:
            if role=='worker':
                c=obj('get','sharedmemorychannel',VM,'-n',NS)['status']
                if c.get('phase')!='Ready':time.sleep(2);continue
                ssh(role,'sudo systemctl is-active --quiet vmweave-guest-broker && test -S /run/vmweave/gpu.sock',stderr=subprocess.DEVNULL)
            if ready_nodes():
                boot=ssh(role,'cat /proc/sys/kernel/random/boot_id',stderr=subprocess.DEVNULL).strip()
                if iobj('get','node',name)['status']['nodeInfo']['bootID']==boot:break
        except (subprocess.CalledProcessError,KeyError):pass
        time.sleep(2)
    else:raise RuntimeError('VM recovery timeout')
    after=identity(role);save('lifecycle/'+label+'-after.json',after)
    assert before['vmi_uid']!=after['vmi_uid']
    assert before['node']['metadata']['uid']==after['node']['metadata']['uid']
    assert before['cluster_uid']==after['cluster_uid'] and before['disk_markers']==after['disk_markers']
    if role=='worker':
        for key in ('allocation','generation','workerPodUID'):
            assert before['channel'][key]!=after['channel'][key],key+' unchanged'
    normal(label.lower()+'-recovery')
    elapsed=time.monotonic()-began
    save('timings/'+label+'-recovered.json',{'at':now(),'elapsed_seconds':elapsed,'within_600_seconds':elapsed<=600})
    assert elapsed<=600
def basic():
    normal('g1-a');normal('g1-b')
def negative():
    pod=start('g2-no-socket',socket=False)
    finish('g2-no-socket',pod,release=False,expect_failure=True)
    obs=observation();save('gpu/g2-no-session.json',obs);assert not obs['gpu_processes']
def g4():
    for mode in ('delete','sigkill'):
        name='g4-'+mode;pod=start(name)
        if mode=='delete':
            # Orphan the single running Pod first: Job controller must not retry deletion.
            inner('delete','job',name,'-n',INNER,'--cascade=orphan','--wait=true')
            began=time.monotonic()
            inner('delete','pod',pod,'-n',INNER,'--wait=true','--timeout=60s')
            q=quiescent(name);elapsed=time.monotonic()-began
            save('timings/'+name+'-termination.json',{'at':now(),'delete_to_reclaimed_seconds':elapsed})
            assert elapsed<=60
        else:
            container=iobj('get','pod',pod,'-n',INNER)['status']['containerStatuses'][0]['containerID'].split('://',1)[1]
            # Send from the guest's ancestor PID namespace; PID 1 may ignore
            # signals sent by another process in its own container namespace.
            code="""import os,json,signal
matches=[]
for pid in os.listdir('/proc'):
 if not pid.isdigit():continue
 try:
  cmd=open('/proc/'+pid+'/cmdline','rb').read().split(bytes([0]))[0]
  cg=open('/proc/'+pid+'/cgroup').read()
  if cmd==b'/opt/vmweave/bin/correctness' and CONTAINER in cg:
   matches.append({'pid':int(pid),'cgroup':cg,'status':open('/proc/'+pid+'/status').read()})
 except FileNotFoundError:pass
assert len(matches)==1,matches
print(json.dumps(matches),flush=True)
os.kill(matches[0]['pid'],signal.SIGKILL)
""".replace('CONTAINER',repr(container))
            save('gpu/'+name+'-signal.json',json.loads(ssh('worker','sudo python3 -c '+shlex.quote(code))))
            p=finish(name,pod,release=False,expect_failure=True)
            assert p['status']['containerStatuses'][0]['state']['terminated']['exitCode']==137
        normal(name+'-next')
def g5():
    pod=start('g5-active');before=observation()
    service_before=ssh('worker','sudo systemctl show kubelet -p MainPID -p ActiveState')
    began=time.monotonic();ssh('worker','sudo systemctl restart kubelet')
    while time.monotonic()-began<120:
        if ready_nodes():break
        time.sleep(1)
    else:raise RuntimeError('kubelet recovery timeout')
    save('recovery/G5.json',{'before':before,'after':observation(),'service_before':service_before,'service_after':ssh('worker','sudo systemctl show kubelet -p MainPID -p ActiveState'),'elapsed_seconds':time.monotonic()-began,'pod':iobj('get','pod',pod,'-n',INNER)})
    finish('g5-active',pod);normal('g5-next')
def q1():
    pod=start('q1-overquota',mode='--quota')
    try:finish('q1-overquota',pod,release=False)
    except RuntimeError as e:
        quiescent('q1-failed');normal('q1-small');raise
    logs=inner('logs',pod,'-n',INNER)
    assert any(json.loads(x).get('cuda_code')==2 for x in logs.splitlines() if x.startswith('{'))
    normal('q1-small')
def g6():
    pod=start('g6-active')
    save('recovery/G6-injection-start.json',{'at':now(),'observation':observation()})
    ssh('worker','sudo systemctl stop vmweave-guest-broker')
    save('recovery/G6-broker-stopped.txt',ssh('worker','sudo systemctl show vmweave-guest-broker -p ActiveState -p Restart; sudo journalctl -u vmweave-guest-broker --no-pager -n 60'))
    finish('g6-active',pod,expect_failure=True,reclaim=False)
    save('recovery/G6-after-fault.json',observation())
    recreate('worker','G6')
def main():
    assert json.loads((OUT/'cluster/K1-result.json').read_text())['result']=='PASS'
    assert ready_nodes(),'cluster must be ready before scenarios'
    create_namespace()
    for role in ('cp','worker'):
        ssh(role,'test -f /home/ubuntu/nested/persistent-marker || cat /proc/sys/kernel/random/uuid > /home/ubuntu/nested/persistent-marker')
    cases={'G1-G3':basic,'G2':negative,'G4':g4,'G5':g5,'K2':lambda:recreate('worker','K2'),'K3':lambda:recreate('cp','K3'),'Q1':q1,'G6':g6}
    selected=sys.argv[1:] or list(cases)
    for name in selected:
        target=OUT/f'verification-{name}.json'
        if target.exists() and json.loads(target.read_text())['result']=='PASS':continue
        started=now();began=time.monotonic();print(name,'START',flush=True)
        try:cases[name]()
        except Exception as e:
            save(f'verification-{name}.json',{'result':'FAIL','started':started,'finished':now(),'elapsed_seconds':time.monotonic()-began,'error':str(e)})
            print(name,'FAIL',str(e),flush=True)
            raise
        save(f'verification-{name}.json',{'result':'PASS','started':started,'finished':now(),'elapsed_seconds':time.monotonic()-began})
        print(name,'PASS',flush=True)
if __name__=='__main__':main()
