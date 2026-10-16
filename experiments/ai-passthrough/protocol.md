# VMWeave와 passthrough AI 성능 비교 프로토콜

2026-10-16 실행 전 고정. 기준 main: `3f980b0f0706312c615e9ded4facac7bc2849e9f`.

- 동일 GPU 2 (`GPU-c654d43e-43f8-c28e-77c2-1f17a0cbf46a`, `0000:aa:00.0`)를 순차 사용한다. 기존 GPU 1 VM과 GPU 3 서비스는 유지한다.
- VMWeave는 기준 main에서 새로 빌드한 Guest/Worker와 수정 HAMi 라이브러리를 사용한다. Core 100, VRAM 8192 MiB. passthrough는 GPU 전체를 사용하며 동일 메모리 제한을 적용했다고 주장하지 않는다.
- 동일 Ubuntu 이미지, 8 vCPU, RAM 16 GiB, PyTorch 2.11.0+flyt.cu128, FP32 eager, TF32 off, SGD(lr=0.01, foreach=False, fused=False), ReLU/MSE. cuBLASLt 비활성화. AMP/compile/NCCL 범위 제외.
- MLP 32→64→8 및 2048→4096→1024 × batch 32/1024 × GPU resident/매 step CPU→GPU 전송 = 8조건. fixture는 한 번 생성한 파일을 양쪽에 복사하고 SHA256으로 확인한다.
- 정확성은 별도 실행에서 1/10/100 step의 loss, gradient, weight를 rtol=1e-4, atol=1e-6으로 비교한다. 실패 조건은 성능 정상 비교에서 제외하고 실패 자체를 보고한다. CPU fallback 금지.
- 성능은 조건마다 새 프로세스, 모드·블록마다 새 VM 부팅. warmup ≥30초, 측정 ≥120초, 측정 구간 양 끝 CUDA synchronize, step별 item/CPU copy/synchronize 금지. 시간은 완료까지의 wall clock, 처리량은 완료 step×batch/시간이다.
- 5 paired blocks, 모드 순서는 W/P, P/W, W/P, P/W, W/P. 블록마다 조건 순서를 순환하여 시간 편향을 줄인다. 목표 80측정. paired throughput ratio 및 개별 반복값, 평균·표준편차·95% CI를 보고한다. 작은 n과 불완전한 순서 균형을 명시한다.
- 주 비교: VM QEMU CPU 32–39, VMWeave Worker 40–43. Worker 추가 CPU를 숨기지 않고 host CPU-seconds/sample로 기록한다. 보조 비교는 총 CPU 예산을 같게 맞춰 수행한다.
- GPU utilization/VRAM/clocks/power/temperature와 CPU를 수집한다. VFIO 상태에서는 Guest nvidia-smi로 측정한다. Grafana·원시 CSV·그래프·실제 화면 캡처를 보존한다.
- GPU 전환 전 IOMMU 그룹, 장치 파일 FD, 실행 중 작업을 검사한다. 대상 GPU의 HAMi/DCGM 접근만 일시 중지하고 설정을 복원한다. 다른 GPU의 AI 프로세스를 중단해야 하는 상황에서는 전환을 강행하지 않는다.
- 성능 허용 오버헤드 임계값은 정하지 않았으므로 임의 PASS/FAIL을 부여하지 않는다. 실제 실행하지 못한 조건은 미측정으로 명시한다.

사전 점검에서 단일 프로세스 종료 시 VM을 종료하는 과거 `Allocation` harness를 발견했다. 정식 비교는 최신 `VM` lifecycle + Guest broker + session-worker로 수행한다. 이 변경은 본 측정 전에 적용하며 단일 작업 사전 점검은 별도 보존한다.

토폴로지 사전 확인: GPU 2의 NUMA node는 2이며 CPU 32–47이 로컬이다. 본 측정 Worker affinity는 기존 harness의 48–51(node 3) 대신 40–43(node 2)로 고정한다. 보조 비교는 passthrough에 12 vCPU/host CPU 32–43을 할당하여 VMWeave 8+4의 총 12 CPU 예산과 맞춘다.

사전 검사 추가(본 측정 전): 원래 large 모델의 첫 가중치 32 MiB 복사가 `FLYT_EXEC_MAX_COPY_BYTES=16 MiB`에 걸려 model.cuda()에서 invalid value로 실패했다. 원래 4개 large 조건을 별도 실패 검사로 유지하고, 중간 모델 1024→2048→512(최대 가중치 8 MiB) 4조건을 추가한다. 정확성을 통과한 small/medium에 같은 5-block 절차를 적용한다. 이 추가는 large 성능의 대체 추정치가 아니다.

총 CPU 예산 보조 측정은 small/batch32/resident와 medium/batch1024/resident 두 조건, 3 paired blocks(W/P, P/W, W/P)로 고정한다. VMWeave는 주 비교와 동일한 8+4 CPU, passthrough는 12 vCPU와 CPU 32–43을 사용한다. 이 보조 결과를 주 비교의 5-block 통계에 섞지 않는다.
