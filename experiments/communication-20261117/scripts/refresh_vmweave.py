"""Rebuild the comparison using published VMWeave ON; preserve historical N/F/L.

Run only after refresh-20261118 contains completed, cleaned-up measurements.
The original analyzers remain unchanged for historical provenance; this is the
current analysis entry point. Cross-campaign observations are never paired.
"""
import csv,gzip,hashlib,json,math,statistics
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
Q=P/'refresh-20261118'
H=P/'history/v0.5.11/analysis'
A=P/'analysis'
T=2.7764451051977987
def load(p):return json.loads(p.read_text())
def table(p):return list(csv.DictReader(p.open()))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def write(p,rows,fields=None):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def ci(values):
    assert len(values)==5
    m=statistics.mean(values);h=T*statistics.stdev(values)/math.sqrt(5)
    return [m,m-h,m+h]
def number(x):return float(x) if x not in ('',None) else None
def analyze():
    protocol=load(Q/'protocol/frozen.json');assert protocol['main_profile']=='ON'
    assert load(Q/'evidence/cleanup-complete.json')['namespace_removed']
    oldrows=table(H/'blocks.csv');oldsummary=table(H/'summary.csv')
    fields=list(oldrows[0]);summary_fields=list(oldsummary[0]);new=[];source=[];quality=[]
    for entry in protocol['schedule']:
        label=entry['label'];d=Q/'results'/label;e=load(d/'execution.json')
        assert e['status']=='passed' and e['returncode']==0 and e['order']==entry['conditions']
        assert (Q/'evidence'/(label+'-released.json')).exists()
        identity=load(Q/'evidence'/(label+'-session.json'));obs=[json.loads(l) for l in (d/'observer.jsonl').read_text().splitlines()]
        clock=min(identity['clocks'],key=lambda c:c['host_after_ns']-c['host_before_ns'])
        offset=clock['guest_ns']-(clock['host_after_ns']+clock['host_before_ns'])/2
        quality.append(dict(label=label,clock_offset_ms=offset/1e6,clock_uncertainty_ms=(clock['host_after_ns']-clock['host_before_ns'])/2e6))
        for r in e['results']:
            raw=np.frombuffer(gzip.decompress((d/f'c{r["id"]:02d}.u64.gz').read_bytes()),dtype='<u8')
            assert len(raw)==r['completed'] and len(raw)>0 and np.all(raw>0)
            assert r['correctness']=='PASS' and r['elapsed_ns']>=30e9 and int(raw.sum())<=r['elapsed_ns']
            sec=r['elapsed_ns']/1e9;k=r['K'];n=len(raw)
            row=dict(block=entry['block'],mode='V' if entry['profile']=='ON' else 'V_OFF',id=r['id'],direction=r['direction'],bytes=r['bytes'],K=k,samples=n,elapsed_s=sec,p50_us=float(np.quantile(raw,.5)/1000),p95_us=float(np.quantile(raw,.95)/1000) if n>=1000 else None,mean_us=float(np.mean(raw)/1000),GiB_s=r['bytes']*n/sec/2**30 if not k else None,kernels_s=k*n/sec if k else None,amortized_us=sec*1e6/(n*k) if k else None,client_cpu_s=r['client_cpu_ns']/1e9,path_cpu_s=None,cpu_core_s_per_operation=None,cpu_core_s_per_GiB=None,cpu_throttled_s=None)
            begin=r['start_utc_ns']-offset;end=r['end_utc_ns']-offset
            usable=[x for x in obs if all(role in x['cpu'] for role in ['server','qemu'])]
            if usable and usable[0]['utc_ns']<=begin and usable[-1]['utc_ns']>=end:
                ts=np.asarray([x['utc_ns'] for x in usable],dtype=float)
                vals=[sum(x['cpu'][role]['usage_usec'] for role in ['server','qemu']) for x in usable]
                delta=float((np.interp(end,ts,vals)-np.interp(begin,ts,vals))/1e6)
                th=[sum(x['cpu'][role].get('throttled_usec',0) for role in ['server','qemu']) for x in usable]
                row.update(path_cpu_s=delta,cpu_core_s_per_operation=delta/(n*(k or 1)),cpu_core_s_per_GiB=delta/(r['bytes']*n/2**30) if not k else None,cpu_throttled_s=float((np.interp(end,ts,th)-np.interp(begin,ts,th))/1e6))
            new.append(row);source.append(dict(block=entry['block'],mode=row['mode'],id=r['id'],session=label,path=str(d.relative_to(P)),release='v0.5.12',batch=entry['profile']))
    assert len(new)==100 and sum(r['mode']=='V' for r in new)==80
    rows=[r for r in oldrows if r['mode']!='V']+[r for r in new if r['mode']=='V']
    write(A/'blocks.csv',rows,fields);write(A/'vmweave-off-blocks.csv',[r for r in new if r['mode']=='V_OFF'],fields)
    summaries=[]
    for mode in ['V','V_OFF']:
        for id in (range(16) if mode=='V' else [0,13,14,15]):
            rs=[r for r in new if r['mode']==mode and r['id']==id];assert len(rs)==5
            g=dict(mode=mode,id=id,direction=rs[0]['direction'],bytes=rs[0]['bytes'],K=rs[0]['K'],p95_available_blocks=sum(r['p95_us'] is not None for r in rs),min_samples=min(r['samples'] for r in rs))
            for key in ['p50_us','p95_us','GiB_s','kernels_s','amortized_us','path_cpu_s']:
                xs=[r[key] for r in rs];c=ci(xs) if all(x is not None for x in xs) else [None]*3
                g.update({key+'_'+n:v for n,v in zip(['mean','low95','high95'],c)})
            summaries.append(g)
    main=[r for r in oldsummary if r['mode']!='V']+[r for r in summaries if r['mode']=='V']
    write(A/'summary.csv',main,summary_fields);write(A/'vmweave-off-summary.csv',[r for r in summaries if r['mode']=='V_OFF'],summary_fields)
    pairs=[]
    for id in [0,13,14,15]:
        metric='mean_us' if id==0 else 'amortized_us'
        lookup={(r['block'],r['mode']):r for r in new if r['id']==id}
        c=[math.exp(x) for x in ci([math.log(lookup[b,'V'][metric]/lookup[b,'V_OFF'][metric]) for b in range(1,6)])]
        pairs.append(dict(id=id,K=lookup[1,'V']['K'],metric=metric,ratio_ON_over_OFF=c[0],low95=c[1],high95=c[2],nonregression_5pct='PASS' if c[2]<=1.05 else 'REGRESSION' if c[1]>1.05 else 'INCONCLUSIVE',reference_mean=statistics.mean(lookup[b,'V_OFF'][metric] for b in range(1,6)),candidate_mean=statistics.mean(lookup[b,'V'][metric] for b in range(1,6))))
    write(A/'vmweave-batch-paired.csv',pairs)
    idx={(r['mode'],int(r['id'])):r for r in main};cross=[]
    for id in range(16):
        for den in ['N','F','L']:
            for metric in ['p50_us','GiB_s','kernels_s']:
                v=number(idx['V',id][metric+'_mean']);d=number(idx[den,id][metric+'_mean'])
                if v is not None and d is not None:cross.append(dict(id=id,comparison='V/'+den,metric=metric,ratio_of_block_means=v/d,inference='descriptive_only_different_campaigns'))
    write(A/'cross-campaign-ratios.csv',cross)
    # Do not leave the previous paired V/F or V/L confidence intervals active.
    write(A/'paired-ratios.csv',[],list(table(H/'paired-ratios.csv')[0]))
    native=[r for r in table(H/'native-deltas.csv') if r['mode']!='V']
    for id in range(16):
        v=idx['V',id];n=idx['N',id]
        native.append(dict(id=id,mode='V',p50_added_us=number(v['p50_us_mean'])-number(n['p50_us_mean']),low95=None,high95=None,bandwidth_retention_ratio=number(v['GiB_s_mean'])/number(n['GiB_s_mean']) if id in range(1,13) else None,bandwidth_low95=None,bandwidth_high95=None))
    write(A/'native-deltas.csv',native)
    save(A/'selection.json',dict(main_intervals=320,retained_historical_intervals=240,replaced_vmweave_intervals=80,additional_batch_off_intervals=20,vmweave_version='v0.5.12',vmweave_main_profile='optimized + batch ON',not_deployment_default=True,original_vmweave='results/b[1-5]-V; superseded, retained unchanged',historical_analyses='history/v0.5.11/analysis',original_report='REPORT-v0.5.11.md',pairing='Only refreshed OFF/ON share paired blocks. Never pair new V with historical N/F/L.',new_sources=source))
    save(A/'clock-quality.json',quality)
    save(A/'validation.json',dict(complete=True,main_intervals=320,new_intervals=100,original_other_backends_unchanged=True,statistics='t4 intervals within each backend; cross-campaign ratios descriptive only; paired log-ratios only for refreshed V ON/OFF'))
    # Historical external-environment findings remain historical, not refresh evidence.
    for name in ['environment-quality.json','metadata-verification.json']:
        save(A/name,dict(status='see_versioned_evidence',historical='history/v0.5.11/analysis/'+name,refresh='refresh-20261118/evidence',selection='selection.json'))
    write(A/'environment-sensitivity.csv',[],list(table(H/'environment-sensitivity.csv')[0]))
    return rows,main,new,summaries,pairs

def plots(main,off):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'N':'#64748b','V':'#2563eb','F':'#d97706','L':'#059669'}
    labels={'N':'Native (historical)','V':'VMWeave 0.5.12 ON (new)','F':'Flyt TCP (historical)','L':'Lupine (historical)'}
    for metric,name,ylabel,logy in [('GiB_s','transfer-bandwidth','Completed payload / elapsed time (GiB/s)',False),('p50_us','transfer-latency','Mean block p50 completion latency (us)',True)]:
        fig,axs=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
        for ax,direction in zip(axs,['H2D','D2H']):
            for mode in 'NVFL':
                rs=sorted([r for r in main if r['mode']==mode and r['direction']==direction],key=lambda r:int(r['bytes']))
                x=[int(r['bytes']) for r in rs];y=[number(r[metric+'_mean']) for r in rs]
                ax.plot(x,y,'o-',color=colors[mode],label=labels[mode])
                if not logy:ax.fill_between(x,[max(0,number(r[metric+'_low95'])) for r in rs],[number(r[metric+'_high95']) for r in rs],color=colors[mode],alpha=.1)
            ax.set_xscale('log',base=2)
            if logy:ax.set_yscale('log')
            ax.set_xticks([4,4096,65536,1048576,16777216,67108864],['4 B','4 KiB','64 KiB','1 MiB','16 MiB','64 MiB'],rotation=30);ax.set_title(direction);ax.set_ylabel(ylabel);ax.grid(alpha=.2)
        axs[1].legend(fontsize=8);fig.suptitle('Different measurement campaigns; descriptive comparison',fontsize=10)
        for ext in ['png','svg']:fig.savefig(A/(name+'.'+ext),dpi=180)
        plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for j,mode in enumerate('NVFL'):
        r=next(r for r in main if r['mode']==mode and int(r['id'])==0);m=number(r['p50_us_mean'])
        axs[0].bar(j,m,color=colors[mode],yerr=[[m-number(r['p50_us_low95'])],[number(r['p50_us_high95'])-m]],capsize=4)
        rs=sorted([r for r in main if r['mode']==mode and r['direction']=='kernel'],key=lambda r:int(r['K']))
        axs[1].plot([int(r['K']) for r in rs],[number(r['kernels_s_mean']) for r in rs],'o-',color=colors[mode],label=labels[mode])
    axs[0].set_xticks(range(4),['N (old)','V (new, ON)','F (old)','L (old)']);axs[0].set_ylabel('Mean block p50 latency (us)');axs[0].set_title('One kernel + synchronization')
    axs[1].set_xscale('log');axs[1].set_yscale('log');axs[1].set_xlabel('K launches / synchronization');axs[1].set_ylabel('Completed kernels/s')
    fig.legend(*axs[1].get_legend_handles_labels(),loc='outside lower center',ncols=2,fontsize=8)
    fig.suptitle('Different campaigns; VMWeave batching explicitly enabled',fontsize=10)
    for ext in ['png','svg']:fig.savefig(A/('kernel-path.'+ext),dpi=180)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4),layout='constrained')
    for rows,label,color in [(main,'Batch ON','#2563eb'),(off,'Batch OFF','#64748b')]:
        rs=sorted([r for r in rows if r['mode'] in ['V','V_OFF'] and r['direction']=='kernel'],key=lambda r:int(r['K']))
        ax.plot([int(r['K']) for r in rs],[number(r['kernels_s_mean']) for r in rs],'o-',label=label,color=color)
    ax.set_xscale('log');ax.set_yscale('log');ax.set_xlabel('K launches / synchronization');ax.set_ylabel('Completed kernels/s');ax.set_title('Same v0.5.12 binaries: paired OFF / ON');ax.legend();ax.grid(alpha=.2)
    for ext in ['png','svg']:fig.savefig(A/('vmweave-batch.'+ext),dpi=180)
    plt.close(fig)

if __name__=='__main__':
    rows,main,new,summaries,pairs=analyze();plots(main,[r for r in summaries if r['mode']=='V_OFF'])
    print('Updated 80 VMWeave rows; preserved 240 historical N/F/L rows; 20 OFF intervals separate')
