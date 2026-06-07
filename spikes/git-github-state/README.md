# Local Git And GitHub State Collection Spike

## Hypothesis

WorkState can use read-only local `git` and GitHub CLI commands to collect a
useful, privacy-preserving, normalized view of objective repository state
without modifying the repository or GitHub.

This is the third M0 feasibility spike. It is not the final WorkState runtime,
repository snapshot, persisted schema, polling service, or workflow inference
engine.

## Scope And Non-Goals

The spike collects objective local Git facts and, where available, GitHub
repository, branch, pull-request, and check facts. It writes one JSON document
to stdout and diagnostics to stderr.

It does not implement:

- persistence, a database, a registry, a daemon, a scheduler, or retries
- fetch, pull, push, hooks, webhooks, or any other mutation
- `likely_waiting_for`, `phase`, ownership, semantic completion, or a suggested
  next action
- prompt, source-code, diff, PR-text, review-text, or CI-log collection
- GitHub Enterprise support
- the final WorkState snapshot or production schema

## Run The Collector

Requirements:

- Python 3
- Git
- optional `gh 2.92.0` for the GitHub portion
- an active authenticated `github.com` account visible to `gh`

Run:

```sh
python3 spikes/git-github-state/collect_state.py /path/to/repository
```

The target must be a working-tree Git repository. A local absolute
`repo_root` is intentionally included in local CLI output so a later
N-repository workspace can identify the repository. Committed examples use
placeholders instead of a real user path.

## Read-Only Command Boundary

The collector runs only these command forms:

```text
git --no-optional-locks rev-parse --is-bare-repository
git --no-optional-locks rev-parse --is-inside-work-tree
git --no-optional-locks rev-parse --show-toplevel
git --no-optional-locks status --porcelain=v2 --branch -z --untracked-files=all
git --no-optional-locks remote
git --no-optional-locks remote get-url --all <remote>

gh auth status --active --hostname github.com
gh repo view OWNER/REPO --json nameWithOwner,defaultBranchRef
gh api graphql -f owner=OWNER -f name=REPO \
  -f qualifiedName=refs/heads/BRANCH -f query=<static-query>
gh pr list -R OWNER/REPO --head BRANCH --state all --limit 100 --json <fields>
gh pr checks NUMBER -R OWNER/REPO --json bucket
```

All subprocesses use argument arrays, `shell=False`, an explicit working
directory, separate stdout/stderr capture, disabled stdin, and bounded
timeouts. The collector does not run arbitrary aliases, shell scripts, GitHub
mutation APIs, or commands supplied by input.

Git environment:

```text
GIT_OPTIONAL_LOCKS=0
GIT_TERMINAL_PROMPT=0
LC_ALL=C
```

GitHub CLI environment:

```text
GH_PROMPT_DISABLED=1
NO_COLOR=1
GH_PAGER=cat
PAGER=cat
LC_ALL=C
```

The authentication preflight intentionally checks only the account that `gh`
will use:

```text
gh auth status --active --hostname github.com
```

It never uses `--show-token` or `--json`. Human-readable authentication stdout
and stderr are discarded after exit classification.

## Timeouts

- local Git command: 10 seconds
- local `gh` authentication preflight: 5 seconds
- GitHub network command: 15 seconds

A timeout becomes structured unavailable or partial state. This spike does not
retry.

## Provisional Output Contract

The output uses deterministic two-space-indented, sorted-key JSON and ends with
one newline. The shape is spike-only:

```json
{
  "collected_at": "2026-06-06T00:00:00Z",
  "collector": {
    "reason_code": null,
    "status": "ok"
  },
  "git": {
    "available": true,
    "branch": {
      "detached": false,
      "name": "feature/example",
      "unborn": false
    },
    "head_sha": "0123456789abcdef0123456789abcdef01234567",
    "is_repository": true,
    "remotes": [
      {
        "github": {
          "host": "github.com",
          "name_with_owner": "owner/repository"
        },
        "name": "origin"
      }
    ],
    "upstream": {
      "ahead": 1,
      "behind": 0,
      "configured": true,
      "ref": "origin/feature/example"
    },
    "working_tree": {
      "clean": false,
      "conflicted": 0,
      "staged": 1,
      "unstaged": 2,
      "untracked": 1
    }
  },
  "github": {
    "branch": {
      "remote_sha": "0123456789abcdef0123456789abcdef01234567",
      "status": "published"
    },
    "checks": {
      "cancel": 0,
      "fail": 0,
      "overall": "pending",
      "pass": 2,
      "pending": 1,
      "skipping": 0,
      "status": "observed"
    },
    "failures": [],
    "pull_request": {
      "base_ref": "main",
      "head_ref": "feature/example",
      "is_draft": true,
      "merge_state_status": "CLEAN",
      "mergeable": "MERGEABLE",
      "number": 123,
      "review_decision": null,
      "state": "OPEN",
      "status": "observed",
      "url": "https://github.com/owner/repository/pull/123"
    },
    "reason_code": null,
    "repository": {
      "default_branch": "main",
      "name_with_owner": "owner/repository"
    },
    "status": "ok"
  },
  "repo_root": "/path/to/repository",
  "schema_version": 1
}
```

## Local Git Fields

The collector distinguishes:

- missing target, non-directory, non-Git directory, bare repository, and
  working-tree repository
- full HEAD SHA, named branch, detached HEAD, and unborn branch
- staged, unstaged, untracked, and conflicted counts
- configured upstream, upstream ref, and locally known ahead/behind counts
- configured remote names and sanitized GitHub identities

`git status --porcelain=v2 --branch -z --untracked-files=all` is parsed as a
NUL-delimited machine format. Paths are consumed only to parse record
boundaries; they are never returned or persisted. Ahead/behind values reflect
local remote-tracking refs and may be stale because the collector never
fetches.

For structured error documents, `git.available` reflects only observed command
availability:

```text
missing or non-directory target: null
git executable missing:          false
Git command invoked:             true
```

This keeps path-validation failures from claiming that Git was available when
no Git command ran.

## Remote Sanitization

HTTPS, `ssh://`, and scp-style `github.com` remotes may produce only:

```json
{
  "host": "github.com",
  "name_with_owner": "owner/repository"
}
```

Userinfo, credentials, queries, fragments, raw URLs, and malformed identities
are discarded. Non-GitHub remotes expose only their configured remote name.

When multiple GitHub remotes exist, selection prefers the upstream remote,
then `origin`, then a sole distinct identity. Otherwise GitHub collection is
not applicable because the identity is ambiguous.

## Branch Publication And PR Correlation

Branch publication uses a static GraphQL `repository.ref` query. Every GraphQL
`String!` value and the query use `-f/--raw-field`, not `-F/--field`, so values
are not type-converted or interpreted as file references.

- returned target OID: `published`, with `remote_sha`
- successful `ref: null`: objectively `not_published`
- command, authentication, permission, rate-limit, timeout, GraphQL, or JSON
  failure: `unknown`

A failed lookup is never treated as evidence that a branch was deleted.

Branch name alone is insufficient PR correlation evidence. Candidate PRs must
match the exact branch name, be same-repository, and have a case-insensitively
matching repository owner. Missing or malformed ownership data is rejected.

- Open PRs require a published branch and `headRefOid == remote_sha`.
- Historical closed or merged PRs require the remote SHA when the branch is
  published.
- After an objectively observed unpublished branch, historical PRs may instead
  use `headRefOid == local head_sha`.
- Multiple equally valid candidates produce `ambiguous`; no candidate is
  guessed.

An unpublished branch can therefore still have a safely correlated historical
PR after GitHub deletes the remote branch.

## GitHub And Check Fields

Repository metadata contains only `name_with_owner` and `default_branch`.
Pull-request data contains only number, state, draft status, head/base refs,
review decision, mergeability, merge-state status, and a locally constructed
canonical URL. Bodies, comments, reviews, commits, files, and logs are not
requested. Before emission, the PR number must be a positive non-boolean
integer, state must be `OPEN`, `CLOSED`, or `MERGED`, and head/base refs must be
non-empty strings. For pinned `gh 2.92.0`, `reviewDecision` may be an empty
string when no review decision exists; the collector normalizes both `""` and
null to `review_decision: null`. A non-empty review decision string is
preserved. `mergeable` and `mergeStateStatus` remain limited to null or a
non-empty string. Malformed command output becomes a safe `invalid_json` stage
failure.

For pinned `gh 2.92.0`, `gh pr checks --json bucket` is accepted only when it
exits `0` and returns a JSON array containing known buckets:

```text
pass
fail
pending
skipping
cancel
```

Counts and aggregate state come exclusively from bucket values. Any nonzero
exit is a stage failure even if stdout resembles valid JSON. This behavior is
tested for `gh 2.92.0` and is not assumed for every future release.

If `statusCheckRollup` is null or empty, `gh pr checks` is not invoked and the
normal result is `checks.status: none` with zero counts.

## Applicability And Partial Failure

Overall GitHub states:

```text
ok:             reason_code null, failures []
not_applicable: one whole-GitHub reason, failures []
unavailable:    collection could not meaningfully begin, failures []
partial:        reason_code null, one or more failed stage objects
```

Safe failure entries contain only:

```json
{
  "reason_code": "network_unavailable",
  "stage": "branch_lookup"
}
```

Normal states do not enter `failures`:

- detached HEAD, unborn branch, no remote, or no supported GitHub remote:
  whole-GitHub `not_applicable`
- no upstream: valid local state
- branch not published: valid branch observation; historical PR correlation
  still runs
- no PR: `pull_request.status: none`, checks not applicable
- PR with no checks: `pull_request.status: observed`, `checks.status: none`

If repository metadata succeeds and branch lookup fails, repository metadata
is preserved, GitHub becomes `partial`, and branch, PR, and checks remain
`unknown`. Raw stderr, GraphQL errors, URLs, argv, and exceptions are never
included.

## Exit Codes

```text
0  local Git collection succeeded; GitHub may be ok, partial, unavailable,
   or not applicable
2  missing/non-directory target, non-Git directory, or bare repository
1  Git unavailable, local Git timeout/invalid output, or unexpected collector
   failure
```

The collector attempts a safe JSON error document before returning a nonzero
exit.

## Privacy Inspection

Normalized output and diagnostics must contain none of:

```text
changed filenames
untracked filenames
diff or file contents
raw remote URLs
credentials or tokens
account names or token scopes
keyring information
raw authentication output
raw stdout or stderr
command lines or environment variables
PR bodies, comments, review text, check logs, or artifacts
```

## Automated Validation

Run:

```sh
python3 -m compileall spikes tests
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m json.tool .codex/hooks.json >/dev/null

npm ci --prefix spikes/chatgpt-mcp
npm run check --prefix spikes/chatgpt-mcp
npm test --prefix spikes/chatgpt-mcp

ruby -e 'require "yaml"; Dir[".github/workflows/*.yml", ".github/workflows/*.yaml"].each { |p| YAML.load_file(p); puts "yaml ok #{p}" }'

python3 spikes/git-github-state/collect_state.py . | python3 -m json.tool
git diff --check
git status --short
```

Use a separate command without a pipeline when validating exit codes.
Automated tests use temporary repositories and fake GitHub responses; CI does
not require GitHub credentials or live network access.

## Live Dogfooding Procedure

1. Before publication, run the collector on the implementation branch and
   record local branch, worktree, upstream, publication, and no-PR behavior
   where the active `gh` account is available.
2. Push the implementation branch outside the collector, rerun it, and verify
   branch publication.
3. Create the draft PR outside the collector, rerun it, and verify repository,
   PR number, open/draft state, base/head refs, and current checks.
4. After CI completes, compare normalized buckets with GitHub UI or independent
   `gh` output.
5. Run against a temporary local repository with no remote and verify local
   success, GitHub `not_applicable/no_remote`, and exit `0`.
6. Search the captured normalized JSON for forbidden filenames, remote URLs,
   credentials, PR text, comments, and logs.

Issue creation, branch push, and draft PR creation are implementation workflow
actions outside collector runtime. Fixture results must not be presented as
live GitHub success.

## Result Recording Template

```text
status: pending | completed | partial
tested_date:
git_version:
gh_version:

pre_publication:
  local_git:
  github:

published_branch:
  branch_status:
  remote_sha_match:

draft_pr:
  publication:
  pr_status:
  draft:
  head_base:
  checks:

completed_ci:
  normalized_counts:
  independent_comparison:

local_only_repository:
  local_git:
  github:
  exit_code:

privacy:
  forbidden_data_found:

limitations:
```

## Known Limitations

- Ahead/behind counts can be stale because fetching is prohibited.
- Large working trees may exceed the 10-second status timeout.
- Submodules are not recursively inspected.
- Multiple unrelated GitHub identities can remain ambiguous.
- `mergeable` and `mergeStateStatus` may temporarily be unknown.
- GitHub permissions can limit observable repository or ref state.
- The active-account preflight may report unavailable in an environment where
  `gh` cannot access its authenticated account, even when another GitHub client
  can access the repository.
- The check exporter contract is pinned to `gh 2.92.0`.

## Live Verification Result

Status:

```text
partial
```

Test environment:

```text
tested_date: 2026-06-06
git_version: 2.54.0
gh_version: 2.92.0
implementation_branch: spike/git-github-state-collection
draft_pr: 10
```

Reproducible observations:

- Before publication, the collector returned exit `0`, normalized the local
  implementation branch and dirty working-tree counts, and preserved those
  local results when GitHub collection was unavailable.
- After the branch was pushed, the collector returned exit `0`, reported the
  configured upstream, zero locally known ahead/behind counts, and a clean
  working tree.
- After draft PR creation, the same local result remained stable.
- In all three repository runs, the required
  `gh auth status --active --hostname github.com` preflight returned nonzero in
  this execution environment. The collector returned
  `github.status: unavailable` with `reason_code: gh_not_authenticated`, did
  not attempt later GitHub stages, and did not expose raw authentication
  output.
- A temporary committed local-only repository returned exit `0`, normalized a
  clean `main` branch, and returned GitHub
  `not_applicable/no_remote`.
- Direct missing-target and bare-repository runs returned structured JSON and
  exit `2`.
- Automated validation completed with 92 Python tests and 21 ChatGPT MCP tests
  passing. Fixtures covered published/unpublished/unknown branch state,
  SHA-based PR association, and all check buckets without live network access.

Independent GitHub observation confirmed that the implementation branch was
published and draft PR `#10` existed. That observation came from the
implementation workflow, not from collector output, and is not counted as
collector-level GitHub success.

Privacy inspection found no changed filenames, diff content, raw remote URLs,
credentials, tokens, account details, token scopes, keyring information, raw
authentication output, raw stderr, command lines, PR bodies, comments, review
text, CI logs, or local absolute paths in committed examples or recorded
results.

Conclusion:

- Local Git collection feasibility, structured exit codes, privacy behavior,
  and preservation of local evidence during GitHub unavailability were
  demonstrated.
- Fixture coverage demonstrated the GitHub normalization and correlation logic.
- Live collection of branch publication, draft PR state, and check buckets was
  not demonstrated because the required active-account `gh` preflight was not
  available in this execution environment.
- The spike result is partial rather than proof of complete live GitHub polling
  feasibility.
