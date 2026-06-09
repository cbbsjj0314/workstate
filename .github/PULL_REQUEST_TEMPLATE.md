<!--
PR 본문은 한국어로 작성한다.

빠르게 훑어볼 수 있도록 짧고 구체적으로 쓴다.
긴 문단보다 짧은 bullet을 우선한다.
추상적인 효과보다 실제 변경 사항과 확인된 결과를 먼저 적는다.
같은 내용을 여러 section에서 반복하지 않는다.
해당하지 않는 optional section은 통째로 삭제한다.

일반 prose paragraph에 80자, 88자, 100자 등의 column limit 기반 hard wrapping을 적용하지 않는다.

object name, endpoint, route, schema, field, enum, status value, event name, API, CLI command, module, class, function, config key, environment variable, filename, directory path, package name, library name, framework name, protocol name과 기타 identifier는 번역하거나 변형하지 않는다.

Product contract를 변경하는 PR은 어떤 판단이나 invariant가 달라지는지 명확히 적는다.
Spike PR은 확인된 사실과 아직 입증하지 못한 내용을 구분한다.
Docs-only PR도 실행한 docs validation과 changed docs reread 결과를 적는다.
실행하지 않은 검증을 실행한 것처럼 적지 않는다.

PR title은 `<type>: <clear outcome>` 형식을 기본으로 한다.

권장 type:
- docs
- spike
- ci
- feat
- fix
- refactor
- test
- chore

Good examples:
- docs: translate owner-facing documentation to Korean
- docs: revise product contract around automatic event capture
- spike: collect local Git and GitHub workflow state
- ci: add docs validation and repository hygiene
- fix: preserve unpublished branch PR correlation

Avoid:
- update docs
- fix stuff
- misc changes
- WIP
-->

## Summary

<!--
이 PR이 왜 필요한지와 무엇을 바꾸는지 1~3개 bullet로 요약한다.
내부 구현 세부사항만 나열하지 말고 결과와 범위가 드러나게 쓴다.
-->

-

---

## Changes

<!--
실제로 변경한 document, command, event, schema field, adapter, source file, test 또는 workflow를 구체적으로 적는다.
-->

-

---

<!--
Product contract, architecture invariant, event/snapshot model, CLI semantics, persistence shape, privacy boundary 또는 adapter boundary가 바뀌는 경우에만 남긴다.
단순 번역이나 formatting 변경이라도 contract semantics를 의도적으로 유지했다면 그 사실을 짧게 적을 수 있다.
해당하지 않으면 이 section을 삭제한다.
-->

## Contract impact

- Affected contract:
- Semantic change: Yes / No
- Compatibility or migration impact:
- Canonical reference:

---

<!--
Feasibility spike, external integration probe, dogfooding 결과 또는 불확실한 동작을 다루는 PR에서만 남긴다.
확인된 사실과 아직 입증하지 못한 내용을 구분한다.
해당하지 않으면 이 section을 삭제한다.
-->

## Evidence / Limitations

- Confirmed:
- Not demonstrated:
- Test environment or relevant versions:

---

## Validation

<!--
`command or check: result` 형식으로 작성한다.
실행한 command와 실제 결과만 적는다.
실행하지 않은 검증은 이유와 함께 `not run`으로 표시한다.

Repository의 주요 GitHub Actions check:
- `Validate docs and examples`
- `Validate Python spikes`
- `Validate ChatGPT MCP spike`

예:
- `git diff --check`: passed
- `python3 -m unittest discover -s tests -p 'test_*.py' -v`: passed
- changed docs reread: passed
- `Validate docs and examples`: passed
- runtime tests: not run, docs-only change
-->

-

---

<!--
리뷰어가 특히 확인해야 하는 내용, 의미가 바뀌기 쉬운 부분, 외부 환경 의존성, privacy/security caveat 또는 불확실한 가정이 있을 때만 남긴다.
단순히 Summary나 Validation을 반복하지 않는다.
해당하지 않으면 이 section을 삭제한다.
-->

## Review focus / Risks

- Review focus:
- Risk: Low / Medium / High
- Assumptions or caveats:

---

<!--
이번 PR과 인접하지만 의도적으로 포함하지 않은 작업이 있을 때만 남긴다.
범위가 자명하거나 후속 작업이 없다면 이 section을 삭제한다.
-->

## Out of scope / Deferred

-
