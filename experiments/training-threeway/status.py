#!/usr/bin/env python3
"""Read-only progress and completed-pair loss checks while the campaign runs."""
import json
import math
from pathlib import Path


def status(root):
    counts={}
    data={}
    for phase in ['pilot','formal','formal-recovery','interrupted']:
        counts[phase]={m:0 for m in ['passthrough','flyt','vmweave']}
        for p in (root/phase).glob('*/*/*/result.json'):
            try:x=json.loads(p.read_text())
            except json.JSONDecodeError:continue
            block,mode,case=p.parents[2].name,p.parents[1].name,p.parent.name
            counts[phase][mode]+=1
            if phase in ['formal','formal-recovery']:data[(block,mode,case)]=x
    checked=0;failures=[];maximum=0
    for (block,mode,case),x in data.items():
        ref=data.get((block,'passthrough',case))
        if mode=='passthrough' or ref is None:continue
        checked+=1
        maximum=max(maximum,abs(x['final_loss']-ref['final_loss']))
        if not math.isclose(x['final_loss'],ref['final_loss'],rel_tol=1e-4,abs_tol=1e-6):
            failures.append({'block':block,'mode':mode,'case':case})
    return {'completed':counts,'formal_loss_pairs_checked':checked,'max_absolute_loss_difference':maximum,'loss_failures':failures}


if __name__=='__main__':
    print(json.dumps(status(Path(__file__).parent/'results/20261102'),indent=2))
