"""CLI entry point for checkrefs_batch."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from .pipeline import process_batch, process_pdf


@click.command()
@click.argument("input_path", type=click.Path(exists=True), default="data")
@click.option("-o", "--output", "output_dir", type=click.Path(), default="output", help="Output directory for reports.")
@click.option("-e", "--email", default="", help="Email for CrossRef polite pool (recommended).")
@click.option("--scholar/--no-scholar", default=False, help="Enable Google Scholar fallback.")
@click.option("--rate-limit", type=float, default=1.0, help="Seconds between CrossRef requests.")
@click.option("--single", is_flag=True, help="Treat INPUT_PATH as a single PDF file.")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
def main(
    input_path: str,
    output_dir: str,
    email: str,
    scholar: bool,
    rate_limit: float,
    single: bool,
    verbose: bool,
) -> None:
    """Check references in academic PDFs against CrossRef and Google Scholar."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    out = Path(output_dir)
    kwargs = dict(
        email=email,
        rate_limit=rate_limit,
        use_scholar=scholar,
        verbose=verbose,
    )

    if single:
        pdf = Path(input_path)
        if not pdf.is_file():
            click.echo(f"Error: {input_path} is not a file", err=True)
            sys.exit(1)
        report = process_pdf(pdf, out, **kwargs)
        _print_summary(report)
    else:
        input_dir = Path(input_path)
        if not input_dir.is_dir():
            click.echo(f"Error: {input_path} is not a directory", err=True)
            sys.exit(1)
        reports = process_batch(input_dir, out, **kwargs)
        for report in reports:
            _print_summary(report)


def _print_summary(report):
    click.echo(f"\n=== {report.filename} ===")
    click.echo(f"  Total refs:    {report.total_refs}")
    click.echo(f"  Verified:      {report.verified_count}")
    click.echo(f"  Likely match:  {report.likely_count}")
    click.echo(f"  Not found:     {report.not_found_count}")
    click.echo(f"  Errors:        {report.error_count}")
    click.echo(f"  Format issues: {len(report.format_issues)}")


if __name__ == "__main__":
    main()
