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

## Question answering

[ask.py](../scripts/ask.py)가 질문에 답한다.

1. 모델이 지식 노트 목록에서 질문과 관련된 노트를 고른다.
2. bigram BM25로 시작 노트를 보태고, personalized PageRank로 연결 노트를 넓힌다.
3. 적용할 날짜의 조문 시행본을 찾는다.
4. 모델이 근거 번호를 붙여 답한다.
5. 답에 쓴 숫자를 근거 원문과 대조한다.

조회 기준은 질문에서 확인한 이직일이다. 이직일을 확인할 수 없으면 상담 기준일을 쓴다. 노트에 해당 시행본이 없으면 수집 원문에서 찾는다.

[llm.py](../scripts/llm.py)는 모델 호출을 맡는다. [bench_qa.py](../scripts/bench_qa.py)는 vault 유무의 답을 같은 질문으로 비교하고, 외부 상담 서비스와 대조할 입력을 고정한다. [평가 절차](evaluation-protocol.md)

## Demo

[export_view.py](../scripts/export_view.py)는 wiki를 그래프 JSON으로 내보낸다. 화면은 이직일에 맞는 규정으로 구직급여 상한액을 계산한다. 그래프에는 규칙을 적용한 순서가 나타난다.

서버의 [model.py](../view/model.py)도 같은 규정으로 상한액을 계산한다. 모델은 계산 결과와 법령 발췌를 바탕으로 설명을 작성한다. 서버는 설명의 금액과 근거 ID를 검사한 뒤 화면에 보낸다. [화면 설명](../view/README.md)

## Validation

[vault.py](../scripts/vault.py)는 LinkML, 자체 SHACL, CPSV-AP·CCCEV 공식 SHACL을 검사한다. 법령이 정한 당사자 유형은 특정 개인·기관이 아니므로 `Participation.hasParticipant` 누락을 문서화한 예외로 둔다. [schema의 적용 예외](../ontology/schema.md#classes)

역량 질문 검사는 지정한 범위의 근거 연결을 확인할 뿐, 자연어 질문에 대한 답변 정확도를 재지 않는다. 답변 정확도는 [평가 절차](evaluation-protocol.md)로 따로 잰다.
