"""Command-line interface for spotlift using Typer."""

from typing import Optional
import typer
import pandas as pd
from pathlib import Path

from spotlift.core.single_spot import analyze_spots
from spotlift.pro.installer import verify_and_install

app = typer.Typer()

@app.command()
def run(
    spots: Path = typer.Option(..., exists=True, help="CSV of TV airings"),
    telemetry: Path = typer.Option(..., exists=True, help="Parquet or CSV telemetry"),
    metric: str = typer.Option("value", help="Metric column name"),
    window: int = typer.Option(8, help="Post-spot window in minutes"),
    output: Optional[Path] = typer.Option(None, help="Output CSV path"),
):
    """Run spot-by-spot attribution and export results."""
    # Load inputs permissively
    if spots.suffix.lower() == ".csv":
        airings = pd.read_csv(spots)
    else:
        airings = pd.read_parquet(spots)

    if telemetry.suffix.lower() in (".parquet", ".pq"):
        telemetry_df = pd.read_parquet(telemetry)
    else:
        telemetry_df = pd.read_csv(telemetry)

    res = analyze_spots(
        airings=airings,
        telemetry=telemetry_df,
        metric_col=metric,
        window_minutes=window,
    )

    if output:
        res.to_csv(output, index=False)
        typer.echo(f"Results exported to: {output}")
    else:
        typer.echo(res.head().to_string())


@app.command()
def inspect(spots: Path = typer.Option(..., exists=True), window: int = 8):
    """Quick inspection of spot file with overlap diagnostics."""
    import pandas as pd
    from spotlift.io.loaders import validate_airings_df
    df = pd.read_csv(spots)
    validated = validate_airings_df(df)
    typer.echo(validated.head().to_string())


app_auth = typer.Typer()
app.add_typer(app_auth, name="auth")

@app_auth.command("install-pro")
def auth_install_pro(key: str = typer.Option(..., help="SpotLift Pro license key")):
    """Verify and install SpotLift Pro binary/wheel using provided license key."""
    try:
        verify_and_install(key)
        typer.echo("spotlift-pro installed successfully.")
    except Exception as exc:
        typer.echo(f"Failed to install pro: {exc}")
