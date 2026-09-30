# 사용자 namespace 등록

`management.namespaces`에 등록한 namespace만 중앙 Operator가 관리합니다.
같은 목록으로 cache 범위, Webhook selector, RoleBinding을 생성합니다.
중앙 ServiceAccount가 대상 namespace의 권한을 받으며 별도 Controller는 생성하지 않습니다.

새 설치에서는 `team-a`, `team-b` 등을 먼저 만들고 설치 values에 지정합니다.
사용자에게 Profile 승인 권한이나 system namespace의 SA를 부여하지 않습니다.

```sh
kubectl auth can-i update virtualmachines.kubevirt.io -n team-a \
  --as=system:serviceaccount:vmweave-system:vmweave-controller
kubectl auth can-i create pods -n unrelated \
  --as=system:serviceaccount:vmweave-system:vmweave-controller
```

active 설치의 첫 결과는 `yes`, 미등록 namespace의 결과는 `no`여야 합니다.
review 설치에서는 workload 수정이 거부됩니다.

현재 설치 도구는 이미 설치된 release의 관리 목록/모드 변경을 자동 처리하지 않고 거부합니다.
변경은 [유지보수 절차](../guides/upgrade-uninstall.md)에 따라 회수 후 수행합니다.
빈 목록은 전체 클러스터 관리라는 의미가 아니며 허용되지 않습니다.
