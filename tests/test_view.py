"""Source integrity and model-boundary checks for the isolated viewer."""

import hashlib
import importlib.util
import json
import io
from pathlib import Path

import pytest

import export_view as E
import build_baseline as B

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("viewer_model", ROOT / "view/model.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
DATA = json.loads((ROOT / "view/data/vault.json").read_text(encoding="utf-8"))


def test_graph_has_only_real_notes_and_declared_relations():
    nodes = {node["id"]: node for node in DATA["nodes"]}
    assert len(nodes) == DATA["meta"]["nodeCount"]
    assert len(DATA["edges"]) == DATA["meta"]["relationCount"]
    for node in nodes.values():
        assert (ROOT / node["path"]).is_file()
        assert node["path"].startswith("wiki/")
    for edge in DATA["edges"]:
        assert edge["source"] in nodes and edge["target"] in nodes
        assert edge["relation"]


def test_scenario_sources_match_exact_vault_blocks():
    for key, evidence in DATA["evidence"].items():
        if key == "previous":
            continue
        _, body = E.read_note(ROOT / evidence["path"])
        assert E.block(body, evidence["anchor"]) == evidence["text"]
    _, body = E.read_note(ROOT / DATA["baseline"]["path"])
    assert E.block(body, "q1") == DATA["baseline"]["quote"]


def test_historical_excerpt_matches_saved_response_when_available():
    evidence = DATA["evidence"]["previous"]
    path = ROOT / evidence["path"]
    if not path.exists():
        pytest.skip("Local historical response cache is optional; committed excerpt remains available")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == evidence["sha256"]
    law = json.loads(raw)["법령"]
    unit = next(u for u in law["조문"]["조문단위"] if u.get("조문번호") == "68" and u.get("조문여부") == "조문")
    assert unit["항"][0]["항내용"] == evidence["text"]
    assert law["기본정보"]["시행일자"] == evidence["sourceVersion"]


def test_block_lookup_does_not_confuse_parent_and_child():
    body = "parent ^v20260101-p1\n\nchild ^v20260101-p1-i1\n"
    assert E.block(body, "v20260101-p1") == "parent"
    with pytest.raises(ValueError):
        E.block(body, "v20250101-p1")


@pytest.mark.parametrize("date,cap", [("2025-12-31", 66000), ("2026-01-01", 68100), ("2026-09-30", 68100)])
def test_server_recomputes_amount_without_trusting_client(date, cap):
    assert M.resolve(DATA, date)["cap"] == cap


@pytest.mark.parametrize("date", ["2025-02-29", "2026-10-15", "2024-01-01", "20260101", None])
def test_server_rejects_invalid_or_unsupported_dates(date):
    with pytest.raises(ValueError):
        M.resolve(DATA, date)


def test_model_cannot_replace_rule_amount_or_invent_citations():
    facts = M.resolve(DATA, "2026-09-30")
    with pytest.raises(ValueError, match="금액"):
        M.validate_explanation(json.dumps({"cap": 66000, "explanation": "Wrong", "evidenceIds": ["current"]}), facts)
    with pytest.raises(ValueError, match="근거"):
        M.validate_explanation(json.dumps({"cap": 68100, "explanation": "Wrong", "evidenceIds": ["invented"]}), facts)
    assert M.validate_explanation(json.dumps({"cap": 68100, "explanation": "근거 설명", "evidenceIds": ["current", "rate"]}), facts)["explanation"] == "근거 설명"


def test_status_does_not_expose_key(monkeypatch):
    monkeypatch.setattr(M, "configuration", lambda: {"provider": "nvidia", "model": "test", "key": "test-secret"})
    assert M.status() == {"provider": "nvidia", "model": "test", "configured": True}


def test_model_receives_the_same_question_as_the_captured_service(monkeypatch):
    baseline = json.loads((ROOT / "view/data/baseline-responses.json").read_text(encoding="utf-8"))["responses"][0]
    monkeypatch.setattr(M, "configuration", lambda: {"provider": "nvidia", "model": "nvidia/nemotron-3-ultra-550b-a55b", "key": "test-secret", "nvidiaThinking": True})
    def opener(request, timeout):
        payload = json.loads(request.data)
        content = json.loads(payload["messages"][1]["content"])
        assert content["question"] == baseline["question"]
        assert set(content["evidence"]) == {"current", "rate", "transition", "effective"}
        assert payload["chat_template_kwargs"] == {"enable_thinking": True}
        assert "test-secret" not in request.data.decode()
        reply = {"cap": 68100, "evidenceIds": ["current", "rate"], "explanation": "하루 상한액은 68,100원입니다."}
        response = io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(reply)}}]}).encode())
        response.status = 200
        return response
    assert M.explain(baseline["separationDate"], opener)["cap"] == 68100


def test_captured_answers_have_provenance_and_screenshots():
    baseline = json.loads((ROOT / "view/data/baseline-responses.json").read_text(encoding="utf-8"))
    assert baseline["url"] == "https://ai.moel.go.kr/llc/labor-law-chat"
    assert len(baseline["responses"]) == 2
    for response in baseline["responses"]:
        capture = json.loads((ROOT / "view" / response["capture"]).read_text(encoding="utf-8"))
        assert response["answer"] == capture["answer"]
        assert response["question"] == capture["question"]
        assert 0 < response["firstTextMs"] < response["durationMs"]
        assert capture["observedThroughMs"] > response["durationMs"] + 5000
        assert response["durationMs"] == capture["durationMs"] == response["frames"][-1]["atMs"]
        assert response["firstTextMs"] == response["frames"][0]["atMs"]
        assert [f["atMs"] for f in response["frames"]] == [f["atMs"] for f in capture["frames"]]
        assert response["capturedAt"].startswith("2026-11-09")
        assert response["separationDate"].replace("-", ".") in response["question"]
        assert "66,000원" in response["answer"]
        assert (ROOT / "view" / response["screenshot"]).is_file()


def test_captured_playback_is_reproducible_and_removes_active_html():
    assert B.build() == json.loads((ROOT / "view/data/baseline-responses.json").read_text(encoding="utf-8"))
    unsafe = '<div onclick="bad()"><p>Hello <strong>world</strong></p><img src="bad" onerror="bad()"><script>bad()</script><a href="javascript:bad()">bad link</a><a href="https://example.com/">source</a></div>'
    result = B.clean_html(unsafe)
    assert "onclick" not in result and "onerror" not in result and "javascript:" not in result
    assert "bad()" not in result and "<img" not in result
    assert '<p>Hello <strong>world</strong></p>' in result
    assert 'href="https://example.com/"' in result


def test_streaming_progress_discards_reasoning_and_keeps_validation(monkeypatch):
    monkeypatch.setattr(M, "configuration", lambda: {"provider": "nvidia", "model": "nvidia/nemotron-3-ultra-550b-a55b", "key": "test-secret", "nvidiaThinking": True})
    reply = json.dumps({"cap": 68100, "evidenceIds": ["current"], "explanation": "하루 상한액은 68,100원입니다."})
    def opener(request, timeout):
        assert json.loads(request.data)["stream"] is True
        prompt = json.loads(json.loads(request.data)["messages"][1]["content"])
        assert states[0]["evidenceIds"] == list(prompt["evidence"])
        chunks = [{"delta": {"reasoning_content": "private-reasoning"}},
                  {"delta": {"reasoning_content": "more-private-reasoning"}},
                  {"delta": {"content": reply[:20]}}, {"delta": {"content": reply[20:]}},
                  {"delta": {}, "finish_reason": "stop"}]
        response = io.BytesIO(("".join("data: " + json.dumps({"choices": [chunk]}) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode())
        response.status = 200
        return response
    states = []
    result = M.explain("2026-09-30", opener, on_progress=states.append)
    assert [s["phase"] for s in states] == ["requesting", "reasoning", "writing", "validating"]
    assert states[0]["evidenceIds"] == ["current", "rate", "transition", "effective"]
    assert "private-reasoning" not in json.dumps([states, result])
    assert result["cap"] == 68100


@pytest.mark.parametrize("finish", [None, "length"])
def test_incomplete_nvidia_stream_is_rejected(finish):
    chunk = {"choices": [{"delta": {"content": "{}"}, "finish_reason": finish}]}
    response = io.BytesIO(("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n").encode())
    with pytest.raises(ValueError, match="종료|완료"):
        M.read_nvidia_stream(response, lambda phase: None)
