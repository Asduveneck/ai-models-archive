#!/usr/bin/env python3
"""Small reproducible Hugging Face model archive CLI."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from providers import get_provider

BASE = Path(__file__).resolve().parent


def registry(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("models.yaml must contain a mapping")
    models = data.get("models", [])
    if not isinstance(models, list):
        raise ValueError("models.yaml must contain a models list")
    for model in models:
        if not isinstance(model, dict):
            raise ValueError("each model definition must be a mapping")
        model.setdefault("provider", "huggingface")
        # Accept the descriptive field names while preserving the existing CLI
        # registry keys and archive layout.
        if not model.get("name"):
            model["name"] = model.get("id")
        if not model.get("repo"):
            model["repo"] = model.get("repository")
        if not model.get("name") or not model.get("repo"):
            raise ValueError("each model must define name/id and repo/repository")
        get_provider(model["provider"])
    return models


def root_dir():
    raw = os.environ.get("MODEL_ARCHIVE_ROOT")
    if not raw:
        raise SystemExit("MODEL_ARCHIVE_ROOT is required; copy .env.example to .env")
    return Path(raw).expanduser().resolve()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def model_files(directory):
    return sorted(p for p in directory.rglob("*") if p.is_file()
                  and ".cache" not in p.relative_to(directory).parts
                  and "_archive" not in p.relative_to(directory).parts)


def choose(models, name, priority):
    chosen = [m for m in models if m.get("enabled", True)
              and (not name or m["name"] == name)
              and (not priority or m.get("priority") == priority)]
    if not chosen:
        raise SystemExit("No enabled models match your selection")
    return chosen


def download(model, root):
    provider = get_provider(model.get("provider", "huggingface"))
    repo = model["repo"]
    info = provider.get_metadata(repo, revision=model.get("revision", "main"))
    sha = info.sha
    dest = root / "models" / model["category"] / model["name"] / "revisions" / sha
    meta_dir = dest / "_archive"
    completion = meta_dir / "complete.json"
    if completion.exists():
        print(f"Already archived: {repo} @ {sha}")
        return
    dest.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {repo} @ {sha} to {dest}")
    provider.download(repo, revision=sha, destination=dest)
    meta_dir.mkdir(exist_ok=True)
    card = info.card_data
    card_data = dict(card) if card is not None else {}
    metadata = {
        "provider": provider.name,
        "repository": repo, "upstream_repository": model.get("upstream_repo"),
        "revision": sha, "category": model["category"],
        "priority": model.get("priority"),
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": card_data.get("license"),
        "license_name": card_data.get("license_name"),
        "license_link": card_data.get("license_link"),
        "gated": info.gated,
        "model_card_metadata": card_data,
        "license_review_status": "review_required",
        "note": "Review upstream license, derivative terms, and redistribution rights before commercial use."
    }
    write_json(meta_dir / "metadata.json", metadata)
    write_json(meta_dir / "repository-files.json", [
        {"path": s.rfilename, "size": getattr(s, "size", None)}
        for s in (info.siblings or [])
    ])
    checksums = {str(p.relative_to(dest)): file_hash(p) for p in model_files(dest)}
    write_json(meta_dir / "checksums.json", checksums)
    write_json(completion, {"revision": sha, "file_count": len(checksums)})
    print(f"Complete: {len(checksums)} files. License: {metadata['license'] or 'unspecified'} (review required)")


def verify(root):
    manifests = list((root / "models").rglob("_archive/checksums.json"))
    if not manifests:
        raise SystemExit("No completed archives found")
    failures = 0
    for manifest in manifests:
        dest = manifest.parent.parent
        expected = json.loads(manifest.read_text())
        actual = {str(p.relative_to(dest)): file_hash(p) for p in model_files(dest)}
        ok = expected == actual and (manifest.parent / "complete.json").exists()
        print(f"{'OK' if ok else 'FAIL'} {dest} ({len(expected)} files)")
        failures += not ok
    if failures:
        raise SystemExit(f"Verification failed for {failures} archive(s)")


def licenses(root):
    manifests = list((root / "models").rglob("_archive/metadata.json"))
    if not manifests:
        print("No archived license metadata found")
    for path in manifests:
        m = json.loads(path.read_text())
        print(f"{m['repository']} @ {m['revision'][:12]}: "
              f"{m.get('license') or 'unspecified'}; "
              f"{m['license_review_status']}; upstream={m.get('upstream_repository') or 'unknown'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["list", "download", "verify", "licenses"])
    parser.add_argument("--config", type=Path, default=BASE / "models.yaml")
    parser.add_argument("--env-file", type=Path, default=BASE / ".env")
    parser.add_argument("--name", help="Model name from models.yaml")
    parser.add_argument("--priority", choices=["p1", "p2", "p3"])
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    models = registry(args.config)
    if args.command == "list":
        for m in models:
            print(f"{m.get('priority', '-'):3} {m['name']:24} {m['repo']} "
                  f"{'enabled' if m.get('enabled', True) else 'disabled'}")
        return
    root = root_dir()
    if args.command == "download":
        for model in choose(models, args.name, args.priority):
            download(model, root)
    elif args.command == "verify":
        verify(root)
    else:
        licenses(root)


if __name__ == "__main__":
    main()
