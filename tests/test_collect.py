"""Tests for the 고용24 guide parser in scripts/collect.py, with the structure of the 실업급여(상용직) page."""

import pytest

import collect

PAGE = """<h2>실업급여(상용직)</h2>
<ul class="box_list_doc type02">
<li><a href="#CI00001700" class="active">개요</a></li>
<li><a href="#CI00001701">지원내용</a></li>
<li><a href="#CI00001905">신청절차</a></li>
</ul>
<div id="CI00001700"><div class="se-contents"><p><br></p></div></div>
<h3 id="CI00001701" class="t1_sb">지원내용</h3>
<div class="box_border_type_policy"><div class="se-contents"><p><br></p></div></div>
<h3 id="CI00001905" class="t1_sb">신청절차</h3>
<div class="box_border_type_policy"><p>서류 제출 요청&nbsp;→ 사전 확인</p></div>
<h3 class="t1_sb">유사 제도</h3>
<ul><li><a href="#none">실업급여(일용직)</a></li></ul>
<p class="b1_r mt40">최종 수정일: 2026-08-25</p>"""


def test_sections_follow_the_table_of_contents():
    sections, modified = collect.page_sections(PAGE, "실업급여(상용직)")
    assert sections == {"개요": "", "지원내용": "", "신청절차": "서류 제출 요청 → 사전 확인"}
    assert modified == "2026-08-25"


NOTE = """---
identifier: raw-work24-si00000411-20261015t1337
title: 실업급여(상용직)
license: 공공누리 표시 없음
---

고용24 실업급여(상용직) 안내의 원문 노트다.
"""


def guide(tmp_path):
    folder = tmp_path / "raw" / "work24" / "실업급여(상용직)"
    folder.mkdir(parents=True)
    (folder / "실업급여(상용직) 20261015T1337.md").write_text(NOTE, encoding="utf-8", newline="\n")
    (folder / "실업급여(상용직) 20261015T1337.html").write_text(PAGE, encoding="utf-8", newline="\n")
    return folder / "실업급여(상용직) 20261015T1337.md"


def test_quote_appends_a_checked_quotation(tmp_path):
    note = guide(tmp_path)
    assert collect.quote("실업급여(상용직)", "신청절차", "서류 제출 요청 → 사전 확인", raw=tmp_path / "raw") == 1
    meta = collect.L.frontmatter(note)
    assert meta["hasPart"] == [{"identifier": "raw-work24-si00000411-20261015t1337-q1", "text": "서류 제출 요청 → 사전 확인",
                                "sha256": collect.L.body_hash("서류 제출 요청 → 사전 확인")}]
    assert collect.quotations(note) == {"q1": "서류 제출 요청 → 사전 확인"}
    assert collect.quote("실업급여(상용직)", "신청절차", "서류 제출 요청 → 사전 확인", raw=tmp_path / "raw") == 1


def test_quote_refuses_text_outside_the_section(tmp_path):
    guide(tmp_path)
    with pytest.raises(SystemExit):
        collect.quote("실업급여(상용직)", "지원내용", "서류 제출 요청", raw=tmp_path / "raw")


def test_check_raw_finds_a_changed_quotation(tmp_path, monkeypatch):
    import check_raw
    note = guide(tmp_path)
    collect.quote("실업급여(상용직)", "신청절차", "서류 제출 요청 → 사전 확인", raw=tmp_path / "raw")
    monkeypatch.setattr(collect.L, "RAW", tmp_path / "raw")
    monkeypatch.setattr(collect.L, "VAULT", tmp_path)
    problems = []
    check_raw.check_quotations(problems)
    assert problems == []
    note.write_text(note.read_text(encoding="utf-8").replace("사전 확인 ^q1", "사전 교육 ^q1"), encoding="utf-8", newline="\n")
    check_raw.check_quotations(problems)
    assert any("^q1 differs" in p for p in problems)


INTERPRETATION = {"ExpcService": {"법령해석례일련번호": "343439", "안건번호": "26-0321", "해석일자": "20260708", "해석기관명": "법제처",
                                  "안건명": "민원인 - 10일을 산정할 때 토요일 및 공휴일을 포함하여야 하는지?",
                                  "질의요지": "10일의 입력기간을 산정할 때 토요일 및 공휴일을 포함하여야 하는지",
                                  "회답": "10일의 입력기간을 산정할 때 토요일 및 공휴일을 포함하여야 합니다.", "이유": "민법을 준용합니다."}}


def interpretation(tmp_path, response=INTERPRETATION):
    import json
    folder = tmp_path / "raw" / "law" / "법령해석례"
    folder.mkdir(parents=True)
    stem = "법령해석례 26-0321 20261019T2100"
    (folder / f"{stem}.json").write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    (folder / f"{stem}.md").write_text("---\nidentifier: raw-expc-343439-20261019t2100\ntitle: 해석례\n---\n\n시험용 원문 노트다.\n",
                                       encoding="utf-8", newline="\n")
    return folder / f"{stem}.md"


def test_quote_takes_an_interpretation_from_its_response(tmp_path):
    note = interpretation(tmp_path)
    assert collect.quote("법령해석례 26-0321", "회답", "토요일 및 공휴일을 포함하여야 합니다.", raw=tmp_path / "raw") == 1
    assert collect.quotations(note) == {"q1": "토요일 및 공휴일을 포함하여야 합니다."}
    with pytest.raises(SystemExit):
        collect.quote("법령해석례 26-0321", "질의요지", "민법을 준용합니다.", raw=tmp_path / "raw")


def test_check_raw_finds_an_interpretation_of_another_case(tmp_path, monkeypatch):
    import check_raw
    other = {"ExpcService": dict(INTERPRETATION["ExpcService"], 법령해석례일련번호="339523")}
    interpretation(tmp_path, other)
    monkeypatch.setattr(collect.L, "RAW", tmp_path / "raw")
    problems = []
    check_raw.check_interpretations({"interpretations": [{"id": "343439"}]}, problems)
    assert any("response is of 법령해석례 339523" in p for p in problems)
    assert any("343439 not collected" in p for p in problems)


PRECEDENT = {"PrecService": {"판례정보일련번호": "195380", "사건번호": "2015두44165", "선고일자": "20180424", "법원명": "대법원",
                             "사건명": "조기재취업수당부지급처분취소", "판결유형": "판결",
                             "판시사항": "<br/>  ‘고용된 경우’의 해석",
                             "판결요지": "<br/>  일시 중단된 기간도 &quot;계속 고용된 기간&quot;에<br/>포함된다고 보아야 한다.", "판례내용": "【주    문】<br/>  원심판결을 파기한다."}}


def precedent(tmp_path, response=PRECEDENT):
    import json
    folder = tmp_path / "raw" / "law" / "판례"
    folder.mkdir(parents=True)
    stem = "판례 2015두44165 20261108T0200"
    (folder / f"{stem}.json").write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    (folder / f"{stem}.md").write_text("---\nidentifier: raw-prec-195380-20261108t0200\ntitle: 판례\n---\n\n시험용 원문 노트다.\n",
                                       encoding="utf-8", newline="\n")
    return folder / f"{stem}.md"


def test_quote_takes_a_precedent_across_its_line_breaks(tmp_path):
    note = precedent(tmp_path)
    text = "일시 중단된 기간도 \"계속 고용된 기간\"에 포함된다고 보아야 한다."
    assert collect.quote("판례 2015두44165", "판결요지", text, raw=tmp_path / "raw") == 1
    assert collect.quotations(note) == {"q1": text}
    with pytest.raises(SystemExit):
        collect.quote("판례 2015두44165", "판시사항", "원심판결을 파기한다.", raw=tmp_path / "raw")


def test_check_raw_finds_a_precedent_of_another_case(tmp_path, monkeypatch):
    import check_raw
    precedent(tmp_path, {"PrecService": dict(PRECEDENT["PrecService"], 판례정보일련번호="159916")})
    monkeypatch.setattr(collect.L, "RAW", tmp_path / "raw")
    problems = []
    check_raw.check_precedents({"precedents": [{"id": "195380"}]}, problems)
    assert any("response is of 판례 159916" in p for p in problems)
    assert any("195380 not collected" in p for p in problems)
