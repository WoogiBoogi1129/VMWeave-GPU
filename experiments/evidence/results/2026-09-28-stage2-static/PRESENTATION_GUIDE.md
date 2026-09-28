# 발표 배치안 — 요청 한 건을 따라가고 계산 결과로 마무리

## 슬라이드 1: “Guest의 CUDA 요청이 Worker까지 전달되는가?”

[02-malloc-roundtrip.png](terminal-captures/02-malloc-roundtrip.png)를 사용한다.

1. 왼쪽 `submit`, request ID **3**, requested_bytes **1048576**: “가상머신이 1 MiB 할당을 요청합니다.”
2. 오른쪽 `take`, 같은 ID **3**: “Worker가 같은 요청을 받았습니다.”
3. 오른쪽 `respond`, allocation_handle **1**, api_result **0**: “Worker가 할당하고 성공 응답을 보냅니다.”
4. 왼쪽 `receive`, 같은 handle **1**, api_result **0**: “가상머신이 같은 결과를 회수합니다.”

그림 아래 문장: **“동일한 요청 식별자로 Guest의 제출·수신과 Worker의 수신·응답을 연결했다.”**

양쪽 모두 호스트 터미널에서 수집한 로그를 조회한 화면이다. 왼쪽 터미널이 VM에 실시간 접속한 화면이라고 설명하지 않는다. 필드의 `null`은 그 시점에 응답 결과가 없다는 뜻이다.

## 슬라이드 2: “실제 GPU 계산과 결과 회수도 가능한가?”

[04-kernel-sync.png](terminal-captures/04-kernel-sync.png)를 먼저 설명한 뒤 [06-accuracy-free.png](terminal-captures/06-accuracy-free.png)를 보여준다. 한 슬라이드에 작은 캡처 여러 장을 넣기보다 두 장으로 나누거나 발표 중 이미지를 전환한다.

- request **10**, api_id **8243**는 `cuLaunchKernel`이다. 요청 왕복과 성공 응답을 확인한다.
- request **11**, api_id **4128**은 `cudaDeviceSynchronize`다. launch 응답 이후 GPU 작업 완료를 확인한다.
- 결과 화면의 `checked_elements=262144`, `mismatches=0`이 전체 정수 검산 결과다.
- 오른쪽 기준(reference)·실제 출력(output) SHA-256이 같고, request **17**의 free가 성공했다.

그림 아래 문장: **“1 MiB 입력을 복사하고 GPU 커널을 실행한 뒤, 회수한 정수 262,144개가 기준과 모두 일치함을 확인했다.”**

자료 설명에는 “새 VM 대표 실행 1회, 2026-09-28–29 KST, 실험 후 원본 로그 조회 화면”을 명시한다. 과거 독립 실행 3회와 구분한다.

## 보조 자료

| 질문 | 제시할 화면 또는 원본 |
|---|---|
| 어떤 프로그램·GPU·세션인가? | [01-program-binding](terminal-captures/01-program-binding.png), [배치 식별자](raw/identity.json) |
| 데이터가 실제로 왕복했나? | [03-H2D](terminal-captures/03-h2d.png), [05-D2H](terminal-captures/05-d2h.png): 각 1 MiB, 같은 handle 1 |
| 로그 대응을 독립 확인할 수 있나? | [07-cleanup-verification](terminal-captures/07-cleanup-verification.png), [원본 Guest 로그](raw/guest-stderr.txt), [Worker 로그](raw/worker-stderr.txt), [요청 CSV](raw/requests.csv) |
| 실험 자원은 정리됐나? | [Released와 종료 확인](raw/final-audit.json), [backing PVC 빈 상태](backing-audit.json) |

이 시연에서 시간 수치를 성능 그래프로 만들지 않는다. 추적과 단계별 대기가 켜져 있으며 목적은 동작·정확성 확인이다. 4 GiB·compute 50은 환경 조건으로만 표기한다.
