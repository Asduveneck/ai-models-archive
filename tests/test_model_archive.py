import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import model_archive
from providers import HuggingFaceProvider, get_provider


def write_registry(tmp_path, text):
    path = tmp_path / "models.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_registry_defaults_provider_for_legacy_config(tmp_path):
    config = write_registry(tmp_path, """models:\n  - name: sample\n    repo: org/model\n    category: llm\n""")
    model = model_archive.registry(config)[0]
    assert model["provider"] == "huggingface"


def test_registry_accepts_explicit_provider_and_alias_fields(tmp_path):
    config = write_registry(tmp_path, """models:\n  - id: sample\n    provider: huggingface\n    repository: org/model\n    category: llm\n""")
    model = model_archive.registry(config)[0]
    assert (model["name"], model["repo"], model["provider"]) == (
        "sample", "org/model", "huggingface"
    )


def test_registry_rejects_unsupported_provider(tmp_path):
    config = write_registry(tmp_path, """models:\n  - name: sample\n    repo: org/model\n    provider: other\n""")
    with pytest.raises(ValueError, match="Unsupported provider: other"):
        model_archive.registry(config)


def test_provider_resolution():
    assert isinstance(get_provider("huggingface"), HuggingFaceProvider)
    with pytest.raises(ValueError, match="Unsupported provider: nope"):
        get_provider("nope")


def test_download_resolves_revision_and_preserves_archive_metadata(tmp_path, monkeypatch):
    sha = "a" * 40
    card = {"license": "apache-2.0", "base_model": "org/base"}
    siblings = [SimpleNamespace(rfilename="README.md", size=12)]
    info = SimpleNamespace(sha=sha, card_data=card, siblings=siblings, gated=False)
    calls = {}

    class FakeProvider:
        name = "huggingface"

        def get_metadata(self, repository, revision):
            calls["metadata"] = (repository, revision)
            return info

        def download(self, repository, revision, destination):
            calls["download"] = (repository, revision, destination)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "README.md").write_text("card", encoding="utf-8")
            return destination

    monkeypatch.setattr(model_archive, "get_provider", lambda name: FakeProvider())
    model_archive.download({
        "name": "sample", "repo": "org/model", "provider": "huggingface",
        "category": "llm", "revision": "main", "upstream_repo": "org/base",
    }, tmp_path)

    destination = tmp_path / "models/llm/sample/revisions" / sha
    assert calls["metadata"] == ("org/model", "main")
    assert calls["download"] == ("org/model", sha, destination)
    metadata = json.loads((destination / "_archive/metadata.json").read_text())
    assert metadata["provider"] == "huggingface"
    assert metadata["revision"] == sha
    assert metadata["license"] == "apache-2.0"
    assert metadata["upstream_repository"] == "org/base"
    assert metadata["license_review_status"] == "review_required"
    assert metadata["downloaded_at_utc"]
    assert json.loads((destination / "_archive/repository-files.json").read_text()) == [
        {"path": "README.md", "size": 12}
    ]
    assert "README.md" in json.loads(
        (destination / "_archive/checksums.json").read_text()
    )
    assert json.loads((destination / "_archive/complete.json").read_text()) == {
        "revision": sha, "file_count": 1
    }

    model_archive.verify(tmp_path)


def test_huggingface_provider_forwards_commit_and_destination(monkeypatch, tmp_path):
    calls = {}

    class FakeAPI:
        def model_info(self, repository, **kwargs):
            calls["info"] = (repository, kwargs)
            return SimpleNamespace(sha="commit")

    monkeypatch.setattr("providers.huggingface.HfApi", FakeAPI)
    monkeypatch.setattr(
        "providers.huggingface.snapshot_download",
        lambda **kwargs: (calls.__setitem__("snapshot", kwargs), str(tmp_path))[1],
    )
    provider = HuggingFaceProvider()
    metadata = provider.get_metadata("org/model", revision="main")
    provider.download("org/model", revision=metadata.sha, destination=tmp_path)

    assert calls["info"] == (
        "org/model", {"revision": "main", "files_metadata": True}
    )
    assert calls["snapshot"] == {
        "repo_id": "org/model", "revision": "commit", "local_dir": str(tmp_path)
    }
