"""Store the public 1350 pages that the evaluation cases come from, and the original question and answer of each case.

Usage:
    uv run python -X utf8 scripts/dump_1350.py [DIR] [--offline]

DIR defaults to docs/evaluation/1350. The script reads the URLs of cases.jsonl, fetches each page once,
and stores its response bytes as pages/<page id> <YYYYMMDDTHHMM>.html, listed in pages/index.jsonl with its SHA-256.
A page whose bytes match its latest stored copy is not stored again. --offline skips fetching.
It then writes originals.jsonl with the original question and answers of every case in cases.jsonl, matched by
URL, 신청일 and 답변일, from the latest copy of each page.
"""

import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
BLOCK = re.compile(r'<dl>\s*<dt[^>]*><img[^>]*alt="(질의|답변)"[^>]*/?></dt>\s*<dd class="body03_g">(.*?)</dd>\s*<dd>(.*?)</dd>\s*</dl>', re.DOTALL)
STAMP = re.compile(r"(신청일|답변일) : (\d{4})\.(\d\d)\.(\d\d) (\d\d:\d\d)")


def text(fragment):
    fragment = re.sub(r'<div class="pic_right">.*?</div>', "", fragment, flags=re.DOTALL)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    fragment = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    lines = [line.rstrip() for line in fragment.replace("\r", "").split("\n")]
    return "\n".join(lines).strip()


def threads(page):
    """Each question with the answers that follow it, in page order."""
    found = []
    for kind, body, meta in BLOCK.findall(page):
        stamp = STAMP.search(re.sub(r"<!--.*?-->", "", meta, flags=re.DOTALL))
        when = f"{stamp[2]}-{stamp[3]}-{stamp[4]} {stamp[5]}" if stamp else None
        if kind == "질의":
            found.append({"posted": when, "question": text(body), "answers": []})
        elif found:
            found[-1]["answers"].append({"answered": when, "answer": text(body)})
    return found


def page_id(url):
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["id"][0]


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(folder, offline=False):
    cases = rows(folder / "cases.jsonl")
    pages = folder / "pages"
    pages.mkdir(exist_ok=True)
    index_path = pages / "index.jsonl"
    index = rows(index_path) if index_path.exists() else []
    latest = {}
    for entry in index:
        latest[entry["id"]] = entry
    urls = sorted({c["url"] for c in cases}, key=page_id)
    for number, url in enumerate([] if offline else urls):
        ident = page_id(url)
        body = fetch(url)
        digest = hashlib.sha256(body).hexdigest()
        if latest.get(ident, {}).get("sha256") != digest:
            retrieved = datetime.now(KST).strftime("%Y%m%dT%H%M")
            name = f"{ident} {retrieved}.html"
            (pages / name).write_bytes(body)
            latest[ident] = {"id": ident, "url": url, "file": name, "retrieved": retrieved, "sha256": digest}
            index.append(latest[ident])
        if number + 1 < len(urls):
            time.sleep(1)
    index_path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in index), encoding="utf-8", newline="\n")

    found = {}
    for ident, entry in latest.items():
        page = (pages / entry["file"]).read_bytes().decode("cp949", errors="replace")
        for thread in threads(page):
            for answer in thread["answers"] or [{"answered": None, "answer": None}]:
                found.setdefault((entry["url"], thread["posted"], answer["answered"]), []).append(
                    {"question": thread["question"], "answers": thread["answers"], "page": entry["file"]})
    out, missing = [], []
    for case in cases:
        hit = found.get((case["url"], case["posted"], case["answered"]))
        if not hit:
            missing.append(case["id"])
            continue
        if len({h["question"] for h in hit}) > 1:
            missing.append(case["id"] + " (ambiguous)")
            continue
        out.append({"id": case["id"], "question": hit[0]["question"], "answers": hit[0]["answers"], "page": hit[0]["page"]})
    (folder / "originals.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out),
                                            encoding="utf-8", newline="\n")
    print(f"pages {len(urls)}, cases {len(out)}/{len(cases)}")
    for ident in missing:
        print("MISSING", ident)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--offline"]
    main(Path(args[0]) if args else ROOT / "docs/evaluation/1350", offline="--offline" in sys.argv[1:])
