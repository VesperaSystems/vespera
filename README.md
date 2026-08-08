# Vespera

**Local-first AI deal analysis and due diligence.**

Read a dataroom, cross-check its claims, score it against your investment thesis, and get an indicative valuation range — without your documents ever leaving your machine.

```bash
pip install vespera
vespera review ./dataroom --thesis my-thesis.md
```

Vespera reads the documents in a local folder — contracts, board minutes, financials, NDAs — and produces a structured deal report. All analysis runs on your machine via [Ollama](https://ollama.com). Document contents never leave your network: no cloud upload, no third-party AI provider, no account.

## What it does

Built for the first-pass review in M&A, VC, and PE deals:

- **Due diligence findings** — change-of-control clauses, termination rights, exclusivity, IP ownership, material liabilities, missing signatures — each with severity, a verbatim evidence excerpt, and the source file and page
- **Key metrics** — revenue, ARR, growth, margins, retention, runway, extracted only where explicitly stated, every value cited to its source
- **Contradiction detection** — the same metric reported differently in two documents, conflicting claims across contracts and board minutes, referenced schedules that aren't in the dataroom
- **Deal readiness score** — a reproducible severity-weighted score with a Strong / Balanced / Cautious reading
- **Thesis fit** — write your investment thesis once in Markdown; every deal is scored against it, with aligned points, conflicts, and unknowns
- **Indicative valuation** — a multiples-based screening range with every assumption listed (a range to interrogate, never an appraisal)

```text
Vespera

Reviewing ./dataroom

Documents found: 8

Deal readiness: 44/100 — Balanced reading
Indicative range: 38.4–76.8m GBP (screening only)
Thesis fit: 55/100

Findings:
- Inconsistencies between documents: 3
- Termination rights: 4
- Change-of-control clauses: 1
- Missing signatures: 1

Report: vespera-output/report.md
Evidence: vespera-output/findings.json · vespera-output/deal.json

All document analysis was performed locally.
```

Use it as a library too — the full analysis is one function returning one typed object:

```python
from pathlib import Path
from vespera.deal import analyze_dataroom

analysis = analyze_dataroom(Path("./dataroom"), thesis_path=Path("my-thesis.md"))
print(analysis.score.score, analysis.score.label)
```

## Privacy model

- **No cloud calls for analysis.** Inference runs on a local Ollama server (`localhost` by default).
- **No telemetry, no accounts, no database.** Vespera reads your documents and writes two output files. That's it.
- The only network activity you'll ever need is `ollama pull` to download a model once.

## Quick start

1. Install [Ollama](https://ollama.com/download) — the free app that runs AI models on your own computer — and open it once.

2. Install Vespera (needs Python 3.12+):

   ```bash
   pip install vespera
   ```

3. Point it at a folder of documents (optionally with your thesis):

   ```bash
   vespera review ./dataroom --thesis my-thesis.md
   ```

That's it. On the first run Vespera automatically downloads its default local model (`qwen3:4b`, ~2.6 GB, one-time) and then starts the review. If anything is missing, Vespera tells you exactly what to do.

Prefer a more thorough (slower) review? Use `--model qwen3:8b`. See what's available with `vespera models`.

Try it on the included synthetic example:

```bash
git clone https://github.com/VesperaSystems/vespera
cd vespera
vespera review ./examples/sample-dataroom --thesis ./examples/thesis.md
```

### Commands

```bash
vespera review PATH [--thesis thesis.md] [--model qwen3:8b] [--output vespera-output] [--host http://localhost:11434]
vespera models      # show recommended + locally installed Ollama models
vespera --version
```

The thesis file is plain Markdown — write your criteria however you normally would (see [examples/thesis.md](examples/thesis.md)).

## Supported document types

| Format | Notes |
| --- | --- |
| PDF | Priority format; per-page source references |
| DOCX | Paragraphs and tables; no page numbers |
| TXT / MD | Plain text |

Scanned image-only documents are not analysed in this version (no OCR).

## Limitations

Vespera is automated document triage. It is **not** legal, financial, or investment advice, and it does not replace review by qualified professionals. The indicative valuation is a multiples-based screening range resting entirely on stated assumptions — it is not an appraisal and must not be relied on for any decision. Local language models can miss issues and misread context; findings must be verified against the source documents. Vespera is designed to tell a human professional *where to look first* — not to make decisions.

## Roadmap

- IC memo generation from your firm's own template
- More valuation approaches (DCF, VC method) with the same assumptions-first framing
- OCR for scanned documents
- More document formats (XLSX, EML, PPTX)
- Additional local model providers (llama.cpp, MLX)
- Multi-language document support

## Development

```bash
git clone https://github.com/VesperaSystems/vespera
cd vespera
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The LLM is behind a tiny provider interface (`vespera/llm/base.py`), so tests inject a fake provider and never require Ollama.

## License

[Apache-2.0](LICENSE) — Copyright 2026 Daniel Molloy
