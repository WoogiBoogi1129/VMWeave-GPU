"""Audit formal measurements without contacting the cluster."""
from common import *
from evidence_io import read_text,exists
import hashlib,lzma
analysis=json.loads((OUT/'analysis.json').read_text())
summary=json.loads((OUT/'summary.json').read_text())
main=json.loads((OUT/'protocol-main.json').read_text())
follow=json.loads((OUT/'protocol-followup.json').read_text())
assert (OUT/'main-complete.json').exists() and (OUT/'followup-complete.json').exists()
expected={f'hd-main-v2-r{r}-{p}':4 for r in range(1,6) for p in ['t','s']}
expected.update({s['name']:5 if s['mode']=='regression' else 2 if s['mode']=='patterns' else 1 for s in follow['sessions']})
final_hash=json.loads((OUT/'build/final-runtime-hashes.json').read_text())
checks=[]
for name,count in expected.items():
    d=OUT/'runs'/name;rows=[r for r in analysis['rows'] if r['run']==name]
    assert len(rows)==count,(name,len(rows),count)
    assert not (d/'failure.json').exists(),name
    e=json.loads((d/'execution.json').read_text());assert e['exit_code']==0 and len(e['results'])==count
    assert all(r['status']=='PASS' and r['mismatches']==0 for r in e['results'])
    v=json.loads((d/'output-validation.json').read_text());assert len(v)==count and all(r['pass'] and r['sha256']==r['expected'] for r in v)
    assert sorted(r['bytes'] for r in v)==sorted(r['bytes'] for r in e['results'])
    for result in e['results']:
        assert sum(x['file'].endswith('-'+result['mode']+'-'+str(result['bytes'])+'.output.bin') for x in v)==1
    clean=json.loads((d/'cleanup.json').read_text());assert clean['released']
    identity=json.loads((d/'identity.json').read_text());assert identity['gpu_uuid']==GPU
    path=rows[0]['path'];libs=json.loads((d/'runtime-libraries.json').read_text())
    expected_guest=main['runtime_hashes']['libflyt_guest.so' if path=='S' else 'cricket-client.so'] if name.startswith('hd-main') else final_hash['libflyt_guest.so']
    effective={Path(line.split()[1]).name:line.split()[0] for line in (d/'guest-effective-hashes.txt').read_text().splitlines()}
    assert effective['libflyt_guest.so' if path=='S' else 'cricket-client.so']==expected_guest
    expected_probe=main['runtime_hashes']['probe-'+path] if name.startswith('hd-main') else follow['hashes']['probe-S']
    assert effective['probe-'+path]==expected_probe
    if path=='S':
        released=json.loads((d/'channel-released.json').read_text());assert released['status']['phase']=='Released' and released['metadata']['uid']==identity['channel_uid']==clean['uid']
        expected_worker=main['runtime_hashes']['flyt-shm-worker'] if name.startswith('hd-main') else final_hash['flyt-shm-worker']
        assert libs and all(l['executable_sha256']==expected_worker for l in libs)
        assert all(l['environment']['GPU_CORE_UTILIZATION_POLICY']=='FORCE' and l['environment']['CUDA_DEVICE_SM_LIMIT']=='100' and any('libvgpu' in f for f in l['library_hashes']) for l in libs)
        if not name.startswith('hd-main'):
            assert 'HD_WORKER_EXIT,0\n' in read_text(d/'worker-stream.txt')
            status=json.loads((d/'worker-final-status.json').read_text());assert status.get('deleted_after_exit_marker') or status['status']['phase']=='Succeeded'
            assert all(l['environment']['HD_METRICS']==str(int(rows[0]['metrics'])) for l in libs)
    else:
        assert identity['sm_count']==188 and identity['vm_ip']!=identity['cell_ip']
        assert all(not any('libvgpu' in f for f in l['library_hashes']) for l in libs)
        events=[json.loads(l) for l in read_text(d/'stdout.jsonl').splitlines() if l.startswith('{')]
        transport=next(x for x in events if x['event']=='TRANSPORT');assert transport['socktype']==1 and transport['connection_is_local']==0
    for row in rows:
        target=60 if row['bytes']==16777216 and row['mode']=='copy' or name.startswith('hd-main') else 10
        assert target<=row['elapsed']<target+1,(name,row['elapsed'])
        assert row['seconds']==target and row['warmup_min_s']==(10 if target==60 else 3)
        assert row['warmup_elapsed']>=row['warmup_min_s'] and row['warmup_completed']>=50
    checks.append({'run':name,'windows':count,'samples':sum(r['completed'] for r in rows),'correctness':True,'effective_binaries_and_policy':True,'released':True})
assert all(c['samples_valid'] and c['dropped_records']==0 and c['all_results_pass'] for c in analysis['checks'])
for phase in ['main','cause','confirm']:
    assert all(g['first_seconds']['mean']['repeats']==5 for g in summary['groups'] if g['phase']==phase)
prior=json.loads((OUT/'prior-sha256.json').read_text())
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in prior.items())
archives=[]
if (OUT/'archive-manifest.json').exists():
    for r in json.loads((OUT/'archive-manifest.json').read_text()):
        raw=(OUT/r['archive']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['archive_sha256'];assert hashlib.sha256(lzma.decompress(raw)).hexdigest()==r['sha256'];archives.append(r['archive'])
mapping_checks=[]
for name in ['hd-confirm-r1-original','hd-confirm-r1-direct']:
    records=[json.loads(line) for line in read_text(OUT/'runs'/name/'mapping-component.jsonl').splitlines()]
    assert len(records)==16 and {(r['bytes'],r['mode']) for r in records}=={(n*1048576,m) for n in [4,8,12,16] for m in range(4)}
    assert all(r['verified'] and r['count']>=80 and 0<r['min_ms']<=r['mean_ms']<=r['max_ms'] for r in records)
    mapping_checks.append({'run':name,'conditions':len(records),'verified':True})
failures=[{'run':p.parent.name,**json.loads(p.read_text())} for p in sorted((OUT/'runs').glob('*/failure.json'))]
cpu=json.loads((OUT/'cpu-analysis.json').read_text())
primary_cpu=[r for r in cpu['rows'] if r['run'] in expected and r['mode']=='copy' and r['bytes']==16777216]
assert len(primary_cpu)==len(expected) and all(r['cores'] is not None for r in primary_cpu)
min_coverage=min(p['coverage'] for r in primary_cpu for p in r['parts'].values())
assert min_coverage>=.9,min_coverage
save(OUT/'validation.json',{'status':'PASS','formal_sessions':len(checks),'formal_windows':sum(c['windows'] for c in checks),'formal_samples':sum(c['samples'] for c in checks),'runs':checks,'prior_files_unchanged':len(prior),'lossless_archives_checked':len(archives),'mapping_components':mapping_checks,'failed_attempts_excluded':failures,'minimum_primary_cpu_coverage':min_coverage,'limits':'PASS checks integrity/correctness and campaign conditions, not production compatibility, statistical significance, or HAMi cap enforcement.'})
print('PASS:',len(checks),'formal sessions;',sum(c['windows'] for c in checks),'windows')
