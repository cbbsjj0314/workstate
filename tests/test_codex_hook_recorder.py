import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDER = REPO_ROOT / "spikes" / "codex-hooks" / "record_event.py"
SECRET_PROMPT = "please edit password=super-secret\nWorkState-Handoff-ID: ws_01JABCDEF234567890"
SECRET_MESSAGE = "assistant response with token secret-output"


class RecorderTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.log_path = Path(self.tmpdir.name) / "data" / "codex.jsonl"

    def run_recorder(self, argv_event, payload, log_path=None):
        env = os.environ.copy()
        env["WORKSTATE_CODEX_EVENT_LOG"] = str(log_path or self.log_path)
        input_text = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(
            [sys.executable, str(RECORDER), argv_event],
            input=input_text,
            text=True,
            capture_output=True,
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )

    def read_records(self):
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines()]

    def base_payload(self, event_name):
        return {
            "hook_event_name": event_name,
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": str(REPO_ROOT),
            "model": "gpt-test",
            "permission_mode": "plan",
        }

    def test_session_start(self):
        payload = self.base_payload("SessionStart")
        payload["turn_id"] = None
        payload["source"] = "startup"

        result = self.run_recorder("SessionStart", payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        record = self.read_records()[0]
        self.assertEqual(record["hook_event_name"], "SessionStart")
        self.assertEqual(record["session_id"], "session-1")
        self.assertIsNone(record["turn_id"])
        self.assertEqual(record["permission_mode"], "plan")
        self.assertEqual(record["event_data"]["session_start_source"], "startup")

    def test_user_prompt_submit(self):
        payload = self.base_payload("UserPromptSubmit")
        payload["prompt"] = SECRET_PROMPT

        self.run_recorder("UserPromptSubmit", payload)

        record = self.read_records()[0]
        self.assertEqual(record["event_data"]["prompt_length"], len(SECRET_PROMPT))
        self.assertEqual(
            record["event_data"]["prompt_sha256"],
            hashlib.sha256(SECRET_PROMPT.encode("utf-8")).hexdigest(),
        )
        self.assertTrue(record["event_data"]["workstate_handoff_id_detected"])
        self.assertEqual(record["event_data"]["workstate_handoff_id"], "ws_01JABCDEF234567890")

    def test_post_tool_use_apply_patch(self):
        payload = self.base_payload("PostToolUse")
        payload.update(
            {
                "tool_name": "apply_patch",
                "tool_use_id": "tool-1",
                "tool_input": {"patch": "source code secret"},
                "tool_response": {"output": "tool response secret"},
            }
        )

        self.run_recorder("PostToolUse", payload)

        event_data = self.read_records()[0]["event_data"]
        self.assertEqual(event_data["tool_name"], "apply_patch")
        self.assertTrue(event_data["file_edit_candidate"])
        self.assertNotIn("source code secret", json.dumps(event_data))
        self.assertNotIn("tool response secret", json.dumps(event_data))
        self.assertTrue(event_data["tool_response_present"])

    def test_post_tool_use_apply_patch_aliases(self):
        for alias in ("Edit", "Write"):
            with self.subTest(alias=alias):
                alias_log = Path(self.tmpdir.name) / alias / "codex.jsonl"
                payload = self.base_payload("PostToolUse")
                payload.update({"tool_name": alias, "tool_use_id": f"tool-{alias}", "tool_input": {}})

                self.run_recorder("PostToolUse", payload, log_path=alias_log)

                record = json.loads(alias_log.read_text(encoding="utf-8").splitlines()[0])
                self.assertEqual(record["event_data"]["tool_name"], "apply_patch")
                self.assertTrue(record["event_data"]["file_edit_candidate"])

    def test_post_tool_use_bash_is_not_file_edit_candidate(self):
        payload = self.base_payload("PostToolUse")
        payload.update(
            {
                "tool_name": "Bash",
                "tool_use_id": "tool-2",
                "tool_input": {"cmd": "cat secret.txt"},
                "tool_response": None,
            }
        )

        self.run_recorder("PostToolUse", payload)

        event_data = self.read_records()[0]["event_data"]
        self.assertEqual(event_data["tool_name"], "Bash")
        self.assertFalse(event_data["file_edit_candidate"])
        self.assertFalse(event_data["tool_response_present"])
        self.assertNotIn("cat secret.txt", json.dumps(event_data))

    def test_stop_outputs_json_preserves_inactive_stop_hook_flag_and_hashes_message(self):
        payload = self.base_payload("Stop")
        payload["stop_hook_active"] = False
        payload["last_assistant_message"] = SECRET_MESSAGE

        result = self.run_recorder("Stop", payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '{"continue":true}')
        event_data = self.read_records()[0]["event_data"]
        self.assertFalse(event_data["stop_hook_active"])
        self.assertTrue(event_data["last_assistant_message_present"])
        self.assertEqual(event_data["last_assistant_message_length"], len(SECRET_MESSAGE))
        self.assertEqual(
            event_data["last_assistant_message_sha256"],
            hashlib.sha256(SECRET_MESSAGE.encode("utf-8")).hexdigest(),
        )

    def test_stop_preserves_active_stop_hook_flag(self):
        payload = self.base_payload("Stop")
        payload["stop_hook_active"] = True

        result = self.run_recorder("Stop", payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '{"continue":true}')
        event_data = self.read_records()[0]["event_data"]
        self.assertTrue(event_data["stop_hook_active"])
        self.assertFalse(event_data["last_assistant_message_present"])
        self.assertEqual(event_data["last_assistant_message_length"], 0)
        self.assertIsNone(event_data["last_assistant_message_sha256"])

    def test_missing_optional_fields_are_null(self):
        payload = {"hook_event_name": "SessionStart", "cwd": str(REPO_ROOT), "source": "startup"}

        self.run_recorder("SessionStart", payload)

        record = self.read_records()[0]
        self.assertIsNone(record["session_id"])
        self.assertIsNone(record["turn_id"])
        self.assertIsNone(record["model"])
        self.assertIsNone(record["permission_mode"])

    def test_missing_required_session_start_source_is_fail_open_without_persisting(self):
        payload = self.base_payload("SessionStart")

        result = self.run_recorder("SessionStart", payload)

        self.assertEqual(result.returncode, 0)
        self.assertIn("required hook input field", result.stderr)
        self.assertFalse(self.log_path.exists())

    def test_missing_required_user_prompt_is_fail_open_without_persisting(self):
        payload = self.base_payload("UserPromptSubmit")

        result = self.run_recorder("UserPromptSubmit", payload)

        self.assertEqual(result.returncode, 0)
        self.assertIn("required hook input field", result.stderr)
        self.assertFalse(self.log_path.exists())

    def test_non_string_user_prompt_is_fail_open_without_persisting(self):
        payload = self.base_payload("UserPromptSubmit")
        payload["prompt"] = {"text": SECRET_PROMPT}

        result = self.run_recorder("UserPromptSubmit", payload)

        self.assertEqual(result.returncode, 0)
        self.assertIn("required hook input field", result.stderr)
        self.assertFalse(self.log_path.exists())

    def test_missing_required_post_tool_use_tool_input_is_fail_open_without_persisting(self):
        payload = self.base_payload("PostToolUse")
        payload.update({"tool_name": "Bash", "tool_use_id": "tool-1"})

        result = self.run_recorder("PostToolUse", payload)

        self.assertEqual(result.returncode, 0)
        self.assertIn("required hook input field", result.stderr)
        self.assertFalse(self.log_path.exists())

    def test_missing_required_stop_active_flag_is_fail_open_with_stop_json(self):
        payload = self.base_payload("Stop")

        result = self.run_recorder("Stop", payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '{"continue":true}')
        self.assertIn("required hook input field", result.stderr)
        self.assertFalse(self.log_path.exists())

    def test_malformed_json_is_fail_open_without_persisting(self):
        result = self.run_recorder("UserPromptSubmit", "{not-json")

        self.assertEqual(result.returncode, 0)
        self.assertIn("malformed hook input JSON", result.stderr)
        self.assertFalse(self.log_path.exists())

    def test_mismatched_argv_and_stdin_event_is_fail_open_without_persisting(self):
        payload = self.base_payload("UserPromptSubmit")

        result = self.run_recorder("Stop", payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '{"continue":true}')
        self.assertIn("missing or mismatched", result.stderr)
        self.assertFalse(self.log_path.exists())

    def test_output_directory_creation_and_posix_permissions(self):
        payload = self.base_payload("SessionStart")
        payload["source"] = "startup"

        self.run_recorder("SessionStart", payload)

        self.assertTrue(self.log_path.exists())
        if os.name == "posix":
            dir_mode = stat.S_IMODE(self.log_path.parent.stat().st_mode)
            file_mode = stat.S_IMODE(self.log_path.stat().st_mode)
            self.assertEqual(dir_mode, 0o700)
            self.assertEqual(file_mode, 0o600)

    def test_multiple_sequential_event_appends(self):
        session_payload = self.base_payload("SessionStart")
        session_payload["source"] = "startup"
        prompt_payload = self.base_payload("UserPromptSubmit")
        prompt_payload["prompt"] = SECRET_PROMPT

        self.run_recorder("SessionStart", session_payload)
        self.run_recorder("UserPromptSubmit", prompt_payload)

        records = self.read_records()
        self.assertEqual([r["hook_event_name"] for r in records], ["SessionStart", "UserPromptSubmit"])

    def test_sensitive_raw_text_is_not_persisted(self):
        prompt_payload = self.base_payload("UserPromptSubmit")
        prompt_payload["prompt"] = SECRET_PROMPT
        stop_payload = self.base_payload("Stop")
        stop_payload["stop_hook_active"] = False
        stop_payload["last_assistant_message"] = SECRET_MESSAGE

        self.run_recorder("UserPromptSubmit", prompt_payload)
        self.run_recorder("Stop", stop_payload)

        log_text = self.log_path.read_text(encoding="utf-8")
        self.assertNotIn("super-secret", log_text)
        self.assertNotIn("secret-output", log_text)
        self.assertNotIn(SECRET_PROMPT, log_text)
        self.assertNotIn(SECRET_MESSAGE, log_text)

    def test_digests_are_deterministic(self):
        prompt_payload = self.base_payload("UserPromptSubmit")
        prompt_payload["prompt"] = SECRET_PROMPT
        stop_payload = self.base_payload("Stop")
        stop_payload["stop_hook_active"] = False
        stop_payload["last_assistant_message"] = SECRET_MESSAGE

        self.run_recorder("UserPromptSubmit", prompt_payload)
        self.run_recorder("UserPromptSubmit", prompt_payload)
        self.run_recorder("Stop", stop_payload)
        self.run_recorder("Stop", stop_payload)

        records = self.read_records()
        self.assertEqual(records[0]["event_data"]["prompt_sha256"], records[1]["event_data"]["prompt_sha256"])
        self.assertEqual(
            records[2]["event_data"]["last_assistant_message_sha256"],
            records[3]["event_data"]["last_assistant_message_sha256"],
        )

    def test_session_and_turn_correlation_fields_are_preserved(self):
        payload = self.base_payload("PostToolUse")
        payload.update({"tool_name": "Bash", "tool_use_id": "tool-3", "tool_input": {}})

        self.run_recorder("PostToolUse", payload)

        record = self.read_records()[0]
        self.assertEqual(record["session_id"], "session-1")
        self.assertEqual(record["turn_id"], "turn-1")

    def test_log_inside_repo_fails_open(self):
        payload = self.base_payload("SessionStart")
        payload["source"] = "startup"
        repo_log = REPO_ROOT / ".workstate-test-events.jsonl"
        try:
            result = self.run_recorder("SessionStart", payload, log_path=repo_log)
            self.assertEqual(result.returncode, 0)
            self.assertIn("recorder failure", result.stderr)
            self.assertFalse(repo_log.exists())
        finally:
            if repo_log.exists():
                repo_log.unlink()


if __name__ == "__main__":
    unittest.main()
