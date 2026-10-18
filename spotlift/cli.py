from __future__ import annotations

import os
import sys
from pathlib import Path

import typer
from rich.console import Console

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from spotlift.contracts.exceptions import SpotliftError
from spotlift.io.fixtures import generate_dach_benchmark_dataset
from spotlift.pro.bridge import is_pro_available
from spotlift.pro.installer import install_pro

app = typer.Typer(
    name="spotlift",
    help="High-Frequency Linear TV & Connected TV (CTV) Attribution Engine.",
    no_args_is_help=True,
)
console = Console()



@app.command()
def demo(
    out_dir: Path = typer.Option(
        Path("./demo_data"),
        "--out-dir",
        "-o",
        help="Target folder to export synthetic DACH TV, GA4, and Amazon datasets.",
    ),
    n_days: int = typer.Option(14, "--days", "-d", help="Flight duration in days."),
    n_spots: int = typer.Option(600, "--spots", "-s", help="Number of TV airings."),
) -> None:
    """Generates synthetic DACH benchmark datasets and executes an immediate diagnostic pass."""
    console.print(f"[bold cyan]⚡ Generating realistic DACH TV & Omnichannel benchmark dataset ({n_spots} spots)...[/bold cyan]")
    out_dir.mkdir(parents=True, exist_ok=True)

    airings, ga4, amz = generate_dach_benchmark_dataset(n_days=n_days, n_spots=n_spots)

    airings_path = out_dir / "tv_schaltplan.csv"
    ga4_path = out_dir / "ga4_minutes.parquet"
    amz_path = out_dir / "amazon_hourly.csv"

    airings.to_csv(airings_path, index=False)
    ga4.to_parquet(ga4_path, index=False)
    amz.to_csv(amz_path, index=False)

    console.print(f"[green]✔ Saved TV Airings to:[/] {airings_path}")
    console.print(f"[green]✔ Saved GA4 Telemetry to:[/] {ga4_path}")
    console.print(f"[green]✔ Saved Amazon Telemetry to:[/] {amz_path}")

    # Immediate diagnostic attribution pass
    import spotlift as sl

    console.print("\n[bold]Running Open-Core Diagnostic Attribution Pass:[/bold]")
    sl.analyze_spots(airings=airings, web_telemetry=ga4, window_minutes=8)


@app.command()
def run(
    spots: Path = typer.Option(..., "--spots", "-s", help="Path to broadcast airings CSV/Parquet (Schaltplan)."),
    web: Path = typer.Option(..., "--web", "-w", help="Path to GA4 minute-level session CSV/Parquet."),
    amazon: Path | None = typer.Option(None, "--amazon", "-a", help="Optional path to Amazon hourly telemetry CSV/Parquet."),
    window: int = typer.Option(8, "--window", help="Post-spot response window in minutes."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Path to save spot-level attribution CSV."),
    html: Path | None = typer.Option(None, "--html", help="Path to export client interactive HTML report."),
    excel: Path | None = typer.Option(None, "--excel", help="Path to export multi-tab Excel post-buy deck."),
    api_key: str | None = typer.Option(None, "--key", "-k", help="SpotLift Pro license key."),
    clip_negative: bool = typer.Option(
        False,
        "--clip-negative",
        help="If True, clips negative lifts at 0.0. Defaults to False (unbiased signed lift).",
    ),
) -> None:
    """Executes attribution analysis across broadcast TV, web sessions, and Amazon sales."""
    import spotlift as sl

    console.print("[bold blue]Loading data files...[/bold blue]")
    airings_df = sl.load_airings(spots)
    web_df = sl.load_telemetry(web)
    amz_df = sl.load_telemetry(amazon) if amazon else None

    effective_key = api_key or os.getenv("SPOTLIFT_API_KEY")

    if is_pro_available() and effective_key:
        console.print("[bold purple]SpotLift Pro license detected. Running Shifted-Gamma EM Deconvolution & Omnichannel Audit...[/bold purple]")
        pro_results = sl.analyze_omnichannel_pro(
            airings=airings_df,
            web_telemetry=web_df,
            amazon_telemetry=amz_df,
            api_key=effective_key,
            window_minutes=window,
            export_html=str(html) if html else None,
            export_excel=str(excel) if excel else None,
            clip_negative=clip_negative,
        )
        res_df = pro_results["spots_df"]
    else:
        console.print("[bold]Running Open-Core Diurnal Attribution...[/bold]")
        res_df = sl.analyze_spots(
            airings=airings_df,
            web_telemetry=web_df,
            window_minutes=window,
            clip_negative=clip_negative,
        )

    if out:
        res_df.to_csv(out, index=False)
        console.print(f"[green]✔ Saved attribution records to:[/] {out}")


@app.command()
def auth(
    key: str = typer.Option(..., "--key", "-k", prompt=True, hide_input=True, help="SpotLift Pro License Key (SL_PRO_...)"),
) -> None:
    """Authenticates SpotLift Pro key with Polar.sh and installs the matching compiled wheel."""
    console.print("[bold cyan]Validating SpotLift Pro license key with Polar.sh...[/bold cyan]")
    try:
        install_pro(key)
        console.print("[bold green]✔ License validated and cached successfully! SpotLift Pro is now unlocked.[/bold green]")
    except SpotliftError as err:
        console.print(f"[bold red]❌ Authentication failed:[/] {err}")
        raise typer.Exit(code=1)


@app.command()
def sql(
    source: str = typer.Option("ga4", "--source", "-s", help="Telemetry source: 'ga4' or 'amc'."),
    project: str = typer.Option("your-gcp-project", "--project", "-p", help="GCP project ID (GA4)."),
    dataset: str = typer.Option("analytics_123456789", "--dataset", "-d", help="GA4 dataset ID."),
    start: str = typer.Option("2026-03-01", "--start", help="Start date YYYY-MM-DD."),
    end: str = typer.Option("2026-03-21", "--end", help="End date YYYY-MM-DD."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Optional file path to write generated SQL."),
) -> None:
    """Generates standard GA4 BigQuery or Amazon Marketing Cloud (AMC) telemetry extraction SQL."""
    import spotlift as sl

    if source.lower() == "ga4":
        query = sl.generate_ga4_bigquery_sql(
            project_id=project,
            dataset_id=dataset,
            start_date=start,
            end_date=end,
        )
    elif source.lower() == "amc":
        query = sl.generate_amc_telemetry_sql(
            start_date=start,
            end_date=end,
        )
    else:
        console.print(f"[bold red]Unknown source '{source}'. Must be 'ga4' or 'amc'.[/bold red]")
        raise typer.Exit(code=1)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(query, encoding="utf-8")
        console.print(f"[green]✔ Saved {source.upper()} extraction SQL to:[/] {out}")
    else:
        print(query)


if __name__ == "__main__":
    app()

