# Codex Hooks Lifecycle Capture Spike

## Hypothesis

WorkState can use official project-local Codex hooks to capture objective
Codex lifecycle facts locally without disrupting normal Codex workflow.

This is an M0 feasibility spike. It is not the final WorkState runtime,
schema, database, event store, or workflow-state inference engine.

## Hook Events

The project-local hook configuration lives in `.codex/hooks.json` and covers:

- `SessionStart`
- `UserPromptSubmit`
- `PostToolUse` for `Bash`, `apply_patch`, and the documented `Edit`/`Write`
  matcher aliases
- `Stop`

Every command hook sets `timeout` to `5` seconds. The recorder is
observational and fail-open.

Project-local hooks require Codex review and trust before execution. Use
`/hooks` in Codex to review and trust the configured command hooks. Do not use
`--dangerously-bypass-hook-trust` for normal dogfooding.

## Event Log

The recorder writes one normalized JSON object per line outside the repository.

Override path:

```sh
WORKSTATE_CODEX_EVENT_LOG=/absolute/path/to/codex.jsonl
```

Default path:

```sh
$XDG_DATA_HOME/workstate/events/codex.jsonl
```

Fallback path:

```sh
~/.local/share/workstate/events/codex.jsonl
```

Where the platform permits, the parent directory is created with `0700`
permissions and the JSONL file with `0600` permissions. Each record is appended
with one write.

## Recorded Fields

Common fields include:

- `schema_version`
- `recorded_at`
- `source`
- `hook_event_name`
- `session_id`
- `turn_id`
- `cwd`
- `repo_root`
- `model`
- `permission_mode`
- `event_data`

`SessionStart` may not include `turn_id`; correlate it by `session_id`.
Turn-scoped events such as `UserPromptSubmit`, `PostToolUse`, and `Stop`
preserve `turn_id` when Codex provides it. Missing optional fields remain
`null`.

`SessionStart` records the official input `source` as
`session_start_source`.

`Edit` and `Write` are treated only as matcher aliases for `apply_patch`; the
persisted `tool_name` is canonicalized to `apply_patch`.

`PostToolUse` records whether `tool_response` was present, but it does not
persist or parse the raw response.

`Stop` preserves the official boolean `stop_hook_active` input. It does not
default a missing value to `true`.

## Privacy Behavior

The recorder does not persist:

- raw user prompts
- raw assistant messages
- full transcripts
- full Bash commands
- full tool payloads or responses
- source file contents
- credentials or secrets

The recorder does not read or parse `transcript_path`.

`UserPromptSubmit` stores prompt length and a SHA-256 digest. It also detects a
conservative visible `WorkState-Handoff-ID` header when present.

`Stop` stores assistant-message presence, length, and SHA-256 digest when the
message is present.

## Stdout And Fail-Open Behavior

The configured argv hook event name is authoritative. If stdin
`hook_event_name` is missing or differs, the recorder writes a sanitized
diagnostic to stderr, persists no event, and exits successfully.

The recorder also validates minimum event-specific input before persistence.
When required input is missing or has the wrong type, it writes a sanitized
diagnostic to stderr, persists no event, and exits successfully.

For `Stop`, the recorder emits compact valid JSON:

```json
{"continue":true}
```

It never returns `decision: "block"` and never asks Codex to continue a turn
with additional work after a turn should stop normally.

## Automated Validation

Run:

```sh
python3 -m json.tool .codex/hooks.json >/dev/null
python3 -m compileall spikes tests
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## Inspect The JSONL

Use the configured log path or default path:

```sh
tail -n 20 "$WORKSTATE_CODEX_EVENT_LOG"
```

Or with the default fallback:

```sh
tail -n 20 "${XDG_DATA_HOME:-$HOME/.local/share}/workstate/events/codex.jsonl"
```

## Disable Or Remove

To disable this spike, remove `.codex/hooks.json` or disable hooks in Codex
configuration:

```toml
[features]
hooks = false
```

## Manual Dogfooding Procedure

1. Review and trust project hooks with `/hooks`.
2. Start or resume a Codex session in this repository.
3. Submit a plan-mode prompt.
4. Run a turn that uses `apply_patch` or its supported alias.
5. Allow the turn to stop normally.
6. Inspect the JSONL outside the repository.
7. Verify event ordering and `session_id`/`turn_id` correlation where provided.
8. Inspect whether Plan mode is observable in hook payloads, including whether
   `permission_mode` differs from Default mode.
9. Verify raw prompt and assistant content are absent.
10. Record the result below.

## Spike Results

Live Codex verification was completed against:

```text
codex-cli 0.137.0
```

### Confirmed Capabilities

- All four configured lifecycle event types were observed:
  `SessionStart`, `UserPromptSubmit`, `PostToolUse`, and `Stop`.
- Multiple events from one session shared the same `session_id`.
- Separate turns had distinct `turn_id` values.
- Turn-scoped events correlated correctly by `turn_id`.
- `SessionStart` had no `turn_id`, as expected.
- `PostToolUse` captured a file-edit operation as canonical
  `tool_name: apply_patch`.
- Additional `PostToolUse` events for `Bash` were captured.
- JSONL was written outside the Git repository under the default
  `~/.local/share/workstate/events/` location.
- Raw-field inspection found none of these persisted raw fields: `prompt`,
  `last_assistant_message`, `tool_input`, `tool_response`, `transcript`,
  `transcript_path`, or `command`.
- Both tested turns ended normally, and no hook-caused interruption was
  observed.

### Unmet Expectation / Limitation

- Plan mode was tested twice, including an isolated retest.
- In the isolated retest, the observed sequence was `SessionStart`,
  `UserPromptSubmit`, and `Stop`.
- The Codex UI was in Plan mode, but all observed Plan-mode records reported
  `permission_mode: default`.
- The earlier Plan-mode turn also reported `permission_mode: default`.
- For `codex-cli 0.137.0`, this spike did not demonstrate that the hook payload
  field `permission_mode` can distinguish Plan mode from Default mode.
- The recorder preserves the supplied `permission_mode` value and does not
  translate it.
- Hook latency was not formally benchmarked.

Codex lifecycle event capture feasibility was demonstrated. Reliable Plan-mode
identification through `permission_mode` was not demonstrated. This is a
partial-success result rather than proof of every original success criterion.

## Known Limitations

- Fixture tests validate the recorder, not live Codex invocation behavior.
- Live dogfooding did not validate reliable Plan-mode identification through
  `permission_mode` in `codex-cli 0.137.0`.
- `Bash` events are observed tool completions only; they do not imply file
  changes.
- The schema is provisional and scoped to this spike.
- No derived workflow state, ChatGPT integration, GitHub polling, snapshot
  materialization, database, or production runtime is included.
