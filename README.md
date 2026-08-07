# Vespera

**Local-first AI due diligence.**

Review a dataroom without sending confidential documents to a third-party AI provider.

```bash
pip install vespera
vespera review ./dataroom
```

Vespera scans the documents in a local folder — contracts, board minutes, NDAs — and produces a structured due diligence report with evidence-backed findings, each linked to its source document and page. All analysis runs on your machine via [Ollama](https://ollama.com). Document contents never leave your network.

## What it does

Vespera performs the *first-pass* review of a document collection for M&A, VC, and PE due diligence:

- Recursively discovers PDF, DOCX, TXT, and Markdown documents
- Extracts text and analyses it with a local LLM
- Produces structured findings across categories including change-of-control clauses, termination rights, assignment restrictions, exclusivity, IP ownership, material liabilities, missing signatures, and cross-document inconsistencies
- Writes a Markdown report and a machine-readable JSON evidence file

```text
Vespera

Reviewing ./dataroom

Documents found: 6
Documents processed: 6

Findings:
- Change-of-control clauses: 1
- Termination rights: 3
- Missing signatures: 1
- IP ownership / assignment: 2

Report: vespera-output/report.md
Evidence: vespera-output/findings.json

All document analysis was performed locally.
```

Every finding carries its category, severity, a short verbatim evidence excerpt, a confidence score, and the source file and page.

## Privacy model

- **No cloud calls for analysis.** Inference runs on a local Ollama server (`localhost` by default).
- **No telemetry, no accounts, no database.** Vespera reads your documents and writes two output files. That's it.
- The only network activity you'll ever need is `ollama pull` to download a model once.

## Quick start

1. Install [Ollama](https://ollama.com) and pull a model:

   ```bash
   ollama pull qwen3:8b
   ```

2. Install Vespera (Python 3.12+):

   ```bash
   pip install vespera
   ```

3. Review a dataroom:

   ```bash
   vespera review ./dataroom
   ```

Try it on the included synthetic example:

```bash
git clone https://github.com/VesperaSystems/vespera
cd vespera
vespera review ./examples/sample-dataroom
```

### Commands

```bash
vespera review PATH [--model qwen3:8b] [--output vespera-output] [--host http://localhost:11434]
vespera models      # show default + locally installed Ollama models
vespera --version
```

## Supported document types

| Format | Notes |
| --- | --- |
| PDF | Priority format; per-page source references |
| DOCX | Paragraphs and tables; no page numbers |
| TXT / MD | Plain text |

Scanned image-only documents are not analysed in this version (no OCR).

## Limitations

Vespera is automated document triage. It is **not** legal, financial, or investment advice, and it does not replace review by qualified professionals. Local language models can miss issues and misread context; findings must be verified against the source documents. Vespera is designed to tell a human professional *where to look first* — not to make decisions.

## Roadmap

- OCR for scanned documents
- More document formats (XLSX, EML, PPTX)
- Additional local model providers (llama.cpp, MLX)
- Configurable finding categories and custom review checklists
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

[Apache-2.0](LICENSE)
