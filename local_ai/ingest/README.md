# local_ai/ingest — Offline Document Ingestion Pipeline

Converts C programming PDFs into structured, model-ready chunks for local AI and RAG.

```
PDF → HTML → cleaned HTML → chunks.json
```

## Why structured HTML beats raw PDF for small models

| Raw PDF | Structured HTML chunks |
|---------|----------------------|
| OCR noise, layout artifacts | Clean prose and code separated |
| Entire document in one context | Small, focused chunks |
| Font/position metadata mixed in | Semantic tags only (h2, p, pre) |
| 4 096-token context fills fast | Each chunk ≈ 50–300 tokens |
| Model hallucinates from noise | Model sees only the relevant section |

Small models like qwen2.5-coder:1.5b and :3b have limited context windows and
degrade quickly when fed noisy input. Pre-processing to clean semantic chunks
lets the model focus on meaning rather than layout recovery.

## Quick start

```bash
# Step 1 — PDF → HTML (tries pymupdf, then pdfminer, then pypdf)
python local_ai/ingest/pdf_to_html.py textbook.pdf -o local_ai/ingest/output/textbook.html

# Step 2 — HTML → cleaned semantic HTML
python local_ai/ingest/html_cleaner.py local_ai/ingest/output/textbook.html

# Step 3 — cleaned HTML → chunk JSON
python local_ai/ingest/chunker.py local_ai/ingest/output/textbook.cleaned.html
```

Output after three steps:
```
local_ai/ingest/output/
├── textbook.html             ← raw extraction
├── textbook.cleaned.html     ← semantic tags only
└── textbook.chunks.json      ← ready for RAG / model prompts
```

## Tool requirements

Each step uses a different library. Only installed packages are tried;
nothing is downloaded automatically.

| Step | Primary | Fallback 1 | Fallback 2 |
|------|---------|------------|------------|
| pdf_to_html.py | pymupdf | pdfminer.six | pypdf |
| html_cleaner.py | stdlib only | — | — |
| chunker.py | stdlib only | — | — |

Install recommendation (offline-friendly, one package):
```
pip install pymupdf
```

## Chunk format

```json
{
  "id": "textbook_cleaned_0012",
  "source_file": "textbook.cleaned.html",
  "section": "Chapter 3: Arrays and Pointers",
  "content": "A pointer stores the address of another variable ...",
  "content_type": "text",
  "estimated_tokens": 94
}
```

`content_type` is one of:
- `text` — prose explanation
- `code` — C source code from a `<pre>` block
- `question` — detected exam question or exercise

## Chunking strategy

Chunk boundaries are placed at:
1. **Heading tags** (`h1`–`h4`) — natural section boundaries
2. **Code blocks** (`<pre>`) — always their own chunk, never merged
3. **Soft size ceiling** — text paragraphs merge up to ~3 000 chars, then split

This avoids mid-sentence splits and keeps code examples isolated from prose,
which is important because small models handle mixed code+prose poorly.

## Pipeline design

```
pdf_to_html.py     reads: PDF
                  writes: .html  (heading/code heuristics; font-size based)

html_cleaner.py    reads: .html (any source)
                  writes: .cleaned.html
                  keeps:  h1-h4, p, pre, code, ul, ol, li, table, tr, td, th
                  strips: script, style, svg, nav, inline CSS, positioning tags

chunker.py         reads: .cleaned.html
                  writes: .chunks.json
                  emits:  one JSON object per semantic chunk
```

Each script is also importable as a module:
```python
from local_ai.ingest.pdf_to_html import pdf_to_html
from local_ai.ingest.html_cleaner import clean_html
from local_ai.ingest.chunker import chunk_html

html_path     = pdf_to_html(Path("textbook.pdf"), output / "textbook.html")
cleaned_path  = clean_html(html_path)
chunks_path   = chunk_html(cleaned_path)
```

## Connecting to the existing RAG index

The project's `local_ai/rag/` directory already has a BM25-style keyword index
(`build_index.py` + `search_docs.py`). To make chunks searchable:

1. Copy or symlink `chunks.json` into `local_ai/rag/docs/`
2. Run `python local_ai/rag/build_index.py` to rebuild the index
3. The proxy will pick up matching chunks via `search_docs.search()`

Future enhancement: extend `build_index.py` to parse the `section`/`content`
fields from chunks.json natively, so each chunk becomes a distinct RAG passage
with its section as the heading.

## Future directions

- **Vector embeddings**: once a local embedding model (e.g. `nomic-embed-text`)
  is available, replace BM25 with cosine similarity search over chunk embeddings.
- **Vector DB**: FAISS or `chromadb` in local-only mode for approximate nearest
  neighbour search; both run fully offline.
- **Tutoring / QA**: feed retrieved chunks as context into the proxy's system
  prompt; the model answers questions grounded in the textbook.
- **Metadata extraction**: `metadata/` directory is reserved for per-document
  metadata (year, subject, chapter map) to enable filtered retrieval.

## Directory layout

```
local_ai/ingest/
├── pdf_to_html.py       ← Step 1: PDF → HTML
├── html_cleaner.py      ← Step 2: messy HTML → semantic HTML
├── chunker.py           ← Step 3: HTML → chunks.json
├── pdf_to_html/         ← reserved: multi-strategy output / debug files
├── html_cleaner/        ← reserved: per-document cleaning configs
├── chunker/             ← reserved: custom chunking profiles
├── metadata/            ← reserved: document metadata JSON
├── output/              ← default output directory
└── README.md            ← this file
```
