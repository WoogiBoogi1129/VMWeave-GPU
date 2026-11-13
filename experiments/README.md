# 실험 실행과 증거

현재 [실험·평가 문서](../docs/evaluation/index.md)에서 목적별 결과를 찾을 수 있습니다.

| 영역 | 디렉터리·진입점 |
|---|---|
| CNN 단계별 학습 검증 | [사전 진단](cnn-preflight/README.md), [Conv2d forward](cnn-forward/README.md), [backward·SGD](cnn-training/README.md), [작은 CNN·MNIST 일부](cnn-model/README.md) |
| 기본 라이브러리 경로 학습 | [LSTM 학습·정확성·체크포인트 검증](rnn-default/README.md) |
| 학습·애플리케이션 비교 | [training-threeway](training-threeway/README.md), [ai-passthrough](ai-passthrough/README.md), [pytorch-smoke](pytorch-smoke/README.md) |
| VM 내부 Kubernetes | [공식 PyTorch·Device Plugin](device-plugin-pytorch/README.md), [nested-k8s-gpu](nested-k8s-gpu/README.md), [초기 k8s-gpu-pod](k8s-gpu-pod/) |
| 자원 제한·격리 | [thesis-isolation](thesis-isolation/README.md), [vram-accounting](vram-accounting/README.md), [sm-core-limit](sm-core-limit/README.md) |
| 성능·진단 실행 도구 | [performance](performance/README.md), [system-comparison](system-comparison/README.md), [shm-first-bundle](shm-first-bundle/README.md), [h2d-diagnosis](h2d-diagnosis/), [diagnostics](diagnostics/) |
| 공통 증거·제어기 검증 | [evidence](evidence/README.md), [operator](operator/), [dra-smoke](dra-smoke/README.md) |
| SHM 단계별 계약 이력 | [channel-controller](channel-controller/README.md), [vm-shm-channel](vm-shm-channel/README.md), [shm-cuda-core](shm-cuda-core/README.md), [shm-async](shm-async/README.md), [shm-compatibility](shm-compatibility/README.md), [shm-lifecycle](shm-lifecycle/README.md), [rpc-removal](rpc-removal/README.md) |

현재 빌드의 계약·큐·CUDA dispatcher는 `runtime/shm/`, 배포용 smoke는 `tools/guest-smoke/`에 있다.
새 campaign은 [새 실험 자료 규칙](../docs/evaluation/experiment-layout.md)을 따른다.
과거 링크는 [경로 안내](../docs/history/link-map.md), 전체 결과는 [증거 색인](../docs/evaluation/catalog.md)을 확인한다.

기존 결과의 내부 경로·해시·성공/실패 내역을 보존합니다.
새 재실행은 새 결과 디렉터리를 사용합니다.

- [2026-10-12~13 VRAM 할당량 및 성능 경합 결과](thesis-isolation/report.md)
- [2026-10-16~17 VMWeave와 passthrough VM의 동일 FP32 학습 성능 비교](ai-passthrough/README.md)
- [2026-10-28 VM 내부 2노드 Kubernetes·GPU Pod 결과·캡처 및 향후 중앙 Operator 실습](nested-k8s-gpu/README.md)
- [2026-10-29 Guest/Pod SGEMM 처리량](nested-k8s-gpu/results/20261029-sgemm-throughput/REPORT.md) · [VMWeave·Flyt·Passthrough 기존 결과 비교](nested-k8s-gpu/results/20261029-performance-comparison/REPORT.md)
- [2026-10-30 내부 Kubernetes 전송 지연·대역폭 및 Rodinia 처리량 통합 보고서](nested-k8s-gpu/results/20261030-transfer-app-throughput/REPORT.md)

- [2026-11-02~03 VMWeave·Flyt·Passthrough 학습 비교](training-threeway/results/20261102/REPORT.md)

- [2026-11-06 공식 PyTorch 이미지·Device Plugin 기능 검증과 실제 캡처](device-plugin-pytorch/results/20261106-official/REPORT.md)
