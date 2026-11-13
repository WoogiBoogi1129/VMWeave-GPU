# CNN 학습 지원 사전 진단

현재 SHM Guest/Worker를 변경하지 않고, VMWeave VM 하나에서 PyTorch CNN의 최초 실패 지점과
CPU 참조값을 수집한다. Passthrough 실행·성능 측정·cuDNN 중계 기능 구현은 이번 단계에 포함하지 않는다.

## 시험 계약

- 기존 전용 VM `vmweave-test-b/dp-dev-20261105`와 공개 Device Plugin을 사용한다.
- 공식 PyTorch·Guest 이미지는 이전 공식 이미지 검증의 `submitted.json`에 고정된 digest를 재사용한다.
  실제 제출 선언과 imageID를 결과에 기록한다. 기존 이미지·wheel·Worker 바이너리를 교체하지 않는다.
- `TORCH_CUDNN_V8_API_DISABLED=1`, `DISABLE_ADDMM_CUDA_LT=1`, FP32 eager, NCHW,
  TF32 off, deterministic, cuDNN benchmark off, CPU thread 1, seed 20261107.
- 입력 `[2,3,8,8]`, Conv2d 3→4, kernel3/stride1/padding1, bias 포함. 입력 gradient도 요구한다.
- CPU에서 forward 1회, Conv 학습 3 step, Conv–BatchNorm–ReLU 학습 3 step의 전체 tensor를 보존한다.
- GPU에서 기초 CUDA 연산을 확인하고 각 CNN 시험을 독립 Pod/process로 실행한다.
  각 GPU 시험에서도 동일 CPU 참조를 먼저 계산한다. GPU 결과가 생성되면 출력·loss·input/parameter
  gradient·갱신 parameter·BatchNorm buffer를 `rtol=1e-4, atol=1e-6`으로 비교한다.
- CPU는 참조이며 fallback이 아니다. forward 실패 뒤 backward/optimizer는 NOT_REACHED다.
- child timeout 120초, Pod deadline 240초. signal/오류/미도달 단계를 그대로 기록한다.
- 기본 실패 재현과 `LD_DEBUG=bindings` 진단을 별도 실행한다. loader binding은 심볼 해석 증거이며,
  binding 기록만으로 함수 실행·반환 성공을 주장하지 않는다.
- `cudnn-stream`은 필요할 때만 실행하는 분리된 최소 C API 재현이다. cuDNN handle과 CUDA 기본
  stream을 사용하며 native 충돌 가능성 때문에 별도 프로세스에서 수행한다.

## 실행

연결 JSON은 기존 `experiments/device-plugin-pytorch/README.md` 형식을 따른다. 자격증명은 `.local/`
등 Git 밖에 둔다. 신규 namespace와 runID는 `cnn-preflight-`로 시작해야 한다.

```sh
python3 experiments/cnn-preflight/runner/run.py --connection CONNECTION --results RESULTS prepare
python3 experiments/cnn-preflight/runner/run.py --connection CONNECTION --results RESULTS run --name cpu-reference --mode cpu --case all
python3 experiments/cnn-preflight/runner/run.py --connection CONNECTION --results RESULTS run --name gpu-basic --case basic
python3 experiments/cnn-preflight/runner/run.py --connection CONNECTION --results RESULTS run --name conv-forward --case conv-forward
python3 experiments/cnn-preflight/runner/run.py --connection CONNECTION --results RESULTS run --name conv-train --case conv-train
python3 experiments/cnn-preflight/runner/run.py --connection CONNECTION --results RESULTS run --name conv-bn --case conv-bn
```

실패 시 runner도 0이 아닌 코드로 종료한다. 결과 수집은 계속 가능하며 `collect --name NAME`으로
복구할 수 있다. 진단 실행에는 별도 이름과 `--loader-trace`를 사용한다. namespace와 Pod는
create-only이며 기존 실행을 덮어쓰지 않는다. GPU Pod는 순차 실행하고 기존 활성 GPU Pod가 있으면 거절한다.

supervisor는 child 종료 후 로그·CPU tensor·선택적 loader trace를 checksum과 함께 Pod 로그에 보존한다.
runner는 이를 검증해 파일로 복원한다. native signal은 PASS로 변환하지 않는다.
시험 시작 전 VM 상태를 보존하고, 끝나면 원래 Halted 상태와 Channel Stopped 복귀를 별도로 확인한다.

호출 추적은 `workloads/trace_stream.c`를 shared library로 빌드해 별도 immutable ConfigMap의
`binaryData.trace-stream.so`에 넣고, `--code-map NAME --stream-trace`로 실행한다.
2026-11-07에 사용한 ConfigMap 원문과 source/binary는 결과의 `sources/`에 있다.
새 실행에서는 namespace를 바꾸고 새 ConfigMap을 생성한다. 이 interposer는 호출을 기록한 뒤
원래 native 함수로 위임하는 진단 도구이며 VMWeave cuDNN 구현이 아니다.

## 구현 목록의 분류

보고서에서 실제 도달·실패 API, 심볼 해석 결과, 소스 분석상 후속 필요 API를 분리한다.
CPU 참조 성공이나 과거 RPC 검증을 현재 SHM의 CNN 성공으로 취급하지 않는다.

[2026-11-07 실제 결과](results/20261107/REPORT.md): CPU CNN 참조와 GPU 기초 연산은 통과했으며,
CNN은 원격 cuDNN handle의 native `cudnnSetStream` 전달에서 SIGSEGV가 발생했다.
후속 backward·BatchNorm GPU 검증은 미도달이다. 충돌 후 기초 연산 재사용과 원래 VM 상태 복귀를 확인했다.
