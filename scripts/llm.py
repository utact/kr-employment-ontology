"""Call the language model named in .env and return its JSON answer.

LLM_PROVIDER selects nvidia, gemini or openai; the key and model come from NVIDIA_*, GEMINI_* or OPENAI_* in .env
or the environment. OPENAI_MODEL has no default, so that the model is always named.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"LLM_PROVIDER", "NVIDIA_API_KEY", "NVIDIA_MODEL", "NVIDIA_THINKING",
        "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_THINKING_LEVEL",
        "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_REASONING_EFFORT", "CLAUDE_MODEL", "CLAUDE_EFFORT"}
DEFAULTS = {"nvidia": "nvidia/nemotron-3-ultra-550b-a55b", "gemini": "gemini-3.1-pro-preview", "openai": "",
            "claude": "claude-opus-5-5", "codex": "gpt-6.2-sol"}


def configuration(provider=None):
    values = {}
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.strip() in KEYS:
                values[key.strip()] = value.strip().strip("\"'")
    values.update({k: os.environ[k] for k in KEYS if os.environ.get(k)})
    provider = (provider or values.get("LLM_PROVIDER", "nvidia")).lower()
    if provider not in DEFAULTS:
        raise ValueError("LLM_PROVIDER must be nvidia, gemini, openai, claude or codex")
    key = values.get(f"{provider.upper()}_API_KEY", "")
    # Claude runs through the signed-in Claude Code CLI, which holds its own credentials.
    if not key and provider not in ("claude", "codex"):
        raise ValueError(f"{provider.upper()}_API_KEY is not set")
    model = values.get(f"{provider.upper()}_MODEL") or DEFAULTS[provider]
    if not model:
        raise ValueError(f"{provider.upper()}_MODEL is not set")
    effort = values.get("OPENAI_REASONING_EFFORT", "")
    if provider == "claude":
        effort = values.get("CLAUDE_EFFORT", "high")
    elif provider == "codex":
        effort = "medium"
    return {"provider": provider, "model": model, "key": key,
            "nvidiaThinking": values.get("NVIDIA_THINKING", "true").lower() == "true",
            "thinking": values.get("GEMINI_THINKING_LEVEL", "high"),
            "effort": effort}


def parse_json(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("the model returned no JSON object")
    return json.loads(text[start:end + 1])


def complete(system, user, provider=None, max_tokens=16384, retries=2):
    """JSON object the model returns for a system and user message, with the model name and duration."""
    config = configuration(provider)
    if config["provider"] == "codex":
        return codex_cli(system, user, config)
    if config["provider"] == "claude":
        return claude_cli(system, user, config, retries)
    if config["provider"] == "nvidia":
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        payload = {"model": config["model"], "max_tokens": max_tokens, "temperature": 0.2,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if config["model"].startswith("nvidia/nemotron-"):
            payload["chat_template_kwargs"] = {"enable_thinking": config["nvidiaThinking"]}
        headers = {"Authorization": f"Bearer {config['key']}", "Content-Type": "application/json"}
    elif config["provider"] == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        # Reasoning models take max_completion_tokens and no temperature; json_object needs "JSON" in a message.
        payload = {"model": config["model"], "max_completion_tokens": max_tokens,
                   "response_format": {"type": "json_object"},
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if config["effort"]:
            payload["reasoning_effort"] = config["effort"]
        headers = {"Authorization": f"Bearer {config['key']}", "Content-Type": "application/json"}
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config['model']}:generateContent"
        payload = {"systemInstruction": {"parts": [{"text": system}]},
                   "contents": [{"role": "user", "parts": [{"text": user}]}],
                   "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens}}
        if config["model"].startswith("gemini-3"):
            payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": config["thinking"].upper()}
        headers = {"x-goog-api-key": config["key"], "Content-Type": "application/json"}
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    start = time.perf_counter()
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                result = json.load(response)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(10 * (attempt + 1))
                continue
            raise ValueError(f"{config['provider']} HTTP {e.code}: {e.read()[:300]!r}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(10 * (attempt + 1))
                continue
            raise ValueError(f"{config['provider']} connection failed: {e}") from None
    if config["provider"] in ("nvidia", "openai"):
        choice = result["choices"][0]
        if choice.get("finish_reason") not in (None, "stop"):
            raise ValueError(f"the model stopped early: {choice.get('finish_reason')}")
        text = choice["message"]["content"]
        usage = result.get("usage", {})
    else:
        candidate = result["candidates"][0]
        text = "".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought"))
        usage = result.get("usageMetadata", {})
    return {"json": parse_json(text), "provider": config["provider"], "model": config["model"],
            "usage": usage, "durationMs": round((time.perf_counter() - start) * 1000)}


def codex_cli(system, user, config):
    """One isolated subscription turn. Accept only a completed, tool-free conversation."""
    import shutil
    import subprocess
    import tempfile

    executable = shutil.which("codex.exe") or shutil.which("codex")
    if not executable:
        raise ValueError("Codex CLI를 찾을 수 없습니다.")
    env = {k: v for k, v in os.environ.items() if k.upper() not in {"CODEX_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL"}}
    options = dict(capture_output=True, encoding="utf-8", errors="replace", env=env,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="consult-") as folder:
        prompt = Path(folder) / "instructions.md"
        prompt.write_text(system, encoding="utf-8")
        command = [executable, "exec", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check",
                   "--sandbox", "read-only", "--json", "-m", config["model"],
                   "-c", "forced_login_method=chatgpt", "-c", "model_provider=openai",
                   "-c", "web_search=disabled", "-c", "project_doc_max_bytes=0",
                   "-c", "mcp_servers={}", "-c", "skills.include_instructions=false",
                   "-c", 'developer_instructions="Complete this single turn directly from the supplied messages '
                         'and the knowledge permitted by the task. Do not call any tool, including listing MCP '
                         'resources, reading files, searching, or asking the user through a tool. Express missing '
                         'information in the requested JSON response."',
                   "-c", "model_reasoning_effort=" + config["effort"],
                   "-c", "model_instructions_file=" + prompt.as_posix()]
        for feature in ("shell_tool", "unified_exec", "apps", "plugins", "multi_agent", "multi_agent_v2", "hooks", "memories"):
            command.extend(("--disable", feature))
        done = subprocess.run([*command, "-"], input=user, cwd=folder, timeout=300, **options)
    if done.returncode:
        # Keep prompts, credentials and diagnostic bodies out of the HTTP error.
        final_error = next((s for s in reversed(done.stderr.splitlines()) if s.lower().startswith("error:")), "")
        if "os error 5" in final_error or "access is denied" in final_error.lower():
            raise ValueError("Codex 실행 권한이 거부되었습니다.")
        raise ValueError(f"Codex 구독 호출을 완료하지 못했습니다 (종료 코드 {done.returncode}).")
    message, usage = "", None
    for line in done.stdout.splitlines():
        event = json.loads(line)
        if event["type"] in ("turn.failed", "error"):
            raise ValueError("Codex 구독 호출이 실패했습니다.")
        if event["type"].startswith("item."):
            item = event["item"]
            if item["type"] not in ("agent_message", "reasoning"):
                tool = (str(item.get("server", "")) + "/" + str(item.get("tool", ""))).strip("/")
                raise ValueError(f"외부 작업이 포함된 응답은 비교에서 제외합니다. ({tool or item['type']})")
            if event["type"] == "item.completed" and item["type"] == "agent_message":
                message = item["text"]
        if event["type"] == "turn.completed":
            usage = event.get("usage") or {}
    if usage is None or not message:
        raise ValueError("Codex 첫 응답이 완료되지 않았습니다.")
    return {"json": parse_json(message), "provider": "codex", "model": config["model"],
            "usage": {"prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0)},
            "durationMs": round((time.perf_counter() - start) * 1000)}


def claude_cli(system, user, config, retries=2):
    """One turn of the Claude Code CLI in print mode, without tools, MCP servers, settings or the project's CLAUDE.md."""
    import subprocess
    import tempfile

    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="llm-") as folder:
        prompt = Path(folder) / "system.txt"
        prompt.write_text(system + "\n\nJSON 객체 하나만 출력한다. 다른 글은 쓰지 않는다.", encoding="utf-8")
        command = ["claude", "-p", "--model", config["model"], "--effort", config["effort"],
                   "--system-prompt-file", str(prompt), "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                   "--no-session-persistence", "--output-format", "json"]
        for attempt in range(retries + 1):
            done = subprocess.run(command, input=user, capture_output=True, text=True, encoding="utf-8", cwd=folder,
                                  timeout=900)
            try:
                result = json.loads(done.stdout)
            except json.JSONDecodeError:
                result = {"is_error": True, "result": (done.stdout or done.stderr)[:300]}
            if not result.get("is_error"):
                break
            if attempt < retries:
                time.sleep(30 * (attempt + 1))
                continue
            raise ValueError(f"claude failed: {str(result.get('result'))[:300]}")
    usage = result.get("usage", {})
    usage = {"prompt_tokens": sum(usage.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
             "completion_tokens": usage.get("output_tokens", 0), "costUsd": result.get("total_cost_usd")}
    return {"json": parse_json(result["result"]), "provider": "claude", "model": config["model"],
            "usage": usage, "durationMs": round((time.perf_counter() - start) * 1000)}
