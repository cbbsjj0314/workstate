# WorkState

WorkState는 개인 repository를 위한 local-first workflow 복구 도구이다.

integration이 허용하는 범위에서 관찰 가능한 workflow event를 자동으로 수집하고, 그 사실로 repository snapshot을 계산하며, resume 시 derived workflow status를 보여주도록 설계한다.

핵심 resume 질문은 다음과 같다.

> 무엇이 누구의 처리를 기다리고 있는가? (`What is waiting for whom?`)

이 질문의 답은 observed event와 repository snapshot에서 도출한다. 수동으로 유지하는 source-of-truth field로 사용하려는 것이 아니다.

## 제품 방향

WorkState는 사용자가 다음 정보를 복구할 수 있도록 해야 한다.

- 최근에 발생한 일
- local working tree에 남아 있는 내용
- commit된 내용과 commit되지 않은 내용
- branch가 push되었는지 여부
- PR 존재 여부
- validation과 CI 상태
- 실행 중인 작업이 있는지 여부
- 마지막으로 작업한 actor
- 누구의 처리가 필요할 가능성이 높은지
- 아직 확인이 필요한 해석

자동 수집이 누락되거나 불완전하거나 잘못된 경우를 위해 manual checkpoint는 fallback 또는 repair 수단으로 유지한다. 이는 의도한 주요 UX가 아니다.

## 핵심 모델

WorkState는 다음 네 계층을 분리한다.

- observed events: integration 또는 local tool에서 수집한 객관적 사실
- repository snapshot: 결정론적으로 계산한 현재 repository 상태
- derived workflow state: evidence와 confidence를 바탕으로 추론한 workflow 의미
- optional recommendation: 객관적 사실이 아닌 제안된 next action

현재 dogfooding 환경에서는 약 3개의 repository를 사용할 수 있지만, WorkState는 N개의 repository를 지원하도록 설계한다. 모델을 ChatGPT, Codex, GitHub, CI, PR 또는 현재 dogfooding 개수에 하드코딩해서는 안 된다.

## 현재 상태

이 repository에는 product contract와 세 가지 초기 M0 feasibility spike 결과가 있다. 이 spike들은 feasibility evidence를 제공하지만 production integration이나 final architecture를 구현한 것은 아니다.

- Codex hooks spike는 Codex lifecycle event capture feasibility를 입증했다. `SessionStart`, `UserPromptSubmit`, `PostToolUse`, `Stop`을 관찰했고 Git repository 외부 JSONL 기록을 입증했다. 그러나 Plan mode 기록도 `permission_mode: default`를 보고했으므로 `permission_mode`를 통한 신뢰할 수 있는 Plan-mode 식별은 입증하지 못했고, hook latency도 정식 benchmark하지 않았다. Plan-mode detection이 해결되지 않아 Issue #5는 open 상태이다.
- ChatGPT MCP spike는 ChatGPT Plus custom app 연결과 tool discovery, 명시적인 `health_check` read 호출, 한 번의 간접 `record_observation` write 성공을 입증했다. 의미상 유사한 명시적 write는 차단되었다고 보고되었고, 신뢰할 수 있거나 예측 가능한 write invocation은 입증하지 못했다. 최종 결과는 `Outcome C`이며 production WorkState ChatGPT adapter가 아니다.
- Git/GitHub collector spike는 사용자의 정상 authenticated terminal 환경에서 read-only 수집에 성공했다. local Git state, GitHub repository identity, branch publication state, SHA-correlated draft PR state, completed CI check buckets를 수집했고 GitHub 수집이 unavailable 또는 partial인 경우에도 local Git evidence를 보존했다. Codex execution environment에서는 사용자의 정상 `gh` credentials에 접근할 수 없었지만 이는 정상 user-terminal 수집 실패가 아니라 execution-environment limitation이다. 이 collector는 final runtime collector나 final persisted schema가 아니다.

아직 다음 항목은 구현하지 않았다.

- production runtime CLI
- final persisted schema
- event store
- snapshot materialization runtime
- derived workflow-state engine
- inference engine
- recommendation engine
- production ChatGPT integration
- production Codex integration
- production GitHub polling service
- multi-repository runtime registry
- background daemon

의도한 `workstate resume`, `workstate status`, `workstate events`, `workstate inspect`, `workstate confirm`, `workstate repair`, `workstate checkpoint` command는 여전히 conceptual contract이며 실행 가능한 runtime command가 아니다.

## 문서

- [문제](docs/01-problem.md)
- [Workflow 모델](docs/02-workflow-model.md)
- [Event와 snapshot 모델](docs/03-event-and-snapshot-model.md)
- [CLI contract](docs/04-cli-contract.md)
- [MVP 범위](docs/05-mvp-scope.md)
- [제품 원칙](docs/06-product-principles.md)
- [ADR](docs/adr)
