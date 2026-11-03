"""BotHub bothub.v1 adapter. Binds 127.0.0.1:8643 and dispatches by capability name."""

from __future__ import annotations

import hmac
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_TIMEOUT = 90
CHAT_TIMEOUT = 150
BIND_HOST = "127.0.0.1"
BIND_PORT = 8643
AUTH_ENV = "API_SERVER_KEY"
TARGET_BOT = "hermes-evolving"
PROTOCOL_VERSION = "1.0"
SKILL_RULE = "本轮只按该技能处理下面的用户原文；不要再加载其他技能；结果用飞书纯文本，不要输出思考过程。"

CAPABILITIES: dict[str, dict[str, object]] = {
    "hermes.weekly_report.reminder": {
        "kind": "script",
        "path": "scripts/weekly_report_reminder.py",
        "confirm": True,
    },
    "hermes.weekly_meeting.create": {
        "kind": "script",
        "path": "scripts/weekly_tech_meeting.py",
        "confirm": True,
    },
    "hermes.log.sls": {
        "kind": "skill",
        "skills": ["alibabacloud-sls-query"],
        "daily_error_skill": "daily-sls-error-analysis",
        "note": "不要新建或修改文档。不要改写告警原文。",
    },
    "hermes.debug.plan": {
        "kind": "skill",
        "skills": ["systematic-debugging"],
        "note": "只给排查步骤，不改代码。不要新建或修改文档。",
    },
    "hermes.tech.analyze": {
        "kind": "skill",
        "skills": [],
        "note": "按用户原文回答。不要新建或修改文档。",
    },
    "hermes.tech.design": {
        "kind": "skill",
        "skills": [],
        "note": "按用户原文给出方案。不要新建或修改文档。",
    },
    "hermes.code.review": {
        "kind": "skill",
        "skills": ["github-code-review"],
        "note": "不要新建或修改文档。",
    },
    "hermes.task.reminder": {
        "kind": "skill",
        "skills": [],
        "confirm": True,
        "note": "使用 cron 创建提醒，不要运行周报脚本。",
    },
    "hermes.feishu.doc": {
        "kind": "skill",
        "skills": ["feishu-doc-api"],
        "note": "只读。不要新建或修改文档。",
    },
    "hermes.feishu.bitable": {
        "kind": "skill",
        "skills": ["feishu-bitable-api"],
        "note": "只读。不要新建或修改文档。",
    },
    "hermes.lingos.role": {
        "kind": "skill",
        "skills": ["lingos-platform"],
        "note": "不要新建或修改文档。",
    },
    "hermes.data.magic_camera": {
        "kind": "skill",
        "skills": ["magic-camera-analysis"],
        "note": "不要新建或修改文档。",
    },
    "hermes.data.rds": {
        "kind": "skill",
        "skills": [],
        "note": "只读 SQL 或慢日志，禁止改数据。不要新建或修改文档。",
    },
    "hermes.image.generate": {
        "kind": "skill",
        "skills": ["image-generation"],
    },
    "hermes.media.transcript": {
        "kind": "skill",
        "skills": ["video-transcript-to-feishu-doc"],
        "confirm": True,
    },
    "hermes.news.weekly": {
        "kind": "skill",
        "skills": ["weekly-ai-trends"],
        "note": "输出飞书纯文本。不要新建或修改文档。",
    },
}

_missing_key_logged = False


def api_key() -> str:
    return os.environ.get(AUTH_ENV, "").strip()


def authorized(header: str | None) -> bool:
    global _missing_key_logged
    expected = api_key()
    if not expected:
        if not _missing_key_logged:
            print(f"缺少环境变量 {AUTH_ENV}", file=sys.stderr)
            _missing_key_logged = True
        return False
    if not header:
        return False
    scheme, _, token = header.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return False
    return hmac.compare_digest(token.strip(), expected)


def preload(identifiers: list[str]) -> tuple[str, list[str], list[str]]:
    agent_root = HERMES_ROOT / "hermes-agent"
    agent_path = str(agent_root)
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)
    from agent.skill_commands import build_preloaded_skills_prompt

    return build_preloaded_skills_prompt(identifiers)


def run_script(
    script: Path,
    timeout: float,
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(script), *(args or [])],
        cwd=str(HERMES_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )


def run_skill_turn(system_prompt: str, text: str, context: list[str]) -> dict[str, object]:
    agent_root = HERMES_ROOT / "hermes-agent"
    source = (agent_root / "run_agent.py").read_text(encoding="utf-8")
    if "class AIAgent" not in source:
        raise RuntimeError("AIAgent is not available")
    agent_path = str(agent_root)
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)
    from hermes_constants import get_hermes_home
    from hermes_cli.env_loader import load_hermes_dotenv

    home = get_hermes_home()
    load_hermes_dotenv(hermes_home=home, project_env=agent_root / ".env")
    model = ""
    base_url = None
    provider = "auto"
    config_path = home / "config.yaml"
    if config_path.is_file():
        import yaml

        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        model_cfg = loaded.get("model") if isinstance(loaded, dict) else None
        if isinstance(model_cfg, dict):
            model = str(model_cfg.get("default") or "")
            base_url = model_cfg.get("base_url") or None
            provider = str(model_cfg.get("provider") or "auto")
    if base_url and "openrouter.ai" in str(base_url):
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    else:
        key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    from run_agent import AIAgent

    history = [{"role": "user", "content": item} for item in context]
    agent = AIAgent(
        model=model,
        api_key=key,
        base_url=base_url,
        provider=provider,
        quiet_mode=True,
        ephemeral_system_prompt=system_prompt or None,
        platform="cli",
    )
    result = agent.run_conversation(user_message=text, conversation_history=history)
    return result if isinstance(result, dict) else {"final_response": str(result)}


def handle(payload: object) -> tuple[int, dict[str, object]]:
    if not isinstance(payload, dict):
        return 200, _response(None, "failed", "请求与协议不一致", "INVALID_REQUEST")
    task = payload.get("task") if isinstance(payload.get("task"), dict) else None
    if payload.get("protocol_version") != PROTOCOL_VERSION:
        return 200, _response(task, "failed", "请求与协议不一致", "INVALID_REQUEST")
    identity = payload.get("identity")
    if not isinstance(identity, dict) or identity.get("target_bot_id") != TARGET_BOT:
        return 200, _response(task, "failed", "请求与协议不一致", "INVALID_REQUEST")
    capability = identity.get("target_capability")
    if not isinstance(capability, str) or capability not in CAPABILITIES:
        return 200, _response(task, "failed", "没有这个能力", "CAPABILITY_NOT_FOUND")
    spec = CAPABILITIES[capability]
    if spec.get("confirm") and not _confirmed(payload):
        return 200, _response(
            task,
            "waiting_confirm",
            "这个能力需要确认后才会执行，本次没有改任何数据。",
            "CONFIRM_REQUIRED",
        )
    if spec["kind"] == "script":
        return 200, _run_script_capability(task, spec)
    return 200, _run_skill_capability(task, payload, capability, spec)


def _confirmed(payload: dict[str, object]) -> bool:
    constraints = payload.get("constraints")
    return isinstance(constraints, dict) and constraints.get("confirmed") is True


def _run_script_capability(task: dict[str, object] | None, spec: dict[str, object]) -> dict[str, object]:
    raw_path = Path(str(spec["path"]))
    script = raw_path if raw_path.is_absolute() else HERMES_ROOT / raw_path
    notify_chat = os.environ.get("HERMES_NOTIFY_CHAT_ID", "").strip()
    script_args = ["--notify-chat", notify_chat] if notify_chat else None
    try:
        completed = run_script(script, SCRIPT_TIMEOUT, script_args)
    except subprocess.TimeoutExpired:
        print("script timeout", file=sys.stderr)
        return _response(task, "failed", "这个能力执行超时")
    except OSError:
        print("script failed to start", file=sys.stderr)
        return _response(task, "failed", "这个能力执行失败")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr)
    summary = (completed.stdout or "").strip() or "这个能力执行失败"
    if completed.returncode != 0:
        return _response(task, "failed", summary)
    return _response(task, "success", summary)


def _run_skill_capability(
    task: dict[str, object] | None,
    payload: dict[str, object],
    capability: str,
    spec: dict[str, object],
) -> dict[str, object]:
    text, context = _input_parts(payload)
    skills = [str(item) for item in spec.get("skills") or []]
    extra = spec.get("daily_error_skill")
    if isinstance(extra, str) and extra and _wants_daily_error(text):
        skills.append(extra)
    system_parts: list[str] = []
    if skills:
        try:
            prompt, loaded, missing = preload(skills)
        except Exception:
            print(f"skill preload failed for {capability}", file=sys.stderr)
            return _response(task, "failed", f"{capability} 没有加载到技能")
        if missing or not loaded:
            return _response(task, "failed", f"{capability} 没有加载到技能")
        if prompt:
            system_parts.append(prompt)
    system_parts.append(SKILL_RULE)
    note = spec.get("note")
    if isinstance(note, str) and note:
        system_parts.append(note)
    system_prompt = "\n\n".join(system_parts)
    box: dict[str, object] = {}

    def target() -> None:
        try:
            box["result"] = run_skill_turn(system_prompt, text, context)
        except Exception as exc:
            box["error"] = exc.__class__.__name__

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(CHAT_TIMEOUT)
    if worker.is_alive():
        return _response(task, "failed", "爱马仕聊天响应超时")
    if box.get("error"):
        print(f"skill turn failed: {box['error']}", file=sys.stderr)
        return _response(task, "failed", "爱马仕聊天服务暂时不可用")
    result = box.get("result")
    if not isinstance(result, dict) or result.get("failed"):
        return _response(task, "failed", "爱马仕聊天没有返回可用结果")
    content = result.get("final_response")
    if not isinstance(content, str) or not content.strip():
        return _response(task, "failed", "爱马仕聊天没有返回可用结果")
    return _response(task, "success", content.strip(), usage=_usage(result.get("usage")))


def _input_parts(payload: dict[str, object]) -> tuple[str, list[str]]:
    incoming = payload.get("input")
    if not isinstance(incoming, dict):
        return "", []
    text = incoming.get("text")
    context = incoming.get("context")
    clean_context = [item for item in context if isinstance(item, str)] if isinstance(context, list) else []
    return text if isinstance(text, str) else "", clean_context


def _wants_daily_error(text: str) -> bool:
    folded = text.lower()
    return "分布" in text and ("error" in folded or "错误" in text)


def _usage(raw: object) -> dict[str, int | None]:
    usage = {"input_tokens": None, "output_tokens": None}
    if not isinstance(raw, dict):
        return usage
    prompt = raw.get("prompt_tokens", raw.get("input_tokens"))
    completion = raw.get("completion_tokens", raw.get("output_tokens"))
    if isinstance(prompt, int) and not isinstance(prompt, bool):
        usage["input_tokens"] = prompt
    if isinstance(completion, int) and not isinstance(completion, bool):
        usage["output_tokens"] = completion
    return usage


def _response(
    task: dict[str, object] | None,
    status: str,
    summary: str,
    code: str | None = None,
    usage: dict[str, int | None] | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "protocol_version": PROTOCOL_VERSION,
        "status": status,
        "summary": summary,
        "usage": usage or {"input_tokens": None, "output_tokens": None},
    }
    if code:
        body["error"] = {"code": code, "message": summary}
    if task:
        echo = {
            key: task[key]
            for key in ("task_id", "trace_id", "parent_task_id", "depth")
            if key in task
        }
        if echo:
            body["task"] = echo
    return body


class InvokeHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/bothub/v1/invoke":
            self._send(404, _response(None, "failed", "路径不存在", "INVALID_REQUEST"))
            return
        if not authorized(self.headers.get("Authorization")):
            self._send(401, _response(None, "failed", "调用凭证无效", "UNAUTHORIZED"))
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length < 0 or length > 2_000_000:
            self._send(200, _response(None, "failed", "请求与协议不一致", "INVALID_REQUEST"))
            return
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(200, _response(None, "failed", "请求与协议不一致", "INVALID_REQUEST"))
            return
        status, body = handle(payload)
        self._send(status, body)

    def _send(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    if not api_key():
        print(f"缺少环境变量 {AUTH_ENV}", file=sys.stderr)
    server = ThreadingHTTPServer((BIND_HOST, BIND_PORT), InvokeHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
