"""Offline validation and summaries; no cluster/GPU access. Python stdlib except plots."""
import argparse
import csv
import json
import math
import statistics as st
from pathlib import Path

DEFAULT=Path(__file__).resolve().parents[1]/'results/20261030-transfer-app-throughput'
def read(out,name):return json.loads((out/name).read_text())
def percentile(values,p):return sorted(values)[math.ceil(len(values)*p)-1]
def csv_write(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def analyze(out):
    assert read(out,'completed.json')['result']=='PASS'
    runs=[read(out,'runs/'+p.name) for p in sorted((out/'runs').glob('*.json')) if '-pod-' not in p.stem]
    assert len(runs)==18
    transfers=[];apps=[];app_samples=[];seen=set()
    references=read(out,'reference/native-outputs.json')
    for r in runs:
        key=(r['workload'],r['mode'],r['pair']);assert key not in seen;seen.add(key)
        name=r['name']
        for state in ('before','active','reclaimed'):
            o=read(out,'observations/'+name+'-'+state+'.json');assert o['result']=='PASS'
            if state=='active':assert len(o['host_gpu_processes'])==1 and o['host_gpu_processes'][0]['child_matches']
            else:assert not o['host_gpu_processes'] and not o['children']
        if r['mode']=='pod':
            p=read(out,'runs/'+name+'-pod-final.json');assert p['status']['phase']=='Succeeded'
            assert p['spec']['nodeName']=='vw-k8s-worker-01'
            assert all(c['state']['terminated']['exitCode']==0 for c in p['status']['containerStatuses'])
        common={'name':name,'mode':r['mode'],'pair':r['pair']}
        if r['workload']=='copy':
            cells=[x for x in r['records'] if x['event']=='copy_result'];assert len(cells)==8
            assert {(x['bytes'],x['direction']) for x in cells}=={(n,d) for n in (4096,1048576,16777216,67108864) for d in ('H2D','D2H')}
            for x in cells:
                ret=x['api_return_seconds'];done=x['completion_seconds']
                assert x['correct'] and len(ret)==len(done)==x['count'] and x['count']>=20 and x['seconds']>=2
                assert all(0<a<=b for a,b in zip(ret,done))
                bw=x['bytes']*x['count']/x['seconds']/1e9
                assert math.isclose(bw,x['GB_per_second'],rel_tol=1e-6,abs_tol=1e-8)
                assert abs(sum(done)-x['seconds'])<max(.01,.01*x['seconds'])
                transfers.append({**common,'direction':x['direction'],'bytes':x['bytes'],'count':x['count'],'seconds':x['seconds'],
                    'GB_per_second':bw,'mean_completion_ms':1000*st.mean(done),'p50_completion_ms':1000*st.median(done),
                    'p95_completion_ms':1000*percentile(done,.95),'p50_api_return_ms':1000*st.median(ret)})
        else:
            hashes=r['output_hashes'];ref=references[r['workload']]['hashes']['output-02.bin']
            assert r['correct'] and len(hashes)==4 and set(hashes.values())=={ref}
            assert [x['warmup'] for x in r['samples']]==[True,True,False,False]
            samples=[x['seconds'] for x in r['samples'] if not x['warmup']]
            assert len(samples)==2 and min(samples)>0
            for x in r['samples']:app_samples.append({**common,'workload':r['workload'],**x})
            apps.append({**common,'workload':r['workload'],'completed_tasks':2,'seconds':sum(samples),
                         'tasks_per_second':2/sum(samples),'mean_task_ms':1000*st.mean(samples)})
    assert seen=={(w,m,p) for w in ('copy','nw','srad') for m in ('guest','pod') for p in (1,2,3)}
    summary=[]
    for n in (4096,1048576,16777216,67108864):
        for d in ('H2D','D2H'):
            s={'bytes':n,'direction':d}
            for m in ('guest','pod'):
                rs=sorted((x for x in transfers if x['bytes']==n and x['direction']==d and x['mode']==m),key=lambda x:x['pair'])
                s[m]={metric:st.median(x[metric] for x in rs) for metric in ('GB_per_second','p50_completion_ms','p95_completion_ms','p50_api_return_ms')}
                s[m]['run_GB_per_second']=[x['GB_per_second'] for x in rs]
                s[m]['min_GB_per_second']=min(s[m]['run_GB_per_second']);s[m]['max_GB_per_second']=max(s[m]['run_GB_per_second'])
            s['paired_bandwidth_change_percent']=[100*(p/g-1) for g,p in zip(s['guest']['run_GB_per_second'],s['pod']['run_GB_per_second'])]
            s['median_paired_bandwidth_change_percent']=st.median(s['paired_bandwidth_change_percent']);summary.append(s)
    app_summary=[]
    for w in ('nw','srad'):
        s={'workload':w}
        for m in ('guest','pod'):
            rs=sorted((x for x in apps if x['workload']==w and x['mode']==m),key=lambda x:x['pair'])
            vals=[x['tasks_per_second'] for x in rs]
            s[m]={'median_tasks_per_second':st.median(vals),'run_tasks_per_second':vals,
                  'min_tasks_per_second':min(vals),'max_tasks_per_second':max(vals),
                  'median_run_mean_ms':st.median(x['mean_task_ms'] for x in rs)}
        s['paired_throughput_change_percent']=[100*(p/g-1) for g,p in zip(s['guest']['run_tasks_per_second'],s['pod']['run_tasks_per_second'])]
        s['median_paired_throughput_change_percent']=st.median(s['paired_throughput_change_percent']);app_summary.append(s)
    b,a=read(out,'inventory/before-channel.json'),read(out,'inventory/after-channel.json')
    identity={k:b['status'].get(k)==a['status'].get(k) for k in ('allocation','generation','workerPodUID','gpuUUID','resourcePrefix')};assert all(identity.values())
    def controllers(label):return {(x['namespace'],x['kind'],x['name']):x for x in read(out,'inventory/'+label+'-controllers.json')}
    bc,ac=controllers('before'),controllers('after')
    changed=[list(k) for k in sorted(bc.keys()|ac.keys()) if bc.get(k)!=ac.get(k)]
    def pods(label):return {(x['namespace'],x['name']):{'uid':x['uid'],'containers':[(c['name'],c.get('imageID'),c.get('restartCount')) for c in x['containers']]} for x in read(out,'inventory/'+label+'-outer-pods.json')}
    bp,ap=pods('before'),pods('after');pod_changed=[list(k) for k in sorted(bp.keys()|ap.keys()) if bp.get(k)!=ap.get(k)]
    mon=[json.loads(x) for x in (out/'gpu-monitor.jsonl').read_text().splitlines()]
    errors=[x for x in mon if 'error' in x];foreign=[x for x in mon if any(not p['expected_worker'] for p in x.get('processes',[]))]
    assert not errors and not foreign
    nodes=read(out,'inventory/after-inner-nodes.json')['items']
    assert len(nodes)==2 and all(any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']) for n in nodes)
    jobs=read(out,'inventory/final-jobs.json')['items'];assert len(jobs)==9 and all(j['status'].get('succeeded')==1 and not j['status'].get('active') for j in jobs)
    final=read(out,'observations/final-idle.json');assert final['result']=='PASS' and not final['children']
    result={'processes':18,'copy_windows':len(transfers),'application_measured_tasks':24,'application_warmup_tasks':24,
            'full_copy_checks':48,'application_full_output_checks':48,'transfer_summary':summary,'application_summary':app_summary,
            'identities_unchanged':identity,'changed_outer_controllers':changed,'changed_outer_pods':pod_changed,
            'gpu_monitor_samples':len(mon),'gpu_monitor_errors':errors,'foreign_target_gpu_samples':foreign,'completed_jobs':9,'final_idle':True}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    csv_write(out/'transfer-runs.csv',transfers);csv_write(out/'application-runs.csv',apps);csv_write(out/'application-samples.csv',app_samples)
    print(json.dumps(result,indent=2));return result

def plots(out,result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    sizes=[4096,1048576,16777216,67108864];labels=['4 KiB','1 MiB','16 MiB','64 MiB']
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for j,d in enumerate(('H2D','D2H')):
        rows=[next(x for x in result['transfer_summary'] if x['bytes']==n and x['direction']==d) for n in sizes]
        for m,color in (('guest','#356fa3'),('pod','#dc8b32')):
            axes[0,j].plot(labels,[x[m]['GB_per_second'] for x in rows],'-o',label=m,color=color)
            axes[1,j].plot(labels,[x[m]['p50_completion_ms'] for x in rows],'-o',label=m+' p50',color=color)
            axes[1,j].plot(labels,[x[m]['p95_completion_ms'] for x in rows],'--',label=m+' p95',color=color)
        for i in (0,1):axes[i,j].set_title(d);axes[i,j].grid(alpha=.25);axes[i,j].legend(fontsize=8)
        axes[0,j].set_ylabel('Effective bandwidth (GB/s)')
        axes[1,j].set_ylabel('Copy + sync completion (ms, log scale)');axes[1,j].set_yscale('log')
    fig.suptitle('VMWeave nested Kubernetes: isolated copies | 2026-10-30 KST\nMedian of three runs; pageable memory; entire relay path')
    fig.savefig(out/'transfer.png',dpi=180);fig.savefig(out/'transfer.pdf');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(9,4),layout='constrained')
    for ax,s in zip(axes,result['application_summary']):
        for j,m in enumerate(('guest','pod')):
            vals=s[m]['run_tasks_per_second'];med=st.median(vals)
            ax.bar(j,med,width=.55,color=('#356fa3','#dc8b32')[j]);ax.scatter([j-.07,j,j+.07],vals,c='black',s=25,zorder=3)
            ax.text(j,max(vals)*1.04,f'{med:.3f}',ha='center')
        ax.set_title('NW: sequence alignment' if s['workload']=='nw' else 'SRAD: image denoising')
        ax.set_ylabel('Application processing tasks/s');ax.set_xticks([0,1],['Guest direct','Kubernetes Pod'])
        ax.set_ylim(0,1.25*max(s[m]['max_tasks_per_second'] for m in ('guest','pod')));ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('Rodinia: allocation + transfers + algorithm + sync\nThree sessions, two measured tasks/session; startup and CPU input preparation excluded',fontsize=11)
    fig.savefig(out/'applications.png',dpi=180);fig.savefig(out/'applications.pdf');plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=DEFAULT);p.add_argument('--no-plots',action='store_true');a=p.parse_args()
    r=analyze(a.out)
    if not a.no_plots:plots(a.out,r)
