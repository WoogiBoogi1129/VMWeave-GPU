# VMWeave-GPU

<div class="hero" markdown>

**가상머신의 GPU 실행을 공유 메모리로 연결합니다.**

Kubernetes가 관리하는 VM의 CUDA 호출, GPU 자원 요청, 실행과 회수를
하나의 흐름으로 다루는 연구 프로젝트입니다.

[시작하기](getting-started/index.md){ .md-button .md-button--primary }
[실험 결과 읽기](evaluation/index.md){ .md-button }

</div>

## 실행 구조

<figure class="architecture-figure" markdown>

![VMWeave 중앙 제어와 사용자 namespace 구조](assets/architecture.svg)

</figure>

[그림 크게 보기](assets/architecture.svg){ target="_blank" rel="noopener" }

Guest의 CUDA interception은 요청을 SHM 큐에 기록합니다. Worker가 요청을 받아
HAMi/CUDA 경로에서 실행하고 응답합니다. Kubernetes 제어기는 VM·요청·Worker의
연결과 채널 수명 주기를 관리합니다. [아키텍처 자세히 보기](architecture/index.md)

## 읽는 순서

| 목적 | 시작 문서 |
|---|---|
| 시스템이 해결하려는 문제 이해 | [소개와 설계 범위](overview/index.md) |
| 현재 가능한 기능 확인 | [지원·검증 현황](overview/status.md) |
| 설치 및 기능 확인 | [설치와 시작](getting-started/index.md) |
| 논문·발표에서 결과 검토 | [실험과 평가](evaluation/index.md) |
| 코드 수정과 실험 재현 | [개발 안내](development/index.md) |

## 연구 상태

2026-09-30 Go Operator 전환 후 N/T/S 5회 반복·105개 구간과 단일 VM 상한 20회를 새로 측정했습니다.
상한 25·50·75는 각각 5회 모두 사전 이용률 기준을 초과했습니다. 학습·메모리 결과는 기존 구현의 별도 실험입니다. [후속 실험 환경 정리](history/cleanup-2026-09-30.md)도 확인하세요.
제한된 CUDA 실행·학습과 두 VM의 메모리 제한을 검증했으며 전체 호환성 및 장애
시험은 미완료입니다. 현재 오버헤드 실험은 SHM 경로의 성능 우위를 입증하지 않습니다.
[결과와 해석의 범위](evaluation/resource-performance.md)를 함께 읽으세요.
