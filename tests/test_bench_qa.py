import json
from argparse import Namespace

import pytest

import bench_qa as bench


def test_external_message_matches_both_runs_and_freeze_is_immutable(tmp_path, monkeypatch):
    path = tmp_path / "inputs.jsonl"
    row = {"id": "example", "as_of": "2025-01-03", "question": "언제 신청해요?"}
    path.write_text(json.dumps(row), encoding="utf-8")
    assert bench.inputs(path, "live")[0]["message"] == row["question"]
    config = dict(provider="test", model="fixture", thinking="", effort="", nvidiaThinking=False)
    monkeypatch.setattr(bench.llm, "configuration", lambda _: config)
    monkeypatch.setattr(bench, "product_version", lambda: "test-version")
    monkeypatch.setattr(bench.ask, "Index", lambda: None)
    seen = []

    def fake(question, day):
        seen.append(question)
        return {"question": question, "asOf": day, "versionDate": day, "status": "answered", "evidence": [],
                "output": {"answer": "시험 응답", "questions": [], "citations": []}}

    monkeypatch.setattr(bench.ask, "answer", lambda ix, q, d, provider: fake(q, d))
    monkeypatch.setattr(bench.ask, "generate", lambda payload, provider: fake(payload["question"], payload["상담 기준일"]))
    args = Namespace(inputs=path, trial=tmp_path / "trial", context="historical", provider="test", ids=["example"],
                     out=tmp_path / "fixed.json")
    bench.preview(args)
    bench.preview(args)
    expected = "상담 기준일은 2025-01-03입니다.\n언제 신청해요?"
    assert seen == [expected, expected]
    bench.freeze(args)
    saved = bench.read(args.out)["firstTurns"][0]
    assert saved["message"] == expected and saved["sha256"] == bench.digest(expected)
    replies = tmp_path / "replies.jsonl"
    reply = {"id": "example", "sent": row["question"], "first_response": "비교 응답"}
    replies.write_text(json.dumps(reply), encoding="utf-8")
    grade = Namespace(frozen=args.out, responses=replies, out=tmp_path / "grading")
    with pytest.raises(ValueError, match="실제 입력"):
        bench.blind(grade)
    reply["sent"] = expected
    replies.write_text(json.dumps(reply), encoding="utf-8")
    bench.blind(grade)
    mapping = bench.read(grade.out / "key.json")["example"]
    packet = bench.read(grade.out / "answers.json")[0]
    assert packet[next(k for k, v in mapping.items() if v == "external")] == "비교 응답"
    with pytest.raises(FileExistsError):
        bench.freeze(args)
    row["question"] += " 오늘요."
    path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="변경"):
        bench.preview(args)
    (args.trial / "example.memory.json").unlink()
    with pytest.raises(ValueError, match="실행 대기"):
        bench.freeze(args)
