"""Reconstruct final diagnostic sources from the published patch and test bounds."""
from common import *
import hashlib,shutil,tempfile
os.sched_setaffinity(0,{48,49,50,51})
BASE.mkdir(parents=True,exist_ok=True)
meta=json.loads((OUT/'build/portable-patches.json').read_text())
with tempfile.TemporaryDirectory(prefix='hd-patch-',dir='/dev/shm') as tmp:
    root=Path(tmp)
    tracked=subprocess.check_output(['git','-C',str(ROOT),'ls-files','runtime/shm'],text=True).splitlines()
    for file in tracked:
        rel=Path(file).relative_to('runtime/shm');dst=root/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/file,dst)
    patch=OUT/'build/final-portable.patch'
    result=subprocess.run(['patch','-p1','--batch','-i',str(patch)],cwd=root,text=True,capture_output=True,check=True)
    final=next(v for v in meta['versions'] if v['label']=='final')
    for file,hashes in final['files'].items():assert hashlib.sha256((root/file).read_bytes()).hexdigest()==hashes['after']
    q=root/'shm-queue';h=root/'shm-contract/include'
    # /dev/shm can be noexec: keep the small test executable in private workspace.
    exe=BASE/'scatter-final-asan'
    compile_result=call(['gcc','-O1','-g','-fsanitize=address,undefined','-I'+str(q/'include'),'-I'+str(h),ROOT/'experiments/h2d-diagnosis/test_scatter.c',q/'src/queue.c',q/'src/perf.c',q/'src/diag.c','-pthread','-ldl','-o',exe])
    passed=call(['env','ASAN_OPTIONS=halt_on_error=1','UBSAN_OPTIONS=halt_on_error=1','HD_METRICS=1','HD_VARIANT=direct',exe])
    (OUT/'build/portable-final-test.txt').write_text(result.stdout+compile_result+passed)
save(OUT/'build/portable-validation.json',{'patch_reconstructs_recorded_source':True,'scatter_teardown_asan_ubsan':'PASS','source_files_verified':len(final['files'])})
