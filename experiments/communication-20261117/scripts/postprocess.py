"""Run only after all 320 intervals; public push remains a separately reviewed step."""
from common import *
def main():
 complete=json.loads((O/'evidence/campaign-complete.json').read_text());assert complete['intervals']==320
 python=R/'.local/evidence-venv/bin/python'
 for name in ['analyze.py','verify_results.py','verify_metadata.py','environment_review.py']:
  with (B/(name+'.log')).open('w') as log:S.run(['taskset','-c','24,25',str(python),str(O/'scripts'/name)],stdout=log,stderr=S.STDOUT,check=True)
 if not (O/'evidence/cleanup-complete.json').exists():
  with (B/'cleanup.log').open('w') as log:S.run(['python3',str(O/'scripts/cleanup.py')],stdout=log,stderr=S.STDOUT,check=True)
 if not (O/'evidence/private-workspace-cleanup.json').exists():
  with (B/'private-cleanup.log').open('w') as log:S.run(['python3',str(O/'scripts/private_storage_cleanup.py')],stdout=log,stderr=S.STDOUT,check=True)
 with (B/'report.log').open('w') as log:S.run(['python3',str(O/'scripts/report.py')],stdout=log,stderr=S.STDOUT,check=True)
 save(O/'evidence/postprocess-complete.json',{'utc':time.time(),'analyzed':True,'independently_verified':True,'cleanup_finished':True,'report_written':True,'scope':'Measurement analysis, verification, cleanup and report generation; repository publication is a separate subsequent step.'})
 print('POSTPROCESS_COMPLETE; REVIEW REPORT AND PUBLISH',flush=True)
if __name__=='__main__':main()
