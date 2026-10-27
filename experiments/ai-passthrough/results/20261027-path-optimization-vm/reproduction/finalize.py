"""Finalize local evidence and cross-links after successful cleanup audit."""
import json,hashlib,shutil,datetime,subprocess,sys
from pathlib import Path
R=Path.cwd();B=R/'.local/path-optimization-20261027';O=R/'experiments/ai-passthrough/results/20261027-path-optimization-vm';C=Path('/home/ubuntu/taeuk/vmweave-path-optimization-20261027')
assert json.loads((O/'post-status.json').read_text())['stage']=='COMPLETE'
assert json.loads((O/'final-audit.json').read_text())['status']=='PASS'
assert json.loads((O/'comparison.json').read_text())['status']=='DO_NOT_PROMOTE'
assert 'Ran 6 tests' in (O/'layout-permissions-root.log').read_text() and 'OK' in (O/'layout-permissions-root.log').read_text()
subprocess.run([sys.executable,str(B/'report.py')],check=True)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
save(O/'status.json',{'stage':'COMPLETE_DO_NOT_PROMOTE','completed_at':now,'formal_VMs':15,'formal_samples':150,'actual_VM_correctness':'PASS','child_recovery':'PASS','VM_recreation':'PASS','wait_profiles':'EXPLORATORY_1_VM_EACH_0_10_50_US','GPU_sanitizer':'TOOL_STARTUP_BLOCKED_NOT_PASS','performance':'DO_NOT_PROMOTE','production_deployment':'NOT_PERFORMED_GATE_FAILED','main_commit_push':'NOT_PERFORMED','release_image_and_Helm_update':'NOT_PERFORMED','report':'REPORT.md','next_steps':'NEXT-STEPS.md'})
d=json.loads((C/'status.json').read_text())
d['status']='ACTUAL_VM_TESTED_PERFORMANCE_GATE_FAILED_NOT_PROMOTED'
d['checks'].update({'layout_permissions':'PASS_6_IN_ISOLATED_ROOT_CONTAINER','actual_VM_PCI_BAR':'PASS_CONTROL_AND_COMBINED_CANDIDATE','device_verification_kernels':'PASS_DEFAULT_BLOCKING_AND_NONBLOCKING_EXPLICIT_COMPLETION','actual_VM_child_recovery':'PASS','actual_VM_generation_recreation':'PASS','Flyt_performance_comparison':'COMPLETED_DO_NOT_PROMOTE','GPU_sanitizer':'TOOL_STARTUP_BLOCKED_NOT_PASS'})
d['P6a']='EXPLORATORY_0_10_50_US_1_VM_PER_PROFILE'
d['not_run']=['individual-stage full performance ablation','full syscall-failure/concurrency qualification','successful GPU Compute Sanitizer qualification','full CUDA API/kernel/stream semantic qualification']
d['deployment']='NOT_PERFORMED_PERFORMANCE_GATE_FAILED'
d['actual_VM_report']='../flyt-k8s-poc-github/experiments/ai-passthrough/results/20261027-path-optimization-vm/REPORT.md'
d['actual_VM_completed_at']=now
save(C/'status.json',d)
def insert(path,block,marker):
    text=path.read_text()
    if marker not in text:
        head,tail=text.split('\n',1);path.write_text(head+'\n\n'+block+'\n'+tail)
marker='후속 실제 VM 실험'
if not (C/'validation/REPORT-host-only.md').exists():
    shutil.copy2(C/'validation/REPORT.md',C/'validation/REPORT-host-only.md')
insert(C/'validation/REPORT.md','''후속 실제 VM 실험(2026-10-27): 실제 PCI BAR 정확성, CUDA 자식 장애 복구와 VM 세대 전환을 통과했다.
Flyt/control/candidate 각 5개 VM 비교에서 후보는 control보다 실행시간이 34.3% 짧았지만,
Flyt보다 종합 10.0% 길었다. 운영·main·릴리스 이미지·Helm은 승격하지 않았다.
[실제 VM 비교 보고서](../../flyt-k8s-poc-github/experiments/ai-passthrough/results/20261027-path-optimization-vm/REPORT.md),
[후속 개선안](../../flyt-k8s-poc-github/experiments/ai-passthrough/results/20261027-path-optimization-vm/NEXT-STEPS.md).
root 권한 검사도 후속에서 6/6 통과했다. GPU Compute Sanitizer는 도구 시작 단계 문제로 미완료다.
아래는 선행 호스트 경로 검증 당시의 기록이다.''',marker)
for filename in ['20261027-memset-native.md','20261027-path-optimization.md','20261027-path-optimization-preparation.md']:
    insert(R/'experiments/ai-passthrough/plans'/filename,'''후속 실제 VM 실험(2026-10-27): PCI BAR 통합·자식 장애 복구·VM 세대 전환 검증과
Flyt/control/candidate 각 5개 VM 성능 비교를 완료했다. control 대비 실행시간 34.3% 감소,
Flyt 대비 종합 10.0% 증가로 승격 조건 미충족. 운영·main·릴리스 이미지·Helm 변경 없음.
[결과와 검증 한계](../results/20261027-path-optimization-vm/REPORT.md),
[다음 개선안](../results/20261027-path-optimization-vm/NEXT-STEPS.md). 아래 준비/검증 전 표기는 과거 기록이다.''',marker)
insert(R/'experiments/ai-passthrough/results/20261027-path-optimization-validation/README.md',
       '후속 실제 VM 실험과 Flyt 5회 비교를 수행했다. [최신 보고서](../20261027-path-optimization-vm/REPORT.md).\ncontrol 대비 34.3% 개선했지만 Flyt 대비 종합 10.0% 느려 운영 승격은 하지 않았다. 아래는 선행 검증 기록이다.',marker)
repro=O/'reproduction';repro.mkdir(exist_ok=True)
for p in B.iterdir():
    if p.suffix in ['.py','.cu'] or p.name.endswith('.Containerfile'):
        shutil.copy2(p,repro/p.name)
(repro/'README.md').write_text('''# Executed campaign scripts

These are the scripts used from the repository root on the experiment host.
They reference the isolated candidate build and local guest packages under
`.local/path-optimization-20261027`; binary hashes and image digests are in the parent directory.

The fixed formal protocol predates measurements. Supplementary qualification hooks were added
without changing the formal measurement branch; see `../formal-harness-scope-check.json`.
`analyze.py` and `plot.py` regenerate derived outputs from the preserved raw JSON.

Do not rerun the infrastructure scripts against the original output/resource names: outputs are
exclusive-create and belong to this completed campaign. A new run needs new output paths and
experiment resource names, and must recheck the test GPU, CPU placement and current production state.
No private SSH key or runtime Mongo password is included here.

Root layout permission check used a rootless Podman container with UID 0, network disabled,
NVIDIA_VISIBLE_DEVICES=void, read-only candidate mount at /work, and
VMWEAVE_GUEST_LIBRARY=/work/build/libvmweave_guest.so. The command was
`python3 /work/source/tests/integration/layout_permissions.py -v` in the candidate Worker image.
''')
save(repro/'manifest.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(repro.iterdir()) if p.is_file() and p.name!='manifest.json'})
previous_evidence=C/'validation/evidence-sha256.json'
if not (C/'validation/evidence-sha256-host-only.json').exists():
    shutil.copy2(previous_evidence,C/'validation/evidence-sha256-host-only.json')
hashes=json.loads(previous_evidence.read_text())
for key in hashes:
    if (C/key).is_file():hashes[key]=hashlib.sha256((C/key).read_bytes()).hexdigest()
hashes['validation/REPORT-host-only.md']=hashlib.sha256((C/'validation/REPORT-host-only.md').read_bytes()).hexdigest()
save(previous_evidence,hashes)
save(O/'evidence-sha256.json',{str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.rglob('*')) if p.is_file() and p.name!='evidence-sha256.json'})
print('Local reports and status updated; no git commit, push, release publication or production change.')
