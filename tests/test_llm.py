import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import llm


@pytest.mark.parametrize("used_tool", [False, True])
def test_subscription_turn_uses_the_selected_policy_without_external_sources(monkeypatch, used_tool):
    import shutil
    import subprocess

    monkeypatch.setenv("OPENAI_API_KEY", "unused-api-key")
    monkeypatch.setattr(shutil, "which", lambda name: "codex")
    config = llm.configuration("codex")
    assert (config["model"], config["effort"]) == ("gpt-6.2-sol", "medium")

    def run(command, **kwargs):
        assert "forced_login_method=chatgpt" in command and "model_reasoning_effort=medium" in command
        assert "web_search=disabled" in command and "OPENAI_API_KEY" not in kwargs["env"]
        assert kwargs["input"] == "질문" and (Path(kwargs["cwd"]) / "instructions.md").read_text(encoding="utf8") == "지시"
        events = [{"type": "item.completed", "item": {"type": "agent_message", "text": '{"ok":true}'}},
                  {"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 3}}]
        if used_tool:
            events.insert(0, {"type": "item.started", "item": {"type": "web_search"}})
        return SimpleNamespace(returncode=0, stdout="\n".join(json.dumps(e) for e in events))

    monkeypatch.setattr(subprocess, "run", run)
    if used_tool:
        with pytest.raises(ValueError, match="외부 작업"):
            llm.complete("지시", "질문", "codex")
    else:
        result = llm.complete("지시", "질문", "codex")
        assert result["json"] == {"ok": True} and result["usage"]["prompt_tokens"] == 7
