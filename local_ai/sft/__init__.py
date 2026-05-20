"""Supervised Fine-Tuning (SFT) pipeline using LoRA adapters.

Scripts:
  train_lora.py      — fine-tune a base model with LoRA on accepted training records
  evaluate_lora.py   — single-prompt inference with a saved LoRA adapter
  benchmark_lora.py  — run the full benchmark suite against a LoRA adapter

Artifacts are stored under sft/artifacts/<adapter_name>/.
Reports are stored under sft/reports/.
"""
