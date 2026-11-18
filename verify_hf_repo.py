#!/usr/bin/env python3
"""Inspect a Hugging Face model repository without downloading model weights."""
import argparse
from datetime import date
from pathlib import Path
import re

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.errors import GatedRepoError, HfHubHTTPError, RepositoryNotFoundError


def inspect_repository(repository: str):
    api = HfApi()
    try:
        info = api.model_info(repository, files_metadata=False)
    except GatedRepoError as exc:
        raise RuntimeError("repository is gated; authenticate and request access before review") from exc
    except RepositoryNotFoundError as exc:
        raise RuntimeError(
            "repository is missing, private, or inaccessible; verify the ID and authentication; "
            "do not substitute another repository"
        ) from exc
    except HfHubHTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (401, 403):
            raise RuntimeError(
                f"Hub returned HTTP {status}; authentication or repository access is required"
            ) from exc
        raise RuntimeError(f"Hugging Face Hub request failed ({status or 'unknown status'}): {exc}") from exc
    except Exception as exc:
        # Includes transport/DNS failures; never mistake these for repository absence.
        raise RuntimeError(f"Hub lookup could not be completed ({type(exc).__name__}); repository status is unverified") from exc

    card = None
    card_error = None
    try:
        # Fetch the text card only. No repository snapshot or weight files are downloaded.
        card_path = hf_hub_download(repository, "README.md", repo_type="model")
        card = Path(card_path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # Card absence is review uncertainty, not evidence of a bad repo.
        card_error = str(exc)
    return info, card, card_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", help="Exact owner/model ID from the proposed manifest entry")
    parser.add_argument("--expected-name", required=True, help="Requested model name")
    parser.add_argument("--expected-size", required=True, help="Requested parameter size, e.g. 0.6B")
    args = parser.parse_args()
    try:
        info, card, card_error = inspect_repository(args.repository)
    except RuntimeError as exc:
        parser.error(str(exc))
    print(f"Repository: {info.id}")
    print(f"URL: https://huggingface.co/{info.id}")
    print(f"Verified: {date.today().isoformat()}")
    title = next((line.lstrip('# ').strip() for line in card.splitlines() if line.startswith('#')), '') if card else ''
    print(f"Requested: {args.expected_name} ({args.expected_size})")
    print(f"Card title: {title or 'unavailable'}")
    def comparable(value):
        return re.sub(r"[^a-z0-9]", "", value.lower())
    if title:
        name_ok = comparable(args.expected_name) in comparable(title) or comparable(title) in comparable(args.expected_name)
        print(f"Name comparison: {'MATCH' if name_ok else 'MISMATCH — STOP'}")
    else:
        print("Name comparison: UNVERIFIED — STOP")
    print("Card parameter-size mentions:")
    if card:
        mentions = [line.strip() for line in card.splitlines()
                    if any(word in line.lower() for word in ("parameter", "billion", "million", "\u1d2e", "\u1d39"))]
        print("\n".join(f"  {line}" for line in mentions[:20]) or "  none found; confirm from card/config manually")
        size_ok = comparable(args.expected_size) in comparable(" ".join(mentions))
        print(f"Size comparison: {'MATCH' if size_ok else 'MISMATCH or UNVERIFIED — STOP'}")
    else:
        print(f"  unavailable ({card_error}); confirm from repository metadata manually")
        print("Size comparison: UNVERIFIED — STOP")
    print("Compare the displayed name and parameter count with the request. If either is unclear or differs, stop; do not guess a replacement.")


if __name__ == "__main__":
    main()
