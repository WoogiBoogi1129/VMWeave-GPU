# Rodinia 3개 비교군 실험 — 2026-10-25

Passthrough, Flyt SHM, VMWeave v0.5.3에서 NW `2048 10`과 LU `-s 2064`를 비교했다.
본 측정 18건과 별도 진단 8건의 전체 출력 해시가 native 기준과 일치했다.
이는 학습 samples/s 측정이나 Flyt 논문의 정확한 재현이 아니다.

## 결과와 해석

사전 지정한 주 지표는 **초기화를 포함한 단발 실행 시간**이다.
각 방식·워크로드당 3회 중앙값이며, 상대 처리량은 Passthrough 중앙 시간 / 해당 방식 중앙 시간이다.

| 방식 | NW 시간 | LU 시간 | NW 상대 처리량 | LU 상대 처리량 |
|---|---:|---:|---:|---:|
| Passthrough | 1.624538초 | 1.615478초 | 100% | 100% |
| Flyt SHM | 0.377979초 | 0.489624초 | 429.80% | 329.94% |
| VMWeave | 1.359958초 | 1.218818초 | 119.46% | 132.54% |

**이 순위를 GPU 연산 성능 순위로 해석하면 안 된다.** 별도 진단에서 Passthrough의
첫 할당·초기화는 약 1.60초, VMWeave는 약 0.66~0.67초였다. Flyt는 이미 할당한
가상 서버를 재사용하며 MPS를 사용했다. 각 요인의 독립적인 인과 효과를 분리한 실험은 아니다.

할당 이후 구간의 단일 진단에서는 Passthrough 대비 Flyt가 NW 8.73% / LU 3.54%,
VMWeave가 NW 4.34% / LU 1.71%였다. **추가 동기화가 들어간 단일 진단**이므로
확정 처리량이나 지속 실행 성능으로 일반화하지 않는다.
Flyt NW의 본 측정 CV는 25.92%, 실행 시간 범위는 0.247370~0.420960초였다.
추가 NW 진단 2건에서는 변동이 주로 호출 루프·나머지 호스트 처리 구간에 나타났지만,
RPC·스케줄링·서버 내부 비용의 세부 기여는 확정하지 못했다.

- [상세 보고서](REPORT.txt), [원시 CSV](raw.csv), [통계](comparison.json)
- [초기화 포함 비교 그림](comparison.png), [구간별 진단 그림](diagnostic-breakdown.png)
- [진단 원자료](diagnostic-comparison.json), [Flyt NW 변동](flyt-nw-variation.json)
- [계획](PLAN.md), [버전·이미지 digest](manifest.json), [원본 체크섬](SHA256SUMS.json)

## 환경과 측정 정의

동일 물리 GPU를 순차 사용했다. VM은 8 vCPU / 16GiB, QEMU CPU는 32–39,
원격 backend CPU는 40–43으로 고정했다. 원격 할당은 100% / 8192MiB이고,
운영 VMWeave의 50% / 2048MiB 설정은 보존했다.
Driver 580.173.02, CUDA 12.8.93, 동일 계측 바이너리와 seed 7을 사용했다.
VMWeave 소스는 `47e3b98ce1f4fd4e06005f440d12211fad376b2a`의 공개 v0.5.3이다.

순서는 P/F/V → F/V/P → V/P/F였다. 환경 전환 후 워크로드별 준비 실행 1건을
제외했고, 본 측정은 매번 새 애플리케이션 프로세스에서 실행했다.
주 시간은 `(main 진입 − ELF preinit) + (마지막 CUDA 동기화 완료 − 첫 cudaMalloc 진입)`이다.
CPU 입력 생성·출력 검증·파일 쓰기·종료 정리는 제외했다.
기존 Rodinia stdout의 타이머가 아닌 `timing.json` 기반 값을 집계한다.
커널 실행 횟수는 NW 255회, LU 385회다.

Flyt는 기록된 개발 브랜치 및 호환성 패치를 사용한 비교군이다. Guest의 누락된 libtirpc
커밋 대신 Host 커밋을 사용했고, cuDNN 9에서 제거된 미사용 wrapper를 빌드에서 제외했다.
Rust IPC 의존성의 `ftok` 문자열 종료 버그도 수정했다. SHM 데이터 경로와 제어 RPC를
사용했으며 TCP 데이터 경로로 대체하지 않았다. 근거는 manifest, 두 patch 파일,
Cargo.lock 및 qualification 로그에 보존했다. NW/LU 검증을 전체 CUDA 지원으로 확대 해석하지 않는다.

## 공개 자료 검증과 재현 범위

저장소 루트에서 Python 표준 라이브러리만으로 체크섬·원시 값·통계·출력 판정을 검증할 수 있다.
클러스터를 조회하거나 변경하지 않는다.

```sh
python3 experiments/ai-passthrough/results/20261025-rodinia-threeway/verify_results.py
```

`timed-src/`와 `diagnostic-src/`는 실제 계측 소스이고, [Rodinia 라이선스](RODINIA-LICENSE)를
함께 보존한다. 원본 archive의 해시는 [소스 식별 정보](source-provenance.json)에 있다.
`native-reference.json`은 앞선 native-host 정확성 실험의 기준 해시를 복사한 자료다.
Passthrough 성능 기준은 이 디렉터리의 새 VM 측정값이다.

`reproduction/`은 당시 사용한 **환경 전용 실행 스크립트의 보존본**이다.
절대 경로, 로컬 Guest 디스크·키·빌드 이미지·공개 Guest payload,
앞선 SGEMM 실행기 등 별도의 로컬 준비물에 의존한다. 새 clone에서 곧바로 클러스터 실험을
재실행할 수 있는 범용 실행기로 제공하는 것은 아니다. 실제 재실행에는 해당 준비물,
대상 GPU·namespace·운영 보존 조건 확인과 빌드/정확성 gate가 필요하다.
이 공개 작업에서는 GPU 실험을 다시 실행하지 않았다.

## 실패·제외·정리 기록

본 측정에는 성공한 18건만 포함하며 준비 실행 18건은 `warmup/`, 별도 진단 8건은
`diagnostic/`에 구분했다. Flyt의 libtirpc/라이브러리·netbase·IPC 준비 문제,
잘못된 LD_PRELOAD 실행, 관리 Pod hostPID 누락 및 VM 템플릿 추출 오류는
준비 단계 문제로 기록했고 본 측정으로 집계하지 않았다. root의 단계별 로그와
[로컬 전용 원본 목록·해시](local-only-inventory.json)를 함께 제공한다.

대용량 반복 실패 로그, 전체 명령 audit 및 운영 리소스 스냅샷은 로컬에 보존한다.
공개 묶음에는 선별한 근거를 포함하며, 생략된 원본을 공개 다운로드할 수 있다고 주장하지 않는다.
전체 로그 중 일부는 `.gitignore`의 `*.log` 예외로 이 결과 묶음에 명시적으로 추가했다.

[실험 정리 결과](cleanup.json)는 시험 자원 제거, GPU 드라이버·모니터·KubeVirt 설정 복원,
운영 VM·채널 UID와 설정 보존 및 `Ready` 확인을 기록한다.
이후 수행한 과거 Pod 일괄 정리 작업은 이 성능 실험 결과 묶음의 범위에 포함하지 않는다.
