"""Vespera command-line interface."""

from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)

import vespera
from vespera.config import DEFAULT_MODEL, DEFAULT_OLLAMA_HOST, RECOMMENDED_MODELS, ReviewConfig
from vespera.documents.loader import discover_documents, load_document
from vespera.llm.ollama import OllamaError, OllamaProvider
from vespera.review.aggregator import aggregate_findings
from vespera.review.analyzer import analyze_document, cross_document_findings
from vespera.review.models import DocumentSummary, Finding
from vespera.review.report import write_outputs

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

OLLAMA_MISSING_HELP = """\
[red]Ollama is not running.[/red]

Vespera uses [bold]Ollama[/bold] to run the AI model locally, so your documents never
leave this computer.

- If Ollama is not installed yet: download it from [link]https://ollama.com/download[/link]
  and open it once (macOS users can also run: brew install ollama).
- If Ollama is installed: start the Ollama app, or run [bold]ollama serve[/bold] in
  another terminal.

Then re-run this command.\
"""


def _ensure_ready(provider: OllamaProvider) -> None:
    """Check Ollama is up and the model is present; download the model if not."""
    if not provider.is_server_running():
        console.print(OLLAMA_MISSING_HELP)
        raise typer.Exit(code=1)
    if provider.has_model():
        return
    console.print(
        f"Model [cyan]{provider.model}[/cyan] is not installed yet — "
        "downloading it now (one-time step).\n"
    )
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Downloading {provider.model}", total=None)
        for event in provider.pull_model():
            total, completed = event.get("total"), event.get("completed")
            if total:
                progress.update(task, total=total, completed=completed or 0)
    console.print(f"Model [cyan]{provider.model}[/cyan] ready.\n")


def _version_callback(value: bool):
    if value:
        console.print(f"vespera {vespera.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version."
    ),
):
    """Vespera — local-first AI due diligence."""


@app.command()
def review(
    path: Path = typer.Argument(..., exists=True, file_okay=False, help="Dataroom directory."),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="Ollama model to use."),
    output: Path = typer.Option(Path("vespera-output"), "--output", "-o", help="Output directory."),
    host: str = typer.Option(DEFAULT_OLLAMA_HOST, "--host", help="Ollama server URL."),
):
    """Review a local dataroom and produce a due diligence report."""
    config = ReviewConfig(model=model, ollama_host=host, output_dir=output)
    provider = OllamaProvider(model=config.model, host=config.ollama_host)

    console.print("\n[bold]Vespera[/bold]\n")

    try:
        _ensure_ready(provider)
    except OllamaError as error:
        console.print(f"[red]Error:[/red] {error}")
        raise typer.Exit(code=1)

    console.print(f"Reviewing [cyan]{path}[/cyan]\n")

    paths = discover_documents(path)
    console.print(f"Documents found: {len(paths)}")
    if not paths:
        console.print("[yellow]No supported documents (.pdf, .docx, .txt, .md) found.[/yellow]")
        raise typer.Exit(code=1)

    findings: list[Finding] = []
    summaries: dict[str, DocumentSummary] = {}
    reviewed: list[str] = []
    empty: list[str] = []
    processed = 0

    try:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Analysing documents", total=len(paths))
            for doc_path in paths:
                relative_name = str(doc_path.relative_to(path))
                progress.update(task, description=f"Analysing {relative_name}")
                document = load_document(doc_path)
                if document.is_empty:
                    empty.append(relative_name)
                else:
                    doc_findings, summary = analyze_document(
                        document, provider, config, relative_name
                    )
                    findings.extend(doc_findings)
                    if summary is not None:
                        summaries[relative_name] = summary
                    reviewed.append(relative_name)
                processed += 1
                progress.advance(task)

            # comparing documents needs deeper reasoning than clause extraction, so
            # this single call runs with the model's thinking mode enabled
            cross_task = progress.add_task("Cross-referencing documents (deep check)", total=1)
            deep_provider = OllamaProvider(
                model=config.model, host=config.ollama_host, think=True
            )
            findings.extend(cross_document_findings(summaries, deep_provider, config))
            progress.advance(cross_task)
    except OllamaError as error:
        console.print(f"\n[red]Error:[/red] {error}")
        raise typer.Exit(code=1)

    findings = aggregate_findings(findings)
    report_path, findings_path = write_outputs(findings, reviewed, config.output_dir, empty)

    console.print(f"Documents processed: {processed}\n")
    console.print("[bold]Findings:[/bold]")
    category_counts = Counter(f.category for f in findings)
    if category_counts:
        for category, count in category_counts.most_common():
            console.print(f"- {category[0].upper() + category[1:]}: {count}")
    else:
        console.print("- No findings recorded")
    console.print(f"\nReport: [green]{report_path}[/green]")
    console.print(f"Evidence: [green]{findings_path}[/green]")
    console.print("\n[dim]All document analysis was performed locally.[/dim]\n")


@app.command()
def models(
    host: str = typer.Option(DEFAULT_OLLAMA_HOST, "--host", help="Ollama server URL."),
):
    """Show recommended and locally installed Ollama models."""
    provider = OllamaProvider(model=DEFAULT_MODEL, host=host)
    local = provider.list_local_models()
    annotations = dict(RECOMMENDED_MODELS)

    console.print("Recommended models (pick with --model):")
    for name, annotation in RECOMMENDED_MODELS:
        markers = f" [dim]({annotation})[/dim]"
        if name == DEFAULT_MODEL:
            markers += " [green](default)[/green]"
        if local and name not in local:
            markers += f" [yellow]not installed — run: ollama pull {name}[/yellow]"
        console.print(f"- {name}{markers}")

    if local:
        others = [name for name in local if name not in annotations]
        if others:
            console.print("Other locally installed Ollama models:")
            for name in others:
                console.print(f"- {name}")
    else:
        console.print(
            f"[yellow]Could not list local models — is Ollama running at {host}?[/yellow]"
        )


if __name__ == "__main__":
    app()
