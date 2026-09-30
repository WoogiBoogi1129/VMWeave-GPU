# 현재 VMWeave에서 새 실험

새 실험은 중앙 Go Operator와 `vmweave.io/v1alpha1`을 사용합니다.
기존 `flyt-*` namespace와 실험 배포는 삭제했으므로 과거 리소스가 남아 있다고 가정하지 않습니다.
관리자가 등록한 사용자 namespace에서 새 VM·Request·Channel을 준비하고, 결과를 새 디렉터리에 보관합니다.

| 실험 | 현재 사용할 경로 | 검증 상태 |
|---|---|---|
| GPU 복사·PTX·회수 smoke | `scripts/run-evidence-smoke.py --api-group vmweave.io` | 9월 30일 두 namespace 실제 GPU 검증 완료 |
| 메모리 probe | 같은 실행기의 `--probe memory` | CLI에 새 API 경로 존재; 새 Operator에서 전체 quota 실험 재검증 필요 |
| PyTorch 학습 | 과거 학습 도구·고정 wheel을 별도로 이식 | 새 Operator campaign 검증 미완료 |
| N/T/S 성능 비교 | `experiments/performance/`의 새 API 실행기 | 경로별 5회·105구간 완료; [결과](resource-performance.md) |
| 단일 VM 상한 | 같은 실행기의 `single` 단계 | 20회 완료; 25·50·75에서 사전 이용률 기준 위반 |

API 명칭 변경만으로 모든 상위 실험 도구가 호환되는 것은 아닙니다.
과거 성능·학습 결과는 [역사 재현](reproduction.md)의 기록이며 새 제어기의 측정 결과로 표시하지 않습니다.

## GPU smoke

[Guest 준비](../getting-started/guest-images.md)와 [첫 VM](../getting-started/first-vm.md)의 자동 smoke 경로를 따릅니다.
VM은 Halted, 새 Channel은 BackingReady에서 시작합니다. 완료된 Released Channel을 재활성화하지 않습니다.
다음 실행에는 새 VM/Channel/PVC를 준비하거나, 기존 VM의 binding 제거와 backing 비사용을 검증하는 별도 절차가 필요합니다.
초기 실험에서는 새 전용 리소스를 사용하는 편이 명확합니다.

## 메모리 probe

첫 VM과 동일한 준비 후 별도 새 Channel에 실행합니다. 아래 namespace/VM/Channel은 먼저 생성해야 합니다.

```sh
python3 scripts/run-evidence-smoke.py --namespace team-a --api-group vmweave.io \
  --name memory-vm --channel memory-request --key YOUR_KEY \
  --artifacts .local/guest-artifacts --probe memory --scenario below --bytes 67108864 \
  --output .local/experiments/memory-new-run
```

단일 probe 성공은 전체 quota 실험 PASS가 아닙니다. 경계/OOM/재할당/동시 실행 조건과
HAMi 정책·독립 반복·제외 조건을 설계하고 각각 실제로 검증해야 합니다.

## PyTorch·성능 실험 전환 체크포인트

1. 고정 wheel·Guest/Worker ABI와 기존 측정 프로그램을 보존합니다.
2. 구 renderer/controller 설치 호출을 새 Profile/VM/Request/Channel 생성으로 교체합니다.
3. namespace·API group·UID·helper 이름을 하드코딩하지 않도록 실행 도구를 점검합니다.
4. 먼저 작은 실제 GPU 실행에서 Ready→정상 연산→Detached→Released를 검증합니다.
5. 그 후 기존 측정 경계·워밍업·반복·정책을 명시하여 새 결과를 수집합니다.

이 문서는 미완료 campaign을 완료했다고 선언하지 않습니다. 과거 결과 디렉터리나
고정된 source/프로토콜/체크섬을 덮어쓰지 않습니다.

## 결과와 정리

소스 commit·dirty 여부, 이미지 digest, namespace/객체 UID, 환경·quota, raw 출력,
성공·실패·제외 판정, detach·회수 증거를 기록합니다. 비밀키·TLS 키·원본 Secret은 공개하지 않습니다.
새 VM 초기 기동 시간은 GPU 연산 측정과 분리하고 [부팅 단계](../getting-started/guest-images.md)를 기록합니다.
종료 후 Channel 정상 삭제, 필요 데이터 백업, 관리 범위 해제, namespace 삭제 순서는
[운영 절차](../guides/upgrade-uninstall.md)를 따릅니다.
