# shotsNews MVP 실행 설정 가이드

## 1. 기본 설치

```bash
python -m pip install -r requirements.txt
```

## 2. 환경파일 만들기

아래 둘 중 하나를 사용합니다.

- `config/app.env`
- 프로젝트 루트 `.env`

카테고리별 소스 분리가 필요하면 아래 파일을 추가로 사용할 수 있습니다.

- `config/source_pools.json` (선택)

가장 쉬운 방법은 예시 파일 복사입니다.

```bash
copy config\app.example.env config\app.env
```

그 다음 `config/app.env` 값을 실제 값으로 수정합니다.

## 2-1. 카테고리별 source pool 파일(선택)

기본 동작은 기존과 동일하게 공용 환경변수 소스를 사용합니다.
하지만 카테고리마다 다른 수집원을 쓰고 싶다면 `config/source_pools.example.json`을 복사해서
`config/source_pools.json`을 만들면 됩니다.

```bash
copy config\source_pools.example.json config\source_pools.json
```

JSON 키는 아래 5개 카테고리를 사용합니다.

- `ai_tech`
- `economy`
- `society`
- `health`
- `entertainment_trend`

각 카테고리 안에서는 아래 소스 키를 사용할 수 있습니다.

- `rss`: RSS 피드 URL 배열
- `youtube`: YouTube 채널 피드 URL 배열
- `reddit`: subreddit 이름 배열
- `twitter`: X/Twitter 검색어 배열 또는 단일 문자열

특정 카테고리에 해당 소스 키가 없으면 기존 `app.env` 공용 값으로 자동 fallback 합니다.

## 3. 꼭 넣어야 하는 값

### OpenAI
- `OPENAI_API_KEY`

### Notion
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`
- `NOTION_ENABLED=true`

## 4. 선택 값

### Reddit
- `APP_REDDIT_SUBREDDITS`
- `APP_REDDIT_USER_AGENT`

### YouTube
- `APP_YOUTUBE_FEED_URLS`

### Twitter/X
- `TWITTER_BEARER_TOKEN`
- `TWITTER_QUERY`

토큰이 없으면 해당 소스는 자동으로 비활성처럼 동작합니다.
`source_pools.json`이 있어도 토큰이 없으면 X 수집은 실제 호출되지 않습니다.

## 5. 실행 방법

### 데스크톱 UI 실행

```bash
python scripts/run_desktop.py
```

### SQLite만 먼저 생성

```bash
python scripts/bootstrap_db.py
```

## 6. Notion 준비 체크리스트

1. Notion에서 데이터베이스 생성
2. 통합(Integration) 생성
3. 데이터베이스에 통합 연결
4. 데이터베이스 ID 확인
5. `NOTION_TOKEN`, `NOTION_DATABASE_ID` 입력
6. `NOTION_ENABLED=true` 변경

## 7. 권장 초기값

- `APP_TOP_K=5`
- `APP_SCHEDULER_INTERVAL_MINUTES=60`
- `APP_RSS_URLS`는 2~5개 정도부터 시작
- 카테고리별 source pool은 처음에는 1~2개 카테고리만 분리해서 시작
- Twitter/X는 토큰 확보 전까지 비워 두기

## 8. 문제 확인 포인트

- OpenAI 키가 없으면 실제 대본 대신 대체 문구가 나올 수 있음
- Notion 값이 비어 있으면 동기화는 건너뜀
- `config/source_pools.json` 문법이 잘못되면 앱은 조용히 공용 env 소스로 fallback 함
- Windows 콘솔에서는 일부 한글 출력이 깨져 보일 수 있으나 실행 자체와는 별개일 수 있음
