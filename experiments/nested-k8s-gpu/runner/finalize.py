from gpu import *
import hashlib,re
cases=['G1-G3','G2','G4','G5','K2','K3','Q1','G6']
results={c:json.loads((OUT/f'verification-{c}.json').read_text()) for c in cases}
assert all(v['result']=='PASS' for v in results.values()),'required scenarios are incomplete'
assert json.loads((OUT/'cluster/K1-result.json').read_text())['result']=='PASS'
assert ready_nodes()
quiescent('handoff')  # observation only; no extra GPU workload
save('cluster/nodes-final.json',iobj('get','nodes'))
save('cluster/system-pods-final.json',iobj('get','pods','-n','kube-system'))
save('cluster/jobs-final.json',iobj('get','jobs','-n',INNER))
save('cluster/test-pods-final.json',iobj('get','pods','-n',INNER))
assert all(not j.get('status',{}).get('active',0) for j in iobj('get','jobs','-n',INNER)['items'])
inner('delete','deployment/cpu-web','pod/cpu-client','service/cpu-web','-n',INNER,'--ignore-not-found','--grace-period=1','--wait=true','--timeout=60s')
save('cluster/test-pods-after-cleanup.json',iobj('get','pods','-n',INNER))
for role in ('cp','worker'):
    save('inventory/'+role+'-final.txt',ssh(role,'hostname; cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id; ip -4 address; ip -4 route; timedatectl show -p NTPSynchronized; df -h /; sudo systemctl is-active kubelet crio wg-quick@wg0; sudo sha256sum /etc/kubernetes/pki/ca.crt'))
save('raw/broker-final-journal.log',ssh('worker','sudo journalctl -u vmweave-guest-broker --no-pager'))
save('raw/experiment-controller.log',k('logs','-n',SYSTEM,'deploy/nested-controller','--timestamps'))
channel=obj('get','sharedmemorychannel',VM,'-n',NS)
save('inventory/channel-final.json',channel)
save('inventory/outer-vms-final.json',obj('get','vm','-n',NS))
save('inventory/outer-vmis-final.json',obj('get','vmi','-n',NS))
save('inventory/gpu-worker-final.json',obj('get','pod',channel['status']['resourcePrefix']+'-worker','-n',NS))
save('inventory/outer-events-final.json',obj('get','events','-n',NS))
save('inventory/gpu-final.txt',run(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv']))
old=json.loads((OUT/'inventory/protected-channel-before.json').read_text())
new=obj('get','sharedmemorychannel','vmweave-k8s-01','-n','vmweave-test-a')
save('inventory/protected-channel-final.json',new)
unchanged={key:old['status'][key]==new['status'][key] for key in ('allocation','generation','vmiUID','workerPodUID')}
unchanged['channel_uid']=old['metadata']['uid']==new['metadata']['uid']
assert all(unchanged.values()) and new['status']['phase']=='Ready'
before=json.loads((OUT/'inventory/protected-pods-before.json').read_text())
after=obj('get','pods','-A')['items'];byuid={p['metadata']['uid']:p for p in after}
changes=[]
for p in before:
    if p['status'].get('phase')!='Running':continue
    q=byuid.get(p['uid'])
    if q is None:changes.append({'namespace':p['namespace'],'name':p['name'],'change':'original UID missing'})
    elif q['status'].get('phase')!='Running' or [(c['name'],c.get('restartCount'),c.get('ready')) for c in p['status'].get('containerStatuses',[])]!=[(c['name'],c.get('restartCount'),c.get('ready')) for c in q['status'].get('containerStatuses',[])]:
        changes.append({'namespace':p['namespace'],'name':p['name'],'before':p['status'],'after':q['status']})
save('inventory/protected-comparison.json',{'channel_unchanged':unchanged,'running_pod_changes':changes})
expected=sum((i*2654435761+17+1234567)&0xffffffff for i in range(8388608))
numerical=[];attribution=[]
for path in sorted((OUT/'gpu').glob('*-final.log')):
    for line in path.read_text().splitlines():
        if not line.startswith('{'):continue
        row=json.loads(line)
        if row.get('event')=='RESULT':
            assert row['elements']==8388608 and row['mismatches']==0 and row['checksum']==expected and row['kernel_launches']==1
            numerical.append({'test':path.name.removesuffix('-final.log'),**row})
assert len(numerical)==10,len(numerical)
for path in sorted((OUT/'gpu').glob('*-active.json')):
    o=json.loads(path.read_text());mapped=[p for p in o['gpu_processes'] if p['child_matches']]
    assert len(mapped)==1 and mapped[0]['gpu_uuid']==EXPECTED_GPU
    attribution.append({'test':path.name.removesuffix('-active.json'),'worker_uid':o['channel_status']['workerPodUID'],'allocation':o['channel_status']['allocation'],'channel_session_ids':o['channel_status']['sessions'],**mapped[0]})
save('object-identities.json',{'gpu_attribution':attribution,'vms':obj('get','vmi','-n',NS),'nodes':iobj('get','nodes'),'pods':iobj('get','pods','-n',INNER)})
verification={'result':'PASS','at':now(),'K1':{'result':'PASS'},**results,'numeric_checks':numerical,'gpu_mapping_count':len(attribution),'protected_channel_unchanged':unchanged,'protected_running_pod_changes':len(changes),'scope':'single execution per condition; no statistical reliability or performance claim','broker_epoch_capture':'per-client random epoch not exported by baseline; Channel session ID, allocation and CUDA child PID used for attribution'}
save('verification.json',verification)
if changes:
    verification['environment_control']='NOT_ESTABLISHED: concurrent outer workload replacements found in final comparison'
    verification['operational_interpretation']='Observed PASS; external changes prevent claiming isolated fault recovery'
    verification['external_change_discovery']='After all scenarios, during final baseline comparison; no further GPU workloads submitted'
    save('verification.json',verification)
print(json.dumps({'result':'PASS','correctness_runs':len(numerical),'gpu_attributions':len(attribution),'protected_pod_changes':len(changes)},indent=2))
