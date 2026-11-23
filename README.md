# Korean Employment Ontology

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB)](pyproject.toml)
[![Obsidian](https://img.shields.io/badge/Obsidian-7C3AED)](index.md)
[![LinkML](https://img.shields.io/badge/LinkML-2563EB)](ontology/schema.yaml)
[![SHACL](https://img.shields.io/badge/SHACL-176B50)](ontology/shapes/README.md)

이직한 근로자를 위한 실업급여 상담 챗봇을 개발한다. 구직자가 자신의 상황을 질문하면 수급 조건과 예상 금액, 다음 신청 절차를 근거와 함께 안내한다.

- 질문만으로 결론을 낼 수 있으면 결론과 적용 근거부터 설명한다.
- 사실이 부족하면 확인된 부분까지 설명하고, 결론을 바꿀 사실만 되묻는다.
- 근거가 부족하면 판단을 보류한다. 질문 전체가 이직·실업급여와 무관하면 상담 범위를 안내한다.

검증할 질문은 두 가지다. 고용보험 지식을 정리한 vault가 같은 언어 모델의 답을 개선하는가? 그 챗봇은 구직자의 질문에 고용노동부 AI 노동법 상담보다 정확하고 이해하기 쉽게 답하는가?

## Motivation

하루 8시간 일한 일용근로자의 구직급여 일액 상한을 이직일만 바꿔 [고용노동부 AI 노동법 상담](https://ai.moel.go.kr/)에 물었다.

| 이직일 | AI 노동법 상담 응답 | 적용 규정에 따른 상한액 |
| --- | ---: | ---: |
| 2026-09-30 | 66,000원 | 68,100원 |
| 2025-12-31 | 66,000원 | 66,000원 |

2026-01-01부터 고용보험법 시행령 제68조제1항의 기초일액 상한은 113,500원이고, 법 제46조제1항제1호의 지급 비율 60%를 곱하면 68,100원이다. 부칙 제35934호 제4조는 시행 전 이직자에게 종전 규정을 적용한다. [1350 상담 안내](https://1350.moel.go.kr/rtmview.do?id=1000324861)도 두 상한액과 적용 시점을 밝힌다. 두 응답은 2026-11-09에 수집했다. [수집 기록](view/README.md#baseline-responses) · [비교 영상](https://github.com/user-attachments/assets/2c39a92c-2c16-4051-8402-d00298c80bdd)

이 사례에서 결론을 가른 것은 이직일과 경과조치다. 그래서 계산 규칙을 적용 조건과 함께 보관한다. 다만 범용 모델이 스스로 맞힐 수 있는 질문이라면 챗봇이 맞혀도 vault의 기여는 알 수 없다. 같은 모델이 같은 질문에 어떻게 다르게 답하는지부터 비교하는 이유다.

## Architecture

```mermaid
flowchart LR
    A["원문 · raw/"] -->|조문 생성·지식 작성| B["지식과 인용 · wiki/"]
    S["LinkML schema"] -.->|구조 정의| B
    B --> C["RDF 변환·검증"]
    B --> D["질문별 근거 검색"]
    D --> E["답변 생성·인용 검사"]
```

Ontology는 급여·수급 요건·증빙이 어떤 조문에 근거하는지 표현한다. LLM Wiki는 이 지식을 Obsidian vault에 축적하고 갱신하는 방식이다. 스크립트가 조문 노트를 생성하면 LLM이 근거를 인용해 지식 노트를 연결한다. 별도 검증 agent가 노트와 원문을 대조한다. [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) · [운영 규칙](AGENTS.md)

자유질문에는 그래프 기반 RAG(retrieval-augmented generation)를 쓴다. 모델이 질문을 지식 노트에 연결하고 BM25 어휘 검색이 출발 노트를 보탠다. Personalized PageRank로 연결된 노트의 순위를 매긴 뒤, 선택한 노트가 인용한 시행본의 조문과 원문 발췌를 모델에 전달한다. 예를 들어 상한액을 물으면 금액 제한과 이직일 조건을 함께 찾을 수 있다. 어떤 조건이 질문자에게 적용되는지는 모델이 근거를 읽고 판단한다. 상한액 데모에서는 서버가 직접 계산한다. [검색과 답변 생성](docs/architecture.md#question-answering)

Competency questions는 ontology가 답할 수 있어야 하는 질문이다. 예를 들어 피보험자격 확인을 누가 청구하고 어디에 제출하는지 묻는다. 법령과 서식에서 기대 답을 정하고 SPARQL로 노트와 근거의 연결을 검사한다. 실제 상담 문장으로 생성한 답은 1350 벤치마크에서 따로 평가한다. [Ontology Development 101](https://protege.stanford.edu/publications/ontology_development/ontology101-noy-mcguinness.html) · [역량 질문](docs/competency-questions.md)

## Evaluation

구직자의 실제 질문에서 vault가 답변을 개선하는지 확인하려고 1350 공개 상담을 수집했다. 2026-11-19 수집본 390건 중 질문이 아닌 1건을 제외하고 389건을 비식별 재서술했다. 모델에 제공하는 사례 정보는 질문과 상담 기준일이다. 게시 답변은 별도로 보관한다. [1350 공개 상담](https://1350.moel.go.kr/rtmlist.do)

같은 법적 쟁점의 다른 사례에도 답할 수 있는지 평가하려고 관련 조문이나 장·절을 기준으로 사례를 나눴다. development set은 272건, test set은 117건이다. 중복·후속 질문은 원래 상담과 같은 쪽에 배정했다.

1. development set에서 같은 모델의 응답을 vault 유무에 따라 비교한다.
2. 결론·적용 조건·다음 행동이 달라진 사례부터 오류를 찾아 고친다.
3. test set의 같은 질문으로 개선한 챗봇과 AI 노동법 상담의 답을 비교한다.

두 답이 일치한 사례도 외부 비교를 위해 보관한다. 정오는 사건 당시의 법령과 공식 자료를 대조해 사람이 검토한 기준 답안으로 판단한다. 필요한 근거를 찾았는지, 근거 밖의 내용이 섞였는지, 구직자가 이해하기 쉽게 답했는지도 평가한다.

주 점수는 이직한 근로자의 급여 상담에 대해 산출한다. 특례와 범위 밖 질문은 별도로 집계한다. 중복·후속 질문과 개선에 활용한 사례는 독립 평가 점수에서 제외한다.

2026-11 개발 사례 분석에서 두 응답을 비교한 234건 중 207건은 두 차례의 검토 모두 답변에 차이가 있다고 판정했다. 어느 쪽이 더 정확한지는 이 수치로 알 수 없다. 사람이 검토한 기준 답안으로 독립 평가한 결과는 아직 없다. [평가 절차와 채점 기준](docs/evaluation-protocol.md)

## Data and schema

| 자료 | 수집 경로 |
| --- | --- |
| 법률·시행령·시행규칙 | 법제처 공동활용 API |
| 행정규칙 | 법제처 공동활용 API |
| 대법원 판례, 법령해석례 | 법제처 공동활용 API |
| 고용24 안내 | 안내 웹페이지 |

현행·시행예정 원문과 경과조치 판단에 필요한 과거 버전을 보존한다. 질문에는 로컬에 저장한 시행본으로 답한다. 운영자가 기간을 지정해 조회하면 도구가 등록된 법령의 공포와 행정규칙의 발령을 추린다. 상담에 영향을 주는 개정은 원문 수집과 검증을 거쳐 vault에 반영한다. [수집 목록](scripts/sources.yaml) · [vault 기준일](ontology/release.yaml) · [조회 범위와 갱신 방식](docs/architecture.md#source-updates)

공공서비스는 CPSV-AP 3.2.0, 요건·증빙은 CCCEV 2.1.0, 법령과 버전은 ELI 1.4로 모델링한다. 개념 분류는 SKOS, 출처는 PROV-O로 표현하며, class와 property는 [LinkML schema](ontology/schema.yaml)에 정의한다. [schema 문서](ontology/schema.md)

## Quick start

Python 3.12 이상과 [uv](https://docs.astral.sh/uv/)가 필요하다.

```sh
git clone https://github.com/utact/kr-employment-ontology.git
cd kr-employment-ontology
uv sync --frozen
```

질문에 답하려면 `.env.example`을 `.env`로 복사하고 언어 모델 설정을 채운다. `--as-of`로 상담 기준일을 지정한다. [시행본 선택](docs/architecture.md#question-answering)

```sh
uv run python -X utf8 scripts/ask.py answer "2025년 12월 31일에 퇴사한 일용근로자의 구직급여 하루 상한액은?" --as-of 2026-01-15 --provider nvidia --format text
```

`uv run python -X utf8 view/serve.py`를 실행한 뒤 [로컬 예제 화면](http://127.0.0.1:8765/view/)을 연다. [화면 설명](view/README.md)

검사는 다음 명령으로 실행한다. 원문을 다시 수집하려면 `.env`에 `LAW_OC`가 필요하다.

```sh
uv run python -X utf8 scripts/lint.py
uv run python -X utf8 scripts/cq.py
uv run python -X utf8 scripts/coverage.py
uv run python -X utf8 -m pytest
```

## License

코드는 [MIT License](LICENSE)를 따른다. 수집 원문, 표준과 시각 자산의 이용 조건은 각 출처 표기를 따른다. [표준 출처](ontology/shapes/README.md) · [시각 자산 출처](view/README.md#visual-assets)
