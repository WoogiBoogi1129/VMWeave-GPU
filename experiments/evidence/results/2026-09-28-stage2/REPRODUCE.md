# 2단계 재현 및 오프라인 검증

저장소 루트 기준이다. 공개 원본 검사는 GPU·클러스터 없이 Python 표준 라이브러리로 가능하다.

```sh
python3 experiments/evidence/summarize_stage2.py experiments/evidence/results/2026-09-28-stage2
python3 -m unittest discover -s tests/control -p test_stage2_evidence.py -v
cd experiments/evidence/results/2026-09-28-stage2
sha256sum -c SHA256SUMS
```

`verify_stage2.py`는 같은 allocation/generation/session/request ID의 네 레코드, API·입력 크기,
응답 상태·결과 도메인·크기, endpoint 내부 순서, 연속 ID, 예상 호출 순서를 검사한다.
1 MiB의 할당 handle을 H2D·D2H·free에서 대조한다. `output.bin.gz`를 풀어 seed로
다시 생성한 262,144개 CPU 기준값과 전수 비교하고 입력·기준·출력 SHA-256도 확인한다.
Worker 시계에 일정 offset을 주어도 판정이 같아야 하며 두 시스템 사이의 지연은 산출하지 않는다.

## 실제 GPU 재실행

현재 환경용 실행기다. 기존 `flyt-evidence` 제어기·HAMi·ivshmem launcher,
해제된 `evidence-vm-a-backing` PVC, 기존 `evidence-c28-affinity` host-PID helper,
`.local/evidence-20260924/images.json`의 control/hook 이미지가 필요하다.
이름이 다른 새 `--prefix`와 비어 있는 출력 경로를 사용한다. 공유 PVC에 미해제 채널이 있으면 진행하지 않는다.
기존 전체 캠페인 실행기는 호출하지 않는다.

1. 공개 커밋의 소스를 별도 context에 복사하고 [실제 Containerfile](build/Stage2.Containerfile)로
   `build`, `worker` target을 빌드한다. 실제 빌드의 control_plane.py는 당시 HEAD 버전이었다.
   기존 로컬 control_plane.py 수정본은 빌드 context에서 제외했다. 이 Worker 이미지만
   `ENV FLYT_TRACE_REQUESTS=1`이며 일반 Containerfile/소스 기본값은 trace OFF다.
2. build 이미지의 `/opt/flyt/lib/libflyt_guest.so`를 새 private `artifacts/`에 복사한다.
   같은 이미지 안에서 다음 명령으로 probe를 빌드한다.

```sh
gcc -O2 -I/usr/local/cuda/include experiments/evidence/stage2_probe.c \
  -L/opt/flyt/lib -lflyt_guest -Wl,-rpath,/tmp/campaign -o artifacts/stage2-probe
```

3. 새 Worker를 OCI archive로 저장하고 `scripts/import-evidence-image.py`로 CRI-O에 가져온다.
   import는 해당 archive 하나를 가져오는 임시 node 관리 Pod를 생성하고 삭제한다.
   출력의 manifest digest를 다음 `--worker-image`에 사용한다. 이번 실제 digest는
   [worker-image.json](build/worker-image.json)에 있다.
4. private `artifacts/`에 Guest SSH key/public key와 기존 `campaign-probe-guest`,
   `campaign-probe-native`를 실행 권한을 보존해 준비한다. 두 campaign binary는 공통 준비 도구의
   호환성 때문에 필요하며 2단계에서는 실행하지 않는다. 실제 프로그램은 `stage2-probe`뿐이다.
5. 별도 터미널에서 캡처를 먼저 시작하고 runner를 실행한다.

```sh
NODE_PATH="$PWD/.local/evidence-20260924/tools/node_modules" \
  node scripts/capture-stage2.cjs .local/STAGE2-NEW/captures
python3 experiments/evidence/run_stage2.py \
  --base .local/STAGE2-NEW --output .local/STAGE2-NEW/public \
  --prefix evidence-s2-NEW \
  --worker-image localhost/flyt-worker@sha256:ACTUAL_MANIFEST_DIGEST
```

`NEW`는 소문자·숫자의 고유 이름으로 바꾼다. runner는 3개 VM을 순차 준비·실행·UID 확인 후 drain한다.
Guest 8 vCPU/16 GiB, Worker CPU 16–19, Guest CPU 0–7, GPU 1의 고정 UUID,
메모리 설정 4096 MiB/compute 50/1 session을 사용한다. Guest에 복사하는 library와 probe의
SHA-256 및 실행 명령을 회차마다 저장한다. 설치된 libvgpu 실제 해시·환경도 따로 보존한다.
실시간 viewer는 `127.0.0.1:9899`의 `/`, `/state.json`만 제공하며 private key/VM cloud-init을 노출하지 않는다.

## 호스트 회귀 검사 실행 메모

이번 build 이미지에는 Python과 실행 가능한 `libcuda.so.1`이 없다. 첫 전체 스크립트는
Driver 라이브러리 탐색에서 중단됐고, stub SONAME을 연결한 재실행은 C 검사 5개 통과 후
Python 부재에서 중단됐다. 이 초기 로그도 `build/`에 보존했다. 이어서 Python이 있는 새
Worker 이미지에서 layout 검사 6개를 root로 실행해 전부 통과했다. 이들은 GPU 기능 실험과 별도다.

```sh
# build 이미지 내부: 실제 GPU 호출을 mock하는 C 회귀 검사에만 stub 사용
mkdir -p /tmp/cuda-stub
ln -s /usr/local/cuda/lib64/stubs/libcuda.so /tmp/cuda-stub/libcuda.so.1
export LD_LIBRARY_PATH=/tmp/cuda-stub:/usr/local/cuda/lib64
bash scripts/test-shm-training.sh /build
# 위 이미지에 Python이 없으면 마지막 layout 검사는 Python이 있는 Worker 이미지에서 분리
FLYT_GUEST_LIBRARY=/art/libflyt_guest.so python3 tests/integration/layout_permissions.py -v
```

실제 VM 실험 Worker에서는 호스트 NVIDIA Driver 580.173.02를 사용했다. stub을 GPU 실험에
주입하지 않았으며 로드된 라이브러리 경로·해시는 각 `runtime-libraries.json`에서 확인한다.
