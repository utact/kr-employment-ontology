# 자유질문 평가 절차

챗봇의 답을 볼트 없는 같은 모델의 답, 그리고 고용노동부 AI 노동법 상담의 답과 비교한다. 입력과 채점 자료는 Git에서 제외한 `docs/evaluation/`에 둔다.

## 순서

1. 볼트 유무 양쪽의 답을 같은 질문으로 받고, 결론·조건·행동이 갈리는 문항을 고른다.
2. 틀린 문항마다 공식 원문, 위키 서술, 모델에 넘긴 근거, 답을 차례로 대조해 처음 어긋난 곳을 고친다. 고친 뒤 같은 질문과 조건 하나만 바꾼 질문으로 전후를 비교한다.
3. 고른 문항을 AI 노동법 상담에 직접 입력하고 첫 응답을 그대로 저장한다. 자동화하지 않는다.
4. 답의 출처를 가리고, 당시 시행 중인 공식 자료로 양쪽을 채점한다.

## 실행

질문 파일은 UTF-8 JSONL이며 각 행에 `id`, `as_of`, `question`이 있다.

```sh
uv run python -X utf8 scripts/bench_qa.py preview docs/evaluation/inputs.jsonl docs/evaluation/trial-01 --context historical --ids case-1
uv run python -X utf8 scripts/bench_qa.py freeze docs/evaluation/trial-01 docs/evaluation/fixed.json --ids case-1
uv run python -X utf8 scripts/bench_qa.py message docs/evaluation/fixed.json case-1
uv run python -X utf8 scripts/bench_qa.py blind docs/evaluation/fixed.json docs/evaluation/responses.jsonl docs/evaluation/grading-01
```

- `preview`: 볼트 유무 양쪽의 첫 응답을 입력, 상담일, 모델 설정, 코드·위키 지문과 함께 저장한다. `--context historical`은 과거 상담일 안내를 질문에 붙이고, `live`는 붙이지 않는다.
- `freeze`: 검토를 마친 문항의 입력과 응답을 고정한다.
- `message`: AI 노동법 상담에 붙여 넣을 문장을 출력한다.
- `blind`: 외부 응답(`responses.jsonl`의 `id`, `sent`, `first_response`)과 챗봇 답을 A/B로 섞어 `answers.json`에, 배정표를 `key.json`에 따로 쓴다.

## 채점

- 자격, 금액, 기한, 신청 경로처럼 상담자의 행동을 바꾸는 쟁점별로 채점한다.
- 결론에 필요한 사실이 질문에 없으면 되물음도 맞는 응답으로 본다.
- 1350 게시 답변과 모델의 자동 판정은 정답으로 쓰지 않는다.
- 질문의 표현은 바꾸지 않는다. 같은 사례의 여러 표현은 한 건으로 센다.
- 문항, 채점 기준, 제품 버전은 결과를 보기 전에 정한다. 개발에 쓴 문항으로 얻은 결과는 그 문항에 한해 보고한다.
