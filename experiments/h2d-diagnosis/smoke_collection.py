from run_diagnostic import *
ensure_admin()
for path in ['S','T']:
 one('hd-pilot-collection-'+path.lower(),'stock',metrics=False,mode='copy',seconds=3,warmup=2,path=path)
