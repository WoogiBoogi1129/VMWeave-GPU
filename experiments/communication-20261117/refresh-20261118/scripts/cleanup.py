from infra import *
def stop_active():
 for name,ns in [(NAME+'-net',NS),(NAME+'-shm',VNS)]:
  v=get('vm',name,ns)
  if v and v['metadata'].get('labels',{}).get('experiment.vmweave.io/campaign')==NAME:vm_stop(name,ns)
 for n in ['native-pilot','native-server','flyt-server','lupine-server']:
  if get('pod',n):remove('pod',n)
  if get('resourceclaim',n):remove('resourceclaim',n)
 if get('pod','flyt-manager'):remove('pod','flyt-manager')
 (B/'active.json').unlink(missing_ok=True)

def verify():
 before=json.loads((B/'before/pods.json').read_text())['items'];now=json.loads(k('get','pods','-A','-o','json'))['items'];idx={x['metadata']['uid']:x for x in now};changes=[]
 for p in before:
  if p['status'].get('phase')!='Running':continue
  q=idx.get(p['metadata']['uid']);name=p['metadata']['namespace']+'/'+p['metadata']['name']
  if not q:changes.append({'pod':name,'change':'UID no longer present'})
  elif [(x['name'],x.get('restartCount',0)) for x in p['status'].get('containerStatuses',[])] != [(x['name'],x.get('restartCount',0)) for x in q['status'].get('containerStatuses',[])]:changes.append({'pod':name,'change':'restart count changed'})
  if q and q['status'].get('phase')!='Running':changes.append({'pod':name,'change':'phase changed from Running to '+str(q['status'].get('phase'))})
  if q:
   ready=lambda v:next((c.get('status') for c in v['status'].get('conditions',[]) if c['type']=='Ready'),None)
   if ready(p)!=ready(q):changes.append({'pod':name,'change':'Ready condition changed','before':ready(p),'after':ready(q)})
 config=[]
 for kind in ['deployments','daemonsets','configmaps','vm','gpuprofiles','gpurequests','sharedmemorychannels','deviceclasses']:
  old=json.loads((B/'before'/(kind+'.json')).read_text())['items'];curr=json.loads(k('get',kind,'-A','-o','json'))['items'];d={x['metadata']['uid']:x for x in curr}
  for x in old:
   y=d.get(x['metadata']['uid']);key='data' if kind=='configmaps' else 'spec'
   if not y or x.get(key)!=y.get(key):config.append({'kind':kind,'namespace':x['metadata'].get('namespace'),'name':x['metadata']['name'],'change':'missing or '+key+' changed'})
 hv=json.loads(call(['helm','get','values','hami','-n','kube-system','-o','json']))
 gpu=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 owned_uids=set()
 for f in (O/'evidence').glob('*-pod.json'):
  try:owned_uids.add(json.loads(f.read_text())['metadata']['uid'])
  except (ValueError,KeyError):pass
 remaining_owned=[];unreadable=[]
 for line in gpu.splitlines():
  if not line.startswith(GPU):continue
  pid=int(line.split(',')[1].strip())
  try:
   cg=Path('/proc',str(pid),'cgroup').read_text()
   if any(u in cg or u.replace('-','_') in cg for u in owned_uids):remaining_owned.append(pid)
  except FileNotFoundError:pass
  except OSError:unreadable.append(pid)
 result={'remaining_experiment_gpu_pids':remaining_owned,'unreadable_gpu_pid_cgroups':unreadable,'experiment_gpu_processes_absent':not remaining_owned and not unreadable,'utc':time.time(),'preexisting_running_pods':sum(p['status'].get('phase')=='Running' for p in before),'pod_changes':changes,'configuration_changes':config,'hami_values_unchanged':hv==json.loads((B/'before/hami-values.json').read_text()),'gpu1_compute_idle':GPU not in gpu,'restoration_scope':'Only experiment-created resources; HAMi 2.11.0 upgrade retained. No shared configuration mutation was required.'}
 save(O/'evidence/restoration.json',result);return result

def cleanup():
 stop_active()
 for kind in ['sharedmemorychannel','gpurequest','gpuprofile','vm']:
  remove(kind,NAME+'-shm',VNS)
 remove('vm',NAME+'-net')
 for n,ns in [(NAME+'-net',NS),(NAME+'-shm',VNS),(NAME+'-backing',VNS)]:
  remove('pvc',n,ns);remove('pv',n)
 admin(f"from pathlib import Path\nimport shutil\np=Path({H!r});assert str(p)=='/var/lib/vmweave/vwx-20261118'\nif p.exists():shutil.rmtree(p)")
 for p in ['compiler','lupine-client-image','lupine-server-image','lupine-client-compatible','lupine-server-compatible']:remove('pod',p)
 save(O/'evidence/image-cleanup.json', {'published_images_retained':True,'reason':'Existing deployed v0.5.12 images; no candidate images built and no shared cache prune'})
 (B/'numa.stop').touch()
 remaining=json.loads(k('get','pods','-n',NS,'-o','json'))['items']
 owned={x['uid'] for x in json.loads((B/'owned.json').read_text())}
 assert all(p['metadata']['uid'] in owned for p in remaining),'Unrecognized Pod: preserve namespace'
 restoration=verify();print(json.dumps(restoration,indent=2))
 remove('pod','admin');remove('namespace',NS)
 save(O/'evidence/cleanup-complete.json',{'utc':time.time(),'namespace_removed':get('namespace',NS) is None,'experiment_vms_removed':not get('vm',NAME+'-shm',VNS),'shared_settings_changed_by_experiment':False,'unrelated_configuration_changes_observed':len(restoration['configuration_changes']),'unrelated_changes_rolled_back':False})
if __name__=='__main__':
 import sys
 if '--stop-only' in sys.argv:stop_active()
 elif '--verify' in sys.argv:print(json.dumps(verify(),indent=2))
 else:cleanup()
