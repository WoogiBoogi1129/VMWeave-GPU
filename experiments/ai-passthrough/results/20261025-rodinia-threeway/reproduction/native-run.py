import sys,importlib.util,json
from pathlib import Path
import rodinia_campaign as h
spec=importlib.util.spec_from_file_location('native_setup',h.B/'native-setup.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);r=n.r
spec=importlib.util.spec_from_file_location('transition',h.R/'experiments/ai-passthrough/results/20261022-sgemm-bestcase/transition.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t);t.RESOURCE='vmweave.io/rodinia-passthrough';r.native.RESOURCE=t.RESOURCE
label=sys.argv[1];v=r.native.Native('rodinia-p-1025-'+label);bound=False
try:
 t.to_native();bound=True;v.prepare();s={'mode':'passthrough','name':v.name,'namespace':v.ns,'ssh':v.ssh,'scp':v.scp,'ip':v.ip};h.save(h.B/'active-native.json',s);h.stage(s)
 if label=='qualification':h.measure(s,'qualification','gate')
 else:
  h.measure(s,'warmup',label);h.measure(s,'formal',label)
  if label=='r3':h.measure(s,'diagnostic',label)
finally:
 if r.c.get('vm',v.name,ns=v.ns):v.cleanup()
 if Path('/sys/bus/pci/devices/0000:40:00.0/driver').resolve().name=='vfio-pci':t.to_vmweave()
