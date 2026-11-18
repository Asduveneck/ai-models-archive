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


@pytest.mark.parametrize("archived", [False, True])
def test_dry_run_resolves_revision_without_writes_or_downloads(tmp_path, monkeypatch, capsys, archived):
    sha = "b" * 40
    info = SimpleNamespace(sha=sha)
    calls = {"metadata": 0, "download": 0}

    class FakeProvider:
        name = "huggingface"

        def get_metadata(self, repository, revision):
            calls["metadata"] += 1
            return info

        def download(self, repository, revision, destination):
            calls["download"] += 1
            raise AssertionError("dry-run must not download")

    monkeypatch.setattr(model_archive, "get_provider", lambda name: FakeProvider())
    root = tmp_path / "archive"
    destination = root / "models/llm/sample/revisions" / sha
    if archived:
        completion = destination / "_archive/complete.json"
        completion.parent.mkdir(parents=True)
        completion.write_text("{}", encoding="utf-8")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    model_archive.dry_run({
        "name": "sample", "repo": "org/model", "provider": "huggingface",
        "category": "llm", "revision": "main",
    }, root)

    output = capsys.readouterr().out
    assert calls == {"metadata": 1, "download": 0}
    assert str(destination) in output
    assert ("Already archived:" if archived else "Would download:") in output
    assert not root.exists() if not archived else root.exists()
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before


def test_dry_run_cli_uses_selection_and_does_not_require_writable_archive(tmp_path, monkeypatch, capsys):
    config = write_registry(tmp_path, """categories: [llm]
models:
  - name: selected
    repo: org/model
    category: llm
  - name: other
    repo: org/other
    category: llm
""")
    calls = []

    class FakeProvider:
        name = "huggingface"

        def get_metadata(self, repository, revision):
            calls.append((repository, revision))
            return SimpleNamespace(sha="c" * 40)

        def download(self, *args, **kwargs):
            raise AssertionError("dry-run must not download")

    monkeypatch.setattr(model_archive, "get_provider", lambda name: FakeProvider())
    monkeypatch.setenv("MODEL_ARCHIVE_ROOT", str(tmp_path / "missing"))
    monkeypatch.setattr("sys.argv", ["model_archive.py", "download", "--config", str(config),
                                     "--name", "selected", "--dry-run"])
    model_archive.main()
    assert calls == [("org/model", "main")]
    assert "selected" in capsys.readouterr().out
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("manifest_text, message", [
    ("categories: [llm]\nmodels: {}", "'models' must be a list"),
    ("categories: [llm]\nmodels:\n  - name: incomplete\n    repo: org/model\n", "category is required"),
    ("categories: [llm]\nmodels:\n  - name: bad\n    repo: org/model\n    category: llm\n    provider: missing\n", "Unsupported provider: missing"),
])
def test_dry_run_reports_invalid_manifest_without_provider_lookup(
    tmp_path, monkeypatch, capsys, manifest_text, message,
):
    config = write_registry(tmp_path, manifest_text)
    monkeypatch.setenv("MODEL_ARCHIVE_ROOT", str(tmp_path / "archive"))
    monkeypatch.setattr("sys.argv", ["model_archive.py", "download", "--config", str(config),
                                     "--dry-run"])
    with pytest.raises(SystemExit) as exc:
        model_archive.main()
    assert exc.value.code == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "archive").exists()


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
