from pathlib import Path

import pytest


@pytest.fixture
def demo_repo(tmp_path: Path) -> Path:
    (tmp_path / "PRD.md").write_text(
        "# Demo\nBuild an API where a user can create and list notes. Persist notes and include tests.\n",
        encoding="utf-8",
    )
    return tmp_path
