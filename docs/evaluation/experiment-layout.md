# 새 실험 자료의 구조와 공개 규칙

이 규칙은 새 campaign에 적용한다. 기존 실행기의 위치·결과·SHA256 목록은 변경하지 않는다.
과거 결과의 상태는 해당 실행 보고서를 따르며 새로운 코드의 검증으로 재해석하지 않는다.

```text
experiments/<topic>/
  README.md                  # 목적, 상태, 실행 진입점, 결과 목록
  plans/                     # 사전 조건·비교군·측정 경계
  runner/                    # 실행·수집·분석 도구
  workloads/                 # 입력·workload 소스·이미지 정의
  results/<run-id>/
    REPORT.md                # 조건·결과·실패·제외·한계
    manifest.json            # commit, image digest, 입력, 실행 명령
    SHA256SUMS               # 보존하는 파일의 bytes 기준
```

작은 실험은 필요한 항목만 만든다. 실행 시각·정확한 source SHA·미커밋 변경 여부·GPU/환경 식별자·
이미지 digest·warm-up·반복 수·시간 측정 경계·실패/중단/대체 내역을 남긴다.
과거 결과를 덮어쓰지 않고 재실행마다 새 run-id를 사용한다.

Git에는 보고서, 소스, 재현 설정, 요약 CSV, 선별 그림, manifest와 checksum을 우선 포함한다.
새 대용량 원시 로그·영상·시계열은 Release 또는 지속 보존 가능한 데이터 저장소 사용을 먼저 검토한다.
10 MiB 이상 신규 파일은 저장 위치를 명시적으로 검토하는 프로젝트 기준으로 삼는다.
이는 GitHub 업로드 제한이 아니며 기존 원본을 삭제하라는 규칙도 아니다.

외부 묶음을 사용하면 manifest에 아래 항목을 기록한다.

| 필드 | 내용 |
|---|---|
| `sourceRevision` | 재현 코드의 정확한 커밋 |
| `artifacts[].url` | 안정적으로 접근 가능한 다운로드 URL |
| `artifacts[].bytes` | 압축 파일 자체의 길이 |
| `artifacts[].sha256` | 다운로드한 압축 파일 자체의 SHA256 |
| `artifacts[].description` | 원본/파생 자료 구분과 포함 범위 |

공개 전에 실제 다운로드와 hash 대조를 확인한다. 로그인 필요 여부·보존 책임도 보고서에 기록한다.
Actions의 단기 artifact만 논문 원본의 영구 주소로 사용하지 않는다.

체크섬 대상에는 `.gitattributes`의 `-text`를 적용해 checkout 시 개행 변환을 방지한다.
원본 source까지 checksum에 포함했다면 그 경로도 보호한다. `-whitespace`는 캡처·패치처럼
원래 공백 보존이 필요한 경우에만 적용한다. attributes 변경만으로 과거 파일을 재정규화하지 않는다.

결과를 등록할 때 [실험 진입점](../../experiments/README.md)과 [증거 색인](catalog.md)을 갱신한다.
연구 근거에는 해당 보고서 경로·커밋·hash를 함께 남긴다.
[보존 정책](artifacts.md) · [역사 문서 경로 안내](../history/link-map.md)
