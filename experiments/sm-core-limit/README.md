# VMWeave SM Core 제한 수정 검증

기준일: 2026-10-15 KST. 배포 여부와 최종 수치는 [report.md](report.md), 원시 결과는 [evidence](evidence/)에 기록한다.

## 25/50/75% 추가 반복 실험

추가 결과는 [limit-validation.md](limit-validation.md)에 별도로 정리한다. 각 제한률에서 새 VM/Worker로 3회씩, 회당 150초(준비 30초) 실행한다. 후보는 `idle-reset`, 정책은 FORCE, GPU는 유휴 GPU 2다. 실행 순서는 25/50/75 → 75/50/25 → 50/25/75다.

```bash
# 위 카나리 이미지, helper 및 로컬 빌드 산출물 준비 후 실행
python3 experiments/sm-core-limit/runner/validate_limits.py
# matplotlib가 설치된 Python 환경에서 실행
python3 experiments/sm-core-limit/runner/analyze_limits.py
```

`SM_TEST_OUT`으로 단일 VM 실행기의 기록 위치를 지정할 수 있다. 반복 실행기는 관리 명령 감사 로그를 `.local`에 보관하고, 결과·시계열·실제 라이브러리 SHA·자원 회수 기록을 공개 evidence 디렉터리로 복사한다. 완료된 실행이 있으면 덮어쓰지 않는다.

## 변경 후보

현재 설치 HAMi v2.10.0의 HAMi-core 기준 커밋은 `b216ba1be1b8e21488d1c7370ed3357b3049aad1`이다. 설치 라이브러리 SHA-256은 `e98badc7ab64065af728fcca833ed372f16702d1e1c18eec01b1d8f6cbf7a9fb`이며 실행 중인 기존 Worker에서도 확인했다.

- `original`: 위 커밋을 실험 도구체인으로 재빌드한 대조군. 설치 바이너리와 빌드 옵션이 같다고 주장하지 않는다.
- `patched`: [0001](patches/0001-linear-sm-gain.patch). `delta()`의 SM² 비례 보정량을 SM 비례로 변경하고 풀 계산을 `int64_t`로 승격한다.
- `idle-reset`: [0002](patches/0002-linear-sm-gain-with-idle-reset.patch). **0001 적용 전 기준 커밋에 적용하는 대체 패치**다. 선형 보정과 함께, 커널 호출/대기가 1초 넘게 없고 측정 사용률이 0이면 누적 토큰과 share를 초기화한다. 최초 커널 이전에도 적립하지 않는다. limiter에서 대기 중인 호출은 활동 시각을 갱신하여 유휴 상태와 구분한다. 이 추가 변경은 이번 VMWeave 실험에서 도출한 후보이며 업스트림 PR의 내용이 아니다.

업스트림 근거: [이슈 #274](https://github.com/Project-HAMi/HAMi-core/issues/274), [PR #286](https://github.com/Project-HAMi/HAMi-core/pull/286). PR은 기여 지침 사유로 **미병합 종료**되었다. 정식 릴리스 수정으로 간주하지 않는다.

## 재현

저장소 루트에서 실행한다. CUDA 12.8 및 gcc/CMake가 있는 로컬 빌드 이미지 digest는 `runner/build.sh`에 고정되어 있다. 다른 환경에서는 `SM_BUILD_IMAGE`를 명시하고 도구체인 차이를 기록해야 한다.

```bash
bash experiments/sm-core-limit/runner/build.sh
python3 experiments/sm-core-limit/runner/test_delta.py
python3 experiments/sm-core-limit/runner/test_activity.py
python3 experiments/sm-core-limit/runner/native.py \
  --name new-run --variants original,patched --limits 25,50,75,100 \
  --seconds 270 --warmup 30 --reps 1048576 --repeat 3
python3 experiments/sm-core-limit/runner/analyze.py
```

Native 실행기는 GPU 0 UUID를 고정하고 다른 GPU 프로세스가 있으면 실행을 거부한다. 각 조건은 독립된 프로세스와 HAMi 캐시를 사용한다. `--reps 8192`는 짧은 커널, `--reps 1048576`은 기존 실험과 같은 긴 커널이다. CUDA driver API, grid 2048, block 256, 커널별 동기화를 사용한다. 30초 준비 후 처리량을 계산하며 장치 사용률은 초기화 영향을 줄이기 위해 실행기 시작 32초 이후 표본을 요약한다. 이 두 시간축은 완전히 동일하지 않으므로 원시 값도 보존한다.

## VMWeave 카나리

`Worker.Containerfile`은 현재 Worker 바이너리를 그대로 보존하고 실행 전 gate만 추가한다. 기존 이미지 OCI history에 누락이 있어 카나리 빌드 시 history 메타데이터를 정규화했으며 파일시스템 레이어는 유지했다. `runner/vmweave.py`는 기존 allocation 수명주기 실행기를 재사용한다.

정규화는 `python3 experiments/sm-core-limit/runner/normalize_oci.py <원본 OCI> <새 OCI>`로 재현한다. 새 OCI를 시험 노드 이미지 저장소에 import한 뒤 확인한 digest를 `podman build --build-arg WORKER_BASE=<정규화한 이미지 digest> -f experiments/sm-core-limit/Worker.Containerfile experiments/sm-core-limit`에 전달한다. 원본 이미지 provenance와 정규화 manifest는 `evidence/build.json`에 기록되어 있다.

1. 전용 GPUProfile, VM, PV/PVC, SharedMemoryChannel을 생성한다.
2. 새 Worker가 gate에서 대기하는 동안, **그 Pod의 mount namespace에만** 후보 `libvgpu.so`를 읽기 전용 bind mount한다.
3. 라이브러리 SHA를 확인한 뒤 gate를 해제한다. `LD_PRELOAD` 중복 로딩을 사용하지 않는다.
4. Guest → SHM → Worker → HAMi → GPU 경로로 동일 연산을 실행한다. Guest context는 Worker가 관리하므로 Guest probe에서는 runtime 초기화를 사용한다.
5. controller가 detach 및 backing 회수를 완료한 `Released` 상태를 확인한 후 시험 VM/Channel/PVC/PV를 삭제한다.

이 절차는 실험 전용이다. 관리자 helper와 로컬 이미지가 필요하며, 전역 HAMi 파일이나 기존 Worker는 교체하지 않는다. `SM_TEST_GPU`로 명시한 유휴 GPU에서 실행한다. 정식 배포에는 검증을 마친 라이브러리를 포함하는 HAMi 이미지와 버전 고정, 새로운 Worker 생성 및 SHA 검증 절차가 필요하다. 여기의 gate 이미지와 관리자 mount 절차를 운영 배포 방식으로 사용하지 않는다.

## 판정

설정 전달, 실제 라이브러리 로딩, limiter 활성화, 사용률, 완료 처리량을 분리해 확인한다. 제한 100의 처리량 회귀와 메모리 quota도 비교한다. `analysis.json`의 평균 ±5%p는 최초 계획에서 제안한 기준이며 HAMi의 공식 보장 수치가 아니다.

단일 반복 예비 시험은 3회 반복·장시간·다중 VM·유휴 후 재개 전체 검증을 대체하지 않는다. 예비 단계가 기준에 미달하면 전역 배포를 수행하지 않는다. 토큰 기반 커널 제출 제한은 물리 SM 전용 할당이나 커널 선점을 제공하지 않는다.
