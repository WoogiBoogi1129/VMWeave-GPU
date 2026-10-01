"""Build the report only from completed, verified independent repetitions."""
from common import *
import datetime
v=json.loads((OUT/'validation.json').read_text());assert v['complete']
s=json.loads((OUT/'summary.json').read_text())['summary'];c=json.loads((OUT/'cpu-summary.json').read_text())['summary']
names={'query':'cudaMemGetInfo','kernel':'launch + sync','h2d-4096':'H2D 4 KiB + sync','d2h-4096':'D2H 4 KiB + sync','h2d-1048576':'H2D 1 MiB + sync','d2h-1048576':'D2H 1 MiB + sync','h2d-16777216':'H2D 16 MiB + sync','d2h-16777216':'D2H 16 MiB + sync'}
latency=['| 항목 | 기존 설정 (ms) | 결합 개선 (ms) | 평균 감소율 |','|---|---:|---:|---:|']
for key,label in names.items():
 a,b=s['base'][key],s['both'][key]
 latency.append(f"| {label} | {a['mean_us']/1000:.4f} ± {a['sd_us']/1000:.4f} | {b['mean_us']/1000:.4f} ± {b['sd_us']/1000:.4f} | {v['improvements'][key]*100:.1f}% |")
ablation=['| 설정 | query | launch+sync | H2D 16 MiB | D2H 16 MiB |','|---|---:|---:|---:|---:|']
for name,label in [('base','기존'),('wait','대기만 개선'),('copy','복사만 개선'),('both','결합')]:
 ablation.append('| '+label+' | '+' | '.join(f"{s[name][m]['mean_us']/1000:.4f}" for m in ['query','kernel','h2d-16777216','d2h-16777216'])+' |')
cpu=['| 작업 | 기존 CPU 코어 상당 | 개선 CPU 코어 상당 | 기존 CPU µs/반복 | 개선 CPU µs/반복 |','|---|---:|---:|---:|---:|']
for key,label in [('query-1048576','query'),('kernel-1048576','launch+sync'),('copy-4096','4 KiB 복사 왕복'),('copy-1048576','1 MiB 복사 왕복'),('copy-16777216','16 MiB 복사 왕복')]:
 a,b=c['base'][key],c['both'][key];cpu.append(f"| {label} | {a['cores']:.3f} | {b['cores']:.3f} | {a['cpu_us_iteration']:.1f} | {b['cpu_us_iteration']:.1f} |")
uncertainty=max(min(x['uncertainty'] for x in json.loads(p.read_text())) for p in (OUT/'runs').glob('sf-r*/clock-map.json'))
text='''# SHM 첫 구현 묶음 — 실제 VM 개발·검증 결과

계측, 대기 정책, private 버퍼 복사 경로를 수정하고 네 조건을 각각 독립 5회 실행했다.
본 비교는 같은 Guest/Worker 바이너리의 기능 설정만 변경한 SHM 내부 비교다.
HAMi FORCE 100, GPU, VM 이미지, CPU affinity, CUDA workload와 동기화 경계는 동일하다.
실행마다 새 VM·채널·Worker를 만들었고 20세션·100개 측정 구간을 검증했다.
GPU는 NVIDIA RTX PRO 6000 Blackwell Server Edition, 드라이버는 580.173.02,
빌드 CUDA Toolkit은 12.8이다. Guest는 8 vCPU·16GiB이며 GPU 메모리 한도는 4GiB이다.
장치 UUID와 소프트웨어·배치 원본은 [실행 환경](environment-formal.json)에 보존했다.

## 지연 결과

각 값은 실행별 평균의 평균 ± SD이며 표본 요청들을 독립 반복으로 세지 않았다.
query는 작은 cudaMemGetInfo 요청이다. 파일명의 1048576은 probe의 버퍼 설정이며 query payload 크기가 아니다.

'''+ '\n'.join(latency)+'''

![소형 호출](figures/small-latency.png)

![대형 전송](figures/large-latency.png)

## 변경 효과 분리

아래 단위는 ms이다. 대기 변경과 복사 변경을 독립적으로 켜고 끈 결과이며,
결합 효과를 각 변경의 단순 합으로 가정하지 않는다.

'''+ '\n'.join(ablation)+'''

대기 개선은 양쪽의 1ms sleep을 50µs 요청 sleep으로 변경한다. **본 실험은 active spin 0µs**이다.
10ms 동안 일이 없으면 1ms sleep으로 backoff한다. 실제 sleep 시간은 OS 스케줄링에 따라 더 길 수 있다.
idle 직후 첫 요청은 여전히 긴 sleep을 만날 수 있으며 event/doorbell 기반 구현은 아니다.

복사 개선은 Guest의 최대 16MiB+48B private staging 재사용, Worker의 검증된 private 입력을 이용한
동기 H2D, preallocated private 응답 버퍼를 이용한 D2H, 대형 payload의 정렬된 volatile 64-bit snapshot이다.
descriptor 검증과 byte snapshot은 유지한다. H2D CPU 전체 payload 복사는 4→3회,
D2H는 3→2회가 된다. 공유 메모리를 GPU에 직접 전달하는 zero-copy 구현은 아니다.
Guest staging은 종료까지 보유하므로 최대 약 16MiB의 추가 retained buffer라는 비용이 있다.

## CPU 비용

초당 가능한 한 많은 작업을 수행하는 포화 부하이므로 개선 후 초당 CPU 소비도 증가한다.
동시에 처리한 작업 수가 증가하므로 작업 한 건당 CPU 시간도 함께 평가해야 한다.
Worker와 QEMU/Guest가 포함된 launcher Pod의 서로 겹치지 않는 cgroup 카운터를 합산했다.
복사 반복은 H2D+sync와 D2H+sync 두 방향을 모두 포함한다.

'''+ '\n'.join(cpu)+'''

![CPU 비용](figures/cpu-cost.png)

초기 20µs spin 예비 실행은 더 짧은 지연과 높은 포화 CPU 소비를 보였다.
이 결과를 바탕으로 active spin을 사용하지 않는 후보를 별도 예비 실행한 뒤 본 실험 조건을 고정했다.
예비 실행 3세션은 본 실험 5회 반복에 포함하지 않는다. 기본값 선택은 지연뿐 아니라
p95 악화 여부와 작업당 CPU 비용의 추가 검토를 포함한다.

## 코드 반영

검증을 통과한 `bounded` 대기, spin 0µs, sleep 요청 50µs, `optimized` 복사를
실제 런타임 기본값으로 채택했다. 계측은 기본적으로 꺼져 있다.
기존 동작은 Guest와 Worker 양쪽에서 `FLYT_WAIT_MODE=legacy`, `FLYT_COPY_MODE=legacy`를
설정하고 새 프로세스를 시작하여 복원할 수 있다. 최종 기본값으로 재빌드한 바이너리는
본 비교 실험의 바이너리와 구분해 별도로 실제 VM 회귀 검증했다.

## 검증·측정 범위

- 조건별 10초 측정, 최소 3초·50회 워밍업. 기존 microbenchmark 측정 길이를 재사용한 집중 실험이다.
  상세 계획의 장시간 workload sweep과 별개이며 60초 측정으로 보고하지 않는다.
- 모든 구간에서 CUDA 오류 여부와 종료 시 전체 결과 버퍼를 검산했다. 모든 반복 출력의 매번 전체 검산을 뜻하지 않는다.
- 원시 CSV 표본 수·연속 번호·유한 양수 지연, Guest/Worker 해시, 실제 HAMi 매핑과 설정, 정상 Released 상태를 대조했다.
- p95는 실행별 값을 보존한다. p99는 실행당 10,000표본 미만이면 생략하며 대형 복사 tail을 과도하게 해석하지 않는다.
- 구간별 내부 계측은 프로세스 누적치로 startup/warmup을 포함한다. receive와 exchange는 중첩하므로 합산하지 않는다.
  본 실험에는 계측을 동일하게 켰고, 최종 사용자 기본값에서는 계측 출력이 opt-in이다.
- API 지연은 Guest monotonic clock으로 계산한다. CPU 시계열의 Guest/Host 정렬 불확실성 최대치는 '''+f'{uncertainty:.3f}초'+'''이다.
- 기존 Flyt TCP/RPC+MPS와 정책을 맞춘 전송-only 비교는 이번 범위에 포함하지 않는다.
  이 결과는 SHM 구현 개선을 입증하며 TCP라는 전송 매체 자체보다 우수하다는 일반 결론은 아니다.
- HAMi 이용률 상한 준수, CUDA Graph, 명령 배치, 비동기 API 의미 변경, pinned memory, doorbell은 이번 변경에 포함하지 않는다.
- 최종 재빌드 후 메모리 경계·소유권·오류 처리 C 회귀와 layout Python 6개 테스트를 통과했다.
  새 경계·복사 테스트는 ASan/UBSan으로도 확인했고, 제어 경로 Python 54개 테스트를 통과했다.
  정상 경로는 leak 검사를 포함한다. fatal CUDA 오류 경로는 기존 계약대로 프로세스 종료가
  poisoned context를 회수하므로 leak 검사에서 잔류 메모리를 보고했다. 최초 로그를 보존하고,
  fatal 테스트에서 destroy의 실패·컨텍스트 유지까지 검증한 뒤 이 경로만 leak 검사를 끄고 ASan/UBSan을 수행했다.
- 보충 2VM 회귀의 B Worker 종료 계측은 Pod 정리로 누락됐다. 실행 중 해시·정책, 결과·CSV·Released는 확인했다.
  [누락 및 수집기 보완 이력](supplemental-collection-note.json)에 검증 범위 변경을 명시했다.

## 준비 실패와 복구

노드의 기존 image GC가 사용하지 않는 로컬 전용 이미지를 제거했다. Guest/launcher/hook의 원래 digest를 복구했고,
sf-r1-base는 Worker 이미지 부재로 affinity 설정 단계에서 멈췄다. **아직 측정 명령이 실행되지 않았음을 확인한 뒤**
동일 UID의 준비된 세션을 이어서 실행했다. 성능 표본의 폐기·재실행은 없었다.
임시 stopped image-reference containers로 실험 이미지에만 참조를 유지했으며 글로벌 kubelet 설정은 바꾸지 않았다.
초기 이미지 build context 및 이전 import namespace 실패와 테스트 컨테이너의 Python/driver-stub 준비 이력도 보존한다.

## 자료

- [프로토콜](protocol.json), [검증과 채택 조건](validation.json), [실행별 지연](summary.json), [CPU 원시 집계](cpu-summary.json)
- [원시 실행·CSV·프로세스·해시](runs/), [명령 이력](commands.jsonl), [빌드 자료](build/)
- [실제 Grafana 캡처](captures/), [실제 터미널 로그 조회 캡처](terminal-captures/), [모니터링 설정](monitoring/)
- [기본 정책·다중 VM 최종 회귀 검증](REGRESSION.md), [자원 정리](cleanup-complete.json)
- [최종 자원·GPU 감사](final-audit.json), [기존 결과 무변경 확인](prior-evidence-integrity.json)
- [개발·실험 실행 코드](../../../shm-first-bundle/README.md), [런타임 설정](../../../../runtime/shm/PERFORMANCE.md)
- [SHA256 목록](SHA256SUMS)
'''
(OUT/'README.md').write_text(text)
