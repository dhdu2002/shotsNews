# Daily Issue Desktop MVP (비UI 파이프라인)

`src/daily_issue_app`에는 로컬 실행 가능한 MVP 파이프라인이 포함되어 있습니다.
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

## 비UI 파이프라인 실행

`config/app.example.env`를 참고해 환경변수를 설정한 뒤 실행합니다.

```bash
python scripts/run_desktop.py
```

## UI 연동 진입점

- `DesktopApp.run_now()`
- `DesktopApp.status()`
- `DesktopApp.start()` / `DesktopApp.stop()`
