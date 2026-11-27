import json

import pytest

import ask
import lawlib
import llm


SOURCE = {"key": "E1", "citation": "시험 규정", "text": "지정한 날에 신청한다."}


def test_cited_raw_quote_reaches_answer_but_is_not_a_search_seed(tmp_path):
    wiki, raw = tmp_path / "wiki", tmp_path / "raw"
    wiki.mkdir()
    raw.mkdir()
    text = SOURCE["text"]
    (wiki / "신청.md").write_text("---\ntype: Rule\nstatus: reviewed\nsource: ['[[안내#^q1]]']\n---\n신청", encoding="utf8")
    (raw / "안내.md").write_text(
        f"---\nidentifier: raw-work24-guide\nurl: https://example.org\ngeneratedAtTime: '2025-01-03'\n"
        f"hasPart:\n- identifier: raw-work24-guide-q1\n  text: {text}\n  sha256: {lawlib.body_hash(text)}\n---\n{text} ^q1\n",
        encoding="utf8")
    index = ask.Index(tmp_path)
    assert set(index.docs) == {"신청"}
    retrieval = index.retrieve("신청", "2025-01-03")
    evidence = ask.context(index, retrieval, consultation_day="2025-01-03")["evidence"]
    assert evidence[0]["text"] == text and evidence[0]["link"] == "안내#^q1"
    assert ask.render(statement(), evidence)["citations"] == ["E1"]
    earlier = ask.context(index, retrieval, consultation_day="2025-01-02")["evidence"]
    with pytest.raises(ValueError, match="시행본"):
        ask.render(statement(), earlier)


def statement(quote="지정한 날에"):
    return {"action": "answer", "statements": [
        {"text": "지정한 날에 신청하세요.", "support": [{"key": "E1", "quote": quote}]}
    ], "questions": []}


def test_relation_ablation_keeps_seeds_linked_notes_and_budget(tmp_path):
    folder = tmp_path / "wiki"
    folder.mkdir()
    for name, relation in [("신청 기준", "requires: '[[예외]]'"), ("예외", ""), ("신청 방법", "")]:
        (folder / f"{name}.md").write_text(f"---\ntype: Rule\nstatus: verified\n{relation}\n---\n{name}", encoding="utf8")
    index = ask.Index(tmp_path)
    settings = dict(linked=["신청 기준"], seeds=1, top=2, as_of="2026-10-14")
    graph = index.retrieve("신청 기준", **settings)
    flat = index.retrieve("신청 기준", **settings, use_relations=False)
    assert graph["seeds"] == flat["seeds"]
    assert [n["note"] for n in graph["notes"]] == ["신청 기준", "예외"]
    assert [n["note"] for n in flat["notes"]] == ["신청 기준", "신청 방법"]
    index.spread = lambda seeds: {"신청 기준": 1, "예외": 0.8}
    mixed = index.retrieve("신청 기준", **{**settings, "top": 3})
    assert [n["note"] for n in mixed["notes"]] == ["신청 기준", "예외", "신청 방법"]


def test_review_sees_omitted_evidence_and_rejects_a_fabricated_quote(monkeypatch):
    evidence = [SOURCE, {"key": "E2", "citation": "예외", "text": "다음 날 신청할 수 있다."}]
    payload = ask.response_input("언제 신청해요?", "2026-10-01", "2026-10-01", [], evidence, "vault")
    calls = []

    def complete(system, user, provider=None):
        calls.append(json.loads(user))
        candidate = statement() if len(calls) == 1 else statement("언제든지")
        return {"json": candidate, "model": "test", "usage": {}, "durationMs": 1}

    monkeypatch.setattr(llm, "complete", complete)
    result = ask.generate(payload)
    assert calls[1]["evidence"] == evidence and result["evidence"] == evidence
    assert result["status"] == "unverified" and "언제든지" not in ask.customer_text(result)
    assert result["draft"]["citations"] == ["E1"]


def test_quotes_do_not_allow_unresolved_versions_or_wrong_units():
    with pytest.raises(ValueError, match="시행본"):
        ask.render(statement(), [{**SOURCE, "versionNote": "시행 전"}])
    bundle = {"question": "", "evidence": [{**SOURCE, "text": "10일"}, {"key": "E2", "text": "10원"}]}
    assert ask.check_answer({"action": "answer", "answer": "10원[E1]", "citations": ["E1"]}, bundle)


def test_relevant_blocks_keeps_exception_beyond_original_budget():
    class SourceNote:
        meta = {}
        sources = [("법", f"p{i}") for i in range(6)]
    index = object.__new__(ask.Index)
    index.notes = {"노트": SourceNote(), "법": "법"}
    index.idf = {"해외": 4}
    index.block = lambda note, anchor, day, cited_by: {
        "block": anchor, "text": "해외 신고" if anchor == "p5" else "일반 원칙"}
    blocks = index.relevant_blocks(["노트"], "해외", [], "2026-06-01", 2)
    assert [b["block"] for b in blocks] == ["p0", "p5"]


def test_form_and_its_cited_conditions_enter_the_same_evidence_budget(tmp_path):
    folder = tmp_path / "wiki"
    folder.mkdir()
    def note(name, meta, body=""):
        (folder / f"{name}.md").write_text(f"---\nstatus: verified\n{meta}\n---\n{body}", encoding="utf8")

    note("서비스", "type: PublicService\nhasInputType: '[[신청서]]'")
    note("신청서", "type: EvidenceType\nisDefinedBy: '[[서식]]'")
    note("서식", "type: LegalResourceSubdivision\ntypeSubdivision: form\n"
         "isRealizedBy: [{firstDateEntryInForce: '2025-07-01'}]\ncites: ['[[절차#^v20250701-p2]]']",
         "신청서 ^v20250701-t")
    note("절차", "type: LegalResourceSubdivision\nisRealizedBy: [{firstDateEntryInForce: '2025-07-01'}]",
         "출국일 전일까지 ^v20250701-p2")
    idx = ask.Index(tmp_path)
    current = idx.relevant_blocks(["서비스"], "서비스 출국", [], "2025-07-01", 2)
    assert [(b["note"], b["citedBy"]) for b in current] == [("서식", "신청서"), ("절차", "서식")]
    assert not idx.relevant_blocks(["서비스"], "다른 문의", [], "2025-07-01", 2)
    old = idx.relevant_blocks(["서비스"], "서비스 출국", [], "2025-06-30", 2)
    assert len(old) == 1 and old[0]["versionNote"]


def test_new_amount_must_follow_from_cited_operands_and_user_hours():
    source = {**SOURCE, "text": "시간급 10,320원, 적용률 80%"}
    result = statement(source["text"])
    line = result["statements"][0]
    line.update(text="계산하면 61,920원입니다.", formulas=["10320 * 7.5 * 0.8"])
    assert "61,920원" in ask.render(result, [source], question="하루 7시간 반")["answer"]
    for formula in ("10320 * 8 * 0.75", "61920", "10320 ** 2"):
        line["formulas"] = [formula]
        with pytest.raises(ValueError):
            ask.render(result, [source], question="하루 7시간 반")


def test_monthly_wage_can_be_annualized_without_allowing_twelve_for_other_amounts():
    source = {**SOURCE, "text": "월 5,740,000원"}
    result = statement(source["text"])
    line = result["statements"][0]
    line.update(text="연간 68,880,000원입니다.", formulas=["5740000 * 12"])
    assert "68,880,000원" in ask.render(result, [source])["answer"]
    line["text"] = "하루 68,880,000원입니다."
    with pytest.raises(ValueError, match="산식"):
        ask.render(result, [source])


def test_statute_table_citation_preserves_values_and_cell_boundaries():
    table = "│A│120일│150일│\n├─┼────┼────┤\n│B│120일│180일│"
    source = {**SOURCE, "text": table}
    quote = table.replace("├─┼", "├──┼")
    assert ask.render(statement(quote), [source])["citations"] == ["E1"]
    for changed in [quote.replace("150일", "180일"), quote.replace("┼────┼", "────")]:
        with pytest.raises(ValueError, match="인용 불일치"):
            ask.render(statement(changed), [source])


def test_future_guidance_is_absent_from_both_evidence_and_note_prose(tmp_path):
    from types import SimpleNamespace

    path = tmp_path / "노트.md"
    path.write_text("---\ntype: Concept\n---\n기존 안내\n후속 해석[^1]\n\n[^1]: [[자료#^q1|지침]]\n",
                    encoding="utf-8")
    quote = {"note": "자료", "block": "q1", "quotation": "지침", "text": "지침 원문", "sourceUrl": "url",
             "availableFrom": "2022-06-15"}
    index = SimpleNamespace(notes={"노트": ask.Note(path)}, quotations={("자료", "q1"): quote})
    retrieval = {"asOf": "2022-06-14", "notes": [{"note": "노트"}], "blocks": [quote]}
    before = ask.context(index, retrieval, consultation_day="2022-06-14")
    assert before["notes"][0]["body"] == "기존 안내" and before["evidence"] == []
    after = ask.context(index, retrieval, consultation_day="2022-06-15")
    assert "후속 해석" in after["notes"][0]["body"] and after["evidence"][0]["text"] == "지침 원문"


def test_total_can_reuse_a_verified_daily_amount_shown_to_the_user():
    source = {**SOURCE, "text": "시간급 10,000원"}
    result = statement(source["text"])
    line = result["statements"][0]
    line.update(text="하루 80,000원이고 총 240,000원입니다.", formulas=["10000 * 8", "80000 * 3"])
    question = "하루 8시간씩 3일입니다."
    assert "240,000원" in ask.render(result, [source], question=question)["answer"]
    line["formulas"] = ["80000 * 3"]
    with pytest.raises(ValueError, match="산식"):
        ask.render(result, [source], question=question)


def test_unstated_workday_withholds_estimate_but_retains_eligibility_and_clarification():
    source = {"key": "E2", "text": "시간급 10,000원에 1일 소정근로시간을 곱한다."}
    result = statement()
    result["statements"].append({"text": "8시간이면 80,000원입니다.", "formulas": ["10000 * 8"],
                                 "support": [{"key": "E2", "quote": source["text"]}]})
    errors = []
    out = ask.render(result, [SOURCE, source], question="근속 8년입니다.", amount_errors=errors)
    assert errors and out["action"] == "clarify" and out["citations"] == ["E1"]
    assert "지정한 날" in out["answer"] and "80,000원" not in out["answer"]
    assert len(out["questions"]) == 1 and "소정근로시간" in out["questions"][0]
    assert "80,000원" in ask.render(result, [SOURCE, source], question="하루 8시간입니다.")["answer"]
    result["statements"][1]["text"] = "하루 80,000원입니다."
    with pytest.raises(ValueError, match="소정근로시간"):
        ask.render(result, [SOURCE, source], question="근속 8년입니다.")
    result["statements"][0]["support"][0]["quote"] = "없는 내용"
    with pytest.raises(ValueError, match="인용 불일치"):
        ask.render(result, [SOURCE, source], amount_errors=[])


@pytest.mark.parametrize("hours", ["7시간 반", "7시간 30분", "7.5시간"])
def test_calculation_cannot_drop_part_of_the_users_workday(hours):
    source = {**SOURCE, "text": "시간급 10,000원"}
    result = statement(source["text"])
    line = result["statements"][0]
    line.update(text="75,000원입니다.", formulas=["10000 * 7.5"])
    assert ask.render(result, [source], question=hours)["citations"] == ["E1"]
    line.update(text="70,000원입니다.", formulas=["10000 * 7"])
    with pytest.raises(ValueError, match="산식"):
        ask.render(result, [source], question=hours)


@pytest.mark.parametrize("reason", ["out_of_scope", "insufficient_evidence"])
def test_refusal_does_not_allow_uncited_advice_and_clarification_can_give_partial_help(reason):
    request = {"action": "decline", "reason": reason, "questions": [], "statements": []}
    refusal = ask.render(request, [])
    assert refusal["reason"] == reason and not refusal["citations"]
    assert not ask.check_answer(refusal, {"evidence": []})
    with pytest.raises(ValueError):
        ask.render({**request, "statements": statement()["statements"]}, [])
    partial = ask.render({**statement(), "action": "clarify", "questions": ["언제 신청하셨나요?"]}, [SOURCE])
    assert partial["answer"] and partial["citations"] and partial["questions"]


def test_case_date_needs_a_real_date_from_the_question():
    facts = {"이직일": "2026-01-01", "이직일 원문": "2026년 1월 1일에 퇴사"}
    assert ask.version_day("2026년 1월 1일에 퇴사했어요.", facts, "2026-02-10") == "2026-01-01"
    assert ask.version_day("언제 신청해요?", facts, "2026-02-10") == "2026-02-10"
    assert ask.version_day("2026년 1월 1일에 신청", {**facts, "이직일 원문": "2026년 1월 1일에 신청"},
                           "2026-02-10") == "2026-02-10"


def test_future_effective_date_can_only_use_rules_already_announced():
    evidence = {**SOURCE, "version": "2027-01-01"}
    ask.mark_publication(evidence, "20261101", "2026-10-30")
    with pytest.raises(ValueError, match="시행본"):
        ask.render(statement(), [evidence])
    announced = {**SOURCE, "version": "2027-01-01"}
    ask.mark_publication(announced, "20261001", "2026-10-30")
    assert ask.render(statement(), [announced])["citations"] == ["E1"]


def test_show_reference_date_for_later_consultations():
    record = {"output": {"answer": "답변", "questions": [], "citations": []}, "evidence": [],
              "vaultAsOf": "2026-10-14", "asOf": "2026-10-14"}
    assert ask.customer_text(record) == "답변"
    assert "2026-10-14" in ask.customer_text({**record, "asOf": "2026-11-23"})


def test_missing_historical_statute_never_substitutes_a_future_or_stale_version(monkeypatch):
    rows = [{"시행일자": d} for d in ("20250101", "20260101")]
    monkeypatch.setattr(lawlib, "stored_versions", lambda law: ({"20250101": {}}, rows, {}, {}))
    for day in ("2024-01-01", "2026-02-01"):
        assert ask.statute_on("법", "art-1", day, {}) is None


def test_historical_rule_uses_the_listed_edition(tmp_path, monkeypatch):
    folder = tmp_path / "admrul" / "23"
    folder.mkdir(parents=True)
    monkeypatch.setattr(lawlib, "CACHE", tmp_path)
    (folder / "versions.json").write_text(json.dumps({"20240201": {"행정규칙일련번호": "10"}}))
    (folder / "10-20240201.json").write_text(json.dumps({"AdmRulService": {"조문내용": ["제10조(대상) 당시 원문"]}}))
    assert ask.rule_on("23", "규정", "art-10", "2026-02-12", {}) == ("2024-02-01", "제10조(대상) 당시 원문")
    assert ask.rule_on("23", "규정", "art-10", "2023-12-31", {}) is None


def test_old_form_and_notice_are_citable_only_from_their_published_editions(tmp_path, monkeypatch):
    from types import SimpleNamespace

    day = "2025-03-04"
    form = SimpleNamespace(name="고용보험법 시행규칙 별지 제97호서식",
                           meta={"number": "별지 제97호서식", "identifier": "law-006288-form-97"})
    law = {"기본정보": {"공포일자": "20250201"}, "별표": {"별표단위": {
        "별표구분": "서식", "별표번호": "000097", "별표내용": ["당시 서식"]}}}
    monkeypatch.setattr(lawlib, "stored_versions", lambda name: ({"20250223": law}, [{"시행일자": "20250223"}], {}, {}))
    assert ask.historical_unit(form, day, {}) == ("2025-02-23", "당시 서식", "20250201")
    folder = tmp_path / "admrul" / "87610"
    folder.mkdir(parents=True)
    monkeypatch.setattr(lawlib, "CACHE", tmp_path)
    (folder / "versions.json").write_text(json.dumps({"20240101": {"행정규칙일련번호": "10"}}))
    service = {"행정규칙기본정보": {"행정규칙명": "고시", "발령일자": "20240101"}, "조문내용": "당시 고시"}
    (folder / "10-20240101.json").write_text(json.dumps({"AdmRulService": service}))
    notice = SimpleNamespace(name="고시", meta={"identifier": "admrul-87610"})
    assert ask.historical_unit(notice, "2024-10-02", {}) == ("2024-01-01", "당시 고시", "20240101")
    assert ask.historical_unit(notice, "2023-12-31", {}) is None
