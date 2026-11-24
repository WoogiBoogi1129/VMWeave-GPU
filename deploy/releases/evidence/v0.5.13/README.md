# v0.5.13 배포 검증 — 2026-11-24

중앙 Operator Helm revision **23**, chart **0.5.13**과 현재 GPU Worker에
`GPU_CORE_UTILIZATION_POLICY=default`를 적용했다. 실행 중 SM 한도 변경 기능은
배포하지 않았다. 게시 소스는 `d98e210efde8922364808a47fb2730a9524fd18b`다.

## 확인한 결과

- 공개 이미지 7개의 source revision과 digest, 공개 chart 및 릴리스 자산 SHA256을 확인했다.
- Worker 이미지 기본 환경과 실제 GPU 실행 자식 프로세스에서 `default`를 확인했다.
- Worker 실행 바이너리와 마운트된 HAMi 라이브러리는 기존 해시와 일치한다.
- GPU2 예약 **25%, 1024 MiB, 1슬롯**, VM/PVC와 GPU UUID를 보존했다.
- GPU 복사·PTX 커널 정답 확인과 SGEMM 전체 결과 검증을 통과했다.
  두 테스트 뒤 Broker 세션이 회수됐고 시험 namespace는 삭제했다.
- Guest 라이브러리와 Device Plugin **0.1.4 / Helm revision 5**, helper/hook 이미지는 유지했다.
- CRD spec, HAMi/DRA Helm 값과 무관한 실행 Pod **119개**의 UID·재시작 횟수는 같다.
  기존 Draining Channel 3개도 유지했다.
- 로컬 Operator race/vet, control plane 138개(1 skipped), deployment 21개,
  문서·레이아웃 검사와 GitHub Actions 12개가 통과했다.

## 배포 절차와 범위

유휴 상태를 확인한 `vmweave-test-b/dp-dev-20261105`만 정상 종료했다.
기존 Channel의 회수 완료 후 새 immutable Profile/Request `dp-dev-20261105-v0513`과
새 Channel로 Worker를 생성하고 VM을 재기동했다. 이전 Profile/Request는 롤백용으로
남겼다. VM cloud-init의 channel layout 식별자만 새 allocation/generation으로 갱신됐다.

이번 작업에서 특권 관리 Pod, `chroot`, 타 Pod의 `nsenter`·라이브러리 바인드 마운트나
호스트 이미지 삭제를 사용하지 않았다. 기존 Worker에서 노출된 라이브러리의 해시를 읽어 비교했다.

`default`는 HAMi 모니터의 경쟁 신호에 의존한다. **유휴 SM 초과 사용 성능이나
경쟁 상황의 제한 동작, DRA 모니터 연동은 이번에 측정하지 않았다.**
현재 설정과 지원 GPU 연산의 정상 실행을 확인한 기록이며, 과거 작업의 모든 호스트 변경을
감사한 결과가 아니다. 이전 릴리스의 성능·호환성 제한은 그대로 적용된다.

## 증거 재검증

```bash
python3 deploy/releases/evidence/v0.5.13/validate.py
```

`artifacts.json`은 이 디렉터리의 파일 SHA256 목록이다. 검증기는 공개 자산 식별자,
릴리스 기록, 실행 프로세스 환경, GPU 정답·종료 코드, 자원 보존을 상호 확인한다.
`live-state.json`, `validation.json`, `preservation.json`은 필요한 필드만 보존한 기록이다.
전체 Kubernetes 스냅샷과 보류한 개발 코드의 SHA256 백업은 작업 노드의
`/home/ubuntu/taeuk/backups/vmweave-default-policy-20261124/`에 있다.
