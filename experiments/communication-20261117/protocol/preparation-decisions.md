실행 준비 중 결정 사항 (본 측정 전)

- GPU index 1 / UUID `GPU-772181af-05a4-0c24-de59-8487bd37c142`를 기존 HAMi DRA DeviceClass로 예약한다. Claim은 cores=100, memory=97887Mi 전체 capacity를 소비한다. classic HAMi의 제외 UUID, DeviceClass, ResourceSlice 및 Operator 설정을 변경하지 않는다.
- N/F/L은 `comm-20261117`, V는 이미 중앙 Operator에 등록된 `vmweave-test-a`에서 캠페인 고유 이름의 객체만 생성한다. 기존 학생의 VM, Pod, Claim은 수정하지 않는다.
- V/F/L 클라이언트는 동일 체크섬의 Ubuntu 24.04 cloud image, 4 vCPU, 16 GiB. V 전용 VM 하나와 F/L이 순차 사용하는 네트워크 VM 하나를 사용한다. 각 세션마다 VM을 새로 부팅하고 서버를 새로 생성한다. CPU affinity는 QEMU 8–11, 원격 서버 12–15, Native 8–11이다. 같은 NUMA 0의 CPU들이며 메모리 strict binding/CPU 독점 예약은 하지 않는다.
- VMWeave v0.5.11의 현재 운영 Guest에서 읽은 `VMWEAVE_BULK_COPY=0`을 유지한다. 공개된 동일 digest의 worker와 Guest library를 사용하며 성능 옵션을 튜닝하지 않는다. Worker 기본 session/pinned-pool 동작도 변경하지 않는다. pageable이라는 분류는 클라이언트 버퍼를 뜻하며 내부 staging 구현까지 같다는 뜻은 아니다.
- Flyt는 2026-09-29 TCP 비교의 `596a86939bae125d127a9ed6f70d92c332f47644` 기반 호환성 수정 빌드를 재사용한다. SHM Flyt 빌드는 사용하지 않는다. 188 SM 및 전체 GPU 메모리를 설정하고 MPS를 실험 Pod 안에서만 실행한다. 원본 무수정 Flyt 또는 gRPC CUDA 데이터 경로라고 표시하지 않는다.
- HAMi 차트 후보인 Lupine CUDA 13.3.1 이미지는 host driver 580.173.02의 libcuda로 시작할 때 `cuGraphNodeGetContainingGraph` 심볼 오류가 발생했다. compat 라이브러리 경로에서는 listen까지 확인했으나 이 조합의 성능/연산 검증은 수행하지 않았다. 대신 공식 Lupine **v2.1.0 / CUDA 12.9.1 / Ubuntu 24.04**, client/server 동일 source revision `4fe630ac2a3dd15e67dd1804c80bbb60db1439de`를 선정했다. 실제 호스트 드라이버와 CUDA 12.8.1 benchmark runtime을 사용한다. 운영 드라이버 업그레이드는 하지 않는다.
- VMWeave의 `cuModuleLoadData`는 이번 cubin 입력을 오류 801로 거부했다. 같은 PTX 소스를 N/V/L에는 PTX로, ELF를 요구하는 legacy F에는 CUDA 12.8.1 ptxas의 sm_120 cubin으로 제공한다. F의 ELF section-table 위치만 보정하며 kernel/segment bytes 불변을 검증한다. JIT, module load 및 ABI 등록은 모두 측정 전에 끝낸다. GPU machine code가 네 방식에서 동일하다고 주장하지 않는다.
- 측정기 검토에서 D2H 최종 버퍼 검사가 별도 재복사로 덮이지 않도록 수정했다. Native 초기 검산은 수정 전 버전이며 정식 통계에는 포함하지 않는다. 최종 artifact는 네 경로 공통 검산 후 해시를 고정한다.
- 준비 실패와 재시도는 `results/pilot-*` 및 `evidence`에 보존한다. VM 재부팅으로 `/tmp/comm`이 삭제된 SCP 준비 실패와 CUDA module 형식 실패를 성능 표본으로 취급하지 않는다.

- 초기 N/F API 검산은 `GPU_CORE_UTILIZATION_POLICY=DISABLE`을 사용했다. V의 실제 환경 조사에서 기본 정책 사용이 확인되어, 본 측정은 N/V/F/L 모두 이 override를 제거하고 DRA 주입의 동일 cores=100 정책을 사용한다. 5블록 통계에는 최종 구성만 포함한다.
