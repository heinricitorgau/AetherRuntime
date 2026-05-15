# Minimal LoRA Training Pipeline

> **This is a tiny overfit sanity test — NOT production training.**
>
> Purpose: verify that `train → save adapter → load adapter → inference` works
> end-to-end on the local machine before committing to a full SFT run.

---

## What This Does

1. Loads `Qwen/Qwen2.5-Coder-3B-Instruct` from HuggingFace (or local cache)
2. Applies LoRA on `q/k/v/o/gate/up/down_proj` (r=8, α=16, dropout=0.05)
3. Fine-tunes on N examples from `sft_chatml.jsonl` for 1 epoch
4. Saves the adapter to `artifacts/<run_name>/`
5. Optionally runs a single-prompt inference to confirm the adapter loads

It intentionally uses `batch_size=1` and `gradient_accumulation=4` so it fits in an RTX 4060 8 GB VRAM budget.

---

## Prerequisites

### Python packages

```powershell
# PyTorch with CUDA 12.1 (RTX 4060)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# HuggingFace ecosystem
pip install transformers peft accelerate sentencepiece safetensors
```

### Other requirements

- Ollama does NOT need to be running — this pipeline talks directly to HuggingFace.
- The dataset must pass `sft_readiness_check.py` before training:
  ```powershell
  python local_ai/training_quality/sft_readiness_check.py
  ```

---

## Quick Start

### Step 1 — Tiny overfit test (8 examples, 1 epoch)

```powershell
python local_ai/sft/train_lora.py `
    --dataset local_ai/training_quality/reports/sft_chatml.jsonl `
    --limit 8 `
    --epochs 1 `
    --output-dir local_ai/sft/artifacts/test_lora
```

Expected output:
```
[train] device=cuda  dtype=torch.float16  model=Qwen/Qwen2.5-Coder-3B-Instruct
[train] loading tokenizer ...
[train] loading ... (8 examples)
[train] loading Qwen/Qwen2.5-Coder-3B-Instruct ...
trainable params: 13,631,488 || all params: 3,099,955,200 || trainable%: 0.4398
[train] starting ...
...
  adapter    → local_ai/sft/artifacts/test_lora
  train_loss = 0.xxxx
  elapsed    = ~180s
```

### Step 2 — Verify adapter loads and generates output

```powershell
python local_ai/sft/evaluate_lora.py `
    --adapter local_ai/sft/artifacts/test_lora `
    --prompt "Write a C program that prints Hello."
```

Expected: a complete `#include <stdio.h> ... int main() ... printf("Hello") ...` program.

### Step 3 — Run base model for comparison (no adapter)

```powershell
python local_ai/sft/evaluate_lora.py `
    --adapter local_ai/sft/artifacts/test_lora `
    --prompt "Write a C program that prints Hello." `
    --no-lora
```

---

## File Structure

```
local_ai/sft/
  train_lora.py          main training script
  evaluate_lora.py       adapter load + single-prompt inference
  configs/
    default_lora.json    LoRA hyperparameters (reference, not loaded by script)
  artifacts/
    test_lora/           saved LoRA adapter (adapter_model.bin + adapter_config.json)
  reports/
    train_report.json    timing, loss, config snapshot from last run
```

---

## LoRA Config

| Parameter | Value |
|-----------|------:|
| r | 8 |
| lora_alpha | 16 |
| lora_dropout | 0.05 |
| target_modules | q/k/v/o/gate/up/down_proj |
| batch_size | 1 |
| grad_accum | 4 |
| learning_rate | 2e-4 |
| warmup_steps | 2 |
| max_seq_len | 1024 |

`fp16` is used on RTX 4060 (sm_89, Ampere+). `bfloat16` is used on sm_80+.
CPU fallback uses `float32` but will be extremely slow.

---

## RTX 4060 8 GB Notes

- 3B model in fp16 uses ~6 GB VRAM at rest
- With gradient checkpointing + batch=1, peak usage stays under 8 GB
- `device_map="auto"` is used — model layers map to GPU automatically
- If you get OOM: reduce `--limit` to 4, or add `--max-length 512` (not yet exposed as flag)

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: torch` | Run the pip install commands above |
| CUDA OOM during training | Reduce `--limit` to 4 |
| CUDA OOM during inference | Model too large for VRAM — use CPU (slow) or reduce dtype |
| `adapter not found` | Run `train_lora.py` first |
| Loss = 0.0 or NaN | Usually dtype mismatch — check that fp16/bf16 matches GPU capability |
| Model output is garbage | Expected for 1-epoch overfit test — this only verifies the pipeline works |

---

## What "Overfit Test" Means

Training on 8 examples for 1 epoch is not meaningful learning — the model will not improve on held-out data. The only thing this run proves is:

1. The training loop does not crash
2. The adapter file is saved correctly
3. `PeftModel.from_pretrained` can reload the adapter
4. The model can generate tokens after adapter merge

To do real fine-tuning: use all `~50` accepted records, run `3–5` epochs, and run the full benchmark before and after to measure improvement.

---

## Comparing Before and After Fine-tuning

```powershell
# Step 1: establish golden baseline (before fine-tuning)
python local_ai/benchmark/run_baseline.py --strict-code-only --run-id pre_sft

# Step 2: lock it
python local_ai/benchmark/lock_golden_baseline.py --run-id pre_sft

# Step 3: load fine-tuned model into Ollama and re-run
python local_ai/benchmark/run_baseline.py --strict-code-only --run-id post_sft

# Step 4: compare
python local_ai/benchmark/compare_against_golden.py --run-id post_sft
```
