"""Pipeline command line: `uv run abcap --help`."""

import json
import uuid
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from app.core.config import get_settings
from app.core.logging import configure_logging

app = typer.Typer(help="Alberta school capacity data pipeline.", no_args_is_help=True)


class Source(StrEnum):
    raw = "raw"
    sample = "sample"


SourceOpt = Annotated[
    Source,
    typer.Option(help="raw = full downloaded data (make data); sample = small committed subset."),
]


@app.callback()
def _main() -> None:
    configure_logging(get_settings().log_level)


@app.command()
def download(
    force: Annotated[bool, typer.Option(help="Re-download files even if unchanged.")] = False,
    skip_optional: Annotated[
        bool, typer.Option(help="Skip optional sources (EPSB school points).")
    ] = False,
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
    out: Annotated[str, typer.Option(help="Also write the report as JSON to this path.")] = "",
) -> None:
    """Recompute the source facts behind docs/source_mapping.md from data/raw/."""
    from pipeline.audit import audit as run_audit

    report = run_audit(get_settings().raw_dir)
    text = json.dumps(report, indent=2, default=str)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"wrote {out}")
    else:
        typer.echo(text)


@app.command()
def migrate() -> None:
    """Apply database migrations (alembic upgrade head)."""
    from pipeline.run import migrate as run_migrate

    run_migrate(get_settings().database_url)
    typer.echo("database is at the latest migration")


@app.command()
def run(source: SourceOpt = Source.raw) -> None:
    """Run the pipeline: load every source file into the raw schema, then verify row counts."""
    from app.db.session import get_engine
    from pipeline.dbt import dbt_vars
    from pipeline.run import run_pipeline

    settings = get_settings()
    run_id = uuid.uuid4()
    variables = dbt_vars(settings.utilization_threshold_pct, settings.over_capacity_pct)
    summary = run_pipeline(
        get_engine(), settings.data_dir / source.value, source.value, run_id, variables
    )
    for s in summary:
        rows = s.get("rows_out", s.get("rows"))
        typer.echo(f"  {s['step']:<20} rows={rows}")
    typer.echo(f"run_id={run_id}: OK (see ops.pipeline_run)")


@app.command()
def verify(source: SourceOpt = Source.raw) -> None:
    """Compare source-file row counts with the raw tables (no loading)."""
    from app.db.session import get_engine
    from pipeline.verify import RowCountMismatch, verify_raw_counts

    with get_engine().connect() as conn:
        try:
            v = verify_raw_counts(conn, get_settings().data_dir / source.value)
        except RowCountMismatch as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
    for name, c in v.per_file.items():
        typer.echo(f"  {name:<58} source={c['source']:>6} loaded={c['loaded']:>6}")
    typer.echo(f"{v.files} files, {v.loaded_rows} rows: all match")


@app.command(
    "dbt",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def dbt_command(ctx: typer.Context) -> None:
    """Run any dbt command against DATABASE_URL, e.g. `abcap dbt docs generate`."""
    from pipeline import dbt

    settings = get_settings()
    variables = dbt.dbt_vars(settings.utilization_threshold_pct, settings.over_capacity_pct)
    res = dbt.invoke(list(ctx.args), settings.database_url, variables)
    raise typer.Exit(0 if res.success else 1)


@app.command("make-sample")
def make_sample() -> None:
    """Rebuild data/sample/ from data/raw/ (a small real subset for CI)."""
    from pipeline.sample import build_sample

    settings = get_settings()
    written = build_sample(settings.raw_dir, settings.data_dir / "sample")
    for name, n in written.items():
        typer.echo(f"  {name:<58} {n:>5}")
    typer.echo(f"{len(written)} files written to {settings.data_dir / 'sample'}")


if __name__ == "__main__":
    app()
