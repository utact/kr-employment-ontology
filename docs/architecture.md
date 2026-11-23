# System architecture

## Knowledge base construction

| 기능 | 처리 내용 | 구현 파일 |
| --- | --- | --- |
| 원문 수집 | 법제처 API 응답·첨부파일·시행 버전 저장과 수집 결과 검사 | [collect.py](../scripts/collect.py), [check_raw.py](../scripts/check_raw.py) |
| 조문 생성 | 법령·조문 노트, 조·항·호 블록, 버전, 인용·위임 관계 생성 | [statutes.py](../scripts/statutes.py) |
| schema | LinkML class와 property의 표준 IRI | [schema.yaml](../ontology/schema.yaml) |
| RDF 변환·검증 | wiki를 RDF로 변환하고 LinkML·SHACL로 검사 | [vault.py](../scripts/vault.py) |
| 인용 검사 | 인용문·숫자·날짜·관계·구조 검사 | [lint.py](../scripts/lint.py) |
| 검증 원장 | 검증 agent에 노트와 인용 근거 제공, 노트와 근거의 hash 기록 | [verify.py](../scripts/verify.py) |
| 역량 질문 | SPARQL 질의로 기대 답의 근거 연결 확인 | [cq.py](../scripts/cq.py), [competency-questions.md](competency-questions.md) |

법령 조문은 스크립트가 생성하고, 요건·해석·관계는 LLM이 원문을 인용해 쓴다. 별도 검증 agent가 각 문장을 인용 블록과 대조한 뒤 `verified`로 바꾼다. `verified` 노트에도 공개 출처로 풀리지 않는 질문은 question callout으로 남는다.

예를 들어 [기초일액 상한](../wiki/Constraint/기초일액%20상한.md)은 금액 제한을 이직일 조건에 `appliesWhen`으로 연결한다. `source`는 상한의 근거 조문과 경과조치를 가리킨다. 전자는 어떤 조건을 함께 살펴볼지, 후자는 원문 어디에서 확인할지를 알려 준다.

## Source updates

질문을 받기 전에 원문을 수집해 노트에 연결한다. 원문과 vault 버전을 보존하면 평가에 쓴 자료를 다시 대조할 수 있다. 법령 데이터에 MCP로 접근해 상담 시점에 원문을 조회하는 방식도 가능하다. 이 저장소의 자유질문 경로는 로컬 자료를 읽는다. [MCP의 도구와 리소스](https://modelcontextprotocol.io/docs/learn/architecture)

새 공포가 있으면 시행예정본도 다시 수집한다. vault 기준일을 바꿀 때는 조문 노트를 다시 생성하고 인용 근거가 바뀐 지식 노트를 재검증한다. 수집기를 언제 실행할지는 운영자가 정한다. 상담일이 vault 기준일보다 늦어도 자유질문 경로는 그 사이의 개정을 원격으로 확인하지 않는다. [원문 수집 기준](../ontology/sources.md#raw-sources) · [기준일](../ontology/release.yaml)

## Question answering

[ask.py](../scripts/ask.py)가 질문에 답한다.

1. 모델이 노트 목록에서 출발 개념을 고르고 질문의 일상어를 법령 용어로 바꾼다.
2. 글자 두 개 단위의 BM25 검색으로 출발 노트를 보탠다.
3. 모델이 고른 노트를 우선 유지하고, 관계와 역방향 링크를 따른 personalized PageRank 순위로 나머지를 채운다.
4. 선택한 노트가 인용한 조문에서 적용할 시행본의 항·호·목을 가져온다.
5. 모델이 조건과 원문을 읽고 근거를 붙여 답한다. 코드는 인용문과 숫자를 검사한다.

검색 단위는 지식 노트이고 답변의 인용 단위는 조문 블록이다. 상위 블록을 인용하면 그 아래 호·목도 전달한다. 검색기는 embedding이나 벡터 유사도를 사용하지 않는다. 관계별 가중치는 검색 순위에 반영한다. 자유질문에서 조건의 충족 여부를 일괄 판정하는 규칙 엔진은 구현하지 않았다.

조회 기준은 질문에서 확인한 이직일이다. 이직일을 확인할 수 없으면 상담 기준일을 쓴다. 노트에 해당 시행본이 없으면 수집 원문에서 찾는다.

판례·법령해석례·고용24 안내의 인용문은 `raw/`에 둔다. 지식 노트의 설명은 모델에 전달되지만, 검색기는 `wiki/` 안의 노트만 색인한다. 따라서 `raw/` 인용 블록을 직접 가리키는 링크는 답변에 쓸 근거 블록에서 빠진다.

[llm.py](../scripts/llm.py)는 모델 호출을 맡는다. [bench_qa.py](../scripts/bench_qa.py)는 vault 유무의 답을 같은 질문으로 비교하고, 외부 상담 서비스와 대조할 입력을 고정한다. [평가 절차](evaluation-protocol.md)

## Demo

[export_view.py](../scripts/export_view.py)는 wiki를 그래프 JSON으로 내보낸다. 화면은 이직일에 맞는 규정으로 구직급여 상한액을 계산한다. 그래프에는 규칙을 적용한 순서가 나타난다.

서버의 [model.py](../view/model.py)도 같은 규정으로 상한액을 계산한다. 모델은 계산 결과와 법령 발췌를 바탕으로 설명을 작성한다. 서버는 설명의 금액과 근거 ID를 검사한 뒤 화면에 보낸다. [화면 설명](../view/README.md)

## Validation

[vault.py](../scripts/vault.py)는 LinkML, 자체 SHACL, CPSV-AP·CCCEV 공식 SHACL을 검사한다. 법령이 정한 당사자 유형은 특정 개인·기관이 아니므로 `Participation.hasParticipant` 누락을 문서화한 예외로 둔다. [schema의 적용 예외](../ontology/schema.md#classes)

역량 질문 검사는 지정한 범위의 근거 연결을 확인할 뿐, 자연어 질문에 대한 답변 정확도를 재지 않는다. 답변 정확도는 [평가 절차](evaluation-protocol.md)로 따로 잰다.
