"""Canonical Path anchors for every local_ai subsystem.

Usage:
    from local_ai.shared.paths import LOCAL_AI_ROOT, QUALITY_DIR
"""
from __future__ import annotations

from pathlib import Path

LOCAL_AI_ROOT       = Path(__file__).resolve().parent.parent
REPO_ROOT           = LOCAL_AI_ROOT.parent
SHARED_DIR          = LOCAL_AI_ROOT / "shared"
CONFIG_DIR          = LOCAL_AI_ROOT / "config"
BENCHMARK_DIR       = LOCAL_AI_ROOT / "benchmark"
QUALITY_DIR         = LOCAL_AI_ROOT / "quality"
TRAINING_QUALITY_DIR = LOCAL_AI_ROOT / "training_quality"  # legacy alias
INGEST_DIR          = LOCAL_AI_ROOT / "ingest"
SFT_DIR             = LOCAL_AI_ROOT / "sft"
RAG_DIR             = LOCAL_AI_ROOT / "rag"
PROMPTS_DIR         = LOCAL_AI_ROOT / "prompts"
EVAL_CASES_DIR      = LOCAL_AI_ROOT / "eval_cases"

# Data paths
TRAINING_DATA_DIR   = INGEST_DIR / "output" / "training"
GOLDEN_DIR          = BENCHMARK_DIR / "golden"
BENCHMARK_REPORTS   = BENCHMARK_DIR / "reports"
QUALITY_REPORTS     = TRAINING_QUALITY_DIR / "reports"
SFT_ARTIFACTS       = SFT_DIR / "artifacts"
SFT_REPORTS         = SFT_DIR / "reports"


def repo_root() -> Path:
    """Return the repository root directory."""
    return REPO_ROOT


def local_ai_root() -> Path:
    """Return the local_ai package root directory."""
    return LOCAL_AI_ROOT


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve *path* from the repository root unless it is already absolute."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate
