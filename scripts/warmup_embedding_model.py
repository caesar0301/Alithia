#!/usr/bin/env python3
"""Standalone embedding model warmup script for Docker builds and local setup.

Downloads the sentence_transformers embedding model to Alithia's own cache directory.
Uses ModelScope for download (reliable in China), with HF mirror fallback.

Usage:
    python scripts/warmup_embedding_model.py [--verbose]

Environment:
    ALITHIA_HF_CACHE: Override Alithia cache (default: ~/.cache/alithia/models/huggingface)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def get_cache_dir() -> Path:
    """Get Alithia embedding model cache directory.

    Priority:
    1. ALITHIA_HF_CACHE env var (for Docker builds)
    2. Default: ~/.cache/alithia/models/huggingface
    """
    env_cache = os.environ.get("ALITHIA_HF_CACHE")
    if env_cache:
        return Path(env_cache)
    return Path.home() / ".cache" / "alithia" / "models" / "huggingface"


def download_from_modelscope(model_name: str, cache_dir: Path, verbose: bool = False) -> Path | None:
    """Download model from ModelScope.

    Args:
        model_name: Model name (e.g., "all-MiniLM-L6-v2").
        cache_dir: Cache directory.
        verbose: Print progress.

    Returns:
        Path to downloaded model, or None if failed.
    """
    try:
        from modelscope.hub.snapshot_download import snapshot_download

        # ModelScope model path
        modelscope_model = f"sentence-transformers/{model_name}"

        if verbose:
            print(f"Downloading from ModelScope: {modelscope_model}")

        model_path = snapshot_download(
            modelscope_model,
            cache_dir=str(cache_dir),
        )

        if verbose:
            print(f"ModelScope download complete: {model_path}")

        return Path(model_path)

    except ImportError:
        if verbose:
            print("ModelScope SDK not installed, trying HF mirror", file=sys.stderr)
        return None
    except Exception as e:
        if verbose:
            print(f"ModelScope download failed: {e}, trying HF mirror", file=sys.stderr)
        return None


def download_from_hf_mirror(model_name: str, cache_dir: Path, verbose: bool = False) -> bool:
    """Download model from HuggingFace mirror.

    Args:
        model_name: Model name.
        cache_dir: Cache directory.
        verbose: Print progress.

    Returns:
        True if successful.
    """
    # Set HF mirror before importing sentence_transformers
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    try:
        from sentence_transformers import SentenceTransformer

        if verbose:
            print(f"Downloading from HF mirror: https://hf-mirror.com")

        model = SentenceTransformer(model_name, cache_folder=str(cache_dir))

        if verbose:
            print(f"HF mirror download complete: {model_name}")
            print(f"Max sequence length: {model.max_seq_length}")

        return True

    except Exception as e:
        if verbose:
            print(f"HF mirror download failed: {e}", file=sys.stderr)
        return False


def warmup_model(model_name: str = "all-MiniLM-L6-v2", verbose: bool = False) -> bool:
    """Download and cache the embedding model.

    Priority: ModelScope → HF mirror

    Args:
        model_name: Model name to download.
        verbose: Print progress messages.

    Returns:
        True if successful, False otherwise.
    """
    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"Warming up embedding model: {model_name}")
        print(f"Cache directory: {cache_dir}")

    # Try ModelScope first
    model_path = download_from_modelscope(model_name, cache_dir, verbose)

    if model_path:
        # Verify by loading
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(str(model_path))
            if verbose:
                print(f"Model loaded successfully from ModelScope")
                print(f"Max sequence length: {model.max_seq_length}")
            return True
        except Exception as e:
            if verbose:
                print(f"Failed to load ModelScope model: {e}", file=sys.stderr)

    # Fallback to HF mirror
    return download_from_hf_mirror(model_name, cache_dir, verbose)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-download embedding model for Alithia Agent",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress",
    )
    parser.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="Model name to download (default: all-MiniLM-L6-v2)",
    )
    args = parser.parse_args()

    success = warmup_model(model_name=args.model, verbose=args.verbose)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())