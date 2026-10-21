"""Amazon Marketing Cloud (AMC) ingestion pipeline.

Ported from the Revitive R scripts ``amz_response.R`` and
``amz_response_v2.R``.  This is a **pure-Python** module — no compiled
``spotlift_pro`` extension is required — so it imports and runs standalone
even when the Pro binary is not installed.

Pipeline overview
-----------------
1.  Refresh the Amazon LWA OAuth access token.
2.  For each TV spot build a per-spot AMC SQL sub-query (before / after window).
3.  Batch the sub-queries with ``UNION ALL`` (40 per batch by default) to stay
    within AMC workflow rate limits.
4.  Create one AMC workflow execution per batch.
5.  Poll each workflow until it reaches a terminal status.
6.  Download the CSV report(s) for every successful workflow.
7.  Combine the reports, join the spot metadata back on, and return a tidy
    ``pandas.DataFrame``.

If a SQLAlchemy ``connection`` is supplied the results can also be upserted
into a database table (delete-then-insert, mirroring the R
``dbWithTransaction`` pattern).
"""

from __future__ import annotations

import io
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx
import pandas as pd

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

TOKEN_URL = "https://api.amazon.co.uk/auth/o2/token"
AMC_BASE_URL = "https://advertising-api.amazon.com/amc/reporting"
TERMINAL_STATUSES: tuple[str, ...] = ("SUCCEEDED", "FAILED", "REJECTED", "CANCELLED")
DEFAULT_QUERIES_PER_CHUNK = 40
DEFAULT_POLL_INTERVAL_SECONDS = 5
DEFAULT_MAX_POLL_SECONDS = 300
DEFAULT_BEFORE_MINUTES = 60
DEFAULT_AFTER_MINUTES = 15
DEFAULT_SPOT_TIMEZONE = "Europe/Berlin"
AMC_ACCEPT_HEADER = "application/vnd.amcworkflowexecutions.v1+json"


# ── Exceptions ───────────────────────────────────────────────────────────────


class AMCIngestionError(Exception):
    """Raised when any step of the AMC ingestion pipeline fails."""


# ── Configuration ───────────────────────────────────────────────────────────


@dataclass
class AMCConfig:
    """Holds all credentials and identifiers needed to talk to the AMC API."""

    instance_id: str
    advertiser_id: str
    marketplace_id: str
    client_id: str
    client_secret: str
    refresh_token: str

    # Optional overrides (rarely changed)
    token_url: str = TOKEN_URL
    base_url: str = AMC_BASE_URL
    spot_timezone: str = DEFAULT_SPOT_TIMEZONE


# ── Internal helpers ────────────────────────────────────────────────────────


def _auth_headers(config: AMCConfig, access_token: str, *, accept: str | None = None) -> dict[str, str]:
    """Build the standard AMC auth header dict."""
    headers: dict[str, str] = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientID": config.client_id,
        "Amazon-Advertising-API-AdvertiserId": config.advertiser_id,
        "Amazon-Advertising-API-MarketplaceId": config.marketplace_id,
        "Content-Type": "application/json",
    }
    if accept:
        headers["Accept"] = accept
    return headers


def _fmt_ts(dt: datetime) -> str:
    """Format a datetime as ``YYYY-MM-DDTHH:MM:SS`` (AMC's expected format)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ── OAuth ───────────────────────────────────────────────────────────────────


def refresh_access_token(config: AMCConfig, client: httpx.Client) -> str:
    """Refresh the Amazon LWA access token.

    POSTs to ``config.token_url`` with the refresh-token grant and returns
    the ``access_token`` from the response.

    Raises:
        AMCIngestionError: if the token endpoint returns a non-200 status.
    """
    logger.info("Refreshing Amazon LWA access token from %s", config.token_url)
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": config.refresh_token,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
    }
    try:
        resp = client.post(config.token_url, data=payload)
    except httpx.RequestError as exc:
        raise AMCIngestionError(f"Network error refreshing access token: {exc}") from exc

    if resp.status_code != 200:
        body = resp.text
        raise AMCIngestionError(
            f"Failed to refresh access token (HTTP {resp.status_code}): {body}"
        )

    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise AMCIngestionError("Token endpoint returned no access_token field")
    logger.info("Amazon access token refreshed successfully")
    return token


# ── Workflow creation ───────────────────────────────────────────────────────


def create_workflow(
    config: AMCConfig,
    access_token: str,
    sql_query: str,
    time_start: datetime,
    time_end: datetime,
    client: httpx.Client,
) -> str:
    """Create a single AMC workflow execution.

    POSTs to ``/amc/reporting/{instanceId}/workflowExecutions`` with the SQL
    query body and explicit time window.

    Returns:
        The ``workflowExecutionId`` string.

    Raises:
        AMCIngestionError: if the request fails or the response lacks an id.
    """
    url = f"{config.base_url}/{config.instance_id}/workflowExecutions"
    body = {
        "workflow": {"sqlQuery": sql_query},
        "timeWindowType": "EXPLICIT",
        "timeWindowStart": _fmt_ts(time_start),
        "timeWindowEnd": _fmt_ts(time_end),
        "timeWindowTimeZone": "UTC",
    }
    headers = _auth_headers(config, access_token)

    logger.debug("Creating AMC workflow at %s", url)
    try:
        resp = client.post(url, json=body, headers=headers)
    except httpx.RequestError as exc:
        raise AMCIngestionError(f"Network error creating workflow: {exc}") from exc

    if resp.status_code != 200:
        raise AMCIngestionError(
            f"Workflow creation failed (HTTP {resp.status_code}): {resp.text}"
        )

    data = resp.json()
    workflow_id = data.get("workflowExecutionId")
    if not workflow_id:
        raise AMCIngestionError(
            f"Workflow creation response missing workflowExecutionId: {data}"
        )
    logger.info("Created AMC workflow %s", workflow_id)
    return workflow_id


# ── Workflow polling ─────────────────────────────────────────────────────────


def poll_workflow(
    config: AMCConfig,
    access_token: str,
    workflow_id: str,
    client: httpx.Client,
    *,
    max_poll_seconds: int = DEFAULT_MAX_POLL_SECONDS,
    poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Poll a workflow execution status until it reaches a terminal state.

    GETs ``/workflowExecutions/{workflowId}`` every *poll_interval* seconds
    until the ``status`` field is one of ``TERMINAL_STATUSES`` or the
    *max_poll_seconds* timeout is exceeded.

    Returns:
        The final workflow status body dict (contains ``status``,
        ``statusReason``, ``error``, etc.).

    Raises:
        AMCIngestionError: if the poll times out or the GET fails.
    """
    url = f"{config.base_url}/{config.instance_id}/workflowExecutions/{workflow_id}"
    headers = _auth_headers(config, access_token, accept=AMC_ACCEPT_HEADER)

    elapsed = 0.0
    status_body: dict[str, Any] = {}
    while True:
        try:
            resp = client.get(url, headers=headers)
        except httpx.RequestError as exc:
            raise AMCIngestionError(
                f"Network error polling workflow {workflow_id}: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise AMCIngestionError(
                f"Workflow status poll failed (HTTP {resp.status_code}): {resp.text}"
            )

        status_body = resp.json()
        status = status_body.get("status", "UNKNOWN")
        logger.debug("Workflow %s status: %s", workflow_id, status)

        if status in TERMINAL_STATUSES:
            return status_body

        if elapsed >= max_poll_seconds:
            raise AMCIngestionError(
                f"Workflow {workflow_id} did not reach a terminal status within "
                f"{max_poll_seconds}s (last status: {status})"
            )

        time.sleep(poll_interval)
        elapsed += poll_interval


# ── Report download ──────────────────────────────────────────────────────────


def get_download_urls(
    config: AMCConfig,
    access_token: str,
    workflow_id: str,
    client: httpx.Client,
) -> list[str]:
    """Fetch the presigned download URLs for a completed workflow's reports.

    GETs ``/workflowExecutions/{workflowId}/downloadUrls`` and returns the
    list of URLs from the ``downloadUrls`` field.
    """
    url = (
        f"{config.base_url}/{config.instance_id}/workflowExecutions/{workflow_id}"
        f"/downloadUrls"
    )
    headers = _auth_headers(config, access_token)
    try:
        resp = client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise AMCIngestionError(
            f"Network error fetching download URLs for {workflow_id}: {exc}"
        ) from exc

    if resp.status_code != 200:
        raise AMCIngestionError(
            f"Download URL request failed (HTTP {resp.status_code}): {resp.text}"
        )

    data = resp.json()
    urls = data.get("downloadUrls", [])
    if isinstance(urls, str):
        urls = [urls]
    logger.info("Workflow %s returned %d download URL(s)", workflow_id, len(urls))
    return urls


def download_report(download_url: str, client: httpx.Client) -> pd.DataFrame:
    """Download a CSV report from a presigned URL and parse it into a DataFrame.

    Also normalizes the ``expr$0`` column that AMC sometimes emits for
    un-aliased ``SUM(conversions)`` expressions back to ``conversions``.
    """
    try:
        resp = client.get(download_url)
    except httpx.RequestError as exc:
        raise AMCIngestionError(f"Network error downloading report: {exc}") from exc

    if resp.status_code != 200:
        raise AMCIngestionError(
            f"Report download failed (HTTP {resp.status_code}): {resp.text[:200]}"
        )

    csv_text = resp.content.decode("utf-8")
    df = pd.read_csv(io.StringIO(csv_text))

    # Normalise the AMC-internal ``expr$0`` / ``expr0`` alias that appears when
    # the SQL omits an explicit AS alias for the SUM column.
    rename_map: dict[str, str] = {}
    for col in df.columns:
        if str(col).strip() in ("expr$0", "expr0", "Expr$0", "Expr0"):
            rename_map[col] = "conversions"
    if rename_map:
        df = df.rename(columns=rename_map)

    return df


# ── SQL query builders ──────────────────────────────────────────────────────


def build_spot_sub_query(
    spot_id: str,
    kind: str,
    ts_start_iso: str,
    ts_end_iso: str,
) -> str:
    """Build a single per-spot AMC SQL sub-query.

    Mirrors ``build_sub_query()`` from the R v2 script — selects the spot_id
    and kind as literal columns, sums conversions grouped by event subtype /
    event name, within the given UTC window.
    """
    # Escape single quotes in the spot_id / kind to avoid SQL injection
    safe_spot_id = spot_id.replace("'", "''")
    safe_kind = kind.replace("'", "''")
    return (
        "SELECT\n"
        f"  '{safe_spot_id}' AS spot_id,\n"
        f"  '{safe_kind}' AS kind,\n"
        "  conversion_event_name,\n"
        "  event_subtype,\n"
        "  SUM(conversions) AS conversions\n"
        "FROM conversions\n"
        f"WHERE event_dt_utc >= '{ts_start_iso}'\n"
        f"  AND event_dt_utc < '{ts_end_iso}'\n"
        "GROUP BY\n"
        "  event_subtype,\n"
        "  conversion_event_name"
    )


def chunk_queries(queries: Sequence[str], chunk_size: int) -> list[str]:
    """Split a list of SQL sub-queries into batches joined by ``UNION ALL``.

    Mirrors ``chunk_queries()`` from the R v2 script.
    """
    return [
        "\nUNION ALL\n".join(queries[i : i + chunk_size])
        for i in range(0, len(queries), chunk_size)
    ]


def build_batched_queries(
    spots: pd.DataFrame,
    *,
    before_minutes: int = DEFAULT_BEFORE_MINUTES,
    after_minutes: int = DEFAULT_AFTER_MINUTES,
    queries_per_chunk: int = DEFAULT_QUERIES_PER_CHUNK,
    spot_timezone: str = DEFAULT_SPOT_TIMEZONE,
) -> tuple[list[str], datetime, datetime]:
    """Build the batched UNION ALL SQL queries from a TV spots DataFrame.

    For each spot two sub-queries are generated (one for the *before* window
    and one for the *after* window).  Sub-queries are chunked into batches of
    *queries_per_chunk* (default 40) and joined with ``UNION ALL``.

    The input DataFrame must have at least:
      * ``spot_id`` — unique spot identifier
      * ``timestamp`` — broadcast time (naive datetimes are assumed to be in
        *spot_timezone*; tz-aware datetimes are converted to UTC)

    Returns:
        A tuple of ``(list_of_sql_queries, time_start, time_end)`` where
        *time_start* / *time_end* are the overall UTC window that spans every
        sub-query (used for the AMC workflow timeWindowStart/End).
    """
    if spots.empty:
        return [], datetime.now(tz=timezone.utc), datetime.now(tz=timezone.utc)

    ts_series = pd.to_datetime(spots["timestamp"])
    if ts_series.dt.tz is None:
        ts_series = ts_series.dt.tz_localize(spot_timezone)
    ts_series = ts_series.dt.tz_convert("UTC")

    before_delta = pd.Timedelta(minutes=before_minutes)
    after_delta = pd.Timedelta(minutes=after_minutes)

    ts_before = ts_series - before_delta
    ts_after = ts_series + after_delta

    spot_ids = spots["spot_id"].astype(str).tolist()

    before_queries: list[str] = []
    after_queries: list[str] = []
    for i, spot_id in enumerate(spot_ids):
        ts_start_iso = _fmt_ts(ts_before.iloc[i].to_pydatetime())
        ts_end_iso = _fmt_ts(ts_series.iloc[i].to_pydatetime())
        before_queries.append(
            build_spot_sub_query(spot_id, "before", ts_start_iso, ts_end_iso)
        )

        ts_start_iso = _fmt_ts(ts_series.iloc[i].to_pydatetime())
        ts_end_iso = _fmt_ts(ts_after.iloc[i].to_pydatetime())
        after_queries.append(
            build_spot_sub_query(spot_id, "after", ts_start_iso, ts_end_iso)
        )

    queries = chunk_queries(before_queries, queries_per_chunk) + chunk_queries(
        after_queries, queries_per_chunk
    )

    time_start = ts_before.min().to_pydatetime()
    time_end = ts_after.max().to_pydatetime()

    logger.info(
        "Built %d batched AMC queries from %d spots (chunk=%d)",
        len(queries),
        len(spots),
        queries_per_chunk,
    )
    return queries, time_start, time_end


# ── DB upsert helper ─────────────────────────────────────────────────────────


def upsert_to_db(
    results: pd.DataFrame,
    con: Connection,
    table_name: str,
    *,
    spot_id_column: str = "spot_id",
) -> int:
    """Upsert the results DataFrame into a database table via SQLAlchemy.

    Mirrors the R ``dbWithTransaction`` pattern: delete all existing rows for
    the spot_ids present in *results*, then append the new rows in a single
    transaction.

    Args:
        results: The DataFrame returned by :func:`run_amc_ingestion`.
        con: A SQLAlchemy ``Connection`` (or engine) to use.
        table_name: The target table name.
        spot_id_column: The column used to identify which rows to delete.

    Returns:
        The number of rows inserted.
    """
    from sqlalchemy import text  # local import — keeps the module importable
                                       # without SQLAlchemy installed

    if results.empty:
        logger.info("No rows to upsert into %s", table_name)
        return 0

    unique_spot_ids = results[spot_id_column].dropna().unique().tolist()
    if not unique_spot_ids:
        logger.warning("No valid spot_ids found in results — skipping upsert")
        return 0

    quoted_ids = ", ".join(
        "'" + str(sid).replace("'", "''") + "'" for sid in unique_spot_ids
    )
    delete_sql = f"DELETE FROM {table_name} WHERE {spot_id_column} IN ({quoted_ids})"

    with con.begin():  # transactional
        con.execute(text(delete_sql))
        results.to_sql(
            table_name,
            con=con,
            if_exists="append",
            index=False,
            method=None,
        )

    logger.info(
        "Upserted %d rows into %s (deleted %d existing spot_id rows)",
        len(results),
        table_name,
        len(unique_spot_ids),
    )
    return len(results)


# ── Main entry point ─────────────────────────────────────────────────────────


def run_amc_ingestion(
    config: AMCConfig,
    spots: pd.DataFrame,
    *,
    before_minutes: int = DEFAULT_BEFORE_MINUTES,
    after_minutes: int = DEFAULT_AFTER_MINUTES,
    max_poll_seconds: int = DEFAULT_MAX_POLL_SECONDS,
    poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
    queries_per_chunk: int = DEFAULT_QUERIES_PER_CHUNK,
    db_connection: Connection | None = None,
    db_table_name: str | None = None,
    http_client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Run the full AMC ingestion pipeline and return a tidy conversions DataFrame.

    This is the main entry point.  It takes a DataFrame of TV spots (with
    columns ``spot_id``, ``timestamp``, and ``format`` or ``spot_length``),
    queries Amazon Marketing Cloud for conversion events around each spot,
    and returns a combined DataFrame.

    Args:
        config: An :class:`AMCConfig` with AMC credentials.
        spots: DataFrame with columns ``spot_id``, ``timestamp``, and
            ``format`` (or ``spot_length``).
        before_minutes: Minutes *before* the spot to query (default: 60).
        after_minutes: Minutes *after* the spot to query (default: 15).
        max_poll_seconds: Maximum seconds to poll each workflow (default: 300).
        poll_interval: Seconds between status polls (default: 5).
        queries_per_chunk: Number of UNION ALL sub-queries per workflow (default: 40).
        db_connection: Optional SQLAlchemy connection.  If provided (and
            ``db_table_name`` is set) the results are upserted into the table.
        db_table_name: Table name for the optional DB upsert.
        http_client: Optional pre-configured ``httpx.Client``.  If omitted a
            default client is created and closed at the end.

    Returns:
        A ``pandas.DataFrame`` with columns: ``spot_id``, ``spot_length``,
        ``spot_time``, ``kind`` (``"pre"`` or ``"post"``),
        ``conversion_event_name``, ``event_subtype``, ``conversions``,
        ``be_timestamp``.

    Raises:
        AMCIngestionError: if any step of the pipeline fails.
    """
    if spots.empty:
        logger.info("No eligible spots — returning empty DataFrame")
        return pd.DataFrame(
            columns=[
                "spot_id",
                "spot_length",
                "spot_time",
                "kind",
                "conversion_event_name",
                "event_subtype",
                "conversions",
                "be_timestamp",
            ]
        )

    # Validate required columns
    required = {"spot_id", "timestamp"}
    missing = required - set(spots.columns)
    if missing:
        raise AMCIngestionError(
            f"Spots DataFrame is missing required column(s): {missing}"
        )

    # ── 1. Build batched queries ───────────────────────────────────────────
    queries, time_start, time_end = build_batched_queries(
        spots,
        before_minutes=before_minutes,
        after_minutes=after_minutes,
        queries_per_chunk=queries_per_chunk,
        spot_timezone=config.spot_timezone,
    )

    if not queries:
        logger.warning("No queries generated from %d spots", len(spots))
        return pd.DataFrame(
            columns=[
                "spot_id",
                "spot_length",
                "spot_time",
                "kind",
                "conversion_event_name",
                "event_subtype",
                "conversions",
                "be_timestamp",
            ]
        )

    logger.info(
        "AMC query window: %s to %s (UTC)",
        time_start.strftime("%Y-%m-%d %H:%M:%S"),
        time_end.strftime("%Y-%m-%d %H:%M:%S"),
    )

    # ── 2. Create HTTP client (if not provided) ─────────────────────────────
    own_client = False
    if http_client is None:
        http_client = httpx.Client(timeout=30.0)
        own_client = True

    try:
        # ── 3. Refresh OAuth token ─────────────────────────────────────────
        access_token = refresh_access_token(config, http_client)

        # ── 4. Create all workflows ─────────────────────────────────────────
        workflow_ids: list[str] = []
        for i, sql in enumerate(queries):
            try:
                wf_id = create_workflow(
                    config, access_token, sql, time_start, time_end, http_client
                )
                workflow_ids.append(wf_id)
            except AMCIngestionError:
                logger.exception("Failed to create workflow %d/%d", i + 1, len(queries))
                raise
            # Small delay to respect rate limits (matching the R script)
            if i < len(queries) - 1:
                time.sleep(0.2)

        logger.info("Created %d AMC workflow(s)", len(workflow_ids))

        # ── 5. Poll all workflows ───────────────────────────────────────────
        statuses: dict[str, dict[str, Any]] = {}
        for wf_id in workflow_ids:
            status_body = poll_workflow(
                config,
                access_token,
                wf_id,
                http_client,
                max_poll_seconds=max_poll_seconds,
                poll_interval=poll_interval,
            )
            statuses[wf_id] = status_body
            logger.info(
                "Workflow %s final status: %s", wf_id, status_body.get("status")
            )

        # Check for failures
        failed = {
            wf_id: body
            for wf_id, body in statuses.items()
            if body.get("status") != "SUCCEEDED"
        }
        if failed:
            for wf_id, body in failed.items():
                logger.error(
                    "Workflow %s failed: status=%s reason=%s error=%s",
                    wf_id,
                    body.get("status"),
                    body.get("statusReason"),
                    body.get("error"),
                )
            raise AMCIngestionError(
                f"{len(failed)} workflow(s) failed: "
                + ", ".join(f"{wf}={body.get('status')}" for wf, body in failed.items())
            )

        # ── 6. Download reports ─────────────────────────────────────────────
        reports: list[pd.DataFrame] = []
        for wf_id in workflow_ids:
            if statuses[wf_id].get("status") != "SUCCEEDED":
                continue
            download_urls = get_download_urls(config, access_token, wf_id, http_client)
            for url_idx, dl_url in enumerate(download_urls):
                if not dl_url:
                    continue
                logger.debug(
                    "Downloading report %d/%d for workflow %s",
                    url_idx + 1,
                    len(download_urls),
                    wf_id,
                )
                report_df = download_report(dl_url, http_client)
                reports.append(report_df)

        logger.info("Downloaded %d AMC report(s)", len(reports))

        # ── 7. Combine reports ──────────────────────────────────────────────
        if not reports:
            logger.warning("No reports downloaded — returning empty DataFrame")
            return pd.DataFrame(
                columns=[
                    "spot_id",
                    "spot_length",
                    "spot_time",
                    "kind",
                    "conversion_event_name",
                    "event_subtype",
                    "conversions",
                    "be_timestamp",
                ]
            )

        combined = pd.concat(reports, ignore_index=True)

        # Map 'before' -> 'pre', 'after' -> 'post' (matching R v2)
        if "kind" in combined.columns:
            combined["kind"] = combined["kind"].replace(
                {"before": "pre", "after": "post"}
            )

        # ── 8. Join spot metadata back on ───────────────────────────────────
        # Determine which column holds the spot length
        spot_length_col = None
        for candidate in ("format", "spot_length"):
            if candidate in spots.columns:
                spot_length_col = candidate
                break

        spot_meta = spots[["spot_id", "timestamp"]].copy()
        if spot_length_col:
            spot_meta["spot_length"] = spots[spot_length_col].values
        else:
            spot_meta["spot_length"] = pd.NA

        spot_meta["spot_id"] = spot_meta["spot_id"].astype(str)
        combined["spot_id"] = combined["spot_id"].astype(str)

        # Rename timestamp -> spot_time before merge
        spot_meta = spot_meta.rename(  # type: ignore[call-overload]
            columns={"timestamp": "spot_time"}
        )
        results: pd.DataFrame = combined.merge(  # type: ignore[no-redef]
            spot_meta, on="spot_id", how="left"
        )

        # ── 9. Add processing timestamp & finalise column order ──────────────
        be_timestamp = pd.Timestamp.now()
        results["be_timestamp"] = be_timestamp

        # Ensure conversions column is numeric
        if "conversions" in results.columns:
            results["conversions"] = pd.to_numeric(
                results["conversions"], errors="coerce"
            )

        final_columns = [
            "spot_id",
            "spot_length",
            "spot_time",
            "kind",
            "conversion_event_name",
            "event_subtype",
            "conversions",
            "be_timestamp",
        ]
        for col in final_columns:
            if col not in results.columns:
                results[col] = pd.NA
        results = results[final_columns]  # type: ignore[assignment]

        spot_id_series: pd.Series = results["spot_id"]  # type: ignore[assignment]
        logger.info(
            "AMC ingestion complete: %d conversion rows for %d spot(s)",
            len(results),
            int(spot_id_series.nunique()),
        )

        # ── 10. Optional DB upsert ───────────────────────────────────────────
        if db_connection is not None and db_table_name:
            upsert_to_db(results, db_connection, db_table_name)

        return results

    finally:
        if own_client:
            http_client.close()


# ── Convenience: run with a config dict ──────────────────────────────────────


def run_amc_ingestion_from_dict(
    config_dict: dict[str, Any],
    spots: pd.DataFrame,
    **kwargs: Any,
) -> pd.DataFrame:
    """Convenience wrapper that builds an :class:`AMCConfig` from a dict.

    The dict must contain the same keys as :class:`AMCConfig` fields
    (``instance_id``, ``advertiser_id``, ``marketplace_id``, ``client_id``,
    ``client_secret``, ``refresh_token``).
    """
    config = AMCConfig(**config_dict)
    return run_amc_ingestion(config, spots, **kwargs)