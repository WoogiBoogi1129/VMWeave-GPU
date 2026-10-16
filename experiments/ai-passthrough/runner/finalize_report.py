"""Fill the report only from validated, completed measurements and cleanup evidence."""
import json,statistics
from pathlib import Path
R=Path(__file__).resolve().parents[1];E=R/'results/20261016'
v=json.loads((E/'validation.json').read_text());assert v['status']=='PASS' and v['formal_measurements']==80
clean=json.loads((E/'cleanup.json').read_text());assert clean['status']=='PASS'
assert json.loads((E/'equal-budget/validation.json').read_text())['status']=='PASS'
s=json.loads((E/'summary.json').read_text());eq=json.loads((E/'equal-budget/summary.json').read_text())
assert len(s['conditions'])==8 and all(x['n']==5 for x in s['conditions'])
assert len(eq['conditions'])==2 and all(x['n']==3 for x in eq['conditions'])
def table(rows):
 lines=['| 조건 | passthrough samples/s (평균 ± SD) | VMWeave samples/s (평균 ± SD) | VMWeave/PT (%) · 95% CI |','|---|---:|---:|---:|']
 for r in rows:
  a=r['backends']['passthrough'];b=r['backends']['vmweave'];lo,hi=r['ratio_95ci']
  lines.append(f"| {r['condition']} | {a['mean_samples_per_second']:,.2f} ± {a['sd_samples_per_second']:,.2f} | {b['mean_samples_per_second']:,.2f} ± {b['sd_samples_per_second']:,.2f} | {r['paired_geomean_ratio']*100:.3f}% [{lo*100:.3f}, {hi*100:.3f}] |")
 return '\n'.join(lines)
ratios=[x['paired_geomean_ratio'] for x in s['conditions']]
sensitivity=json.loads((E/'sensitivity.json').read_text());assert len(sensitivity['conditions'])==8
sens_lo=min(x['excluding_block2_ratio'] for x in sensitivity['conditions'])*100
sens_hi=max(x['excluding_block2_ratio'] for x in sensitivity['conditions'])*100
section=f'''## 성능 결과

주 비교의 **8조건 × 2경로 × 5반복 = 80측정**을 완료했다. 이 범위에서 VMWeave 처리량은 passthrough의 **{min(ratios)*100:.3f}–{max(ratios)*100:.3f}%**였다. 수치는 조건별 paired 처리량 비율의 기하평균이다. 25/75 Core 배분 실험이나 임의 AI 모델 전체의 성능으로 일반화하지 않는다.

{table(s['conditions'])}

공유 호스트 서비스 교체가 있었던 두 번째 블록을 제외한 사후 민감도 분석(n=4)에서 조건별 비율 범위는 **{sens_lo:.3f}–{sens_hi:.3f}%**였다. [전체 민감도 결과](results/20261016/sensitivity.json). 원래 5개 블록을 주 결과로 유지하며, 이 분석이 서비스 변경의 인과 효과를 분리하는 것은 아니다.

비율 신뢰구간은 같은 블록의 log(VMWeave/PT) 비율에 Student t 구간을 적용한 뒤 지수 변환했다. n=5로 작고 정규성은 보장하지 않는다. 모드 순서는 W/P, P/W, W/P, P/W, W/P여서 완전히 균형 잡힌 순서는 아니다. 통계적 허용 오버헤드를 미리 정하지 않았으므로 성능 자체에 임의 PASS 판정을 붙이지 않는다.

![처리량](figures/throughput.png)
![대조군 대비 처리량 비율](figures/ratio.png)
![CPU 비용](figures/cpu-cost.png)

[모든 반복의 처리량·CPU 비용·GPU 표본 통계](results/20261016/summary.json), [완료 자료 검증](results/20261016/validation.json). GPU 평균은 수집 표본의 산술평균이며, 1초 sleep에 query/SSH 지연이 추가되므로 실제 표본 간격은 CSV 타임스탬프로 확인해야 한다. CPU 값은 표본 구간의 누적 counter 차이로 계산한 추정치다.

반복별 본 측정 구간의 평균 GPU utilization은 VMWeave 0.00–0.28%, passthrough 1.88–15.06%였다. 양쪽 모두 이 작은 eager MLP에서 GPU 포화 상태를 달성하지 못했다. 따라서 포화된 대형 AI 학습 전체에 이 처리량 비율을 적용할 수 없다. 관측한 Pod 프로세스 CPU 사용량은 VMWeave 1.36–1.44 core, passthrough 1.28–1.30 core였으며, 이것이 전체 호스트 비용을 뜻하지는 않는다.

## 동일한 총 CPU 예산의 보조 결과

VMWeave 8 vCPU + Worker CPU 4개와 passthrough 12 vCPU를 비교했다. 두 조건을 별도 3 paired blocks에서 측정했으며 주 비교에 합치지 않았다.

{table(eq['conditions'])}

![CPU 허용 범위 보조 비교](figures/equal-budget.png)

[보조 측정 원시 결과와 통계](results/20261016/equal-budget/summary.json). 이 비교에서는 Guest vCPU 수가 다르므로 주 비교와 보조 비교를 함께 읽어야 한다.

'''
p=R/'README.md';text=p.read_text();assert '## 성능 결과' not in text;text=text.replace('**현재 성능 반복 측정 진행 중이며, 최종 성능 결론은 아직 작성하지 않았다.**','주 비교 80회와 총 CPU 예산 보조 비교 12회를 완료했다. 정확성 통과와 성능 결과, 지원하지 못한 조건을 구분해 기록한다.')
text=text.replace('## 비교 환경',section+'## 비교 환경',1).replace('총 CPU 예산 12개를 맞추는 별도 보조 측정을 계획했다.','총 CPU 예산 12개를 맞추는 별도 보조 측정도 수행했다.')
cleanup='''## 정리와 기존 서비스 관측

실험 VM/Worker를 회수하고 GPU 2를 NVIDIA 드라이버에 복원했다. 임시 KubeVirt 장치 허용 설정과 HAMi/DCGM scheduling 설정을 복구하고 실험 전용 저장소·helper를 정리했다. [정리 검증](results/20261016/cleanup.json)과 [기존 서비스의 주기적 UID·Ready·재시작/PID 관측](results/20261016/service-continuity.jsonl)을 보존한다. 이 관측은 서비스 요청 지연이나 SLA 전체를 검증한 것은 아니다.

'''
text=text.replace('## 시각 자료와 실행 자료',cleanup+'## 시각 자료와 실행 자료',1)
p.write_text(text)
