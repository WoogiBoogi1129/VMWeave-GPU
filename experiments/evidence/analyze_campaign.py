"""Analyze completed runs without converting missing/failed evidence into PASS.

All time windows are host UTC. GPU samples use bounded zero-order hold (<=3 s).
Interference counts include only complete progress chunks inside the common window.
Run with the evidence matplotlib venv; safe to repeat while measurements continue.
"""
import argparse
import csv
import gzip
import json
import statistics
from collections import defaultdict
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text())


def json_lines(path):
    if not path.exists():
        compressed=path.with_name(path.name+'.gz')
        if not compressed.exists() and (path.parent/'samples'/compressed.name).exists():
            compressed=path.parent/'samples'/compressed.name
        if not compressed.exists():
            if path.name=='cpu-pinning.txt' and path.with_suffix('.json').exists():
                yield from read_json(path.with_suffix('.json'))
            return
        stream=gzip.open(compressed,'rt')
    else:
        stream=path.open()
    with stream:
        for line in stream:
            try:
                yield json.loads(line)
            except ValueError:
                continue  # interrupted final write is not a measurement


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.unlink(missing_ok=True)
        return
    if rows:
        keys = list(dict.fromkeys(k for row in rows for k in row))
        with path.open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)


def weighted_samples(samples, start, end, max_gap=3):
    area = coverage = 0.0
    selected = []
    for left, right in zip(samples, samples[1:]):
        t, value = left
        next_t = right[0]
        a, b = max(t, start), min(next_t, end)
        if b > a and 0 < next_t - t <= max_gap:
            area += value * (b - a)
            coverage += b - a
            selected.append(value)
    return {'gpu_utilization_mean_percent': area / coverage if coverage else None,
            'gpu_sample_coverage_fraction': coverage / (end - start),
            'gpu_utilization_min_percent': min(selected) if selected else None,
            'gpu_utilization_max_percent': max(selected) if selected else None}


def chunk_window(events, start, end, offset=0):
    points = [e for e in events if e['event'] in ('MEASUREMENT_START', 'PROGRESS', 'MEASUREMENT_END')]
    count = 0
    chunks = []
    for left, right in zip(points, points[1:]):
        a, b = left['utc_seconds'] - offset, right['utc_seconds'] - offset
        n = right['completed'] - left['completed']
        if a >= start and b <= end and b > a and n >= 0:
            count += n
            chunks.append((a, b, n))
    covered = sum(b-a for a,b,_ in chunks)
    return {'window_completed': count, 'window_throughput': count/(end-start),
            'window_seconds': end-start, 'chunk_covered_seconds': covered,
            'excluded_boundary_seconds': end-start-covered,
            'chunk_window_valid': bool(chunks) and end-start-covered < (end-start)*.01}


def summarize(rows, dimensions, field):
    groups = defaultdict(list)
    for row in rows:
        if row.get(field) is not None:
            groups[tuple(row[k] for k in dimensions)].append(float(row[field]))
    return [{**dict(zip(dimensions, key)), 'metric': field, 'n': len(vals),
             'mean': statistics.mean(vals), 'stddev': statistics.stdev(vals) if len(vals)>1 else None,
             'min': min(vals), 'max': max(vals)} for key, vals in sorted(groups.items())]


def analyze(base, output):
    output.mkdir(parents=True, exist_ok=True)
    gpu = []
    gpu_rows = []
    process_observations=[]
    for sample in json_lines(base/'observations.jsonl'):
        try:
            fields = sample['gpu'].strip().split(',')
            value = float(fields[1])
            gpu.append((sample['timestamp'], value))
            gpu_rows.append({'host_utc_seconds': sample['timestamp'], 'gpu_uuid': fields[0],
                             'utilization_percent': value, 'memory_mib': float(fields[2]),
                             'power_watts': float(fields[3]), 'sm_clock_mhz': float(fields[4]),
                             'collection_seconds': sample['completed_at']-sample['timestamp'],
                             'collector_errors': len(sample['errors'])})
            for line in sample.get('processes','').splitlines():
                parts=[x.strip() for x in line.split(',')]
                if len(parts)==4:
                    try:process_observations.append({'host_utc_seconds':sample['timestamp'],'gpu_uuid':parts[0],
                          'pid':int(parts[1]),'process':parts[2],'memory_mib':float(parts[3])})
                    except ValueError:pass
        except (KeyError, ValueError, IndexError):
            continue
    gpu.sort()
    rows = []
    excluded = []
    identities = {}
    run_pids={}
    for directory in sorted((base/'runs').iterdir()):
        if not (directory/'manifest.json').exists():
            continue
        manifest = read_json(directory/'manifest.json')
        condition = manifest['conditions']
        if not condition.get('phase', '').startswith(('C5-', 'C6-')):
            continue
        if not (directory/'cleanup.json').exists() or not (directory/'metrics.json').exists():
            excluded.append({'run_id': directory.name, 'reason': 'incomplete; not counted'})
            continue
        metrics = read_json(directory/'metrics.json')
        result = metrics['result']
        events = list(json_lines(directory/'stdout.jsonl'))
        start = next((e for e in events if e['event']=='MEASUREMENT_START'), None)
        end = next((e for e in events if e['event']=='MEASUREMENT_END'), None)
        if not start or not end or metrics['execution']!='PASS' or result.get('status')!='PASS':
            excluded.append({'run_id': directory.name, 'reason': 'missing events or failed execution'})
            continue
        offset = uncertainty = 0
        if (directory/'clock-map.json').exists():
            best = min(read_json(directory/'clock-map.json'), key=lambda r:r['uncertainty'])
            offset, uncertainty = best['offset'], best['uncertainty']
        wall_discrepancy=(end['utc_seconds']-start['utc_seconds'])-result['elapsed_seconds']
        alignment='guest wall clock minus pre-run offset' if manifest['backend']=='shm' else 'host wall clock'
        mapped_events=events
        if (directory/'monotonic-clock-map.json').exists():
            bridge=min(read_json(directory/'monotonic-clock-map.json'),key=lambda x:x['uncertainty'])
            anchor=bridge['host_minus_guest_monotonic']
            uncertainty=bridge['uncertainty']
            a,b=start['monotonic_seconds']+anchor,end['monotonic_seconds']+anchor
            mapped_events=[{**e,'utc_seconds':e['monotonic_seconds']+anchor+offset} if 'monotonic_seconds' in e else e for e in events]
            alignment='guest monotonic clock plus in-run host bridge'
        else:
            a, b = start['utc_seconds']-offset, end['utc_seconds']-offset
        row = {'run_id': directory.name, 'phase': condition['phase'], 'repeat': condition['repeat'],
               'workload': condition.get('workload', 'long'), 'mode': result['mode'],
               'backend': manifest['backend'], 'compute': manifest['compute'], 'slot': manifest['slot'],
               'group': condition.get('group',''), 'gpu_uuid': manifest['gpu_uuid'],
               'memory_mib': manifest['memory_mib'], 'sessions': manifest['sessions'],
               'host_start': a, 'host_end': b, 'clock_offset_seconds': offset,
               'clock_uncertainty_seconds': uncertainty,
               'clock_elapsed_discrepancy_seconds': wall_discrepancy,
               'time_alignment':alignment,
               'wall_clock_step_detected':abs(wall_discrepancy)>.01,
               **{k:result[k] for k in ['seed','iterations','completed','elapsed_seconds','throughput',
                                        'checked_elements','mismatches','nonfinite','max_absolute_error','max_relative_error']},
               'accuracy_valid': result['checked_elements']==524288 and result['mismatches']==0 and result['nonfinite']==0,
               'released': read_json(directory/'cleanup.json')['released']}
        row['replaces']=condition.get('replaces','')
        if condition['phase']=='C6-interference':
            scheduled_guest = float(read_json(directory/'command.json')['args'][6])
            wa, wb = scheduled_guest-offset+15, scheduled_guest-offset+75
            row.update(window_start=wa, window_end=wb,
                       window_active_valid=a+uncertainty<=wa and b-uncertainty>=wb)
            row.update(chunk_window(mapped_events,wa,wb,offset))
            row.update(weighted_samples(gpu,wa,wb))
        else:
            row.update(weighted_samples(gpu,a,b))
        row['gpu_alignment_valid']=not (manifest['backend']=='shm' and not (directory/'monotonic-clock-map.json').exists() and abs(wall_discrepancy)>.01)
        if not row['gpu_alignment_valid']:
            # Keep throughput/elapsed from CLOCK_MONOTONIC, but do not average a
            # device-utilization interval whose host correspondence is unknown.
            row['gpu_utilization_mean_percent']=None
        rows.append(row)
        identity = read_json(directory/'identity.json')
        uids = [identity[k] for k in ['uid','worker_uid','launcher_uid'] if k in identity]
        # Earlier runs stored launcher UID only in the pinning record.
        for pin in json_lines(directory/'cpu-pinning.txt'):
            uids.append(pin['pod_uid'])
        identities[directory.name] = set(uids)
        if (directory/'runtime-libraries.json').exists():
            run_pids[directory.name]={p['pid'] for p in read_json(directory/'runtime-libraries.json')}
    replaced={r['replaces'] for r in rows if r['replaces'] and r['accuracy_valid'] and r['gpu_alignment_valid']}
    for row in rows:row['primary']=row['run_id'] not in replaced
    write_csv(output/'gpu-samples.csv', gpu_rows)
    write_csv(output/'runs.csv', rows)
    mappings=[]
    for row in rows:
        for observed in process_observations:
            if observed['pid'] in run_pids.get(row['run_id'],set()) and row['host_start']<=observed['host_utc_seconds']<=row['host_end']:
                mappings.append({'run_id':row['run_id'],**observed,'matches_requested_gpu':observed['gpu_uuid']==row['gpu_uuid']})
    write_csv(output/'gpu-process-mapping.csv',mappings)
    known_pids=set().union(*run_pids.values()) if run_pids else set()
    unexpected=[s for s in process_observations if s['pid'] not in known_pids and
                any(r['primary'] and r['gpu_uuid']==s['gpu_uuid'] and r['host_start']<=s['host_utc_seconds']<=r['host_end'] for r in rows)]
    write_csv(output/'unexpected-gpu-processes.csv',unexpected)
    write_csv(output/'excluded.csv', excluded)
    cpu_rows = []
    previous = {}
    by_id = {r['run_id']:r for r in rows}
    for snapshot in json_lines(base/'cpu-observations.jsonl'):
        if 'processes' not in snapshot:
            continue
        t = snapshot['utc_seconds']
        for proc in snapshot['processes']:
            key = (proc['pid'], proc['start_ticks'])
            ticks = proc['user_ticks']+proc['system_ticks']
            old = previous.get(key)
            previous[key] = (t,ticks)
            if not old or not 0<t-old[0]<=3 or ticks<old[1]:
                continue
            for run_id, uids in identities.items():
                run = by_id[run_id]
                a,b = run.get('window_start',run['host_start']),run.get('window_end',run['host_end'])
                if old[0]<a or t>b:
                    continue
                if not any(u in proc['cgroup'] or u.replace('-','_') in proc['cgroup'] for u in uids):
                    continue
                seconds = (ticks-old[1])/snapshot['clock_ticks']
                cpu_rows.append({'run_id':run_id,'host_start':old[0],'host_end':t,'pid':proc['pid'],
                                 'program':proc['program'],'cpu_seconds':seconds,
                                 'mean_cpu_cores':seconds/(t-old[0]), 'affinity':','.join(map(str,proc['cpus']))})
    write_csv(output/'cpu-samples.csv',cpu_rows)
    cpu_groups=defaultdict(list)
    for sample in cpu_rows:cpu_groups[(sample['run_id'],sample['program'])].append(sample)
    cpu_summary=[]
    for (run_id,program),samples in sorted(cpu_groups.items()):
        run=by_id[run_id]
        coverage=sum(s['host_end']-s['host_start'] for s in samples)
        consumed=sum(s['cpu_seconds'] for s in samples)
        cpu_summary.append({'run_id':run_id,'phase':run['phase'],'backend':run['backend'],'mode':run['mode'],
                            'program':program,'cpu_seconds_observed':consumed,'process_seconds_covered':coverage,
                            'mean_cpu_cores_observed':consumed/coverage,
                            'window_seconds':run.get('window_seconds',run['elapsed_seconds'])})
    write_csv(output/'cpu-summary.csv',cpu_summary)
    c5 = [r for r in rows if r['phase'].startswith('C5-') and r['primary']]
    stats = []
    for metric in ['throughput','elapsed_seconds','gpu_utilization_mean_percent']:
        stats += summarize(c5,['phase','workload','compute'],metric)
    write_csv(output/'compute-summary.csv',stats)
    overhead = []
    for mode in ['resident','transfer']:
        for repeat in range(1,6):
            pair = {r['backend']:r for r in rows if r['phase']=='C6-overhead' and r['mode']==mode and r['repeat']==repeat}
            if set(pair)=={'native','shm'}:
                n,s = pair['native'],pair['shm']
                assert (n['completed'],n['iterations'],n['seed'],n['compute'])==(s['completed'],s['iterations'],s['seed'],s['compute'])
                overhead.append({'mode':mode,'repeat':repeat,'native_run':n['run_id'],'shm_run':s['run_id'],
                                 'native_seconds':n['elapsed_seconds'],'shm_seconds':s['elapsed_seconds'],
                                 'increase_percent':(s['elapsed_seconds']/n['elapsed_seconds']-1)*100})
    write_csv(output/'overhead-pairs.csv',overhead)
    write_csv(output/'overhead-summary.csv',summarize(overhead,['mode'],'increase_percent'))
    interference = []
    for mode in ['resident','transfer']:
        for repeat in range(1,6):
            selected = {(r['group'],r['slot']):r for r in rows if r['phase']=='C6-interference' and r['mode']==mode and r['repeat']==repeat}
            for slot in ['a','b']:
                if (slot,slot) not in selected or ('pair',slot) not in selected:
                    continue
                single,pair = selected[slot,slot],selected['pair',slot]
                valid = all(r['window_active_valid'] and r['chunk_window_valid'] for r in [single,pair])
                x,y = single['window_throughput'],pair['window_throughput']
                interference.append({'mode':mode,'repeat':repeat,'slot':slot,'single_run':single['run_id'],
                    'pair_run':pair['run_id'],'single_kernels_per_second':x,'pair_kernels_per_second':y,
                    'retention':y/x,'slowdown':x/y,'valid':valid,
                    'pair_total_kernels_per_second':sum(r['window_throughput'] for (g,_),r in selected.items() if g=='pair')})
    write_csv(output/'interference-pairs.csv',interference)
    write_csv(output/'interference-summary.csv',summarize([r for r in interference if r['valid']],['mode','slot'],'retention'))
    overlap=[]
    for mode in ['resident','transfer']:
        for repeat in range(1,6):
            pair=[r for r in rows if r['phase']=='C6-interference' and r['group']=='pair' and r['mode']==mode and r['repeat']==repeat]
            if len(pair)!=2:continue
            start=max(r['host_start']+r['clock_uncertainty_seconds'] for r in pair)
            end=min(r['host_end']-r['clock_uncertainty_seconds'] for r in pair)
            overlap.append({'mode':mode,'repeat':repeat,'a_run':next(r['run_id'] for r in pair if r['slot']=='a'),
                            'b_run':next(r['run_id'] for r in pair if r['slot']=='b'),
                            'conservative_overlap_seconds':max(0,end-start),
                            'gpu_uuid':pair[0]['gpu_uuid'],'same_gpu':len({r['gpu_uuid'] for r in pair})==1,
                            'common_window_start_difference_seconds':abs(pair[0]['window_start']-pair[1]['window_start'])})
    write_csv(output/'sharing-overlap.csv',overlap)
    status = {'completed_formal_runs':len(rows),'primary_formal_runs':sum(r['primary'] for r in rows),'expected_primary_runs':108,'excluded_or_incomplete':excluded,
              'accuracy_passes':sum(r['accuracy_valid'] for r in rows), 'released':sum(r['released'] for r in rows),
              'clock_discrepancy_max_seconds':max((abs(r['clock_elapsed_discrepancy_seconds']) for r in rows),default=None),
              'gpu_min_coverage':min((r['gpu_sample_coverage_fraction'] for r in rows),default=None),
              'unexpected_gpu_process_samples':len(unexpected),
              'limiter_verdict':'NOT_EVALUATED',
              'measurement_scope':'Final output correctness; device-wide GPU utilization; whole-path overhead; sampled CPU cost'}
    (output/'analysis-status.json').write_text(json.dumps(status,indent=2)+'\n')
    return rows, stats, overhead, interference


def plots(output, rows, stats, overhead, interference):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figures = output.parent/'figures'
    figures.mkdir(exist_ok=True)
    def save(fig,name):
        fig.savefig(figures/(name+'.png'),dpi=150)
        fig.savefig(figures/(name+'.svg'))
        plt.close(fig)
    gpu_rows=list(csv.DictReader((output/'gpu-samples.csv').open()))
    fig,axes=plt.subplots(2,3,figsize=(14,7),layout='constrained',sharey=True)
    for i,workload in enumerate(['long','short']):
        for j,compute in enumerate([25,50,100]):
            ax=axes[i,j]
            selected=[r for r in rows if r['phase']=='C5-time' and r['workload']==workload and r['compute']==compute and r['primary'] and r['gpu_alignment_valid']]
            for r in selected:
                points=[s for s in gpu_rows if r['host_start']<=float(s['host_utc_seconds'])<=r['host_end']]
                ax.plot([float(s['host_utc_seconds'])-r['host_start'] for s in points],
                        [float(s['utilization_percent']) for s in points],alpha=.7,label='repeat '+str(r['repeat']))
            ax.set(title=f'{workload} / setting {compute}',xlabel='measurement seconds',ylabel='whole-device GPU %',ylim=(0,105));ax.grid(alpha=.2)
            if selected:ax.legend(fontsize=8)
    fig.suptitle('Actual device utilization — every valid time-run repeat')
    save(fig,'compute-utilization')
    for phase,metric,title in [('C5-time','throughput','60 s synchronized kernel throughput'),('C5-fixed','elapsed_seconds','Fixed-work completion time')]:
        fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
        for ax,workload in zip(axes,['long','short']):
            for c in [25,50,100]:
                vals=[r[metric] for r in rows if r['phase']==phase and r['workload']==workload and r['compute']==c and r['primary']]
                if vals:
                    ax.scatter([c]*len(vals),vals,alpha=.65)
                    ax.errorbar(c,statistics.mean(vals),yerr=statistics.stdev(vals) if len(vals)>1 else 0,fmt='ks',capsize=5)
            title_work=workload+' FMA'+(f" / N={1678 if workload=='long' else 11339}" if phase=='C5-fixed' else ' / 60 s')
            ax.set(title=title_work,xlabel='Compute setting (not measured %)',ylabel='kernels/s' if metric=='throughput' else 'seconds',xticks=[25,50,100]);ax.grid(alpha=.2)
        fig.suptitle(title+' — points: repeats; black: mean ± sample SD')
        save(fig,phase.lower())
    if overhead:
        fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
        for ax,mode in zip(axes,['resident','transfer']):
            selected=[r for r in overhead if r['mode']==mode]
            for row in selected:
                ax.plot(['Native + HAMi','VM SHM + Worker + HAMi'],[row['native_seconds'],row['shm_seconds']],marker='o',label='repeat '+str(row['repeat']))
            ax.set(title=mode,ylabel='seconds (same 1819 synchronized kernels)');ax.legend();ax.grid(alpha=.2)
        fig.suptitle('Whole-path elapsed time; boot and final validation excluded')
        save(fig,'overhead')
    if interference:
        fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
        for ax,mode in zip(axes,['resident','transfer']):
            for slot in ['a','b']:
                vals=[r['retention'] for r in interference if r['mode']==mode and r['slot']==slot and r['valid']]
                ax.scatter([slot.upper()]*len(vals),vals,label=slot.upper())
                if vals:ax.errorbar(slot.upper(),statistics.mean(vals),yerr=statistics.stdev(vals) if len(vals)>1 else 0,fmt='ks',capsize=5)
            ax.axhline(1,color='grey',linestyle='--');ax.set(title=mode,ylabel='Concurrent / solo throughput');ax.grid(alpha=.2)
        fig.suptitle('Same per-VM compute 50, 4 GiB, seed and 60 s window')
        save(fig,'interference')
        pair=sorted([r for r in rows if r['phase']=='C6-interference' and r['mode']=='resident' and r['repeat']==1 and r['group']=='pair'],key=lambda r:r['slot'])
        if len(pair)==2:
            origin=min(r['host_start'] for r in pair)
            fig,ax=plt.subplots(figsize=(12,3.8),layout='constrained')
            for i,r in enumerate(pair):
                start=r['host_start']-origin;end=r['host_end']-origin;u=r['clock_uncertainty_seconds']
                ax.broken_barh([(start,end-start)],(i-.25,.5),facecolors=['tab:blue' if i==0 else 'tab:orange'])
                ax.errorbar([start,end],[i,i],xerr=u,fmt='none',ecolor='black',capsize=8)
                ax.text(start+1,i,r['run_id'],va='center',fontsize=9,color='white')
            wa=max(r['window_start'] for r in pair)-origin;wb=min(r['window_end'] for r in pair)-origin
            ax.axvline(wa,color='black',linestyle='--');ax.axvline(wb,color='black',linestyle='--')
            ax.set(yticks=[0,1],yticklabels=['VM A','VM B'],xlabel='Host-aligned seconds since first measurement start',
                   title='Actual 90 s shared run — dashed: common 60 s window; caps: clock uncertainty')
            ax.text(.01,-.30,pair[0]['gpu_uuid'],transform=ax.transAxes,fontsize=10)
            save(fig,'sharing-timeline')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=analyze(args.base,args.output)
    plots(args.output,*result)
    print((args.output/'analysis-status.json').read_text())
