"""Publish portable, hash-checked source diffs for the actual isolated builds."""
from common import *
import difflib,hashlib
records=[]
for label,src in [('pilot-v1',BASE/'source-v1/shm'),('pilot-v2',BASE/'source-v2/shm'),('final',BASE/'source/shm')]:
    if not src.exists():
        alt=src.parent
        if (alt/'CMakeLists.txt').exists():src=alt
        else:raise RuntimeError(src)
    old=ROOT/'runtime/shm'
    tracked=subprocess.check_output(['git','-C',str(ROOT),'ls-files','runtime/shm'],text=True).splitlines()
    rels=sorted({Path(p).relative_to('runtime/shm') for p in tracked}|{Path('shm-queue/include/hd_diag.h'),Path('shm-queue/src/diag.c')})
    patch=[];hashes={}
    for rel in rels:
        a=old/rel;b=src/rel
        left=a.read_text() if a.exists() else '';right=b.read_text() if b.exists() else ''
        if left==right:continue
        patch.extend(difflib.unified_diff(left.splitlines(True),right.splitlines(True),fromfile='a/'+str(rel) if a.exists() else '/dev/null',tofile='b/'+str(rel) if b.exists() else '/dev/null'))
        hashes[str(rel)]={'before':hashlib.sha256(a.read_bytes()).hexdigest() if a.exists() else None,'after':hashlib.sha256(b.read_bytes()).hexdigest() if b.exists() else None}
    p=OUT/'build'/(label+'-portable.patch');p.write_text(''.join(patch))
    records.append({'label':label,'patch':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'files':hashes})
save(OUT/'build/portable-patches.json',{'base_commit':'00cf878','apply':'Copy runtime/shm at base commit, then patch -p1 inside that copy. Never patch production runtime to reproduce diagnostic trials.','versions':records})
