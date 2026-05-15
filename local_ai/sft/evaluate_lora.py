#!/usr/bin/env python3
"""Load a saved LoRA adapter and run a single-prompt inference.

Usage:
  python local_ai/sft/evaluate_lora.py \
      --adapter local_ai/sft/artifacts/test_lora \
      --prompt "Write a C program that prints Hello."

Optional flags:
  --model       Base model ID (default: auto-detected from adapter_config.json)
  --max-tokens  Max new tokens to generate (default: 512)
  --no-lora     Run base model only, skipping adapter load
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Dependency check ──────────────────────────────────────────────────────────

def _check_deps() -> None:
    missing = []
    for pkg in ("torch", "transformers", "peft"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[eval] Missing packages: {', '.join(missing)}", file=sys.stderr)
        print("[eval] Install with:", file=sys.stderr)
        print("  pip install torch --index-url https://download.pytorch.org/whl/cu121", file=sys.stderr)
        print(f"  pip install {' '.join(p for p in missing if p != 'torch')}", file=sys.stderr)
        sys.exit(1)

_check_deps()

import torch  # noqa: E402
from peft import PeftModel  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

_DEFAULT_MODEL   = "Qwen/Qwen2.5-Coder-3B-Instruct"
_DEFAULT_TOKENS  = 512


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_dtype() -> torch.dtype:
    if not torch.cuda.is_available():
        return torch.float32
    major = torch.cuda.get_device_properties(0).major
    return torch.bfloat16 if major >= 8 else torch.float16


def _resolve_base_model(adapter_dir: Path, override: str | None) -> str:
    if override:
        return override
    cfg_path = adapter_dir / "adapter_config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            base = cfg.get("base_model_name_or_path", "")
            if base:
                return base
        except Exception:
            pass
    return _DEFAULT_MODEL


# ── Inference ─────────────────────────────────────────────────────────────────

def evaluate(args: argparse.Namespace) -> None:
    adapter_dir = Path(args.adapter)
    if not args.no_lora and not adapter_dir.exists():
        print(f"[eval] ERROR: adapter directory not found: {adapter_dir}", file=sys.stderr)
        print("[eval] Run train_lora.py first, or use --no-lora to test the base model.",
              file=sys.stderr)
        sys.exit(1)

    base_model_id = _resolve_base_model(adapter_dir, args.model)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype  = _detect_dtype()

    print(f"[eval] base_model={base_model_id}")
    print(f"[eval] device={device}  dtype={dtype}")
    if not args.no_lora:
        print(f"[eval] adapter={adapter_dir}")

    # ── Tokenizer ──
    tok_path = str(adapter_dir) if (adapter_dir / "tokenizer_config.json").exists() else base_model_id
    print(f"[eval] loading tokenizer from {tok_path} ...")
    tokenizer = AutoTokenizer.from_pretrained(tok_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── Base model ──
    print(f"[eval] loading base model {base_model_id} ...")
    load_kwargs: dict = {"trust_remote_code": True, "torch_dtype": dtype}
    if device == "cuda":
        load_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(base_model_id, **load_kwargs)

    # ── Adapter ──
    if not args.no_lora:
        print("[eval] loading LoRA adapter ...")
        model = PeftModel.from_pretrained(model, str(adapter_dir))
        model = model.merge_and_unload()  # merge for faster inference

    model.eval()

    # ── Build prompt using chat template ──
    messages = [
        {"role": "system", "content": "You are a C programming assistant. Output exactly one complete C99 program. Do not explain."},
        {"role": "user",   "content": args.prompt},
    ]
    prompt_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device if hasattr(model, "device") else device)

    print(f"[eval] generating (max_new_tokens={args.max_tokens}) ...")
    print()

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=args.max_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Strip the prompt tokens from output
    new_ids = output_ids[0][inputs["input_ids"].shape[1]:]
    response = tokenizer.decode(new_ids, skip_special_tokens=True)

    print("─" * 60)
    print(response)
    print("─" * 60)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run inference with a saved LoRA adapter"
    )
    parser.add_argument("--adapter",    required=True,
                        help="Path to saved LoRA adapter directory")
    parser.add_argument("--prompt",     required=True,
                        help="User prompt to send to the model")
    parser.add_argument("--model",      default=None,
                        help="Base model ID (auto-detected from adapter_config.json if omitted)")
    parser.add_argument("--max-tokens", type=int, default=_DEFAULT_TOKENS,
                        help=f"Max new tokens (default: {_DEFAULT_TOKENS})")
    parser.add_argument("--no-lora",    action="store_true",
                        help="Run base model only, skip adapter load")
    args = parser.parse_args()
    evaluate(args)


if __name__ == "__main__":
    main()