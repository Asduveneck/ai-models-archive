"""Minimal interface for model repository providers."""
from pathlib import Path
from typing import Any, Protocol


class ModelProvider(Protocol):
    name: str

    def get_metadata(self, repository: str, revision: str = "main") -> Any:
        """Return repository metadata for the requested revision."""
        ...

    def download(self, repository: str, revision: str, destination: Path) -> Path:
        """Download an immutable revision to the archive-selected destination."""
        ...
