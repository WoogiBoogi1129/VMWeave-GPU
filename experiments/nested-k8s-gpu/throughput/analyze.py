"""Analyze the new run only. Optional plots use the existing evidence venv."""
import csv
import hashlib
import json
from pathlib import Path
import statistics as st

EXP=Path(__file__).resolve().parents[1]
OUT=EXP/'results/20261029-sgemm-throughput'
def main():
    assert json.loads((OUT/'completed.json').read_text())['result']=='PASS'
    runs=[json.loads(p.read_text()) for p in sorted((OUT/'runs').glob('*.json')) if '-pod-' not in p.stem]
    assert len(runs)==12,len(runs)
    indexed={};rows=[]
    for run in runs:
        checks=[r for r in run['records'] if r['event']=='correctness']
        assert len(checks)==3 and all(r['failures']==0 and r['fp64_reference_samples']==32 for r in checks)
        for metric in run['records']:
            if metric['event']!='result':continue
            assert abs(metric['gflops']-2*metric['n']**3*metric['completed_gemms']/metric['seconds']/1e9)<.01
            key=(run['n'],metric['phase'],run['mode'],run['pair']);assert key not in indexed
            indexed[key]=metric['gflops'];rows.append({'mode':run['mode'],'pair':run['pair'],**metric})
        active=json.loads((OUT/'observations'/(run['name']+'-active.json')).read_text())
        reclaimed=json.loads((OUT/'observations'/(run['name']+'-reclaimed.json')).read_text())
        assert active['result']==reclaimed['result']=='PASS'
        assert len(active['host_gpu_processes'])==1 and active['host_gpu_processes'][0]['child_matches']
        assert not reclaimed['children'] and not reclaimed['host_gpu_processes']
    with (OUT/'measurements.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=[]
    for n in (1024,4096):
        for phase in ('resident_compute','transfer_inclusive'):
            guest=[indexed[n,phase,'guest',i] for i in (1,2,3)]
            pod=[indexed[n,phase,'pod',i] for i in (1,2,3)]
            ratios=[p/g for p,g in zip(pod,guest)]
            summary.append({'n':n,'phase':phase,'guest_gflops':guest,'pod_gflops':pod,'guest_median':st.median(guest),'pod_median':st.median(pod),'paired_pod_guest_ratios':ratios,'paired_ratio_median':st.median(ratios),'paired_change_percent':(st.median(ratios)-1)*100})
    before=json.loads((OUT/'inventory/before-measurement-channel.json').read_text())
    after=json.loads((OUT/'inventory/after-channel.json').read_text())
    identities={key:before['status'].get(key)==after['status'].get(key) for key in ('allocation','generation','workerPodUID','gpuUUID','resourcePrefix')}
    assert all(identities.values())
    def controllers(label):return {(x['namespace'],x['kind'],x['name']):x for x in json.loads((OUT/f'inventory/{label}-controllers.json').read_text())}
    b,a=controllers('before-measurement'),controllers('after')
    changed=[list(key) for key in sorted(b.keys()|a.keys()) if b.get(key)!=a.get(key)]
    def pods(label):return {(x['namespace'],x['name']):{'uid':x['uid'],'containers':[(c['name'],c.get('imageID'),c.get('restartCount')) for c in x['containers']]} for x in json.loads((OUT/f'inventory/{label}-outer-pods.json').read_text())}
    bp,ap=pods('before-measurement'),pods('after')
    pod_changes=[list(key) for key in sorted(bp.keys()|ap.keys()) if bp.get(key)!=ap.get(key)]
    monitor=[json.loads(line) for line in (OUT/'gpu-monitor.jsonl').read_text().splitlines()]
    errors=[m for m in monitor if 'error' in m]
    foreign=[m for m in monitor if any(not p['expected_worker'] for p in m.get('processes',[]))]
    result={'scope':'same retained Worker VM, Guest vs Pod, effective completion-delimited FP32 SGEMM throughput','runs':12,'measurement_windows':24,'correctness_checks':36,'summary':summary,'identities_unchanged':identities,'changed_outer_controllers':changed,'changed_outer_pods':pod_changes,'gpu_monitor_samples':len(monitor),'gpu_monitor_errors':errors,'foreign_target_gpu_samples':foreign}
    (OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    for x in summary:print(x['n'],x['phase'],'guest',round(x['guest_median'],2),'pod',round(x['pod_median'],2),'paired_change',round(x['paired_change_percent'],2))
    print('External controller changes:',changed,'pod changes:',pod_changes,'foreign GPU samples:',len(foreign),'monitor errors:',len(errors))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for row,n in enumerate((1024,4096)):
        for col,(phase,title) in enumerate(zip(('resident_compute','transfer_inclusive'),('Inputs resident on GPU','H2D + SGEMM + sync + D2H'))):
            ax=axes[row,col];s=next(x for x in summary if x['n']==n and x['phase']==phase)
            for j,mode in enumerate(('guest','pod')):
                vals=s[mode+'_gflops'];med=st.median(vals)
                ax.bar(j,med,width=.55,color=('#356fa3','#dc8b32')[j],alpha=.85)
                ax.scatter([j-.07,j,j+.07],vals,c='black',s=22,zorder=3)
                ax.text(j,max(vals)*1.04,f'{med:,.2f}',ha='center',fontsize=10)
            ax.set_xticks([0,1],['Guest direct','Kubernetes Pod']);ax.set_ylabel('Effective GFLOP/s');ax.set_title(f'{n} × {n}: {title}');ax.set_ylim(0,max(s['guest_gflops']+s['pod_gflops'])*1.22);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('VMWeave nested Kubernetes: paired SGEMM throughput\nMedian bars; three runs as points; independent panel scales | 2026-10-29 KST',fontsize=12)
    fig.savefig(OUT/'throughput.png',dpi=180);fig.savefig(OUT/'throughput.pdf');plt.close(fig)

if __name__=='__main__':main()
