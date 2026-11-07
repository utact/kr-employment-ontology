"""Coverage of the statutes in scope: the articles that wiki notes cite and those they do not, by chapter.

The scope is `coverage` in scripts/sources.yaml: the chapters and articles of each law, and the articles left out with a reason.
It also takes in every article of a lower law that receives a delegation from an article in scope, by the 위임조문 data of 법제처.
Chapters and articles under `defer` stay out of the count until a later phase, and so do the articles they delegate to.
The report lists them by reason, with those that no note cites yet.
An article counts as covered when a wiki note other than a statute note links to it or to one of its blocks.
"""

import argparse
import re

import lawlib as L
import statutes as S

LABEL = re.compile(r"제(\d+)(조|장)(?:의(\d+))?")
LINK = re.compile(r"\[\[([^\]|#]+)")


def key_of(label):
    """Unit key of a label such as 제10조의2 or 제5장의2."""
    match = LABEL.fullmatch(label)
    if not match:
        raise ValueError(f"unknown unit {label}")
    if match[2] == "조":
        return L.article_key(match[1], match[3])
    return "heading-ch" + match[1] + (f"-{match[3]}" if match[3] else "")


DELETED = re.compile(r"제\d+조(?:의\d+)?\s*삭제")


def articles(law):
    """Keys of the articles of the current version, without deleted ones such as 제39조 삭제 <2019. 8. 27.>."""
    return [key for key, (kind, row) in law.rows_of(law.current).items()
            if kind == "article" and not (not row.get("조문제목") and DELETED.match(row.get("조문내용", "")))]


def units_of(law, labels):
    """Keys of the articles that the labels name, directly or through a 장 that holds them."""
    keys = {key_of(label) for label in labels}
    return [key for key in articles(law) if key in keys or any(unit.key in keys for unit in S.Unit(law, key).ancestors())]


def delegated(statutes, found, skip):
    """Articles of lower laws that receive a delegation from an article in found, as {(law, key): upper}, without those in skip."""
    taken = {}
    for (lower, key), uppers in statutes.delegations.items():
        if (lower, key) in found or (lower, key) in skip or lower not in statutes.laws:
            continue
        if key not in articles(statutes.laws[lower]):
            continue
        for upper, provision in uppers:
            try:
                upper_key = S.provision_block(provision)[0]
            except ValueError:
                continue
            if (upper, upper_key) in found:
                taken[lower, key] = (upper, upper_key)
                break
    return taken


def scope(statutes, config):
    """Articles in scope as a set of (law, key), the articles left out as {(law, key): reason}, and the deferred ones as {(law, key): reason}."""
    chosen, left_out, deferred = set(), {}, {}
    for name, entry in config.items():
        law = statutes.laws[name]
        for label, reason in (entry.get("exclude") or {}).items():
            left_out[name, key_of(label)] = reason
        for label, reason in (entry.get("defer") or {}).items():
            for key in units_of(law, [label]):
                if (name, key) not in left_out:
                    deferred[name, key] = reason
        chosen.update((name, key) for key in units_of(law, entry.get("units", [])))
    chosen -= set(left_out) | set(deferred)
    while taken := delegated(statutes, chosen, set(left_out) | set(deferred)):
        chosen.update(taken)
    while taken := delegated(statutes, deferred, chosen | set(left_out)):
        deferred.update({lower: deferred[upper] for lower, upper in taken.items()})
    return chosen, left_out, deferred


def citations(statutes, wiki):
    """The notes that link each unit, as {(law, key): set of note names}, from every note but statute notes."""
    found = {}
    for path in sorted(wiki.rglob("*.md")):
        if path.parent.name in ("LegalResource", "LegalResourceSubdivision"):
            continue
        for name in set(LINK.findall(path.read_text(encoding="utf-8"))):
            unit = statutes.unit_named(name.strip())
            if unit is not None:
                found.setdefault((unit.law.name, unit.key), set()).add(path.stem)
    return found


def chapter(law, key):
    """The 장 that holds an article, or None for an article outside any 장."""
    headings = [unit for unit in S.Unit(law, key).ancestors() if unit.kind == "heading"]
    return headings[-1] if headings else None


def report(statutes, config, wiki, every=False):
    """Lines that count the cited articles in scope by law and 장, and list the others."""
    chosen, left_out, deferred = scope(statutes, config)
    cited = citations(statutes, wiki)
    lines, total, covered = [], 0, 0
    for name in config:
        law = statutes.laws[name]
        keys = [key for key in articles(law) if (name, key) in chosen]
        done = [key for key in keys if (name, key) in cited]
        total, covered = total + len(keys), covered + len(done)
        lines.append(f"{name}: {len(done)}/{len(keys)}")
        groups = {}
        for key in keys:
            heading = chapter(law, key)
            groups.setdefault(f"{heading.number} {heading.title}" if heading else "장 밖", []).append(key)
        for title, group in groups.items():
            lines.append(f"  {title}: {sum(1 for key in group if (name, key) in cited)}/{len(group)}")
            for key in group:
                if every or (name, key) not in cited:
                    unit = S.Unit(law, key)
                    mark = "o" if (name, key) in cited else "-"
                    lines.append(f"    {mark} {unit.number}" + (f" {unit.title}" if unit.title != unit.number else ""))
    lines.append(f"total: {covered}/{total}")
    if deferred:
        lines.append("deferred:")
        groups = {}
        for (name, key), reason in deferred.items():
            groups.setdefault(reason, []).append((name, key))
        for reason, group in groups.items():
            lines.append(f"  {reason}: {sum(1 for unit in group if unit in cited)}/{len(group)}")
            for name, key in group:
                if every or (name, key) not in cited:
                    mark = "o" if (name, key) in cited else "-"
                    lines.append(f"    {mark} {S.Unit(statutes.laws[name], key).name}")
    if left_out:
        lines.append("left out:")
        for (name, key), reason in left_out.items():
            lines.append(f"  {S.Unit(statutes.laws[name], key).name}: {reason}")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="list the cited articles too")
    args = parser.parse_args()
    as_of, _ = L.release()
    statutes = S.Statutes(as_of)
    print("\n".join(report(statutes, S.SOURCES["coverage"], S.WIKI, args.all)))


if __name__ == "__main__":
    main()
