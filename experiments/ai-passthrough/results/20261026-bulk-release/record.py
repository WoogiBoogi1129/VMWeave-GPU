import json,subprocess,re,hashlib,shutil,datetime
from pathlib import Path
b=Path(__file__).resolve().parent;w=Path('/tmp/vmweave-v054');o=w/'experiments/ai-passthrough/results/20261026-bulk-release'
def run(*a):return subprocess.check_output(a,text=True)
def k(*a):return json.loads(run('kubectl',*a,'-o','json'))
lock=json.loads((b/'published-lock.json').read_text());live=json.loads((b/'live-verification.json').read_text());assert live['status']=='PASS' and live['sourceRevision']==lock['sourceRevision']
assert (b/'canary-checked').exists()
assert json.loads((b/'live-large-copy.json').read_text())['status']=='PASS'
assert all(x['match'] for x in json.loads((b/'live-rodinia.json').read_text()))
ch=k('get','sharedmemorychannel','vmweave-k8s-01','-n','vmweave-test-a');assert ch['status']['phase']=='Ready'
q=k('get','gpurequest',ch['spec']['requestRef']['name'],'-n','vmweave-test-a');p=k('get','gpuprofile',q['spec']['profileRef']['name'],'-n','vmweave-test-a')
assert p['spec']['cores']==50 and p['spec']['memoryMiB']==2048
for old in b.glob('pvc-before-*.json'):
 before=json.loads(old.read_text());after=k('get','pvc',before['metadata']['name'],'-n','vmweave-test-a');assert before['metadata']['uid']==after['metadata']['uid']
h=json.loads(run('helm','history','vmweave','-n','vmweave-system','-o','json'));assert h[-1]['status']=='deployed' and h[-1]['chart']=='vmweave-operator-0.5.4'
dra=json.loads(run('helm','history','vmweave-dra','-n','vmweave-dra-driver','-o','json'));assert dra[-1]['revision']==5
ci=json.loads((b/'ci.json').read_text())['workflow_runs'];assert all(x['conclusion']=='success' for x in ci)
lock.update({'scope':'Published v0.5.4 images/chart, isolated GPU canary and production validation passed. Labels are not cryptographic provenance.', 'chart':{'reference':'oci://ghcr.io/woogiboogi1129/charts/vmweave-operator','version':'0.5.4','digest':re.search(r'Digest: (sha256:[0-9a-f]{64})',(b/'publish-check.log').read_text()).group(1)},'workflows':{x['head_branch']+':'+x['name']:x['html_url'] for x in ci},'verification':{'control':'106 tests: 105 passed, 1 skipped','deployment':'16 passed','candidateGPU':'72 large sync/async copy correctness cases; two independent OFF/ON sessions','faults':{'worker':json.loads((b/'fault-worker.json').read_text()),'broker':json.loads((b/'fault-broker.json').read_text())},'canary':'Published library/package and Worker; standard installer/systemd; 50%/2048MiB; GPU smoke and 18 copy cases','production':'Published Guest/Broker/Worker smoke, cache and math-mode checks, 18 enabled-bulk copy cases, NW/LU output hashes; no production fault injection','performance':'Workload-specific improvements; small-copy/D2D variability remains. No universal no-regression claim.'},'deployment':{'helmRevision':h[-1]['revision'],'updatedComponents':['operator','helper','hook','worker','guest-artifacts'],'retainedComponents':['HAMi 2.10.0','DRA Helm revision 5'],'bulkDefault':'off','productionBulk':'Broker enabled; new login sessions export VMWEAVE_BULK_COPY=1; sudo and service workloads need explicit environment','cores':50,'memoryMiB':2048,'vmAndPVCsPreserved':True,'rollback':'Captured v0.5.3 Guest/Broker, environment/profile, Helm revision 11 and previous GPUProfile/GPURequest; restore matched set before fresh VM binding'},'publishedDateKST':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()})
(w/'deploy/releases/v0.5.4.json').write_text(json.dumps(lock,indent=2)+'\n')
for name in ['package-comparison.json','guest-payload-comparison.json','live-verification.json','live-large-copy.json','live-rodinia.json','live-gpu-default.json','live-gpu-cache.json','live-math.json','rollout-complete.json','live-environment.json','cleanup.json']:
 shutil.copy2(b/name,o/name)
(o/'publication.json').write_text(json.dumps({'sourceRevision':lock['sourceRevision'],'tag':'v0.5.4','chart':lock['chart'],'helmRevision':h[-1]['revision']},indent=2)+'\n')
(o/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(o.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
print('Release evidence prepared')
