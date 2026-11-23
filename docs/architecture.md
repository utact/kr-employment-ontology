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

질문을 받기 전에 법제처 공동활용 API와 고용24 안내에서 원문을 수집해 노트에 연결한다. 원문과 vault 버전을 보존하면 평가에 쓴 자료를 다시 대조할 수 있다. 자유질문 경로는 로컬 자료를 읽는다. [법제처 API](https://open.law.go.kr/LSO/openApi/guideList.do)

운영자가 `scripts/collect.py changes 시작일 종료일`을 실행하면 양 끝 날짜를 포함한 공포·발령 목록을 API에서 조회한다. 날짜 형식은 `YYYY-MM-DD`다. 도구는 기간 내 목록을 모두 읽고 다음 항목만 출력한다. [수집 목록](../scripts/sources.yaml)

- 법령은 `laws`와 `references`에 등록된 이름으로 선별한다.
- 행정규칙은 `admrul`에 등록된 ID로 선별한다.

출력 단위는 법령·행정규칙의 시행본이다. 따라서 참조 법령인 국민연금법에서 실업급여와 무관한 조문만 바뀌어도 조회 결과에 잡힌다. 개정 조문이 상담에 영향을 주는지는 별도로 확인한다.

조회 명령은 마지막 조회일을 기록하거나 정기 실행하지 않는다. 운영자가 조회 기간을 이어서 지정하고, 관련 개정이 있으면 시행예정본을 포함해 원문을 수집한다. 기준일을 변경할 때는 조문 노트를 다시 생성하고 인용 근거가 바뀐 지식 노트를 재검증한다. 상담일이 vault 기준일보다 늦으면 답변에 자료 기준일을 표시한다. [원문 수집 기준](../ontology/sources.md#raw-sources) · [기준일](../ontology/release.yaml)

## Question answering

[ask.py](../scripts/ask.py)가 질문에 답한다.

1. 모델이 노트 목록에서 출발 개념을 고르고 질문의 일상어를 법령 용어로 바꾼다.
2. 글자 두 개 단위의 BM25 검색으로 출발 노트를 보탠다.
3. 모델이 고른 노트를 우선 유지하고, 관계와 역방향 링크를 따른 personalized PageRank 순위로 나머지를 채운다.
4. 노트마다 첫 인용 근거를 우선 담고, 남은 자리에는 질문과 어휘가 겹치는 인용 블록부터 담는다.
5. 모델이 조건과 원문을 읽고 근거를 붙여 답한다. 코드는 인용문과 숫자를 검사한다.

검색 후보는 검증된 지식 노트다. 검색기는 embedding이나 벡터 유사도를 사용하지 않는다. 예를 들어 `appliesWhen`으로 연결된 조건은 그래프에서 가까워 검색될 수 있다. 그 조건의 충족 여부는 모델이 질문의 사실과 대조해 판단한다. 관계 탐색의 효과는 출발 노트를 고정하고 PageRank를 끈 결과와 비교한다. [검색 비교 절차](evaluation-protocol.md)

조문은 항·호·목 단위로 인용한다. 상위 블록을 고르면 그 아래 호·목도 전달한다. 시행본 조회에는 질문에서 확인한 이직일을 쓰고, 확인할 수 없으면 상담 기준일을 쓴다. 노트에 해당 시행본이 없으면 수집 원문에서 찾는다. 신청일 등 다른 날짜가 적용 기준인 쟁점에서는 이 선택만으로 적용 법령이 확정되지 않는다.

선택한 노트가 판례·법령해석례·고용24 안내를 인용하면 `raw/`의 해당 인용문도 근거 후보가 된다. 원문 블록과 저장한 hash를 대조하고, 상담일 뒤에 나온 자료는 인용할 수 없게 표시한다.

[llm.py](../scripts/llm.py)는 모델 호출을 맡는다. [bench_qa.py](../scripts/bench_qa.py)는 vault 유무의 답을 같은 질문으로 비교하고, 외부 상담 서비스와 대조할 입력을 고정한다. [평가 절차](evaluation-protocol.md)

## Demo

[export_view.py](../scripts/export_view.py)는 wiki를 그래프 JSON으로 내보낸다. 화면은 이직일에 맞는 규정으로 구직급여 상한액을 계산한다. 그래프에는 규칙을 적용한 순서가 나타난다.

서버의 [model.py](../view/model.py)도 같은 규정으로 상한액을 계산한다. 모델은 계산 결과와 법령 발췌를 바탕으로 설명을 작성한다. 서버는 설명의 금액과 근거 ID를 검사한 뒤 화면에 보낸다. [화면 설명](../view/README.md)

## Validation

[vault.py](../scripts/vault.py)는 LinkML, 자체 SHACL, CPSV-AP·CCCEV 공식 SHACL을 검사한다. 법령이 정한 당사자 유형은 특정 개인·기관이 아니므로 `Participation.hasParticipant` 누락을 문서화한 예외로 둔다. [schema의 적용 예외](../ontology/schema.md#classes)

역량 질문 검사는 지정한 범위의 근거 연결을 확인할 뿐, 자연어 질문에 대한 답변 정확도를 재지 않는다. 답변 정확도는 [평가 절차](evaluation-protocol.md)로 따로 잰다.
