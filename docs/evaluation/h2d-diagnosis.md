# 16MiB CPU→GPU 전송 지연 원인

2026-10-05, 이전 전체 시스템 비교에서 SHM이 20.2% 느렸던 H2D 16MiB를 후속 분석했다.
새 주 비교에서도 SHM 지연이 TCP보다 23.0% 높았다. SHM 내부에서는 Guest의
중간 payload 복사 한 번을 제거하자 계측 OFF H2D 지연이 48.1% 줄었다.

| 16MiB H2D + 동기화 | 평균 ± SD (ms) |
|---|---:|
| 기존 TCP/RPC + MPS | 7.5414 ± 0.3173 |
| 기존 개선 SHM + HAMi | 9.2755 ± 0.3465 |
| 진단 SHM 대조군 / 계측 OFF | 9.2964 ± 0.1612 |
| Guest 복사 제거 / 계측 OFF | 4.8202 ± 0.0448 |

각 값은 새 VM 5회의 세션 평균과 표본 SD다. 주요 구간은 10초·50회 이상 워밍업 후
60초를 측정했다. 4/8/12/16MiB 주 비교 10세션, 원래/복사 제거 × 계측 ON/OFF
20세션, 탐색 CPU/NUMA 2세션을 구분한다. H2D 단독·작은 전송은 10초 보조 구간이다.

## 무엇을 확인했는가

기존 H2D의 `사용자 버퍼 → Guest staging → SHM → Worker private snapshot → CUDA`에서
Guest staging payload 복사만 없앴다. private header, 동기 호출의 입력 수명과 mutex,
Worker의 private snapshot·검증 경계는 유지했다. CPU 전체 payload 복사가 3→2회로 줄며
GPU zero-copy는 아니다. 후보는 별도 실험 빌드에만 적용했고 운영 기본값은 변경하지 않았다.

요청 ID로 Guest/Worker의 내부 구간을 연결했다. 서로 다른 시계를 빼거나
중첩된 exchange/dispatch 시간을 합산하지 않았다. 계측 OFF에서도 end-to-end 개선을
확인했지만 그 이득 전체가 staging memcpy 시간과 같지는 않다.
뒤쪽 복사·CUDA API 시간도 바뀌었으며 캐시·메모리 트래픽의 개별 효과는 분리하지 않았다.

TCP+MPS와 SHM+HAMi의 정책·요청 처리기·버퍼 관리 차이가 남는다.
따라서 기존 20.2%를 전송 매체 하나의 차이로 해석하거나 복사 단계별로 산술 배분하지 않는다.
CPU 시간·p95·작은 전송·정확성·정상 종료 결과는 전체 보고서에서 함께 확인한다.

## 검증과 한계

초기 주 비교는 VM 종료와 SHA256 수집이 경합했다. 종료 전에 자료를 확보하도록 수정한 뒤
T/S 전체를 새 이름으로 재실행했으며 초기 결과를 정식 평균에 합산하지 않았다.
예비 실행의 계측 teardown 문제, 준비 실패, CSV 수집 실패도 보존했다.
크기 스윕은 고정 오름차순이므로 보편적인 역전 크기를 단정하지 않는다.
CPU/NUMA는 한 쌍의 탐색 결과이며 일반 애플리케이션·비동기 API 호환성을 입증하지 않는다.

- [전체 결과 보고서와 그림](https://github.com/WoogiBoogi1129/VMWeave-GPU/blob/985bb0206a037a58b6ead8371df6706ba11c6380/experiments/evidence/results/2026-10-05-h2d-diagnosis/README.md)
- [계측·원시 표본·세션 통계](https://github.com/WoogiBoogi1129/VMWeave-GPU/blob/985bb0206a037a58b6ead8371df6706ba11c6380/experiments/evidence/results/2026-10-05-h2d-diagnosis/analysis.json)
- [검증 결과](https://github.com/WoogiBoogi1129/VMWeave-GPU/blob/985bb0206a037a58b6ead8371df6706ba11c6380/experiments/evidence/results/2026-10-05-h2d-diagnosis/validation.json), [최종 환경 감사](https://github.com/WoogiBoogi1129/VMWeave-GPU/blob/985bb0206a037a58b6ead8371df6706ba11c6380/experiments/evidence/results/2026-10-05-h2d-diagnosis/final-audit.json)
- [실행·분석 도구](../../experiments/h2d-diagnosis/README.md)

증거 링크는 실험 커밋 `985bb0206a037a58b6ead8371df6706ba11c6380`로 고정했다.
