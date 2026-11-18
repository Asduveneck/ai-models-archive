import pytest

from validate_manifest import validate_manifest


def manifest(tmp_path, content):
    path = tmp_path / "manifest.yaml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize("content, message", [
    ("[]", "top level must be a mapping"),
    ("categories: [llm]\nmodels: {}", "'models' must be a list"),
    ("categories: [llm]\nmodels:\n  - name: sample\n    repo: org/model\n", "category is required"),
    ("categories: [llm]\nmodels:\n  - name: sample\n    repo: org/model\n    category: llm\n    provider: unknown\n", "Unsupported provider: unknown"),
    ("categories: [llm]\nmodels:\n  - name: sample\n    repo: org/model\n    category: llm\n    enabled: yesplease\n", "enabled must be a boolean"),
    ("categories: [llm]\nmodels:\n  - name: sample\n    repo: org/model\n    category: llm\n  - name: sample\n    repo: org/other\n    category: llm\n", "duplicates model name"),
])
def test_invalid_manifests_report_useful_errors(tmp_path, content, message):
    with pytest.raises(ValueError, match=message):
        validate_manifest(manifest(tmp_path, content))


def test_manifest_requires_name_repo_and_category(tmp_path):
    path = manifest(tmp_path, "categories: [llm]\nmodels:\n  - provider: huggingface\n")
    with pytest.raises(ValueError) as exc:
        validate_manifest(path)
    message = str(exc.value)
    assert "name is required" in message
    assert "repo is required" in message
    assert "category is required" in message


def test_valid_manifest(tmp_path):
    path = manifest(tmp_path, """categories: [llm]
models:
  - name: sample
    repo: org/model
    category: llm
    priority: p1
    enabled: true
""")
    assert validate_manifest(path) == 1


def test_manifest_rejects_unlisted_category(tmp_path):
    path = manifest(tmp_path, """categories: [llm]
models:
  - name: sample
    repo: org/model
    category: embeddings
""")
    with pytest.raises(ValueError, match="not in the allowed categories"):
        validate_manifest(path)
