# shotsNews MVP

`src/daily_issue_app`에는 로컬 실행 가능한 데스크톱 MVP 파이프라인이 포함되어 있습니다.
SQLite 영속화, 소스 수집, Top-5 랭킹, 3톤 스크립트 생성, Notion 동기화 큐, APScheduler 기반 주기 실행이 코어 계층에 연결되어 있습니다.

## 구현된 MVP 인프라

- RSS 우선 수집 + 카테고리 키워드 필터링
- Reddit/YouTube(피드 URL)/Twitter(X, 선택형) 수집기
- `MultiSourceCollector` 기반 소스 실패 격리
- Top-5 랭킹 (`APP_TOP_K`)
- OpenAI 우선 스크립트 생성 (키 미설정 시 로컬 대체 문구)
- 실행 이력/이슈/스크립트/소스 실패/Notion 큐를 포함한 SQLite 스키마
- 자격정보 부재 시 안전하게 동작하는 Notion 동기화
- APScheduler 기반 런타임 스케줄링
- `DailyIssuePipeline` 중심의 엔드투엔드 실행 경로

## 빠른 시작

1. 의존성 설치

```bash
python -m pip install -r requirements.txt
```

2. 환경파일 준비

- `config/app.example.env`를 `config/app.env`로 복사
- 필요하면 `config/source_pools.example.json`을 `config/source_pools.json`으로 복사
- 또는 루트 `.env` 파일 생성

이제 앱은 `config/app.env` 또는 `.env`를 자동으로 읽고, 있으면 `config/source_pools.json`도 함께 읽습니다.

`source_pools.json`은 카테고리별 RSS/YouTube/Reddit/Twitter(X) 소스 풀을 선택적으로 덮어쓰는 파일입니다.
파일이 없거나 특정 카테고리/소스가 비어 있으면 기존 환경변수 기반 공용 소스를 fallback으로 사용합니다.

3. 실행

```bash
python scripts/run_desktop.py
```

## 상세 설정 가이드

- `docs/setup.md`

## UI 연동 진입점

- `DesktopApp.run_now()`
- `DesktopApp.status()`
- `DesktopApp.start()` / `DesktopApp.stop()`
