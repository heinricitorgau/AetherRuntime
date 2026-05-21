#!/usr/bin/env python3
"""Minimal LoRA fine-tuning for Qwen2.5-Coder-3B-Instruct.

This is a tiny overfit test — NOT production training.
Purpose: verify that train -> save adapter -> load adapter -> inference works end-to-end.

Usage:
  python -X faulthandler local_ai/sft/train_lora.py \
      --dataset local_ai/training_quality/reports/sft_chatml.jsonl \
      --limit 8 \
      --epochs 1 \
      --output-dir local_ai/sft/artifacts/test_lora

Required packages:
  pip install torch --index-url https://download.pytorch.org/whl/cu124
  pip install transformers peft accelerate sentencepiece safetensors
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# ── Env guards (set before any HF library loads) ──────────────────────────────
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

# ── Constants ─────────────────────────────────────────────────────────────────

_DEFAULT_MODEL       = "Qwen/Qwen2.5-Coder-3B-Instruct"
_LORA_R              = 8
_LORA_ALPHA          = 16
_LORA_DROPOUT        = 0.05
_LORA_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                         "gate_proj", "up_proj", "down_proj"]
_BATCH_SIZE          = 1
_GRAD_ACCUM          = 4
_LEARNING_RATE       = 2e-4
_WARMUP_STEPS        = 2
_MAX_SEQ_LEN         = 1024
_VERBOSE             = False

_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
_RETRY_DIR = _HERE.parent / "retry"   # local_ai/retry/

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.shared.config_loader import (
    ConfigError,
    format_config_error,
    load_dataset_profile,
    load_model_profile,
    load_training_job,
)
from local_ai.experiments.register_run import register_run


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(msg: str) -> None:
    if _VERBOSE:
        print(f"[train] {msg}", flush=True)


def _write_report(report: dict, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "train_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _register_train_experiment(args: argparse.Namespace, report: dict, report_path: Path) -> None:
    try:
        output_dir = Path(args.output_dir)
        registered = register_run(
            {
                "run_id": f"train_{output_dir.name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                "run_type": "train",
                "model_profile": getattr(args, "model_profile_name", None),
                "model": args.model,
                "training_job": args.job,
                "dataset_profile": getattr(args, "dataset_profile_name", None),
                "dataset_path": str(Path(args.dataset)),
                "adapter_path": str(output_dir),
                "output_dir": str(output_dir),
                "epochs": args.epochs,
                "limit": args.limit,
                "train_loss": report.get("train_loss"),
                "elapsed_s": report.get("elapsed_s"),
                "success": report.get("success"),
                "linked_reports": {
                    "train_report_json": str(report_path),
                    "adapter_dir": str(output_dir),
                },
                "config_profiles": {
                    "training_job": args.job,
                    "model": getattr(args, "model_profile_name", None),
                    "dataset": getattr(args, "dataset_profile_name", None),
                },
            }
        )
        print(f"[experiments] registered run_id={registered['run_id']}", flush=True)
    except Exception as exc:
        print(f"[experiments] WARNING: could not register train run: {exc}", file=sys.stderr, flush=True)


# ── Arg parsing ───────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal LoRA fine-tuning — overfit sanity check only"
    )
    parser.add_argument("--job",
                        help="Training job profile name from config/training_jobs.json")
    parser.add_argument("--dataset",
                        help="Path to sft_chatml.jsonl")
    parser.add_argument("--limit",      type=int, default=None,
                        help="Max examples to load (default: all)")
    parser.add_argument("--epochs",     type=int, default=1,
                        help="Training epochs (default: 1)")
    parser.add_argument("--output-dir",
                        help="Directory to save LoRA adapter")
    parser.add_argument("--model",      default=_DEFAULT_MODEL,
                        help=f"Base model ID (default: {_DEFAULT_MODEL})")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed progress logs")
    parser.add_argument("--round", default=None, metavar="NAME",
                        help="Retry curriculum round (e.g. round_1). "
                             "Auto-sets --dataset and --output-dir from the round definition. "
                             "Mutually exclusive with --job.")
    return parser.parse_args()


def _apply_job_config(args: argparse.Namespace) -> argparse.Namespace:
    args.model_profile_name = None
    args.dataset_profile_name = None
    if not args.job:
        return args
    job = load_training_job(args.job)
    args.model_profile_name = str(job["model"])
    args.dataset_profile_name = str(job["dataset"])
    model = load_model_profile(str(job["model"]))
    dataset = load_dataset_profile(str(job["dataset"]))
    lora = job.get("lora", {})
    args.dataset = str(dataset["path"])
    args.output_dir = str(job["output_dir"])
    args.epochs = int(job["epochs"])
    args.limit = job.get("limit")
    args.model = str(model["hf_model"])
    args.lora_r = int(lora.get("r", _LORA_R))
    args.lora_alpha = int(lora.get("alpha", _LORA_ALPHA))
    args.lora_dropout = float(lora.get("dropout", _LORA_DROPOUT))
    args.lora_target_modules = list(model.get("lora_target_modules", _LORA_TARGET_MODULES))
    return args


# ── Round config (retry curriculum) ──────────────────────────────────────────

def _apply_round_config(args: argparse.Namespace) -> argparse.Namespace:
    """Resolve dataset / output-dir / LoRA config from retry_curriculum.json for --round."""
    curriculum_path = _RETRY_DIR / "retry_curriculum.json"
    if not curriculum_path.exists():
        print(f"[train] ERROR: curriculum not found: {curriculum_path}", file=sys.stderr)
        sys.exit(1)
    curriculum = json.loads(curriculum_path.read_text(encoding="utf-8"))
    round_def  = curriculum.get(args.round)
    if round_def is None:
        avail = ", ".join(sorted(curriculum))
        print(f"[train] ERROR: unknown round '{args.round}'. Available: {avail}",
              file=sys.stderr)
        sys.exit(1)

    round_dir   = _RETRY_DIR / "rounds" / args.round
    chatml_path = round_dir / "retry_chatml.jsonl"
    if not chatml_path.exists():
        print(f"[train] ERROR: round '{args.round}' not built yet: {chatml_path}",
              file=sys.stderr)
        print(f"  Run: python local_ai/retry/build_retry_round.py --round {args.round}",
              file=sys.stderr)
        sys.exit(1)

    lora = round_def.get("lora", {})
    args.dataset               = str(chatml_path)
    args.output_dir            = str(_REPO_ROOT / "local_ai" / "sft" / "artifacts" /
                                     f"retry_{args.round}")
    args.epochs                = int(round_def.get("epochs", 2))
    args.limit                 = None
    args.lora_r                = int(lora.get("r",       _LORA_R))
    args.lora_alpha            = int(lora.get("alpha",   _LORA_ALPHA))
    args.lora_dropout          = float(lora.get("dropout", _LORA_DROPOUT))
    args.lora_target_modules   = list(_LORA_TARGET_MODULES)
    args.job                   = None
    args.model_profile_name    = None
    args.dataset_profile_name  = None
    return args


def _update_round_registry(round_name: str, updates: dict) -> None:
    """Merge *updates* into the round_registry entry for *round_name*."""
    registry_path = _RETRY_DIR / "round_registry.json"
    if not registry_path.exists():
        return
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        data.setdefault("rounds", {}).setdefault(round_name, {}).update(updates)
        registry_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except Exception as exc:
        print(f"[train] WARNING: could not update round registry: {exc}", file=sys.stderr)


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_args(args: argparse.Namespace) -> None:
    errors: list[str] = []
    if not args.dataset:
        errors.append("--dataset is required unless --job is provided")
    if not args.output_dir:
        errors.append("--output-dir is required unless --job is provided")
    if args.dataset and not Path(args.dataset).exists():
        errors.append(f"--dataset not found: {args.dataset}")
    if args.limit is not None and args.limit < 1:
        errors.append("--limit must be >= 1")
    if args.epochs < 1:
        errors.append("--epochs must be >= 1")
    if errors:
        for e in errors:
            print(f"[train] ERROR: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


# ── Dependency check ──────────────────────────────────────────────────────────

def _check_deps() -> None:
    import importlib.util
    missing = [p for p in ("torch", "transformers", "peft", "accelerate")
               if importlib.util.find_spec(p) is None]
    if missing:
        print(f"[train] ERROR: missing packages: {', '.join(missing)}",
              file=sys.stderr, flush=True)
        print("[train] Install with:", file=sys.stderr, flush=True)
        print("  pip install torch --index-url https://download.pytorch.org/whl/cu124",
              file=sys.stderr, flush=True)
        non_torch = [p for p in missing if p != "torch"]
        if non_torch:
            print(f"  pip install {' '.join(non_torch)}", file=sys.stderr, flush=True)
        sys.exit(1)


# ── Dataset ───────────────────────────────────────────────────────────────────

def _build_dataset(path: Path, tokenizer, limit: int | None):
    """Return a torch.utils.data.Dataset built from sft_chatml.jsonl.

    Defined as a factory so JsonlDataset is declared inside _run_training()
    after torch is imported — avoiding any module-level torch dependency.
    Called from _run_training() only.
    """
    import torch  # already imported by caller; this is just a local alias

    class JsonlDataset(torch.utils.data.Dataset):
        """Loads, tokenizes, and stores all examples as tensors at init time."""

        def __init__(self) -> None:
            self._items: list[dict] = []
            _log("loading jsonl dataset ...")
            with path.open(encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    obj = json.loads(raw)
                    messages = obj.get("messages", [])
                    if not messages:
                        continue
                    text: str = tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=False
                    )
                    self._tokenize_and_append(text)
                    if limit and len(self._items) >= limit:
                        break

            if not self._items:
                raise RuntimeError(f"no training examples found in {path}")

        def _tokenize_and_append(self, text: str) -> None:
            enc = tokenizer(
                text,
                truncation=True,
                max_length=_MAX_SEQ_LEN,
                padding=False,
                return_tensors=None,
            )
            ids  = enc["input_ids"]
            mask = enc["attention_mask"]
            self._items.append({
                "input_ids":      torch.tensor(ids,  dtype=torch.long),
                "attention_mask": torch.tensor(mask, dtype=torch.long),
                "labels":         torch.tensor(ids,  dtype=torch.long),
            })

        def __len__(self) -> int:
            return len(self._items)

        def __getitem__(self, index: int) -> dict:
            return self._items[index]

    return JsonlDataset()


# ── Padding collator ──────────────────────────────────────────────────────────

class _PadCollator:
    """Pad a batch to the longest sequence. Pure torch, no external deps."""

    def __init__(self, pad_token_id: int) -> None:
        self.pad_id = pad_token_id

    def __call__(self, batch: list[dict]) -> dict:
        import torch

        max_len = max(item["input_ids"].shape[0] for item in batch)
        ids_out, mask_out, labels_out = [], [], []
        for item in batch:
            pad = max_len - item["input_ids"].shape[0]
            ids_out.append(
                torch.nn.functional.pad(item["input_ids"],      (0, pad), value=self.pad_id))
            mask_out.append(
                torch.nn.functional.pad(item["attention_mask"], (0, pad), value=0))
            labels_out.append(
                torch.nn.functional.pad(item["labels"],         (0, pad), value=-100))
        return {
            "input_ids":      torch.stack(ids_out),
            "attention_mask": torch.stack(mask_out),
            "labels":         torch.stack(labels_out),
        }


# ── Training ──────────────────────────────────────────────────────────────────

def _run_training(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    report_dir = _HERE / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.monotonic()
    report: dict = {
        "timestamp":  _now(),
        "success":    False,
        "status":     "started",
        "model":      args.model,
        "dataset":    str(Path(args.dataset)),
        "limit":      args.limit,
        "epochs":     args.epochs,
        "output_dir": str(output_dir),
    }
    _write_report(report, report_dir)

    try:
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

        # ── CUDA / dtype ──────────────────────────────────────────────────────
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            props = torch.cuda.get_device_properties(0)
            dtype: torch.dtype = torch.bfloat16 if props.major >= 8 else torch.float16
            _log(f"CUDA: {torch.cuda.get_device_name(0)}"
                 f"  {torch.cuda.memory_allocated(0) // (1024**2)} MB /"
                 f" {props.total_memory // (1024**2)} MB")
        else:
            dtype = torch.float32
            _log("WARNING: no CUDA — CPU training will be very slow")
        _log(f"device={device}  dtype={dtype}")

        # ── Tokenizer ─────────────────────────────────────────────────────────
        _log("loading tokenizer ...")
        tokenizer = AutoTokenizer.from_pretrained(
            args.model, trust_remote_code=True, padding_side="right"
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        _log(f"tokenizer OK  vocab_size={tokenizer.vocab_size}")

        # ── Dataset ───────────────────────────────────────────────────────────
        _log("tokenizing ...")
        dataset = _build_dataset(Path(args.dataset), tokenizer, args.limit)
        lens = [item["input_ids"].shape[0] for item in dataset]
        _log(f"{len(dataset)} examples  seq_len min={min(lens)} max={max(lens)}")

        # ── Base model ────────────────────────────────────────────────────────
        _log("loading model ...")
        load_kw: dict = {"trust_remote_code": True, "torch_dtype": dtype}
        if device == "cuda":
            load_kw["device_map"] = "auto"
        model = AutoModelForCausalLM.from_pretrained(args.model, **load_kw)
        model.config.use_cache = False
        # Required for gradient checkpointing with PEFT — must be called on
        # the base model before get_peft_model wraps it.
        model.enable_input_require_grads()
        if device == "cuda":
            _log(f"model loaded  CUDA: {torch.cuda.memory_allocated(0) // (1024**2)} MB")

        # ── LoRA ──────────────────────────────────────────────────────────────
        _log("applying LoRA ...")
        lora_cfg = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=getattr(args, "lora_r", _LORA_R),
            lora_alpha=getattr(args, "lora_alpha", _LORA_ALPHA),
            lora_dropout=getattr(args, "lora_dropout", _LORA_DROPOUT),
            target_modules=getattr(args, "lora_target_modules", _LORA_TARGET_MODULES),
            bias="none",
            inference_mode=False,
        )
        model = get_peft_model(model, lora_cfg)
        model.print_trainable_parameters()

        # ── Trainer ───────────────────────────────────────────────────────────
        _log("building trainer ...")
        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=_BATCH_SIZE,
            gradient_accumulation_steps=_GRAD_ACCUM,
            learning_rate=_LEARNING_RATE,
            warmup_steps=_WARMUP_STEPS,
            bf16=(dtype == torch.bfloat16),
            fp16=(dtype == torch.float16),
            gradient_checkpointing=True,
            logging_steps=1,
            save_strategy="no",
            remove_unused_columns=False,
            dataloader_num_workers=0,
            report_to="none",
            no_cuda=(device == "cpu"),
        )
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            data_collator=_PadCollator(pad_token_id=tokenizer.pad_token_id),
        )

        # ── Train ─────────────────────────────────────────────────────────────
        _log("starting training ...")
        result = trainer.train()
        loss   = result.training_loss
        _log(f"training finished  loss={loss:.4f}")

        # ── Save adapter ──────────────────────────────────────────────────────
        _log("saving adapter ...")
        model.save_pretrained(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))

        elapsed = time.monotonic() - t_start
        report.update({
            "success":        True,
            "status":         "success",
            "device":         device,
            "dtype":          str(dtype),
            "examples":       len(dataset),
            "lora_r":         getattr(args, "lora_r", _LORA_R),
            "lora_alpha":     getattr(args, "lora_alpha", _LORA_ALPHA),
            "lora_dropout":   getattr(args, "lora_dropout", _LORA_DROPOUT),
            "target_modules": getattr(args, "lora_target_modules", _LORA_TARGET_MODULES),
            "train_loss":     round(loss, 6),
            "elapsed_s":      round(elapsed, 1),
        })
        report_path = _write_report(report, report_dir)
        _register_train_experiment(args, report, report_path)

        # Update round registry if this was a --round training run
        if getattr(args, "round", None):
            _update_round_registry(args.round, {
                "trained":     True,
                "trained_at":  _now(),
                "adapter_path": str(output_dir),
                "train_loss":  round(loss, 6),
            })

        _log("done")
        print(f"  adapter    >> {output_dir}", flush=True)
        print(f"  train_loss = {loss:.4f}", flush=True)
        print(f"  elapsed    = {elapsed:.0f}s", flush=True)
        print(f"  report     >> {report_dir / 'train_report.json'}", flush=True)
        print(flush=True)
        if getattr(args, "round", None):
            print("Next step:", flush=True)
            print(f'  python local_ai/sft/benchmark_lora.py '
                  f'--benchmark c_exam_2025_strict_seeded '
                  f'--adapter "{output_dir}" '
                  f'--round {args.round}', flush=True)
        else:
            print("Next step:", flush=True)
            print(f'  python local_ai/sft/evaluate_lora.py --adapter "{output_dir}" \\',
                  flush=True)
            print('      --prompt "Write a C program that prints Hello."', flush=True)

    except Exception as exc:
        elapsed  = time.monotonic() - t_start
        tb_str   = traceback.format_exc()
        report.update({
            "success":    False,
            "status":     "failed",
            "error":      str(exc),
            "traceback":  tb_str,
            "elapsed_s":  round(elapsed, 1),
        })
        _write_report(report, report_dir)
        print(f"\n[train] FAILED after {elapsed:.1f}s", file=sys.stderr, flush=True)
        print(tb_str, file=sys.stderr, flush=True)
        print(f"[train] report >> {report_dir / 'train_report.json'}", file=sys.stderr, flush=True)
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    global _VERBOSE
    try:
        args = _parse_args()

        # --round and --job are mutually exclusive
        if getattr(args, "round", None) and args.job:
            print("[train] ERROR: --round and --job are mutually exclusive", file=sys.stderr)
            sys.exit(1)

        if getattr(args, "round", None):
            args = _apply_round_config(args)
        elif args.job:
            args = _apply_job_config(args)
        else:
            # Direct --dataset / --output-dir; ensure profile names are set
            args.model_profile_name   = None
            args.dataset_profile_name = None

        _VERBOSE = args.verbose
        _validate_args(args)

        print(
            f"[train] model={args.model} dataset={args.dataset} "
            f"epochs={args.epochs} limit={args.limit}",
            flush=True,
        )

        _check_deps()
        _run_training(args)

    except SystemExit:
        raise
    except ConfigError as exc:
        print(format_config_error(exc), file=sys.stderr, flush=True)
        sys.exit(1)
    except Exception as exc:
        tb_str = traceback.format_exc()
        print(f"\n[train] FATAL: {exc}", file=sys.stderr, flush=True)
        print(tb_str, file=sys.stderr, flush=True)
        try:
            _write_report(
                {"timestamp": _now(), "success": False, "status": "fatal",
                 "error": str(exc), "traceback": tb_str},
                _HERE / "reports",
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
