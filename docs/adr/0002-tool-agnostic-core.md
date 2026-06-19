# ADR 0002: Tool-Agnostic Core

## 상태

Accepted

## 결정

WorkState는 core workflow model을 tool-agnostic하게 유지한다.

## 근거

현재 ChatGPT는 planning session이고 Codex는 delegated AI agent이다. 이들은 workflow profile이지 영구 requirement가 아니다. core model은 non-Codex agent, non-GitHub workflow, local-only 작업, manual planning도 지원해야 한다.

## 결과

- core state는 `planning_session`, `ai_agent`와 같은 generic actor를 사용한다.
- ChatGPT, Codex, GitHub, PR, CI, review, Git 세부 정보는 optional context 또는 external signal이다.
- 향후 workflow profile은 해당 tool을 같은 core field에 mapping할 수 있다.
