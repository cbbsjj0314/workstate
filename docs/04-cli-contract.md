# CLI Contract

이 문서는 의도한 command만 정의한다. Runtime CLI를 정의하거나 구현하지 않는다.

CLI는 integration이 허용하는 범위에서 automatic capture를 지원해야 한다. 그러나 현재 integration capability는 아직 구현되거나 검증되지 않았다.

## `workstate resume`

기본 multi-repo `resume` view를 표시한다.

이 view는 다음 질문에 답해야 한다.

> What is waiting for whom?

답은 observed events와 repository snapshots에서 도출한다. 이 view는 observed state, derived workflow status, pending interpretations, optional suggestions를 구분해 표시해야 한다.

## `workstate status`

하나의 repository 또는 모든 repositories에 대한 현재 repository snapshot과 derived workflow state를 표시한다.

## `workstate events`

하나의 repository 또는 모든 repositories에 대한 최근 observed events를 표시한다.

이 command는 derived interpretation이 존재하는 이유를 설명하는 데 도움을 줘야 한다. M0에서 integrations를 검증하기 전에 event capture가 완전하다고 암시해서는 안 된다.

## `workstate inspect`

derived state, pending interpretation, recommendation의 근거를 검사한다.

## `workstate confirm`

pending interpretations를 승인하거나 거부한다.

interpretation을 confirm해도 observed facts는 변경되지 않는다. 거부 또는 수정은 interpretation status와 corrective information을 기록한다.

## `workstate repair`

automatic capture가 누락되거나 불완전하거나 모호하거나 잘못된 경우 corrective information, missing context, overrides를 추가한다.

이 command는 observed event history를 조용히 다시 쓰거나 삭제해서는 안 된다.

## `workstate checkpoint`

선택적인 manual capture fallback이다.

automatic capture를 사용할 수 없거나 workflow에 manual repair가 필요할 때 이 command는 user-supplied checkpoint를 기록할 수 있다. 이는 일반적인 primary workflow가 아니다.
