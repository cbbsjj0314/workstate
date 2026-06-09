# ADR 0001: Local-First Manual Checkpoint

## 상태

Superseded 상태이며 [ADR 0004](0004-automatic-event-capture-as-core-requirement.md)로 대체되었다.

## 원래 결정

WorkState는 manual checkpoint를 사용하는 local-first 도구로 시작했다.

## 변경된 해석

manual checkpoint는 fallback과 repair 수단으로 여전히 유용하지만, 의도한 주요 UX는 아니다.

현재 product contract는 integration이 허용하는 범위에서 workflow event를 자동으로 수집할 것을 요구한다. capture가 불가능하거나 불완전하거나 모호하거나 잘못된 경우 수동 입력으로 누락된 context, corrective information 또는 override를 추가해야 한다.

## 결과

- local-first 복구는 계속 핵심 requirement로 유지한다.
- manual checkpoint는 더 이상 MVP의 주요 workflow가 아니다.
- observed event history, repository snapshot, derived workflow state, batched interpretation confirmation이 현재 제품 방향을 정의한다.
