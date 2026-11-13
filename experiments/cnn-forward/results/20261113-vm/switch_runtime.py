import json,subprocess,time,sys,pathlib
NS='vmweave-test-b';NAME='dp-dev-20261105';R=pathlib.Path('experiments/cnn-forward/results/20261113-vm');L=pathlib.Path('.local/cnn-validation-20261113')
action=sys.argv[1];assert action in ('candidate','restore')
def k(*args,data=None):return subprocess.check_output(['kubectl','-n',NS,*args],input=data,text=True,timeout=180)
def get(kind,name=NAME):
 s=k('get',kind,name,'--ignore-not-found','-o','json');return json.loads(s) if s.strip() else None
def save(name,obj):(R/(name+'.json')).write_text(json.dumps(obj,indent=2)+'\n')
def create(obj):return json.loads(k('create','-f','-','-o','json',data=json.dumps(obj)))
def ref(o):return {x:o['metadata'][x] for x in ('name','uid')}
def wait(pred,seconds=240):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  value=pred()
  if value:return value
  time.sleep(2)
 raise TimeoutError('runtime transition '+action)
v=get('vm');save(action+'-before-vm',v);old=get('sharedmemorychannel');save(action+'-before-channel',old)
assert old['status']['phase']=='Ready' and v['spec']['runStrategy']=='Always'
print(k('patch','vm',NAME,'--type=json','-p',json.dumps([{'op':'test','path':'/metadata/uid','value':v['metadata']['uid']},{'op':'test','path':'/spec/runStrategy','value':'Always'},{'op':'replace','path':'/spec/runStrategy','value':'Halted'}])),flush=True)
wait(lambda:not get('vmi') and get('sharedmemorychannel')['status']['phase']=='Stopped')
old=get('sharedmemorychannel');save(action+'-stopped-channel',old);print('normal shutdown and reclamation complete',flush=True)
if action=='candidate':
 request=get('gpurequest',old['spec']['requestRef']['name']);profile=get('gpuprofile',request['spec']['profileRef']['name'])
 image='localhost/vmweave-worker@'+(L/'worker-digest').read_text().strip()
 p={key:profile[key] for key in ['apiVersion','kind','spec']};p['metadata']={'name':NAME+'-cnn1113','namespace':NS,'labels':{'experiment':'cnn-forward-20261113'}};p['spec']['workerImage']=image
 p=create(p);save('candidate-profile',p)
 q={key:request[key] for key in ['apiVersion','kind','spec']};q['metadata']={'name':NAME+'-cnn1113','namespace':NS,'labels':{'experiment':'cnn-forward-20261113'}};q['spec']['profileRef']=ref(p)
 q=create(q);save('candidate-request',q)
 spec=dict(old['spec']);spec['workerImage']=image;spec['requestRef']=ref(q)
else:spec=json.loads((R/'candidate-before-channel.json').read_text())['spec']
assert get('sharedmemorychannel')['metadata']['uid']==old['metadata']['uid']
print(k('delete','sharedmemorychannel',NAME,'--wait=true','--timeout=120s'),flush=True)
channel=create(dict(apiVersion=old['apiVersion'],kind=old['kind'],metadata=dict(name=NAME,namespace=NS),spec=spec));save(action+'-created-channel',channel)
v=get('vm');assert v['spec']['runStrategy']=='Halted' and not get('vmi')
annotations=v['spec']['template']['metadata']['annotations'];assert annotations['vmweave.io/shm-channel-uid']==old['metadata']['uid']
keys=['vmweave.io/shm-channel','vmweave.io/shm-channel-uid','vmweave.io/shm-allocation','vmweave.io/shm-generation','hooks.kubevirt.io/hookSidecars']
ops=[{'op':'test','path':'/metadata/uid','value':v['metadata']['uid']},{'op':'test','path':'/metadata/resourceVersion','value':v['metadata']['resourceVersion']}]
ops += [{'op':'remove','path':'/spec/template/metadata/annotations/'+x.replace('/','~1')} for x in keys]
print(k('patch','vm',NAME,'--type=json','-p',json.dumps(ops)),flush=True)
print(k('patch','vm',NAME,'--type=json','-p',json.dumps([{'op':'test','path':'/metadata/uid','value':v['metadata']['uid']},{'op':'test','path':'/spec/runStrategy','value':'Halted'},{'op':'replace','path':'/spec/runStrategy','value':'Always'}])),flush=True)
wait(lambda:get('sharedmemorychannel')['status']['phase']=='Ready',seconds=300)
save(action+'-ready-channel',get('sharedmemorychannel'));save(action+'-ready-vm',get('vm'));save(action+'-ready-vmi',get('vmi'))
worker=get('sharedmemorychannel')['status']['resourcePrefix']+'-worker';save(action+'-ready-worker',get('pod',worker))
print(action,'READY',worker,flush=True)
if action=='restore':
 for kind,f in [('gpurequest','candidate-request'),('gpuprofile','candidate-profile')]:
  before=json.loads((R/(f+'.json')).read_text());now=get(kind,before['metadata']['name']);assert now['metadata']['uid']==before['metadata']['uid']
  print(k('delete',kind,now['metadata']['name'],'--wait=true','--timeout=120s'),flush=True)
