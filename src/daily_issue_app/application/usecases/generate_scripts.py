"""유스케이스: 저장된 이슈의 3톤 스크립트 생성."""

from __future__ import annotations

from ..dto import PersistIssuesResult
from ...domain.interfaces import IssueRepositoryPort, ScriptGeneratorPort


class GenerateScriptsUseCase:
    """이슈별 스크립트를 생성하고 저장한다."""

    def __init__(self, generator: ScriptGeneratorPort, repository: IssueRepositoryPort) -> None:
        self._generator = generator
        self._repository = repository

    def execute(self, persisted: PersistIssuesResult) -> None:
        """저장된 이슈 목록에 대해 스크립트를 생성한다."""
        scripts = [self._generator.generate(issue) for issue in persisted.records]
        self._repository.save_scripts(scripts)
