"""Curate the completed campaign; export actual Prometheus queries and screenshots."""
import json,shutil,subprocess,gzip,urllib.request,urllib.parse,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'.local/sm-pair-20261016';O=ROOT/'experiments/sm-core-limit/evidence/pairs-20261016'
assert (O/'completed.json').exists()
for run in (B/'audit/runs').glob('sm-pair-r*-1016'):
 parts=run.name.split('-');dest=O/('pair-'+parts[2][1:])/parts[3]
 for p in run.glob('*-affinity.json'):shutil.copyfile(p,dest/p.name)
for src,dst in [('monitor.jsonl','monitor.jsonl'),('pmon.txt','pmon.txt'),('campaign.log','campaign.txt')]:shutil.copyfile(B/src,O/dst)
subprocess.run(['python3',str(Path(__file__).with_name('analyze_pairs.py'))],check=True)
subprocess.run([str(ROOT/'.local/evidence-venv/bin/python'),str(Path(__file__).with_name('plot_pairs.py'))],check=True)
s=json.loads((O/'summary.json').read_text());start=min(p['start_utc'] for p in s['pairs'])-20;end=max(p['start_utc'] for p in s['pairs'])+190
queries=['hami_container_device_utilization_ratio','hami_container_device_memory_bytes','sm_pair_core_limit','sm_pair_gpu_util','sm_pair_memory_mib'];Q=O/'prometheus';Q.mkdir(exist_ok=True)
for q in queries:
 args=dict(query=q,start=start,end=end,step=1);url='http://127.0.0.1:19097/api/v1/query_range?'+urllib.parse.urlencode(args)
 data=urllib.request.urlopen(url,timeout=30).read();j=json.loads(data);assert j['status']=='success' and j['data']['result'],q
 with gzip.GzipFile(filename=str(Q/(q+'.json.gz')),mode='wb',mtime=0) as f:f.write(data)
(Q/'queries.json').write_text(json.dumps({'start':start,'end':end,'step':1,'queries':queries,'exported_utc':time.time()},indent=2)+'\n')
for p in s['pairs']:
 subprocess.run(['node',str(Path(__file__).with_name('capture_pair_grafana.cjs')),str(O/'screenshots'/p['pair']),str(int((p['start_utc']-5)*1000)),str(int((p['start_utc']+185)*1000))],check=True)
def hashes():
 (O/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(O))+'\n' for p in sorted(O.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
hashes()
subprocess.run(['node',str(Path(__file__).with_name('capture_pair_terminal.cjs'))],check=True)
hashes()
print('Curated figures, Grafana screenshots, real terminal screenshots, raw queries and hashes')
