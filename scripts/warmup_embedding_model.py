#!/usr/bin/env python3
"""Standalone embedding model warmup script for Docker builds and local setup.

Downloads the FastEmbed ONNX embedding model to Alithia's own cache directory.

Usage:
    python scripts/warmup_embedding_model.py [--verbose]

Environment:
    ALITHIA_EMBEDDING_CACHE: Override Alithia cache (default: ~/.cache/alithia/models/embeddings)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def get_cache_dir() -> Path:
    """Get Alithia embedding model cache directory.

    Priority:
    1. ALITHIA_EMBEDDING_CACHE env var (for Docker builds)
    2. Default: ~/.cache/alithia/models/embeddings
    """
    import os

    env_cache = os.environ.get("ALITHIA_EMBEDDING_CACHE")
    if env_cache:
        return Path(env_cache)
    return Path.home() / ".cache" / "alithia" / "models" / "embeddings"


def warmup_model(model_name: str = DEFAULT_MODEL, verbose: bool = False) -> bool:
    """Download and cache the embedding model.

    Args:
        model_name: Model name to download.
        verbose: Print progress messages.

    Returns:
        True if successful, False otherwise.
    """
    import os

    # Set HF mirror for reliable downloads (especially in China)
    if "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    try:
        from fastembed import TextEmbedding
    except ImportError:
        if verbose:
            print("ERROR: fastembed not installed", file=sys.stderr)
            print("Install with: pip install fastembed", file=sys.stderr)
        return False

    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"Warming up embedding model: {model_name}")
        print(f"Cache directory: {cache_dir}")

    try:
        model = TextEmbedding(model_name=model_name, cache_dir=str(cache_dir))
        vectors = list(model.embed(["warmup probe"]))
        if verbose:
            print(f"Model loaded successfully: {model_name}")
            print(f"Embedding dimensions: {len(vectors[0])}")
        return True
    except Exception as e:
        if verbose:
            print(f"ERROR: Failed to load model: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-download embedding model for Alithia Agent",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model name to download (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    success = warmup_model(model_name=args.model, verbose=args.verbose)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
