import sys,subprocess,json,shutil,os
import rodinia_campaign as h
label=sys.argv[1];os.environ['RODINIA_LABEL']=label;h.drop_admin()
def run(file):subprocess.run([sys.executable,str(h.B/file)],check=True)
try:
 run('prepare.py');run('server-pod.py');run('start-stack.py')
 s=json.loads((h.B/'state.json').read_text());pods=json.loads(h.k('get','pods','-n',s['namespace'],'-o','json'))['items'];launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'));server=next(p for p in pods if p['metadata']['name']=='flyt-server');out=h.O/'identities'/('flyt-'+label);out.mkdir(parents=True,exist_ok=True)
 (out/'affinity.log').write_text(h.finish_affinity('flyt-'+label,launcher,server))
 h.save(out/'state.json',s);h.save(out/'server.json',server);h.save(out/'launcher.json',launcher)
 source=(h.B/'qualify-flyt.py').read_text()
 for stage in ['warmup','formal']:
  target=h.O/stage/label/'flyt';assert not target.exists()
  code=source.replace("out=O/'qualification/flyt'",'out=O/'+repr(stage)+'/'+repr(label)+"/'flyt'")
  exec(compile(code,str(h.B/'qualify-flyt.py'),'exec'),{'__name__':'__main__'})
 if label=='r3':
  d=json.loads((h.B/'ssh.json').read_text());s.update(d);s['mode']='flyt';h.stage(s);h.measure(s,'diagnostic',label)
  for repeat in [2,3]:h.measure(s,'diagnostic','r3-repeat'+str(repeat),['nw'])
 for cmd,name in [('cat /tmp/node.log /tmp/cluster.log','server.log'),('ipcs -q; nvidia-smi; sha256sum /usr/local/cuda/lib64/libcudart.so.12 /usr/local/cuda/lib64/stubs/libcuda.so.1','state.log')]:
  (out/name).write_text(h.k('exec','-n',s['namespace'],'flyt-server','-c','server','--','sh','-c',cmd))
finally:
 if h.get('namespace','rodinia-flyt-1025'):run('cleanup.py')
 h.ensure_admin()
