# Contributor guidance

## Setup and checks

Use Python 3.10 or newer. Create a virtual environment, install runtime dependencies with `pip install -r requirements.txt`, and run checks with `python -m pytest` plus `python validate_manifest.py models.yaml` and `python validate_manifest.py models.example.yaml`. Install pre-commit with `pip install pre-commit`, then enable the commit hooks with `pre-commit install`.

## Registry conventions

Add models as YAML entries with unique `name`, `repo`, and `category`. `provider` defaults to `huggingface`; supported values are registered explicitly in `providers.get_provider`. Optional fields are `revision` (defaults to `main` and resolves to a commit), `upstream_repo`, `enabled` (boolean), and `priority` (`p1`, `p2`, or `p3`). Model additions are routine data changes and do not require code changes.

## Providers

Providers implement the `ModelProvider` interface in `providers/base.py`: expose a `name`, implement `get_metadata(repository, revision)` to resolve metadata and an immutable revision, and implement `download(repository, revision, destination)`. Put provider-specific logic in its own module under `providers/` and add an explicit mapping in `providers/__init__.py`. Keep archive layout, checksums, and licensing metadata handling in `model_archive.py`.

## Adding a model

Before adding a Hugging Face entry, run `python verify_hf_repo.py OWNER/REPO --expected-name 'MODEL NAME' --expected-size 0.6B` for that exact repository ID and the requested identity/size. It checks Hub visibility and reads only the model card; it never downloads model weights. A missing/private/gated result or an unclear/mismatched name or size is a stop condition: resolve access or ask for clarification, and do not guess a replacement.

Record each review in `MODEL_REGISTRY_REVIEWS.md` with the exact repository URL, verification date, requested name/size, and observed card name/size. Keep this review data outside YAML because the manifest schema does not support provenance fields. Then add the manifest entry, validate both manifests, and run the metadata-only dry run:

```bash
python verify_hf_repo.py OWNER/REPO --expected-name 'MODEL NAME' --expected-size 0.6B
python validate_manifest.py models.yaml
python validate_manifest.py models.example.yaml
MODEL_ARCHIVE_ROOT=/tmp/model-archive python model_archive.py download --name ENTRY_NAME --dry-run --env-file /dev/null
```

The dry run resolves repository metadata and destination only; never omit `--dry-run` during registry verification.
