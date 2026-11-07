from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import spotlift as sl
from spotlift.contracts.exceptions import SpotliftError
from spotlift.io.fixtures import (
    generate_dach_benchmark_dataset,
    generate_omnichannel_amc_dataset,
    generate_us_state_dataset,
)
from spotlift.pro.bridge import is_pro_available
from spotlift.pro.installer import install_pro

app = typer.Typer(
    name="spotlift",
    help="High-Frequency Linear TV Attribution Engine.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def demo(
    out_dir: Path = typer.Option(
        Path("./demo_data"),
        "--out-dir",
        "-o",
        help="Target folder to export synthetic datasets.",
    ),
    n_days: int = typer.Option(14, "--days", "-d", help="Flight duration in days."),
    n_spots: int = typer.Option(600, "--spots", "-s", help="Number of TV airings."),
    scenario: str = typer.Option(
        "dach",
        "--scenario",
        "-sc",
        help="Benchmark scenario: 'dach' (National + 36h AMC lag), 'amc' (Omnichannel + AMC Clean Room), or 'us-state' (Regional State-level).",
    ),
) -> None:
    """Generates synthetic benchmark datasets and executes an immediate diagnostic pass."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sc_clean = scenario.lower().strip()

    if sc_clean == "amc":
        console.print(f"[bold cyan]⚡ Generating realistic Omnichannel TV & AMC Clean Room benchmark dataset ({n_spots} spots)...[/bold cyan]")
        airings, ga4, amc_convs, amc_hourly = generate_omnichannel_amc_dataset(n_days=n_days, n_spots=n_spots)

        airings_path = out_dir / "tv_schaltplan.csv"
        ga4_path = out_dir / "ga4_minutes.parquet"
        amc_convs_path = out_dir / "amc_spot_conversions.csv"
        amc_hourly_path = out_dir / "amazon_hourly.csv"

        airings.to_csv(airings_path, index=False)
        ga4.to_parquet(ga4_path, index=False)
        amc_convs.to_csv(amc_convs_path, index=False)
        amc_hourly.to_csv(amc_hourly_path, index=False)

        console.print(f"[green]✔ Saved TV Airings to:[/] {airings_path}")
        console.print(f"[green]✔ Saved GA4 Telemetry to:[/] {ga4_path}")
        console.print(f"[green]✔ Saved AMC Clean Room Convs to:[/] {amc_convs_path}")
        console.print(f"[green]✔ Saved Amazon Hourly Telemetry to:[/] {amc_hourly_path}")

        console.print("\n[bold]Running Open-Core Diagnostic Attribution Pass:[/bold]")
        res_df = sl.analyze_spots(airings=airings, web_telemetry=ga4, window_minutes=8)

    elif sc_clean in ("us-state", "us_state", "state"):
        console.print(f"[bold cyan]⚡ Generating realistic US Regional State-Targeted benchmark dataset ({n_spots} spots)...[/bold cyan]")
        state_airings, state_telemetry = generate_us_state_dataset(n_days=n_days, n_spots=n_spots)

        airings_path = out_dir / "us_state_airings.csv"
        telem_path = out_dir / "us_state_telemetry.parquet"

        state_airings.to_csv(airings_path, index=False)
        state_telemetry.to_parquet(telem_path, index=False)

        console.print(f"[green]✔ Saved US Regional Airings to:[/] {airings_path}")
        console.print(f"[green]✔ Saved US State Telemetry to:[/] {telem_path}")

        telem_long = pd.concat([
            pd.DataFrame({
                "timestamp": state_telemetry["timestamp"],
                "state": state_telemetry["state"],
                "channel_source": "ga4_direct_organic_sessions",
                "value": state_telemetry["sessions"],
            }),
            pd.DataFrame({
                "timestamp": state_telemetry["timestamp"],
                "state": state_telemetry["state"],
                "channel_source": "ga4_conversions",
                "value": state_telemetry["conversions"],
            }),
        ], ignore_index=True)

        console.print("\n[bold]Running Open-Core Regional State-Segmented Attribution Pass (region_col='state'):[/bold]")
        res_df = sl.analyze_spots(airings=state_airings, web_telemetry=telem_long, window_minutes=8, region_col="state")

    else:
        # Default: DACH
        console.print(f"[bold cyan]⚡ Generating realistic DACH TV & Omnichannel benchmark dataset ({n_spots} spots)...[/bold cyan]")
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

        console.print("\n[bold]Running Open-Core Diagnostic Attribution Pass:[/bold]")
        res_df = sl.analyze_spots(airings=airings, web_telemetry=ga4, window_minutes=8)

    attributed_path = out_dir / "attributed_spots.csv"
    res_df.to_csv(attributed_path, index=False)
    console.print(f"[green]✔ Saved Attributed Spots to:[/] {attributed_path}\n")

    # Render inspectable sample results table
    table = Table(
        title=f"Sample Attributed Airings (First 8 Spots — Scenario: {sc_clean})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Spot ID", style="bold")
    table.add_column("Timestamp (UTC)", style="dim")
    table.add_column("Channel")
    table.add_column("Cost (€/$)", justify="right")
    table.add_column("GRP", justify="right")
    table.add_column("Baseline", justify="right")
    table.add_column("Observed", justify="right")
    table.add_column("Lift", justify="right", style="bold green")
    table.add_column("CPIV (€/$)", justify="right")
    table.add_column("Status", justify="center")

    for _, row in res_df.head(8).iterrows():
        lift_val = row.get("incremental_lift", 0.0)
        lift_style = "bold green" if lift_val > 0 else ("bold red" if lift_val < 0 else "dim")
        lift_str = f"[{lift_style}]{lift_val:+.1f}[/{lift_style}]"

        cpiv_val = row.get("cpiv")
        cpiv_str = f"{cpiv_val:.2f}" if pd.notna(cpiv_val) and cpiv_val is not None else "-"
        status_str = "[yellow]Collision[/yellow]" if row.get("is_overlapping") else "[green]Isolated[/green]"

        table.add_row(
            str(row.get("spot_id", "")),
            str(row.get("timestamp", ""))[:16],
            str(row.get("channel", "")),
            f"{float(row.get('cost', 0.0)):,.0f}",
            f"{float(row.get('grp', 0.0)):.1f}",
            f"{float(row.get('baseline_volume', 0.0)):.0f}",
            f"{float(row.get('observed_volume', 0.0)):.0f}",
            lift_str,
            cpiv_str,
            status_str,
        )

    console.print(table)
    console.print(f"\n[bold]Next step:[/] Inspect full results at [underline]{attributed_path}[/underline] or run with your own files:")
    console.print("  [cyan]spotlift run --spots your_schaltplan.csv --web your_ga4_minutes.parquet --out results.csv[/cyan]")
    console.print("\n[dim]💬 Tested your own campaign data? Share feedback or report an obstacle: https://github.com/flovv/spotlift/issues[/dim]\n")


@app.command()
def validate(
    spots: Path = typer.Option(..., "--spots", "-s", help="Path to broadcast airings CSV/Parquet (Schaltplan)."),
    web: Path = typer.Option(..., "--web", "-w", help="Path to GA4 minute-level session CSV/Parquet."),
    tz: str = typer.Option(
        "UTC",
        "--tz",
        "-z",
        help="Timezone assumed if input timestamps are naive (e.g. Europe/Berlin, UTC, US/Eastern).",
    ),
    window: int = typer.Option(8, "--window", help="Post-spot response window in minutes."),
    conversions_source: str = typer.Option(
        "ga4_conversions",
        "--conversions-source",
        "-c",
        help="Conversion channel source label(s), comma-separated.",
    ),
    region_col: str | None = typer.Option(
        None,
        "--region-col",
        "-r",
        help="Optional column name to segment attribution by region/state (e.g. 'state').",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON summary for AI coding agents and pipelines.",
    ),
) -> None:
    """Performs pre-flight data quality, schema, cadence, and collision validation on campaign files."""
    conv_parts = [s.strip() for s in conversions_source.split(",") if s.strip()]
    conv_source_param: str | list[str] = conv_parts if len(conv_parts) > 1 else (conv_parts[0] if conv_parts else "ga4_conversions")

    result = sl.validate_inputs(
        airings=spots,
        web_telemetry=web,
        tz=tz,
        window_minutes=window,
        conversions_source=conv_source_param,
        region_col=region_col,
    )

    if json_output:
        print(json.dumps(result.summary_dict(), indent=2, default=str))
    else:
        result.print_report()
        if result.is_ready:
            console.print("[dim]💬 Tested your own campaign data? Share feedback or feature requests: https://github.com/flovv/spotlift/issues[/dim]\n")

    if not result.is_ready:
        raise typer.Exit(code=1)


@app.command()
def run(
    spots: Path = typer.Option(..., "--spots", "-s", help="Path to broadcast airings CSV/Parquet (Schaltplan)."),
    web: Path = typer.Option(..., "--web", "-w", help="Path to GA4 minute-level session CSV/Parquet."),
    amazon: Path | None = typer.Option(None, "--amazon", "-a", help="Optional path to Amazon hourly telemetry CSV/Parquet."),
    amc_conversions: Path | None = typer.Option(None, "--amc-conversions", help="Optional path to AMC pre/post spot conversions CSV/Parquet."),
    window: int = typer.Option(8, "--window", help="Post-spot response window in minutes."),
    conversions_source: str = typer.Option(
        "ga4_conversions",
        "--conversions-source",
        "-c",
        help="Conversion channel source label(s), comma-separated for multi-funnel attribution.",
    ),
    region_col: str | None = typer.Option(
        None,
        "--region-col",
        "-r",
        help="Optional column name to segment attribution by region/state (e.g. 'state').",
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Path to save spot-level attribution CSV."),
    markdown_out: Path | None = typer.Option(
        None,
        "--markdown-out",
        "-m",
        help="Path to export executive Markdown post-buy audit summary report.",
    ),
    format: str = typer.Option(
        "csv",
        "--format",
        "-f",
        help="Deliverable format: 'csv', 'markdown', or 'all'.",
    ),
    html: Path | None = typer.Option(None, "--html", help="Path to export client interactive HTML report (SpotLift Pro)."),
    excel: Path | None = typer.Option(None, "--excel", help="Path to export multi-tab Excel post-buy deck (SpotLift Pro)."),
    api_key: str | None = typer.Option(None, "--key", "-k", help="SpotLift Pro license key."),
    clip_negative: bool = typer.Option(
        False,
        "--clip-negative",
        help="If True, clips negative lifts at 0.0. Defaults to False (unbiased signed lift).",
    ),
    tz: str = typer.Option(
        "UTC",
        "--tz",
        "-z",
        help="Timezone assumed if input timestamps are naive (e.g. Europe/Berlin, UTC, US/Eastern).",
    ),
    allow_interpolation: bool = typer.Option(
        False,
        "--allow-interpolation",
        help="If True, linearly interpolates minor telemetry gaps <= 3 min.",
    ),
) -> None:
    """Executes attribution analysis across broadcast TV, web sessions, and Amazon sales."""
    console.print("[bold blue]Loading data files...[/bold blue]")
    airings_df = sl.load_airings(spots, tz=tz)
    web_df = sl.load_telemetry(web, tz=tz, allow_interpolation=allow_interpolation, region_col=region_col)
    amz_df = (
        sl.load_telemetry(amazon, tz=tz, allow_interpolation=allow_interpolation, region_col=region_col)
        if amazon
        else None
    )

    amc_spot_convs_df = None
    if amc_conversions:
        if amc_conversions.suffix.lower() in [".parquet", ".pq"]:
            amc_spot_convs_df = pd.read_parquet(amc_conversions)
        else:
            amc_spot_convs_df = pd.read_csv(amc_conversions)

    # Parse conversions_source (comma-separated support)
    conv_parts = [s.strip() for s in conversions_source.split(",") if s.strip()]
    conv_source_param: str | list[str] = conv_parts if len(conv_parts) > 1 else (conv_parts[0] if conv_parts else "ga4_conversions")

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
            conversions_source=conv_source_param,
            region_col=region_col,
            amc_spot_conversions=amc_spot_convs_df,
        )
        res_df = pro_results["spots_df"]
    else:
        console.print("[bold]Running Open-Core Diurnal Attribution...[/bold]")
        res_df = sl.analyze_spots(
            airings=airings_df,
            web_telemetry=web_df,
            window_minutes=window,
            clip_negative=clip_negative,
            conversions_source=conv_source_param,
            region_col=region_col,
        )

    # Export CSV
    fmt_clean = format.lower().strip()
    should_save_csv = (fmt_clean in ("csv", "all")) or (out is not None)
    should_save_md = (fmt_clean in ("markdown", "all")) or (markdown_out is not None)

    if should_save_csv:
        target_csv = out or Path("spotlift_attribution_records.csv")
        target_csv.parent.mkdir(parents=True, exist_ok=True)
        res_df.to_csv(target_csv, index=False)
        console.print(f"[green]✔ Saved attribution CSV to:[/] {target_csv}")

    # Export Markdown Summary Report
    if should_save_md:
        target_md = markdown_out or (out.with_suffix(".md") if out else Path("spotlift_campaign_summary.md"))
        target_md.parent.mkdir(parents=True, exist_ok=True)
        md_content = sl.generate_markdown_summary(res_df, airings_df=airings_df, web_df=web_df)
        target_md.write_text(md_content, encoding="utf-8")
        console.print(f"[green]✔ Saved executive Markdown report to:[/] {target_md}")

    # Print summary channel performance table
    console.print("\n[bold]Station Performance Summary:[/bold]")
    summary_table = Table(title="Attributed Channel Efficiency (Open-Core)")
    summary_table.add_column("Channel", style="cyan", no_wrap=True)
    summary_table.add_column("Spots", justify="right")
    summary_table.add_column("Spend", justify="right")
    summary_table.add_column("Net Lift", justify="right", style="bold green")
    summary_table.add_column("CPIV", justify="right")
    summary_table.add_column("Collision Rate", justify="right")

    for ch, grp in res_df.groupby("channel"):
        ch_spend = float(grp["cost"].sum())
        ch_lift = float(grp["incremental_lift"].sum())
        ch_cpiv = (ch_spend / ch_lift) if ch_lift > 0 else None
        ch_coll = float(grp["is_overlapping"].mean() * 100.0) if "is_overlapping" in grp.columns else 0.0

        lift_style = "bold green" if ch_lift > 0 else ("bold red" if ch_lift < 0 else "dim")
        summary_table.add_row(
            str(ch),
            f"{len(grp):,}",
            f"{ch_spend:,.0f}",
            f"[{lift_style}]{ch_lift:+,.1f}[/{lift_style}]",
            f"{ch_cpiv:.2f}" if ch_cpiv is not None else "-",
            f"{ch_coll:.1f}%",
        )
    console.print(summary_table)
    console.print("\n[dim]💬 Did this analysis work for your campaign? Share feedback or report an obstacle: https://github.com/flovv/spotlift/issues[/dim]\n")


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
    conversion_event: str = typer.Option("purchase", "--conversion-event", "-e", help="GA4 conversion event name(s), comma-separated."),
    include_paid_search: bool = typer.Option(False, "--include-paid-search/--no-paid-search", help="Whether to include paid branded search in GA4 BigQuery SQL."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Optional file path to write generated SQL."),
) -> None:
    """Generates standard GA4 BigQuery or Amazon Marketing Cloud (AMC) telemetry extraction SQL."""
    if source.lower() == "ga4":
        ev_parts = [s.strip() for s in conversion_event.split(",") if s.strip()]
        conv_ev_param: str | list[str] = ev_parts if len(ev_parts) > 1 else (ev_parts[0] if ev_parts else "purchase")
        query = sl.generate_ga4_bigquery_sql(
            project_id=project,
            dataset_id=dataset,
            start_date=start,
            end_date=end,
            conversion_event_name=conv_ev_param,
            include_paid_search=include_paid_search,
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




@app.command()
def optimize(
    spots: Path = typer.Option(..., "--spots", "-s", help="Path to attributed spots CSV/Parquet (or airings file if --web is provided)."),
    web: Path | None = typer.Option(None, "--web", "-w", help="Optional GA4 telemetry path if spots file is not yet attributed."),
    budget: float | None = typer.Option(None, "--budget", "-b", help="Target total budget. Defaults to current flight spend."),
    max_shift: float = typer.Option(0.35, "--max-shift", "-m", help="Maximum relative budget reallocation allowed per channel (e.g. 0.35 = ±35%)."),
    elasticity: float = typer.Option(0.70, "--elasticity", "-e", help="Diminishing returns elasticity parameter beta (0 < beta < 1)."),
    channel_col: str = typer.Option("channel", "--channel-col", help="Column name identifying media channel/station."),
    cost_col: str = typer.Option("cost", "--cost-col", help="Column name containing spot media spend."),
    lift_col: str = typer.Option("incremental_lift", "--lift-col", help="Column name containing incremental lift."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Optional path to export optimized recommendations CSV."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON summary for AI coding agents and pipelines."),
    scenarios: bool = typer.Option(False, "--scenarios", help="Display multi-scenario comparison (Conservative, Balanced, Aggressive)."),
    export_mmm: Path | None = typer.Option(
        None,
        "--export-mmm",
        help="Optional directory path to export period-aligned PyMC lift test calibration data alongside optimization.",
    ),
    tz: str = typer.Option("UTC", "--tz", "-z", help="Timezone if raw airings are provided."),
) -> None:
    """Solves constrained budget reallocation using diminishing returns response curves and marginal CPIV."""
    if spots.suffix.lower() in [".parquet", ".pq"]:
        df = pd.read_parquet(spots)
    else:
        df = pd.read_csv(spots)

    if lift_col not in df.columns:
        if web is None:
            console.print(f"[bold red]Column '{lift_col}' not found in spots file. Please provide --web to run attribution first.[/bold red]")
            raise typer.Exit(code=1)
        console.print("[dim]Running attribution pass prior to optimization...[/dim]")
        airings_df = sl.load_airings(spots, tz=tz)
        web_df = sl.load_telemetry(web, tz=tz)
        df = sl.analyze_spots(airings=airings_df, web_telemetry=web_df)

    opt_res = sl.optimize_budget(
        df=df,
        total_budget=budget,
        channel_col=channel_col,
        cost_col=cost_col,
        lift_col=lift_col,
        max_shift=max_shift,
        elasticity=elasticity,
        compute_scenarios=True,
    )

    if json_output:
        print(json.dumps(opt_res.summary_dict(), indent=2))
    else:
        opt_res.print_summary(console=console)
        if scenarios and opt_res.scenarios:
            for sc_name, sc_df in opt_res.scenarios.items():
                sc_table = Table(title=f"Scenario: {sc_name.capitalize()}")
                sc_table.add_column("Channel", style="cyan")
                sc_table.add_column("Optimal Spend", justify="right")
                sc_table.add_column("Shift", justify="right")
                sc_table.add_column("Projected Lift", justify="right", style="green")
                sc_table.add_column("Proj CPIV", justify="right")
                for _, r in sc_df.iterrows():
                    s_amt = r["spend_shift"]
                    s_str = f"+€{s_amt:,.0f}" if s_amt > 0 else f"-€{abs(s_amt):,.0f}" if s_amt < 0 else "€0"
                    sc_table.add_row(
                        str(r["channel"]),
                        f"€{r['optimized_spend']:,.0f}",
                        s_str,
                        f"{r['projected_lift']:+,.1f}",
                        f"€{r['projected_cpiv']:.2f}" if r["projected_cpiv"] != float("inf") else "-",
                    )
                console.print(sc_table)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        opt_res.recommendations.to_csv(out, index=False)
        console.print(f"[green]✔ Saved optimized recommendations to:[/] {out}")

    if export_mmm:
        export_mmm.mkdir(parents=True, exist_ok=True)
        ts_col = "timestamp" if "timestamp" in df.columns else None
        pymc_df = sl.export_pymc_lift_test(
            df,
            channel_col=channel_col,
            cost_col=cost_col,
            lift_col=lift_col,
            timestamp_col=ts_col or "timestamp",
            elasticity=elasticity,
        )
        pymc_out = export_mmm / "pymc_lift_test.csv"
        pymc_df.to_csv(pymc_out, index=False)
        console.print(f"[green]✔ Saved PyMC MMM lift test calibration to:[/] {pymc_out}")


@app.command()
def mmm(
    spots: Path = typer.Option(..., "--spots", "-s", help="Path to attributed spots CSV/Parquet (or airings file if --web is provided)."),
    web: Path | None = typer.Option(None, "--web", "-w", help="Optional GA4 telemetry path if spots file is not yet attributed."),
    target: str = typer.Option("pymc", "--target", "-t", help="Target MMM framework: 'pymc', 'meridian', 'robyn', or 'all'."),
    out_dir: Path = typer.Option(Path("./mmm_export"), "--out-dir", "-o", help="Directory path to export calibration files."),
    freq: str = typer.Option("W-MON", "--freq", "-f", help="MMM period frequency: 'W-MON' (weekly) or 'D' (daily)."),
    lift_col: str = typer.Option("incremental_lift", "--lift-col", "-l", help="Incremental lift column ('incremental_lift' or 'key_event_response')."),
    cost_col: str = typer.Option("cost", "--cost-col", "-c", help="Spot media cost column."),
    channel_col: str = typer.Option("channel", "--channel-col", help="Column name identifying media channel/station."),
    timestamp_col: str = typer.Option("timestamp", "--timestamp-col", help="Column name containing spot timestamps."),
    elasticity: float = typer.Option(0.70, "--elasticity", "-e", help="Diminishing returns elasticity beta parameter."),
    adstock_retention: float = typer.Option(0.0, "--adstock-retention", "-a", help="Geometric adstock retention lambda in [0, 1) to scale immediate spike to total cumulative lift."),
    mmm_channel_name: str | None = typer.Option(None, "--mmm-channel-name", help="Optional unified TV channel name (e.g. 'tv_broadcast') to pool stations."),
    api_key: str | None = typer.Option(None, "--key", "-k", help="SpotLift Pro license key (for Meridian and Robyn turnkey exports)."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON summary for AI coding agents and pipelines."),
    tz: str = typer.Option("UTC", "--tz", "-z", help="Timezone if raw airings are provided."),
) -> None:
    """Exports period-aligned calibration datasets and Bayesian priors for PyMC-Marketing, Google Meridian, and Meta Robyn."""
    target_clean = target.lower().strip()
    valid_targets = {"pymc", "meridian", "robyn", "all"}
    if target_clean not in valid_targets:
        console.print(f"[bold red]Invalid target '{target}'. Must be one of: {', '.join(sorted(valid_targets))}[/bold red]")
        raise typer.Exit(code=1)

    if not (0.0 <= adstock_retention < 1.0):
        console.print(f"[bold red]adstock-retention must be in [0.0, 1.0), got {adstock_retention}[/bold red]")
        raise typer.Exit(code=1)

    if spots.suffix.lower() in [".parquet", ".pq"]:
        df = pd.read_parquet(spots)
    else:
        df = pd.read_csv(spots)

    if lift_col not in df.columns:
        if web is None:
            console.print(f"[bold red]Column '{lift_col}' not found in spots file. Please provide --web to run attribution first.[/bold red]")
            raise typer.Exit(code=1)
        console.print("[dim]Running attribution pass prior to MMM export...[/dim]")
        airings_df = sl.load_airings(spots, tz=tz)
        web_df = sl.load_telemetry(web, tz=tz)
        df = sl.analyze_spots(airings=airings_df, web_telemetry=web_df)

    out_dir.mkdir(parents=True, exist_ok=True)
    generated_deliverables: list[tuple[str, Path, str]] = []
    json_summary: dict[str, Any] = {
        "target": target_clean,
        "freq": freq,
        "out_dir": str(out_dir),
        "total_spend": float(df[cost_col].sum()) if cost_col in df.columns else 0.0,
        "total_direct_lift": float(df[lift_col].sum()) if lift_col in df.columns else 0.0,
        "files": {},
    }

    # 1. PyMC-Marketing / Generic Priors
    if target_clean in ("pymc", "all"):
        pymc_df = sl.export_pymc_lift_test(
            df,
            mmm_channel_name=mmm_channel_name,
            channel_col=channel_col,
            timestamp_col=timestamp_col,
            cost_col=cost_col,
            lift_col=lift_col,
            freq=freq,
            elasticity=elasticity,
            adstock_retention=adstock_retention,
        )
        pymc_path = out_dir / "pymc_lift_test.csv"
        pymc_df.to_csv(pymc_path, index=False)
        generated_deliverables.append(("PyMC-Marketing Lift Test", pymc_path, f"{len(pymc_df)} calibration periods"))
        json_summary["files"]["pymc_lift_test"] = str(pymc_path)

        mmm_priors = sl.export_mmm_priors(
            df,
            channel_col=channel_col,
            timestamp_col=timestamp_col,
            cost_col=cost_col,
            lift_col=lift_col,
            freq=freq,
            default_elasticity=elasticity,
            adstock_retention=adstock_retention,
        )
        priors_path = out_dir / "mmm_priors.json"
        priors_path.write_text(json.dumps(mmm_priors, indent=2), encoding="utf-8")
        generated_deliverables.append(("Multi-Framework Priors JSON", priors_path, "Robyn + Meridian + PyMC"))
        json_summary["files"]["mmm_priors"] = str(priors_path)
        json_summary["priors"] = mmm_priors

    # 2. Google Meridian
    if target_clean in ("meridian", "all"):
        effective_key = api_key or os.getenv("SPOTLIFT_API_KEY")
        if is_pro_available() and effective_key:
            meridian_pack = sl.export_meridian_package(
                spots_df=df,
                api_key=effective_key,
                channel_col=channel_col,
                timestamp_col=timestamp_col,
                cost_col=cost_col,
                lift_col=lift_col,
                freq=freq,
                elasticity=elasticity,
                adstock_retention=adstock_retention,
                mmm_channel_name=mmm_channel_name,
                output_dir=out_dir,
            )
            calib_file = out_dir / "calibration_data.csv"
            spec_file = out_dir / "meridian_model_spec.yaml"
            generated_deliverables.append(("Google Meridian Calibration Data (Pro)", calib_file, f"{len(meridian_pack['calibration_df'])} periods"))
            generated_deliverables.append(("Google Meridian ModelSpec YAML (Pro)", spec_file, "LogNormal Hill Priors"))
            json_summary["files"]["meridian_calibration_data"] = str(calib_file)
            json_summary["files"]["meridian_model_spec"] = str(spec_file)
        else:
            if "mmm_priors" not in locals():
                mmm_priors = sl.export_mmm_priors(
                    df,
                    channel_col=channel_col,
                    timestamp_col=timestamp_col,
                    cost_col=cost_col,
                    lift_col=lift_col,
                    freq=freq,
                    default_elasticity=elasticity,
                    adstock_retention=adstock_retention,
                )
            meridian_priors = mmm_priors["google_meridian_priors"]
            meridian_path = out_dir / "meridian_priors.json"
            meridian_path.write_text(json.dumps(meridian_priors, indent=2), encoding="utf-8")
            generated_deliverables.append(("Google Meridian Hill Priors (Open-Core)", meridian_path, "half_saturation + slope"))
            json_summary["files"]["meridian_priors"] = str(meridian_path)
            if not json_output:
                console.print("[dim]Tip: Activate SpotLift Pro (`spotlift auth --key ...`) to export turnkey Meridian calibration_data.csv & ModelSpec YAML.[/dim]")

    # 3. Meta Robyn
    if target_clean in ("robyn", "all"):
        effective_key = api_key or os.getenv("SPOTLIFT_API_KEY")
        if is_pro_available() and effective_key:
            robyn_pack = sl.export_robyn_package(
                spots_df=df,
                api_key=effective_key,
                channel_col=channel_col,
                timestamp_col=timestamp_col,
                cost_col=cost_col,
                lift_col=lift_col,
                freq=freq,
                elasticity=elasticity,
                adstock_retention=adstock_retention,
                mmm_channel_name=mmm_channel_name,
                output_dir=out_dir,
            )
            robyn_csv = out_dir / "calibration_input.csv"
            robyn_r = out_dir / "run_robyn_calibration.R"
            generated_deliverables.append(("Meta Robyn Calibration Input (Pro)", robyn_csv, f"{len(robyn_pack['calibration_df'])} periods"))
            generated_deliverables.append(("Meta Robyn Calibration R Script (Pro)", robyn_r, "Turnkey R Execution Script"))
            json_summary["files"]["robyn_calibration_input"] = str(robyn_csv)
            json_summary["files"]["robyn_r_script"] = str(robyn_r)
        else:
            if "mmm_priors" not in locals():
                mmm_priors = sl.export_mmm_priors(
                    df,
                    channel_col=channel_col,
                    timestamp_col=timestamp_col,
                    cost_col=cost_col,
                    lift_col=lift_col,
                    freq=freq,
                    default_elasticity=elasticity,
                    adstock_retention=adstock_retention,
                )
            robyn_priors = mmm_priors["meta_robyn_hyperparameters"]
            robyn_path = out_dir / "robyn_hyperparameters.json"
            robyn_path.write_text(json.dumps(robyn_priors, indent=2), encoding="utf-8")
            generated_deliverables.append(("Meta Robyn Hyperparameters (Open-Core)", robyn_path, "alphas + gammas"))
            json_summary["files"]["robyn_hyperparameters"] = str(robyn_path)
            if not json_output:
                console.print("[dim]Tip: Activate SpotLift Pro (`spotlift auth --key ...`) to export turnkey Robyn calibration_input.csv & run_robyn_calibration.R.[/dim]")

    if json_output:
        print(json.dumps(json_summary, indent=2))
    else:
        table = Table(title=f"SpotLift MMM Calibration Exporter (Target: {target_clean.upper()})")
        table.add_column("Deliverable", style="cyan", no_wrap=True)
        table.add_column("File Path", style="green")
        table.add_column("Details", style="dim")
        for deliv, pth, details in generated_deliverables:
            table.add_row(deliv, str(pth), details)
        console.print(table)
        console.print(f"\n[green]✔ All {target_clean.upper()} calibration deliverables successfully saved to:[/] {out_dir}\n")


if __name__ == "__main__":
    app()
