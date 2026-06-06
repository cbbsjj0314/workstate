#!/usr/bin/env python3
"""Read-only local Git and GitHub state collector for the WorkState M0 spike."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Sequence
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
GIT_TIMEOUT = 10
GH_AUTH_TIMEOUT = 5
GH_NETWORK_TIMEOUT = 15
KNOWN_CHECK_BUCKETS = {"pass", "fail", "pending", "skipping", "cancel"}
CHECK_PRECEDENCE = ("fail", "pending", "cancel", "pass", "skipping")
PR_STATES = {"OPEN", "CLOSED", "MERGED"}
PR_FIELDS = (
    "number,state,isDraft,headRefName,headRefOid,isCrossRepository,"
    "headRepositoryOwner,baseRefName,reviewDecision,mergeable,"
    "mergeStateStatus,statusCheckRollup,updatedAt"
)
BRANCH_QUERY = """query($owner: String!, $name: String!, $qualifiedName: String!) {
  repository(owner: $owner, name: $name) {
    ref(qualifiedName: $qualifiedName) {
      target { oid }
    }
  }
}"""


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes


class CommandMissing(Exception):
    pass


class CommandTimedOut(Exception):
    pass


class CollectorError(Exception):
    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


class CommandRunner:
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout: int,
        env_overrides: dict[str, str],
    ) -> CommandResult:
        env = os.environ.copy()
        env.update(env_overrides)
        try:
            completed = subprocess.run(
                list(argv),
                cwd=cwd,
                env=env,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise CommandMissing from exc
        except subprocess.TimeoutExpired as exc:
            raise CommandTimedOut from exc
        return CommandResult(tuple(argv), completed.returncode, completed.stdout, completed.stderr)


GIT_ENV = {
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
    "LC_ALL": "C",
}
GH_ENV = {
    "GH_PROMPT_DISABLED": "1",
    "NO_COLOR": "1",
    "GH_PAGER": "cat",
    "PAGER": "cat",
    "LC_ALL": "C",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def decode_ascii(value: bytes) -> str:
    try:
        return value.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CollectorError("git_invalid_output") from exc


def parse_bool_output(result: CommandResult) -> bool:
    if result.returncode != 0:
        raise CollectorError("not_git_repository")
    value = decode_ascii(result.stdout).strip()
    if value == "true":
        return True
    if value == "false":
        return False
    raise CollectorError("git_invalid_output")


def parse_porcelain_v2(data: bytes) -> dict[str, Any]:
    records = data.split(b"\0")
    branch_oid: str | None = None
    branch_name: str | None = None
    upstream_ref: str | None = None
    ahead = 0
    behind = 0
    staged = 0
    unstaged = 0
    untracked = 0
    conflicted = 0
    consume_original_path = False

    for raw in records:
        if not raw:
            continue
        if consume_original_path:
            consume_original_path = False
            continue
        if raw.startswith(b"# "):
            header = decode_ascii(raw[2:])
            key, _, value = header.partition(" ")
            if key == "branch.oid":
                branch_oid = None if value == "(initial)" else value
            elif key == "branch.head":
                branch_name = None if value == "(detached)" else value
            elif key == "branch.upstream":
                upstream_ref = value
            elif key == "branch.ab":
                match = re.fullmatch(r"\+(\d+) -(\d+)", value)
                if not match:
                    raise CollectorError("git_invalid_output")
                ahead, behind = (int(match.group(1)), int(match.group(2)))
            continue

        record_type = raw[:1]
        if record_type in {b"1", b"2"}:
            fields = raw.split(b" ", 2)
            if len(fields) < 3 or len(fields[1]) != 2:
                raise CollectorError("git_invalid_output")
            x, y = chr(fields[1][0]), chr(fields[1][1])
            staged += int(x != ".")
            unstaged += int(y != ".")
            if record_type == b"2":
                consume_original_path = True
        elif record_type == b"u":
            conflicted += 1
        elif record_type == b"?":
            untracked += 1
        elif record_type == b"!":
            continue
        else:
            raise CollectorError("git_invalid_output")

    unborn = branch_oid is None and branch_name is not None
    detached = branch_name is None and branch_oid is not None
    return {
        "head_sha": branch_oid,
        "branch": {"name": branch_name, "detached": detached, "unborn": unborn},
        "working_tree": {
            "clean": staged == unstaged == untracked == conflicted == 0,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "conflicted": conflicted,
        },
        "upstream": {
            "configured": upstream_ref is not None,
            "ref": upstream_ref,
            "ahead": ahead if upstream_ref is not None else 0,
            "behind": behind if upstream_ref is not None else 0,
        },
    }


def sanitize_github_url(raw_url: str) -> dict[str, str] | None:
    candidate = raw_url.strip()
    if not candidate:
        return None

    host: str | None = None
    path: str | None = None
    if "://" in candidate:
        try:
            parsed = urlsplit(candidate)
            host = parsed.hostname
            path = parsed.path
        except ValueError:
            return None
    else:
        scp_match = re.fullmatch(r"(?:[^@/\s]+@)?([^:/\s]+):(.+)", candidate)
        if scp_match:
            host = scp_match.group(1)
            path = scp_match.group(2).split("#", 1)[0].split("?", 1)[0]

    if host is None or path is None or host.lower() != "github.com":
        return None
    clean_path = path.strip("/")
    if clean_path.endswith(".git"):
        clean_path = clean_path[:-4]
    parts = clean_path.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    if any(part in {".", ".."} for part in parts):
        return None
    return {"host": "github.com", "name_with_owner": f"{parts[0]}/{parts[1]}"}


def choose_github_identity(
    remotes: list[dict[str, Any]], upstream_ref: str | None
) -> tuple[dict[str, str] | None, str | None]:
    candidates = [remote for remote in remotes if remote["github"] is not None]
    if not remotes:
        return None, "no_remote"
    if not candidates:
        return None, "no_supported_github_remote"

    upstream_remote = upstream_ref.split("/", 1)[0] if upstream_ref and "/" in upstream_ref else None
    if upstream_remote:
        matched = [remote for remote in candidates if remote["name"] == upstream_remote]
        if len(matched) == 1:
            return matched[0]["github"], None
    origin = [remote for remote in candidates if remote["name"] == "origin"]
    if len(origin) == 1:
        return origin[0]["github"], None
    identities = {remote["github"]["name_with_owner"] for remote in candidates}
    if len(identities) == 1:
        return candidates[0]["github"], None
    return None, "ambiguous_github_remote"


def json_object(data: bytes, reason: str = "invalid_json") -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectorError(reason) from exc
    if not isinstance(value, dict):
        raise CollectorError(reason)
    return value


def classify_gh_failure(stderr: bytes, *, default: str = "command_failed") -> str:
    text = stderr.decode("utf-8", errors="ignore").lower()
    if "rate limit" in text or "rate_limit" in text:
        return "rate_limited"
    if "authentication" in text or "not logged" in text or "authenticate" in text:
        return "gh_not_authenticated"
    if "forbidden" in text or "permission" in text or "resource not accessible" in text:
        return "permission_denied"
    if "network" in text or "connect" in text or "resolve" in text or "timeout" in text:
        return "network_unavailable"
    return default


def safe_failure(stage: str, reason_code: str) -> dict[str, str]:
    return {"stage": stage, "reason_code": reason_code}


def not_applicable_github(reason_code: str) -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "reason_code": reason_code,
        "failures": [],
        "repository": None,
        "branch": {"status": "not_applicable", "remote_sha": None},
        "pull_request": {"status": "not_applicable"},
        "checks": empty_checks("not_applicable"),
    }


def unavailable_github(reason_code: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason_code": reason_code,
        "failures": [],
        "repository": None,
        "branch": {"status": "unknown", "remote_sha": None},
        "pull_request": {"status": "unknown"},
        "checks": empty_checks("unknown"),
    }


def empty_checks(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "overall": None,
        "pass": 0,
        "fail": 0,
        "pending": 0,
        "skipping": 0,
        "cancel": 0,
    }


def parse_branch_lookup(data: bytes) -> tuple[str, str | None]:
    payload = json_object(data)
    if payload.get("errors"):
        raise CollectorError("graphql_error")
    repository = payload.get("data", {}).get("repository") if isinstance(payload.get("data"), dict) else None
    if not isinstance(repository, dict):
        raise CollectorError("invalid_json")
    ref = repository.get("ref")
    if ref is None:
        return "not_published", None
    if not isinstance(ref, dict):
        raise CollectorError("invalid_json")
    target = ref.get("target")
    if not isinstance(target, dict) or not isinstance(target.get("oid"), str) or not target["oid"]:
        raise CollectorError("invalid_json")
    return "published", target["oid"]


def correlate_pull_request(
    candidates: Any,
    *,
    branch_name: str,
    owner: str,
    branch_status: str,
    remote_sha: str | None,
    local_head_sha: str,
) -> dict[str, Any]:
    if not isinstance(candidates, list):
        raise CollectorError("invalid_json")
    if branch_status not in {"published", "not_published"}:
        raise CollectorError("invalid_branch_state")

    correlatable: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise CollectorError("invalid_json")
        head_ref_name = candidate.get("headRefName")
        if not isinstance(head_ref_name, str) or not head_ref_name:
            raise CollectorError("invalid_json")
        if head_ref_name != branch_name:
            continue
        owner_data = candidate.get("headRepositoryOwner")
        login = owner_data.get("login") if isinstance(owner_data, dict) else None
        if (
            candidate.get("isCrossRepository") is not False
            or not isinstance(login, str)
            or not login
            or login.casefold() != owner.casefold()
        ):
            continue
        normalize_pr(candidate)
        correlatable.append(candidate)

    open_matches = [
        candidate
        for candidate in correlatable
        if candidate.get("state") == "OPEN"
        and branch_status == "published"
        and isinstance(remote_sha, str)
        and candidate.get("headRefOid") == remote_sha
    ]
    if len(open_matches) > 1:
        return {"status": "ambiguous"}
    if len(open_matches) == 1:
        return normalize_pr(open_matches[0])

    expected_historical_sha = remote_sha if branch_status == "published" else local_head_sha
    historical = [
        candidate
        for candidate in correlatable
        if candidate.get("state") in {"CLOSED", "MERGED"}
        and candidate.get("headRefOid") == expected_historical_sha
    ]
    if len(historical) > 1:
        return {"status": "ambiguous"}
    if len(historical) == 1:
        return normalize_pr(historical[0])
    return {"status": "none"}


def normalize_pr(candidate: dict[str, Any]) -> dict[str, Any]:
    number = candidate.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise CollectorError("invalid_json")
    if candidate.get("state") not in PR_STATES or not isinstance(candidate.get("isDraft"), bool):
        raise CollectorError("invalid_json")
    for field in ("headRefName", "baseRefName"):
        if not isinstance(candidate.get(field), str) or not candidate[field]:
            raise CollectorError("invalid_json")
    for field in ("reviewDecision", "mergeable", "mergeStateStatus"):
        value = candidate.get(field)
        if value is not None and (not isinstance(value, str) or not value):
            raise CollectorError("invalid_json")
    return {
        "status": "observed",
        "number": candidate["number"],
        "state": candidate["state"],
        "is_draft": candidate["isDraft"],
        "head_ref": candidate["headRefName"],
        "base_ref": candidate["baseRefName"],
        "review_decision": candidate.get("reviewDecision"),
        "mergeable": candidate.get("mergeable"),
        "merge_state_status": candidate.get("mergeStateStatus"),
        "status_check_rollup": candidate.get("statusCheckRollup"),
    }


def parse_check_buckets(data: bytes) -> dict[str, Any]:
    try:
        entries = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectorError("invalid_json") from exc
    if not isinstance(entries, list):
        raise CollectorError("invalid_json")
    counts = {bucket: 0 for bucket in KNOWN_CHECK_BUCKETS}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("bucket") not in KNOWN_CHECK_BUCKETS:
            raise CollectorError("invalid_json")
        counts[entry["bucket"]] += 1
    overall = next((bucket for bucket in CHECK_PRECEDENCE if counts[bucket]), None)
    return {"status": "observed" if entries else "none", "overall": overall, **counts}


def collect_git(target: Path, runner: CommandRunner) -> tuple[dict[str, Any], Path]:
    def git(*args: str) -> CommandResult:
        return runner.run(
            ["git", "--no-optional-locks", *args],
            cwd=target,
            timeout=GIT_TIMEOUT,
            env_overrides=GIT_ENV,
        )

    try:
        bare = parse_bool_output(git("rev-parse", "--is-bare-repository"))
    except CommandMissing as exc:
        raise CollectorError("git_not_installed") from exc
    except CommandTimedOut as exc:
        raise CollectorError("git_timeout") from exc
    if bare:
        raise CollectorError("bare_git_repository")

    try:
        inside = parse_bool_output(git("rev-parse", "--is-inside-work-tree"))
    except CommandTimedOut as exc:
        raise CollectorError("git_timeout") from exc
    if not inside:
        raise CollectorError("not_work_tree")

    try:
        root_result = git("rev-parse", "--show-toplevel")
        if root_result.returncode != 0:
            raise CollectorError("git_invalid_output")
        repo_root = Path(decode_ascii(root_result.stdout).strip()).resolve()
        status_result = git("status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all")
        if status_result.returncode != 0:
            raise CollectorError("git_invalid_output")
        state = parse_porcelain_v2(status_result.stdout)
        remote_result = git("remote")
        if remote_result.returncode != 0:
            raise CollectorError("git_invalid_output")
        remote_names = [name for name in decode_ascii(remote_result.stdout).splitlines() if name]
        remotes: list[dict[str, Any]] = []
        for name in remote_names:
            url_result = git("remote", "get-url", "--all", name)
            identities: list[dict[str, str]] = []
            if url_result.returncode == 0:
                for raw_url in decode_ascii(url_result.stdout).splitlines():
                    identity = sanitize_github_url(raw_url)
                    if identity and identity not in identities:
                        identities.append(identity)
            remotes.append({"name": name, "github": identities[0] if len(identities) == 1 else None})
    except CommandTimedOut as exc:
        raise CollectorError("git_timeout") from exc

    state.update({"available": True, "is_repository": True, "remotes": remotes})
    return state, repo_root


def collect_github(git_state: dict[str, Any], repo_root: Path, runner: CommandRunner) -> dict[str, Any]:
    branch = git_state["branch"]
    if branch["detached"]:
        return not_applicable_github("detached_head")
    if branch["unborn"]:
        return not_applicable_github("unborn_branch")

    identity, identity_reason = choose_github_identity(git_state["remotes"], git_state["upstream"]["ref"])
    if identity is None:
        return not_applicable_github(identity_reason or "no_supported_github_remote")

    def gh(argv: list[str], timeout: int) -> CommandResult:
        return runner.run(argv, cwd=repo_root, timeout=timeout, env_overrides=GH_ENV)

    try:
        auth = gh(["gh", "auth", "status", "--active", "--hostname", "github.com"], GH_AUTH_TIMEOUT)
    except CommandMissing:
        return unavailable_github("gh_not_installed")
    except CommandTimedOut:
        return unavailable_github("command_timeout")
    if auth.returncode != 0:
        return unavailable_github("gh_not_authenticated")

    repository_name = identity["name_with_owner"]
    owner, name = repository_name.split("/", 1)
    try:
        repo_result = gh(
            ["gh", "repo", "view", repository_name, "--json", "nameWithOwner,defaultBranchRef"],
            GH_NETWORK_TIMEOUT,
        )
    except CommandMissing:
        return unavailable_github("gh_not_installed")
    except CommandTimedOut:
        return unavailable_github("command_timeout")
    if repo_result.returncode != 0:
        return unavailable_github(classify_gh_failure(repo_result.stderr))
    try:
        repo_payload = json_object(repo_result.stdout)
        observed_name = repo_payload.get("nameWithOwner")
        default_ref = repo_payload.get("defaultBranchRef")
        if not isinstance(observed_name, str) or observed_name.casefold() != repository_name.casefold():
            raise CollectorError("invalid_json")
        if default_ref is not None and (
            not isinstance(default_ref, dict) or not isinstance(default_ref.get("name"), str)
        ):
            raise CollectorError("invalid_json")
        repository = {
            "name_with_owner": observed_name,
            "default_branch": default_ref["name"] if default_ref else None,
        }
    except CollectorError as exc:
        return unavailable_github(exc.reason_code)

    github: dict[str, Any] = {
        "status": "ok",
        "reason_code": None,
        "failures": [],
        "repository": repository,
        "branch": {"status": "unknown", "remote_sha": None},
        "pull_request": {"status": "unknown"},
        "checks": empty_checks("unknown"),
    }

    branch_name = branch["name"]
    graphql_argv = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"owner={owner}",
        "-f",
        f"name={name}",
        "-f",
        f"qualifiedName=refs/heads/{branch_name}",
        "-f",
        f"query={BRANCH_QUERY}",
    ]
    try:
        branch_result = gh(graphql_argv, GH_NETWORK_TIMEOUT)
    except CommandMissing:
        github["status"] = "partial"
        github["failures"].append(safe_failure("branch_lookup", "gh_not_installed"))
        return github
    except CommandTimedOut:
        github["status"] = "partial"
        github["failures"].append(safe_failure("branch_lookup", "command_timeout"))
        return github
    if branch_result.returncode != 0:
        github["status"] = "partial"
        github["failures"].append(
            safe_failure("branch_lookup", classify_gh_failure(branch_result.stderr))
        )
        return github
    try:
        branch_status, remote_sha = parse_branch_lookup(branch_result.stdout)
    except CollectorError as exc:
        github["status"] = "partial"
        github["failures"].append(safe_failure("branch_lookup", exc.reason_code))
        return github
    github["branch"] = {"status": branch_status, "remote_sha": remote_sha}

    pr_argv = [
        "gh",
        "pr",
        "list",
        "-R",
        repository_name,
        "--head",
        branch_name,
        "--state",
        "all",
        "--limit",
        "100",
        "--json",
        PR_FIELDS,
    ]
    try:
        pr_result = gh(pr_argv, GH_NETWORK_TIMEOUT)
    except CommandMissing:
        github["status"] = "partial"
        github["failures"].append(safe_failure("pull_request_lookup", "gh_not_installed"))
        return github
    except CommandTimedOut:
        github["status"] = "partial"
        github["failures"].append(safe_failure("pull_request_lookup", "command_timeout"))
        return github
    if pr_result.returncode != 0:
        github["status"] = "partial"
        github["failures"].append(
            safe_failure("pull_request_lookup", classify_gh_failure(pr_result.stderr))
        )
        return github
    try:
        candidates = json.loads(pr_result.stdout)
        selected = correlate_pull_request(
            candidates,
            branch_name=branch_name,
            owner=owner,
            branch_status=branch_status,
            remote_sha=remote_sha,
            local_head_sha=git_state["head_sha"],
        )
    except (UnicodeDecodeError, json.JSONDecodeError, CollectorError):
        github["status"] = "partial"
        github["failures"].append(safe_failure("pull_request_lookup", "invalid_json"))
        return github
    github["pull_request"] = selected
    if selected["status"] != "observed":
        github["checks"] = empty_checks("not_applicable")
        return github

    selected["url"] = f"https://github.com/{repository_name}/pull/{selected['number']}"
    rollup = selected.pop("status_check_rollup")
    if rollup is None or rollup == []:
        github["checks"] = empty_checks("none")
        return github

    checks_argv = [
        "gh",
        "pr",
        "checks",
        str(selected["number"]),
        "-R",
        repository_name,
        "--json",
        "bucket",
    ]
    try:
        checks_result = gh(checks_argv, GH_NETWORK_TIMEOUT)
    except CommandMissing:
        github["status"] = "partial"
        github["failures"].append(safe_failure("checks_lookup", "gh_not_installed"))
        return github
    except CommandTimedOut:
        github["status"] = "partial"
        github["failures"].append(safe_failure("checks_lookup", "command_timeout"))
        return github
    if checks_result.returncode != 0:
        github["status"] = "partial"
        github["failures"].append(
            safe_failure("checks_lookup", classify_gh_failure(checks_result.stderr))
        )
        return github
    try:
        github["checks"] = parse_check_buckets(checks_result.stdout)
    except CollectorError as exc:
        github["status"] = "partial"
        github["failures"].append(safe_failure("checks_lookup", exc.reason_code))
    return github


def error_document(reason_code: str, *, git_available: bool | None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "collected_at": utc_now(),
        "repo_root": None,
        "collector": {"status": "error", "reason_code": reason_code},
        "git": {"available": git_available, "is_repository": False},
        "github": unavailable_github("local_git_unavailable"),
    }


def collect(target_text: str, runner: CommandRunner | None = None) -> tuple[dict[str, Any], int]:
    runner = runner or CommandRunner()
    target = Path(target_text).expanduser()
    if not target.exists():
        return error_document("missing_target", git_available=None), 2
    if not target.is_dir():
        return error_document("non_directory_target", git_available=None), 2
    target = target.resolve()
    try:
        git_state, repo_root = collect_git(target, runner)
    except CollectorError as exc:
        exit_code = 1 if exc.reason_code in {"git_not_installed", "git_timeout", "git_invalid_output"} else 2
        return error_document(exc.reason_code, git_available=exc.reason_code != "git_not_installed"), exit_code
    github_state = collect_github(git_state, repo_root, runner)
    return {
        "schema_version": SCHEMA_VERSION,
        "collected_at": utc_now(),
        "repo_root": str(repo_root),
        "collector": {"status": "ok", "reason_code": None},
        "git": git_state,
        "github": github_state,
    }, 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        document = error_document("invalid_arguments", git_available=None)
        print(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True))
        print("collector: invalid_arguments", file=sys.stderr)
        return 2
    try:
        document, exit_code = collect(args[0])
    except Exception:
        document = error_document("unexpected_failure", git_available=None)
        exit_code = 1
    print(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True))
    if exit_code:
        print(f"collector: {document['collector']['reason_code']}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
