from common import *
if not (B/'before').exists():
 (B/'before').mkdir(mode=0o700)
 for resource in ['pods','vm','vmi','gpuprofiles','gpurequests','sharedmemorychannels','resourceclaims','resourceslices','deviceclasses','pv','pvc','deployments','daemonsets','configmaps','nodes']:
  (B/'before'/(resource+'.json')).write_text(k('get',resource,'-A','-o','json'))
 (B/'before/hami-values.json').write_text(call(['helm','get','values','hami','-n','kube-system','-o','json']))
 (B/'before/hami-status.json').write_text(call(['helm','status','hami','-n','kube-system','-o','json']))
 (B/'before/git-status.txt').write_text(call(['git','status','--porcelain'],cwd=R))
 (B/'before/gpu.csv').write_text(call(['nvidia-smi','--query-gpu=index,uuid,name,driver_version,memory.used,utilization.gpu','--format=csv']))
 (B/'before/processes.csv').write_text(call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_memory','--format=csv']))
 save(O/'evidence/baseline.json',{'utc':time.time(),'gpu_uuid':GPU,'gpu_index':1,'hami':'2.11.0','namespace':NS,'vmweave_namespace':VNS,'gpu_allocator':'existing hami-core-gpu.project-hami.io; full capacity claim','global_changes':[]})
if not get('namespace',NS):create({'apiVersion':'v1','kind':'Namespace','metadata':{'name':NS}})
if not get('pod','admin'):
 create({'apiVersion':'v1','kind':'Pod','metadata':{'name':'admin','namespace':NS,'labels':{'hami.io/webhook':'ignore'}},'spec':{'nodeName':NODE,'hostPID':True,'restartPolicy':'Never','terminationGracePeriodSeconds':1,'automountServiceAccountToken':False,'containers':[{'name':'admin','image':IM['worker'],'command':['sleep','86400'],'resources':{'limits':{'cpu':'2','memory':'8Gi'}},'securityContext':{'privileged':True,'runAsUser':0},'volumeMounts':[{'name':'host','mountPath':'/host'}]}],'volumes':[{'name':'host','hostPath':{'path':'/','type':'Directory'}}]}})
wait(lambda:get('pod','admin').get('status',{}).get('phase')=='Running',300)
print('ADMIN_READY')
print(admin("import subprocess;subprocess.run(['docker','images','--format','{{.Repository}}:{{.Tag}} {{.ID}}'],check=True)"))
