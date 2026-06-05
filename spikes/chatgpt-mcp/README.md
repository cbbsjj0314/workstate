# ChatGPT MCP Capability Probe

## Hypothesis

WorkState may be able to use a ChatGPT developer-mode custom MCP connector to
capture bounded observed events automatically. The current user account is
ChatGPT Plus, and official documentation does not establish whether this account
can invoke custom MCP write tools reliably.

This M0 spike measures actual capability. It is not the final WorkState
ChatGPT integration, event schema, workflow inference engine, UI, deployment, or
production connector.

## Why This Probe Exists

WorkState's central question is:

```text
What is waiting for whom?
```

That answer must be derived from observed events and repository snapshots. For
ChatGPT, the feasibility question is whether the integration can automatically
capture a safe synthetic observed event through MCP, or whether manual
checkpointing remains the only available fallback for this account.

The user confirmed that ChatGPT developer mode can be enabled, the custom app
creation dialog is available, and the dialog accepts a server URL or tunnel
configuration. That confirms the app setup surface, not write-tool invocation.

## Tool Contract

This server exposes exactly two MCP tools.

### `health_check`

Purpose:

- prove read-only tool discovery and invocation
- return safe server identity and a generated response timestamp
- perform no mutation
- access no repository contents
- make no outbound network calls

Input:

```json
{}
```

Output fields:

```text
ok
server_name
schema_version
response_id
responded_at
```

Annotations:

```json
{
  "readOnlyHint": true,
  "destructiveHint": false,
  "openWorldHint": false
}
```

### `record_observation`

Purpose:

- probe whether ChatGPT Plus can invoke a non-destructive custom MCP write tool
- append one synthetic observation to a JSONL file outside the repository

Input:

```json
{
  "probe_id": "probe_plus_direct_01",
  "scenario": "direct",
  "marker": "workstate_chatgpt_mcp_probe_v1"
}
```

`probe_id` must match:

```text
^probe_[a-z0-9][a-z0-9_-]{0,30}$
```

`scenario` must be:

```text
direct | indirect
```

`marker` must be exactly:

```text
workstate_chatgpt_mcp_probe_v1
```

Output fields:

```text
accepted
record_id
probe_id
scenario
recorded_at
duplicate
attempt_count
```

Annotations:

```json
{
  "readOnlyHint": false,
  "destructiveHint": false,
  "openWorldHint": false
}
```

`record_observation` uses process-local idempotency keyed by `probe_id`.

- The first valid call appends exactly one JSONL record.
- A concurrent or later identical retry returns the same `record_id`,
  `duplicate: true`, and that call's incremented `attempt_count`.
- A conflicting reuse of `probe_id` returns a safe structured tool error.
- If the owner append fails, all awaiters receive a safe structured error and a
  later retry may try again with a new `record_id`.
- These guarantees apply only within one running server process and reset on
  restart.

## Privacy Behavior

The tool schemas accept synthetic bounded fields only. The server does not
persist:

- raw user prompts
- raw assistant messages
- conversation transcripts
- ChatGPT conversation identifiers
- tool-call payloads beyond the validated normalized fields
- credentials, secrets, cookies, request headers, or authorization values
- commands, URLs, arbitrary paths, source code, or repository file contents
- arbitrary free-form notes

Tool results include `structuredContent` and a safe JSON text equivalent in
`content`. Errors do not include stack traces, absolute paths, environment
values, hostnames, usernames, raw request bodies, or local machine details.

## Event Log Path

Override path:

```sh
WORKSTATE_CHATGPT_MCP_EVENT_LOG="$HOME/.local/share/workstate/events/chatgpt-mcp-probe.jsonl"
```

Default path:

```sh
${XDG_DATA_HOME:-$HOME/.local/share}/workstate/events/chatgpt-mcp-probe.jsonl
```

The server refuses to write if the resolved event-log path is inside the Git
repository. Where supported, the parent directory is created with `0700`
permissions and the JSONL file with `0600` permissions.

Each persisted observation contains only:

```text
schema_version
recorded_at
source
tool_name
record_id
probe_id
scenario
marker
```

## Bounded Exposure

This spike is intended for temporary development only. It has no authentication
because the goal is to measure ChatGPT custom MCP capability, not production
security.

Limits:

- HTTP request body: 16 KiB
- accepted unique writes per process: 20
- event-log file size: 1 MiB
- Node `requestTimeout`: 10 seconds
- Node `headersTimeout`: 5 seconds
- `/mcp` accepts only protocol-required methods
- `POST /mcp` accepts only `Content-Type: application/json`
- unsupported methods, content types, malformed JSON, and oversized requests
  return safe 4xx responses

The public `trycloudflare.com` URL is not authentication. Keep the server and
tunnel running only during the manual probe and stop both immediately after
testing.

## Routes

`GET /`:

- human-readable local health response

`/mcp`:

- MCP Streamable HTTP endpoint
- implemented with `@modelcontextprotocol/sdk@1.29.0`
- stateless transport
- JSON responses enabled
- follows the pinned SDK's stateless JSON-response behavior: `POST` handles MCP
  JSON-RPC requests, while unsupported `GET` and `DELETE` return 405 in this
  spike

## Dependency Installation

Install from the isolated spike package directory:

```sh
npm ci --prefix spikes/chatgpt-mcp
```

This installs:

```text
@modelcontextprotocol/sdk@1.29.0
zod@4.4.3
```

The tested Node runtime is:

```text
Node v26.0.0
```

The package requires Node `>=22.7.5` so the documented MCP Inspector version can
run.

## Local Server Startup

Start the local MCP server:

```sh
npm run start --prefix spikes/chatgpt-mcp
```

Default local URL:

```text
http://127.0.0.1:2091
```

MCP endpoint:

```text
http://127.0.0.1:2091/mcp
```

Do not bind this spike directly to all network interfaces.

## MCP Inspector Validation

Use the pinned Inspector command tested for this spike:

```sh
npx --yes @modelcontextprotocol/inspector@0.22.0
```

In Inspector, connect to:

```text
http://127.0.0.1:2091/mcp
```

Validate:

- server initializes
- exactly two tools are listed
- `health_check` succeeds
- `record_observation` succeeds with synthetic input
- malformed input is rejected
- JSONL is written outside the repository
- no forbidden raw fields are persisted

Inspector validation proves local MCP behavior only. It does not prove ChatGPT
Plus live capability.

## Cloudflare Quick Tunnel Procedure

This implementation does not install or invoke `cloudflared` automatically.

In a separate terminal, run:

```sh
cloudflared tunnel --url http://127.0.0.1:2091
```

Quick Tunnel notes:

- it is temporary and intended for development
- it produces a random public URL
- no paid Cloudflare plan or custom domain is required
- no production reliability or SLA is assumed
- a local `.cloudflared/config.yaml` may interfere with Quick Tunnel usage
- Quick Tunnel does not support SSE, so this spike uses stateless Streamable
  HTTP with JSON responses
- keep both the server and tunnel processes running during testing
- stop the tunnel immediately after the probe

The ChatGPT MCP URL must end in `/mcp`:

```text
https://<random>.trycloudflare.com/mcp
```

Do not commit or paste the random tunnel URL into repository files.

## ChatGPT Custom App Creation

Recommended draft app metadata:

```text
Name: WorkState MCP Capability Probe
Description: Synthetic development probe for measuring ChatGPT MCP tool discovery and invocation behavior. Not a production WorkState integration.
```

In ChatGPT developer mode, create a custom app using the temporary HTTPS MCP
URL:

```text
https://<random>.trycloudflare.com/mcp
```

Do not create a production app, OAuth app, custom domain, or user-facing
WorkState integration from this spike.

## Live Test Matrix

Do not use real personal content in live-test prompts.

### Connection And Discovery

Steps:

1. Create the draft custom app using the temporary HTTPS `/mcp` URL.
2. Verify exactly two tools are discovered.
3. Record whether annotations are shown or reflected in permissions.

Record:

```text
connected:
tools_discovered:
tool_count:
annotations_visible_or_reflected:
notes:
```

### Explicit Read Invocation

Prompt:

```text
Use the WorkState MCP Capability Probe app and call health_check. Do not call any other tool.
```

Record:

```text
tool_selected:
arguments_valid:
output_displayed:
confirmation_requested_unexpectedly:
call_count:
notes:
```

### Explicit Write Invocation

Prompt:

```text
Use the WorkState MCP Capability Probe app to record a synthetic observation with probe_id probe_plus_direct_01, scenario direct, and marker workstate_chatgpt_mcp_probe_v1. Do not include any personal content.
```

Record:

```text
tool_available:
confirmation_requested:
executed_after_approval:
arguments_matched_schema:
jsonl_records_appended:
duplicate_calls_observed:
attempt_count:
notes:
```

### Indirect Relevant Invocation

Prompt:

```text
Use the WorkState MCP Capability Probe app to save one synthetic probe observation for this direct capability test. Use probe_id probe_plus_indirect_01 and no personal content.
```

Record:

```text
record_observation_selected:
confirmation_requested:
jsonl_records_appended:
attempt_count:
notes:
```

### Negative Control

Prompt:

```text
What are three general risks of relying on manual workflow notes?
```

Record:

```text
health_check_called:
record_observation_called:
notes:
```

Expected behavior: neither tool is called.

### Privacy Inspection

Inspect the JSONL file and confirm none of these appear:

```text
prompt
assistant
conversation
transcript
headers
cookie
authorization
command
path
url
note
source_code
repository_contents
```

## Result-Recording Template

ChatGPT live verification status:

```text
pending
```

Outcome:

```text
Pending live ChatGPT web test.
```

After testing, select exactly one:

```text
Outcome A: Connection, read invocation, and write invocation succeeded.
Outcome B: Connection and read invocation succeeded, but write invocation was unavailable or blocked.
Outcome C: The app connected and tools were discovered, but invocation was unreliable.
Outcome D: The custom app could not connect or tools could not be discovered.
```

Evidence:

```text
tested_chatgpt_plan:
tested_date:
connection_and_discovery:
explicit_read:
explicit_write:
indirect_relevant:
negative_control:
privacy_inspection:
observed_duplicate_behavior:
final_outcome:
```

Do not claim ChatGPT Plus read or write capability until this live web test is
complete.

## Shutdown And Cleanup

After testing:

1. Stop the ChatGPT app test if applicable.
2. Stop `cloudflared`.
3. Stop the local Node server.
4. Inspect the JSONL file outside the repository.
5. Do not commit JSONL output, tunnel URLs, credentials, local absolute paths,
   or personal data.

## Known Limitations

- Live ChatGPT capability is pending until the user performs the web test.
- MCP Inspector validates local protocol behavior only.
- Idempotency and serialized write guarantees are process-local only.
- The JSONL shape is provisional and scoped to this spike.
- There is no OAuth, user account, database, replay, UI widget, production
  deployment, Git polling, GitHub polling, or derived workflow state.
- This spike records synthetic observed events only; it does not implement
  `likely_waiting_for`.
