"""Quick compile diagnostic — run directly to debug gcc failures."""
import json, subprocess, tempfile, re
from pathlib import Path

lines = Path(__file__).parent.parent / "ingest/output/training/code_generation.jsonl"
rec = json.loads(lines.read_text(encoding="utf-8").splitlines()[0])
output = rec.get("output", "")

m = re.search(r"```(?:c|C)?\s*\n(.*?)```", output, re.DOTALL)
code = m.group(1).strip() if m else output.strip()

wd = Path(tempfile.mkdtemp())
src = wd / "test.c"
exe = wd / "test.exe"
src.write_text(code, encoding="utf-8")
print("source:", src)
print("code length:", len(code))

gcc = r"C:/msys64/ucrt64/bin/gcc.exe"
cmd = [gcc, "-std=c99", "-o", str(exe), str(src), "-lm"]
print("cmd:", " ".join(cmd))

result = subprocess.run(cmd, capture_output=True, timeout=15)
print("returncode:", result.returncode)
print("stdout raw:", result.stdout[:300])
print("stderr raw:", result.stderr[:500])

for enc in ("utf-8", "cp950", "latin-1"):
    try:
        decoded = result.stderr.decode(enc, errors="replace")
        if decoded.strip():
            print(f"stderr ({enc}):", decoded[:400])
            break
    except Exception:
        pass
