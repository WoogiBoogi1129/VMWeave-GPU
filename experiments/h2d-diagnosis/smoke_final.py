"""Fresh, excluded smoke sessions for the final telemetry teardown correction."""
from run_diagnostic import *
ensure_admin()
for name,variant,metrics in [('hd-pilot-final-original','original',True),
                             ('hd-pilot-final-direct-off','direct',False)]:
    assert not (OUT/'runs'/name).exists(), 'Use a new name for any retry'
    one(name,variant,metrics=metrics,mode='copy',seconds=3,warmup=2)
