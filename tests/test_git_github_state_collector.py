import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PATH = REPO_ROOT / "spikes" / "git-github-state" / "collect_state.py"
SPEC = importlib.util.spec_from_file_location("git_github_state_collector", COLLECTOR_PATH)
collector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = collector
SPEC.loader.exec_module(collector)


def result(argv, returncode=0, stdout=b"", stderr=b""):
    return collector.CommandResult(tuple(argv), returncode, stdout, stderr)


class FakeRunner:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def run(self, argv, *, cwd, timeout, env_overrides):
        call = {
            "argv": list(argv),
            "cwd": Path(cwd),
            "timeout": timeout,
            "env": dict(env_overrides),
        }
        self.calls.append(call)
        response = self.handler(call)
        if isinstance(response, Exception):
            raise response
        return response


def github_git_state(branch="feature/example", head_sha="a" * 40, remotes=None):
    return {
        "head_sha": head_sha,
        "branch": {"name": branch, "detached": False, "unborn": False},
        "working_tree": {"clean": True, "staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0},
        "upstream": {"configured": False, "ref": None, "ahead": 0, "behind": 0},
        "remotes": remotes
        if remotes is not None
        else [{"name": "origin", "github": {"host": "github.com", "name_with_owner": "Owner/Repo"}}],
    }


def repo_json():
    return json.dumps({"nameWithOwner": "Owner/Repo", "defaultBranchRef": {"name": "main"}}).encode()


def branch_json(ref):
    return json.dumps({"data": {"repository": {"ref": ref}}}).encode()


def pr_candidate(**overrides):
    candidate = {
        "number": 12,
        "state": "OPEN",
        "isDraft": True,
        "headRefName": "feature/example",
        "headRefOid": "b" * 40,
        "isCrossRepository": False,
        "headRepositoryOwner": {"login": "owner"},
        "baseRefName": "main",
        "reviewDecision": None,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "statusCheckRollup": [{"__typename": "CheckRun"}],
        "updatedAt": "2026-06-06T00:00:00Z",
    }
    candidate.update(overrides)
    return candidate


class PorcelainParserTest(unittest.TestCase):
    def test_clean_branch_with_upstream(self):
        parsed = collector.parse_porcelain_v2(
            b"# branch.oid " + b"a" * 40 + b"\0# branch.head main\0# branch.upstream origin/main\0# branch.ab +2 -3\0"
        )
        self.assertEqual(parsed["head_sha"], "a" * 40)
        self.assertEqual(parsed["branch"], {"name": "main", "detached": False, "unborn": False})
        self.assertEqual(parsed["upstream"], {"configured": True, "ref": "origin/main", "ahead": 2, "behind": 3})
        self.assertTrue(parsed["working_tree"]["clean"])

    def test_staged_unstaged_untracked_and_rename_counts_without_paths(self):
        payload = (
            b"# branch.oid " + b"a" * 40 + b"\0# branch.head feature/x\0"
            b"1 M. N... 100644 100644 100644 abc abc secret staged.txt\0"
            b"1 .M N... 100644 100644 100644 abc abc secret unstaged.txt\0"
            b"1 MM N... 100644 100644 100644 abc abc secret both.txt\0"
            b"2 R. N... 100644 100644 100644 abc abc R100 renamed secret.txt\0old secret.txt\0"
            b"? hidden secret.txt\0"
        )
        parsed = collector.parse_porcelain_v2(payload)
        self.assertEqual(parsed["working_tree"], {"clean": False, "staged": 3, "unstaged": 2, "untracked": 1, "conflicted": 0})
        self.assertNotIn("secret", json.dumps(parsed))

    def test_conflict_is_not_double_counted(self):
        payload = b"# branch.oid " + b"a" * 40 + b"\0# branch.head main\0u UU N... 100644 100644 100644 100644 a b c conflict.txt\0"
        parsed = collector.parse_porcelain_v2(payload)
        self.assertEqual(parsed["working_tree"], {"clean": False, "staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 1})

    def test_detached_head(self):
        parsed = collector.parse_porcelain_v2(b"# branch.oid " + b"a" * 40 + b"\0# branch.head (detached)\0")
        self.assertTrue(parsed["branch"]["detached"])
        self.assertIsNone(parsed["branch"]["name"])

    def test_unborn_branch(self):
        parsed = collector.parse_porcelain_v2(b"# branch.oid (initial)\0# branch.head main\0")
        self.assertTrue(parsed["branch"]["unborn"])
        self.assertIsNone(parsed["head_sha"])

    def test_invalid_branch_ab_is_rejected(self):
        with self.assertRaisesRegex(collector.CollectorError, "git_invalid_output"):
            collector.parse_porcelain_v2(b"# branch.oid " + b"a" * 40 + b"\0# branch.head main\0# branch.ab unknown\0")


class RemoteSanitizationTest(unittest.TestCase):
    def test_normal_https(self):
        self.assertEqual(
            collector.sanitize_github_url("https://github.com/owner/repo.git"),
            {"host": "github.com", "name_with_owner": "owner/repo"},
        )

    def test_ssh_url(self):
        self.assertEqual(collector.sanitize_github_url("ssh://git@github.com/owner/repo.git"), {"host": "github.com", "name_with_owner": "owner/repo"})

    def test_scp_style(self):
        self.assertEqual(collector.sanitize_github_url("git@github.com:owner/repo.git"), {"host": "github.com", "name_with_owner": "owner/repo"})

    def test_credentials_query_and_fragment_are_removed(self):
        raw = "https://user:token-secret@github.com/owner/repo.git?access=secret#fragment"
        normalized = collector.sanitize_github_url(raw)
        text = json.dumps(normalized)
        self.assertEqual(normalized["name_with_owner"], "owner/repo")
        self.assertNotIn("token-secret", text)
        self.assertNotIn("access", text)

    def test_scp_query_and_fragment_are_removed(self):
        normalized = collector.sanitize_github_url("git@github.com:owner/repo.git?secret=yes#private")
        self.assertEqual(normalized, {"host": "github.com", "name_with_owner": "owner/repo"})

    def test_non_github_remote(self):
        self.assertIsNone(collector.sanitize_github_url("https://gitlab.com/owner/repo.git"))

    def test_malformed_or_extra_path_is_rejected(self):
        self.assertIsNone(collector.sanitize_github_url("https://github.com/owner/repo/extra"))
        self.assertIsNone(collector.sanitize_github_url("https://[invalid/owner/repo"))

    def test_identity_selection_prefers_upstream_then_origin(self):
        remotes = [
            {"name": "origin", "github": {"host": "github.com", "name_with_owner": "a/one"}},
            {"name": "fork", "github": {"host": "github.com", "name_with_owner": "b/two"}},
        ]
        identity, reason = collector.choose_github_identity(remotes, "fork/topic")
        self.assertEqual(identity["name_with_owner"], "b/two")
        self.assertIsNone(reason)
        identity, _ = collector.choose_github_identity(remotes, None)
        self.assertEqual(identity["name_with_owner"], "a/one")

    def test_no_remote_unsupported_and_ambiguous(self):
        self.assertEqual(collector.choose_github_identity([], None), (None, "no_remote"))
        self.assertEqual(collector.choose_github_identity([{"name": "origin", "github": None}], None), (None, "no_supported_github_remote"))
        remotes = [
            {"name": "one", "github": {"host": "github.com", "name_with_owner": "a/one"}},
            {"name": "two", "github": {"host": "github.com", "name_with_owner": "b/two"}},
        ]
        self.assertEqual(collector.choose_github_identity(remotes, None), (None, "ambiguous_github_remote"))


class PullRequestCorrelationTest(unittest.TestCase):
    def correlate(self, candidates, branch_status="published", remote_sha="b" * 40, local_sha="a" * 40):
        return collector.correlate_pull_request(
            candidates,
            branch_name="feature/example",
            owner="OWNER",
            branch_status=branch_status,
            remote_sha=remote_sha,
            local_head_sha=local_sha,
        )

    def test_open_pr_matching_remote_sha(self):
        self.assertEqual(self.correlate([pr_candidate()])["status"], "observed")

    def test_open_pr_mismatching_remote_sha(self):
        self.assertEqual(self.correlate([pr_candidate(headRefOid="c" * 40)])["status"], "none")

    def test_fork_pr_is_rejected(self):
        self.assertEqual(self.correlate([pr_candidate(isCrossRepository=True)])["status"], "none")

    def test_mismatching_owner_is_rejected(self):
        self.assertEqual(self.correlate([pr_candidate(headRepositoryOwner={"login": "other"})])["status"], "none")

    def test_owner_comparison_is_case_insensitive(self):
        self.assertEqual(self.correlate([pr_candidate(headRepositoryOwner={"login": "OwNeR"})])["status"], "observed")

    def test_missing_or_malformed_owner_is_rejected(self):
        for owner in (None, {}, {"login": None}, {"login": ""}, "owner"):
            with self.subTest(owner=owner):
                self.assertEqual(self.correlate([pr_candidate(headRepositoryOwner=owner)])["status"], "none")

    def test_deleted_remote_branch_historical_pr_matches_local_sha(self):
        candidate = pr_candidate(state="MERGED", headRefOid="a" * 40)
        self.assertEqual(self.correlate([candidate], branch_status="not_published", remote_sha=None)["status"], "observed")

    def test_deleted_remote_branch_historical_mismatch(self):
        candidate = pr_candidate(state="MERGED", headRefOid="c" * 40)
        self.assertEqual(self.correlate([candidate], branch_status="not_published", remote_sha=None)["status"], "none")

    def test_published_reused_branch_rejects_old_historical_pr(self):
        old = pr_candidate(state="MERGED", headRefOid="a" * 40)
        self.assertEqual(self.correlate([old])["status"], "none")

    def test_matching_historical_remote_sha(self):
        historical = pr_candidate(state="CLOSED")
        self.assertEqual(self.correlate([historical])["status"], "observed")

    def test_branch_name_mismatch_is_rejected(self):
        self.assertEqual(self.correlate([pr_candidate(headRefName="other")])["status"], "none")

    def test_multiple_valid_open_or_historical_candidates_are_ambiguous(self):
        self.assertEqual(self.correlate([pr_candidate(number=1), pr_candidate(number=2)])["status"], "ambiguous")
        historical = [pr_candidate(number=1, state="MERGED"), pr_candidate(number=2, state="CLOSED")]
        self.assertEqual(self.correlate(historical)["status"], "ambiguous")

    def test_unknown_branch_state_cannot_use_local_sha_fallback(self):
        with self.assertRaisesRegex(collector.CollectorError, "invalid_branch_state"):
            self.correlate([pr_candidate(state="MERGED", headRefOid="a" * 40)], branch_status="unknown", remote_sha=None)


class CheckParserTest(unittest.TestCase):
    def parse(self, buckets):
        return collector.parse_check_buckets(json.dumps([{"bucket": bucket} for bucket in buckets]).encode())

    def test_pass_fail_pending_and_mixed(self):
        self.assertEqual(self.parse(["pass"])["overall"], "pass")
        self.assertEqual(self.parse(["fail"])["overall"], "fail")
        self.assertEqual(self.parse(["pending"])["overall"], "pending")
        mixed = self.parse(["pass", "skipping", "cancel", "pending", "fail", "pass"])
        self.assertEqual(mixed["overall"], "fail")
        self.assertEqual(mixed["pass"], 2)

    def test_empty_array(self):
        self.assertEqual(collector.parse_check_buckets(b"[]"), collector.empty_checks("none"))

    def test_malformed_non_array_and_unknown_bucket(self):
        for payload in (b"{", b"{}", b'[{"bucket":"mystery"}]', b'[{"state":"SUCCESS"}]'):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(collector.CollectorError, "invalid_json"):
                    collector.parse_check_buckets(payload)


class GitHubOrchestrationTest(unittest.TestCase):
    def runner_for(self, *, branch_ref=None, prs=None, checks=None, overrides=None):
        prs = [] if prs is None else prs
        overrides = overrides or {}

        def handler(call):
            argv = call["argv"]
            key = tuple(argv[:3])
            if key in overrides:
                value = overrides[key]
                return value(call) if callable(value) else value
            if argv[:3] == ["gh", "auth", "status"]:
                return result(argv)
            if argv[:3] == ["gh", "repo", "view"]:
                return result(
                    argv,
                    stdout=json.dumps(
                        {"nameWithOwner": argv[3], "defaultBranchRef": {"name": "main"}}
                    ).encode(),
                )
            if argv[:3] == ["gh", "api", "graphql"]:
                return result(argv, stdout=branch_json(branch_ref))
            if argv[:3] == ["gh", "pr", "list"]:
                return result(argv, stdout=json.dumps(prs).encode())
            if argv[:3] == ["gh", "pr", "checks"]:
                return result(argv, stdout=json.dumps(checks).encode())
            raise AssertionError(f"unexpected command prefix: {key}")

        return FakeRunner(handler)

    def test_auth_preflight_uses_only_active_account(self):
        runner = self.runner_for(branch_ref=None)
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        auth = runner.calls[0]["argv"]
        self.assertEqual(auth, ["gh", "auth", "status", "--active", "--hostname", "github.com"])
        self.assertNotIn("--show-token", auth)
        self.assertEqual(state["status"], "ok")

    def test_invalid_inactive_account_does_not_affect_successful_active_check(self):
        runner = self.runner_for(branch_ref=None)
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        self.assertEqual(runner.calls[0]["argv"].count("--active"), 1)
        self.assertEqual(state["status"], "ok")

    def test_nonzero_active_auth_is_unavailable_without_raw_output(self):
        secret = b"account user token scope keyring-secret"
        runner = self.runner_for(overrides={
            ("gh", "auth", "status"): result(["gh"], returncode=1, stdout=secret, stderr=secret)
        })
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        self.assertEqual(state["status"], "unavailable")
        self.assertEqual(state["reason_code"], "gh_not_authenticated")
        self.assertNotIn("keyring-secret", json.dumps(state))

    def test_graphql_argv_uses_only_raw_fields_and_preserves_strings(self):
        git_state = github_git_state(
            branch="feature/123/topic",
            remotes=[{"name": "origin", "github": {"host": "github.com", "name_with_owner": "123/456"}}],
        )
        runner = self.runner_for(branch_ref=None)
        collector.collect_github(git_state, Path("/synthetic/repo"), runner)
        argv = next(call["argv"] for call in runner.calls if call["argv"][:3] == ["gh", "api", "graphql"])
        self.assertNotIn("-F", argv)
        self.assertEqual(argv.count("-f"), 4)
        self.assertIn("owner=123", argv)
        self.assertIn("name=456", argv)
        self.assertIn("qualifiedName=refs/heads/feature/123/topic", argv)
        self.assertTrue(any(value.startswith("query=query(") for value in argv))

    def test_published_branch_and_open_pr_with_checks(self):
        sha = "b" * 40
        runner = self.runner_for(
            branch_ref={"target": {"oid": sha}},
            prs=[pr_candidate(headRefOid=sha)],
            checks=[{"bucket": "pass"}, {"bucket": "pending"}],
        )
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        self.assertEqual(state["branch"], {"status": "published", "remote_sha": sha})
        self.assertEqual(state["pull_request"]["status"], "observed")
        self.assertEqual(state["checks"]["overall"], "pending")
        self.assertEqual((state["status"], state["reason_code"], state["failures"]), ("ok", None, []))

    def test_ref_null_enables_historical_local_sha_correlation(self):
        historical = pr_candidate(state="MERGED", headRefOid="a" * 40, statusCheckRollup=[])
        runner = self.runner_for(branch_ref=None, prs=[historical])
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        self.assertEqual(state["branch"]["status"], "not_published")
        self.assertEqual(state["pull_request"]["status"], "observed")
        self.assertEqual(state["checks"], collector.empty_checks("none"))

    def test_no_pr_is_normal_and_checks_not_applicable(self):
        runner = self.runner_for(branch_ref=None, prs=[])
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["pull_request"], {"status": "none"})
        self.assertEqual(state["checks"], collector.empty_checks("not_applicable"))

    def test_null_or_empty_rollup_skips_checks_command(self):
        for rollup in (None, []):
            with self.subTest(rollup=rollup):
                runner = self.runner_for(branch_ref={"target": {"oid": "b" * 40}}, prs=[pr_candidate(statusCheckRollup=rollup)])
                state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
                self.assertEqual(state["checks"], collector.empty_checks("none"))
                self.assertFalse(any(call["argv"][:3] == ["gh", "pr", "checks"] for call in runner.calls))

    def test_nonzero_checks_exit_is_failure_even_with_valid_json(self):
        runner = self.runner_for(
            branch_ref={"target": {"oid": "b" * 40}},
            prs=[pr_candidate()],
            overrides={
                ("gh", "pr", "checks"): result(["gh"], returncode=1, stdout=b'[{"bucket":"fail"}]')
            },
        )
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        self.assertEqual(state["status"], "partial")
        self.assertEqual(state["reason_code"], None)
        self.assertEqual(state["failures"], [{"stage": "checks_lookup", "reason_code": "command_failed"}])

    def test_exit_zero_malformed_or_unknown_checks_is_invalid_json(self):
        for output in (b"{", b'[{"bucket":"unknown"}]'):
            with self.subTest(output=output):
                runner = self.runner_for(
                    branch_ref={"target": {"oid": "b" * 40}},
                    prs=[pr_candidate()],
                    overrides={("gh", "pr", "checks"): result(["gh"], stdout=output)},
                )
                state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
                self.assertEqual(state["failures"][0]["reason_code"], "invalid_json")

    def test_branch_timeout_is_partial_and_preserves_repository(self):
        runner = self.runner_for(overrides={("gh", "api", "graphql"): collector.CommandTimedOut()})
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        self.assertEqual(state["status"], "partial")
        self.assertIsNone(state["reason_code"])
        self.assertEqual(state["repository"]["default_branch"], "main")
        self.assertEqual(state["branch"]["status"], "unknown")
        self.assertEqual(state["pull_request"]["status"], "unknown")
        self.assertEqual(state["checks"]["status"], "unknown")
        self.assertEqual(state["failures"], [{"stage": "branch_lookup", "reason_code": "command_timeout"}])

    def test_branch_malformed_permission_and_graphql_errors_are_unknown(self):
        cases = [
            result(["gh"], stdout=b"{}"),
            result(["gh"], returncode=1, stderr=b"permission denied"),
            result(["gh"], stdout=b'{"errors":[{"message":"safe fixture"}]}'),
        ]
        for response in cases:
            with self.subTest(response=response):
                runner = self.runner_for(overrides={("gh", "api", "graphql"): response})
                state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
                self.assertEqual(state["branch"]["status"], "unknown")
                self.assertEqual(state["pull_request"]["status"], "unknown")
                self.assertNotEqual(state["pull_request"]["status"], "none")

    def test_initial_repository_failure_is_unavailable(self):
        runner = self.runner_for(overrides={("gh", "repo", "view"): result(["gh"], returncode=1, stderr=b"network unavailable")})
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        self.assertEqual(state["status"], "unavailable")
        self.assertEqual(state["failures"], [])

    def test_pr_query_failure_is_partial_not_none(self):
        runner = self.runner_for(
            branch_ref=None,
            overrides={("gh", "pr", "list"): result(["gh"], returncode=1, stderr=b"network unavailable")},
        )
        state = collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        self.assertEqual(state["status"], "partial")
        self.assertEqual(state["pull_request"]["status"], "unknown")

    def test_detached_unborn_no_remote_and_unsupported_are_not_applicable(self):
        cases = []
        detached = github_git_state()
        detached["branch"] = {"name": None, "detached": True, "unborn": False}
        cases.append((detached, "detached_head"))
        unborn = github_git_state(head_sha=None)
        unborn["branch"] = {"name": "main", "detached": False, "unborn": True}
        cases.append((unborn, "unborn_branch"))
        cases.append((github_git_state(remotes=[]), "no_remote"))
        cases.append((github_git_state(remotes=[{"name": "origin", "github": None}]), "no_supported_github_remote"))
        for git_state, reason in cases:
            with self.subTest(reason=reason):
                runner = FakeRunner(lambda call: (_ for _ in ()).throw(AssertionError("no command expected")))
                state = collector.collect_github(git_state, Path("/synthetic/repo"), runner)
                self.assertEqual((state["status"], state["reason_code"], state["failures"]), ("not_applicable", reason, []))

    def test_multiple_partial_failures_contract(self):
        state = {
            "status": "partial",
            "reason_code": None,
            "failures": [
                collector.safe_failure("branch_lookup", "network_unavailable"),
                collector.safe_failure("checks_lookup", "invalid_json"),
            ],
        }
        self.assertIsNone(state["reason_code"])
        self.assertEqual(set(state["failures"][0]), {"stage", "reason_code"})
        self.assertEqual(len(state["failures"]), 2)

    def test_generated_github_commands_are_read_only_allowlisted(self):
        runner = self.runner_for(
            branch_ref={"target": {"oid": "b" * 40}},
            prs=[pr_candidate()],
            checks=[{"bucket": "pass"}],
        )
        collector.collect_github(github_git_state(), Path("/synthetic/repo"), runner)
        prefixes = [tuple(call["argv"][:3]) for call in runner.calls]
        self.assertEqual(
            prefixes,
            [
                ("gh", "auth", "status"),
                ("gh", "repo", "view"),
                ("gh", "api", "graphql"),
                ("gh", "pr", "list"),
                ("gh", "pr", "checks"),
            ],
        )
        forbidden = {"create", "edit", "merge", "close", "delete"}
        self.assertFalse(any(forbidden.intersection(call["argv"]) for call in runner.calls))


class RealGitIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test User")
        self.git("config", "user.email", "test@example.invalid")

    def git(self, *args, cwd=None, check=True):
        return subprocess.run(
            ["git", *args], cwd=cwd or self.root, text=True, capture_output=True, check=check
        )

    def commit_file(self, name="tracked.txt", content="one\n"):
        (self.root / name).write_text(content, encoding="utf-8")
        self.git("add", name)
        self.git("commit", "-m", "fixture")

    def collect_git(self):
        return collector.collect_git(self.root, collector.CommandRunner())[0]

    def test_clean_repository_and_no_remote_or_upstream(self):
        self.commit_file()
        state = self.collect_git()
        self.assertTrue(state["working_tree"]["clean"])
        self.assertFalse(state["upstream"]["configured"])
        self.assertEqual(state["remotes"], [])

    def test_staged_unstaged_untracked_and_simultaneous_changes(self):
        self.commit_file()
        (self.root / "tracked.txt").write_text("two\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        (self.root / "tracked.txt").write_text("three\n", encoding="utf-8")
        (self.root / "untracked.txt").write_text("private\n", encoding="utf-8")
        state = self.collect_git()
        self.assertEqual(state["working_tree"], {"clean": False, "staged": 1, "unstaged": 1, "untracked": 1, "conflicted": 0})

    def test_branch_name_with_slash_and_detached_head(self):
        self.commit_file()
        self.git("switch", "-c", "feature/with/slash")
        self.assertEqual(self.collect_git()["branch"]["name"], "feature/with/slash")
        self.git("checkout", "--detach")
        self.assertTrue(self.collect_git()["branch"]["detached"])

    def test_unborn_repository(self):
        state = self.collect_git()
        self.assertTrue(state["branch"]["unborn"])
        self.assertIsNone(state["head_sha"])

    def test_unusual_filename_never_appears_in_output(self):
        self.commit_file()
        unusual = "private name with spaces\nand-newline.txt"
        (self.root / unusual).write_text("secret\n", encoding="utf-8")
        state = self.collect_git()
        self.assertEqual(state["working_tree"]["untracked"], 1)
        self.assertNotIn("private name", json.dumps(state))

    def test_ahead_and_behind_with_local_bare_remote(self):
        self.commit_file()
        bare = Path(self.temp.name) / "remote.git"
        self.git("init", "--bare", str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("push", "-u", "origin", "main")
        self.git("symbolic-ref", "HEAD", "refs/heads/main", cwd=bare)
        clone = Path(self.temp.name) / "clone"
        self.git("clone", "--branch", "main", str(bare), str(clone))
        self.git("config", "user.name", "Test User", cwd=clone)
        self.git("config", "user.email", "test@example.invalid", cwd=clone)
        (clone / "remote.txt").write_text("remote\n", encoding="utf-8")
        self.git("add", "remote.txt", cwd=clone)
        self.git("commit", "-m", "remote", cwd=clone)
        self.git("push", cwd=clone)
        self.git("fetch", "origin")
        (self.root / "local.txt").write_text("local\n", encoding="utf-8")
        self.git("add", "local.txt")
        self.git("commit", "-m", "local")
        state = self.collect_git()
        self.assertEqual(state["upstream"]["ahead"], 1)
        self.assertEqual(state["upstream"]["behind"], 1)

    def test_bare_repository_is_distinct_from_non_git(self):
        bare = Path(self.temp.name) / "bare.git"
        self.git("init", "--bare", str(bare))
        document, exit_code = collector.collect(str(bare))
        self.assertEqual(exit_code, 2)
        self.assertEqual(document["collector"]["reason_code"], "bare_git_repository")
        non_git = Path(self.temp.name) / "plain"
        non_git.mkdir()
        document, exit_code = collector.collect(str(non_git))
        self.assertEqual(exit_code, 2)
        self.assertEqual(document["collector"]["reason_code"], "not_git_repository")

    def test_missing_and_non_directory_targets(self):
        document, exit_code = collector.collect(str(Path(self.temp.name) / "missing"))
        self.assertEqual((exit_code, document["collector"]["reason_code"]), (2, "missing_target"))
        file_target = Path(self.temp.name) / "file"
        file_target.write_text("x", encoding="utf-8")
        document, exit_code = collector.collect(str(file_target))
        self.assertEqual((exit_code, document["collector"]["reason_code"]), (2, "non_directory_target"))


class ProcessSafetyTest(unittest.TestCase):
    @mock.patch.object(subprocess, "run")
    def test_runner_uses_shell_false_timeout_noninteractive_and_separate_capture(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(["git"], 0, stdout=b"ok", stderr=b"safe")
        runner = collector.CommandRunner()
        runner.run(["git", "status"], cwd=Path("/synthetic/repo"), timeout=10, env_overrides=collector.GIT_ENV)
        kwargs = run_mock.call_args.kwargs
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], 10)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(kwargs["stderr"], subprocess.PIPE)
        self.assertEqual(kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(kwargs["env"]["LC_ALL"], "C")

    def test_deterministic_json_has_one_document_and_trailing_newline(self):
        document = collector.error_document("", "fixture")
        rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        self.assertEqual(json.loads(rendered)["collector"]["reason_code"], "fixture")
        self.assertTrue(rendered.endswith("\n"))

    def test_failure_entries_have_safe_fields_only(self):
        failure = collector.safe_failure("branch_lookup", "network_unavailable")
        self.assertEqual(set(failure), {"stage", "reason_code"})


if __name__ == "__main__":
    unittest.main()
