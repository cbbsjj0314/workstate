# Documentation Style Guide

## 목적과 책임 경계

이 guide는 WorkState 문서의 독자, 언어, literal 보존, formatting, validation 판단을 일관되게 만든다. Product semantics, schema, API, CLI behavior, runtime behavior를 재정의하지 않으며, repository-level agent instruction의 source of truth는 `AGENTS.md`이고 PR body expectation의 source of truth는 `.github/PULL_REQUEST_TEMPLATE.md`이다.

## 적용 범위

이 guide는 durable documentation, docs-like example, PR body, 향후 documentation Koreanization 작업에 적용한다.

Runtime과 source code behavior, schema/API/CLI semantics, UI/API/client-visible copy, source comment와 docstring, test expectation은 후속 task가 명시적으로 포함하지 않는 한 범위에서 제외한다.

## Primary reader 분류

- `operator_facing`: WorkState를 운영하고 workflow를 복구하는 owner가 주 독자이다.
- `agent_facing`: coding agent가 구현과 검증 경계를 정확히 따르는 데 쓰는 문서이다.
- `public_facing`: repository 외부 독자에게 project 목적과 사용법을 설명하는 문서이다.
- `developer_facing`: code, test, configuration, protocol과 정확히 맞아야 하는 구현 문서이다.
- `mixed_reader`: 둘 이상의 독자 목적이 공존하여 section별 판단이 필요한 문서이다.

## Translation decision 분류

- `translate_korean_first`: durable owner-facing prose를 Korean-first로 작성한다.
- `keep_english`: source code, test, configuration, protocol, upstream terminology와 wording이 맞아야 하는 내용을 English로 유지한다.
- `preserve_literals_only`: 설명은 번역할 수 있지만 identifier와 exact literal은 원문 그대로 유지한다.
- `split_by_section`: mixed-purpose document를 section의 primary role에 따라 다르게 처리한다.
- `defer_to_separate_scope`: 현재 task의 semantic 또는 review 범위를 벗어나는 번역은 별도 작업으로 미룬다.

## Inventory classification

Documentation Koreanization은 번역 전에 inventory classification부터 수행한다. 각 관련 파일에 primary reader와 translation decision을 먼저 지정하고, `mixed_reader` 문서는 필요하면 section별 decision을 기록한다. 모든 문서를 기계적으로 번역하지 않는다.

## Literal / identifier 보존 규칙

Object name, endpoint와 route, schema, table, model, view, API, CLI command, module, class, function, method, field, enum value, status value, event name, config key, environment variable, filename, path, directory path, package, library, framework, protocol의 repository spelling을 보존한다. 예를 들어 `likely_waiting_for`, `agent_reported_complete`, `observed events`, `git diff --check`를 번역하거나 변형하지 않는다.

Code block, inline code, command output, JSON/YAML key, SQL fragment, URL, exact literal은 번역하거나 변경하지 않는다.

## Markdown formatting 규칙

- Normal prose paragraph에 column-limit 기반 hard wrapping을 적용하지 않고 기존 paragraph style을 보존한다.
- Heading, list, blockquote, table, code block, YAML, JSON, shell command, literal content에 필요한 structural line break는 보존한다.
- Korean documentation은 `~이다`, `~한다`, `~해야 한다`와 같은 concise declarative style을 사용한다.
- 명시적 요청이 없으면 repository documentation에 `~입니다`, `~합니다`, `~하세요` 같은 honorific ending을 사용하지 않는다.

## Privacy/security boundary

Public/tracked docs, example, PR body, issue, log, fixture, committed file에 private local path, raw prompt, assistant message, transcript, secret, credential, token, authorization value, sensitive raw remote URL, account detail, sensitive runtime output, full tool payload를 노출하지 않는다. Example은 sanitized and bounded value만 사용한다. Raw, private, local-only evidence를 public-facing documentation의 근거로 승격하지 않는다.

## Docs-code consistency 확인

Schema, API, CLI, event, status value, command, test, workflow, spike result를 설명하는 문서는 current repository evidence와 대조한다. Confirmed behavior, provisional design, hypothesis, unresolved limitation을 구분하며, evidence가 뒷받침하지 않는 spike result를 general product capability로 서술하지 않는다.

## Validation

Docs-only change에서는 다음을 수행한다.

- `git diff --check`
- `.github/workflows/docs.yml` inspection
- 적용 가능한 `.github/workflows/docs.yml` safe local check
- Changed documentation reread

실제로 성공한 check만 passed로 보고한다. Package installation과 unrelated runtime test는 docs-only style guide change에 필요하지 않다.

## PR body / commit title

PR body는 `.github/PULL_REQUEST_TEMPLATE.md`를 따르고 applicable section만 남긴다. Korean-first로 짧고 구체적으로 작성하며 실제 변경과 validation result에 근거해야 한다. PR title과 commit title은 `<type>: <clear outcome>` 형식을 사용하고 full template을 이 guide에 복제하지 않는다.

## Agent checklist

- [ ] `AGENTS.md`와 이 guide를 읽는다.
- [ ] Primary reader를 분류하고 translation decision을 선택한다.
- [ ] Identifier와 literal을 보존한다.
- [ ] Broad reformatting을 피한다.
- [ ] Privacy/security boundary를 지킨다.
- [ ] 적용 가능한 docs validation을 실행한다.
- [ ] Changed files, validation, semantic impact, deferred scope를 보고한다.

## Completion criteria

- Translation 전에 documentation reader intent를 분류했다.
- Identifier 또는 literal spelling을 의도치 않게 변경하지 않았다.
- Documentation wording으로 schema/API/CLI/runtime semantics를 변경하지 않았다.
- Private, local, sensitive evidence를 노출하지 않았다.
- 적용 가능한 docs validation을 실행했거나 실행하지 못한 이유를 명시했다.
