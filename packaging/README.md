# 패키징 메모 (Windows MVP)

- 대상 런타임: Python + PySide6 데스크톱 셸
- 목표 산출물: Windows 실행 파일 (`PyInstaller` 기준)
- 메인 엔트리포인트 모듈: `daily_issue_app.main:main`
- 기본 런타임 데이터 경로: `%LOCALAPPDATA%\\DailyIssueDesktop`
- 권장 배포 형식: 초기에는 `onedir`, 안정화 후 `onefile` 검토
