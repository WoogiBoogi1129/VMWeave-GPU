import pathlib,json,subprocess,time
D=pathlib.Path('.local/cnn-release-20261113');E=pathlib.Path('deploy/releases/evidence/v0.5.10');end=time.monotonic()+1200
while not (D/'rollout-result.json').exists():
 if time.monotonic()>end:raise TimeoutError('rollout pending')
 time.sleep(2)
worker=json.loads((D/'rollout-result.json').read_text())['workerPod']
program="import pathlib,json; rows=[]\nfor p in pathlib.Path('/proc').glob('[0-9]*'):\n try:\n  args=(p/'cmdline').read_bytes().split(b'\\0')\n  if b'--session-events' in args: rows.append(dict(pid=int(p.name),command=' '.join(a.decode() for a in args)))\n except (OSError,ValueError): pass\nprint(json.dumps(rows))"
def k(*args):return subprocess.check_output(['kubectl','-n','vmweave-test-b',*args],text=True,timeout=30)
while time.monotonic()<end:
 sessions=json.loads(k('exec',worker,'--','python3','-c',program))
 if sessions:
  gpu=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader'],text=True).strip().splitlines();statuses={}
  for row in gpu:
   pid=row.split(',')[1].strip()
   if not pid.isdigit():continue
   try:s=(pathlib.Path('/proc')/pid/'status').read_text()
   except OSError:continue
   statuses[pid]='\n'.join(line for line in s.splitlines() if line.startswith(('Name:','Pid:','NSpid:')))
  if any('NSpid:' in s and int(s.split('NSpid:')[1].split()[-1]) in {x['pid'] for x in sessions} for s in statuses.values()):
   proof=dict(status='PASS',observationScope='host PID namespace',phase='published-idle',utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),workerPod=worker,sessions=sessions,gpu=gpu,hostProcessStatus=statuses)
   (E/'gpu-observation.json').write_text(json.dumps(proof,indent=2)+'\n');print('Matched live GPU process and Worker session');break
 time.sleep(1)
else:raise TimeoutError('live GPU observation')
