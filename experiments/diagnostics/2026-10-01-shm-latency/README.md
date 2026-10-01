# SHM+HAMi 지연 역전 원인 분석 — 2026-10-01

현재 결과는 SHM이라는 전송 매체 자체가 TCP보다 느리다는 증거가 아니다. 구현을 확인하면 SHM도 요청을 인코딩하고 응답을 기다리며, 양쪽의 1ms 폴링과 여러 번의 payload 복사를 수행한다. **소형 요청은 대기 정책, 대형 전송은 복사 경로까지 우선 개선할 근거가 있다.** HAMi만의 지연 기여량이나 각 원인의 VM 전체 지연 비중은 아직 분리 측정하지 않았다.

기존 GPU campaign 원본은 수정하지 않았다. 이번 추가 실행은 실제 campaign Guest 라이브러리의 큐를 사용하는 **호스트 일반 RAM 구성요소 진단**이다. VM·CUDA·HAMi·PCI BAR·Guest I/O 스레드를 포함하는 재실험이 아니며, 운영 런타임도 수정하지 않았다.

## 기존 실험에서 나타난 패턴

경로별 독립 5회 실행 평균. 원본과 전체 SD는 [기존 결과](../../evidence/results/2026-09-30-performance/OVERHEAD.md) 및 [원시 집계](../../evidence/results/2026-09-30-performance/analysis/overhead.csv)에 있다.

| 측정 항목 | Flyt TCP/RPC+MPS | SHM+HAMi | S/T |
|---|---:|---:|---:|
| cudaMemGetInfo | 0.717 ms | 1.467 ms | 2.05 |
| kernel launch + sync | 1.769 ms | 2.825 ms | 1.60 |
| H2D 4 KiB + sync | 1.891 ms | 2.828 ms | 1.50 |
| D2H 4 KiB + sync | 1.881 ms | 2.834 ms | 1.51 |
| H2D 1 MiB + sync | 2.991 ms | 5.272 ms | 1.76 |
| D2H 1 MiB + sync | 3.090 ms | 5.170 ms | 1.67 |
| H2D 16 MiB + sync | 10.525 ms | 43.956 ms | 4.18 |
| D2H 16 MiB + sync | 11.924 ms | 46.974 ms | 3.94 |

소형 요청에도 ms 단위 고정 비용이 있고, 대형 전송에서는 크기에 따른 추가 비용이 증가한다. 이 두 현상을 나누어 조사했다.

## 1. 소형 요청 경로의 1ms 폴링 대기

[Worker](../../../runtime/shm/src/worker.c)는 빈 큐를 만날 때 `nanosleep({0,1000000})`을 호출한다. [Guest 수신 함수](../../../runtime/shm/shm-queue/src/queue.c)의 `flyt_shm_receive`도 응답이 없으면 같은 시간을 쉰다. 요청이 이미 공유 메모리에 있어도 상대 스레드가 깨어나기 전에는 처리할 수 없다. 실제 campaign 라이브러리의 [disassembly](results/flyt_shm_receive.asm)에도 이 호출이 존재한다.

두 sleep이 매 요청마다 정확히 2ms씩 더해지는 것은 아니다. 양쪽 실행 시점이 겹치며 잔여 대기 시간이 달라진다. 또한 sleep 종료 후 CPU 스케줄링 지연이 추가될 수 있다. [Linux nanosleep 문서](https://man7.org/linux/man-pages/man2/nanosleep.2.html)

실제 campaign의 `libflyt_guest.so` 해시를 원본 protocol과 대조한 뒤, 동일한 큐 함수에 요청 0 B/응답 16 B를 전달했다. 일반 RAM에 두 endpoint를 두고 CPU 48/50에 고정했다. 각 조건은 200회 워밍업 후 1초 측정, 독립 프로세스 3회이다. 아래 SD는 실행별 평균의 SD이며 전체 개별 요청 분산을 뜻하지 않는다.

| Worker / Guest 대기 | 큐 왕복 평균 ± SD | CPU 사용량: 코어 상당 |
|---|---:|---:|
| 1ms sleep / 1ms sleep | 1,092.29 ± 8.21 µs | 0.045 |
| busy polling / 1ms sleep | 1,084.62 ± 9.75 µs | 1.020 |
| 1ms sleep / busy polling | 1,076.69 ± 1.82 µs | 1.018 |
| busy polling / busy polling | 1.71 ± 0.97 µs | 2.000 |

**이 구성요소에서는 대기 정책만 바꿔도 ms 수준의 지연이 사라졌다. 한쪽만 바꾸면 남은 쪽의 대기가 지배했다.** 다만 이 값을 VM 지연 개선량으로 대입해서는 안 된다. 양쪽 busy polling의 개별 실행 평균은 2.831/1.152/1.145 µs로 변동했으며, CPU 두 코어를 거의 전부 소비했다. 해결책으로 무조건 busy polling을 배포할 근거는 아니다.

## 2. 기존 kernel 수치를 분해하면 두 번의 원격 왕복이 보인다

[측정 코드](../../performance/overhead_probe.c)의 kernel 지표는 `cuLaunchKernel` 다음 `cudaDeviceSynchronize`까지 포함한다. 복사 지표도 각 방향의 `cudaMemcpy` 다음 sync를 포함한다. SHM에서는 각각 별도 요청/응답이다. 저장된 `first_seconds`와 `second_seconds`를 재분석했다.

| 경로 | launch API 대기 | 뒤따르는 sync API 대기 | 합계 |
|---|---:|---:|---:|
| 직접 CUDA+HAMi | 1.66 µs | 6.47 µs | 8.12 µs |
| TCP/RPC+MPS | 898.10 µs | 870.93 µs | 1,769.03 µs |
| SHM+HAMi | 1,425.44 µs | 1,399.62 µs | 2,825.06 µs |

두 API가 각각 약 1.4ms를 소비하는 것은 호출마다 고정 대기를 지불하는 설명과 부합한다. 여기서 sync 시간은 **호스트가 관측한 API 대기 시간**이며 순수 GPU 실행 시간이 아니다. SHM resident 처리량 355.19 jobs/s도 작업당 약 2.8ms와 일관된다.

TCP에도 같은 명시적 sync가 있으므로 이 사실 자체가 불공정한 비교를 의미하지 않는다. 다만 이번 순차 완료형 벤치마크는 batching이나 비동기 중첩의 이점을 보여주는 조건이 아니다. [분해 계산 코드](reanalyze.py)와 [실행별 계산 결과·입력 해시](results/kernel-decomposition.json)를 보존했다.

## 3. 현재 SHM은 zero-copy가 아니며 인코딩도 남아 있다

`queue.c`의 encode/decode는 128 B descriptor에 식별자·API·schema·offset·length·상태를 기록하고 검증한다. 소켓 전송을 없애도 프로세스 간 요청 표현, 객체 handle 변환, 결과 전달은 남는다. 직렬화 형식이 가벼워질 가능성과 전체 호출 경로가 빠르다는 주장은 구분해야 한다.

H2D 경로는 다음과 같다. 화살표는 실제 payload 복사를 나타낸다.

```text
Guest 사용자 버퍼
 → Guest 요청 staging (calloc + memcpy)
 → SHM 요청 arena (memcpy)
 → Worker private snapshot (malloc + volatile 바이트 복사)
 → Worker CUDA용 host staging (malloc + memcpy)
 → GPU (CUDA H2D)
```

GPU 전송 이전에 **CPU 전체 payload 복사 4회**가 있다. D2H는 GPU→Worker host result 이후 Worker 응답 버퍼→SHM 응답 arena→Guest 사용자 버퍼로 이어져 **CPU 전체 payload 복사 3회**가 있다. `calloc`의 실제 메모리 초기화 비용은 allocator/페이지 상태에 따라 달라지므로 별도 고정 1회 복사로 계산하지 않았다.

근거: [Guest cudaMemcpy](../../../runtime/shm/src/guest.c), [큐 submit/take/respond/receive](../../../runtime/shm/shm-queue/src/queue.c), [CUDA copy 실행기](../../../runtime/shm/cuda-dispatch/src/exec.c), [응답 복사](../../../runtime/shm/src/dispatch.c). 이 경로는 공유 arena 자체를 GPU에 등록하여 직접 전송하는 구현이 아니다.

특히 snapshot은 `const volatile unsigned char`를 한 바이트씩 읽는 루프다. 실제 라이브러리의 [Worker take disassembly](results/flyt_shm_worker_take.asm)에서도 byte load/store와 1바이트 증가가 확인된다. 동일 형태의 루프와 libc memcpy를 호스트 일반 RAM에서 비교했다. 버퍼는 사전 접근하고 20회 워밍업, 조건당 0.3초, 독립 프로세스 3회이다.

| 크기 | volatile snapshot 평균 ± SD | memcpy 평균 ± SD |
|---|---:|---:|
| 4 KiB | 1.048 ± 0.0005 µs | 0.0499 ± 0.00004 µs |
| 1 MiB | 263.40 ± 0.11 µs | 28.15 ± 0.78 µs |
| 16 MiB | 4,231.24 ± 21.63 µs | 965.13 ± 0.37 µs |

실제 큐에서도 양쪽 대기를 제거했지만 16 MiB 요청은 9.79 ± 1.02ms, 16 MiB 응답은 6.79 ± 1.67ms가 걸렸다. CUDA가 없는 일반 RAM 조건에서도 크기 의존 비용이 남는다. 따라서 폴링 개선만으로 대용량 문제까지 해결될 것으로 기대할 수 없다. 반대로 이 수치만으로 원래 44–47ms 중 몇 ms가 snapshot 때문인지 계산할 수는 없다.

snapshot은 외부에서 변할 수 있는 공유 메모리를 신뢰 가능한 private 데이터로 옮기는 안전 경계이기도 하다. 검증을 삭제하거나 mutable SHM 포인터를 그대로 실행기에 넘기는 방식은 피해야 한다. 버퍼 소유권·수명·안정된 snapshot·범위 검사를 유지하면서 중복 staging과 복사 방식을 개선해야 한다.

## 4. 확인한 추가 경로와 아직 분리하지 못한 요인

- **Guest 스레드 전달:** API 호출 스레드→전용 I/O 스레드→호출 스레드로 condition variable handoff가 있다. 전역 lock과 한 개 job으로 직렬화하며, 큐도 한 개 pending 요청만 허용한다. 이번 순차 측정에서 lock 경쟁의 기여량은 측정하지 않았지만 handoff 비용은 존재한다.
- **Worker 파일 작업:** 응답마다 `/tmp/flyt-slot-*-guest`를 fopen/fclose한다. trace가 꺼져도 이 작업은 남는다. 이 비용의 비중은 미측정이며 주원인으로 단정하지 않는다.
- **PCI BAR 매핑:** [Guest mapping](../../../runtime/shm/src/mapping.c)은 `resource2`를 mmap하고 호스트는 backing file을 mmap한다. 일반 RAM 진단과 동일한 캐시 동작을 가정할 수 없다. Linux는 `resourceN`과 prefetchable resource용 `resourceN_wc` 인터페이스를 구분한다. 실제 Guest PAT/PTE 및 읽기/쓰기 대역폭은 아직 측정하지 않아 UC/WC를 확정하지 않는다. `_wc` 변경도 읽기 성능·메모리 순서·ring 원자성 검증 없이 적용하지 않는다. [Linux PCI sysfs 문서](https://docs.kernel.org/PCI/sysfs-pci.html)
- **HAMi와 MPS:** 원래 S는 HAMi 100, T는 MPS 전체 SM 조건이다. 25% 상한으로 S가 느려진 결과가 아니다. 직접 CUDA+HAMi가 query 6.59µs, launch+sync 8.12µs였으므로 HAMi가 모든 경우에 약 1ms를 추가한다는 설명은 맞지 않는다. 다만 Worker에서 HAMi만 켜고 끈 대응 실험은 없어 그 기여를 0이라고 할 수도 없다.
- **커널·실행기:** 동일 작업을 사용했지만 T는 offline cubin, S는 PTX 로딩 등 차이가 있다. 동일 SASS를 입증하지 않았다. 그렇더라도 query/복사에서도 지연 역전이 있으므로 커널 코드 차이만으로 전체 현상을 설명할 수 없다.

## 개선 및 검증 순서

| 순서 | 변경/측정 | 확인할 결과 |
|---|---|---|
| 1 | VM 안에서 Guest submit/receive 대기, Worker take→dispatch→respond, sleep 횟수·시간을 요청 ID로 계측 | 고정 지연의 실제 기여량. VM/호스트 시계는 직접 빼지 말고 각 clock domain 내 구간을 비교 |
| 2 | 양쪽 알림 방식 또는 제한된 짧은 spin+대기 설계. 현재 ivshmem-plain에는 알림 설계 변경이 필요 | query/소형 요청 p50·p95·p99와 CPU 예산 동시 비교; 유실 wakeup·타임아웃 검증 |
| 3 | 버퍼 풀, 안전한 bulk snapshot, 중복 staging 제거; pinned staging은 별도 평가 | 크기별 H2D/D2H 시간·유효 대역폭·전체 데이터 검산 |
| 4 | Guest BAR 읽기/쓰기 및 NUMA 배치 별도 계측 | CPU 복사와 매핑 특성의 기여 분리 |
| 5 | 같은 실행기/정책에서 전송만 변경하거나 SHM의 HAMi on/off 대응 실험 | HAMi·MPS·전송 차이 분리. 100과 정책 hook 제거는 이 진단 목적에서만 구분 |
| 6 | 동기 API 의미를 보존한 batching/pipeline을 별도 workload로 평가 | 원래 순차 완료 지표와 분리하여 throughput/latency 보고 |

한 번에 여러 최적화를 적용하면 인과 구분이 어려우므로 원본→대기만 변경→복사만 변경→결합 순으로 반복한다. 운영 런타임 최적화와 VM 전체 재측정은 이번 분석에서 수행하지 않았다.

## 재현·감사 자료

- [진단 실행기](run.py), [큐 진단 C](queue_probe.c), [복사 진단 C](copy_probe.c)
- [명령·stdout·stderr·종료 코드·시간](results/commands.jsonl), [실제 터미널 transcript](results/diagnostics.terminal)
- [환경·원본 라이브러리 및 진단 바이너리 해시](results/environment.json), [전체 반복·평균·SD](results/summary.json)
- `results/q-*.csv.gz`: 큐 왕복 개별 표본. 30회 큐 실행, 18회 복사 실행. 큐 원시 표본 수·평균 검산 및 종료 후 전체 payload 검산을 통과했다. 매 요청은 상태 및 첫/마지막 바이트를 검사하며, 전체 payload 검사는 측정 종료 후 수행했다. 복사 진단은 실행 종료 후 전체 memcmp를 수행했다.
- [검증·원본 불변성 기록](results/validation.json), [새 자료 SHA256 목록](SHA256SUMS)

라이브러리는 기존 protocol에 기록된 해시와 일치한다. stage2 빌드 context의 큐 소스는 당시 경로 `experiments/shm-queue/src/queue.c`에 있으며 현재 `runtime/shm/shm-queue/src/queue.c`와 내용이 같다. Worker/Guest/mapping 소스도 해당 build context와 일치한다. 실제 라이브러리 disassembly를 추가 확인했으며 전체 Worker 이미지를 재빌드한 실험은 아니다.

재실행에는 원래 측정 라이브러리와 현재 큐 헤더, gcc, objdump가 필요하다. `run.py`의 CPU 48/50 및 private artifact 경로를 환경에 맞추고 **새 출력 디렉터리에서** 실행해야 한다. 이미 존재하는 results는 덮어쓰지 않는다. 이 진단은 짧은 구성요소 비교이며 장시간 안정성·다중 VM 공정성·GPU 성능 검증을 대체하지 않는다.
