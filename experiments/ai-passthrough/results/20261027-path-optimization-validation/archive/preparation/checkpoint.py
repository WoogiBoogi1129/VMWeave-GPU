from pathlib import Path
import difflib,sys,shutil
b=Path(__file__).resolve().parents[1]; prev=b/'previous'
if not prev.exists():shutil.copytree(b/'baseline',prev)
paths=sorted({p.relative_to(prev) for p in (prev/'runtime').rglob('*') if p.is_file() and '__pycache__' not in p.parts}|{p.relative_to(b/'source') for p in (b/'source/runtime').rglob('*') if p.is_file() and '__pycache__' not in p.parts})
d=[]
for rel in paths:
 a=prev/rel;c=b/'source'/rel
 old=a.read_text() if a.exists() else '';new=c.read_text() if c.exists() else ''
 if old!=new:d.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+str(rel) if a.exists() else '/dev/null',tofile='b/'+str(rel) if c.exists() else '/dev/null'))
(b/'patches'/sys.argv[1]).write_text(''.join(d))
shutil.rmtree(prev);shutil.copytree(b/'source',prev,ignore=shutil.ignore_patterns('__pycache__'))
print(sys.argv[1],len(d),'diff lines')
