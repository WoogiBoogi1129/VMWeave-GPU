# 동일 VM의 legacy Conv2d forward 검증 — 2026-11-13

**결과: 후보의 공유메모리 경로에서 Conv2d forward 198건이 CPU 참조와 일치했다.**
기존 기본 cuBLASLt MLP 및 cuDNN LSTM의 5-step 학습 회귀도 통과했다.
저장한 원시 텐서 292개를 별도 CPU 프로세스에서 다시 검산했다.
후보는 공개 릴리스하지 않았으며 시험 VM은 공개 v0.5.9 구성으로 복원했다.

**범위 제한:** `TORCH_CUDNN_V8_API_DISABLED=1`을 명시한 legacy forward만 검증했다.
기본 cuDNN graph 경로는 후보에서도 첫 forward에서 SIGSEGV가 재현됐다.
CNN backward·BatchNorm·전체 CNN 학습이나 성능 개선을 검증한 결과가 아니다.

## 고정 조건

- 시험 VM: `vmweave-test-b/dp-dev-20261105`, VM UID 유지,
  GPU compute25%, VRAM1,024MiB, 단일 client. 다른 VM/Passthrough로 대체하지 않았다.
- 공식 PyTorch 이미지:
  `docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be`.
  실제 Pod imageID 확인, PyTorch `2.11.0+cu128`, Python3.12, Worker cuDNN9.8.
- FP32 contiguous NCHW `[2,3,8,8]`, Conv2d 3→4, kernel3, groups1, dilation1.
  bias on/off × stride1/2 × padding0/1 × deterministic on/off = 16설정.
  TF32 off, benchmark=False. 각 설정을 기본·명시적 stream에서 각각 3회 실행한다.
- seed20261113, 고정 허용오차 `rtol=1e-4`, `atol=1e-6`.
  CPU에서 동일 입력·파라미터로 참조를 계산하고 unfold+matmul 식으로도 점검했다.
  GPU 결과는 CUDA Tensor 및 grad_fn을 확인하고 CPU로 가져와 비교했다.
  CNN backward는 실행하지 않았다.
- 새 cuDNN 호출을 공유메모리 요청으로 중계한다. 전송 방식을 네트워크 RPC로 바꾸지 않았다.

## 결과

| 실행 | 결과 | 비교/관찰 |
|---|---|---|
| 공개 v0.5.9 CPU matrix | PASS | 공식 이미지 CPU 16설정 |
| 공개 v0.5.9 stream | PASS | 기본·명시적 stream set/get |
| 공개 v0.5.9 default Conv2d | SIGSEGV | 첫 forward, CPU 참조까지 정상 |
| 공개 v0.5.9 legacy Conv2d | SIGSEGV | 첫 forward, CPU 참조까지 정상 |
| 후보 stream | PASS | 기존 스트림 중계 유지 |
| 후보 최소 legacy forward | PASS | 6개 출력, 최대 절대오차 2.384185791e-7 |
| 후보 전체 matrix | PASS | 96개 출력, 최대 절대오차 3.576278687e-7 |
| 후보 matrix 새 Pod 재실행 | PASS | 96개 출력, 동일 오차 |
| 후보 기본 Lt MLP 5-step | PASS | 22개 출력·loss·gradient·갱신 파라미터, 최대 절대오차 4.284083843e-8 |
| 후보 기본 cuDNN LSTM 5-step | PASS | 36개 텐서, 최대 절대오차 3.516674042e-6 |
| 후보 LSTM 새 Pod 재실행 | PASS | 36개 텐서, 동일 오차 |
| 후보 default Conv2d | SIGSEGV | 기본 graph 경로는 미지원 |
| 후보 오류 후 GPU 기본 연산 | PASS | 새 client의 matmul 재사용 확인 |
| 공개 v0.5.9 복원 후 GPU 기본 연산 | PASS | 공개 Guest hash를 확인하고 실행 |

MLP/LSTM은 기존 `experiments/rnn-default`의 MNIST 입력과 CPU 검산 절차를 그대로
사용했다. default Lt와 cuDNN을 비활성화하지 않았다. LSTM의 최대 절대오차는 1e-6보다
크지만, 상대오차를 포함한 사전 기준 `atol + rtol*abs(reference)`를 모든 원소가 충족했다.

[Worker 로그](candidate-final-worker.log)에서 실제 `cudnnConvolutionForward`
(`api=13107`) 성공 198회를 확인했다. heuristic 조회 성공도 8회 기록됐다.
캐시는 같은 프로세스의 동일 convolution 조건에서 재사용되므로 heuristic 횟수는
forward 횟수와 다르다. 기록된 library API 중 nonzero 결과는 없었다.
default 경로의 Guest 비정상 종료를 Worker의 forward 성공으로 계산하지 않았다.

[독립 텐서 검산](tensor-audit.json)은 GPU 출력 198개와 MLP/LSTM 텐서 94개를
다시 읽어 비교했다. CNN CPU 참조도 입력과 state_dict에서 재계산했다.
이 별도 감사 프로세스만 로컬 `2.11.0+flyt.cu128`의 CPU 기능을 사용했다.
실제 VM 워크로드는 모두 위 공식 이미지다. 검산 환경을 GPU 실행 환경과 혼동하지 않는다.

## 실패 기록과 진단 경계

처음 후보 실행을 시도할 때 runner가 `status.image`의 로컬 태그를 digest 문자열과
직접 비교해 Pod 생성 전에 중단했다. `spec.containers[].image`와 실제 `status.imageID`를
container 이름으로 연결해 검증하도록 수정했다. 다른 digest, Ready=false, 다른 spec을
거부하는 검사도 통과했다. 최초 중단은 [preflight 기록](candidate-stream/preflight.json)에 남았다.

baseline 및 후보 default 경로의 실패를 삭제하거나 legacy 성공으로 대체하지 않았다.
loader trace는 symbol binding의 증거이며 단독으로 정확한 fault instruction을 증명하지
않는다. 확인한 사실은 stream 테스트 통과, 첫 Conv2d forward SIGSEGV, legacy 후보의
실제 Worker 실행·정확성 통과다. 기본 graph API 전체 지원으로 확대 해석하지 않는다.

## VM 복구

작업 시작 때 VM은 `runStrategy=Always`였지만 VMI Failed, Channel
`Draining/AwaitingDetachEvidence`였다. 2026-11-13 14:11:03 KST 노드 재부팅 후
launcher가 KVM 할당 오류로 실패했고, Kubernetes는 sandbox가 없다고 보고했다.
Guest attachment는 이전 실행의 Mapped 상태로 남아 있었다.

1. 시험 VM을 Halted로 두고 재실행을 막았다. VM·VMI·Channel·Attachment·Pod·PVC와
   보호할 control-plane VM의 원본을 캡처했다.
2. pinned 대상 UID/generation/allocation, 이전 Running 기록, 현재 boot ID/boot time,
   node Ready 및 reboot 이후 PodSandboxNotReady를 대조했다.
3. 해당 노드의 임시 hostPID 관찰 Pod가 할당 파일의 device/inode를 식별하고 전체
   프로세스의 mappings/FD와 대상 프로세스 identity를 검사했다. CRI sandbox/container도
   검사했으며 2회 관찰 모두 일치 항목과 검사 오류가 0이었다.
4. read-only 감사 및 9개 거부 조건 확인 후, 같은 검증을 다시 실행했다.
   controller service account를 사용하는 관찰자가 실제 관찰 근거 hash와 boot ID를
   `VerifiedNodeRebootNoMappings` 증거로 Guest attachment의 Detached 상태에 기록했다.
   일반 controller가 이후 finalizer 해제, VMI 정리, 회수, Stopped 전환을 수행했다.
5. VM을 다시 시작해 Running/Ready 및 Device Plugin Ready를 확인했다.

이는 증거 없는 상태 조작이 아닌 **일회성 관리자 관찰 기반 복구**다. finalizer 직접 삭제,
PVC/SHM 파일 수동 삭제, admission 우회, 다른 Draining 채널 수정은 하지 않았다.
자동 재부팅 복구 정책을 새로 배포한 것은 아니다. 증거는
[읽기 전용 감사](recovery/read-only-audit.log), [최종 attestation](recovery/attestation.log),
[회수된 Channel](recovery/reclaimed-channel.json)에 있다.

## 후보 적용과 복원

후보 Guest는 Pod의 별도 immutable ConfigMap으로 주입했고, SHA256 검사 후 사용했다.
설치된 broker/Device Plugin은 공개 버전을 유지했다. Worker는 동일 소스 빌드의 pinned
후보 이미지로 별도 승인 Profile/Request를 만들고, 정상 종료·회수 후 Channel을 재생성했다.
[후보 식별자](candidate-artifact-identity.json)와 [Worker 바이너리 hash](candidate-worker-binaries.txt)를 보존했다.

검증 후 같은 정상 종료·회수 절차로 공개 v0.5.9 Worker와 원래 Profile/Request 참조를
복원했다. 공개 Guest hash로 GPU 기본 연산이 통과한 뒤 실험 namespace 두 개,
임시 관찰/build Pod 및 후보 Profile/Request를 삭제했다.

[복원 검증](restoration.json)은 원래 VM UID/spec, Channel spec, Profile/Request/PVC
UID/spec, Plugin values와 보호 대상 control-plane VM/VMI를 비교한다.
Channel UID·allocation·generation 및 cloud-init layout marker는 정상 재연결로 변경된다.
최종 VM은 원래 의도한 Always/Running/Ready이며, 실패했던 시작 상태를 재현하지 않는다.

## 다음 단계

이번 단계의 forward 검증은 완료했다. 다음 CNN 학습 단계에는 legacy
`cudnnConvolutionBackwardData`와 `cudnnConvolutionBackwardFilter` 경로, 입력·가중치·bias
gradient 및 optimizer 갱신의 CPU 비교가 필요하다. BatchNorm과 기본 cuDNN graph 경로는
별도 확장 범위로 유지한다. 이 결과를 학습 처리량이나 실제 모델 규모의 성능 비교로
인용해서는 안 된다.
