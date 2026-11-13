#!/usr/bin/env python3
"""Run on a dedicated, already prepared VM. Connection config stays private.

Config: sshArgv, context, node, image, brokerGID, outerNamespace, channel,
gpuUUID. --slots=2 injects SIGKILL into one broker in this test VM.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--connection',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--namespace',required=True)
    ap.add_argument('--slots',type=int,choices=[1,2],required=True)
    a=ap.parse_args();c=json.loads(a.connection.read_text());a.output.mkdir(parents=True,exist_ok=False)
    def save(name,obj):
        (a.output/(name+'.json')).write_text(json.dumps(obj,indent=2)+'\n')
    def ssh(command):
        return subprocess.check_output(c['sshArgv']+[command],text=True,timeout=90)
    def k(*args,data=None):
        command=shlex.join(['kubectl','--context',c['context'],'-n',a.namespace,*args])
        return subprocess.check_output(c['sshArgv']+[command],input=data,text=True,timeout=90)
    def wait(fn,seconds=90):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            value=fn()
            if value:return value
            time.sleep(1)
        raise TimeoutError(str(fn))
    def pod(name):return json.loads(k('get','pod',name,'-o','json'))
    def logs(name):
        text=k('logs',name);(a.output/(name+'.jsonl')).write_text(text)
        return [json.loads(x) for x in text.splitlines() if x.startswith('{')]
    def snapshot(name):
        save(name+'-pods',json.loads(k('get','pods','-o','json')))
        save(name+'-node',json.loads(k('get','node',c['node'],'-o','json')))
        if a.slots==1:
            paths=['/run/vmweave-device-plugin/status.json']
        else:paths=[f'/run/vmweave-device-plugin/slots/{i}/status.json' for i in range(2)]
        save(name+'-brokers',[json.loads(ssh('sudo cat '+p)) for p in paths])
    def gpu_snapshot(label, worker_uid):
        raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],text=True)
        records=[]
        for row in raw.splitlines():
            if c['gpuUUID'] not in row:continue
            pid=int(row.split(',')[0]);root=Path(f'/proc/{pid}')
            group=(root/'cgroup').read_text()
            if worker_uid.replace('-','_') not in group and worker_uid not in group:continue
            records.append({'pid':pid,'gpu':row,'cgroup':group,'status':(root/'status').read_text()})
        save(label+'-cuda-processes',records)
        return {r['pid'] for r in records}
    def create(name,seed,seconds,start):
        o={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':a.namespace,'labels':{'vmweave-experiment':a.namespace}},'spec':{'nodeSelector':{'kubernetes.io/hostname':c['node']},'restartPolicy':'Never','automountServiceAccountToken':False,'activeDeadlineSeconds':360,'terminationGracePeriodSeconds':2,'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':1000,'supplementalGroups':[c['brokerGID']],'seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'gpu','image':c['image'],'imagePullPolicy':'IfNotPresent','args':[str(seed),str(seconds),str(start)],'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'1','memory':'512Mi','vmweave.io/gpu':1}}}]}}
        save(name+'-submitted',o);save(name+'-created',json.loads(k('create','-f','-','-o','json',data=json.dumps(o))))
    def running(name):
        p=pod(name)
        if p['status']['phase'] in ['Failed','Succeeded']:
            logs(name);save(name+'-unexpected',p);raise RuntimeError(name+' finished before readiness')
        return p['status']['phase']=='Running'
    def success(name):
        p=pod(name)
        if p['status']['phase']=='Failed':
            logs(name);save(name+'-failed',p);raise RuntimeError(name+' failed')
        return p if p['status']['phase']=='Succeeded' else None
    def slot(name):
        text=k('exec',name,'--','cat','/proc/self/mountinfo');(a.output/(name+'-mountinfo.txt')).write_text(text)
        import re
        found=re.findall(r' /(?:run/)?vmweave/slots/(\d+) /run/vmweave ro[, ]',text)
        assert len(found)==1,(name,text)
        return int(found[0])
    def progress(name):return max([x.get('loops',0) for x in logs(name)]+[0])
    namespace={'apiVersion':'v1','kind':'Namespace','metadata':{'name':a.namespace,'labels':{'vmweave-experiment':a.namespace}}}
    save('namespace-created',json.loads(k('create','-f','-','-o','json',data=json.dumps(namespace))))
    result={'slots':a.slots,'scope':'fixed slots sharing VM quota; no per-Pod memory/compute guarantee','checks':{}}
    try:
        wait(lambda:int(json.loads(k('get','node',c['node'],'-o','json'))['status'].get('allocatable',{}).get('vmweave.io/gpu','0'))==a.slots)
        snapshot('before')
        if a.slots==1:
            create('single',5,3,int(time.time())+3)
            save('single-final',wait(lambda:success('single')))
            records=logs('single');assert records[-1]['event']=='pass' and records[-1]['loops']>0
            result['checks']['singleSlotRegression']='PASS'
            snapshot('single-complete')
        else:
            start=int(time.time())+15
            create('a',3,240,start);create('b',11,240,start)
            for name in ['a','b']:wait(lambda:running(name))
            wait(lambda:progress('a')>=20 and progress('b')>=20)
            sa,sb=slot('a'),slot('b');assert sa!=sb
            result['mapping']={'a':sa,'b':sb}
            snapshot('concurrent')
            outer=json.loads(subprocess.check_output(['kubectl','-n',c['outerNamespace'],'get','sharedmemorychannel',c['channel'],'-o','json'],text=True));save('outer-channel',outer)
            allpods=json.loads(subprocess.check_output(['kubectl','-n',c['outerNamespace'],'get','pods','-o','json'],text=True))['items']
            worker=next(p for p in allpods if p['metadata']['uid']==outer['status']['workerPodUID']);save('outer-worker',worker)
            cmd="import pathlib,json; rows=[]\nfor p in pathlib.Path('/proc').iterdir():\n if not p.name.isdigit():continue\n try: rows.append({'pid':p.name,'cmd':(p/'cmdline').read_bytes().decode(errors='replace').replace(chr(0),' '),'status':(p/'status').read_text()})\n except (FileNotFoundError,PermissionError):pass\nprint(json.dumps(rows))"
            save('worker-processes',json.loads(subprocess.check_output(['kubectl','-n',c['outerNamespace'],'exec',worker['metadata']['name'],'--','python3','-c',cmd],text=True)))
            worker_uid=worker['metadata']['uid']
            initial_pids=gpu_snapshot('concurrent',worker_uid);assert len(initial_pids)==2,initial_pids
            result['checks']['concurrentDistinctSlots']='PASS'
            for name,own in [('a',sa),('b',sb)]:
                text=k('exec',name,'--','sh','-ec','test -S /run/vmweave/gpu.sock; test ! -e /run/vmweave/slots; test ! -e /run/vmweave/layout.bin; test ! -e /dev/nvidia0; ls -la /run/vmweave')
                (a.output/(name+'-access.txt')).write_text(text)
                # Extra CUDA client must be rejected by the broker's existing lock.
                r=subprocess.run(c['sshArgv']+[shlex.join(['kubectl','--context',c['context'],'-n',a.namespace,'exec',name,'--','/opt/vmweave/bin/sgemm'])],text=True,capture_output=True,timeout=30)
                (a.output/(name+'-duplicate.txt')).write_text(r.stdout+r.stderr);assert r.returncode!=0 and ': 46' in r.stdout+r.stderr
            result['checks']['socketBoundaryAndDuplicateClient']='PASS'
            before=progress('b')
            k('rollout','restart','daemonset/vmweave-device-plugin','-n','vmweave-device-plugin')
            k('rollout','status','daemonset/vmweave-device-plugin','-n','vmweave-device-plugin','--timeout=60s')
            wait(lambda:progress('b')>before and progress('a')>20)
            result['checks']['pluginRestart']='PASS'
            create('c',23,180,0);time.sleep(4)
            p=pod('c');save('c-pending',p)
            assert p['status']['phase']=='Pending' and not p['spec'].get('nodeName')
            assert any('Insufficient vmweave.io/gpu' in x.get('message','') for x in p['status'].get('conditions',[]))
            result['checks']['thirdPodPending']='PASS'
            # First test graceful cleanup. C must reuse A's exact slot.
            k('exec','a','--','touch','/tmp/stop');save('a-final',wait(lambda:success('a')));logs('a')
            wait(lambda:running('c'));wait(lambda:progress('c')>=10)
            assert slot('c')==sa;assert progress('b')>before
            reused_pids=gpu_snapshot('after-graceful-reuse',worker_uid)
            assert len(reused_pids)==2 and len(initial_pids & reused_pids)==1
            result['checks']['gracefulReleaseAndReuse']='PASS'
            logs('c');k('delete','pod','c','--grace-period=0','--force','--wait=true','--timeout=30s')
            # Forced API deletion is not evidence of process termination. Verify
            # retirement of C's CUDA process before attempting slot reuse.
            old_child=next(iter(reused_pids-initial_pids))
            wait(lambda:not Path(f'/proc/{old_child}').exists(),45)
            save('forced-child-reaped',{'pid':old_child,'reaped':True,'time':time.time()})
            create('d',37,180,0);wait(lambda:running('d'));wait(lambda:progress('d')>=10);assert slot('d')==sa
            forced_pids=gpu_snapshot('after-forced-reuse',worker_uid)
            assert len(forced_pids)==2 and len(reused_pids & forced_pids)==1
            assert (initial_pids & reused_pids)==(reused_pids & forced_pids)
            result['checks']['forcedReleaseAndReuse']='PASS'
            before=progress('b');snapshot('before-broker-fault')
            code=f"import pathlib,os,signal,json; expected={('/run/vmweave/slots/'+str(sa)+'/gpu.sock')!r}; matches=[]\nfor p in pathlib.Path('/proc').iterdir():\n if p.name.isdigit():\n  try: args=(p/'cmdline').read_bytes().split(bytes([0]))\n  except (FileNotFoundError,PermissionError): continue\n  if b'/opt/vmweave/control/guest_broker.py' in args and expected.encode() in args:matches.append(int(p.name))\nassert len(matches)==1,matches\nprint(json.dumps({{'pid':matches[0],'slot':{sa}}}));os.kill(matches[0],signal.SIGKILL)"
            save('broker-fault',json.loads(ssh('sudo python3 -c '+shlex.quote(code))))
            wait(lambda:int(json.loads(k('get','node',c['node'],'-o','json'))['status']['allocatable']['vmweave.io/gpu'])==1,45)
            wait(lambda:progress('b')>before)
            create('e',41,10,0);time.sleep(4);save('e-pending',pod('e'));assert pod('e')['status']['phase']=='Pending'
            result['checks']['brokerFaultFencedPeerContinues']='PASS'
            k('delete','pod','e','--wait=true','--timeout=30s')
            k('exec','b','--','touch','/tmp/stop');save('b-final',wait(lambda:success('b')));logs('b')
            wait(lambda:pod('d')['status']['phase']=='Failed',60);save('d-faulted',pod('d'));logs('d')
            snapshot('after-broker-fault')
            # A killed broker may leave its own host child alive until VM teardown;
            # record this instead of treating guest health withdrawal as reclamation.
            gpu_snapshot('after-broker-fault',worker_uid)
        result['status']='PASS'
    except Exception as e:
        result['status']='FAIL';result['error']=str(e)
        try:save('failure-pods',json.loads(k('get','pods','-o','json')))
        except Exception:pass
        raise
    finally:
        save('summary',result)
        # Only the newly created experiment namespace is removed.
        ns=json.loads(k('get','namespace',a.namespace,'-o','json'))
        expected=json.loads((a.output/'namespace-created.json').read_text())['metadata']['uid']
        assert ns['metadata']['uid']==expected
        k('delete','namespace',a.namespace,'--wait=true','--timeout=60s')
        save('cleanup',{'namespace':a.namespace,'uid':expected,'deleted':True})
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
