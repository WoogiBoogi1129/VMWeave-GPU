# 운영 점검과 문제 해결

## 점검 순서

1. 제어기·webhook Pod의 readiness와 로그를 확인합니다.
2. Profile·Request·VM·PVC UID 참조와 Channel 상태를 확인합니다.
3. Worker 배치 노드, 이미지 digest, HAMi 적용, Guest/Worker mapping ACK를 확인합니다.
4. 지원하는 최소 CUDA 작업을 실행하고 응답·검산 결과를 확인합니다.
5. 종료 시 drain, detach 및 Released를 확인합니다.

```sh
kubectl -n YOUR_NAMESPACE get pods
kubectl -n YOUR_NAMESPACE get flytsharedmemorychannels,flytchannelattachments
kubectl -n YOUR_NAMESPACE describe flytsharedmemorychannel YOUR_CHANNEL
```

| 증상 | 우선 확인할 사항 |
|---|---|
| review에서 GPUUnavailable | CPU 전용 환경이면 예상 상태; GPU Ready와 구분 |
| ImagePullBackOff | registry 접근·이미지 digest·노드 이미지 캐시 |
| backing 또는 mapping 대기 | 로컬 PVC 노드·권한, QEMU UID/GID, hook, BAR·layout |
| CUDA 함수 실패 | 현재 API 범위와 Guest/Worker 버전 일치 |
| OOM | 요청 quota·실제 HAMi 정책·잔여 할당; 기존 세션의 작은 재요청 가능 여부 |
| Released 미도달 | 진행 중 요청, detach 증거, 실행 세대 및 finalizer 보유 이유 |

제어기와 webhook은 `/livez`, `/readyz`, `/metrics`를 제공합니다.
기본 chart는 전체 Grafana/Prometheus 스택을 설치하지 않습니다.
실험에 사용한 dashboard와 수집 자료는 각 결과 묶음의 원본으로 연결합니다.

[채널 수명 주기](../architecture/lifecycle.md) · [제어기 설치·운영 세부](../getting-started/cpu-control-plane.md)
