import os
import sys,importlib.util,json
from pathlib import Path
import measure as m
h=m.h
spec=importlib.util.spec_from_file_location('native_setup',h.B/'native-setup.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);r=n.r
spec=importlib.util.spec_from_file_location('transition',h.R/'experiments/ai-passthrough/results/20261022-sgemm-bestcase/transition.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t);t.RESOURCE='vmweave.io/rodinia-steady-passthrough';r.native.RESOURCE=t.RESOURCE
# Wait for an actual address, not merely a nonempty interface list.
import inspect,textwrap
source=textwrap.dedent(inspect.getsource(r.native.Native.prepare))
source=source.replace("v['status'].get('interfaces')", "v['status'].get('interfaces') and v['status']['interfaces'][0].get('ipAddress')")
exec(source,r.native.__dict__)
r.native.Native.prepare=r.native.prepare
label=sys.argv[1];attempt=os.environ.get('RODINIA_ATTEMPT',label);v=r.native.Native('rodinia-p-1026-'+attempt)
try:
 t.to_native();v.prepare();s={'mode':'passthrough','name':v.name,'namespace':v.ns,'ssh':v.ssh,'scp':v.scp,'ip':v.ip};h.save(h.B/'active-native.json',s);m.stage(s);m.measure(s,'qualification' if label.startswith('gate') else 'formal',label)
 if label=='r3':m.measure(s,'profile-gate',label,['nw'])
 if label=='r5':m.measure(s,'diagnostic',label)
finally:
 if r.c.get('vm',v.name,ns=v.ns):v.cleanup()
 if Path('/sys/bus/pci/devices/0000:40:00.0/driver').resolve().name=='vfio-pci':t.to_vmweave()
 h.drop_admin()
