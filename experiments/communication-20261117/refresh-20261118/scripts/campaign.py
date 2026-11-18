"""VMWeave-only refresh; no Flyt/Lupine/Native resources are created."""
from common import *
from backends import start,close,idle
from run_session import run
import profiles,signal,traceback,base64

def interrupted(*args):raise RuntimeError('Campaign interrupted; retain partial data and release owned GPU')
signal.signal(signal.SIGTERM,interrupted)

def check_session(label,profile,guest_sha):
    out=O/'results'/label
    x=json.loads((out/'client-effective.json').read_text());assert len(x)==1,x
    assert x[0]['environment']['VMWEAVE_KERNEL_BATCH']==('1' if profile=='ON' else '0')
    assert x[0]['libraries']=={'/opt/comm/artifacts/V/libvmweave_guest.so':guest_sha}
    for name in ['VMWEAVE_BULK_COPY','VMWEAVE_BULK_DIRECT']:assert x[0]['environment'][name]=='1'
    log=(out/'stderr.txt').read_text()
    if profile=='ON':assert 'kernel-batch v1 enabled' in log and 'terminal_error=0' in log
    else:assert 'kernel-batch v1 enabled' not in log
    assert not (out/'collection-error.txt').exists()

def main():
    old=json.loads((R/'experiments/communication-20261117/protocol/frozen.json').read_text())
    guest_sha=hashlib.sha256((B/'artifacts/V/libvmweave_guest.so').read_bytes()).hexdigest()
    assert guest_sha==json.loads((R/'deploy/releases/v0.5.12.json').read_text())['guestLibrarySHA256']
    assert hashlib.sha256((B/'artifacts/V/probe').read_bytes()).hexdigest()==old['artifacts']['V/probe']
    assert hashlib.sha256((B/'artifacts/sequence.ptx').read_bytes()).hexdigest()==old['artifacts']['sequence.ptx']
    schedule=[]
    for block in range(1,6):
        order=next(x['condition_order'] for x in old['blocks'] if x['block']==block)
        for profile in (['OFF','ON'] if block%2 else ['ON','OFF']):
            schedule.append(dict(block=block,profile=profile,label=f'b{block}-{profile}',conditions=order if profile=='ON' else [i for i in order if i in [0,13,14,15]]))
    frozen={'schema':1,'frozen_utc':time.time(),'release':'v0.5.12','source_revision':json.loads((R/'deploy/releases/v0.5.12.json').read_text())['sourceRevision'],'gpu_uuid':GPU,'gpu_index':1,'main_profile':'ON','seconds':30,'warmup_seconds':10,'blocks':5,'formal_intervals':100,'schedule':schedule,'images':IM,'guest_sha256':guest_sha,'probe_sha256':old['artifacts']['V/probe'],'ptx_sha256':old['artifacts']['sequence.ptx'],'broker_environment':profiles.BASE,'application_environment':profiles.APP,'gpu_capacity':{'cores':100,'memory':'97887Mi'},'cpu':old['cpu'],'lifecycle':'Fresh VM boot and DRA binding for each block. ON and OFF use fresh client processes and CUDA children within that boot; alternating order. Main ON repeats the original 16-condition order. OFF repeats only the four kernel conditions.','statistics':'5 independent blocks; arithmetic block means and t4 CI. OFF/ON paired log-ratios only within refreshed blocks. Historical N/F/L comparisons are descriptive cross-campaign point ratios, never paired block CI.','historical_comparison':'Native/Flyt/Lupine frozen results unchanged; no current paired experiment with them.','sources':{str(f.relative_to(O)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((O/'scripts').glob('*.py'))},'historical_frozen_sha256':hashlib.sha256((R/'experiments/communication-20261117/protocol/frozen.json').read_bytes()).hexdigest()}
    assert not (O/'protocol/frozen.json').exists()
    save(O/'protocol/frozen.json',frozen)
    (O/'protocol/frozen.sha256').write_text(hashlib.sha256((O/'protocol/frozen.json').read_bytes()).hexdigest()+'  frozen.json\n')
    profiles.ACTIVE='ON';profiles.NEXT='ON'
    # Short correctness pilot is excluded; all formal settings are already frozen.
    run('V','pilot-ON',[0,15,2,8,5,11,6,12],pilot=True)
    pilot_log=(O/'results/pilot-ON/stderr.txt').read_text()
    assert 'kernel-batch v1 enabled' in pilot_log and 'terminal_error=0' in pilot_log
    for block in range(1,6):
        rows=[r for r in schedule if r['block']==block]
        profiles.ACTIVE=rows[0]['profile'];base=start('V',f'block-{block}-boot')
        try:
            for row in rows:
                profiles.ACTIVE=row['profile']
                for suffix in ['-channel.json','-claim.json','-layout.bin','-client-sha256.txt']:
                    (O/'evidence'/(row['label']+suffix)).write_bytes((O/'evidence'/(base['label']+suffix)).read_bytes())
                print('SESSION_START',row,flush=True)
                run('V',row['label'],row['conditions'],session=base,keep_vm=True)
                check_session(row['label'],row['profile'],guest_sha)
            save(O/'evidence'/f'block-{block}-complete.json',{'block':block,'utc':time.time(),'vmi_uid':base['vmi_uid'],'server_uid':base['server_uid']})
        finally:close(base)
    save(O/'evidence/measurement-complete.json',{'status':'complete','utc':time.time(),'formal_intervals':100})

if __name__=='__main__':
    try:
        save(B/'campaign-state.json',{'status':'running','utc':time.time()});main()
        save(B/'campaign-state.json',{'status':'measurements_complete','utc':time.time()})
    except BaseException as e:
        save(B/'campaign-state.json',{'status':'failed','utc':time.time(),'error':str(e)})
        traceback.print_exc();raise
    finally:
        from cleanup import cleanup
        cleanup()
