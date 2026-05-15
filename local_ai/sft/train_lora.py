#!/usr/bin/env python3
"""Minimal LoRA fine-tuning for Qwen2.5-Coder-3B-Instruct.

This is a tiny overfit test — NOT production training.
Purpose: verify that train -> save adapter -> load adapter -> inference works end-to-end.

Usage:
  python local_ai/sft/train_lora.py \
      --dataset local_ai/training_quality/reports/sft_chatml.jsonl \
      --limit 8 \
      --epochs 1 \
      --output-dir local_ai/sft/artifacts/test_lora

Required packages:
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
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

import torch  # type: ignore[import-not-found]

# Env-var guards
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

_HERE = Path(__file__).resolve().parent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(msg: str) -> None:
    print(f"[train] {msg}", flush=True)


def _write_report(report: dict, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "train_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── Arg parsing ───────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal LoRA fine-tuning — overfit sanity check only"
    )
    parser.add_argument("--dataset",    required=True,
                        help="Path to sft_chatml.jsonl")
    parser.add_argument("--limit",      type=int, default=None,
                        help="Max examples to load (default: all)")
    parser.add_argument("--epochs",     type=int, default=1,
                        help="Training epochs (default: 1)")
    parser.add_argument("--output-dir", required=True,
                        help="Directory to save LoRA adapter")
    parser.add_argument("--model",      default=_DEFAULT_MODEL,
                        help=f"Base model ID (default: {_DEFAULT_MODEL})")
    return parser.parse_args()


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_args(args: argparse.Namespace) -> None:
    errors: list[str] = []
    if not Path(args.dataset).exists():
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
    missing = []
    for pkg in ("torch", "transformers", "peft", "accelerate"):
        # Use find_spec so we don't accidentally load the stubs above
        import importlib.util
        if importlib.util.find_spec(pkg) is None:
            missing.append(pkg)
    if missing:
        print(f"[train] ERROR: missing packages: {', '.join(missing)}",
              file=sys.stderr, flush=True)
        print("[train] Install with:", file=sys.stderr, flush=True)
        print("  pip install torch --index-url https://download.pytorch.org/whl/cu121",
              file=sys.stderr, flush=True)
        non_torch = [p for p in missing if p != "torch"]
        if non_torch:
            print(f"  pip install {' '.join(non_torch)}", file=sys.stderr, flush=True)
        sys.exit(1)


# ── JsonlDataset ──────────────────────────────────────────────────────────────

class JsonlDataset(torch.utils.data.Dataset):
    """Loads sft_chatml.jsonl, tokenizes, stores tensors."""

    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> dict:
        return self._items[idx]


def _make_jsonl_dataset(
    path: Path,
    tokenizer: object,
    limit: int | None,
    max_len: int,
) -> JsonlDataset:
    """Load, apply chat template, tokenize, return JsonlDataset."""
    items: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            obj = json.loads(raw)
            messages = obj.get("messages", [])
            if not messages:
                continue
            text: str = tokenizer.apply_chat_template(  # type: ignore[union-attr]
                messages, tokenize=False, add_generation_prompt=False
            )
            enc = tokenizer(  # type: ignore[operator]
                text,
                truncation=True,
                max_length=max_len,
                padding=False,
                return_tensors=None,
            )
            ids  = enc["input_ids"]
            mask = enc["attention_mask"]
            items.append({
                "input_ids":      torch.tensor(ids,  dtype=torch.long),
                "attention_mask": torch.tensor(mask, dtype=torch.long),
                "labels":         torch.tensor(ids,  dtype=torch.long),  # causal LM
            })
            if limit and len(items) >= limit:
                break

    if not items:
        raise RuntimeError(f"no training examples found in {path}")

    return JsonlDataset(items)


# ── Padding collator (no external deps) ──────────────────────────────────────

class _PadCollator:
    """Pad a batch to the longest sequence using only torch primitives."""

    def __init__(self, pad_token_id: int) -> None:
        self.pad_id = pad_token_id

    def __call__(self, batch: list[dict]) -> dict:
        import torch  # type: ignore[import-not-found]  # noqa: PLC0415

        max_len = max(item["input_ids"].shape[0] for item in batch)
        input_ids_out, mask_out, labels_out = [], [], []
        for item in batch:
            n   = item["input_ids"].shape[0]
            pad = max_len - n
            input_ids_out.append(
                torch.nn.functional.pad(item["input_ids"],      (0, pad), value=self.pad_id)
            )
            mask_out.append(
                torch.nn.functional.pad(item["attention_mask"], (0, pad), value=0)
            )
            labels_out.append(
                torch.nn.functional.pad(item["labels"],         (0, pad), value=-100)
            )
        return {
            "input_ids":      torch.stack(input_ids_out),
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
        # ── Imports ───────────────────────────────────────────────────────────
        _log("importing torch / peft / transformers ...")
        import torch  # type: ignore[import-not-found]  # noqa: PLC0415
        from peft import LoraConfig, TaskType, get_peft_model  # type: ignore[import-not-found]  # noqa: PLC0415
        from transformers import (  # type: ignore[import-not-found]  # noqa: PLC0415
            AutoModelForCausalLM,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
        _log("imports OK")

        # ── CUDA ──────────────────────────────────────────────────────────────
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            props = torch.cuda.get_device_properties(0)
            dtype: torch.dtype = torch.bfloat16 if props.major >= 8 else torch.float16
            total_mb = props.total_memory // (1024 ** 2)
            alloc_mb = torch.cuda.memory_allocated(0) // (1024 ** 2)
            _log(f"CUDA: {torch.cuda.get_device_name(0)}")
            _log(f"CUDA memory: {alloc_mb} MB allocated / {total_mb} MB total")
        else:
            dtype = torch.float32
            _log("WARNING: no CUDA — CPU training will be very slow")

        _log(f"device={device}  dtype={dtype}")

        # ── Tokenizer ─────────────────────────────────────────────────────────
        _log(f"loading tokenizer ({args.model}) ...")
        tokenizer = AutoTokenizer.from_pretrained(
            args.model,
            trust_remote_code=True,
            padding_side="right",
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        _log(f"tokenizer loaded  vocab_size={tokenizer.vocab_size}")

        # ── Dataset ───────────────────────────────────────────────────────────
        _log(f"loading jsonl dataset ({args.dataset}) ...")
        _log("tokenizing ...")
        dataset = _make_jsonl_dataset(
            Path(args.dataset), tokenizer, args.limit, _MAX_SEQ_LEN
        )
        lens = [item["input_ids"].shape[0] for item in dataset]
        _log(f"{len(dataset)} examples  seq_len min={min(lens)} max={max(lens)}")

        # ── Base model ────────────────────────────────────────────────────────
        if device == "cuda":
            _log(f"CUDA before model load: {torch.cuda.memory_allocated(0) // (1024**2)} MB")

        _log(f"loading model ({args.model}) ...")
        load_kw: dict = {"trust_remote_code": True, "torch_dtype": dtype}
        if device == "cuda":
            load_kw["device_map"] = "auto"

        model = AutoModelForCausalLM.from_pretrained(args.model, **load_kw)
        model.config.use_cache = False

        if device == "cuda":
            _log(f"CUDA after model load: {torch.cuda.memory_allocated(0) // (1024**2)} MB")

        # ── LoRA ──────────────────────────────────────────────────────────────
        _log("applying LoRA ...")
        lora_cfg = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=_LORA_R,
            lora_alpha=_LORA_ALPHA,
            lora_dropout=_LORA_DROPOUT,
            target_modules=_LORA_TARGET_MODULES,
            bias="none",
            inference_mode=False,
        )
        model = get_peft_model(model, lora_cfg)
        model.print_trainable_parameters()

        # ── Trainer ───────────────────────────────────────────────────────────
        _log("building trainer ...")
        fp16 = dtype == torch.float16
        bf16 = dtype == torch.bfloat16

        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=_BATCH_SIZE,
            gradient_accumulation_steps=_GRAD_ACCUM,
            learning_rate=_LEARNING_RATE,
            warmup_steps=_WARMUP_STEPS,
            fp16=fp16,
            bf16=bf16,
            gradient_checkpointing=True,
            logging_steps=1,
            save_strategy="no",
            remove_unused_columns=False,
            dataloader_num_workers=0,
            report_to="none",
            no_cuda=(device == "cpu"),
        )

        collator = _PadCollator(pad_token_id=tokenizer.pad_token_id)
        trainer  = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            data_collator=collator,
        )

        # ── Train ─────────────────────────────────────────────────────────────
        _log("starting training ...")
        train_result = trainer.train()
        loss = train_result.training_loss
        _log(f"training finished  loss={loss:.4f}")

        # ── Save adapter ──────────────────────────────────────────────────────
        _log(f"saving adapter to {output_dir} ...")
        model.save_pretrained(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))

        elapsed = time.monotonic() - t_start
        report.update({
            "success":        True,
            "status":         "success",
            "device":         device,
            "dtype":          str(dtype),
            "examples":       len(dataset),
            "lora_r":         _LORA_R,
            "lora_alpha":     _LORA_ALPHA,
            "lora_dropout":   _LORA_DROPOUT,
            "target_modules": _LORA_TARGET_MODULES,
            "train_loss":     round(loss, 6),
            "elapsed_s":      round(elapsed, 1),
        })
        _write_report(report, report_dir)

        _log("done")
        print(f"  adapter    → {output_dir}", flush=True)
        print(f"  train_loss = {loss:.4f}", flush=True)
        print(f"  elapsed    = {elapsed:.0f}s", flush=True)
        print(f"  report     → {report_dir / 'train_report.json'}", flush=True)
        print(flush=True)
        print("Next step:", flush=True)
        print(f'  python local_ai/sft/evaluate_lora.py --adapter "{output_dir}" \\',
              flush=True)
        print('      --prompt "Write a C program that prints Hello."', flush=True)

    except Exception as exc:
        elapsed = time.monotonic() - t_start
        tb_str  = traceback.format_exc()
        report["success"]   = False
        report["status"]    = "failed"
        report["error"]     = str(exc)
        report["traceback"] = tb_str
        report["elapsed_s"] = round(elapsed, 1)
        report_path = _write_report(report, report_dir)
        print(f"\n[train] FAILED after {elapsed:.1f}s", file=sys.stderr, flush=True)
        print(tb_str, file=sys.stderr, flush=True)
        print(f"[train] report → {report_path}", file=sys.stderr, flush=True)
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    try:
        args = _parse_args()
        _validate_args(args)

        _log(f"dataset    = {args.dataset}")
        _log(f"limit      = {args.limit}")
        _log(f"epochs     = {args.epochs}")
        _log(f"output_dir = {args.output_dir}")
        _log(f"model      = {args.model}")

        _check_deps()
        _run_training(args)

    except SystemExit:
        raise
    except Exception as exc:
        tb_str = traceback.format_exc()
        print(f"\n[train] FATAL: {exc}", file=sys.stderr, flush=True)
        print(tb_str, file=sys.stderr, flush=True)
        try:
            report_dir = _HERE / "reports"
            _write_report(
                {"timestamp": _now(), "success": False, "status": "fatal",
                 "error": str(exc), "traceback": tb_str},
                report_dir,
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
