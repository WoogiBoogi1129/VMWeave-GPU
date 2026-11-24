# VMWeave v0.5.13: Worker의 HAMi 기본 제한 정책 명시

새 GPU Worker에 `GPU_CORE_UTILIZATION_POLICY=default`를 명시한다.
기존 예약 compute, VRAM, Guest/Worker ABI 및 GPU 선택은 유지한다.
실행 중 SM 한도 변경 기능은 배포 보류하며 API와 이미지에 포함하지 않는다.

## Helm과 이미지

```yaml
workloads:
  gpuCoreUtilizationPolicy: default
```

Operator가 이 값을 새 Worker Pod의 환경변수로 전달한다. Worker 이미지에도
같은 기본값을 포함한다. `force`와 `disable`은 명시적인 관리자 선택이며,
잘못된 정책 값은 chart와 controller가 거부한다. Operator chart는 0.5.13이다.

`default`는 HAMi 모니터의 경쟁 판단에 따라 제한을 적용하거나 완화한다.
설정만으로 모든 유휴 SM 활용, 정확한 이용률 또는 DRA 모니터 연동을 보증하지 않는다.
이번 변경은 정책 전달을 대상으로 하며 새로운 GPU 성능 주장을 하지 않는다.

## 적용 범위와 롤백

Helm upgrade는 중앙 Operator와 향후 Worker 생성 정책을 갱신한다.
이미 실행 중인 Worker를 재생성하지 않으므로 기존 프로세스 설정은 유지된다.
현재 Worker가 정책 미설정 상태이면 HAMi-core의 기본 정책을 이미 선택한다.
새 Worker 이미지는 공개 digest로 지정하여 새 Profile/Request에 사용한다.
기존 immutable Profile/Channel은 임의 수정하지 않는다.

이전 Helm revision과 이미지 digest로 복원할 수 있다. CRD 확장과
호스트 HAMi 라이브러리 교체는 필요하지 않다. Guest 바이너리 프로토콜을
변경하지 않아 기존 Device Plugin 패키지를 그대로 사용할 수 있다.
