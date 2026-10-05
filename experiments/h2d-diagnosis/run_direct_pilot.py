from run_diagnostic import *
ensure_admin()
for v in ['original','direct']:
 one('hd-pilot-v3-'+v,v,mode='copy',seconds=10,warmup=3)
