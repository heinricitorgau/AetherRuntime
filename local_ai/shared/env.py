"""Read CLAW_* environment variables with typed defaults.

All defaults mirror the hardcoded constants in proxy.py and run_baseline.py
so that config/model_profiles.json can eventually replace both.
"""
from __future__ import annotations

import os


def get_env_str(name: str, default: str) -> str:
    """Return a string environment variable or *default* when unset."""
    return os.environ.get(name, default)


def get_env_int(name: str, default: int) -> int:
    """Return an integer environment variable, falling back on parse failure."""
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def get_env_float(name: str, default: float) -> float:
    """Return a float environment variable, falling back on parse failure."""
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def get_env_bool(name: str, default: bool) -> bool:
    """Return a boolean environment variable using common truthy spellings."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def proxy_url() -> str:
    return get_env_str("CLAW_PROXY_URL", "http://127.0.0.1:8082")


def model_name() -> str:
    return get_env_str("CLAW_MODEL", "qwen2.5-coder:3b")


def ollama_url() -> str:
    return get_env_str("CLAW_OLLAMA_URL", "http://localhost:11434")


def benchmark_max_tokens() -> int:
    return get_env_int("CLAW_BENCHMARK_MAX_TOKENS", 768)


def benchmark_timeout() -> int:
    return get_env_int("CLAW_BENCHMARK_TIMEOUT_SECONDS", 660)


def ollama_timeout() -> int:
    return get_env_int("CLAW_OLLAMA_TIMEOUT", 300)


def first_token_timeout() -> int:
    return get_env_int("CLAW_FIRST_TOKEN_TIMEOUT", 90)
