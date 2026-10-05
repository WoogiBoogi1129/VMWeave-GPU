"""Preserve outer driver outputs, including aborted attempts, after execution."""
from common import *
assert (OUT/'followup-complete.json').exists()
(OUT/'drivers').mkdir(exist_ok=True)
for name in ['main.txt','main-v2.txt','collection-recovery.txt','prepare_followup.py.txt','run_followup.py.txt']:
 p=BASE/name
 if p.exists():(OUT/'drivers'/name).write_text(redact(p.read_text()))
