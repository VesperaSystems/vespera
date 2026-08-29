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
- **Mechanically verified citations** — the source file and page on every finding are stamped by code, not by the model, and every evidence quote is checked in code against the source document; a quote that cannot be matched verbatim is labelled as inference, so you never have to take a citation on trust
- **Run record** — every report states the model, version, date, and verification counts behind it, and `deal.json` holds the full machine-readable analysis, so any figure can be explained months later
- **Fast triage** — `vespera triage` screens a dataroom in minutes: the three most decisive items, a criterion-by-criterion check of your investment criteria (met / violated / unknown), what's missing from the room, and a verdict on whether a full review is worth running
- **Key metrics** — revenue, ARR, growth, margins, retention, runway, taken only from financial-record documents (financial statements, investor updates, board minutes) and only where explicitly stated; figures in plans, marketing, or third-party material are excluded by construction, and every value is cited to its source
- **Contradiction detection** — the same metric reported differently in two documents, conflicting claims across contracts and board minutes, referenced schedules that aren't in the dataroom
- **AI adoption profile** — is AI evidenced in the product, operations, and engineering, or only claimed? "AI-powered" marketing with a rule-based mechanism underneath is flagged as a red flag, and the profile feeds the valuation: AI-native economics, AI-augmented operations, and AI-adoption headroom carry different margin structures and multiples
- **Deal readiness score** — a reproducible severity-weighted score with a Strong / Balanced / Cautious reading
- **Thesis fit** — write your investment thesis once in Markdown; every deal is scored against it, with aligned points, conflicts, and unknowns
- **Indicative valuation** — a multiples-based screening range with every assumption listed (a range to interrogate, never an appraisal)

```text
Vespera

Reviewing ./dataroom

Documents found: 9

Deal readiness: 44/100 — Balanced reading
AI posture: AI claimed, not evidenced
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
vespera triage PATH [--thesis thesis.md]   # fast screen: is a full review worth it?
vespera review PATH [--thesis thesis.md] [--model qwen3:8b] [--output vespera-output] [--host http://localhost:11434]
vespera models      # show recommended + locally installed Ollama models
vespera --version
```

The thesis file is plain Markdown — write your criteria however you normally would (see [examples/thesis.md](examples/thesis.md)).

## The workflow: triage first, then review

`triage` and `review` answer different questions — run them in order.

1. **`vespera triage ./dataroom --thesis thesis.md`** — minutes. Reads document summaries only and answers *"is this worth my time?"*: the three most decisive items (deal-breaker / concern / strength), a checklist of your criteria with each marked met, violated, or unknown, and the essentials missing from the room. Nothing in it is quote-verified — it is a screen, not evidence.
2. **Your call.** If the verdict is "significant deal-breakers evident" and you agree with the reasons, stop there — you've spent minutes, not hours.
3. **`vespera review ./dataroom --thesis thesis.md`** — only if the deal survives your look. This is the full analysis: findings with mechanically verified quotes, contradictions, risk matrix, readiness score, thesis fit, valuation, and the run record.

One rule: never hand anyone the triage output as the deliverable. Triage exists to protect your time. The review — with your judgment on top — is the work product.

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
