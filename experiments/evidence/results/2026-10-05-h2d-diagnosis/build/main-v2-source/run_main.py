"""Five matched original-system repetitions; new probe splits copy/sync timing."""
from run_diagnostic import *
ensure_admin()
for r in range(1,6):
 for path in (['T','S'] if r%2 else ['S','T']):
  name=f'hd-main-v2-r{r}-{path.lower()}'
  if (OUT/'runs'/name/'cleanup.json').exists():
   assert not (OUT/'runs'/name/'failure.json').exists();continue
  one(name,'stock',metrics=False,path=path)
save(OUT/'main-complete.json',{'independent_repetitions_per_system':5,'sessions':10,'windows':40,'seconds_per_window':60})
