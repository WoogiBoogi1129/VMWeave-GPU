"""Run the supplementary correctness check in fresh post-campaign sessions."""
from backends import *


def run(reuse_host_context=False):
 assert (O/'measurements-complete.json').exists()
 from collect_context import collect
 if reuse_host_context:
  import math
  context=json.loads((O/'host-context/summary.json').read_text())
  protocol=json.loads((O/'protocol.json').read_text())
  end=max(json.loads(p.read_text())['end_utc'] for p in (O/'formal').glob('*/*/*/exit.json'))
  assert not context['preview'] and context['start_utc']==math.ceil(protocol['created_utc']/30)*30 and context['end_utc']==math.floor(end/30)*30
 else:context=collect(O)
 print('HOST_CONTEXT_COLLECTED',context['available'],flush=True)
 results={}
 for mode in ['passthrough','vmweave','flyt']:
  s=None
  dest=O/'transfer-validation'/mode;dest.mkdir(parents=True,exist_ok=False)
  try:
   s=open_mode(mode,'transfer-validation')
   if mode=='vmweave':
    code="import json,subprocess;from pathlib import Path;pid=subprocess.check_output(['systemctl','show','vmweave-guest-broker','-p','MainPID','--value'],text=True).strip();env=dict(v.split('=',1) for v in Path('/proc',pid,'environ').read_text().split('\\0') if '=' in v);keys=['VMWEAVE_BULK_COPY','VMWEAVE_BROKER_REUSE','VMWEAVE_BROKER_GATHER','VMWEAVE_BROKER_OWNER'];print(json.dumps({k:env.get(k) for k in keys}))"
    flags=json.loads(remote(s,'sudo python3 -c '+shlex.quote(code)))
    assert list(flags.values())==['1']*4
    save(O/'inventory/broker-observed-flags.json',{'utc':time.time(),'flags':flags,'scope':'Observed in a rebuilt post-campaign validation VM, configured with the same published artifacts and flags. See infrastructure/validation-environment-rebuild.'})
    library=remote(s,'sha256sum /opt/vmweave/lib/libvmweave_guest.so').split()[0]
    assert library==json.loads((O/'artifacts.json').read_text())['vmweave_guest']['sha256']
   copy(s,[R/'experiments/training-threeway/transfer_check.py'],'/tmp/training/')
   path='/tmp/training/transfer-check.json'
   cmd=command(s,['--out',path])
   cmd[-1]=cmd[-1].replace('/tmp/training/bench.py','/tmp/training/transfer_check.py')
   with (dest/'stdout.txt').open('w') as out,(dest/'stderr.txt').open('w') as err:
    start=time.time();p=S.run(cmd,stdout=out,stderr=err,timeout=630)
    save(dest/'exit.json',{'returncode':p.returncode,'start_utc':start,'end_utc':time.time()})
    assert p.returncode==0
   S.run(s['scp']+['ubuntu@'+s['ip']+':'+path,str(dest/'result.json')],check=True,capture_output=True)
   results[mode]=json.loads((dest/'result.json').read_text());assert results[mode]['passed']
  finally:
   if s:close_mode(s)
   else:recover_start(mode)
 ref=results['passthrough']['checks']
 assert all(x['checks']==ref for x in results.values())
 save(O/'transfer-validation/summary.json',{'passed':True,'checks':24,'systems':list(results),'output_hashes_match_across_systems':True})
 print('TRANSFER_VALIDATION_PASSED',flush=True)


if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--reuse-host-context',action='store_true')
 run(p.parse_args().reuse_host_context)
