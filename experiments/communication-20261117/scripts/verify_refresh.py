"""Independent standard-library validation of refreshed V and preserved N/F/L."""
import array,csv,gzip,hashlib,json,math,re,statistics,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];Q=P/'refresh-20261118';A=P/'analysis';H=P/'history/v0.5.11'
def load(p):return json.loads(p.read_text())
def table(p):return list(csv.DictReader(p.open()))
def same(a,b):return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-9)
protocol=load(Q/'protocol/frozen.json')
assert hashlib.sha256((Q/'protocol/frozen.json').read_bytes()).hexdigest()==(Q/'protocol/frozen.sha256').read_text().split()[0]
for name,sha in protocol['sources'].items():assert hashlib.sha256((Q/name).read_bytes()).hexdigest()==sha,name
original=load(H/'preserved-original-files.json')
for name,sha in original['sha256'].items():assert hashlib.sha256((P/name).read_bytes()).hexdigest()==sha,name
for line in (H/'SHA256SUMS').read_text().splitlines():
    sha,name=line.split(maxsplit=1)
    if name.startswith('analysis/') or name in ['REPORT.md','README.md','bundle.json','analysis-requirements.txt']:
        assert hashlib.sha256((H/name).read_bytes()).hexdigest()==sha,name
rows=table(A/'blocks.csv');off=table(A/'vmweave-off-blocks.csv');old=table(H/'analysis/blocks.csv')
for mode in 'NFL':
    assert [r for r in rows if r['mode']==mode]==[r for r in old if r['mode']==mode]
    assert [r for r in table(A/'summary.csv') if r['mode']==mode]==[r for r in table(H/'analysis/summary.csv') if r['mode']==mode]
assert len(rows)==320 and len(off)==20 and not table(A/'paired-ratios.csv')
new=[r for r in rows if r['mode']=='V']+off
idx={(int(r['block']),r['mode'],int(r['id'])):r for r in new};assert len(idx)==100
checked=0;quality=[];vmis=set();cuda_pids=set();packets=[]
for entry in protocol['schedule']:
    label=entry['label'];mode='V' if entry['profile']=='ON' else 'V_OFF';d=Q/'results'/label;e=load(d/'execution.json')
    assert e['status']=='passed' and e['returncode']==0 and e['order']==entry['conditions']
    ident=load(Q/'evidence'/(label+'-session.json'));vmis.add(ident['vmi_uid'])
    assert ident['server_pinning'] and all(x['cpus']==[12,13,14,15] for x in ident['server_pinning'])
    assert ident['pinning'] and all(x['cpus']==[8,9,10,11] for x in ident['pinning'])
    claim=load(Q/'evidence'/(label+'-claim.json'))['status']['allocation']['devices']['results']
    assert len(claim)==1 and claim[0]['device']=='hami-gpu-1' and claim[0]['driver']=='hami-core-gpu.project-hami.io'
    assert claim[0]['consumedCapacity']=={'cores':'100','memory':'97887Mi'}
    pod=load(Q/'evidence'/(label+'-pod.json'))
    assert next(c['image'] for c in pod['spec']['containers'] if c['name']=='main')==protocol['images']['worker']
    effective=load(d/'client-effective.json');assert len(effective)==1
    assert set(effective[0]['libraries'].values())=={protocol['guest_sha256']}
    for key,value in protocol['application_environment'][entry['profile']].items():assert effective[0]['environment'][key]==value
    profile=load(Q/'evidence'/(label+'-effective-profile.json'))
    for key,value in protocol['broker_environment'].items():assert profile['broker'][0]['env'][key]==value
    observed=[json.loads(line) for line in (d/'observer.jsonl').read_text().splitlines()]
    foreign=[p for x in observed for p in x.get('target_processes',[]) if not p['owned']]
    thermal=[x for x in observed if 'gpu' in x and int(x['gpu'].split(',')[-1].strip(),16)&(8|32|64|128)]
    assert not foreign and not thermal,label
    pids=[line.split(',')[1].strip() for line in (d/'gpu-processes.csv').read_text().splitlines() if line.startswith(protocol['gpu_uuid'])]
    assert len(pids)==1 and pids[0] not in cuda_pids;cuda_pids.update(pids)
    events=[json.loads(line) for line in (d/'stdout.jsonl').read_text().splitlines() if line.startswith('{')]
    setup=next(x for x in events if x['event']=='SETUP');assert setup['device_count']==1 and setup['input_seed']==20261117
    assert [r['id'] for r in e['results']]==entry['conditions']
    for result in e['results']:
        id=result['id'];r=idx[entry['block'],mode,id];raw=array.array('Q')
        raw.frombytes(gzip.decompress((d/f'c{id:02d}.u64.gz').read_bytes()))
        if sys.byteorder!='little':raw.byteswap()
        n=len(raw);assert n==result['completed']==int(r['samples']) and min(raw)>0
        assert result['correctness']=='PASS' and result['elapsed_ns']>=30_000_000_000 and sum(raw)<=result['elapsed_ns']
        assert result['final_sequence']==result['total_launches']%(1<<32)
        assert same(statistics.mean(raw)/1000,r['mean_us'])
        raw=sorted(raw)
        def quantile(p):
            x=(n-1)*p;lo=int(x);return (raw[lo]+(raw[min(lo+1,n-1)]-raw[lo])*(x-lo))/1000
        assert same(quantile(.5),r['p50_us'])
        if n>=1000:assert same(quantile(.95),r['p95_us'])
        else:assert r['p95_us']==''
        rate=n*(result['K'] or result['bytes']/2**30)/(result['elapsed_ns']/1e9)
        assert same(rate,r['kernels_s'] if result['K'] else r['GiB_s'])
        checked+=n
    if entry['profile']=='ON':
        m=re.findall(r'kernel-batch packets=(\d+) submitted=(\d+) terminal_error=(\d+)',(d/'stderr.txt').read_text());assert len(m)==1
        count,submitted,error=map(int,m[0]);assert not error and submitted==e['results'][-1]['total_launches']
        assert 0<submitted/count<=128
        packets.append(dict(block=entry['block'],packets=count,submitted=submitted,launches_per_packet=submitted/count,scope='whole process including warmup/correctness and all K values'))
    else:assert 'kernel-batch v1 enabled' not in (d/'stderr.txt').read_text()
    assert load(Q/'evidence'/(label+'-released.json'))['gpu_idle']
    quality.append(dict(session=label,observer_samples=len(observed),foreign_gpu_processes=len(foreign),hardware_thermal_slowdown_samples=len(thermal),gpu_query_errors=sum('gpu_error' in x for x in observed),process_check_errors=sum('process_check_error' in x for x in observed)))
assert len(vmis)==5 and len(cuda_pids)==10
for b in range(1,6):assert load(Q/'evidence'/f'b{b}-ON-session.json')['vmi_uid']==load(Q/'evidence'/f'b{b}-OFF-session.json')['vmi_uid']
for g in table(A/'summary.csv')+table(A/'vmweave-off-summary.csv'):
    if g['mode'] not in ['V','V_OFF']:continue
    for field in ['p50_us','p95_us','GiB_s','kernels_s','amortized_us','path_cpu_s']:
        vals=[idx[b,g['mode'],int(g['id'])][field] for b in range(1,6)]
        if any(x=='' for x in vals):assert g[field+'_mean']=='';continue
        vals=list(map(float,vals));m=statistics.mean(vals);h=2.7764451051977987*statistics.stdev(vals)/math.sqrt(5)
        for key,v in zip(['mean','low95','high95'],[m,m-h,m+h]):assert same(g[field+'_'+key],v)
for r in table(A/'vmweave-batch-paired.csv'):
    logs=[math.log(float(idx[b,'V',int(r['id'])][r['metric']])/float(idx[b,'V_OFF',int(r['id'])][r['metric']])) for b in range(1,6)]
    m=statistics.mean(logs);h=2.7764451051977987*statistics.stdev(logs)/math.sqrt(5)
    for key,v in zip(['ratio_ON_over_OFF','low95','high95'],[m,m-h,m+h]):assert same(r[key],math.exp(v))
    expected='PASS' if float(r['high95'])<=1.05 else 'REGRESSION' if float(r['low95'])>1.05 else 'INCONCLUSIVE'
    assert r['nonregression_5pct']==expected
summary={(r['mode'],int(r['id'])):r for r in table(A/'summary.csv')}
for r in table(A/'cross-campaign-ratios.csv'):
    den=r['comparison'][-1];id=int(r['id']);field=r['metric']+'_mean'
    assert r['inference']=='descriptive_only_different_campaigns'
    assert same(r['ratio_of_block_means'],float(summary['V',id][field])/float(summary[den,id][field]))
old_native=table(H/'analysis/native-deltas.csv');new_native=table(A/'native-deltas.csv')
assert [r for r in old_native if r['mode']!='V']==[r for r in new_native if r['mode']!='V']
for r in new_native:
    if r['mode']=='V':assert r['low95']==r['high95']==r['bandwidth_low95']==r['bandwidth_high95']==''
assert load(Q/'evidence/cleanup-complete.json')['namespace_removed'] and load(Q/'evidence/final-resource-audit.json')['passed']
out=dict(passed=True,new_intervals=100,main_composite_intervals=320,new_raw_samples_checked=checked,historical_NFL_intervals_preserved=240,historical_NFL_aggregates_identical=True,original_files_verified=len(original['sha256']),vm_boots=5,unique_cuda_children=10,independent_method='Python standard library array/sort/statistics; no analyzer imports',cross_campaign_paired_CIs_removed=True,quality=quality,batch_packets=packets)
(A/'independent-verification.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['quality','batch_packets']},indent=2))
