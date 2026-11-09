# 구현 구조

## 원문에서 지식까지

| 기능 | 처리 내용 | 구현 파일 |
| --- | --- | --- |
| 원문 수집 | 법제처 API 응답·첨부파일·시행 버전 저장 및 수집 결과 검사 | [collect.py](../scripts/collect.py), [sources.yaml](../scripts/sources.yaml) |
| 스키마 정의 | LinkML 클래스·속성·표준 IRI 정의 | [schema.yaml](../ontology/schema.yaml) |
| 조문 생성 | 법령·조문 노트 및 조·항·호 인용 블록 생성, 버전 기록 | [statutes.py](../scripts/statutes.py) |
| RDF 변환·검증 | 위키·원문 메타데이터를 LinkML 데이터로 구성하고 RDF로 변환·검사 | [vault.py](../scripts/vault.py) |
| 검증 원장 | 검증 에이전트용 맥락 구성, 내용·인용 해시 및 검증 정보 기록 | [verify.py](../scripts/verify.py) |
| 위임 관계 | 법제처 위임조문 데이터의 `basedOn` 관계 변환 | [statutes.py](../scripts/statutes.py) |
| 판례 수집 | 대법원 판례 8건 수집 및 인용 보존 | [collect.py](../scripts/collect.py)의 `precedents` |

`raw/`는 수집한 원문, `wiki/`는 인스턴스 지식, `ontology/schema.yaml`은 LinkML로 정의한 지식 구조이다. 원문의 조문 생성은 스크립트, 요건·해석·관계의 작성과 대조는 LLM 및 검증 에이전트가 담당한다.

Ingest·Query·Lint를 반복해 지식을 구축하고 관리한다. Ingest는 원문 수집과 지식 반영, Query는 근거를 연결한 질의, Lint는 위키의 인용·규칙·구조 검사이다.

## 웹 실행

1. [export_view.py](../scripts/export_view.py)가 `wiki/`의 각 파일을 노드로, frontmatter의 관계를 간선으로 내보낸다. 출력은 `view/data/vault.json`이다.
2. [scenario.js](../view/scenario.js)가 선택한 이직일로 규정·상한액을 결정하고 여섯 단계의 실행 기록을 만든다. 현재 예제에서 정의한 노드 ID와 관계를 사용한다.
3. [model.py](../view/model.py)의 `resolve`가 서버에서도 날짜 조건과 계산을 수행한다. `explain`은 계산 결과와 선택된 법령 발췌 4개를 언어 모델에 한 번 전달한다.
4. 응답의 `cap`이 계산값과 같은지, `evidenceIds`가 전달한 근거의 부분집합인지, 설명의 형식이 맞는지 검사한다. 설명 문장의 의미 전체를 자동 검증하는 구현은 아니다.
5. [app.js](../view/app.js)가 결과를 표시한다. [evidence-flow.js](../view/evidence-flow.js)의 빛 이동은 이미 요청에 포함한 근거와 그래프 노드의 연결을 나타낸다.

RDF는 검증과 SPARQL 질의에 사용한다. 웹의 데이터는 위키에서 별도로 생성한 JSON이며, 화면이 RDF 저장소에 질의하지 않는다. 그래프의 단계별 이동은 언어 모델의 사고 과정이나 자유질문 검색 기록이 아니다. 자유질문을 추가하려면 실제 검색·판정 과정에서 노드 ID와 실행 이벤트를 생성해야 한다.

NVIDIA 스트림에서 추론·내용 토큰의 도착 여부를 관측해 처리 상태를 표시한다. 추론 본문은 버리고, 답변은 완성된 JSON의 금액·근거 ID 검사를 마친 뒤 표시한다.

## 수치의 정의

| 수치 | 집계 기준 |
| --- | --- |
| 법령 19개 | `sources.yaml`의 핵심 법령 6개와 참조 법령 13개. 시행 버전 수와 구분 |
| 행정규칙 19종 | 설정의 행정규칙 수집 항목. 연도별·시행일별 원문 파일 수와 구분 |
| 노드 1,371개 | 위키 파일과 일대일 대응. 지식 노트 755개 + 생성된 법령·하위 단위 노트 616개 |
| 관계 7,898개 | 출발 노드·도착 노드·관계 속성·인용 anchor의 조합으로 중복 제거. RDF 전체 triple 수와 구분 |
| 조문 171/171개 | 수집 설정의 구축 범위와 위임 관계로 정한 대상 조문에 대한 인용 여부 |
| 역량 질문 24개 | 등록된 SPARQL 질의 실행과 기대 답에 적힌 근거 조문의 연결 검사 |

## 검증의 범위

[vault.py](../scripts/vault.py)는 LinkML, 자체 생성 SHACL, CPSV-AP·CCCEV의 공식 SHACL shape을 검사한다. 법령이 정한 당사자 유형은 특정 개인·기관 인스턴스가 아니므로 `Participation.hasParticipant`의 필수값 누락을 문서화한 예외로 처리한다. [스키마의 적용 예외](../ontology/schema.md#classes)

[cq.py](../scripts/cq.py)는 구조 검사를 통과한 RDF에 24개 질의를 실행하고 기대 답의 근거 연결을 확인한다. 모든 자연어 질문에 대한 LLM 답변 정확도를 측정하는 벤치마크는 아니다. [scenarios.md](scenarios.md)에 이용 시나리오 3개가 있으나 자동 단계 연결 검사가 대상으로 삼는 것은 `sc-01`이다.

`verified`는 생성기 또는 별도 에이전트의 검증 상태이다. 사람의 최종 승인인 `reviewed`와 구분하며, `verified`에도 공개 출처로 결론을 내리지 못한 질문이 남을 수 있다. [검토 상태의 정의](../CLAUDE.md#review) · [미해결 질문 처리 결정](decisions.md)

## 재현

```sh
uv run python -X utf8 scripts/cq.py
uv run python -X utf8 scripts/coverage.py
uv run python -X utf8 scripts/lint.py
uv run python -X utf8 scripts/export_view.py --check
```

최초 클론에서는 공개 원문·위키와 저장된 그래프로 탐색 화면과 역량 질문 검사를 실행할 수 있다. `lint.py`의 저장소 전체 검사에는 원문 생성 재현이 포함되므로, 커밋하지 않는 과거 버전의 로컬 캐시가 필요한 경우가 있다. 원문 수집을 다시 실행하려면 `.env`에 `LAW_OC`를 설정한다. 언어 모델 호출에는 별도의 NVIDIA 키가 필요하다.
