"""Read-only source analysis; writes derived files only beside this script. No GPU access."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics as st

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
AI=ROOT/'experiments/ai-passthrough/results'
CURRENT=OUT.parent/'20261029-sgemm-throughput'
inputs={}
def read(p,kind='json'):
    p=Path(p);data=p.read_bytes();inputs[str(p.relative_to(ROOT))]=hashlib.sha256(data).hexdigest()
    if kind=='json':return json.loads(data)
    if kind=='csv':return list(csv.DictReader(data.decode().splitlines()))
    return data.decode()
def close(a,b):assert math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-8),(a,b)

def main():
    current=read(CURRENT/'summary.json');raw=read(CURRENT/'measurements.csv','csv');assert len(raw)==24
    for row in current['summary']:
        for mode in ('guest','pod'):
            samples=[r for r in raw if int(r['n'])==row['n'] and r['phase']==row['phase'] and r['mode']==mode]
            assert len(samples)==3
            close(st.median(float(r['gflops']) for r in samples),row[mode+'_median'])
            for r in samples:close(float(r['gflops']),2*int(r['n'])**3*int(r['completed_gemms'])/float(r['seconds'])/1e9)
    old=read(AI/'20261022-sgemm-bestcase/summary.json');oldraw=read(AI/'20261022-sgemm-bestcase/measurements.csv','csv')
    old_manifest=read(AI/'20261022-sgemm-bestcase/manifest.json')
    sgemm_reference=[]
    for mode in ('vmweave','passthrough'):
        r=next(r for r in oldraw if r['stage']=='explore' and int(r['n'])==4096 and r['backend']==mode)
        close(float(r['tflops']),2*4096**3*int(r['completed_gemms'])/float(r['seconds'])/1e12)
        sgemm_reference.append({'experiment':'20261022-exploration','mode':mode,'n':4096,'tflops':float(r['tflops']),'independent_runs':1,'sync_every':16,'minimum_seconds':60,'compute_quota_percent':100})
        formal=[float(r['tflops']) for r in oldraw if r['stage'] in ('b1','b2','b3') and r['backend']==mode]
        assert len(formal)==3;close(st.median(formal),old['mode_summary'][mode]['median_tflops'])
    for mode in ('guest','pod'):
        r=next(r for r in current['summary'] if r['n']==4096 and r['phase']=='resident_compute')
        sgemm_reference.append({'experiment':'20261029-nested','mode':mode,'n':4096,'tflops':r[mode+'_median']/1000,'independent_runs':3,'sync_every':1,'minimum_seconds':5,'compute_quota_percent':50})
    steady=read(AI/'20261026-rodinia-steady/comparison.json');steadyraw=read(AI/'20261026-rodinia-steady/raw.csv','csv');assert len(steadyraw)==160
    read(AI/'20261026-rodinia-steady/manifest.json')
    rodinia=[]
    for work in ('nw','lu','srad','sc'):
        pt=next(r['mean_s'] for r in steady if r['workload']==work and r['mode']=='passthrough')
        for mode in ('native','passthrough','flyt','vmweave'):
            r=next(r for r in steady if r['workload']==work and r['mode']==mode)
            samples=[x for x in steadyraw if x['workload']==work and x['mode']==mode]
            assert len(samples)==10 and len({x['session'] for x in samples})==5
            for session in {x['session'] for x in samples}:assert len([x for x in samples if x['session']==session])==2
            vals=[float(x['seconds']) for x in samples];close(st.mean(vals),r['mean_s']);close(st.stdev(vals),r['std_s'])
            if mode!='native':rodinia.append({'workload':work,'mode':mode,'mean_seconds':r['mean_s'],'std_seconds':r['std_s'],'time_ratio_vs_passthrough':r['mean_s']/pt,'relative_throughput_percent':100*pt/r['mean_s'],'samples':10,'independent_sessions':5})
    cold=read(AI/'20261025-rodinia-threeway/comparison.json');coldraw=read(AI/'20261025-rodinia-threeway/raw.csv','csv');assert len(coldraw)==18
    for r in cold:
        vals=[float(x['seconds']) for x in coldraw if x['workload']==r['workload'] and x['mode']==r['mode']]
        assert len(vals)==3;close(st.median(vals),r['median_seconds'])
    candidate=read(AI/'20261027-path-optimization-vm/comparison.json')
    candidate_rows=read(AI/'20261027-path-optimization-vm/workloads.csv','csv')
    for r in candidate_rows:
        for mode,key in [('flyt','flyt_median_s'),('control','control_median_s'),('candidate','candidate_median_s')]:
            x=next(x for x in candidate['raw_workload_summary'] if x['mode']==mode and x['workload']==r['workload'])
            close(float(r[key]),st.median(x['session_medians_s']))
    for p in [CURRENT/'REPORT.md',CURRENT/'PLAN.md',ROOT/'experiments/nested-k8s-gpu/throughput/sgemm.c',
              OUT.parent/'20261028-minimal/versions.json',AI/'20261022-sgemm-bestcase/REPORT.md',AI/'20261022-sgemm-bestcase/bench.py',
              AI/'20261026-rodinia-steady/README.md',AI/'20261026-rodinia-steady/REPORT.txt',
              AI/'20261026-rodinia-steady/reproduction/rodinia_campaign.py',AI/'20261026-rodinia-steady/reproduction/measure.py',
              AI/'20261025-rodinia-threeway/README.md',AI/'20261027-path-optimization-vm/REPORT.md']:
        read(p,'text')
    for dirname,manifest_type in [('20261022-sgemm-bestcase','text'),('20261025-rodinia-threeway','json'),('20261026-rodinia-steady','json')]:
        base=AI/dirname
        if manifest_type=='text':expected=dict((name,digest) for digest,name in (line.split('  ',1) for line in (base/'SHA256SUMS').read_text().splitlines()))
        else:expected=json.loads((base/'SHA256SUMS.json').read_text())
        for path,digest in inputs.items():
            p=ROOT/path
            if p.is_relative_to(base):
                name=str(p.relative_to(base));assert name in expected and expected[name]==digest,(dirname,name)
    output={'scope':'historical evidence comparison; no new GPU run; no cross-protocol speedup inference',
            'current_sgemm':current['summary'],'historical_sgemm_4096_reference_only':sgemm_reference,
            'historical_sgemm_16384_formal':old['mode_summary'],'historical_sgemm_paired_geomean_ratio':old['paired_geomean_ratio'],
            'rodinia_steady':rodinia,'rodinia_initialization_inclusive':cold,'path_optimization_candidate':candidate_rows,
            'candidate_status':candidate['status'],'flyt_matched_sgemm':'NOT_AVAILABLE_IN_REVIEWED_EVIDENCE'}
    (OUT/'comparison.json').write_text(json.dumps(output,indent=2)+'\n')
    (OUT/'source-hashes.json').write_text(json.dumps(inputs,indent=2)+'\n')
    for name,data in [('sgemm-reference.csv',sgemm_reference),('rodinia-steady.csv',rodinia)]:
        with (OUT/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4.5),layout='constrained')
    for ax,data,labels,title in [(axes[0],sgemm_reference[2:],['Guest direct','Inner Pod'],'2026-10-29 | 50% quota | sync every GEMM\n5 s/run; median of 3'),(axes[1],sgemm_reference[:2],['VMWeave v0.5.2','Passthrough'],'2026-10-22 | 100% quota | sync every 16\n60 s/run; exploration n=1')]:
        vals=[r['tflops'] for r in data];bars=ax.bar(labels,vals,color=['#356fa3','#dc8b32']);ax.bar_label(bars,fmt='%.3f',padding=4)
        ax.set_ylim(0,90);ax.set_ylabel('Effective TFLOP/s');ax.set_title(title,fontsize=10);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('FP32 SGEMM N=4096: historical context, NOT a controlled four-way ranking',fontsize=11)
    fig.savefig(OUT/'sgemm-context.png',dpi=180);fig.savefig(OUT/'sgemm-context.pdf');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.8),layout='constrained')
    for j,mode in enumerate(('passthrough','flyt','vmweave')):
        vals=[next(r['time_ratio_vs_passthrough'] for r in rodinia if r['mode']==mode and r['workload']==work) for work in ('nw','lu','srad','sc')]
        bars=ax.bar([i+(j-1)*.25 for i in range(4)],vals,width=.23,label={'passthrough':'Passthrough','flyt':'Flyt SHM','vmweave':'VMWeave v0.5.3'}[mode]);ax.bar_label(bars,fmt='%.2fx',padding=3,fontsize=9)
    ax.set_xticks(range(4),['NW 2048','LU 2064','SRAD 2048','StreamCluster']);ax.set_ylabel('Mean time / Passthrough mean time (lower is better)');ax.set_ylim(0,38);ax.legend();ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    ax.set_title('2026-10-26 steady-state Rodinia only\n5 sessions × 2 samples; no nested-Pod measurement',fontsize=12)
    fig.savefig(OUT/'rodinia-context.png',dpi=180);fig.savefig(OUT/'rodinia-context.pdf');plt.close(fig)
    print('PASS: 24 current SGEMM windows, historical SGEMM, 160 Rodinia samples, 18 initialization-inclusive samples, candidate medians; source hashes')
    print(json.dumps(rodinia,indent=2))

if __name__=='__main__':main()
