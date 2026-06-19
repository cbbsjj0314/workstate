# Workflow 모델

WorkState는 N개 repository의 repository 단위 workflow 복구를 모델링한다.

의도한 제품 동작은 integration이 허용하는 범위에서 관찰 가능한 workflow event를 자동으로 수집하는 것이다. 초기 M0 feasibility spike는 mixed evidence를 만들었다. Codex lifecycle capture는 Plan-mode 식별 limitation과 함께 입증되었고, ChatGPT MCP 결과는 신뢰할 수 있는 write invocation을 입증하지 못한 `Outcome C`이며, Git/GitHub collector는 정상 authenticated terminal 환경에서 입증되었다. 이 문서는 여전히 production 구현 기능이 아니라 product contract를 설명한다.

## Actor와 adapter

핵심 모델은 특정 adapter에 종속되지 않는다.

- `user`: 작업을 결정하고 승인하는 human operator이다.
- `planning_session`: 현재는 ChatGPT이며, 향후 workflow profile에서는 일반적인 planning actor 또는 session이다.
- `ai_agent`: 현재는 Codex이며, 향후에는 다른 delegated AI agent일 수 있다.
- `ci`: workflow에서 CI를 사용하는 경우의 automated check이다.
- `reviewer`: review를 담당하는 사람 또는 process이다.
- `external_system`: 관찰 가능한 signal을 제공할 수 있는 모든 non-core system이다.

ChatGPT, Codex, Git, GitHub, CI는 중요한 integration 대상이지만 adapter이다. 핵심 event model을 이러한 tool에 영구적으로 종속해서는 안 된다.

## 모델 계층

WorkState는 네 계층을 분리한다.

1. Observed events

   integration 또는 local tool에서 직접 수집한 사실이다.

   예시는 다음과 같다.

   - `planning_prompt_created`
   - `agent_prompt_submitted`
   - `agent_turn_completed`
   - `plan_output_observed`
   - `file_changes_observed`
   - `commit_created`
   - `branch_pushed`
   - `pr_created`
   - `pr_merged`
   - `validation_started`
   - `validation_passed`
   - `validation_failed`
   - `ci_pending`
   - `ci_passed`
   - `ci_failed`
   - `agent_reported_complete`

   event name은 의미상 성공이 아니라 관찰한 사실을 나타내야 한다. 예를 들어 `file_changes_observed`를 `local_changes_applied`보다 선호하고, `agent_reported_complete`는 validation 또는 work-item completion과 구분해야 한다.

2. Repository snapshot

   observed fact와 local/tool inspection으로 계산한 현재 repository 상태의 결정론적 요약이다. snapshot value는 event가 아니다. 예를 들어 `validation_not_observed`는 event가 아니라 snapshot value이다.

3. Derived workflow state

   event와 snapshot에서 추론한 workflow 의미이다. `likely_waiting_for`는 derived value이며, derived workflow state는 provenance, evidence, confidence, interpretation status를 함께 제공한다.

4. Optional recommendation

   제안된 next action이다. 객관적 사실이 아니라 제안으로 표시해야 한다.

## Resume 경험

resume view는 주된 제품 경험이다. 다음 항목을 표시해야 한다.

- observed state
- derived workflow status
- 확인 대기 중인 해석
- optional suggestion

핵심 질문은 다음과 같다.

> 무엇이 누구의 처리를 기다리고 있는가? (`What is waiting for whom?`)

답은 다음과 같은 evidence로 뒷받침해야 한다.

```yaml
derived_workflow:
  likely_waiting_for: user
  confidence: high
  evidence:
    - kind: event
      ref: agent_turn_completed
    - kind: event
      ref: file_changes_observed
    - kind: snapshot
      ref: validation.status
      value: not_observed
```

이 evidence shape는 conceptual이다. 최종 persisted schema를 정의하지 않으면서 event evidence와 snapshot evidence를 구분한다.

## Proposal 동작

객관적 event는 관찰될 때 자동으로 기록해야 한다. 결정론적인 snapshot update는 자동으로 계산해야 한다. 어느 쪽도 즉각적인 사용자 확인을 요구해서는 안 된다.

proposal은 불확실한 interpretation에만 사용한다. spike mode에서는 precision과 recall을 측정하기 위해 즉시 확인을 사용할 수 있다. product mode에서는 workflow boundary 또는 `resume` 시점에 확인을 일괄 처리해야 한다.

즉각적인 interruption은 충돌, correlation을 막는 모호함 또는 high-risk state change가 있는 경우에만 사용해야 한다.

## Manual repair

capture가 누락되거나 불완전하거나 잘못된 경우에는 수동 입력이 여전히 필요하다. repair는 corrective information 또는 override를 추가한다. observed event history를 암묵적으로 다시 쓰거나 삭제해서는 안 된다.
