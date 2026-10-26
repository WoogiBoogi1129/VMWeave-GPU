# Flyt–PyTorch 호환성 복구 계획

상태: 2026-10-26 사용자 승인 후 실행. 독립 Flyt 시험 빌드의 V1~V6 호환성 검증을 완료했고, 새 VM 쌍 10개로 후속 처리량 본실험 30구간을 완료했다. 기존 VMWeave 패키징은 보존한다. 아래는 승인된 계획이며 실제 결과와 제한은 말미 및 복구 보고서에 기록한다.

## 1. 목표와 변경 금지 조건

기존 성능 실험의 Python 3.10.12 / PyTorch 2.11.0+flyt.cu128 / CUDA 12.8과 동일한 MLP를 Flyt SHM/MPS 경로에서 실행하도록 호환성을 복구한다. 복구 후 승인된 처리량 실험을 재개하고 결과를 별도 캠페인으로 게시한다.

**기존 VMWeave 패키징 자료는 수정·삭제·덮어쓰기하지 않는다.** 보존 대상은 다음을 포함하며 아래 목록으로 한정하지 않는다.

- `runtime/shm/`, VMWeave 패키지/배포/설치 스크립트, `deploy/releases/`, 기존 릴리스 manifest 및 이미지 digest.
- `.local/thesis-isolation-20261012/guest-python-cuda.tgz`, `bundle-stage/`, 기존 Guest/Worker 패키지·이미지·빌드 캐시 및 보관 바이너리.
- `experiments/thesis-isolation/config/e2-environment.json`과 기존 결과·실행기·증거, 기존 Flyt Rodinia 패키지와 소스 작업 트리.
- 운영 VM의 패키지, 서비스, 환경변수, 시스템 라이브러리, 심볼릭 링크, 컨테이너 이미지 태그와 저장소의 기존 미커밋 변경.

이 작업에서 VMWeave 구현을 변경하거나 기존 패키지를 다시 빌드해 대체하지 않는다. 이름에 `flyt`가 들어 있는 기존 번들도 기존 실험의 기준 패키지이므로 보존한다. 새 Flyt 시험 산출물만 독립 경로에 추가한다.

## 2. 현재 증거와 미확인 사항

[실패 보고서](../evidence/20261026-flyt-mps-comparison/REPORT.md)를 기준으로 한다.

| 구분 | 확인된 내용 | 아직 확정하지 못한 내용 |
|---|---|---|
| Runtime 대체 방식 | PyTorch import가 `cudaGetDriverEntryPointByVersion`, version `libcudart.so.12` 심볼 부재로 실패. Flyt 클라이언트에서 해당 export가 발견되지 않음 | 이 API 하나를 추가하면 전체 MLP가 실행되는지 |
| 실제 runtime + Flyt preload | A 재사용 백엔드와 B 새 백엔드에서 각각 40초 초기화 timeout, 출력 0바이트 | timeout의 내부 원인과 정지 위치 |
| 정적 코드 | Flyt `init_rpc` constructor, `dlopen` 가로채기, `cuGetProcAddress` 계열 및 PCI 탐색용 `popen` 경로 존재 | 재진입·자식 프로세스 preload 상속·IPC 대기가 실제 timeout을 유발했는지 |
| VMWeave 참고 코드 | `guest_torch.c`에 진입점 조회 구현, `guest_compat.c`에 Driver 조회 구현 존재 | Flyt의 심볼 테이블·ABI·원격 처리에 그대로 적용 가능한지 |

VMWeave 코드는 동작 이해를 위한 읽기 전용 참고다. VMWeave 라이브러리를 Flyt 프로세스에 섞어 성공시키거나 Flyt 측정으로 보고하지 않는다. 다른 PyTorch 버전으로 낮추거나 모델을 바꾸는 것도 기본 해결안에 포함하지 않는다.

## 3. 보존과 작업 격리

### 3.1 사전 기준선

- 기존 Git HEAD, index/worktree diff, untracked 목록을 기록한다. 기존 변경을 stash/reset/clean하지 않는다.
- 기준 번들 SHA256을 `e2-environment.json`의 `d242f281efa068996e4c9893811d64b32a7965faaf16b58bc93cb957d78841ec`와 대조한다. 불일치하면 현재 값을 보존·보고하며 기준 파일을 고쳐 맞추지 않는다.
- 읽거나 복제할 패키지·라이브러리·소스의 파일 목록과 해시, 사용할 기존 이미지의 tag→digest를 기록한다. 전후 보존 감사에 사용할 보호 범위를 확정한다.

### 3.2 새 경로만 사용

- 저장소 변경은 최신 main에서 만든 별도 작업 브랜치/worktree에서 수행한다. 실행 당시 쓰인 로컬 Flyt 소스의 수정 내역까지 보존한 독립 복사본을 만들어 패치한다. 커밋 ID만으로 기존 빌드를 재현했다고 가정하지 않는다.
- 예시 작업 경로: `.local/flyt-compatibility-<실행ID>/{source,build,packages,logs}`. 기존 소스/번들은 읽기 전용으로 마운트하거나 별도 복사본을 사용한다. **쓰기 가능한 hardlink 복제는 금지**한다.
- 시험 VM 내부는 `/opt/flyt-compat/<실행ID>/`를 사용한다. 기준 Python/CUDA 번들은 새 VM 안의 별도 경로 또는 전용 컨테이너에 복사하고, 원본 번들과 manifest는 그대로 둔다. 고정 절대 경로가 필요하면 시험 VM 내부에서만 매핑한다.
- 시험 이미지는 `flyt-compat:<실행ID>` 등 새 태그로 빌드하고 digest를 기록한다. 기존 태그 재지정, 기존 이미지 제거, 전역 image/cache prune은 하지 않는다.
- 전용 namespace·VM·MPS pipe·SHM·포트/IPC 자원을 사용한다. 실행 환경변수는 시험 프로세스에만 전달하며 호스트 전역 `ldconfig`, `/etc/ld.so.preload`, 운영 서비스 환경은 변경하지 않는다.

완료 기준: 보호 대상 기준선과 변경 허용 경로가 기록되고 기존 파일을 수정하지 않고 빌드/실행할 수 있는 구성이 준비됨.

## 4. 단계별 호환성 복구

### A. ABI 및 심볼 의존성 조사 — GPU 없이 우선 수행

1. 실제 사용한 PyTorch `libc10_cuda.so`, `libtorch_cuda.so`, Flyt 클라이언트와 CUDA runtime의 해시를 확정한다.
2. `readelf`/`objdump`/`nm`으로 필요한 심볼·symbol version·SONAME·NEEDED·RPATH/RUNPATH와 Flyt export를 대조한다. 버전 문자열이 있는 import 오류이므로 함수 이름만 추가하는 것으로 충분하다고 가정하지 않는다.
3. 동일 CUDA 12.8 헤더와 공식 API 정의를 대조하여 함수 서명, 요청 API 버전, flags, 반환 코드, query status, 실패 시 함수 포인터 상태를 정리한다.
4. 기존 `cuGetProcAddress`/`cuGetProcAddress_v2`와 Flyt의 `elf2_symbol_address`가 실제 어떤 함수 주소를 반환하는지 확인한다. 요청된 API 버전 및 기본/스레드별 스트림 의미를 검토한다.

산출물: `abi-matrix.csv`, ELF 의존성/심볼 검사 기록, 최소 재현 프로그램. GPU 작업 없이 PyTorch import 문제와 Driver 조회 문제를 분리한다.

### B. 최소 Flyt 전용 수정

우선 Runtime 대체 방식의 진입점 조회 호환성을 복구한다. **별도 Flyt 소스에 최소 패치를 적용하는 방식을 기본안**으로 한다. 패키징 외부 shim은 ABI와 심볼 소유권을 명확하게 검증할 수 있을 때만 후보로 평가하고, 검증되지 않은 shim과 원본 runtime을 중첩하지 않는다.

- `cudaGetDriverEntryPointByVersion` 및 실제로 필요한 관련 API를 Flyt의 Driver 조회 경로에 연결한다.
- 조회 결과는 해당 Flyt 원격 실행 경로의 함수 주소여야 한다. Native CUDA 주소나 VMWeave 주소로 우회하지 않는다.
- 미지원 심볼/버전/flags는 공식 계약에 맞게 실패 처리한다. NULL 포인터와 성공 상태를 반환하거나 에러를 무조건 성공으로 바꾸는 식의 임시 처리를 금지한다.
- 관측된 필수 symbol version 및 export 규칙을 새 Flyt 빌드에만 적용한다.
- 다음 누락 API가 나타나면 필요 API 목록과 실제 호출을 근거로 범위를 확장한다. import 성공과 GPU 계산 성공을 구분한다.

의미 있는 검증: 지원 API 조회와 호출, 존재하지 않는 심볼, 지원되지 않는 버전/flags, 반환 포인터의 소유 모듈, PyTorch import. 테스트는 별도 최소 프로그램과 새 패키지를 사용한다.

### C. preload timeout 분리 진단

B의 기본 경로가 정상 동작하면 preload를 대체 성능 경로로 채택할 필요는 없다. 다만 기존 timeout은 해결 여부와 별개로 미확인 원인으로 남기지 않도록 짧은 진단을 수행한다.

- 시험 프로세스의 초기화 단계 로그, `strace -ff`의 process/file/IPC/network 대기, timeout 직전 스택을 수집한다. stdout 0바이트를 ‘아무 코드도 실행되지 않음’으로 해석하지 않는다.
- `init_rpc` constructor→관리자 IPC→SHM 초기화→동적 로딩 순서를 좁혀 확인한다. 진단용 로그는 별도 빌드에만 추가한다.
- `popen`으로 시작되는 shell/lspci 등에 preload가 상속되어 constructor가 반복 실행되는지, loader 재진입/락 대기인지, 관리자 큐 응답 문제인지 각각 증거로 판별한다. 현재는 모두 가설이다.
- 원인이 확인되면 Flyt의 자식 환경 전달·PCI 탐색·초기화 순서를 필요한 범위에서 수정한다. 시스템 전역 preload 해제나 RPC/검증 생략으로 해결하지 않는다.
- 기본 경로가 통과하고 preload의 원인 수정이 별도 대규모 변경을 요구하면, preload를 미지원 진단 경로로 명시하고 기본 경로로만 후속 검증한다.

진단 시도는 40초 기본 timeout과 제한된 실행 횟수로 관리하며 성능 표본에 포함하지 않는다. timeout이면 스택/로그를 보존하고 동일 실패를 무한 반복하지 않는다.

## 5. 복구 검증 순서와 통과 기준

| 단계 | 검사 | 통과 기준 |
|---|---|---|
| V1 로딩 | 동일 Python/PyTorch/CUDA 기준 복사본으로 import·동적 로딩 | 누락 심볼/재진입 timeout 없이 완료, 실제 로딩 경로 기록 |
| V2 최소 GPU 연산 | 할당, H2D/D2H, 동기화, 작은 행렬 곱 | CPU 기준 일치 및 Flyt 서버의 실제 API/커널 처리 확인 |
| V3 기존 MLP | 입력/가중치·seed·FP32·batch 동일, 관측 MLP 실행 | 기존 rtol=1e-4/atol=1e-6 충족; CPU fallback 없음 |
| V4 두 VM | 별도 SHM·virtual server, 동일 GPU/MPS 데몬 | 두 클라이언트/컨텍스트 대응과 동시 실제 작업 확인; 결과 혼선 없음 |
| V5 자원·부하 | 94 SM 요청, 2GiB 제한, 원/확대 부하 | 요청값과 유효 적용값을 구분해 기록; 실제 부하 완료; 제한 계층 검증 |
| V6 보존 감사 | 기존 패키지/소스/이미지 전후 대조 | 의도한 새 Flyt 경로 외 기존 패키징 변경·삭제·덮어쓰기 없음 |

V5의 SM 실제 값은 지원되는 컨텍스트 affinity 조회 등으로 확인하고 반올림이 있으면 기록한다. 메모리 제한은 적용 계층을 확인하며, 필요 시 시험 세션에서만 경계 할당을 진단한다. 기존 VMWeave의 물리 SM 독점 분할과 같다고 가정하지 않는다.

호환성 진단 실행은 별도 세션에 두고 성능 측정에 합산하지 않는다. 후속 본실험은 새 VM/세션으로 시작하므로 이번 진단을 본실험의 웜업으로 사용하지 않는다. 시험용 MLP 연산이나 검증을 완화해 통과시키지 않는다.

## 6. 성능 실험 재개 및 결과 게시

V1~V6 통과 후 [기존 승인 계획](flyt-mps-comparison-plan-20261026.md)의 Flyt 전용 실험을 새 캠페인에서 재개한다.

- 원/확대 각각 총 5회, 조건당 목표 120초, 총 30구간·순수 목표 관측 60분.
- 본실험 웜업 없음, VMWeave 재측정 없음, p99 분석 없음.
- SHM은 승인된 Flyt 512MiB/process와 기존 VMWeave 64MiB 차이를 유지·명시한다.
- 수정된 경로는 **‘호환성 패치를 적용한 Flyt’**로 이름 붙이고 원본 Flyt 성능으로 오인되지 않게 한다. 패치 diff·소스/빌드/라이브러리 해시를 제공한다.
- 실패 보고서와 기존 N/A 그래프는 당시 결과로 그대로 보존한다. 성공 시 새 디렉터리에 별도 보고서·그래프·집계 자료를 생성한다.
- 게시 범위는 새 Flyt 전용 패치/빌드 설명/검증 도구/결과와 필요한 새 문서다. 기존 VMWeave 패키징 자료와 그 manifest는 게시 diff에 포함하지 않는다. 실험 README 등 탐색용 문서는 새 자료 링크를 추가하는 범위로만 변경 가능하며 패키징 파일은 변경하지 않는다.
- 검증 후 승인된 게시 범위에 따라 별도 작업 브랜치에서 main에 반영하고 원격 커밋을 확인한다. 기존 작업 트리의 변경을 함께 커밋하지 않는다.

## 7. 중단·복구와 산출물

기존 패키지 보존 실패, Native/CPU/VMWeave 우회, 결과 불일치, 운영 자원 영향이 발견되면 중단한다. 다른 작업자가 수정했을 가능성이 있는 기존 파일을 임의로 원복하지 않고 전후 증거와 충돌을 보고한다. 정리는 이번 실행 ID로 생성한 자원·경로에 한정하며 기존 패키지·캐시를 삭제하지 않는다.

산출물:

- 보호 대상 `preservation-before.json`/`preservation-after.json` 및 비교 결과.
- ABI 대응표, 최소 재현 코드, 초기화 타임라인/스택, timeout 원인 또는 확인되지 않은 범위.
- Flyt 전용 patch, 새 패키지/이미지 manifest, 빌드 명령 및 의존성.
- V1~V6 검증 결과·정확성·경로/자원 증거, cleanup 기록.
- 복구 보고서와 이후 별도 성능 비교 보고서·그래프. 대형 바이너리와 자격증명은 기존 게시 원칙에 따라 분리한다.

작업량은 A에서 필수 API 범위를 확인한 뒤 구체화한다. 현재 심볼 하나의 부재만으로 수정 규모나 성공을 확약하지 않는다. 진단/빌드 시간은 성능 측정 60분과 별도다.

## 8. 검토 요청

권장안은 **기존 VMWeave 패키징과 기존 Flyt 빌드를 보존하고, 독립 복사본의 Flyt API 호환성을 최소 수정 → V1~V6 검증 → 승인된 짧은 성능 실험 재개 → 새 결과 main 게시** 순서다.

이 계획 승인 후에는 위 범위의 Flyt 전용 코드 수정과 새 시험 패키지 생성까지 진행한다. 기존 VMWeave 패키징 변경, 기준 PyTorch 버전 변경, 모델/측정 지표 변경이 필요해지면 실행하지 않고 수정안을 다시 검토받는다.


## 9. 승인 후 실행 기록 — 2026-10-26

- [복구 결과와 근거](../evidence/20261026-flyt-compatibility/REPORT.md): 진입점 조회, preload PCI 탐색 재진입, 내부/구조체 포인터 전달, 확대 부하의 메모리 사용 문제를 독립 Flyt 복사본에서 수정했다.
- 최종 진단은 동일 MLP·정확성 기준, 두 VM 동시 동작, 원/확대 부하, 실효 94 SM 조회와 2GiB 추가 할당 거부를 통과했다. 보호 대상 25,279개 파일의 사전/사후 해시 비교도 통과했다.
- 실제 GPU 가상주소를 보존하는 새 시험 빌드는 비이동 실험에 한정하며 체크포인트 생성·복원을 오류로 차단한다. 기존 Flyt/VMWeave 패키지는 변경하지 않았다. 일반 배포·모든 CUDA API 호환성을 검증한 것은 아니다.
- import가 정상 등록 RPC를 계속 수행하는 것이 확인되어 제한된 진단 timeout을 300초까지 늘렸다. 본실험의 120초 관측이나 웜업 없음 규칙은 바꾸지 않았다.
- 본실험의 원 P 첫 3회는 부하 커널 동기화 후 완료 통보를 받았지만 이후 버퍼/캐시 회수의 별도 확인 응답은 없었다. 4회차부터는 `observe 0` 제어 명령(요청·GPU 연산 0개)으로 회수 완료를 확인한다. 앞선 표본은 버리거나 재측정하지 않고 절차 차이를 보고서에 명시한다.
- [후속 성능 비교 산출물](../evidence/20261026-flyt-mps-recovered/REPORT.md)은 별도 캠페인에 저장한다. 진단 요청과 이전 초기화 실패는 성능 표본에 합산하지 않는다.

- 후속 본실험은 원/확대 각 5회, 조건당 120초, 웜업 없이 총 30구간을 완료했다. 정상 완료 79,511건, 요청 오류·정확성 불일치 0건이다. VMWeave는 재측정하지 않았고 처리량 감소율만 비교했다.
- 실험 종료 후 보호 대상 25,279개 파일, 기존 이미지 참조 107개, 기존 작업 트리·스테이징 변경의 보존을 재확인했다. 별도 원본 host manifest 1,569개 파일도 일치했다. [최종 보존 검증](../evidence/20261026-flyt-compatibility/validation/final-source-protection.json)을 참조한다.
