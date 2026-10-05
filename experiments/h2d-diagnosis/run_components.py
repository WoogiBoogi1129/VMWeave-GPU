"""Actual Guest BAR diagnostic, before any CUDA requests on a dedicated channel."""
from runtime import *
ensure_admin()
for r in range(1,6):
 name=f'hd-map-r{r}'
 if (OUT/'runs'/name/'cleanup.json').exists():continue
 s=Session(name);save(s.out/'condition.json',{'phase':'mapping-component','repeat':r,'cuda_workload':False,'cpu':0,'seconds_per_size_mode':2,'first_20_operations_excluded':True})
 try:
  s.prepare();call(s.scp+[str(BASE/'diagnostic/map-probe'),'ubuntu@'+s.ip+':/tmp/perf/'])
  (s.out/'map.jsonl').write_text(call(s.ssh+['sudo taskset -c 0 /tmp/perf/map-probe /tmp/perf/layout.bin '+s.bdf],timeout=180))
  (s.out/'guest-mapping.txt').write_text(call(s.ssh+['sudo sh -c '+shlex.quote('cat /sys/bus/pci/devices/'+s.bdf+'/resource; cat /sys/kernel/debug/x86/pat_memtype_list; lscpu')],check=False))
  rows=[json.loads(l) for l in (s.out/'map.jsonl').read_text().splitlines()];assert len(rows)==16 and all(x['verified'] for x in rows)
  save(s.out/'component-validation.json',{'passed':True,'rows':16,'note':'Host-to-Guest BAR mapping; no CUDA workload; not end-to-end latency.'})
 except Exception as e:save(s.out/'failure.json',{'error':str(e)});raise
 finally:s.close()
