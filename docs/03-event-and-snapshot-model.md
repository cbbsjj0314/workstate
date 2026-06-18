# Event And Snapshot Model

이 문서는 WorkState의 canonical conceptual data-model contract이다.

이 문서는 final production schema, enum set, migration format, event-store implementation, immutability mechanism, replay architecture, persistence format을 정의하지 않는다. 이러한 세부 사항은 M0와 M1에서 검증해야 한다.

## Layers

WorkState는 다음 layer를 구분한다.

- observed events
- repository snapshots
- derived workflow state
- optional recommendations

Fact와 interpretation은 서로 다른 layer이다.

## Observed Events

Observed event는 integration 또는 local tool에서 직접 포착한 objective fact이다.

예:

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

Objective name을 사용해야 한다. Observation만 발생했는데 semantic success를 암시하는 name은 피해야 한다.

Naming 규칙:

- `file_changes_observed`를 `local_changes_applied`보다 우선한다.
- integration이 authoritative plan-completed event를 제공하지 않는 한 `plan_output_observed`를 우선한다.
- `agent_reported_complete`는 validation success 또는 work-item completion과 구분한다.

## Repository Snapshot

Repository snapshot은 현재 repository state의 deterministic summary이며 event가 아니다.

Conceptual example은 다음과 같다.

```yaml
working_tree:
  has_changes: true
  changed_file_count: 4

commit:
  latest_commit: null

remote:
  pushed: false

pull_request:
  exists: false

validation:
  status: not_observed

execution:
  active_actor: none
  last_actor: codex
  last_event: agent_turn_completed
```

`validation_not_observed`는 event가 아니라 snapshot value이다.

## Derived Workflow State

Derived workflow state는 observed events와 repository snapshots에서 계산한 workflow 의미이다.

Conceptual example은 다음과 같다.

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
  provenance:
    source: rule
  interpretation_status: inferred
```

`likely_waiting_for`는 중요한 product concept이지만 derived value이다. Objective source-of-truth field로 취급해서는 안 된다.

위 evidence shape은 conceptual example이다. Final persisted schema를 정의하지 않으면서 event evidence와 snapshot evidence를 구분한다.

Derived state는 다음 정보를 노출해야 한다.

- provenance
- evidence
- confidence or certainty
- interpretation status

## Provenance And Interpretation Status

다음 term을 정확하게 사용해야 한다.

- `observed`: integration 또는 local tool에서 직접 포착한 event
- `inferred`: evidence에서 도출한 workflow interpretation
- `confirmed`: user가 수락한 inferred interpretation
- `overridden`: user가 수정한 inferred interpretation 또는 previously confirmed interpretation

Observed fact는 `confirmed` 또는 `overridden`으로 transition하지 않는다. Interpretation은 inferred, confirmed, overridden 상태가 될 수 있다. Interpretation correction은 corrective information을 additively 기록하며 supporting observed events를 삭제하지 않는다.

## Proposal Behavior

Proposal은 uncertain interpretation에만 사용한다.

- Objective event는 관찰되면 자동으로 기록해야 한다.
- Deterministic snapshot update는 자동으로 계산해야 한다.
- Uncertain semantic interpretation은 proposal을 생성한다.
- Product-mode confirmation은 workflow boundary 또는 `resume` 중에 batch 처리한다.
- Spike-mode immediate confirmation은 precision과 recall을 측정하는 데 사용할 수 있다.

Unconfirmed proposal은 `resume` 중에 보여야 한다.

## Optional Recommendation

WorkState는 next action을 제안할 수 있지만 이를 objective fact로 제시해서는 안 된다.

Conceptual example은 다음과 같다.

```yaml
recommendation:
  action: review_diff
  source: rule
  confidence: medium
```

WorkState는 plan의 적절성, change의 requirement 충족 여부, code quality의 수용 가능 여부, 추가 revision 필요 여부, PR merge 여부, work item의 실제 완료 여부를 결정하는 user, reviewer, coding agent의 판단을 대체하지 않는다.

## Handoff Correlation

Stable handoff ID는 여러 tool의 related event를 correlate할 수 있다.

```text
WorkState-Handoff-ID: ws_01J...
```

목적은 다음과 같은 observation을 연결하는 것이다.

```text
ChatGPT: revision prompt created
Codex: revision prompt received
```

Visible header는 M0 spike에서 허용된다. Final UX는 가능한 경우 이 metadata를 자동으로 전달해야 한다. User가 handoff ID를 직접 관리해서는 안 된다.

Content hash에만 의존하는 방식보다 random stable ID가 권장된다. Correlation에 raw prompt content가 필요해서는 안 된다.

이 문서는 final wire protocol을 정의하지 않는다.

## Privacy Defaults

Default persisted data는 다음 항목으로 제한해야 한다.

- event type
- repository identity
- source session or turn ID
- timestamp
- stable correlation ID
- content hash or local HMAC where useful
- short redacted summary

Raw ChatGPT 또는 Codex prompt content는 opt-in이어야 한다. WorkState는 credentials, secrets, full source code를 기본적으로 저장해서는 안 된다.
