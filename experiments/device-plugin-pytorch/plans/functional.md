# 공식 PyTorch 이미지 + VMWeave Device Plugin 기능 검증

사용자 승인 범위: 공식 이미지의 GPU 연산·작은 학습·정상/강제 종료 회수·후속 Pod 재사용.
성능 벤치마크, 처리량, Guest/Pod 성능 비교, nested HAMi, 다중 CUDA client는 제외한다.

## 고정 조건

- 공식 이미지: `docker.io/pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime`.
- amd64 digest: `sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be`.
- 선택 근거: 기존 실행 경로와 CUDA 12.8 및 PyTorch 2.11 계열을 맞추되 공식 배포물을 직접 사용.
- Guest package: Device Plugin v0.1.0 공개 이미지, library SHA256 `32bf53906f6cd4fd681c7af9068aad6274ea8c972c31e57d5efaf009e74e1bc5`.
- 시험 VM: `vmweave-test-b/dp-dev-20261105`, 내부 namespace `dp-torch-20261106`.
- GPU quota compute 25%, VRAM 1024 MiB를 우선 유지하고 관측값을 기록. GID 998, non-root UID 1000.
- 기존 Plugin·Broker·Worker 유지. 공식 PyTorch·CUDA 파일과 wheel은 교체하지 않는다.
- initContainer가 Guest library와 `libcuda.so.1` alias를 emptyDir에 준비. workload는 읽기 전용 mount.
- `LD_PRELOAD`, adapter library 탐색 경로, `VMWEAVE_MIRROR_DEVICE_VA=1`을 연결 조건으로 명시한다.
  Mirror VA는 ATen kernel 인자 내부 device pointer 전달에 필요한 기존 VMWeave 설정이다.
- GPU socket/env는 Device Plugin이 할당 시 주입한다. workload에 broker hostPath를 직접 선언하지 않는다.

## 판정 단계

1. 이미지·파일 식별, PyTorch import, CPU 참조 계산.
2. CUDA 인식·할당·H2D/D2H·덧셈·matmul 전체 출력 검증.
3. FP32 MLP 32→64→8, batch 32, MSE, SGD lr 0.01, seed 20261106, 5 step.
4. step 1/5의 전체 loss/output/weight/gradient를 CPU 참조와 `rtol=1e-4`, `atol=1e-6`으로 비교.
   finite, gradient 생성, 파라미터 갱신을 확인한다. 수렴·성능은 판정하지 않는다.
5. A 실행 중 B Pending, A 종료 뒤 B 성공, 세션 회수. 추가 SIGKILL 후 후속 Pod 성공.
6. 원본 로그·API JSON·실제 터미널 PNG·checksum·VM 종료 기록 보존.

기본 프로파일은 공식 PyTorch의 SGD 기본 실행 경로를 사용한다. FP32 검산을 위해 TF32를 끄고
CPU thread 1 및 `CUBLAS_WORKSPACE_CONFIG=:4096:8`을 고정한다.
별도 compat 프로파일은 필요할 때만 `DISABLE_ADDMM_CUDA_LT=1`, SGD `foreach=False, fused=False`를 적용한다.
이때 기본 프로파일과 결과를 분리한다. 허용 오차를 사후 완화하지 않는다.

## 중단 기준

CUDA 연결/연산이 실패하면 그 이후 학습·GPU 재사용 성공을 주장하지 않는다.
CPU 자동 fallback, 수정 wheel 교체, 성공할 때까지 태그 변경을 하지 않는다.
준비 오류는 수정 후 원본 실패를 보존하고 재시도한다. runtime 미지원은 최소 재현과 별도 개선 항목으로 남긴다.
실험 끝에는 시험 VM을 정상 Halt하고 Channel Stopped를 확인한다. 기존 사용자 자원은 변경하지 않는다.
