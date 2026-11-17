"""Hugging Face Hub implementation of the model provider interface."""
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download


class HuggingFaceProvider:
    name = "huggingface"

    def __init__(self):
        self.api = HfApi()

    def get_metadata(self, repository: str, revision: str = "main"):
        # model_info resolves mutable refs (for example, main) to an immutable SHA.
        return self.api.model_info(repository, revision=revision, files_metadata=True)

    def download(self, repository: str, revision: str, destination: Path) -> Path:
        path = snapshot_download(
            repo_id=repository,
            revision=revision,
            local_dir=str(destination),
        )
        return Path(path)
