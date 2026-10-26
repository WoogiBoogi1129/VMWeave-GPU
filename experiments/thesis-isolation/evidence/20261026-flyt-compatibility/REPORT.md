# Flyt–PyTorch 호환성 복구 결과

**승인된 모델·Python/PyTorch/CUDA·2GiB 제한을 유지한 상태에서 호환성 검증을 통과했다.** 새 Flyt 복사본만 수정했으며 기존 VMWeave 패키징·번들·결과를 교체하지 않았다. 본실험은 새 VM 쌍에서 별도로 실행하며 [성능 비교 보고서](../20261026-flyt-mps-recovered/REPORT.md)에 집계한다. 아래 진단 요청은 성능 표본이 아니다.

## 확인한 문제와 수정

| 단계 | 관측과 근거 | 시험 빌드 변경 / 결과 |
|---|---|---|
| Runtime 로딩 | 기존 Flyt에 `cudaGetDriverEntryPointByVersion` 등 고정 PyTorch 빌드의 import 심볼 부재 | CUDA 12.8 헤더 계약에 맞는 제한적 조회·전달 구현. Flyt 소유 함수 주소만 반환. 같은 PyTorch import 성공 |
| preload timeout | 15초 추적에서 PCI 탐색 shell 실행이 반복됨. shell이 preload를 상속해 Flyt constructor 및 관리자 IPC에 재진입 | `popen(lspci...)`를 sysfs PCI vendor/device/resource2 탐색으로 교체. 외부 shell 실행 없이 preload import 성공 |
| 내부 메모리 주소 | 원본 map은 할당 시작 주소를 토큰으로 관리. 16바이트 할당의 시작점 복사는 성공했지만 +4바이트 복사는 오류 1. 원본 map의 CPU 재현에서도 내부 주소 조회 실패 | 클라이언트별 할당 범위 조회 추가. 수정 후 +4바이트 D2H는 값 2.0 및 오류 0 반환 |
| MLP 첫 연산 | 가중치·입력 전송 이후 cuBLAS 오류 3. 앞선 4개 커널 호출 뒤, cuBLAS 생성 **이전** `cuCtxSynchronize`가 오류 700 반환. MPS 로그에도 fatal GPU error 기록 | 오류를 단순 cuBLAS 메모리 부족으로 처리하지 않음. 커널 인자의 첫 포인터만 치환하던 구현을 검토하고 실제 GPU 가상주소를 보존하도록 변경. 구조체 내부 포인터도 주소 치환 없이 전달. 기존 MLP 정확성 통과 |
| 확대 부하 | 직접 주소 보존만 적용한 빌드는 원 부하 통과, 확대 1GiB 할당은 2GiB 제한에서 OOM | 등록 시 모든 커널을 미리 조회하던 경로를 첫 사용 시 조회로 변경. 같은 2GiB에서 원/확대 부하 모두 완료. 제한값·모델·버퍼 크기는 유지 |

커널 지연 조회만 먼저 적용한 시험은 MLP 오류를 해결하지 못했다. 주소 보존 수정으로 MLP가 통과한 뒤 확대 부하의 메모리 사용을 줄이는 데 지연 조회를 채택했다. 오류 700의 선행 여부와 수정 후 통과는 직접 관측했지만 모든 커널 인자 바이트의 의미를 독립 추적한 것은 아니므로, 특정 구조체 필드 하나를 유일한 원인으로 단정하지 않는다.

CUDA 진입점 조회에서 없는 선택적 심볼은 공식 헤더 계약에 따라 `cudaSuccess`와 **NULL + SymbolNotFound**를 반환할 수 있다. 이는 호출 가능한 포인터나 query-success를 꾸며내는 처리가 아니다. 지원하지 않는 버전·flags·그래프 기능은 테스트와 구현에 명시했다. Native GPU/CPU/VMWeave 라이브러리로 우회해 성공시키지 않았다.

## 검증 결과

| 검증 | 결과 | 근거 |
|---|---|---|
| V1 로딩·ABI | PASS | [API 테스트](validation/api-tests.log), [수정 후 preload import](validation/fixed-preload-import.log), 최종 qualification ready 기록 |
| V2 기본 GPU 계산 | PASS | [할당·왕복 복사](validation/minimal-copy.log), [내부 주소](validation/offset-after.log), [2×2 SGEMM](validation/minimal-gemm.log): 모든 상태 0, 결과 `[23,34,31,46]` |
| V3 기존 MLP | PASS | 최종 qualification의 모든 관측 요청이 기존 rtol=1e-4 / atol=1e-6 검사 통과 |
| V4 두 VM 동시 동작 | PASS | A/B 동시 MLP 관측, 별도 SHM·서버 및 동일 GPU/MPS 구성. 두 방향 요청 모두 정상 완료 |
| V5 자원·부하 | PASS | 양쪽 서버에서 requested SM=94, affinity query status=0, effective SM=94. 원/확대 memory·compute 완료 및 2GiB 추가 할당 거부 |
| V6 보존 | PASS | [보존 비교](validation/preservation-check.json): 사전 기록한 25,279개 파일 변경 0개. 기존 index/worktree diff도 동일. [진단 환경 정리](cleanup.json) |

최종 qualification 원본은 [status](validation/qualification-1793005956527081884/status.json.gz)와 같은 디렉터리의 압축된 요청·부하·서버 로그다. 확대 부하가 실패했던 직전 시험은 [별도 기록](validation/qualification-1793005749242005705/status.json.gz)으로 보존했다. V2 최소 검사는 복구 중간 빌드의 단계별 증거이고, 최종 빌드는 기존 MLP와 네 부하의 실제 계산·복사·정확성을 다시 검증했다.

진단 import는 수많은 정상 등록 RPC가 계속 진행하는 것이 추적되어, 한정된 재시도의 timeout을 60초에서 300초로 늘렸다. 이는 성능 구간을 늘린 것이 아니다. 최종 본실험은 준비 완료 후 조건당 120초를 적용하며 초기 요청을 버리지 않는다. 실패한 진단 백엔드의 컨텍스트·등록 모듈을 다음 검사의 기준선으로 재사용하지 않았다.

## 시험 빌드의 적용 범위

- **비이동 실험 전용**이다. 실제 GPU 가상주소를 그대로 전달하므로 이 빌드의 체크포인트 생성·복원은 오류를 반환하도록 차단했다. 기존 Flyt 및 VMWeave 빌드의 기능은 변경하지 않았다.
- 검증 대상은 고정 eager FP32 MLP 및 승인된 부하다. CUDA Graph, preload 방식의 전체 MLP, 모든 Driver API, 체크포인트 호환성이나 일반 배포를 검증하지 않았다. preload 경로의 다음 VMM 심볼 요구는 본실험 경로로 채택하지 않았다.
- 실제 CUDA 연산은 Flyt 서버에서 실행한다. VM에는 GPU 직접 할당을 추가하지 않았고, Guest `libcuda`/`libcudart` 시험 링크는 새 Flyt 클라이언트를 가리킨다. 서버의 Native CUDA 라이브러리는 정상 원격 실행에 필요한 구성이다.
- 본실험 원 P 3회차에서 실행 중 `cuCtxGetCurrent` 기록과 서버의 `execCtx` 포인터를 양쪽 모두 읽기 전용으로 대조해 일치를 확인했다([검증 기록](../20261026-flyt-mps-recovered/raw/original-r3-ab/context-audit-validation.json)). 이는 해당 회차의 추가 경로 증거다. MPS affinity 조회 94는 컨텍스트 설정 증거이며 VMWeave와 같은 물리 SM 독점 분할을 입증하지 않는다. HAMi의 50%/2048MiB 요청, Flyt의 94 SM/2GiB 정책과 실제 조회를 구분해 기록했다.
- 초기화·정리·지원하지 않는 경로까지 일반 제품 수준의 회귀 검증을 한 것이 아니다. 본실험은 매 반복 새 VM 쌍과 서버를 사용한다.

## 산출물·재현·보존

[guest.patch](patches/guest.patch), [host.patch](patches/host.patch), [소스·바이너리 manifest](manifest.json), [빌드 환경](build-environment.json), [패키지 SHA256](package-sha256.json), [테스트](tests/), [빌드 설명](BUILD.md)을 제공한다. `*-preexisting.patch`는 복구 이전 Flyt 작업 트리의 수정이며 이번 변경과 분리했다. 대형 바이너리·기존 번들·SSH 키·생성된 DB 자격증명은 커밋하지 않는다.

원본 보존 기준선과 사후 기록은 [before](validation/preservation-before.json.gz) / [after](validation/preservation-after.json.gz)에 있다. Host Flyt 원본은 독립 복사 후 추가로 [manifest](validation/host-original-manifest.json.gz)를 기록했으므로 최초 25,279개 사전 감사와 동일한 시점의 증거로 표현하지 않는다. 원본 Host 소스에는 쓰기 작업을 수행하지 않았다.

preload 재귀의 [추적 발췌](validation/preload-recursion-excerpt.txt)와 [전체 추적 파일 해시](validation/preload-trace-index.json), [cuBLAS 이전 GPU 오류](validation/pre-cublas-fault-server.log)를 공개한다. 상세 원본은 새 로컬 실행 디렉터리에 보존했다. 기존 실패 보고서·N/A 그래프는 당시 결과로 남겨두고 이번 결과로 덮어쓰지 않았다.
