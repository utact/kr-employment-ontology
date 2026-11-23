# Korean Employment Ontology

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB)](pyproject.toml)
[![Obsidian](https://img.shields.io/badge/Obsidian-7C3AED)](index.md)
[![LinkML](https://img.shields.io/badge/LinkML-2563EB)](ontology/schema.yaml)
[![SHACL](https://img.shields.io/badge/SHACL-176B50)](ontology/shapes/README.md)

이직한 근로자가 실업급여의 자격, 금액, 신청 절차를 확인할 수 있도록 돕는 챗봇이다. 고용보험 법령의 조·항·호와 시행 시점을 요건, 계산 규칙, 증빙에 연결한 ontology를 Obsidian vault에 담는다. 이 지식이 같은 언어 모델의 답을 개선하는지, 개선한 챗봇이 고용노동부 AI 노동법 상담보다 정확하고 이해하기 쉽게 답하는지를 검증한다.

## Demo

<https://github.com/user-attachments/assets/2c39a92c-2c16-4051-8402-d00298c80bdd>

하루 8시간 일한 일용근로자의 구직급여 일액 상한을 이직일만 바꿔 [고용노동부 AI 노동법 상담](https://ai.moel.go.kr/)에 물었다.

| 이직일 | AI 노동법 상담 응답 | 적용 규정에 따른 상한액 |
| --- | ---: | ---: |
| 2026-09-30 | 66,000원 | 68,100원 |
| 2025-12-31 | 66,000원 | 66,000원 |

2026-01-01부터 고용보험법 시행령 제68조제1항의 기초일액 상한은 113,500원이고, 법 제46조제1항제1호의 지급 비율 60%를 곱하면 68,100원이다. 부칙 제35934호 제4조는 시행 전 이직자에게 종전 규정을 적용한다. [1350 상담 안내](https://1350.moel.go.kr/rtmview.do?id=1000324861)도 두 상한액과 적용 시점을 밝힌다. 응답은 2026-11-09에 수집했고, 두 질문으로 서비스 전체의 정확도를 평가하지 않는다. [수집 기록](view/README.md#baseline-responses)

## Evaluation

구직자의 이직·실업급여 질문에 vault가 얼마나 도움이 되는지 실제 상담 사례로 평가하기 위해 고용노동부 고객상담센터 1350의 공개 상담을 수집했다. 2026-11-19 수집본의 관측 390건 중 질문이 아닌 1건을 제외한 389건을 비식별 재서술했다. 평가 입력에는 질문과 상담 기준일을 담고 게시 답변은 따로 보관한다. 채점 기준은 사건 당시의 법령과 공식 자료를 대조해 사람이 검토한 답안이다. [1350 공개 상담](https://1350.moel.go.kr/rtmlist.do)

1. 같은 법적 쟁점의 다른 사례에도 지식을 적용할 수 있는지 확인하기 위해 관련 조문이나 장·절을 기준으로 층화했다. 중복·후속 질문은 원래 상담과 묶어 development set 272건과 test set 117건으로 나눴다.
2. 모델별로 같은 질문에 vault를 쓰는 조건과 쓰지 않는 조건을 비교한다. development set에서 결론, 적용 조건, 다음 행동이 달라진 사례부터 기준 답안과 대조해 지식이나 답변 과정을 고친다. 두 답이 일치한 사례도 외부 비교를 위해 보관한다.
3. test set에서는 개선을 마친 챗봇과 AI 노동법 상담에 같은 질문을 입력해 비교한다. 분할 전에 개선에 활용한 사례는 독립 평가 점수에서 제외한다.

주 점수는 이직한 근로자의 급여 상담을 대상으로 한다. 특례와 범위 밖 질문은 따로 집계하고, 중복·후속 질문은 독립 점수에서 제외한다. 상담 답변은 정확성·근거 검색·근거 밖 내용의 혼입·간결성으로 평가한다. [평가 절차](docs/evaluation-protocol.md)

Competency questions는 ontology가 표현해야 할 지식 요구사항이다. 예를 들어 피보험자격 확인을 누가 청구하고 어디에 제출하는지 묻고, 법령과 서식에 근거한 기대 답을 둔다. SPARQL로 기대 답에 필요한 노트와 근거의 연결을 검사한다. [Competency questions](docs/competency-questions.md)

## Data and schema

| 자료 | 수집 경로 |
| --- | --- |
| 법률·시행령·시행규칙 | 법제처 공동활용 API |
| 행정규칙 | 법제처 공동활용 API |
| 대법원 판례, 법령해석례 | 법제처 공동활용 API |
| 고용24 안내 | 안내 웹페이지 |

현행·시행예정 원문과, 경과조치 판단에 필요한 과거 버전을 보존한다. [수집 목록](scripts/sources.yaml) · [기준일과 경과 기간](ontology/release.yaml)

공공서비스는 CPSV-AP 3.2.0, 요건·증빙은 CCCEV 2.1.0, 법령과 버전은 ELI 1.4로 모델링한다. 개념 분류는 SKOS, 출처는 PROV-O로 표현하며, class와 property는 [LinkML schema](ontology/schema.yaml)에 정의한다. [schema 문서](ontology/schema.md)

## Architecture

```mermaid
flowchart LR
    A["원문 · raw/"] -->|조문 생성·지식 작성| B["지식과 인용 · wiki/"]
    S["LinkML schema"] -.->|구조 정의| B
    B --> C["RDF 변환·검증"]
    B --> D["질문별 근거 검색"]
    D --> E["답변 생성·인용 검사"]
```

원문·지식·schema를 나눈 [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 방식이다. 법령 조문 노트는 스크립트가 원문에서 생성하고, LLM은 원문을 인용해 지식과 관계를 쓰며, 별도 검증 agent가 대조한다. [운영 규칙](AGENTS.md) · [구현 구조](docs/architecture.md)

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

예제 화면은 `uv run python -X utf8 view/serve.py`로 열고 <http://127.0.0.1:8765/view/>에서 본다. [화면 설명](view/README.md)

검사는 다음 명령으로 실행한다. 원문을 다시 수집하려면 `.env`에 `LAW_OC`가 필요하다.

```sh
uv run python -X utf8 scripts/lint.py
uv run python -X utf8 scripts/cq.py
uv run python -X utf8 scripts/coverage.py
uv run python -X utf8 -m pytest
```

## License

코드는 [MIT License](LICENSE)를 따른다. 수집 원문, 표준과 시각 자산의 이용 조건은 각 출처 표기를 따른다. [표준 출처](ontology/shapes/README.md) · [시각 자산 출처](view/README.md#visual-assets)
