"""Pipeline command line: `uv run abcap --help`."""

import uuid

import typer

from app.core.config import get_settings
from app.core.logging import configure_logging

app = typer.Typer(help="Alberta school capacity data pipeline.", no_args_is_help=True)


@app.callback()
def _main() -> None:
    configure_logging(get_settings().log_level)


@app.command()
def download(
    force: bool = typer.Option(False, help="Re-download files even if unchanged."),
    skip_optional: bool = typer.Option(False, help="Skip optional sources (EPSB school points)."),
) -> None:
    """Download all source files into data/raw/ and write data/raw/manifest.json."""
    from pipeline.download import download_all

    settings = get_settings()
    run_id = uuid.uuid4().hex
    entries = download_all(
        settings.raw_dir,
        settings.ckan_base_url,
        run_id,
        force=force,
        include_optional=not skip_optional,
        timeout=settings.http_timeout_seconds,
    )
    typer.echo(f"run_id={run_id}: {len(entries)} files in {settings.raw_dir}")


@app.command()
def audit(
    out: str = typer.Option("", help="Also write the report as JSON to this path."),
) -> None:
    """Recompute the source facts behind docs/source_mapping.md from data/raw/."""
    import json
    from pathlib import Path

    from pipeline.audit import audit as run_audit

    report = run_audit(get_settings().raw_dir)
    text = json.dumps(report, indent=2, default=str)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"wrote {out}")
    else:
        typer.echo(text)


if __name__ == "__main__":
    app()
