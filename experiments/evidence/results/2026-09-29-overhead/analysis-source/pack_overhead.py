"""Lossless publication packing; private original CSVs/outputs remain intact."""
import argparse,gzip,hashlib,json,lzma,os,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--watch',action='store_true');a=p.parse_args();os.sched_setaffinity(0,{48,49,50,51})
def digest(f):
 h=hashlib.sha256()
 while block:=f.read(1024*1024):h.update(block)
 return h.hexdigest()
def pack(run):
 if (run/'packing.json').exists():return
 manifest=[]
 for f in sorted([*run.glob('*.csv.gz'),*run.glob('*.output.bin')]):
  target=Path(str(f)[:-3]+'.xz') if f.suffix=='.gz' else Path(str(f)+'.xz');temp=Path(str(target)+'.tmp')
  op=gzip.open if f.suffix=='.gz' else open
  with op(f,'rb') as src,temp.open('wb') as out:
   pr=subprocess.Popen(['xz','-6','-T2','-c'],stdin=subprocess.PIPE,stdout=out);h=hashlib.sha256();n=0
   while block:=src.read(1024*1024):h.update(block);n+=len(block);pr.stdin.write(block)
   pr.stdin.close();assert pr.wait()==0
  with lzma.open(temp,'rb') as verify:assert digest(verify)==h.hexdigest()
  temp.replace(target)
  manifest.append({'file':target.name,'original_bytes':n,'original_sha256':h.hexdigest(),'compressed_bytes':target.stat().st_size,'packing':'xz -6 -T2; exact byte equality verified'})
  f.unlink() # Only redundant publication copy. Private originals remain.
 (run/'packing.json').write_text(json.dumps(manifest,indent=2)+'\n');print('PACKED',run.name,flush=True)
while True:
 for run in sorted(a.output.glob('r*-*')):
  if (run/'cleanup.json').exists() and (run/'execution.json').exists():pack(run)
 if not a.watch:break
 time.sleep(10)
