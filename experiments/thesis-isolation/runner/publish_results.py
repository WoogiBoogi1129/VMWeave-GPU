import pathlib,json,tarfile,hashlib,shutil,csv,html
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=pathlib.Path(__file__).resolve().parents[3];exp=root/'experiments/thesis-isolation';base=exp/'results/20261012-campaign';pub=exp/'evidence/20261013';pub.mkdir(parents=True,exist_ok=True)
s=json.loads((base/'stage7/summary.json').read_text());plan=json.loads((base/'stage6/plan.json').read_text());e1=[]
for p in sorted((base/'pairs').glob('iso-e1-*/verdict.json')):
 d=json.loads(p.read_text());assert d['status']=='PASS' and d['observer_errors']==0 and d['observer_mismatches']==0;e1.append(d)
assert len(e1)==10
n=sum(d['observer_attempts'] for d in e1)
files=set()
for p in (base/'pairs').glob('iso-e1-*/verdict.json'):files.add(p)
for run in plan['runs']:
 p=base/'pairs'/run['name'];files.update(p.glob('*.json'))
 for slot in ['a','b']:files.add(base/'runs'/(run['name']+'-'+slot)/'cleanup.json')
for d in e1:
 for name in d['sessions']:
  p=base/'runs'/name
  for fname in ['requests-events.jsonl','cleanup.json']:
   if (p/fname).exists():files.add(p/fname)
files.update((base/'stage7').glob('*'));files.update(p for p in (base/'stage6').glob('*.json'))
manifest={str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
with tarfile.open(pub/'raw-evidence.tar.gz','w:gz') as tar:
 for p in sorted(files):tar.add(p,arcname=str(p.relative_to(base)),recursive=False)
(pub/'raw-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
for name in ['summary.json','per-run.csv','analysis.md']:shutil.copy(base/'stage7'/name,pub/name)
(pub/'e1-summary.json').write_text(json.dumps({'repetitions':10,'pass':10,'observer_attempts':n,'errors':0,'mismatches':0,'verdicts':[str(p.relative_to(base)) for p in sorted((base/'pairs').glob('iso-e1-*/verdict.json'))]},indent=2)+'\n')
rows=list(csv.DictReader((pub/'per-run.csv').open()));fig,axes=plt.subplots(1,2,figsize=(11,4))
for i,(key,title,reference) in enumerate([('throughput_retention_pct','Throughput retention (%)',100),('p99_increase_pct','p99 change (%)',0)]):
 for j,c in enumerate(['memory','compute']):
  vals=[float(r[key]) for r in rows if r['condition']==c];axes[i].scatter([j+(k-4.5)*.025 for k in range(10)],vals,label=c)
 axes[i].axhline(reference,color='gray',linestyle='--');axes[i].set_xticks([0,1],['Memory load','Compute load']);axes[i].set_ylabel(title);axes[i].grid(axis='y',alpha=.2)
fig.suptitle('VMWeave-GPU: 10 paired repetitions (5 per direction)');fig.tight_layout();fig.savefig(pub/'paired-results.png',dpi=180);fig.savefig(pub/'paired-results.pdf');plt.close(fig)
allg=[g for g in s['groups'] if g['direction']=='all'];table='\n'.join(f"| {g['condition']} | {g['throughput_rps']['mean']:.4f} | {g['p99_ms']['mean']:.3f} | {g['throughput_retention_pct']['mean']:.3f}% | {g['p99_increase_pct']['mean']:.3f}% |" for g in allg)
report=f'''# VMWeave-GPU 실험 결과 — 2026-10-12~13

## 목적과 범위

동일 GPU를 사용하는 두 VM에서 VRAM 할당량과 성능 경합을 측정했다. 사용자가 단계별로 승인한 원래 성능 실험을 완료했다. 이후 수정된 계획서는 성능 실험을 삭제하고 데이터 접근 검사를 E2로 재번호화했으므로, 아래에서는 **성능 경합 P**로 구분한다. 수정 계획의 E2~E4를 수행한 것으로 표시하지 않는다.

## 환경과 재현

시험 대상 소스: `01b7e2a01fafaaaadbc43c5913bcbd8eca5458e5`. 결과 게시 커밋은 이 문서가 속한 커밋이며 시험 대상 소스와 다르다.

- GPU: RTX PRO 6000 Blackwell Server Edition, 시험 GPU 1대, 드라이버 580.173.02.
- VM 각각 8 vCPU/16 GiB RAM, 독립 Worker·64 MiB SHM·클라이언트 1개. 연산 설정 각각 50%.
- E1: 역할을 교환하며 관측 VM 4096 MiB/할당 VM 1024 MiB. 성능 P: 각각 2048 MiB.
- P: Python 3.10.12, PyTorch 2.11.0+flyt.cu128, CUDA 12.8, FP32 eager MLP 1024→2048→1024, batch 32, seed 20261012.
- 정확성: CPU FP32 기준과 모든 출력 비교, rtol=1e-4/atol=1e-6. 지연시간은 forward+GPU 동기화이며 CPU 복사·검증은 제외한다. 처리량 경과 시간에는 검증이 포함된다.
- 요청 타임아웃 설정 40초, 본 측정 구간 1260초. 방향별 5회, 각 반복에서 세 조건 순서를 고정 seed로 무작위화. 첫 완료 측정을 포함해 10회/30구간.
- 메모리 부하: 자기 128 MiB 버퍼의 반복 곱셈. 연산 부하: 자기 1024×1024 FP32 행렬 곱, 행렬 합계 12 MiB. CUDA 동기화 후 완료 횟수 기록.

이미지 digest 및 준비 당시 설정은 [config](config/)에, 실행 당시 순서·seed는 아래 원시 묶음의 각 protocol.json에 있다. 초기 protocol.json의 pending 표시는 준비 시점 스냅샷이며 최종 성능 조건은 이 보고서와 묶음의 stage6/plan.json을 따른다.

## 결과 요약

| 실험 | 수행 | 결과 | 판정 |
|---|---:|---|---|
| E1 VRAM 할당량/OOM 회복 | 10회 | 관측 {n:,}건, 오류·불일치 0; 10회 OOM 및 동일 프로세스 회복 | 실행기 PASS 10/10 |
| P 성능 경합 | 10회 × 3조건 | 정상 {s['successful']:,}건, 오류·불일치 0, 모든 구간 ≥10,000건 | 측정 완료; 서비스 적합성 INCONCLUSIVE |
| 수정 E2 데이터 읽기·쓰기 격리 | 0회 | 단계별 승인된 성능 작업 범위에 포함되지 않음 | 미실행 |
| 수정 E3 GPU 실행 오류 전파 | 0회 | 이번 단계 범위 밖 | 미실행 |
| 수정 E4 Worker 종료 전파 | 0회 | 이번 단계 범위 밖 | 미실행 |

## 성능 결과

| 조건 | 평균 처리량 (건/초) | 반복별 p99 평균 (ms) | 처리량 유지율 | p99 증가율 |
|---|---:|---:|---:|---:|
{table}

변화율은 동일 반복의 기준 조건과 짝지어 계산한 뒤 동일 가중 평균했다. 평균 p99는 요청 전체를 합친 p99가 아니다.

![반복별 기준 대비 변화](evidence/20261013/paired-results.png)

## 해석과 한계

시험한 MLP와 부하에서 처리량·p99의 변화가 작았고 결과 불일치는 관찰되지 않았다. GPU 포화 부하임을 입증한 것은 아니며 다른 워크로드나 물리 GPU 격리 보장으로 일반화하지 않는다. 요청 자기상관, 방향별 5회 반복의 한계가 있어 통계적 유의성을 주장하지 않는다. 서비스 SLA가 없어 적합성은 판정 보류다. E1의 OOM은 이번 할당량 설정에서의 관측이며 모든 드라이버 상태의 증명이 아니다.

초기 성능 파일럿은 잘못된 Python 번들 경로로 준비 실패했고 본 측정에 포함하지 않았다. 수정 후 단계 3 정확성 확인과 단계 4 파일럿을 거쳐 본 측정을 시작했다. 실패 원본과 전체 명령/인벤토리 로그는 로컬 `results/`에 그대로 보존했다. 인증·클러스터 정보가 섞일 수 있는 전체 원본은 공개 묶음에서 제외했다. 선택된 측정 원시 자료는 원본 바이트와 해시로 보존했다.

## 근거와 재현

- [방향별 상세 분석](evidence/20261013/analysis.md), [반복별 CSV](evidence/20261013/per-run.csv), [기계 판독 집계](evidence/20261013/summary.json).
- [원시 증거 묶음](evidence/20261013/raw-evidence.tar.gz), [원본 파일별 SHA256](evidence/20261013/raw-sha256.json), [E1 집계](evidence/20261013/e1-summary.json).
- [집계 도구](runner/summarize_performance.py), [단일 반복 실행기](runner/measure_e2_repeat.py), [반복 제어기](runner/repeat_e2_campaign.py), [워크로드](probes/mlp.py).
- 재집계: 저장소 루트에서 아래 명령을 실행한다. 새 GPU 실험을 시작하지 않는다.

```bash
mkdir -p experiments/thesis-isolation/results/20261012-campaign
tar -xzf experiments/thesis-isolation/evidence/20261013/raw-evidence.tar.gz -C experiments/thesis-isolation/results/20261012-campaign
python3 experiments/thesis-isolation/runner/summarize_performance.py
```

실제 GPU 재실행은 로컬 키·번들·클러스터 준비가 필요하며 일반 클론만으로 즉시 실행되지 않는다. 하드코딩한 기존 실행 ID에 덮어쓰지 않도록 새 캠페인 경로를 사용해야 한다. 20개 성능 세션의 정상 회수 기록이 원시 묶음에 있다.

## 결과 화면

아래는 저장된 결과를 HTML로 렌더링한 화면 캡처다. 실험 당시 실시간 Grafana 화면으로 표시하지 않는다.

![저장된 결과 화면](evidence/20261013/results-screen.png)
'''
(exp/'report.md').write_text(report)
body=f'<h1>VMWeave-GPU — Recorded experiment results</h1><p>2026-10-12–13 · source 01b7e2a01faf · generated from saved evidence</p><h2>E1: 10/10 PASS · {n:,} observer requests · 0 errors/mismatches</h2><h2>Performance: 30/30 intervals · {s["successful"]:,} successful requests</h2><p>0 errors / mismatches · all intervals ≥10,000 requests · 20 sessions released</p><img width="1050" src="paired-results.png"><p>Service suitability: INCONCLUSIVE. Renumbered isolation E2–E4: not executed.</p><p>This is a rendered evidence summary, not a live experiment dashboard.</p>'
(pub/'results-screen.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font:18px sans-serif;margin:40px;color:#17324d;background:#f5f8fc}h1{font-size:30px}h2{font-size:22px}</style>'+body)
(exp/'README.md').write_text('# 2026-10-12~13 실험\n\n[최종 보고서](report.md) · [선별 원시 증거](evidence/20261013/raw-evidence.tar.gz)\n\nE1 및 단계별 승인된 성능 실험 P를 기록한다. 수정 계획의 E2~E4는 미실행이다. `results/`는 로컬 전체 원본이며 공개 증거는 `evidence/`에 선별한다.\n')
(exp/'.gitignore').write_text('results/\n__pycache__/\n*.pyc\n')
p=root/'experiments/README.md';t=p.read_text();link='- [2026-10-12~13 VRAM 할당량 및 성능 경합 결과](thesis-isolation/report.md)';
if link not in t:p.write_text(t+'\n'+link+'\n')
print('E1 requests',n,'archive bytes',(pub/'raw-evidence.tar.gz').stat().st_size)
