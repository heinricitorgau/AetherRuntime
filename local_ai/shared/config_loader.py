"""Load and validate config-driven pipeline profiles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from local_ai.shared.paths import CONFIG_DIR, resolve_repo_path
except ImportError:  # pragma: no cover - direct script execution
    from paths import CONFIG_DIR, resolve_repo_path


class ConfigError(ValueError):
    """Raised when a config file or profile is missing required data."""


def format_config_error(exc: ConfigError) -> str:
    """Return a concise, user-facing config error block."""
    return f"[config] ERROR: {exc}"


def _config_path(name: str) -> Path:
    return CONFIG_DIR / f"{name}.json"


def _require_keys(kind: str, profile_name: str, data: dict[str, Any], keys: set[str]) -> None:
    missing = sorted(keys - set(data))
    if missing:
        raise ConfigError(
            f"{kind} profile '{profile_name}' is missing required keys: "
            + ", ".join(missing)
        )


def load_config(name: str) -> dict[str, Any]:
    """Load `local_ai/config/<name>.json` with clear errors."""
    path = _config_path(name)
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config file must contain an object: {path}")
    return data


def _load_profile(config_name: str, profile_name: str) -> dict[str, Any]:
    profiles = load_config(config_name)
    profile = profiles.get(profile_name)
    if profile is None:
        available = ", ".join(sorted(profiles)) or "<none>"
        raise ConfigError(
            f"unknown {config_name} profile '{profile_name}'. Available: {available}"
        )
    if not isinstance(profile, dict):
        raise ConfigError(f"{config_name} profile '{profile_name}' must be an object")
    return dict(profile)


def load_model_profile(profile_name: str) -> dict[str, Any]:
    """Load a validated model profile."""
    profile = _load_profile("models", profile_name)
    _require_keys(
        "model",
        profile_name,
        profile,
        {"hf_model", "ollama_model", "dtype", "max_tokens", "temperature", "lora_target_modules"},
    )
    return profile


def load_dataset_profile(profile_name: str) -> dict[str, Any]:
    """Load a validated dataset profile with resolved `path`."""
    profile = _load_profile("datasets", profile_name)
    _require_keys("dataset", profile_name, profile, {"path", "format", "type"})
    profile["path"] = resolve_repo_path(profile["path"])
    return profile


def load_benchmark_profile(profile_name: str) -> dict[str, Any]:
    """Load a validated benchmark profile."""
    profile = _load_profile("benchmarks", profile_name)
    _require_keys(
        "benchmark",
        profile_name,
        profile,
        {"dataset", "model", "prompt_profile", "scoring"},
    )
    load_dataset_profile(str(profile["dataset"]))
    load_model_profile(str(profile["model"]))
    return profile


def load_training_job(job_name: str) -> dict[str, Any]:
    """Load a validated training job with resolved dataset and output paths."""
    job = _load_profile("training_jobs", job_name)
    _require_keys("training job", job_name, job, {"model", "dataset", "output_dir", "epochs"})
    job["output_dir"] = resolve_repo_path(job["output_dir"])
    load_model_profile(str(job["model"]))
    load_dataset_profile(str(job["dataset"]))
    return job


def load_runtime_profile(profile_name: str) -> dict[str, Any]:
    """Load a validated runtime profile."""
    profile = _load_profile("runtime_profiles", profile_name)
    _require_keys(
        "runtime",
        profile_name,
        profile,
        {"ollama_timeout_seconds", "first_token_timeout_seconds"},
    )
    if "proxy_port" in profile:
        profile["proxy_port"] = int(profile["proxy_port"])
    if "ollama_port" in profile:
        profile["ollama_port"] = int(profile["ollama_port"])
    profile["ollama_timeout_seconds"] = int(profile["ollama_timeout_seconds"])
    profile["first_token_timeout_seconds"] = int(profile["first_token_timeout_seconds"])
    return profile


def _self_test() -> None:
    load_model_profile("qwen3b_local")
    load_dataset_profile("c_exam_sft_v1")
    load_dataset_profile("c_exam_test_2025")
    load_dataset_profile("c_exam2_benchmark_all")
    load_benchmark_profile("c_exam_2025_strict_seeded")
    load_benchmark_profile("c_exam2_all_strict_seeded")
    load_training_job("tiny_lora_test")
    load_runtime_profile("qwen3b_benchmark")
    print("config_loader self-test: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Config loader utilities")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        try:
            _self_test()
        except ConfigError as exc:
            print(format_config_error(exc))
            raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
