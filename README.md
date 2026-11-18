# AI Models Archive

A small, reusable Python CLI for downloading Hugging Face models to a configurable directory, preserving model cards and license files, recording repository metadata, and verifying SHA-256 checksums.

## Quick start

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e '.[dev]'
pre-commit install
cp .env.example .env
cp models.example.yaml models.yaml
python model_archive.py download
```

The included `models.yaml` is a starting registry. Edit it to add the models you want to archive, or copy `models.example.yaml` to use the example registry separately. A download saves every file in each selected repository snapshot, including model weights, so review the registry before running it.

Use `--name` or `--priority` to select models from the registry. For example:

```bash
python model_archive.py download --name qwen3-0.6b-4bit
python model_archive.py download --name qwen3-0.6b-4bit --dry-run
```

`--dry-run` performs the same model selection and provider revision lookup as a download, then reports whether that exact revision is archived or would be downloaded and its destination. It does not create directories, write files, or download model data.

Before adding a Hugging Face repository, verify its exact ID and card with:

```bash
python verify_hf_repo.py OWNER/REPO --expected-name 'MODEL NAME' --expected-size 0.6B
```

This checks Hub visibility and fetches only `README.md`; no model weights are downloaded. Compare the displayed card title and parameter-size claims with the requested model. Missing/private/gated repositories, authentication failures, and unclear or mismatched model details require stopping for access or clarification; do not guess a replacement. Record the source URL, verification date, requested and observed identity/size, and decision in [MODEL_REGISTRY_REVIEWS.md](MODEL_REGISTRY_REVIEWS.md). This keeps provenance reviewable without adding fields to the manifest schema. After adding the entry, run both manifest validators and `python model_archive.py download --name ENTRY_NAME --dry-run` with `MODEL_ARCHIVE_ROOT` set. Never run a real download as part of verification.

## Other commands

```bash
python model_archive.py list
python model_archive.py verify
python model_archive.py licenses
python validate_manifest.py models.yaml
python validate_manifest.py models.example.yaml
python -m pytest
```

`list` shows configured models, `verify` checks archived files against their recorded checksums, and `licenses` reports metadata for models already in the archive. The validator accepts one manifest path per invocation and checks required fields, types, provider support, and duplicate names. `licenses` does not download files or review license terms for you. Pre-commit runs the Python test suite and validates both checked-in manifests on every commit.

## Switch destinations without editing Python

The required environment variable is `MODEL_ARCHIVE_ROOT`. Relative paths resolve against the directory where you run the command; absolute paths are recommended for external drives.

Local test `.env`:

```dotenv
MODEL_ARCHIVE_ROOT=./archive
```

External drive `.env.external` (create from `.env.external.example` and edit the volume name):

```dotenv
MODEL_ARCHIVE_ROOT=/Volumes/AI-Archive
```

Then run:

```bash
python model_archive.py download --env-file .env.external
python model_archive.py verify --env-file .env.external
```

Alternatively, use a shell export without an `.env` file:

```bash
export MODEL_ARCHIVE_ROOT="$HOME/model-library"
python model_archive.py download --env-file /dev/null
```

**Safety:** Check that `/Volumes/AI-Archive` is actually mounted before starting. The script does **not** enforce mount checks because it is intended to work with local directories and multiple operating systems. It creates the destination if necessary, so a mistyped `/Volumes/...` path could write to the Mac's internal disk.

Never commit real `.env` files or access tokens. For gated models, authenticate with `hf auth login` or use `HF_TOKEN` privately.

## YAML registry

`models.yaml` controls the models and priorities:

```yaml
categories:
  - llm
  - Documents
  - Embeddings
  - Reranking

models:
  - name: qwen3-0.6b-4bit
    provider: huggingface
    repo: mlx-community/Qwen3-0.6B-4bit
    category: llm
    priority: p1
    personal_notes: "Compact model for local experimentation; note your use case and any limitations."
    revision: main
    upstream_repo: Qwen/Qwen3-0.6B
    enabled: true
```

Declare every accepted category in the top-level `categories` list. Each model's `category` must exactly match one of those values; the manifest validator checks this before downloads, dry runs, or other commands that load the manifest. Add a category to the list before assigning it to a model.

`provider` selects the model repository backend. It defaults to `huggingface` for older registry files, and currently Hugging Face is the only supported value. The archive manager uses a small provider interface for repository metadata, immutable revision resolution, and snapshot downloads; archive layout, manifests, checksums, and licensing review remain in the manager. A future provider can implement that interface and be added to the explicit `get_provider` mapping without a plugin system. Storage destinations continue to come from `MODEL_ARCHIVE_ROOT` in the environment or `.env` file, not from model entries. Archive provenance records the provider, repository, resolved commit, timestamp, available model-card/license metadata, and configured upstream reference. This is a historical metadata snapshot, not a license review: every model remains `review_required`, including quantized derivatives.

`personal_notes` is an optional field for your own intended use, recommendations, strengths, or limitations. When present, it is copied into the archive's readable `_archive/metadata.json` file. It can be a string, mapping, list, or another JSON-compatible YAML value. The example uses a string. Notes are captured when a revision is first archived; downloading an already completed revision does not update its metadata.

`revision: main` is resolved to a full immutable commit hash before downloading. You can pin a commit hash in YAML for strict repeatability. Add more entries and use `--name` or `--priority` to select models:

```bash
python model_archive.py download --name qwen3-0.6b-4bit
python model_archive.py download --priority p1
```

## Archive layout

```text
archive/
└── models/
    └── llm/
        └── qwen3-0.6b-4bit/
            └── revisions/
                └── <full-commit-sha>/
                    ├── README.md                  # If provided by publisher
                    ├── model files...             # Repo snapshot
                    └── _archive/
                        ├── metadata.json          # License ID and model-card metadata
                        ├── repository-files.json  # Published file listing
                        ├── checksums.json         # SHA-256 for downloaded files
                        └── complete.json          # Written after successful download
```

All files published in the selected repository snapshot are downloaded, including README/model cards, license files **if present**, configs and weights. The script preserves published license metadata but does not download legal documents linked on external websites. `_archive` files are generated by this script, not by the publisher.

Re-running a completed revision skips it; interrupted downloads can be rerun. `verify` detects changed, missing, and extra non-cache files within completed snapshots. The downloaded file list and checksums are recorded locally; this is not a cryptographic attestation from the model publisher.

## Licensing — short practical summary

**A public Hugging Face repository is not automatically open source or commercially licensed.** The script records the repository's license identifier, model-card metadata, upstream model reference, and gating status, and sets `license_review_status` to `review_required` for every model.

| License type | General implication |
| --- | --- |
| Apache-2.0 / MIT | Usually allow commercial use and redistribution, subject to notice, attribution, and other terms. |
| RAIL / OpenRAIL | Often impose use restrictions; read the exact license. |
| Custom license | Review before using commercially, fine-tuning, or redistributing. |
| Noncommercial | Do not assume commercial use is allowed. |
| Missing/unclear | Treat as requiring permission or legal review. |

**For a quantized or fine-tuned model**, review both the derivative repository's terms and the original base model's terms. A derivative's license label does not override upstream restrictions. Before monetizing or open-sourcing a product, separately check (1) inference/commercial usage, (2) redistribution of weights, (3) distribution of derivatives, and (4) attribution/notice obligations. Also consider applicable use policies, trademarks, and third-party components. Open-sourcing your application code is not the same as redistributing model weights.

This is a workflow guide, **not legal advice**. Model terms can change, and the metadata saved here is a historical record rather than a legal clearance decision.

## Scope and limitations

- Downloads **one quantized model** by default; no large archive downloads are enabled.
- Downloads are **not** model execution. For this MLX checkpoint, use a compatible MLX runtime separately.
- Saves a snapshot of each selected revision, not a complete history of every commit.
- Does not mirror external license URLs or automatically retrieve upstream model files/licenses. Review the upstream model card separately before commercial use.
- Does not validate that a model can actually run on your hardware.
- Keep a second copy of irreplaceable fine-tuned weights and manifests; one HDD is not a backup strategy.

## References

- [Hugging Face Hub downloads](https://huggingface.co/docs/huggingface_hub/en/guides/download)
- [Hugging Face model cards](https://huggingface.co/docs/hub/model-cards)
- [Hugging Face licenses](https://huggingface.co/docs/hub/repositories-licenses)
