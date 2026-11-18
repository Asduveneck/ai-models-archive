# Model registry verification log

Keep review provenance here rather than adding unsupported fields to `models.yaml`.
For each new or changed Hugging Face entry, copy this record and complete it from
`python verify_hf_repo.py OWNER/REPO` and the linked model card.

```text
Entry name:
Requested model / parameter size:
Repository ID:
Source URL:
Verified (YYYY-MM-DD):
Hub result (public / gated / private / missing / auth issue):
Displayed model-card name:
Parameter size shown by card/config:
Decision (confirmed / stopped for clarification):
Notes:
```

Do not record a confirmation if access was denied, the card/config did not establish
the requested size, or the displayed model did not match. Resolve uncertainty with
the requester; do not infer an alternate repository.
