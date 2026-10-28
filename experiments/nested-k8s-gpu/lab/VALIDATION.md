# 문서·실습 보조 도구 검증

검증일: 2026-10-28. 대상은 향후 **기존 `vmweave-system` 경로의 실습 문서**와 보조 도구다.
기존 실험의 기능 결과와 혼동하지 않는다. 이 작업에서 중앙 Operator 설정이나 운영 VM을 변경하지 않았다.

| 검증 | 결과·범위 |
|---|---|
| 중앙 Operator 사전 점검 | PASS. `preflight.py`를 실제 외부 context의 `vmweave-test-b`에 읽기 전용 실행. 두 구성요소 active·관리 범위·release digest·Ready·RoleBinding·admission 연결·중복 controller 범위 확인. [원본](preflight-observed-20261028.json) |
| 로컬 manifest 생성 | PASS. 임시 공개키와 가상 GPU UUID로 9개 파일 생성. 새 VM 2개 Halted·고유 firmware UUID, 지정 namespace, PV/PVC 3쌍, Profile 미승인 상태 확인. 클러스터 적용 없음 |
| 잘못된 입력 거부 | PASS. 중앙 시스템/과거 실험 namespace, 미지정 GPU UUID, 중복 CIDR, 같은 Node IP, PV 루트 `/`의 6개 입력 거부 |
| Python 구문 | PASS. 세 `lab/*.py` 파일 AST 파싱 |
| Bash 구문 | PASS. 생성된 설치기 2개와 문서의 Bash 블록 20개 `bash -n`. 명령 실행 성공을 뜻하지 않음 |
| 기존 원본 SHA256 | PASS. 실험 338개, 캡처 7개 파일 일치. 과거 원본과 해시 목록 수정 없음 |
| 문서 사이트 | `make docs-check`로 문서 계약·strict build·사이트 링크 검사; 저장소 반영 전 통과 확인 |
| 공개 자료 점검 | JSON 198개 파싱. private key·JWT·접근 토큰 형태 및 자격 정보 포함 여부 점검. kubeadm 예제 문자열과 Kubernetes Event 이름의 패턴 일치는 실제 인증정보와 구분 |

`observe_gpu.py`는 Channel/Worker UID와 호스트 cgroup·NSpid를 대조하고 관측 도중 runtime 교체를 거부한다.
구문 검증까지 수행했으며, 이 도구로 새 GPU 작업을 실행하거나 새 중앙 실습의 회수를 관측하지 않았다.

**미실행:** 중앙 Operator를 통한 새 VM 생성, Kubernetes init/join, 새 GPU binding·Pod 연산,
장애 주입·철거·장시간 안정성 시험. 따라서 이 문서와 도구가 모든 환경에서 동작한다고 보장하지 않는다.
실습 당일 권한·이미지 호환성·가용 quota·OS·망 충돌·외부 동시 변경을 다시 확인하고 새 실행 증거를 남긴다.
