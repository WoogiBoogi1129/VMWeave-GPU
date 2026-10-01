"""CPU cores consumed inside each measured window, including QEMU/Guest cost."""
from common import *
import statistics
samples=[json.loads(l) for l in (OUT/'monitoring/cpu.jsonl').read_text().splitlines()]
rows=[]
for run in sorted((OUT/'runs').glob('sf-*')):
    if not run.name.startswith(('sf-r','sf-pilot')):continue
    if not (run/'execution.json').exists():continue
    identity=json.loads((run/'identity.json').read_text());offset=identity['clock_offset']
    start=None;condition=None
    for line in (run/'stdout.jsonl').read_text().splitlines():
        if not line.startswith('{'):continue
        e=json.loads(line)
        if e['event']=='CONDITION':condition=e['mode']+'-'+str(e['bytes'])
        if e['event']=='MEASUREMENT_START':start=e['utc']-offset
        if e['event']!='MEASUREMENT_END':continue
        end=e['utc']-offset;parts={}
        for role in ['worker','launcher']:
            points=[]
            for x in samples:
                if x['run_id']!=run.name or not start<=x['utc']<=end:continue
                for p in x['pods']:
                    if p['role']==role:points.append((x['utc'],p['cpu']['usage_usec']))
            points.sort()
            if len(points)>=2:
                duration=points[-1][0]-points[0][0]
                parts[role]={'cores':(points[-1][1]-points[0][1])/1e6/duration,'observed_s':duration,'coverage':duration/(end-start),'samples':len(points)}
        total=sum(p['cores'] for p in parts.values()) if len(parts)==2 else None
        rate=e['completed']/e['elapsed']
        rows.append({'run':run.name,'variant':run.name.split('-')[-1],'condition':condition,'parts':parts,
                     'total_cores':total,'iterations_s':rate,'cpu_us_iteration':total/rate*1e6 if total is not None else None})
summary={}
for v in ['base','wait','copy','both']:
    selected=[r for r in rows if r['variant']==v and r['run'].startswith('sf-r') and r['total_cores'] is not None]
    summary[v]={}
    for c in sorted({r['condition'] for r in selected}):
        group=[r for r in selected if r['condition']==c]
        summary[v][c]={'repeats':len(group),'cores':statistics.mean(r['total_cores'] for r in group),
                       'cpu_us_iteration':statistics.mean(r['cpu_us_iteration'] for r in group),
                       'min_coverage':min(p['coverage'] for r in group for p in r['parts'].values())}
save(OUT/'cpu-summary.json',{'scope':'Pod cgroup CPU inside measured windows. Launcher includes QEMU/Guest; copy window includes both directions. Host/Guest alignment uncertainty in clock-map.json.','rows':rows,'summary':summary})
print(json.dumps(summary,indent=2))
