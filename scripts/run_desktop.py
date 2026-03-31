"""로컬 데스크톱 런타임 실행 스크립트."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))



def _load_main() -> Callable[[], int]:
    module = import_module("src.daily_issue_app.main")
    return getattr(module, "main")


if __name__ == "__main__":
    raise SystemExit(_load_main()())
