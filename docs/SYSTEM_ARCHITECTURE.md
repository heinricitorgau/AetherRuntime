# System Architecture

## Runtime Path

```mermaid
flowchart LR
    User["User"]
    Launcher["local_ai/run.ps1 or run.sh"]
    CLI["claw CLI<br/>Rust runtime"]
    Proxy["local_ai/proxy.py<br/>Anthropic-compatible proxy"]
    Ollama["Bundled Ollama"]
    Model["Local model<br/>qwen2.5-coder"]
    Logs["runtime logs<br/>proxy.err.log"]

    User --> Launcher
    Launcher --> CLI
    Launcher --> Proxy
    Launcher --> Ollama
    CLI -->|"Anthropic Messages API"| Proxy
    Proxy -->|"OpenAI-compatible chat API"| Ollama
    Ollama --> Model
    Proxy --> Logs
```

## Benchmark And Training Path

```mermaid
flowchart TB
    Cases["eval cases and SFT records"]
    Bench["benchmark/run_baseline.py"]
    ProxyCfg["proxy /config check"]
    Proxy["local_ai/proxy.py"]
    Ollama["Bundled Ollama"]
    Results["results.jsonl<br/>raw_outputs.jsonl"]
    Score["benchmark/scoring.py"]
    Reports["report.json / report.md"]
    Analysis["report_analysis.py"]
    SFT["local_ai/sft training pipeline"]
    Artifacts["LoRA artifacts and reports"]

    Cases --> Bench
    Bench --> ProxyCfg
    ProxyCfg --> Proxy
    Bench --> Proxy
    Proxy --> Ollama
    Bench --> Results
    Results --> Score
    Score --> Reports
    Results --> Analysis
    Cases --> SFT
    SFT --> Artifacts
```

## Main Components

| Component | Role |
| --- | --- |
| `rust/` | CLI and runtime implementation |
| `local_ai/run.ps1`, `local_ai/run.sh` | Start bundled Ollama, proxy, and the CLI |
| `local_ai/proxy.py` | Translate Anthropic-style requests to Ollama-compatible requests |
| `local_ai/benchmark/` | Run golden baselines, score outputs, and analyze regressions |
| `local_ai/eval_cases/` | Task definitions and expected validation signals |
| `local_ai/sft/` | Fine-tuning experiments, artifacts, and comparison reports |
| `local_ai/runtime/` | Bundled runtime assets, logs, and model cache |

## Reliability Notes

- The proxy exposes `/health` for readiness and `/config` for effective timeout inspection.
- Benchmark runs verify proxy timeout configuration before sending tasks.
- Strict benchmark mode uses code-only prompting and skips repair retries so model-quality measurements are not distorted by avoidable runtime retries.
- Runtime logs in `local_ai/runtime/logs/proxy.err.log` show effective request timeout, socket timeout, request duration, and repair-loop behavior.
