#!/usr/bin/env python3
"""Derive Pod -> slot -> transport process -> host CUDA PID from saved evidence."""
import argparse
import json
from pathlib import Path
import re

p=argparse.ArgumentParser();p.add_argument('result',type=Path);a=p.parse_args()
def read(name):return json.loads((a.result/(name+'.json')).read_text())
summary=read('summary');assert summary['status']=='PASS'
processes={int(x['pid']):x for x in read('worker-processes')}
slots={}
for cuda in read('concurrent-cuda-processes'):
    inner=int(re.search(r'^NSpid:\s*(.*)$',cuda['status'],re.M).group(1).split()[-1])
    child=processes[inner]
    parent=int(re.search(r'^PPid:\s*(\d+)',child['status'],re.M).group(1))
    command=processes[parent]['cmd'].split()
    assert command[0]=='/opt/vmweave/bin/vmweave-shm-session-worker'
    slot=int(command[2]);assert slot not in slots
    slots[slot]={'transportPID':parent,'cudaContainerPID':inner,'cudaHostPID':cuda['pid']}
assert set(slots)=={0,1}
records={}
for name in ['a','b']:
    rows=[json.loads(x) for x in (a.result/(name+'.jsonl')).read_text().splitlines() if x.startswith('{')]
    last=rows[-1];assert last['event']=='pass' and last['loops']>0
    records[name]=dict(last,slot=summary['mapping'][name],**slots[summary['mapping'][name]])
overlap=min(v['end'] for v in records.values())-max(v['start'] for v in records.values())
assert overlap>0
out={'mapping':records,'overlapSeconds':overlap,'checkedElements':sum(v['loops']*v['elementsPerLoop'] for v in records.values()),'scope':'application intervals overlap; no hardware kernel concurrency or performance claim'}
(a.result/'analysis.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
