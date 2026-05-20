"""Data ingestion pipeline: PDF → HTML → chunks → training records.

Stages:
  pdf_to_html      — convert C-exam PDFs to structured HTML
  html_cleaner     — strip layout noise, extract question/answer pairs
  chunker          — semantic chunking into training-sized pieces
  prepare_training — assemble chunks into training JSONL records
  generate_answers — generate model answers for training records
  split_training   — split into accepted / rejected sets
"""
