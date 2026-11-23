"""Preview exact customer inputs in both QA modes, then export selected first turns for external comparison."""

import argparse
import hashlib
import json
import os
import re
import secrets
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import ask
import llm


def serialized(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def store(path, obj):
    """Publish a complete result once. A concurrent retry can never replace a saved first turn."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temp = Path(file.name)
            file.write(serialized(obj).encode("utf-8"))
        if os.name == "nt":
            os.rename(temp, path)  # Windows refuses to rename over an existing destination.
        else:
            os.link(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inputs(path, context):
    rows, seen = [], set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ident, day, question = row["id"], row["as_of"], row["question"]
        if not re.fullmatch(r"[\w-]+", ident) or ident in seen or not question.strip():
            raise ValueError(f"중복 ID 또는 잘못된 입력: {ident}")
        seen.add(ident)
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError(f"상담일 형식 오류: {ident}")
        visible = f"상담 기준일은 {day}입니다.\n{question}" if context == "historical" else question
        rows.append({"id": ident, "as_of": day, "message": visible, "sha256": digest(visible)})
    if not rows:
        raise ValueError("입력 문항이 없습니다.")
    return rows


def product_version():
    root = ask.ROOT
    files = [root / "scripts" / name for name in ("ask.py", "bench_qa.py", "llm.py", "lawlib.py", "statutes.py")]
    entries = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in [*files, *sorted((root / "wiki").rglob("*.md")), *sorted((root / "raw").rglob("*.md")),
                         *sorted((root / "raw/law/판례").glob("*.json")), *sorted((root / "raw/law/법령해석례").glob("*.json"))]}
    return digest(serialized(entries))


def choose(rows, ids):
    if not ids:
        return rows
    unknown = set(ids) - {r["id"] for r in rows}
    if unknown:
        raise ValueError(f"없는 문항 ID: {sorted(unknown)}")
    return [r for r in rows if r["id"] in ids]


def validate_record(run, row, mode, fingerprint):
    if (run.get("question") != row["message"] or run.get("asOf") != row["as_of"]
            or run.get("mode") != mode or run.get("trialFingerprint") != fingerprint
            or row["sha256"] != digest(row["message"])):
        raise ValueError(f"실제 실행의 제품·조건·입력이 시험과 다릅니다: {row['id']}")


def preview(args):
    config = llm.configuration(args.provider)
    settings = {k: config[k] for k in ("provider", "model", "thinking", "effort", "nvidiaThinking")}
    rows = inputs(args.inputs, args.context)
    selected = choose(rows, args.ids)
    manifest = {"product": product_version(), "context": args.context, "modelSettings": settings, "inputs": rows}
    path = args.trial / "manifest.json"
    if not path.exists():
        store(path, manifest)
    if read(path) != manifest:
        raise ValueError("입력·제품·모델 설정이 변경되었습니다. 새 시험 폴더를 사용하세요.")
    fingerprint = digest(serialized(manifest))
    index = None
    for row in selected:
        for mode in ("vault", "memory"):
            target = args.trial / f"{row['id']}.{mode}.json"
            if target.exists():
                saved = read(target)
                validate_record(saved, row, mode, fingerprint)
            else:
                if mode == "vault":
                    if index is None:
                        index = ask.Index()
                    saved = ask.answer(index, row["message"], row["as_of"], provider=config["provider"])
                else:
                    payload = ask.response_input(row["message"], row["as_of"], day, [], [], "memory")
                    saved = ask.generate(payload, provider=config["provider"])
                saved["recordedAt"] = datetime.now(timezone.utc).isoformat()
                saved["mode"], saved["trialFingerprint"] = mode, fingerprint
                validate_record(saved, row, mode, fingerprint)
                store(target, saved)
            day = saved["versionDate"]
            print(f"{row['id']} {mode} {saved['status']}", flush=True)


def freeze(args):
    manifest = read(args.trial / "manifest.json")
    fingerprint = digest(serialized(manifest))
    rows = choose(manifest["inputs"], args.ids)
    fixed = []
    for row in rows:
        answers = {}
        for mode in ("vault", "memory"):
            path = args.trial / f"{row['id']}.{mode}.json"
            if not path.is_file():
                raise ValueError(f"동일 입력의 {mode} 실행 대기: {row['id']}")
            run = read(path)
            validate_record(run, row, mode, fingerprint)
            answers[mode] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "status": run["status"], "text": ask.customer_text(run)}
        fixed.append({**row, "comparison": answers})
    store(args.out, {"context": manifest["context"], "product": manifest["product"],
                     "modelSettings": manifest["modelSettings"], "firstTurns": fixed})


def sheet(args):
    """Print only the exact message for the selected item, ready to paste in a fresh conversation."""
    items = choose(read(args.frozen)["firstTurns"], [args.id])
    print(items[0]["message"])


def blind(args):
    """Prepare independent grading sheets only for actual first turns with matching input."""
    frozen = {r["id"]: r for r in read(args.frozen)["firstTurns"]}
    captured = [json.loads(line) for line in args.responses.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    packet, key = [], {}
    for reply in captured:
        ident = reply["id"]
        if ident not in frozen or ident in key:
            raise ValueError(f"확정 입력에 없거나 중복된 응답: {ident}")
        row = frozen[ident]
        if reply["sent"] != row["message"] or not reply["first_response"].strip():
            raise ValueError(f"실제 입력 또는 첫 응답 확인 필요: {ident}")
        pair = [("vault", row["comparison"]["vault"]["text"]), ("external", reply["first_response"])]
        secrets.SystemRandom().shuffle(pair)
        key[ident] = {"A": pair[0][0], "B": pair[1][0]}
        packet.append({"id": ident, "message": row["message"], "as_of": row["as_of"],
                       "A": pair[0][1], "B": pair[1][1]})
    if not packet or args.out.exists():
        raise ValueError("수집된 응답과 새 채점 폴더가 필요합니다.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent) as tmp:
        ready = Path(tmp) / "packet"
        store(ready / "answers.json", packet)
        store(ready / "key.json", key)
        ready.rename(args.out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("preview")
    run.add_argument("inputs", type=Path)
    run.add_argument("trial", type=Path)
    run.add_argument("--context", required=True, choices=("historical", "live"))
    run.add_argument("--provider", default="codex")
    run.add_argument("--ids", nargs="+")
    lock = sub.add_parser("freeze")
    lock.add_argument("trial", type=Path)
    lock.add_argument("out", type=Path)
    lock.add_argument("--ids", nargs="+", required=True)
    show = sub.add_parser("message")
    show.add_argument("frozen", type=Path)
    show.add_argument("id")
    grade = sub.add_parser("blind")
    grade.add_argument("frozen", type=Path)
    grade.add_argument("responses", type=Path)
    grade.add_argument("out", type=Path)
    args = parser.parse_args()
    try:
        {"preview": preview, "freeze": freeze, "message": sheet, "blind": blind}[args.command](args)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
