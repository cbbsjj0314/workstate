# MVP 범위

WorkState의 MVP 방향은 integration이 허용하는 범위에서 workflow를 자동으로 복구하고 manual repair를 항상 제공하는 것이다.

현재 repository에는 product contract만 있다. 아직 integration 또는 runtime CLI를 구현하지 않았다.

## M0: Integration feasibility spikes

M0에서는 의도한 capture model이 실용적인지 검증한다.

M0에서 검증해야 할 항목은 다음과 같다.

- ChatGPT MCP tool 호출 신뢰성
- Codex lifecycle event capture
- handoff correlation
- file change와 turn completion 관찰
- Git과 GitHub 상태 수집
- 확인 빈도와 UX 마찰

권장하는 spike 순서는 다음과 같다.

1. Codex hooks
2. ChatGPT MCP
3. local Git과 `gh` polling integration

M0 실험에서는 precision과 recall을 측정하기 위해 transition마다 즉시 확인할 수 있다. 이는 의도한 최종 UX가 아니다.

## M1: Dogfooding MVP

M1은 여러 repository에서 사용할 수 있어야 한다.

M1은 최소한 다음 항목을 포함한다.

- observed event history를 위한 검증된 local storage 방식
- repository snapshot
- derived workflow state
- 여러 repository를 위한 resume view
- 부분적인 ChatGPT event capture
- Codex lifecycle capture
- local Git inspection
- GitHub/CI polling
- manual repair/fallback
- 해석 일괄 확인

M1은 사용자가 일반적인 workflow 유지 작업으로 `phase`, `waiting_for`, `next_action`을 반복해서 입력하도록 요구해서는 안 된다.

## 연기한 범위

다음 항목은 M0/M1 validation 이후로 연기한다.

- final persisted schema
- event replay infrastructure
- compaction
- event migration
- distributed consistency
- production-grade event-sourcing abstraction
- handoff metadata를 위한 final wire protocol
- 광범위한 provider marketplace 또는 시장 분석

현재 목표는 완전한 event-sourcing framework나 확정된 persistence format이 아니라 논리적인 event history 보존과 snapshot materialization이다.

## 성공 기준

WorkState는 다음 조건을 만족할 때 성공한 것이다.

- integration이 허용하는 범위에서 대부분의 객관적 event를 자동으로 수집한다.
- 사용자가 `phase`, `waiting_for`, `next_action`을 반복해서 입력하지 않는다.
- 작업을 중단했다가 돌아왔을 때 repository 상태를 빠르게 복구할 수 있다.
- 확인이 드물고 일괄 처리된다.
- 잘못된 해석이 객관적 기록을 손상하지 않는다.
- resume view가 ChatGPT/Codex session을 다시 읽거나 단순한 메모를 유지하는 것보다 유용하다.
- 현재 dogfooding 개수를 하드코딩하지 않고 N개의 repository를 지원한다.

## 실패 기준

WorkState는 다음 조건에서 실패한 것이다.

- 사용자가 모든 workflow transition 후에 manual checkpoint를 실행해야 한다.
- 사용자가 ChatGPT에 상태 기록을 반복해서 요청해야 한다.
- 확인이 메모 작성보다 더 번거롭다.
- WorkState가 잘못된 의미 상태를 자주 기록한다.
- event history를 수집하지만 사용자의 작업 재개에 도움이 되지 않는다.
- automatic capture를 위해 사용자가 integration에서 이미 사용할 수 있는 데이터를 수동으로 다시 입력해야 한다.
