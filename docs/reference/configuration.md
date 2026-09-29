# Kubernetes 리소스와 설정

현재 설치의 기준은 Helm chart와 SHM CRD입니다.

| 리소스 | 역할 |
|---|---|
| `FlytGPUProfile` | 승인 GPU와 Worker 이미지·자원 상한 |
| `FlytGPURequest` | VM UID와 요청 자원 참조 |
| `FlytSharedMemoryChannel` | VM·요청·PVC·이미지·세션·drain 설정 |
| `FlytChannelAttachment` | 매핑과 해제의 증거 |

[CRD 원본](../../deploy/shm/) · [Helm chart](../../charts/flyt-control-plane/)

## 주요 Helm 설정

| 값 | 의미 |
|---|---|
| `mode` | 기본값 `review`; active는 실험용 |
| `activeModeAcknowledged` | active 사용의 명시적 설정 |
| `image.repository`, `image.digest` | 제어기 이미지와 불변 digest |
| `imagePullSecrets` | registry 인증 참조 |
| `tls.existingSecret`, `tls.caBundle` | admission TLS |
| `controller`, `webhook` | 배치·자원·운영 설정 |

전체 필드와 제약은 [values.yaml](../../charts/flyt-control-plane/values.yaml)과
[values.schema.json](../../charts/flyt-control-plane/values.schema.json)을 따릅니다.
`deploy/shm`와 chart에 복제된 CRD는 `make check-layout`에서 일치 여부를 검사합니다.

## 호환성

현재 CRD group/version, 환경변수, 이미지 이름은 `flyt` 식별자를 유지합니다.
이전 RPC CRD와 현재 SHM CRD의 공존 migration은 구현된 것으로 간주하지 않습니다.
기존 RPC 클러스터를 덮어쓰지 말고 독립 환경 또는 별도 migration 계획을 사용합니다.
