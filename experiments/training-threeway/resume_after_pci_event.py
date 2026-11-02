"""Preserve the interrupted ninth block and rerun it without changing the protocol."""
from campaign import *


def recovery_visit(mode,label,cases,stepmap):
    for group,offset in enumerate(range(0,len(cases),5),1):
        s=None
        save(B/'progress.json',{'phase':'formal-recovery','label':label,'mode':mode,'group':group,'utc':time.time()})
        try:
            # Unique inventory/session names preserve the original b9 Flyt evidence.
            s=open_mode(mode,label+'-recovery-g'+str(group))
            for case in cases[offset:offset+5]:
                measure(s,case,'formal-recovery',label,steps=stepmap[slug(case)],warmup=32)
        finally:
            if s:close_mode(s)
            else:recover_start(mode)


def resume():
    probe=O/'infrastructure/b9-passthrough-startup-failure/probe/result.json'
    deadline=time.monotonic()+1800
    while True:
        if probe.exists() and json.loads(probe.read_text())['passed'] and not (B/'active.json').exists():break
        if time.monotonic()>deadline:raise TimeoutError('PCI recovery probe did not complete')
        time.sleep(5)
    assert Path('/sys/bus/pci/devices/0000:40:00.0/driver').resolve().name=='nvidia'
    assert not get('vmi','tt-passthrough-1102')
    seal=json.loads((O/'protocol-seal.json').read_text())
    assert hashlib.sha256((O/'protocol.json').read_bytes()).hexdigest()==seal['protocol_sha256']
    assert hashlib.sha256((R/'experiments/training-threeway/bench.py').read_bytes()).hexdigest()==seal['benchmark_sha256']
    prior=O/'formal/b9';archived=O/'interrupted/formal-b9-attempt1'
    assert len(list(prior.glob('flyt/*/result.json')))==10
    assert not (prior/'passthrough').exists() and not (prior/'vmweave').exists()
    assert not archived.exists() and not (O/'formal/b10').exists()
    archived.parent.mkdir(exist_ok=True)
    prior.rename(archived)
    record={'decision_utc':time.time(),'reason':'PCIe link down/up, device re-enumeration and VFIO startup failure before b9 passthrough measurements. Rerun the entire paired block to avoid mixing pre/post-interruption visits.',
            'preserved_completed_but_unpaired_runs':10,'preserved_directory':str(archived.relative_to(O)),
            'rerun_block':'b9','execution_phase':'formal-recovery','canonical_directory':'formal/b9',
            'unchanged':['benchmark source','protocol steps','warmup','sync','mode and case order','five-case visit grouping','images and libraries'],'performance_based_exclusions':False}
    save(O/'infrastructure/recovery-decision.json',record)
    protocol=json.loads((O/'protocol.json').read_text())
    i=8;cases=CASES[i:]+CASES[:i]
    for mode in protocol['orders'][i]:recovery_visit(mode,'b9',cases,protocol['steps'])
    replacement=O/'formal-recovery/b9'
    assert len(list(replacement.glob('*/*/result.json')))==30
    replacement.rename(O/'formal/b9')
    record['replacement_completed_utc']=time.time();save(O/'infrastructure/recovery-decision.json',record)
    i=9;cases=CASES[i:]+CASES[:i]
    for mode in protocol['orders'][i]:visit(mode,'b10',cases,'formal',protocol['steps'])
    assert len(list((O/'formal').glob('*/*/*/result.json')))==300
    save(O/'measurements-complete.json',{'formal_runs':300,'pilot_runs':54,'interrupted_block_runs_preserved':10,'utc':time.time()})
    print('MEASUREMENTS_COMPLETE',flush=True)


if __name__=='__main__':resume()
