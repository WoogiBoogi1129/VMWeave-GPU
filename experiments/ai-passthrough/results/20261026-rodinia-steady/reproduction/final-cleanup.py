import json,subprocess
import rodinia_campaign as h
h.ensure_admin();assert __import__('pathlib').Path('/sys/bus/pci/devices/0000:40:00.0/driver').resolve().name=='nvidia'
assert not json.loads(h.k('get','vmi','-n','ai-perf-baseline','-o','json'))['items']
for kind in ['vm','sharedmemorychannel']:
 assert not any(x['metadata']['name'].startswith('rodinia-') for x in json.loads(h.k('get',kind,'-n',h.NS,'-o','json'))['items'])
assert not h.get('namespace','rodinia-flyt-1026')
pv=h.get('pv','rodinia-native-1026');assert pv['spec']['local']['path']=='/var/lib/vmweave/rodinia-steady-20261026/native'
h.k('delete','pvc','rodinia-native-1026','-n','ai-perf-baseline','--wait=true','--timeout=90s');h.k('delete','pv','rodinia-native-1026','--wait=true','--timeout=90s');h.k('delete','namespace','ai-perf-baseline','--wait=true','--timeout=90s')
h.admin(['rm','-rf','/var/lib/vmweave/rodinia-steady-20261026'])
units=h.admin(['systemctl','list-units','rodinia-affinity-*','--no-legend','--plain']);assert not units.strip(),units
checks={}
for name,ns,file in [('hami-device-plugin','kube-system','hami-ds-before.json'),('nvidia-dcgm-exporter','gpu-operator','dcgm-ds-before.json')]:
 before=json.loads((h.B/file).read_text());after=h.get('ds',name,ns);assert before['metadata']['uid']==after['metadata']['uid'];checks[name]=before['spec']==after['spec'];assert checks[name];assert after['status']['numberReady']==after['status']['desiredNumberScheduled']
before=json.loads((h.B/'kubevirt-before.json').read_text())['items'][0];after=h.get('kubevirt',before['metadata']['name'],before['metadata']['namespace']);checks['kubevirt_spec_restored']=before['spec']==after['spec'];assert checks['kubevirt_spec_restored']
for kind in ['vm','sharedmemorychannel']:
 before=json.loads((h.O/('production-'+kind+'-pre-formal.json')).read_text());after=h.get(kind,'vmweave-k8s-01');assert before['metadata']['uid']==after['metadata']['uid'];assert before['spec']==after['spec'];h.save(h.O/('production-'+kind+'-final.json'),after)
 if kind=='sharedmemorychannel':assert after['status']['phase']=='Ready'
checks.update({'gpu0_driver':'nvidia','temporary_affinity_units_removed':True,'production_vm_channel_spec_and_uid_preserved':True,'production_channel':'Ready'})
apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader'],text=True);assert h.GPU not in apps;checks['gpu0_no_compute_processes']=True
h.drop_admin();checks['test_resources_removed']=True;checks['pciRebindPerformed']=True;h.save(h.O/'cleanup.json',checks);print(json.dumps(checks,indent=2))
