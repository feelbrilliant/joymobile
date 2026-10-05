# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 참고하는 안내 문서입니다.

## 프로젝트 개요

저장소는 두 부분으로 나뉩니다.

1. **리다이렉트 페이지** (`index.html`)
   방문자를 공식 개통 페이지 `https://www.n-telecom.co.kr/joymobile` 로 1초 후 자동 이동시킵니다.
2. **네이버 블로그 자동화** (`blog/`)
   조이모바일 공식 네이버 블로그 글을 주제 선정부터 스마트에디터 입력까지 자동으로 준비합니다.
   발행 버튼은 사람이 직접 누릅니다. 자세한 구성은 `blog/README.md` 참고.

## 리다이렉트 페이지 (`index.html`)

- 빌드 도구, 패키지 매니저, 테스트, 린터 없음 — 순수 정적 HTML, 한국어(`lang="ko"`, UTF-8)
- `<meta http-equiv="refresh" content="1; url=...">` 로 자동 이동하고, 자동 이동이 안 될 때를 위한 수동 링크를 둡니다
- 스타일은 `<body>` 인라인 `style` 속성으로만 지정
- 이동 대상 URL을 바꿀 때는 `<meta http-equiv="refresh">` 의 `url=` 값과 `<a href>` 두 곳을 **반드시 함께** 수정할 것
- 이 페이지에는 별도 CSS/JS 파일이나 외부 의존성을 추가하지 말 것
- 확인: 브라우저에서 `index.html` 을 열어 1초 뒤 이동하는지, 수동 링크가 같은 주소인지 확인

## 블로그 자동화 (`blog/`)

- Python 3.10+, 의존성은 `blog/requirements.txt` (`anthropic`). 사용자는 Windows에서 `blog/run.bat` 으로 실행
- 테스트: `cd blog && python -m unittest discover -s tests -t .`
- 실행 확인(API 호출 없음): `cd blog && python run.py --id 24 --from-file <초안.txt> --no-open`
- 코드는 `blog/joyblog/` (topics → prompt → generate → post → check → render), 진입점은 `blog/run.py`
- 글 작성 규칙은 `blog/prompts/system.md` 가 기준입니다. 규칙을 바꿀 때 이 파일을 고칩니다
- 요금제 가격·제공량은 `blog/data/plans.json` 에만 둡니다. 프롬프트나 코드에 숫자를 직접 적지 말 것
- `blog/data/topics.csv` 의 `제목` 은 발행 제목 그대로 쓰입니다. 생성된 글에서 제목을 바꾸지 말 것
- 프로그램으로 확인할 수 있는 규칙(글자 수, 키워드 횟수, 금지 표현 등)은 `blog/data/rules.json` 에 둡니다
- 자동화는 스마트에디터에 글을 채우고 임시저장하는 데서 멈춥니다. **발행 버튼을 누르는 코드는 만들지 말 것**
- 네이버 아이디·비밀번호를 코드나 파일에 저장하지 말 것. 로그인은 사람이 브라우저에서 직접 합니다

## 공통

- 사용자에게 보이는 문구는 한국어로 작성할 것
