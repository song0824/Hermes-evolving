import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import job_lock
bothub_invoke = importlib.import_module("bothub_invoke")
weekly_meeting = importlib.import_module("weekly_tech_meeting")
weekly_reminder = importlib.import_module("weekly_report_reminder")

OPS_GROUP = "oc_611b7861968a34f8c2f538f67410b629"
TEST_GROUP = "oc_8b8978c0510660ec4da3c52ebc7bb9a3"
ALERT_TEXT = "查询：lingos-online 今天 Error 分布\n告警原文：服务错误日志升高"


def _request(capability: str, text: str = "填写周报", confirmed: bool | None = None) -> dict:
    payload = {
        "protocol_version": "1.0",
        "identity": {"target_bot_id": "hermes-evolving", "target_capability": capability},
        "task": {"task_id": "task-1", "trace_id": "trace-1"},
        "input": {"text": text, "context": ["上一句"]},
    }
    if confirmed is not None:
        payload["constraints"] = {"confirmed": confirmed}
    return payload


def test_unconfirmed_reminder_does_not_run_script(monkeypatch):
    def fail_if_called(script, timeout):
        raise AssertionError(script)

    monkeypatch.setattr(bothub_invoke, "run_script", fail_if_called)
    status, body = bothub_invoke.handle(_request("hermes.weekly_report.reminder", confirmed=False))
    assert status == 200
    assert body["status"] == "waiting_confirm"
    assert body["error"]["code"] == "CONFIRM_REQUIRED"


def test_confirmed_script_stdout_becomes_summary(tmp_path, monkeypatch):
    script = tmp_path / "fake_reminder.py"
    script.write_text("print('催填完成')\n", encoding="utf-8")
    spec = bothub_invoke.CAPABILITIES["hermes.weekly_report.reminder"]
    monkeypatch.setitem(spec, "path", str(script))
    status, body = bothub_invoke.handle(_request("hermes.weekly_report.reminder", confirmed=True))
    assert status == 200
    assert body["status"] == "success"
    assert body["summary"] == "催填完成"
    assert body["task"]["trace_id"] == "trace-1"


def test_sls_sends_input_text_unchanged(monkeypatch):
    captured = {}

    def fake_preload(identifiers):
        assert identifiers == ["alibabacloud-sls-query", "daily-sls-error-analysis"]
        return "技能正文", ["alibabacloud-sls-query"], []

    def fake_turn(system_prompt, text, context):
        captured["system_prompt"] = system_prompt
        captured["text"] = text
        captured["context"] = context
        return {"final_response": "日志结论", "usage": {"input_tokens": 3, "output_tokens": 4}}

    monkeypatch.setattr(bothub_invoke, "preload", fake_preload)
    monkeypatch.setattr(bothub_invoke, "run_skill_turn", fake_turn)
    status, body = bothub_invoke.handle(_request("hermes.log.sls", text=ALERT_TEXT))
    assert status == 200
    assert body["summary"] == "日志结论"
    assert body["usage"]["input_tokens"] == 3
    assert captured["text"] == ALERT_TEXT
    assert captured["context"] == ["上一句"]
    assert "技能正文" in captured["system_prompt"]
    assert "不要改写告警原文" in captured["system_prompt"]
    assert ALERT_TEXT not in captured["system_prompt"]


def test_unknown_capability():
    status, body = bothub_invoke.handle(_request("hermes.not.real"))
    assert status == 200
    assert body["error"]["code"] == "CAPABILITY_NOT_FOUND"


def test_missing_skill_does_not_call_chat(monkeypatch):
    def fail_if_called(system_prompt, text, context):
        raise AssertionError("agent should not be called")

    monkeypatch.setattr(bothub_invoke, "preload", lambda identifiers: ("", [], identifiers))
    monkeypatch.setattr(bothub_invoke, "run_skill_turn", fail_if_called)
    status, body = bothub_invoke.handle(_request("hermes.code.review", text="看一下这段 diff"))
    assert status == 200
    assert body["status"] == "failed"
    assert "hermes.code.review" in body["summary"]


def test_chat_error_json_is_not_summary(monkeypatch):
    monkeypatch.setattr(bothub_invoke, "preload", lambda identifiers: ("技能正文", ["image-generation"], []))
    monkeypatch.setattr(
        bothub_invoke,
        "run_skill_turn",
        lambda system_prompt, text, context: {
            "failed": True,
            "final_response": "sk-secret-should-not-leak",
        },
    )
    status, body = bothub_invoke.handle(_request("hermes.image.generate", text="画一张"))
    assert status == 200
    assert body["status"] == "failed"
    assert "sk-secret" not in json.dumps(body, ensure_ascii=False)


def test_bad_token_is_unauthorized(monkeypatch):
    monkeypatch.setenv("API_SERVER_KEY", "expected-token")
    assert bothub_invoke.authorized("Bearer wrong-token") is False
    assert bothub_invoke.authorized("Bearer expected-token") is True


def test_notify_chat_argument_does_not_read_environment(monkeypatch):
    monkeypatch.setenv("HERMES_NOTIFY_CHAT_ID", TEST_GROUP)
    assert weekly_reminder.notify_chat_id() == OPS_GROUP
    assert weekly_meeting.message_chat_id() == OPS_GROUP
    assert OPS_GROUP in {chat for chat, _label in weekly_meeting.permission_targets()}
    assert weekly_reminder.notify_chat_id(TEST_GROUP) == TEST_GROUP
    assert weekly_meeting.message_chat_id(TEST_GROUP) == TEST_GROUP
    assert weekly_meeting.permission_targets(TEST_GROUP) == ((TEST_GROUP, "notify"),)


def test_adapter_passes_notify_chat_only_from_its_env(tmp_path, monkeypatch):
    script = tmp_path / "fake_reminder.py"
    script.write_text(
        "import sys\nprint('ARGS:' + ' '.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    spec = bothub_invoke.CAPABILITIES["hermes.weekly_report.reminder"]
    monkeypatch.setitem(spec, "path", str(script))
    monkeypatch.delenv("HERMES_NOTIFY_CHAT_ID", raising=False)
    _status, body = bothub_invoke.handle(_request("hermes.weekly_report.reminder", confirmed=True))
    assert body["summary"] == "ARGS:"

    monkeypatch.setenv("HERMES_NOTIFY_CHAT_ID", TEST_GROUP)
    _status, body = bothub_invoke.handle(_request("hermes.weekly_report.reminder", confirmed=True))
    assert body["summary"] == f"ARGS:--notify-chat {TEST_GROUP}"


def test_script_failure_uses_stdout_not_stderr(tmp_path, monkeypatch):
    script = tmp_path / "fake_fail.py"
    script.write_text(
        "import sys\nprint('open_id=ou_should_not_surface', file=sys.stderr)\nprint('催填消息发送失败，通知没有改发到其他群。')\nraise SystemExit(1)\n",
        encoding="utf-8",
    )
    spec = bothub_invoke.CAPABILITIES["hermes.weekly_report.reminder"]
    monkeypatch.setitem(spec, "path", str(script))
    _status, body = bothub_invoke.handle(_request("hermes.weekly_report.reminder", confirmed=True))
    assert body["status"] == "failed"
    assert body["summary"] == "催填消息发送失败，通知没有改发到其他群。"
    assert "ou_should_not_surface" not in body["summary"]


def test_job_lock_blocks_second_holder(tmp_path):
    first = job_lock.acquire_job_lock("weekly-report-test", tmp_path)
    second = job_lock.acquire_job_lock("weekly-report-test", tmp_path)
    assert first is not None
    assert second is None
    job_lock.release_job_lock(first)
    third = job_lock.acquire_job_lock("weekly-report-test", tmp_path)
    assert third is not None
    job_lock.release_job_lock(third)
