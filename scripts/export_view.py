"""Export a read-only, credential-free snapshot for the /view demonstration.

Run: uv run python -X utf8 scripts/export_view.py [--check]
Only wiki frontmatter links become graph edges. The presentation never opens
the vault filesystem or runs an LLM. Source excerpts are copied verbatim.
"""

import argparse
import hashlib
import json
import math
import random
import re
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[\[([^\]|#]+)(?:#\^([^\]|]+))?(?:\|[^\]]*)?\]\]")
SCENE = {
    "worker": "일용근로자", "date": "이직일",
    "condition": "2026-01-01 이후 이직",
    "transition": "고용보험법 시행령 부칙 제35934호",
    "cap": "고용보험법 시행령 제68조", "rate": "고용보험법 제46조",
    "rule": "구직급여일액 산정", "result": "구직급여일액",
    "workerRule": "일용근로자의 기초일액 산정",
}


def read_note(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Missing frontmatter: {path}")
    _, header, body = text.split("---\n", 2)
    return yaml.safe_load(header), body


def links(value):
    if isinstance(value, str):
        yield from ((m[1], m[2] or "") for m in LINK.finditer(value))
    elif isinstance(value, list):
        for item in value:
            yield from links(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from links(item)


def block(body, identifier):
    for paragraph in body.split("\n\n"):
        if re.search(r"\^" + re.escape(identifier) + r"\s*$", paragraph):
            return re.sub(r"\s*\^" + re.escape(identifier) + r"\s*$", "", paragraph).strip()
    raise ValueError(f"Missing source block: {identifier}")


def money(text):
    match = re.search(r"(\d+)만(?:(\d+))?원", text)
    if not match:
        raise ValueError("Source no longer contains the expected Korean amount")
    return int(match[1]) * 10000 + int(match[2] or 0)


def positions(nodes, edges, scene):
    """Deterministic sampled spring layout; pin scenario nodes for readable zooms."""
    rng = random.Random(42)
    count = len(nodes)
    xy = [[math.cos(i * 2.39996) * math.sqrt(i / count) * 600,
           math.sin(i * 2.39996) * math.sqrt(i / count) * 510] for i in range(count)]
    index = {n["id"]: i for i, n in enumerate(nodes)}
    pairs = sorted({tuple(sorted((index[e["source"]], index[e["target"]]))) for e in edges})
    anchors = [(90, -175), (205, -175), (275, -65), (155, 25),
               (325, 85), (210, 195), (65, 145), (15, 15), (-35, -110)]
    pinned = {index[scene[k]]: p for k, p in zip(SCENE, anchors)}
    for step in range(100):
        delta = [[-x * .003, -y * .003] for x, y in xy]
        for a, b in pairs:
            dx, dy = xy[b][0] - xy[a][0], xy[b][1] - xy[a][1]
            dist = max(math.hypot(dx, dy), 1)
            force = (dist - 85) * .009 / dist
            delta[a][0] += dx * force
            delta[a][1] += dy * force
            delta[b][0] -= dx * force
            delta[b][1] -= dy * force
        for a in range(count):
            for _ in range(25):
                b = rng.randrange(count)
                if a == b:
                    continue
                dx, dy = xy[a][0] - xy[b][0], xy[a][1] - xy[b][1]
                dist2 = max(dx * dx + dy * dy, 16)
                force = 950 / dist2
                delta[a][0] += dx * force
                delta[a][1] += dy * force
        speed = .9 - step * .004
        for i in range(count):
            if i in pinned:
                xy[i] = list(pinned[i])
            else:
                xy[i][0] += max(-9, min(9, delta[i][0])) * speed
                xy[i][1] += max(-9, min(9, delta[i][1])) * speed
    for node, point in zip(nodes, xy):
        node["x"], node["y"] = [round(v, 2) for v in point]


def build(root=ROOT):
    notes = {}
    for path in sorted((root / "wiki").rglob("*.md")):
        meta, body = read_note(path)
        notes[path.stem] = (path, meta, body)
    nodes = [{"id": m["identifier"], "name": name, "type": m["type"],
              "description": m.get("definition", m.get("title", name)),
              "status": m.get("status", "draft"), "path": p.relative_to(root).as_posix(),
              "excerpt": b.strip()[:1200]}
             for name, (p, m, b) in notes.items()]
    edges, seen = [], set()
    for name, (_, meta, _) in notes.items():
        for relation, value in meta.items():
            for target, anchor in links(value):
                if target not in notes or target == name:
                    continue
                key = (meta["identifier"], notes[target][1]["identifier"], relation, anchor)
                if key not in seen:
                    seen.add(key)
                    edges.append(dict(zip(("source", "target", "relation", "anchor"), key)))
    scene = {key: notes[name][1]["identifier"] for key, name in SCENE.items()}
    positions(nodes, edges, scene)
    evidence = {}

    def cite(key, name, anchor, label, url):
        p, _, body = notes[name]
        evidence[key] = {"nodeId": notes[name][1]["identifier"], "title": label,
                         "text": block(body, anchor), "anchor": anchor,
                         "path": p.relative_to(root).as_posix(), "url": url}

    cite("current", SCENE["cap"], "v20260101-p1", "시행령 제68조제1항 · 2026-01-01 시행",
         "https://www.law.go.kr/법령/고용보험법시행령/(20260101,35934,20251223)/제68조")
    cite("effective", SCENE["transition"], "v20260101-a1", "부칙 제35934호 제1조 · 시행일",
         "https://www.law.go.kr/법령/고용보험법시행령/(20260101,35934,20251223)/부칙")
    cite("transition", SCENE["transition"], "v20260101-a4", "부칙 제35934호 제4조 · 경과조치",
         evidence["effective"]["url"])
    cite("rate", SCENE["rate"], "v20191001-p1-i1", "고용보험법 제46조제1항제1호 · 지급 비율",
         "https://www.law.go.kr/법령/고용보험법/제46조")
    history = json.loads((root / "view/data/historical-cap.json").read_text(encoding="utf-8"))
    evidence["previous"] = {**history, "nodeId": scene["cap"]}
    current_cap, old_cap = money(evidence["current"]["text"]), money(history["text"])
    match = re.search(r"100분의\s*(\d+)", evidence["rate"]["text"])
    if not match:
        raise ValueError("Payment ratio cannot be read from the source")
    condition = notes[SCENE["condition"]][1]["unaryTests"]
    threshold = re.fullmatch(r'>= date\("(\d{4}-\d{2}-\d{2})"\)', condition)
    if not threshold:
        raise ValueError("Unsupported date criterion; review the scenario")
    baseline_path = root / "raw/work24/실업급여(일용직)/실업급여(일용직) 20261019T1926.md"
    baseline_meta, baseline_body = read_note(baseline_path)
    quote = block(baseline_body, "q1")
    baseline_amount = re.search(r"최대\s*([\d,]+)원", quote)
    if not baseline_amount:
        raise ValueError("Baseline quote changed")
    as_of = str(yaml.safe_load((root / "ontology/release.yaml").read_text(encoding="utf-8"))["asOf"])
    fingerprint = hashlib.sha256()
    for path in [*(v[0] for v in notes.values()), baseline_path,
                 root / "ontology/release.yaml", root / "view/data/historical-cap.json"]:
        fingerprint.update(path.relative_to(root).as_posix().encode())
        fingerprint.update(path.read_bytes())
    return {"meta": {"asOf": as_of, "fingerprint": fingerprint.hexdigest(),
                     "nodeCount": len(nodes), "relationCount": len(edges),
                     "pairCount": len({tuple(sorted((e['source'], e['target']))) for e in edges}),
                     "classes": dict(Counter(n["type"] for n in nodes))},
            "nodes": nodes, "edges": edges, "scene": scene, "evidence": evidence,
            "scenario": {"id": "daily-benefit-cap", "minDate": "2025-01-01", "maxDate": as_of,
                         "threshold": threshold[1], "criterion": condition,
                         "currentBaseCap": current_cap, "previousBaseCap": old_cap,
                         "rate": int(match[1]) / 100},
            "baseline": {"title": baseline_meta["title"], "url": baseline_meta["url"],
                         "capturedAt": baseline_meta["generatedAtTime"],
                         "modified": str(baseline_meta["modified"]), "quote": quote,
                         "cap": int(baseline_amount[1].replace(",", "")),
                         "path": baseline_path.relative_to(root).as_posix(), "anchor": "q1"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build()
    output = ROOT / "view/data/vault.json"
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != payload:
            raise SystemExit("view/data/vault.json is stale. Run scripts/export_view.py.")
        print("View snapshot matches the vault.")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8", newline="\n")
        print(f"Exported {len(data['nodes'])} notes and {len(data['edges'])} typed relations to {output}")


if __name__ == "__main__":
    main()
