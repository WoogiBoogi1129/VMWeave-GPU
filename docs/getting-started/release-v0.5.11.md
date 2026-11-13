# VMWeave v0.5.11: 고정 GPU 슬롯과 미배치 Worker 회수

Operator 0.5.11과 Device Plugin 0.1.3은 VM 내부 Kubernetes에서
**1~2개의 고정 GPU 슬롯**을 지원한다. 두 Pod는 VM에 이미 승인된 전체 GPU 예산을 공유한다.
Pod별 VRAM/compute 보장이나 동적 슬롯 증감은 제공하지 않는다.

## 변경 사항

- Operator는 `lifecycle: VM`에서 1~2 sessions를 허용하고 Profile 승인을 확인한다.
- Guest bootstrap은 실제 boot layout을 읽어 독립 Broker를 슬롯마다 실행한다.
- Plugin은 슬롯별 상태를 layout과 검증하고 선택된 소켓 directory만 컨테이너에 mount한다.
- 아직 node에 배치되지 않은 Worker를 삭제할 때, 실행되지 않았다는 엄격한 조건과
  소유권/UID 검증으로 detach 증거를 기록한다. 이 경우에도 finalizer를 강제 제거하지 않는다.
- CRD·SHM ABI·CUDA C 실행 경로·기존 GPU quota 계약은 변경하지 않는다.

## 업그레이드

Operator chart와 image를 0.5.11로 함께 갱신하며 기존 namespace 범위·TLS·mode 값을 보존한다.
현재 공개 digest와 적용 검증 상태는 [릴리스 목록](../releases/index.md)의 `current.json`을 따른다.
Helm upgrade만으로 기존 VM의 Guest package나 Worker/Channel이 바뀌지는 않는다.

Guest control package를 바꿀 때는 활성 GPU 작업이 없는지 확인하고 Broker를 정지한 뒤 설치한다.
VM을 Halted로 전환하여 Channel Stopped 및 backing 회수를 확인한 후 새 binding으로 시작한다.
Worker image 변경 시 immutable Profile/Request/Channel은 새 버전으로 생성하며 이전 Profile/Request는
롤백용으로 보존한다. [기존 paired runtime 절차](release-v0.5.9.md)를 함께 따른다.
기존 1슬롯 VM은 기본값 `slotCount: 1`로 유지할 수 있다.

2슬롯은 Profile `maxClients >= 2`, Channel `sessions: 2`, Plugin chart `slotCount: 2`가 필요하다.
Guest는 승인된 부팅 layout에서 개수를 읽으며 chart 값만으로 새 슬롯을 만들지 않는다.
Channel sessions는 immutable이므로 개수 변경은 기존 binding 회수와 Channel 재생성이 필요하다.
이때 정지 VM의 이전 Channel binding annotation도 정리한다.
각 Pod 컨테이너는 `vmweave.io/gpu: 1`을 요청한다.

## 검증과 제한

[발행 전 실제 GPU 실험](../../experiments/fixed-slots/results/20261113/REPORT.md)에서는
1슬롯 회귀, 2개 Pod의 동시 SGEMM 및 정답, 세 번째 Pod Pending, Plugin 재시작,
정상 종료·실제 회수 확인 후 재사용, Broker 부분 장애 시 peer 지속 실행을 확인했다.
이 기록은 작업 트리 후보의 검증이다. 공개 산출물·배포 검증은 별도 릴리스 기록으로 제공한다.

- 강제 Pod 삭제 직후에는 기존 client가 살아 있어 새 접속이 `busy(46)`로 거부될 수 있다.
  실제 CUDA child 회수 확인 또는 새 애플리케이션 실행의 재시도가 필요하다.
- Broker 장애 시 해당 슬롯은 신규 할당을 차단하며 자동 재시작하지 않는다.
  그 슬롯의 Host CUDA child와 VRAM은 VM 전체 정지·binding 회수 전까지 남을 수 있다.
- 정상 peer 실행은 확인했지만 공유 VRAM 고갈, 물리 GPU 고장, 성능 공정성을 격리하지 않는다.
- CNN·LSTM 등 기존 API 지원 범위는 [v0.5.10](release-v0.5.10.md)을 따른다.
  CNN은 여전히 `TORCH_CUDNN_V8_API_DISABLED=1`과 문서의 제한된 FP32 조건이 필요하다.
