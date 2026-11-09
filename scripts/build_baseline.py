"""Build playback data from timestamped, visible AI 노동법 상담 responses."""

import html
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "view/data"


class ResponseHTML(HTMLParser):
    allowed = {"p", "br", "strong", "b", "em", "ul", "ol", "li", "a", "hr", "blockquote"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object"}:
            self.suppressed += 1
        if self.suppressed or tag not in self.allowed:
            return
        attributes = ""
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith("https://"):
                attributes = f' href="{html.escape(href, quote=True)}" target="_blank" rel="noopener noreferrer"'
        self.parts.append(f"<{tag}{attributes}>")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe", "object"}:
            self.suppressed = max(0, self.suppressed - 1)
            return
        if not self.suppressed and tag in self.allowed and tag not in {"br", "hr"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(html.escape(data))


def clean_html(value):
    parser = ResponseHTML()
    parser.feed(value)
    return "".join(parser.parts)


def build():
    responses = []
    for date in ("2026-09-30", "2025-12-31"):
        stem = f"moel-{date[:4]}-timed"
        capture = json.loads((ROOT / "captures" / f"{stem}.json").read_text(encoding="utf-8"))
        responses.append({
            "separationDate": date, "question": capture["question"], "answer": capture["answer"],
            "capturedAt": capture["startedAt"], "cap": 66000,
            "durationMs": capture["durationMs"], "firstTextMs": capture["firstTextMs"],
            "maxObservationGapMs": capture["maxObservationGapMs"],
            "screenshot": f"./data/captures/{stem}.png", "capture": f"./data/captures/{stem}.json",
            "frames": [{"atMs": f["atMs"], "html": clean_html(f["html"])} for f in capture["frames"]],
        })
    return {
        "service": "AI 노동법 상담", "organisation": "고용노동부 · 한국공인노무사회",
        "url": "https://ai.moel.go.kr/llc/labor-law-chat",
        "method": "One fresh conversation per date; timestamped observations of visible response HTML. Final markdown copied with the service copy button.",
        "timingDefinition": "From immediately before clicking Send to the first observation of the final visible response. Browser observation includes automation overhead; not server timing. Cache use unknown; one sample per date, not a benchmark.",
        "responses": responses,
    }


if __name__ == "__main__":
    (ROOT / "baseline-responses.json").write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
