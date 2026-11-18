#!/usr/bin/env python3
"""Validate one model archive YAML manifest."""
import argparse
from pathlib import Path

import yaml

from providers import get_provider


def validate_manifest(path: Path):
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: cannot read valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    categories = data.get("categories")
    if not isinstance(categories, list) or not categories:
        raise ValueError(f"{path}: 'categories' must be a non-empty list of strings")
    seen_categories = set()
    for index, category in enumerate(categories, 1):
        if not isinstance(category, str) or not category.strip():
            raise ValueError(f"{path}: categories[{index}] must be a non-empty string")
        if category in seen_categories:
            raise ValueError(f"{path}: categories contains duplicate category {category!r}")
        seen_categories.add(category)
    models = data.get("models")
    if not isinstance(models, list):
        raise ValueError(f"{path}: 'models' must be a list")

    seen = set()
    errors = []
    for index, model in enumerate(models, 1):
        where = f"{path}: models[{index}]"
        if not isinstance(model, dict):
            errors.append(f"{where} must be a mapping")
            continue
        for key in ("name", "repo", "category"):
            if key not in model or not isinstance(model[key], str) or not model[key].strip():
                errors.append(f"{where}.{key} is required and must be a non-empty string")
        category = model.get("category")
        if isinstance(category, str) and category.strip() and category not in seen_categories:
            errors.append(f"{where}.category {category!r} is not in the allowed categories")
        name = model.get("name")
        if isinstance(name, str) and name:
            if name in seen:
                errors.append(f"{where}.name duplicates model name {name!r}")
            seen.add(name)
        provider = model.get("provider", "huggingface")
        if not isinstance(provider, str):
            errors.append(f"{where}.provider must be a string")
        else:
            try:
                get_provider(provider)
            except ValueError as exc:
                errors.append(f"{where}.provider: {exc}")
        for key in ("revision", "upstream_repo"):
            if key in model and model[key] is not None and not isinstance(model[key], str):
                errors.append(f"{where}.{key} must be a string")
        if "enabled" in model and not isinstance(model["enabled"], bool):
            errors.append(f"{where}.enabled must be a boolean")
        if "priority" in model and model["priority"] not in ("p1", "p2", "p3"):
            errors.append(f"{where}.priority must be one of p1, p2, p3")
    if errors:
        raise ValueError("\n".join(errors))
    return len(models)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Path to one YAML manifest")
    args = parser.parse_args()
    try:
        count = validate_manifest(args.manifest)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Valid manifest: {args.manifest} ({count} models)")


if __name__ == "__main__":
    main()
