# Python API Reference

Complete reference for all functions, classes, and contracts in the `spotlift` open-core library.

---

## Attribution Core

### `spotlift.analyze_spots()`

The primary high-frequency linear TV attribution function.

```python
spotlift.analyze_spots(
    airings: pd.DataFrame,
    telemetry: pd.DataFrame,
    window_minutes: int = 6,
    baseline_fn: Optional[Callable] = None,
    collision_attribution: str = "weighted_share",
    apply_cr_model: bool = True,
    conversions_source: str = "ga4_conversions",
    cr_window_hours: int = 1,
    clip_negative: bool = False,
) -> pd.DataFrame
```

#### Parameters

* **`airings`** (*pd.DataFrame*): Broadcast airings schedule conforming to `AiringLogSchema` (columns: `spot_id`, `timestamp`, `channel`, `creative_id`, `cost`, `grp`).
* **`telemetry`** (*pd.DataFrame*): Minute-level web visits stream conforming to `TelemetryStreamSchema` (columns: `timestamp`, `value`, `channel_source`).
* **`window_minutes`** (*int*, default `6`): Half-open response window duration $[t_0, t_0 + W)$ in minutes.
* **`baseline_fn`** (*Callable*, optional): Custom baseline estimator conforming to `BaselineFn`. Defaults to `compute_diurnal_baseline`. Pass `simple_mean_baseline` for short-history campaigns.
* **`collision_attribution`** (*str*, default `"weighted_share"`): Attribution algorithm for overlapping spots (`"weighted_share"` or `"naive_proportional"`).
* **`apply_cr_model`** (*bool*, default `True`): If `True` and conversion events are present in telemetry, bridges session lift to key events via local hourly conversion rates.
* **`conversions_source`** (*str*, default `"ga4_conversions"`): Label in `telemetry["channel_source"]` representing conversion events.
* **`cr_window_hours`** (*int*, default `1`): Half-width of the hourly neighborhood for conversion rate calculation.
* **`clip_negative`** (*bool*, default `False`): If `False`, preserves signed lift to avoid upward rectification noise bias. If `True`, clamps negative lift at `0.0`.

#### Returns

* **`pd.DataFrame`**: Enriched DataFrame with spot-level attribution metrics (`baseline_volume`, `observed_volume`, `incremental_lift`, `cpiv`, `conversion_rate`, `key_event_response`, `collision_cluster_id`, `collision_method`).

---

## Data Ingestion & Loaders

### `spotlift.load_airings()`

Loads and validates a broadcast airings log from a CSV file path, buffer, or DataFrame.

```python
spotlift.load_airings(filepath_or_df: Union[str, Path, pd.DataFrame]) -> pd.DataFrame
```

* Validates required columns (`spot_id`, `timestamp`, `channel`, `creative_id`, `cost`).
* Parses and normalizes timestamps with explicit timezone handling.
* Fills missing `grp` with `0.0`.

---

### `spotlift.load_telemetry()`

Loads and validates minute-level digital telemetry.

```python
spotlift.load_telemetry(
    filepath_or_df: Union[str, Path, pd.DataFrame],
    zero_fill_gaps: bool = False,
) -> pd.DataFrame
```

* Verifies strict monotonic minute increments.
* Checks for missing minutes. If `zero_fill_gaps=True`, fills missing timestamps with `0.0`; otherwise raises `TelemetryGapError`.

---

## Baseline Estimators

### `spotlift.compute_diurnal_baseline()`

Calculates the decay-weighted cyclic rolling baseline.

```python
spotlift.compute_diurnal_baseline(
    telemetry_series: pd.Series,
    spot_timestamps: list[pd.Timestamp],
    window_minutes: int = 6,
) -> tuple[pd.Series, dict[pd.Timestamp, float]]
```

Returns a tuple of `(calibrated_baseline_series, scaling_factors_dict)`.

---

### `spotlift.simple_mean_baseline()`

Fallback baseline computing the pre-spot moving average for short-history flights without multi-week diurnal history.

```python
spotlift.simple_mean_baseline(
    telemetry_series: pd.Series,
    spot_timestamps: list[pd.Timestamp],
    window_minutes: int = 6,
    pre_window_minutes: int = 15,
) -> pd.Series
```

---

## Collision Mathematics

### `spotlift.compute_continuous_weighted_share()`

Analytical exponential-decay weighted share attribution for overlapping broadcast collision clusters.

```python
spotlift.compute_continuous_weighted_share(
    cluster_df: pd.DataFrame,
    telemetry_series: pd.Series,
    baseline_series: pd.Series,
    window_minutes: int = 6,
    half_life_minutes: float = 1.5,
) -> dict[Any, float]
```

Returns a dictionary mapping each `spot_id` to its attributed incremental lift.

---

## Conversion Rate Bridge

### `spotlift.estimate_conversion_rate_for_spot()`

Calculates the volume-weighted conversion rate for a spot based on the surrounding hourly window.

```python
spotlift.estimate_conversion_rate_for_spot(
    spot_timestamp: pd.Timestamp,
    telemetry_df: pd.DataFrame,
    conversions_source: str = "ga4_conversions",
    window_hours: int = 1,
) -> float
```

Seamlessly crosses midnight boundaries using continuous timestamp slices.

---

### `spotlift.apply_conversion_model()`

Enriches an attributed spots DataFrame with `conversion_rate` and `key_event_response`.

```python
spotlift.apply_conversion_model(
    results: pd.DataFrame,
    telemetry: pd.DataFrame,
    conversions_source: str = "ga4_conversions",
    window_hours: int = 1,
) -> pd.DataFrame
```

---

## Clean Room SQL Generators

### `spotlift.generate_ga4_bigquery_sql()`

Generates a production Google BigQuery SQL query extracting minute-level direct/organic sessions and conversion events.

```python
spotlift.generate_ga4_bigquery_sql(
    project_id: str,
    dataset: str,
    start_date: str,
    end_date: str,
) -> str
```

---

### `spotlift.generate_amc_telemetry_sql()`

Generates an Amazon Marketing Cloud (AMC) clean room SQL query extracting hourly ordered units and sales.

```python
spotlift.generate_amc_telemetry_sql(
    start_date: str,
    end_date: str,
) -> str
```

---

## SpotLift Pro Dispatch

### `spotlift.install_pro()`

Validates a commercial license key and unlocks Pro capabilities.

```python
spotlift.install_pro(
    api_key: str,
    index_url: Optional[str] = None,
    local_path: Optional[str] = None,
) -> bool
```

---

### `spotlift.analyze_omnichannel_pro()`

Pro entry point dispatches to compiled Cython binaries for Shifted-Gamma EM deconvolution, AMC retail halo, and Excel export.

```python
spotlift.analyze_omnichannel_pro(
    airings: pd.DataFrame,
    web_telemetry: pd.DataFrame,
    amazon_telemetry: Optional[pd.DataFrame] = None,
    window_minutes: int = 6,
    export_excel: Optional[str] = None,
    white_label_config: Optional[dict] = None,
    clip_negative: bool = False,
    apply_cr_model: bool = True,
    conversions_source: str = "ga4_conversions",
    cr_window_hours: int = 1,
) -> dict
```
