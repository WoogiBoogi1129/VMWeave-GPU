from pathlib import Path
import json
O=Path('experiments/ai-passthrough/results/20261026-bulk-short');data=json.loads((O/'comparison.json').read_text());copy=json.loads((O/'copy-comparison.json').read_text());diag=json.loads((O/'diagnostic-summary.json').read_text());get=lambda w,m:next(r for r in data if r['workload']==w and r['mode']==m)
lines=['공유 버퍼 개선 축약 성능 비교 — Flyt / VMWeave OFF / VMWeave ON','', '워밍업은 각 workload session에서 1회. NW/LU/SRAD는 3회차에 2+2+1개 측정 표본.', 'StreamCluster는 1회차에만 워밍업1+측정1, 최소 정확성/실행 검증. 단일 표본의 우위/안정성 주장 금지.', '정식 표본 합계48개. Native/Passthrough 재측정 없음. 이번 Flyt는 동일 실행 파일로 재측정.', 'OFF/ON은 같은 후보 Guest/Broker와 같은 Worker; VMWEAVE_BULK_COPY 활성 여부만 다름.', '새 VM/backend를 방식·회차마다 생성. GPU0, VM8vCPU16GiB, QEMU32–39, backend40–43, GPU100%/8192MiB.', '주 측정값은 초기화 이후 CPU 관측 작업 완료 시간; 순수 kernel time 또는 학습 throughput 아님.', '', '평균 작업 완료 시간(초), OFF 대비 ON 감소율, ON/Flyt 시간 비율:']
for w in ['nw','lu','srad','sc']:
 f,a,b=[get(w,m) for m in ['flyt','off','on']];lines.append(f"{w}: Flyt {f['mean_s']:.6f}, OFF {a['mean_s']:.6f}, ON {b['mean_s']:.6f}; 감소 {b['off_time_reduction_pct']:+.2f}%; ON/Flyt {b['flyt_time_ratio']:.3f}배")
lines+=['','원시표본 raw.csv; 평균/중앙값/최소/최대/표준편차/회차별 평균 comparison.json.', '평균은 5개 표본 기준이며 회차별 표본수2/2/1이 다르다. 독립 단위는 VM session 3개다.', '표본 수가 작고 StreamCluster는 단일 표본이므로 통계적 유의성/보편적 우위를 주장하지 않는다.', '', '복사 회귀 검토 (OFF/ON 각1 session; 조건당 워밍업1+측정5, 중앙값):']
flagged=[]
for r in copy:
 if r['mode']!='on':continue
 lines.append(f"{r['bytes']} bytes {r['direction']}: OFF 대비 시간 증가 {r['time_increase_pct']:+.2f}%")
 if r['time_increase_pct']>5:flagged.append(f"{r['bytes']}B/{r['direction']}")
lines+=['5% 초과 증가 관측: '+(', '.join(flagged) or '없음'), '이는 회귀 의심 표시이며, 단일 세션의 표본5개로 통계적 회귀 또는 무회귀를 확정하지 않는다.', '', '별도 진단(16MiB H2D/D2H, 할당·동기화·해제 포함, 시간 통계에서 제외):']
for r in diag:lines.append(r['mode']+': '+json.dumps(r['socket_syscalls'])+'; SCM_RIGHTS='+str(r['fd_transfer_observed']))
lines+=['ON의 FD 전달과 실제 소켓 반환 바이트 감소로 공유 버퍼 경로를 확인했다.', 'syscall trace 시간은 계측 영향을 받으며 Guest/Broker/SHM/CUDA 전체의 배타적 구간 분해가 아니다.', '복사 probe의 CPU 시간은 Guest process 기준이다. Broker CPU/구간별 시간은 이번 축약 진단에서 수집하지 않았다.', '', '재현/해석 제한:', '모든 입력/seed/바이너리는 고정, 모든 출력은 Native reference hash와 대조.', 'SC CUDATIME는 기존 실험처럼 비활성. 추가 memset 동기화 최적화는 적용하지 않았다.', '임계값1MiB 고정, async/D2D와 작은 요청은 기존 경로. 전체 zero-copy가 아니다.', '진단 도구 glibc 불일치와 초기 cleanup 경로 assertion은 setup-failures에 보존.', 'OFF 복사 측정은 재사용하고 진단만 새 VM에서 재실행했다. 성능에 따른 표본 제외 없음.', '기본 활성화/운영 배포/이미지 Helm 교체 없음. main에는 결과 및 재현 자료만 반영.', '', '자료: raw.csv, comparison.json, copy-comparison.json, diagnostic-summary.json, runtime.png/svg,', 'copy-latency.png/svg, manifest.json, cleanup.json, reproduction/, sources/.']
(O/'REPORT.txt').write_text('\n'.join(lines)+'\n')
