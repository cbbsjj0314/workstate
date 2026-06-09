# ADR 0003: SQLite보다 YAML/JSON 우선

## 상태

초기 inspectability를 위한 선호로 Accepted 상태이다. final persisted schema와 storage format은 M0와 M1에서 계속 검증해야 한다.

## 결정

WorkState는 SQLite 또는 다른 storage 방식을 도입하기 전에 초기 example, spike 또는 local-first inspection에 YAML/JSON을 사용할 수 있다.

## 근거

product contract는 아직 validation 중이다. 사람이 읽을 수 있는 example을 사용하면 WorkState가 automatic event capture, repository snapshot, derived workflow state, repair flow를 검증하는 동안 모델을 쉽게 inspect, edit, diff, review할 수 있다.

## 결과

- conceptual example은 투명성과 local-first 특성을 유지할 수 있다.
- YAML/JSON example은 final persisted schema를 정의하지 않는다.
- M0/M1 validation 결과로 필요성이 확인되면 나중에 SQLite 또는 다른 storage 방식을 도입할 수 있다.
