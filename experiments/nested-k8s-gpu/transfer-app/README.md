# 전송·Rodinia 추가 측정 도구

[결과·측정 경계](../results/20261030-transfer-app-throughput/REPORT.md) ·
[사전 계획](../results/20261030-transfer-app-throughput/PLAN.md)

## 오프라인 재계산

저장소 루트에서 실행한다. 클러스터 접속이나 GPU 실행은 없다.

```bash
python3 experiments/nested-k8s-gpu/transfer-app/analyze.py --no-plots
```

`summary.json` 및 CSV를 재계산한다. 원본을 보존하려면 결과 디렉터리 복사본을
`--out /path/to/copy`로 지정한다. 그래프를 생성할 때는 matplotlib가 필요하며
`--no-plots`를 생략한다. 원시 표본, 검산, GPU PID 대응, 세션 회수, Pod 성공,
Channel 동일성 및 대상 GPU의 다른 프로세스 관측 여부를 함께 검증한다.

## GPU 실행 도구의 범위

`run.py`는 유지 중인 실험 환경과 2026-10-30의 경로에 고정되어 있다.
`prepare`와 `run`을 구분하고, 기존 `started.json`이 있으면 재실행을 거부한다.
`--uploaded`는 GPU 측정 전 준비 실패만 복구하는 옵션이며 측정 재시도 옵션이 아니다.
새 실험에는 결과 디렉터리·Guest 경로·이미지 tag·Job 이름을 새로 정해야 한다.
공유 broker는 한 세션씩 사용한다. 기존 결과를 지워 재실행하지 않는다.

실행 전 [인계 문서](../results/20261028-minimal/HANDOFF.md)에 따라 실제 환경과 권한을 확인한다.
SSH 키·known_hosts는 git 밖 `.local/nested-k8s-20261028/`에 있다. 준비 도구는
기존 [SGEMM runner](../throughput/run.py)의 조회·SSH·관측·GPU monitor 함수를 재사용한다.
제품 controller/webhook/broker/Guest 라이브러리를 빌드하거나 교체하지 않는다.

준비 환경에는 다음 입력이 필요하다.

- Guest의 gcc, Podman, 기존 Ubuntu 22.04 base image와 `/opt/vmweave/lib/libvmweave_guest.so`.
- `.local/rodinia-steady-20261026/nw`와 `srad`: 기존
  [동결 소스](../../ai-passthrough/results/20261026-rodinia-steady/src/) 및
  [CUDA 12.8 재빌드 도구](../../ai-passthrough/results/20261026-rodinia-steady/reproduction/build.py).
  준비 시 [당시 manifest](../../ai-passthrough/results/20261026-rodinia-steady/manifest.json)의 바이너리 해시와 일치해야 한다.
  다른 툴체인으로 재빌드한 경우 새 qualification과 별도 결과를 사용해야 한다.
- `.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs/libcudart.so.12`.
  실행에 사용한 해시는 결과의 `inventory/binary-library.sha256`에 있다.
  NVIDIA 런타임과 개인 환경 파일은 이 문서 묶음에 포함하지 않는다.

따라서 새 clone만으로 해당 날짜의 GPU 재실행이 즉시 가능하다는 뜻은 아니다.
오프라인 검산에 필요한 자료는 모두 저장소에 포함한다.

## 소스 및 계측

- `copy.c`: pageable buffer, 각 방향의 copy+device-sync 완료 측정. 할당·검산 제외.
  각 구간 마지막 출력 전체를 입력과 비교하며 매 복사마다 검산한 것은 아니다.
- `barrier.c`: Rodinia 최초 cudaMalloc 뒤 관측을 위해 정지. 이후 호출은 cached
  RTLD_NEXT 함수로 전달한다. Guest와 Pod에 같은 shim을 적용한다.
  Rodinia 원시 `EXPERIMENT_INIT`에는 이 대기 시간이 포함되어 있어 초기화 성능에 사용하지 않는다.
- `Containerfile`: 같은 바이너리·Guest 라이브러리를 Pod 안에 복사. 소켓은 Guest에서 mount.
- `analyze.py`: 전송 p50은 실행 내 중앙값, p95는 nearest-rank 95백분위수.
  최종 표는 독립 실행 3개의 해당 지표 중앙값이다. 반복 복사를 독립 프로세스 표본으로 세지 않는다.

Rodinia 알고리즘은 변경하지 않았다. 출처·라이선스와 과거 SRAD 경계 보완 내역은
[Rodinia 결과](../../ai-passthrough/results/20261026-rodinia-steady/README.md) 및
[라이선스](../../ai-passthrough/results/20261026-rodinia-steady/RODINIA-LICENSE)에 있다.
