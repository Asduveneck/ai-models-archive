"""Supported model providers."""
from .base import ModelProvider
from .huggingface import HuggingFaceProvider


def get_provider(name: str) -> ModelProvider:
    if name == "huggingface":
        return HuggingFaceProvider()
    raise ValueError(f"Unsupported provider: {name}")


__all__ = ["ModelProvider", "HuggingFaceProvider", "get_provider"]
