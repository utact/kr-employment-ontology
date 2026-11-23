# Unemployment benefit demo

구직급여 하루 상한액 예제에서 AI 노동법 상담의 수집 응답, 지식 그래프, 언어 모델의 설명을 나란히 보여 준다. 이직일을 고르면 그날 적용되는 규정과 계산을 그래프 위에서 차례로 짚는다.

## Local setup

```sh
uv run python -X utf8 view/serve.py
```

[로컬 예제 화면](http://127.0.0.1:8765/view/)을 연다. 서버는 `127.0.0.1`에서 `view/`만 제공한다. wiki가 바뀌면 `uv run python -X utf8 scripts/export_view.py`로 `data/vault.json`을 갱신한다.

## Model configuration

`.env`의 `LLM_PROVIDER`로 설명을 생성할 모델을 고른다. 기본 모델은 NVIDIA Nemotron 3 Ultra다. Gemini를 쓰려면 `gemini`로 설정한다. API 키는 서버에서만 읽는다.

서버는 질문, 계산 결과, 법령 발췌 4개를 모델에 보낸다. 응답의 금액과 근거 ID를 검사한 뒤 설명을 표시한다. 요청이 실패하면 화면에 오류를 표시한다.

## Baseline responses

2026-11-09에 고용노동부·한국공인노무사회의 [AI 노동법 상담](https://ai.moel.go.kr/llc/labor-law-chat)에서 질문마다 새 대화를 열었다. [원본 기록](data/captures/)에는 응답과 표시 시점이 담겨 있다. [생성 스크립트](../scripts/build_baseline.py)가 이 기록에서 [화면용 데이터](data/baseline-responses.json)를 만든다.

두 질문 모두 해당 서비스는 66,000원이라고 답했다. 상한액은 [고용노동부의 시행령 개정 안내](https://www.moel.go.kr/news/enews/report/enewsView.do?news_seq=18736)와 [1350 상담 답변](https://1350.moel.go.kr/rtmview.do?id=1000324861)으로 교차 확인했다. 응답 시간은 질문별 1회 화면 관측값이라 서비스 성능 비교에 쓰지 않는다.

종전 시행령 제68조는 `data/historical-cap.json`의 법제처 응답 발췌를 쓴다.

## Visual assets

한반도의 노드 크기와 밝기는 [WorldPop의 2020년 인구 추정치](https://doi.org/10.5258/SOTON/WP00840)에 따른다. 출처는 WorldPop, University of Southampton, Bondarenko et al. (2025), Global2 R2025A v1이며 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)에 따라 가공했다. 집계값과 원본 URL·hash는 `assets/brand-population.json`에 있고, `scripts/build_brand.py`가 SVG를 만든다.

시작 화면 지구본의 대륙은 [Natural Earth 1:110m land](https://www.naturalearthdata.com/about/terms-of-use/)(public domain)이며, `scripts/build_intro.py`가 `assets/intro-geometry.json`을 만든다. 공식 로고와 상담 아이콘의 원본 URL은 `assets/sources.json`에 있다.

## Validation

```sh
uv run python -X utf8 scripts/export_view.py --check
uv run python -X utf8 -m pytest tests/test_view.py
npm test --prefix view
```
