# Employment domain ontology

This vault holds an ontology of the Korean employment domain served by 고용24, written as Markdown notes for Obsidian. The first domain is 이직 and 실업급여 under 고용보험법. Accuracy takes priority over coverage.

## Structure

The vault has three layers: raw sources that are never edited, the wiki that the LLM and scripts write, and the schema that defines the wiki.

| Path | Layer | Content |
| --- | --- | --- |
| `raw/` | Raw | Collected sources |
| `wiki/` | Wiki | Instance notes in one subfolder per class |
| `AGENTS.md` | Schema | Operating rules for every agent |
| `CLAUDE.md`, `.claude/settings.json` | — | Claude Code adapter: a reference to `AGENTS.md` and the hook that enforces the Review rules |
| `ontology/schema.yaml` | Schema | RDF model in LinkML |
| `ontology/schema.md` | Schema | Document generated from `ontology/schema.yaml` |
| `ontology/sources.md` | Schema | Rules for raw sources, statute notes and text checks |
| `ontology/release.yaml` | Schema | Reference date, transitional window and jurisdiction of the wiki |
| `ontology/shapes/` | Schema | Official SHACL shapes of CPSV-AP and CCCEV |
| `ontology/verification.jsonl` | — | Verification ledger |
| `ontology/cq/` | — | SPARQL queries of the competency questions |
| `views/` | — | Obsidian canvases and bases that show the wiki |
| `.obsidian/` | — | Obsidian settings, without the workspace files |
| `scripts/` | — | Collection, generation and validation scripts |
| `tests/` | — | Fixture notes and tests for the scripts |
| `.cache/` | — | Local cache of uncited raw versions, ignored by Git |
| `docs/` | — | Competency questions, scenarios and the free-question benchmark |
| `index.md` | — | Notes by class |

## Reference date

- `asOf` in `ontology/release.yaml` is the reference date (기준 시점) of the whole wiki.
- The current version of a law is the version in force on that date.
  - Decide it by comparing 시행일자 with the reference date, never by the API's 현행 or 연혁 label.
  - When one 시행일자 has several MSTs, use the one with the later 공포일자, then the later 공포번호.
- Changing the reference date is a `schema` operation.
  - Regenerate the statute notes and check the wiki afterwards.

## Sources

[ontology/sources.md](ontology/sources.md) holds the rules for raw sources, statute notes and text checks. Read it before collecting a source, regenerating statute notes, or changing `scripts/collect.py`, `check_raw.py`, `transitional.py`, `statutes.py` or the text comparison of `lint.py`.

- Collect sources with `uv run python -X utf8 scripts/collect.py`, and never edit a saved source.
- Generate statute notes with `uv run python -X utf8 scripts/statutes.py`. The LLM never writes or edits statute text.
- Add a quotation of a 고용24 guide, 법령해석례 or 판례 with `scripts/collect.py quote`, which appends it to the raw note.
- Cite statute blocks by the IDs their notes declare, such as `^v20260918-p1` for 제1항 of the version in force from 2026-09-18.

## Note format

- Name each file with its Korean preferred label (`skos:prefLabel`), unique in the vault.
  - If two notes would share a name, add the kind in parentheses, as in `이직 (사건)`.
  - File names may change, but an `identifier` never does.
- Choose the class by the kind of thing.
  - Benefits and procedures, such as 구직급여 and 실업의 신고: `PublicService`
  - Events, such as 이직: `LifeEvent` or `BusinessEvent`
  - Public bodies, such as 고용노동부: `PublicOrganisation`
  - Party types, such as 사업주 and 피보험자: `Concept` in the 고용보험 당사자 유형 scheme
  - Information that rules and conditions use, such as 이직일 and 기초일액: `InformationConcept`
  - Codes and lists of alternatives, such as 상실사유 구분코드 and 정당한 이직 사유: `Concept` in a `ConceptScheme`
  - Conditions and limits: `Criterion` and `Constraint`
  - Calculations and tables: `Rule`
  - Documents to submit, such as 이직확인서: `EvidenceType`
- Write frontmatter with schema properties only, in this order.
  1. `type`, `identifier`, `aliases` and `definition`
  2. Class properties, those of parent classes first, each group in the order of its table in `ontology/schema.md`
  3. `validFrom`, `validThrough` and `isReplacedBy`
  4. `source`, `status`, `reviewedBy` and `lastReviewed`
- Do not write `prefLabel`; `scripts/vault.py` takes it from the file name.
- Write every relation as wikilinks, only in the direction the schema defines, and read the inverse from backlinks.
  - A wikilink may point to a block, as in `"[[고용보험법 제45조#^v20260918-p5]]"`.
- Write a decision table as a header and rows of cells, which `scripts/vault.py` expands with positions.
- Change classes and properties only in `ontology/schema.yaml`.
  - Run `uv run python -X utf8 scripts/schema_doc.py` afterwards, and never edit `ontology/schema.md` by hand.
- Write the body in Korean.
  - Open with a definition paragraph.
  - Split the explanation under `##` headings.
  - Keep footnotes at the end.

The frontmatter of `wiki/PublicService/구직급여.md` looks like this.

```yaml
---
type: PublicService
identifier: job-seeking-benefit
definition: 이직한 피보험자가 수급 요건을 갖추어 실업의 인정을 받은 날에 지급하는 급여
hasCompetentAuthority: ["[[고용노동부]]"]
hasLegalResource: ["[[고용보험법 제40조]]", "[[고용보험법 제44조]]"]
source: ["[[고용보험법 제40조#^v20260918-p1]]", "[[고용보험법 제44조#^v20260918-p1]]"]
status: draft
---
```

The decision table of `wiki/Rule/소정급여일수 산정.md` starts like this.

```yaml
decisionTable:
  hitPolicy: UNIQUE
  input: ["[[이직일 현재 연령]]", "[[피보험기간]]"]
  output: ["[[소정급여일수]]"]
  rule:
    - ["< 50", "< 1", "120"]
    - ["< 50", "[1..3)", "150"]
```

## Citations

- Footnote every factual sentence with the block it rests on.
  - Statutes: a block of the statute note, labelled with the official citation, as in `[^1]: [[고용보험법 제40조#^v20260918-p1-i1|고용보험법 제40조제1항제1호]]`
  - 단서, 본문, 전단 and 후단: link the block, and name the part in the label, only when the block has it
  - Items of a 별표 or 서식: link the block, and name the item in the label, as in `고용보험법 시행령 별표 2 제1호나목`
  - 항 and 호 of a 행정규칙 article: link the block, and name them in the label, as in `실업인정 및 재취업지원규정 제12조제2항제1호`
  - 판례, 법령해석례 and 고용24 guides: a quotation block of the raw note, labelled with the name of the source, as in `[^2]: [[법령해석례 26-0321 20261019T2045#^q1|법제처 법령해석례 26-0321]]` and `대법원 2015두44165 판결`
    - A 판례 often interprets an earlier version, as 2015두44165 does the 시행령 before 2014-01-01. Cite it for the current version only when the words it interprets are unchanged there, as 계속하여 고용된 경우, and quote both texts in the note.
  - A footnote to a whole raw note rests only on its frontmatter and the basic information of its response, such as 시행일자 and 공포번호.
- Quote statutory text verbatim inside “ ” (U+201C and U+201D), followed directly by its footnote.
  - Statute text itself uses ASCII double quotes, as in `[이하 "기초일액(基礎日額)"이라 한다]`.
  - Use no other quotation marks in prose, such as ‘ ’ or ASCII double quotes.
  - Keep source text and interpretation in separate sentences.
- Write numbers in Arabic numerals, so that they can be checked: 2배, not 두 배, and 10일, not 열흘. Keep the words only where the cited block writes them so, as 두 번 이상 in some statutes.
- Every number, amount and date in a footnoted sentence must appear in a cited block, with the same unit.
  - Scripts compare quotes and numbers with a block as the text checks of `ontology/sources.md` define.
  - Numbers inside citations, such as 제45조제5항, 별표 1 and 부칙 제21473호, are exempt.
  - Numbers inside the names of wiki notes, such as 이직 전 1일 소정근로시간, are exempt, because the note they name carries its own sources.
  - Names that contain digits, such as 고용24, are not numbers.
  - Give a calculated number a footnote that links its `Rule` and states the calculation in inline code, such as `113500 * 60 / 100`; the checker evaluates it.
  - The operands of a calculation must appear in a cited block, as a number or as a ratio such as 100분의 60 for `60 / 100`.
  - Mark a calculation on example inputs with 예시 in its footnote, as in `` [^3]: [[최저기초일액 산정]] 예시 `8 * 10320` ``. Its operands may then appear in the sentence instead.
  - Numbers in the labels of wikilinks, as in `[[기초일액|11만3500원]]`, count as part of the sentence, except the 공포일자 or 시행일자 of the statute note the link names, as in `[[고용보험법 시행령 부칙 제35934호|부칙 제35934호(2025. 12. 23.)]]`.
  - The 시행일 of the version of a cited statute block counts as part of the block, as 2020-08-28 for `[[고용보험법 제62조#^v20200828-p2]]`, because a 부칙 sometimes states it only as a time after 공포, such as 공포 후 1년이 경과한 날.
- Numbers and dates in `definition`, `unaryTests`, decision table cells and `literalExpression` must appear in the blocks of `source` or `isDerivedFrom`.
  - The 시행일 of the version of such a block counts, as in a footnoted sentence.
  - A number in a test or cell carries the unit of its concept's `unitCode` or `currency`, such as 일 for `DAY` and 원 for `KRW`, and a part of a duration its own unit, such as 개월 for `M`.
  - FEEL durations have no weeks, so a part in days also matches a number of 주 that is a seventh of it, as `duration("P14D")` for 2주간.
  - An operand of `*` or `/` carries no unit, because it states a ratio, as 60 and 100 in `기초일액 * 60 / 100`.
  - 0 and 1 in FEEL are exempt, because they often encode structure, as `duration("P1M")` for 다음 달.
- Rank sources in this order.
  1. 법률
  2. 시행령
  3. 시행규칙
  4. 고시·행정규칙
  5. 판례 of 대법원, the final judicial reading of the statutes above
  6. 법령해석례 of 법제처, which interpret the statutes above without binding as they do
  7. 고용24 official guides
  8. Statistics
- State a fact from the highest-ranked source.
  - When a lower-ranked source says otherwise, add a `> [!warning] 출처 불일치` callout that quotes both.
  - When sources of the same rank disagree, record both under a `> [!warning] 출처 충돌` callout and never pick one yourself.
- Write limits and conditions as FEEL `unaryTests` on a `Constraint` or `Criterion`.
  - Use `validFrom` and `validThrough` only for calendar validity.
  - Model a transitional provision (경과조치) as a `Criterion` on the date it depends on, such as 이직일, and link it with `appliesWhen`.
  - A note with `appliesWhen` may cite a version that is not in force on the reference date, when the version's period meets the dates in which all its criteria hold.
  - A criterion on a date may cite such a version when the version's period meets the dates its own test admits, as 2023-07-01 이후 수급자격 인정 신청 cites the 2023-07-01 version of 고용보험법 제40조.
  - Criteria that test no date leave such a citation unchecked, so lint reports it.
- State a provision with its 단서 and exceptions, or name the ones a note leaves out.
  - Leave out a case that a rule, constraint or criterion does not cover through a criterion in `appliesWhen`, as 기초일액 산정 does for 고용보험법 제45조제1항 단서.
  - Leave out the same way a case in which two provisions can apply and neither prevails, as 최저기초일액이 상한액 이하 does for 고용보험법 제45조제4항 and 제5항.
- Describe an item that counts only under the condition of the item above it together with that condition, as each 목 of 고용보험법 시행규칙 별표 2 제5호.
- Never state unconfirmed content as fact.
  - Leave it as a question in a `> [!question]` callout, each line ending in "?".

## RDF export

`uv run python -X utf8 scripts/vault.py export OUT.ttl` writes the wiki as RDF after the checks of `vault.py check` pass.

- Each declared block becomes a version-independent `LegalResourceSubdivision`, such as `law-001761-art-45-p5`, with one `LegalExpression` per version, such as `law-001761-art-45-v20210701-p5`.
  - A version of a block carries the dates of its unit's version, but not the 공포일자, 공포번호 or MST, which belong to the act.
- A block link in `source` names the version of the block, and one to a whole-text block `^v…-t` the version of the note's own unit.
- A block link in `cites`, `basedOn`, `isDerivedFrom`, `implements` or `hasLegalResource` names the block itself, or the unit for a whole-text block, because ELI, CPSV-AP and CCCEV give these properties works as range.
- The export adds what the standards expect and the notes leave implicit.
  - `dct:title` and `dct:description` from the note name and `definition`, for the classes that CPSV-AP and CCCEV describe
  - The language tag `ko` on the names and descriptions that the official shapes require as `rdf:langString`, and only there, because CCCEV requires `xsd:string` for some of them
  - `dct:spatial` of every public organisation, from `jurisdiction` in `ontology/release.yaml`
  - The values of the schema's enumerations as SKOS concepts in concept schemes
- The checks also validate the export against the official shapes of CPSV-AP 3.2.0 and CCCEV 2.1.0 in `ontology/shapes/`, collected with `scripts/collect.py shapes`.
  - `ontology/shapes/README.md` records the SHA-256 of each stored file's bytes.
  - Statute units count as `eli:LegalResource`, because ELI makes subdivisions a kind of it, and as `cccev:ReferenceFramework`. Their versions do not.
  - The export states these types for each unit, so that the file validates without the alignment.
  - Public organisations count as `org:Organization`, because CPSV-AP makes Public Organisation a subclass of it, and the shape of a channel's `ownedBy` requires that class. The export states this type too.
  - `Participation` without `hasParticipant` is a documented deviation, because party types defined by law are not specific agents. It covers only the missing value.

## Review

Notes written by the LLM move through three statuses in order.

1. `draft`: created or edited by the LLM
   - Any edit, or any change in a cited block, returns a note to `draft`.
2. `verified`: checked by a separate agent
   - The verifier did not write the note and works in a fresh context.
   - Run it on the most capable model available.
     - Use effort `xhigh` for the first verification of a note and after any change to what it states: a reading, a condition, a scope, a number, a date or an expression.
     - Use effort `high` after a change that states nothing new, such as a typo, a footnote label or a sentence moved within the note.
     - When unsure, use `xhigh`, because a wrong pass enters the ledger and later notes build on it.
   - Give it the note, the cited blocks and the notes that link to or from the note, which `uv run python -X utf8 scripts/verify.py context <note>...` prints.
   - It compares every factual sentence with the cited blocks, checks schema conformance and looks for contradictions with the linked notes.
   - On any mismatch, the note stays `draft` until the fixes pass a new verification.
3. `reviewed`: approved by the human owner
   - Record `reviewedBy` and `lastReviewed`.
   - The LLM never sets `reviewed`, `reviewedBy` or `lastReviewed`.
   - In Claude Code, `.claude/settings.json` runs `scripts/review_guard.py` before every edit and shell command. It blocks writing these into notes of `wiki/`, and any edit of a reviewed note that does not set its status to draft.
   - Its shell check reads only the command text, so a script that writes them from its own code is not stopped. Other agents follow the rule without the hook.

- Statute notes generated by script start as `verified`, because the script checks them against the raw source.
- Append one line to `ontology/verification.jsonl` for every generated or verified note.
  - Key it by `identifier`.
  - Record the hash of the note without `status`, `reviewedBy` and `lastReviewed`, and the hashes of the cited blocks.
  - Record the generator and its commit, or the verifier's model, effort and session.
  - For a note the verifier passed, `uv run python -X utf8 scripts/verify.py record --model <model> --effort <effort> --session <id> <note>...` writes the line and sets `verified`.
- Retired or superseded instances are never deleted.
  - Set `validThrough` and link the successor with `isReplacedBy`.

## Operations

### Ingest

Ingest reflects a source in the wiki.

1. Save the source to `raw/` with a script.
2. Regenerate the statute notes when the source is a statute.
3. Find related notes through `index.md`.
4. Create or edit notes.
   - If a needed class or property is missing, update the schema first.
5. Update `index.md` with `uv run python -X utf8 scripts/index.py`.

### Query

Query answers a question from the wiki.

- Link the notes that the answer rests on.
- If the wiki lacks the answer, say so and propose sources to collect.

### Lint

Lint checks the wiki for these problems with `uv run python -X utf8 scripts/lint.py`.

- Links
  - Broken links, and links to blocks, quotations or headings that the target note does not declare
  - Notes outside the graph: no other note links to them, and they link only to statute and raw notes, except generated statute notes
  - `source` values that point to anything other than a raw note, a statute block or a quotation
- Schema
  - Notes that fail `uv run python -X utf8 scripts/vault.py check`, which validates them against LinkML, the SHACL shapes of the schema and the official shapes in `ontology/shapes/`
  - `ontology/schema.md` out of date with `ontology/schema.yaml`
  - Canvases in `views/` out of date with the notes, the schema or the competency question queries
  - Duplicate file names, identifiers or aliases
- Rules
  - `unaryTests` and FEEL expressions that do not parse
  - Tests or expressions whose types do not match the `typeRef` of their concepts
  - FEEL names that are not in `requiredInput`
  - Decision table inputs missing from `requiredInput`, and outputs other than `variable`
  - `UNIQUE` decision tables with overlapping rows, where the tests have literal bounds
- Sources
  - Factual sentences, callout titles that end like a sentence included, whose footnotes cite no statute block, quotation or raw note
  - Quotes or numbers that do not match the cited block, numbers in other units, and numbers written in Korean numerals
  - Quotes in marks other than “ ”, and lines of question callouts that are not questions
  - Footnote links to statute blocks without the citation label, or with a part that the block lacks
  - Calculation operands outside the cited blocks, or outside the sentence too when the footnote marks an example
  - Numbers and dates of frontmatter values outside the blocks of `source` and `isDerivedFrom`, or in another unit
  - Facts that cite a version not in force on the reference date, without a date condition in `appliesWhen` or in the test of the criterion itself, or outside the dates of those conditions
  - Cited blocks whose hash differs from the one in the verification ledger
  - `verified` or `reviewed` notes without a matching ledger entry, or whose entry lacks a cited block
  - `reviewed` notes without `reviewedBy` and `lastReviewed`
  - Versions of one unit with the same date, or whose dates overlap
  - Scheduled versions that come into force on or before the reference date
- Secrets
  - `.env` values in tracked files
  - Credential parameters in raw URLs

Lint compares each number with the cited blocks, not the claim it makes. A sentence that puts two numbers of a block together wrongly passes, and so does `duration("P15D")` for "다음 달 15일까지", whose 15일 is in the block. The verifier agent compares the meaning.

### Coverage

`uv run python -X utf8 scripts/coverage.py` counts the articles in scope that wiki notes cite, by law and 장, and lists the others.

- The scope is `coverage` in `scripts/sources.yaml`: the 장 and articles of each law, and the articles left out with a reason.
  - It also takes in every article of a lower law that receives a delegation from an article in scope, by the 위임조문 data.
  - Deleted articles do not count.
- An article is covered when a note other than a statute note links to it or to one of its blocks.
- Leave out only an article that governs a matter other than 이직 and 실업급여, such as 출산전후급여 or the organization of 고용보험심사위원회.
- Put under `defer` the 장 and articles that the human owner has put off to a later phase, with the matter as the reason.
  - They stay out of the count, together with the articles they delegate to.
  - The report lists them by reason, with those that no note cites yet, so that they can be taken up later.
- Settle each question that a source settles, and leave the others open in their callouts.
- Ask the human owner only what the wiki covers, never how a statute is read.

### Competency questions

`docs/competency-questions.md` lists the questions the ontology must answer, with expected answers that cite the provisions they rest on.

- Check them with `uv run python -X utf8 scripts/cq.py`.
- A question is checked when `ontology/cq/<id>.rq` holds its query.
  - The query runs on the export and returns `?item` and `?source` rows: the parts of the answer and the statute units or blocks they rest on.
- Every provision the expected answer cites must be among the sources, or contain one of them.
  - Citations under 범위 밖, 관련 사항 and 검사 항목 are not part of the expected answer.
  - An item of a 별표 or 별지 서식 resolves to the whole unit, because their notes declare no item blocks, so the verifier compares the items.
- A query fails when a BIND or FILTER uses a variable that its own group does not bind.
  - SPARQL evaluates the group before the outer pattern, so the variable is unbound there and a later triple pattern matches every note, as `{ BIND(?rule AS ?item) } UNION { … }` did.
- `scripts/cq.py` also checks the scenarios in `docs/scenarios.md`.
  - A numbered step names its service by `identifier`, as in "서비스는 `job-application`(구직신청)이다", and its 선행 조건 by step number, as in "선행 조건은 3단계 구직 등록이다".
  - The service of a step must `requires` the service of each step that is its 선행 조건.
  - Every competency question a step lists must have a query and pass.

### Views

Obsidian's graph view draws links without their kind, so `views/` shows the ontology in canvases, whose edges carry labels, and in bases.

- Regenerate the canvases with `uv run python -X utf8 scripts/canvas.py` after changing notes, the schema or a query in `ontology/cq/`.
  - `views/schema.canvas` shows the classes grouped by standard, with their object properties and `is_a` as labelled edges.
  - `views/역량 질문/` holds one canvas per checked competency question: the notes its query returns, the notes the query names, the notes that join them, and the statute blocks they cite in `source`.
  - Each edge is labelled with the property of the note it starts from.
- Write the bases in `views/` by hand: tables per class and a queue of notes the human owner has not reviewed.
- The graph view in `.obsidian/graph.json` colors notes by class folder, with the colors of the canvases.
- Commit changes to `.obsidian/` with the work that makes them, but keep `workspace.json` and `workspace-mobile.json` out of Git.

## Conventions

### Language

- Choose the language by reader.
  - `AGENTS.md` and `ontology/sources.md`: English
  - `ontology/schema.md` and `index.md`: English headings, Korean prose
  - `README.md`, `docs/` and vault notes in `wiki/` and `raw/`: Korean
- In Korean prose, write technical terms whose original is English in English.
  - Examples: ontology, schema, class, property, instance, wiki, vault, wikilink, backlink, frontmatter, callout, agent, context, hash
- In Korean prose, write loanwords listed in the Korean dictionary in Korean.
  - Examples: 파일, 폴더, 노트, 링크, 데이터, 스크립트
- Use the terms of the issuing authority.
  - Legal concepts: statutory terms, such as 이직 and 피보험자격
  - 법제처 data: 법제처 terms, such as 현행 법령 and 시행일자
- Coin no project-specific terms.
  - If no standard term exists, define the term where it first appears.

### Letter case

- Use capitals only where they carry meaning.
  - In English text, use sentence case for headings, list items and table cells.
  - In Korean prose, keep English common nouns lowercase.
  - Keep the spelling of proper nouns, such as Obsidian, Markdown and LLM Wiki, and of acronyms, such as API, IRI and RDF.
- Case identifiers by kind.
  - Classes: PascalCase
  - Properties: camelCase
  - Property values: lowercase
  - `identifier` values: kebab-case
- Keep the spelling of codes from external standards, such as `DAY`, `KRW` and `UNIQUE`.

### Korean prose

- Write short declarative sentences ending in "-다".
- Write one paragraph per line.
  - Never break a line mid-sentence.

### Markdown

- Section order
  - Put the overview first.
  - Order the remaining sections by operation, or so that each term is defined before use.
  - Put cross-cutting conventions last.
- Headings
  - Start a repository document with a single `#` heading.
  - Give vault notes no `#` heading, because the file name is the title.
  - Use one language for all headings of a document.
  - Never skip a heading level.
- Spacing
  - Put one blank line between headings, paragraphs, lists, tables and code blocks.
  - End every file with one newline.
- Lists
  - Number a list with `1.` only when order matters, and use `-` otherwise.
  - Keep each item to one point, and move details, cases and examples into nested items.
  - Make the items of one level all sentences or all phrases, and end only sentences with a period.
- Tables
  - Use a table only to compare items of one kind across attributes.
  - Write tables in compact style, with one space inside each pipe and `| --- |` delimiters.
  - Keep cells to phrases without periods, and put longer explanations in a paragraph below the table.
  - State the row order rule above the table when it is not obvious.
- Code
  - Use inline code for paths, file names, properties and values.
  - Put multi-line examples in fenced code blocks with a language, after a sentence that says what they show.
- Links
  - Link vault notes with wikilinks and external sources with `[name](URL)`.
- Emphasis
  - Use callouts for warnings and questions.
  - Do not use bold or italic.
- Checking
  - Check formatting with `npx markdownlint-cli2 "**/*.md"`, configured in `.markdownlint.jsonc` with ignored paths in `.markdownlint-cli2.jsonc`.
  - `wiki/.markdownlint.jsonc` turns off MD041, because vault notes have no `#` heading.
  - The statute note folders also turn off MD029, MD030 and MD052, which statute text trips with its 호 numbers and bracketed notes, and MD033 and MD045 for the image text kept in comments.

### Scripts

- Run Python with `uv run python -X utf8`.
  - Without UTF-8 mode, Python on Windows reads Korean files as CP949.
- Write files in UTF-8 with LF line endings.
- Keep every script check reproducible with the fixture notes in `tests/fixtures/`.
  - Run the tests with `uv run python -X utf8 -m pytest`.
- Enable the pre-commit hook with `git config core.hooksPath .githooks` in every clone.
  - It runs `scripts/secret_scan.py`, which rejects staged files that contain `.env` values.

### Commits

- Commit each unit of work on `main`.
