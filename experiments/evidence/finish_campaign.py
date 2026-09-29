"""Wait for the serial matrix, then run the declared clock retry and publish.

This prepares local reviewable artifacts only; git commit/push is a separate step.
Never overlap a second workload with the measurement matrix.
"""
import argparse
import csv
import json
import os
import subprocess
import time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
base=a.base.resolve();out=a.output.resolve();root=Path(__file__).resolve().parents[2]
def run(args,**kwargs):
    print(json.dumps({'utc_seconds':time.time(),'command':list(map(str,args))}),flush=True)
    subprocess.run(list(map(str,args)),cwd=root,check=True,**kwargs)
while not (base/'MEASUREMENTS_COMPLETE.json').exists():time.sleep(2)
retry=base/'runs/evidence-c28-t-l-25-1-clockretry'
if not (retry/'cleanup.json').exists():
    with (base/'clockretry-terminal.txt').open('w') as stream:
        run(['python3','-u','experiments/evidence/retry_campaign_clock.py','--base',base],stdout=stream,stderr=subprocess.STDOUT)
if not (retry/'monotonic-clock-map.json').exists():raise RuntimeError('Clock retry missing in-run monotonic bridge')
(base/'CLOCK_COLLECTION_COMPLETE').touch()
run([root/'.local/evidence-venv/bin/python','experiments/evidence/analyze_campaign.py','--base',base,'--output',out/'tables'])
run(['python3','experiments/evidence/validate_campaign.py','--base',base,'--tables',out/'tables','--output',out/'protocol/validation.json'])
run(['python3','experiments/evidence/export_campaign_monitoring.py','--base',base,'--output',out/'monitoring','--auth',base/'grafana-auth.json'])
intervals={r['run_id']:r for r in json.loads((out/'monitoring/intervals.json').read_text())}
# Show the first repeat, including the predeclared replacement when applicable.
groups={
 'compute-long':['evidence-c28-t-l-25-1-clockretry','evidence-c28-t-l-50-1','evidence-c28-t-l-100-1'],
 'compute-short':[f'evidence-c28-t-s-{c}-1' for c in [25,50,100]],
 'overhead-resident':[f'evidence-c28-ov-r-{b}-1' for b in ['n','s']],
 'overhead-transfer':[f'evidence-c28-ov-t-{b}-1' for b in ['n','s']],
 'sharing-resident':[f'evidence-c28-in-r-pair-1-{s}' for s in ['a','b']],
 'sharing-transfer':[f'evidence-c28-in-t-pair-1-{s}' for s in ['a','b']],
}
env={**os.environ,'NODE_PATH':str(root/'.local/evidence-20260924/tools/node_modules')}
for label,names in groups.items():
    # Distant compute retry is captured separately to preserve 1 s readability.
    batches=[[name] for name in names] if label.startswith('compute') else [names]
    for n,batch in enumerate(batches):
        title=label+(f'-{n+1}' if len(batches)>1 else '')
        config={'from_ms':min(intervals[x]['from_ms'] for x in batch),
                'to_ms':max(intervals[x]['to_ms'] for x in batch),'run_ids':batch,
                'kind':'Actual Grafana historical query; not a live execution recording',
                'source_queries':'monitoring/queries/','source_events':'runs/*/stdout.jsonl'}
        file=base/'captures'/(title+'-query.json');file.parent.mkdir(exist_ok=True);file.write_text(json.dumps(config,indent=2)+'\n')
        run(['node','scripts/capture-campaign.cjs',base/'captures'/title,0,title,file],env=env)
run(['python3','experiments/evidence/export_campaign.py','--base',base,'--output',out])
run(['python3','experiments/evidence/write_campaign_report.py','--output',out])
(base/'LOCAL_ARTIFACTS_COMPLETE.json').write_text(json.dumps({'utc_seconds':time.time(),'status':'ready for independent review, cleanup and git publication'},indent=2)+'\n')
print('LOCAL_ARTIFACTS_COMPLETE',flush=True)
