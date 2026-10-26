import os
import sys,os,subprocess,json
import measure as m
h=m.h;label=sys.argv[1];attempt=os.environ.get('RODINIA_ATTEMPT',label);os.environ['RODINIA_LABEL']=attempt
h.drop_admin()
def run(f):subprocess.run([sys.executable,str(h.B/f)],check=True)
try:
 
 if '--prepared' not in sys.argv:run('prepare.py')
 run('server-pod.py');run('start-stack.py')
 s=json.loads((h.B/'state.json').read_text());s.update(json.loads((h.B/'ssh.json').read_text()));s['mode']='flyt'
 pods=json.loads(h.k('get','pods','-n',s['namespace'],'-o','json'))['items'];launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'));server=next(p for p in pods if p['metadata']['name']=='flyt-server')
 out=h.O/'identities'/('flyt-'+attempt);out.mkdir(parents=True,exist_ok=True);(out/'affinity.log').write_text(h.finish_affinity('flyt-'+attempt,launcher,server));m.stage(s);m.measure(s,'qualification' if label.startswith('gate') else 'formal',label)
 if label=='r3':m.measure(s,'profile-gate',label,['nw'])
 if label=='r5':m.measure(s,'diagnostic',label)
finally:
 if h.get('namespace','rodinia-flyt-1026'):run('cleanup.py')
