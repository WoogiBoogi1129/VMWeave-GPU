from pathlib import Path
import json,subprocess,time
R=Path.cwd();B=R/'.local/rodinia-threeway-20261025';O=R/'experiments/ai-passthrough/results/20261025-rodinia-threeway';d=json.loads((B/'ssh.json').read_text());s=json.loads((B/'state.json').read_text());out=O/'qualification/flyt';out.mkdir(parents=True,exist_ok=True)
subprocess.run(d['scp']+[str(B/'needle-timed'),str(B/'lud-timed'),'ubuntu@'+s['ip']+':/tmp/flyt-test/'],check=True)
expected=json.loads((R/'experiments/ai-passthrough/results/20261023-large-copy/rodinia-comparison.json').read_text());rows=[]
for name,binary,args in [('nw','needle-timed','2048 10'),('lud2064','lud-timed','-s 2064')]:
 command='mkdir -p /tmp/flyt-test/'+name+' && cd /tmp/flyt-test/'+name+' && sudo timeout -s TERM -k 5 180 env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test /tmp/flyt-test/'+binary+' '+args
 t=time.time();p=subprocess.run(d['ssh']+[command],capture_output=True,text=True,timeout=200);(out/(name+'.log')).write_text(p.stdout+p.stderr);r={'utc':t,'workload':name,'returncode':p.returncode,'wall_seconds':time.time()-t};rows.append(r);(out/'result.json').write_text(json.dumps(rows,indent=2));print(name,p.returncode,flush=True)
 if p.returncode:raise RuntimeError(name+' qualification failed')
 digest=subprocess.check_output(d['ssh']+['sha256sum /tmp/flyt-test/'+name+'/full-output.bin'],text=True).split()[0];r['sha256']=digest;r['matches_native_reference']=digest==next(x['native_host_sha256'] for x in expected if x['workload']==name);assert r['matches_native_reference'];r['timing']=json.loads(subprocess.check_output(d['ssh']+['cat /tmp/flyt-test/'+name+'/timing.json'],text=True));(out/'result.json').write_text(json.dumps(rows,indent=2))
print('Flyt NW/LU correctness PASS',flush=True)
