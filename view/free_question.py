"""First-turn free-question service shared by the local viewer and its HTTP tests."""

import sys
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ask


@lru_cache(maxsize=1)
def index():
    return ask.Index()


def inputs(payload):
    if not isinstance(payload, dict):
        raise ValueError("질문을 입력해 주세요.")
    question = payload.get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("질문은 1~4,000자로 입력해 주세요.")
    day = payload.get("asOf", datetime.now(timezone(timedelta(hours=9))).date().isoformat())
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("상담 기준일은 YYYY-MM-DD 형식으로 입력해 주세요.") from None
    return question, day


def consult(question, day, provider):
    record = ask.answer(index(), question, day, provider=provider)
    output = record["output"]
    sources = {e["key"]: e for e in record["evidence"]}
    quotes = {key: [] for key in output["citations"]}
    if record["status"] == "answered":
        for statement in record["statements"]:
            for item in statement["support"]:
                if item["quote"] not in quotes[item["key"]]:
                    quotes[item["key"]].append(item["quote"])
    return {"question": question, "asOf": day, "status": record["status"], "model": record["model"],
            "answer": output["answer"], "questions": output["questions"],
            "sources": [{"key": key, "citation": sources[key]["citation"], "version": sources[key].get("version"),
                         "quotes": quotes[key]}
                        for key in output["citations"]]}
