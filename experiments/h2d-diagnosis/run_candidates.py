from run_diagnostic import *
ensure_admin()
for v in ['original','reuse','pinned','unroll','chunk']:
 name=('hd-pilot-v2b-' if v=='reuse' else 'hd-pilot-v2-')+v
 if (OUT/'runs'/name/'cleanup.json').exists():continue
 one(name,v,mode='copy',seconds=10,warmup=3)
