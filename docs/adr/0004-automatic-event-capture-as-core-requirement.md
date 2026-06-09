# ADR 0004: Automatic Event Capture를 핵심 requirement로 채택

## 상태

Accepted

## 결정

integration이 허용하는 범위에서 automatic workflow event capture는 WorkState의 핵심 product requirement이다.

manual checkpoint는 fallback과 repair 수단으로 사용할 수 있도록 유지하지만, 의도한 주요 UX는 아니다.

## 근거

manual checkpoint만으로는 충분한 제품 가치를 제공하지 못한다. 사용자가 `phase`, `waiting_for`, `next_action`을 반복해서 기록해야 한다면 WorkState는 단순한 메모보다 실질적으로 낫지 않다.

WorkState는 integration이 허용하는 범위에서 ChatGPT, Codex, Git, GitHub, CI와 관련 tool의 객관적 event를 수집해야 한다. 이러한 integration은 부분적일 수 있고 adapter별로 다를 수 있으므로 event model은 특정 tool에 종속되지 않아야 한다.

불확실한 해석이 객관적 fact를 덮어써서는 안 된다. 해석을 수정할 때에는 해당 해석을 도출한 observed evidence를 보존하면서 corrective information 또는 override를 기록한다.

## 결과

- resume view가 주된 제품 경험이 된다.
- `likely_waiting_for`는 source-of-truth data로 수동 입력하는 값이 아니라 evidence와 confidence에서 도출하는 값이다.
- 최종 구현 세부 사항을 확정하기 전에 M0에서 integration feasibility를 검증해야 한다.
- local-only workflow, capture 실패, repair를 위해 manual checkpoint가 계속 필요하다.
